# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**kindle-ocr** is a macOS Python automation tool that converts Kindle ebooks to Markdown and searchable PDFs. It captures screenshots from the Kindle desktop application, performs OCR using macOS Vision Framework, and outputs both Markdown (for RAG/NotebookLM) and PDF with text layer.

## Build and Run Commands

```bash
# Install package in editable mode
uv pip install -e .

# Full conversion (screenshots → OCR → Markdown + PDF)
kindle-pdf --output "book_name"

# From existing screenshots (skip capture)
kindle-pdf --from-screenshots --output "book_name"

# Screenshots only (no OCR)
kindle-pdf --screenshot-only

# Lint with Ruff
ruff check src/
```

## Architecture

```
src/kindle_to_pdf/
├── __init__.py
├── main.py      # CLI and main KindleToPDF class
└── ocr.py       # macOS Vision Framework OCR
```

### Processing Flow

```
1. Activate Kindle app (AppleScript)
2. Take screenshots (screencapture CLI)
3. OCR each page (macOS Vision Framework)
4. Output Markdown (concatenated text)
5. Output PDF (images + transparent text layer)
```

### Key Files

**main.py** - `KindleToPDF` class
- `take_screenshots()` - Capture pages until duplicate detected
- `perform_ocr()` - OCR all screenshots
- `create_markdown()` - Output `.md` file
- `create_pdf()` - Output `.pdf` with text layer

**ocr.py** - `recognize_text(image_path)`
- Uses `VNRecognizeTextRequest` for Japanese/English OCR
- Returns recognized text string

### Key Patterns

- **Margin system:** Configurable percentages to crop Kindle UI (TOP_MARGIN, etc.)
- **Region selection:** `left`, `right`, or `full` for dual-page displays
- **End detection:** Image byte comparison to detect last page
- **Platform:** macOS-only (Vision Framework, AppleScript, screencapture)

## File Locations

- Screenshots: `./screenshots/` (cleaned on each run)
- Output: `./output/*.md`, `./output/*.pdf`
- Python: 3.12+ required

## Dependencies

- `pymupdf` - PDF creation with text layer
- `pyobjc-framework-Vision` - macOS Vision OCR
- `pyautogui` - Keyboard control for page turning
- `pillow` - Image handling

## Linting

Ruff configured with: E, W, F, I, B (line length: 100)
