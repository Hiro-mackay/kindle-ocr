# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**kindle-ocr** is a macOS Python automation tool that converts Kindle ebooks to high-quality PDFs. It captures screenshots from the Kindle desktop application and creates PDF files using PyMuPDF.

## Build and Run Commands

```bash
# Install package in editable mode
uv pip install -e .

# Run PDF conversion (screenshots → high-quality PDF)
python src/kindle_to_pdf/main.py --direction right --region full

# Or use the installed command
kindle-pdf --direction right --region full

# PDF from existing screenshots (skip capture)
python src/kindle_to_pdf/main.py --from-screenshots

# Screenshots only (no PDF creation)
python src/kindle_to_pdf/main.py --screenshot-only

# Lint with Ruff
ruff check src/
```

## Architecture

The project contains a single CLI tool in `src/kindle_to_pdf/`:

### kindle_to_pdf (`src/kindle_to_pdf/main.py`)
- **Class:** `KindleToPDF`
- **Purpose:** Convert Kindle pages to high-quality PDF
- **Flow:** Activate Kindle → Take screenshots → Create PDF with PyMuPDF
- **Key methods:** `take_screenshots()`, `create_pdf()`

### Key Patterns

- **Margin system:** Configurable percentages to crop Kindle UI elements (TOP_MARGIN, BOTTOM_MARGIN, etc.)
- **Region selection:** `left`, `right`, or `full` screen capture for dual-page displays
- **End detection:** Image byte-level comparison to detect last page automatically
- **Platform integration:** Uses AppleScript (`osascript`) and `screencapture` CLI (macOS-only)

## File Locations

- Screenshots: `./screenshots/` (cleaned on each run)
- Output: `./output/`
- Python: 3.12+ required

## Linting

Ruff is configured with rules: E, W, F, I, B (line length: 100 chars)
