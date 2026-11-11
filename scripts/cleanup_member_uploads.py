"""Preview expired member uploads; --apply removes only eligible temporary media."""

import argparse
import asyncio
import json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the bounded cleanup; default is a preview",
    )
    args = parser.parse_args()

    async def run():
        from app.db import SessionLocal, engine
        from app.services.member_upload_cleanup import cleanup_expired

        try:
            async with SessionLocal() as session:
                print(json.dumps(await cleanup_expired(session, apply=args.apply)))
        finally:
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
