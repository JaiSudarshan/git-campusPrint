"""Checks uploaded files and makes a first-page thumbnail + page count."""
import io

from PIL import Image, ImageOps

try:
    import pymupdf  # PyMuPDF 1.24.3+
except ImportError:  # older versions
    import fitz as pymupdf

THUMB_WIDTH = 360
MAX_PAGES = 300

SIGNATURES = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}


def inspect(data, ext):
    """Return (page_count, thumbnail_jpeg_bytes_or_None).

    Raises ValueError with a student-friendly message if the file is not valid.
    """
    if not data:
        raise ValueError("the file is empty.")
    if not data.startswith(SIGNATURES[ext]):
        raise ValueError("the file content doesn't match its type.")
    if ext == "pdf":
        return _pdf(data)
    return _image(data)


def _pdf(data):
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ValueError("couldn't read this PDF.")
    try:
        if doc.needs_pass:
            raise ValueError("password-protected PDFs can't be printed. Remove the password first.")
        pages = doc.page_count
        if pages < 1:
            raise ValueError("this PDF has no pages.")
        if pages > MAX_PAGES:
            raise ValueError(f"too many pages (max {MAX_PAGES}).")
        try:
            page = doc.load_page(0)
            zoom = THUMB_WIDTH / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            thumb = pix.tobytes("jpeg")
        except Exception:
            thumb = None
        return pages, thumb
    finally:
        doc.close()


def _image(data):
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, "white")
            background.paste(img, mask=img.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")
        img.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 2))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return 1, buf.getvalue()
    except Exception:
        raise ValueError("couldn't read this image.")
