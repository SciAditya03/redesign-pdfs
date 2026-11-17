"""Local PDF validation and inspection (PyMuPDF). Used before anything is sent to Gemini."""

from dataclasses import asdict, dataclass

import pymupdf as fitz

PDF_SIGNATURE = b"%PDF-"


class PdfValidationError(ValueError):
    """Raised when an uploaded file is not an acceptable PDF. The message is safe to show to users."""


@dataclass
class PdfInfo:
    page_count: int
    size_bytes: int
    width_pt: float
    height_pt: float
    text_chars: int
    likely_scanned: bool
    title: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_pdf(data: bytes, label: str = "File") -> PdfInfo:
    """Validate PDF bytes and return basic facts. Raises PdfValidationError with a user-facing message."""
    if not data:
        raise PdfValidationError(f"{label} is empty.")
    # The signature must appear in the first 1 KB (PDF spec allows leading junk only there).
    if PDF_SIGNATURE not in data[:1024]:
        raise PdfValidationError(f"{label} is not a PDF (missing %PDF header).")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types for corrupt input
        raise PdfValidationError(f"{label} could not be opened as a PDF: it may be corrupt.") from exc
    try:
        if doc.needs_pass or doc.is_encrypted:
            raise PdfValidationError(f"{label} is password-protected. Remove the password and upload it again.")
        if doc.page_count == 0:
            raise PdfValidationError(f"{label} has no pages.")
        first = doc[0].rect
        text_chars = 0
        for page in doc:
            text_chars += len(page.get_text("text").strip())
        title = (doc.metadata or {}).get("title") or None
        return PdfInfo(
            page_count=doc.page_count,
            size_bytes=len(data),
            width_pt=round(first.width, 2),
            height_pt=round(first.height, 2),
            text_chars=text_chars,
            likely_scanned=text_chars < 80 * doc.page_count,
            title=title,
        )
    finally:
        doc.close()
