"""Install Nginx headers with config validation and restoration on failure."""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

INCLUDE = "include /etc/nginx/snippets/eskaylation-security.conf;"


def config_blocks(text: str) -> list[dict]:
    """Find blocks without treating quoted braces as syntax."""
    blocks = []
    stack = []
    boundary = 0
    quote = None
    comment = False
    escaped = False
    for index, char in enumerate(text):
        if comment:
            if char == "\n":
                comment = False
            continue
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "#":
            comment = True
        elif char == "{":
            header = re.sub(r"#[^\n]*", "", text[boundary:index]).strip()
            block = {
                "header": header,
                "start": index,
                "end": None,
                "parent": stack[-1] if stack else None,
            }
            stack.append(block)
            blocks.append(block)
            boundary = index + 1
        elif char == "}":
            if not stack:
                raise ValueError("Unbalanced Nginx config")
            stack.pop()["end"] = index
            boundary = index + 1
        elif char == ";":
            boundary = index + 1
    if stack or quote:
        raise ValueError("Incomplete Nginx config")
    return blocks


def secure_config(text: str) -> str:
    """Cover the production vhost and all its response locations with headers."""
    blocks = config_blocks(text)
    selected = []
    for block in blocks:
        if block["header"] != "server":
            continue
        body = text[block["start"] + 1 : block["end"]]
        names = re.findall(r"(?m)^\s*server_name\s+([^;]+);", body)
        if not any("eskaylation.com" in name.split() for name in names):
            continue
        selected.append(block)
        for child in blocks:
            parent = child["parent"]
            while parent is not None and parent is not block:
                parent = parent["parent"]
            if parent is block and child["header"].startswith("location "):
                selected.append(child)
    if not selected:
        raise ValueError("No eskaylation.com server block found")
    for block in sorted(selected, key=lambda value: value["start"], reverse=True):
        start = block["start"] + 1
        # Only check direct directives, not descendant locations' includes.
        direct = text[start : block["end"]]
        direct = direct.split("location ", 1)[0]
        if INCLUDE not in direct:
            text = text[:start] + "\n    " + INCLUDE + "\n" + text[start:]
    return text


def streaming_upload_config(text: str) -> str:
    """Forward uploads to the authorizing API without proxy disk buffering."""
    blocks = config_blocks(text)
    edits = []
    for block in blocks:
        if not block["header"].startswith("location "):
            continue
        server = block["parent"]
        while server is not None and server["header"] != "server":
            server = server["parent"]
        if server is None:
            continue
        server_body = text[server["start"] + 1 : server["end"]]
        names = re.findall(r"(?m)^\s*server_name\s+([^;]+);", server_body)
        if not any("eskaylation.com" in name.split() for name in names):
            continue
        body = text[block["start"] + 1 : block["end"]]
        if not re.search(r"\bproxy_pass\s+http://127\.0\.0\.1:8000\s*;", body):
            continue
        if any(child["parent"] is block for child in blocks):
            raise ValueError("Review nested proxy locations before enabling streaming")
        if not re.search(r"\bproxy_http_version\s+1\.1\s*;", body):
            raise ValueError("Upload streaming requires an existing HTTP/1.1 upstream")
        if re.search(r"\bproxy_request_buffering\s+", body):
            body = re.sub(
                r"\bproxy_request_buffering\s+\S+\s*;",
                "proxy_request_buffering off;",
                body,
            )
        else:
            body = "\n        proxy_request_buffering off;" + body
        edits.append((block["start"] + 1, block["end"], body))
    if not edits:
        raise ValueError("No production API proxy location found")
    for start, end, body in sorted(edits, reverse=True):
        text = text[:start] + body + text[end:]
    return text


def atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(config: Path, snippet: Path, *, stream_uploads: bool = False) -> None:
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("Run this installer as root on the VPS")
    config = config.resolve(strict=True)
    if not config.is_relative_to(Path("/etc/nginx")):
        raise ValueError("Config must resolve inside /etc/nginx")
    original = config.read_bytes()
    updated = secure_config(original.decode()).encode()
    if stream_uploads:
        updated = streaming_upload_config(updated.decode()).encode()
    destination = Path("/etc/nginx/snippets/eskaylation-security.conf")
    previous = destination.read_bytes() if destination.exists() else None
    backup = Path("/var/backups/eskaylation") / ("nginx-" + uuid4().hex)
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(config, backup / "site.conf")
    if previous is not None:
        (backup / "security.conf").write_bytes(previous)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write(destination, snippet.read_bytes())
        atomic_write(config, updated)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except Exception:
        atomic_write(config, original)
        if previous is None:
            destination.unlink(missing_ok=True)
        else:
            atomic_write(destination, previous)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
        raise
    print("Nginx security headers installed; backup: " + str(backup))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--stream-uploads", action="store_true")
    args = parser.parse_args()
    if args.apply:
        snippet = (
            Path(__file__).resolve().parents[1] / "deploy/nginx/security-headers.conf"
        )
        install(args.config, snippet, stream_uploads=args.stream_uploads)
    else:
        updated = secure_config(args.config.read_text())
        print(streaming_upload_config(updated) if args.stream_uploads else updated)


if __name__ == "__main__":
    main()
