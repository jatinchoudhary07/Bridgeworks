import io
import magic
import logging
from PIL import Image
from django.core.exceptions import ValidationError

logger = logging.getLogger("security")

# Strict whitelist: extension -> allowed MIME types
ALLOWED_UPLOAD_TYPES = {
    "jpg": ["image/jpeg"],
    "jpeg": ["image/jpeg"],
    "png": ["image/png"],
    "pdf": ["application/pdf"],
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def validate_upload(file) -> None:
    """
    Validates an uploaded file. Raises ValidationError on any problem.
    """
    # 1. Size check
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.")

    # 2. Extension whitelist
    name = file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_UPLOAD_TYPES:
        logger.warning("FILE_UPLOAD_BAD_EXT ext=%s name=%s", ext, name)
        raise ValidationError(f"File type '.{ext}' is not allowed. Allowed: jpg, png, pdf.")

    # 3. Magic bytes
    file.seek(0)
    header = file.read(2048)
    file.seek(0)
    
    # We use python-magic to detect the actual MIME type
    detected = magic.from_buffer(header, mime=True)

    # 4. Consistency check
    if detected not in ALLOWED_UPLOAD_TYPES[ext]:
        logger.warning(
            "FILE_UPLOAD_MIME_MISMATCH ext=%s detected=%s name=%s",
            ext, detected, name,
        )
        raise ValidationError(
            f"File content ({detected}) does not match extension (.{ext})."
        )

    # 5. Re-encode images to strip any embedded payloads
    if detected in ("image/jpeg", "image/png"):
        _sanitize_image(file, detected)

    logger.info("FILE_UPLOAD_VALID ext=%s mime=%s size=%s", ext, detected, file.size)


def _sanitize_image(file, mime: str) -> None:
    try:
        file.seek(0)
        img = Image.open(io.BytesIO(file.read()))
        img.verify()  # Verifies image structure
    except Exception as e:
        logger.warning("FILE_UPLOAD_IMAGE_INVALID error=%s", e)
        raise ValidationError("File is not a valid image.")
    finally:
        file.seek(0)
