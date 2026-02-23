"""Output file creation (Markdown and PDF)."""

import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from .config import PdfConfig
from .text import merge_paragraph_lines

logger = logging.getLogger(__name__)


def write_markdown(ocr_results: dict[int, str], output_path: Path) -> Path:
    """Create a Markdown file from OCR results."""
    logger.info("Markdownファイルの作成を開始します...")

    sorted_pages = sorted(ocr_results.keys())
    all_lines: list[str] = []

    for page_num in sorted_pages:
        text = ocr_results[page_num].strip()
        if text:
            all_lines.extend(text.split("\n"))

    merged_text = merge_paragraph_lines(all_lines)
    output_path.write_text(merged_text, encoding="utf-8")

    logger.info("Markdownファイルを作成しました: %s", output_path)
    return output_path


def write_pdf(
    sorted_image_files: list[tuple[int, Path]],
    output_path: Path,
    pdf_config: PdfConfig,
) -> Path:
    """Create a PDF with image pages."""
    logger.info("PDFの作成を開始します...")

    doc = fitz.open()

    for _page_num, image_path in sorted_image_files:
        logger.info("PDF処理中: %s", image_path.name)
        img = Image.open(image_path)
        page = doc.new_page(width=img.width, height=img.height)
        page.insert_image(page.rect, filename=str(image_path))

    logger.info("PDFの保存を開始します...")
    logger.debug(
        "最適化設定: garbage=%d, deflate=%s, clean=%s",
        pdf_config.garbage,
        pdf_config.deflate,
        pdf_config.clean,
    )

    doc.save(
        str(output_path),
        garbage=pdf_config.garbage,
        deflate=pdf_config.deflate,
        clean=pdf_config.clean,
    )
    doc.close()

    logger.info("PDFファイルを作成しました: %s", output_path)
    return output_path
