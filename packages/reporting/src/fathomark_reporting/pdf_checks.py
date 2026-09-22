"""Structural checks for PDFs produced by the browser-backed renderer."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class PDFStructureReport:
    """Evidence collected from a parsed report PDF."""

    page_count: int
    text_lengths: tuple[int, ...]
    fonts_by_page: tuple[tuple[str, ...], ...]


def _font_names(font) -> list[str]:
    base_font = font.get("/BaseFont")
    if base_font is not None:
        return [str(base_font)]
    descriptor = font.get("/FontDescriptor")
    if descriptor is not None:
        font_name = descriptor.get_object().get("/FontName")
        if font_name is not None:
            return [str(font_name)]
    descendants = font.get("/DescendantFonts")
    if descendants:
        names = []
        for descendant_ref in descendants:
            names.extend(_font_names(descendant_ref.get_object()))
        return names
    return []


def verify_pdf_structure(
    pdf: bytes,
    *,
    expected_text: Iterable[str] = (),
    output_path: str | Path | None = None,
) -> PDFStructureReport:
    """Reject malformed, blank, fontless, or incomplete report PDFs.

    This is intentionally separate from browser layout checks. Playwright
    verifies the HTML viewport and font loading before printing; this function
    verifies the resulting PDF's page objects, extracted text, and font
    resources after printing.
    """
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
        raise ValueError("PDF bytes must begin with the PDF signature")
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF structure checks require the optional 'pypdf' dependency"
        ) from exc

    reader = PdfReader(BytesIO(pdf))
    if not reader.pages:
        raise ValueError("PDF contains no pages")

    page_text: list[str] = []
    fonts_by_page: list[tuple[str, ...]] = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            raise ValueError(f"PDF page {number} is blank")
        page_text.append(text)

        resources = page.get("/Resources")
        fonts = resources.get("/Font") if resources is not None else None
        if not fonts:
            raise ValueError(f"PDF page {number} has no font resources")
        names = []
        for font_ref in fonts.values():
            font = font_ref.get_object()
            font_names = _font_names(font)
            if not font_names:
                raise ValueError(f"PDF page {number} has a font without BaseFont")
            names.extend(font_names)
        fonts_by_page.append(tuple(sorted(names)))

    full_text = "\n".join(page_text)
    missing = [item for item in expected_text if item not in full_text]
    if missing:
        raise ValueError(f"PDF is missing expected text: {missing}")
    if output_path is not None:
        Path(output_path).write_bytes(pdf)
    return PDFStructureReport(
        page_count=len(reader.pages),
        text_lengths=tuple(len(text.strip()) for text in page_text),
        fonts_by_page=tuple(fonts_by_page),
    )
