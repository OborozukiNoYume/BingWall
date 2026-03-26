from __future__ import annotations

from io import BytesIO

from PIL import Image


def build_test_jpeg_bytes(
    *,
    width: int = 1920,
    height: int = 1080,
    color: tuple[int, int, int] = (32, 96, 160),
) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()
