"""Kindle to PDF conversion tool."""

from .config import AppConfig, MarginConfig, OcrConfig, PdfConfig
from .kindle import KindleToPDF
from .ocr import recognize_text, recognize_text_batch
from .text import merge_paragraph_lines

__all__ = [
    "AppConfig",
    "KindleToPDF",
    "MarginConfig",
    "OcrConfig",
    "PdfConfig",
    "merge_paragraph_lines",
    "recognize_text",
    "recognize_text_batch",
]
