# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**kindle-ocr** is a macOS Python automation tool that converts Kindle ebooks to Markdown and searchable PDFs. It captures screenshots from the Kindle desktop application, performs OCR using macOS LiveText/Vision Framework via ocrmac, and outputs both Markdown (for RAG/NotebookLM) and PDF with text layer.

## Build and Run Commands

```bash
# Install package in editable mode
uv pip install -e .

# Full conversion (screenshots → OCR → Markdown + PDF)
kindle-pdf --output "book_name"

# Vertical text mode (Japanese novels)
kindle-pdf --output "novel" --vertical

# From existing screenshots (skip capture)
kindle-pdf --from-screenshots --output "book_name"

# Screenshots only (no OCR)
kindle-pdf --screenshot-only

# Use Vision framework instead of LiveText
kindle-pdf --output "book" --ocr-framework vision

# Lint with Ruff
uvx ruff check src/
```

## Architecture

```
src/kindle_to_pdf/
├── __init__.py
├── main.py      # CLI and main KindleToPDF class
└── ocr.py       # macOS OCR via ocrmac (LiveText/Vision)
```

### Processing Flow

```
1. Activate Kindle app (AppleScript)
2. Take screenshots (screencapture CLI)
3. OCR each page (ocrmac LiveText/Vision)
4. Output Markdown (concatenated text)
5. Output PDF (images + transparent text layer)
```

### Key Files

**main.py** - `KindleToPDF` class
- `take_screenshots()` - Capture pages until duplicate detected
- `perform_ocr()` - OCR all screenshots with OcrConfig
- `create_markdown()` - Output `.md` file
- `create_pdf()` - Output `.pdf` with text layer

**ocr.py** - `recognize_text(image_path, config)`
- Uses `ocrmac` library with LiveText (default) or Vision framework
- `OcrConfig` dataclass for OCR settings
- Vertical text sorting support (`vertical_mode=True`)

### Key Patterns

- **OCR Engine:** LiveText (default, macOS Sonoma+) or Vision (macOS 10.15+)
- **Vertical Mode:** Sorts text right-to-left, top-to-bottom for Japanese novels
- **Margin system:** Configurable percentages via MarginConfig dataclass
- **Region selection:** `left`, `right`, or `full` for dual-page displays
- **End detection:** Image hash comparison to detect last page
- **Platform:** macOS-only (LiveText/Vision, AppleScript, screencapture)

## File Locations

- Screenshots: `./screenshots/` (cleaned on each run)
- Output: `./output/*.md`, `./output/*.pdf`
- Python: 3.12+ required

## Dependencies

- `ocrmac` - macOS LiveText/Vision OCR wrapper
- `pymupdf` - PDF creation with text layer
- `pyautogui` - Keyboard control for page turning
- `pillow` - Image handling

## Linting

Ruff configured with: E, W, F, I, B (line length: 100)
