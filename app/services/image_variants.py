from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image
from PIL import ImageOps
from PIL import UnidentifiedImageError

from app.domain.resource_variants import RESOURCE_TYPE_PREVIEW
from app.domain.resource_variants import RESOURCE_TYPE_THUMBNAIL
from app.domain.resource_variants import ResourceType

THUMBNAIL_MAX_SIZE = (480, 270)
PREVIEW_MAX_SIZE = (1600, 900)


@dataclass(frozen=True, slots=True)
class LoadedImage:
    image: Image.Image
    width: int
    height: int
    mime_type: str


@dataclass(frozen=True, slots=True)
class GeneratedVariant:
    content: bytes
    file_ext: str
    mime_type: str
    width: int
    height: int


def load_image_bytes(content: bytes, *, fallback_mime_type: str | None) -> LoadedImage:
    if not content:
        raise ValueError("downloaded image is empty")

    try:
        with Image.open(BytesIO(content)) as opened_image:
            normalized = ImageOps.exif_transpose(opened_image)
            normalized.load()
            image = normalized.copy()
            width, height = image.size
            detected_mime_type = Image.MIME.get(opened_image.format or "")
    except UnidentifiedImageError as exc:
        raise ValueError("downloaded file is not a valid image") from exc

    mime_type = detected_mime_type or fallback_mime_type
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "application/octet-stream"
    return LoadedImage(image=image, width=width, height=height, mime_type=mime_type)


def generate_variant_image(
    image: Image.Image,
    *,
    resource_type: ResourceType,
) -> GeneratedVariant:
    max_size = _variant_max_size(resource_type)
    variant_image = image.copy()
    variant_image.thumbnail(max_size, Image.Resampling.LANCZOS)
    width, height = variant_image.size

    has_alpha = "A" in variant_image.getbands() or "transparency" in variant_image.info
    if has_alpha:
        export_image = variant_image.convert("RGBA")
        file_ext = "png"
        mime_type = "image/png"
    else:
        export_image = variant_image.convert("RGB")
        file_ext = "jpg"
        mime_type = "image/jpeg"

    buffer = BytesIO()
    if has_alpha:
        export_image.save(buffer, format="PNG", optimize=True)
    else:
        export_image.save(buffer, format="JPEG", optimize=True, quality=85)
    return GeneratedVariant(
        content=buffer.getvalue(),
        file_ext=file_ext,
        mime_type=mime_type,
        width=width,
        height=height,
    )


def calculate_variant_dimensions(
    *,
    width: int,
    height: int,
    resource_type: ResourceType,
) -> tuple[int, int]:
    max_width, max_height = _variant_max_size(resource_type)
    scale = min(max_width / width, max_height / height, 1.0)
    scaled_width = max(1, int(width * scale))
    scaled_height = max(1, int(height * scale))
    return scaled_width, scaled_height


def _variant_max_size(resource_type: ResourceType) -> tuple[int, int]:
    if resource_type == RESOURCE_TYPE_THUMBNAIL:
        return THUMBNAIL_MAX_SIZE
    if resource_type == RESOURCE_TYPE_PREVIEW:
        return PREVIEW_MAX_SIZE
    raise ValueError(f"Unsupported variant resource type: {resource_type}")
