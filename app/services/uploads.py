"""Parse a single bounded media form only after the route authorizes its caller."""

from fastapi import HTTPException, Request
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser

from app.config import get_settings


class UploadTooLarge(MultiPartException):
    pass


class SingleUploadParser(MultiPartParser):
    completed = False

    def on_end(self) -> None:
        self.completed = True


async def parse_upload(request: Request) -> FormData:
    if request.headers.get("content-type", "").partition(";")[0].strip().lower() != (
        "multipart/form-data"
    ):
        raise HTTPException(422, "Cần gửi một file qua multipart/form-data")
    settings = get_settings()
    limit = (
        max(settings.max_image_size, settings.max_video_size, settings.max_audio_size)
        + 64 * 1024
    )
    length = request.headers.get("content-length")
    if length:
        try:
            size = int(length)
        except ValueError:
            raise HTTPException(400, "Kích thước yêu cầu không hợp lệ") from None
        if size < 0:
            raise HTTPException(400, "Kích thước yêu cầu không hợp lệ")
        if size > limit:
            raise HTTPException(413, "Yêu cầu upload vượt giới hạn")

    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                raise UploadTooLarge("Upload exceeds the request limit")
            yield chunk

    parser = SingleUploadParser(
        request.headers,
        bounded_stream(),
        max_files=1,
        max_fields=1,
        max_part_size=4096,
    )
    try:
        form = await parser.parse()
        if not parser.completed:
            raise MultiPartException("Incomplete multipart body")
        return form
    except BaseException as error:
        # Starlette closes on MultiPartException; also cover malformed input,
        # disconnects and cancellation after the temporary file was opened.
        for temporary in parser._files_to_close_on_error:
            temporary.close()
        if isinstance(error, UploadTooLarge):
            raise HTTPException(413, "Yêu cầu upload vượt giới hạn") from None
        if isinstance(error, (MultiPartException, MultipartParseError)):
            raise HTTPException(
                400, "Form upload không hợp lệ hoặc có quá nhiều file"
            ) from None
        raise
