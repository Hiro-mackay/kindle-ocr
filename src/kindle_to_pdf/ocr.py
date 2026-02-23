"""macOS OCR processing (ocrmac + LiveText)."""

import logging
from pathlib import Path

from ocrmac import ocrmac

from .config import OcrConfig
from .text import merge_line_text, merge_paragraph_lines

logger = logging.getLogger(__name__)

# === Type aliases ===
BoundingBox = tuple[float, float, float, float]  # (x, y, width, height)
OcrResult = tuple[str, float, BoundingBox]  # (text, confidence, bbox)
OcrResults = list[OcrResult]

# === テキスト方向検出の定数 ===
# combined_scoreがこの値を超えたら縦書きと判定
VERTICAL_THRESHOLD = 0.5
# height > width * ASPECT_RATIO_THRESHOLD で縦長と判定
ASPECT_RATIO_THRESHOLD = 1.2
# x座標トレンドの重み（減少傾向なら縦書き）
X_TREND_WEIGHT = 0.6
# アスペクト比の重み
ASPECT_RATIO_WEIGHT = 0.4
# 方向検出に必要な最小結果数
MIN_RESULTS_FOR_DETECTION = 3

# === 行グループ化の閾値（正規化座標） ===
# 横書き: Y座標がこの範囲内なら同じ行とみなす
LINE_THRESHOLD_HORIZONTAL = 0.025
# 縦書き: X座標がこの範囲内なら同じ列とみなす
LINE_THRESHOLD_VERTICAL = 0.02


def _create_ocr_instance(
    image_path: str | Path,
    languages: list[str] | None = None,
) -> ocrmac.OCR:
    """Create an OCR instance using LiveText."""
    if languages is None:
        languages = ["ja", "en"]
    return ocrmac.OCR(
        str(image_path),
        framework="livetext",
        language_preference=languages,
    )


def detect_text_orientation(image_path: str | Path) -> tuple[str, float]:
    """
    Auto-detect text orientation in an image.

    Returns:
        (orientation, confidence):
            orientation: "vertical" or "horizontal"
            confidence: 0.0-1.0
    """
    try:
        ocr_instance = _create_ocr_instance(image_path)
        results: OcrResults = ocr_instance.recognize()
    except Exception:
        return ("horizontal", 0.0)

    if len(results) < MIN_RESULTS_FOR_DETECTION:
        return ("horizontal", 0.0)

    sorted_by_y = sorted(results, key=lambda r: -r[2][1])
    x_coords = [r[2][0] for r in sorted_by_y]

    decreasing_count = sum(
        1 for i in range(len(x_coords) - 1) if x_coords[i] > x_coords[i + 1]
    )
    decreasing_ratio = decreasing_count / (len(x_coords) - 1)

    vertical_boxes = 0
    for _text, _conf, bbox in results:
        _x, _y, width, height = bbox
        if height > width * ASPECT_RATIO_THRESHOLD:
            vertical_boxes += 1
    vertical_ratio = vertical_boxes / len(results)

    combined_score = (decreasing_ratio * X_TREND_WEIGHT) + (vertical_ratio * ASPECT_RATIO_WEIGHT)

    if combined_score > VERTICAL_THRESHOLD:
        return ("vertical", combined_score)
    else:
        return ("horizontal", 1.0 - combined_score)


def _group_by_line_horizontal(results: OcrResults) -> list[list[OcrResult]]:
    """Group text by Y-coordinate proximity for horizontal text."""
    if not results:
        return []

    sorted_results = sorted(results, key=lambda r: -r[2][1])

    lines: list[list[OcrResult]] = []
    current_line: list[OcrResult] = [sorted_results[0]]
    current_y = sorted_results[0][2][1]

    for result in sorted_results[1:]:
        y = result[2][1]
        if abs(y - current_y) <= LINE_THRESHOLD_HORIZONTAL:
            current_line.append(result)
        else:
            lines.append(current_line)
            current_line = [result]
            current_y = y

    lines.append(current_line)

    for line in lines:
        line.sort(key=lambda r: r[2][0])

    return lines


def _group_by_line_vertical(results: OcrResults) -> list[list[OcrResult]]:
    """Group text by X-coordinate proximity for vertical text."""
    if not results:
        return []

    sorted_results = sorted(results, key=lambda r: -r[2][0])

    columns: list[list[OcrResult]] = []
    current_column: list[OcrResult] = [sorted_results[0]]
    current_x = sorted_results[0][2][0]

    for result in sorted_results[1:]:
        x = result[2][0]
        if abs(x - current_x) <= LINE_THRESHOLD_VERTICAL:
            current_column.append(result)
        else:
            columns.append(current_column)
            current_column = [result]
            current_x = x

    columns.append(current_column)

    for column in columns:
        column.sort(key=lambda r: -r[2][1])

    return columns


def recognize_text(
    image_path: str | Path,
    config: OcrConfig | None = None,
) -> str:
    """
    Recognize text using macOS LiveText.

    Args:
        image_path: Path to image file
        config: OCR settings (default: Japanese/English)

    Returns:
        Recognized text

    Raises:
        RuntimeError: If OCR processing fails
    """
    if config is None:
        config = OcrConfig()

    try:
        ocr_instance = _create_ocr_instance(
            image_path,
            languages=config.languages,
        )
        results: OcrResults = ocr_instance.recognize()
    except Exception as e:
        raise RuntimeError(f"OCR処理に失敗しました: {e}") from e

    if not results:
        return ""

    if config.vertical_mode:
        lines = _group_by_line_vertical(results)
    else:
        lines = _group_by_line_horizontal(results)

    text_lines = [merge_line_text(line) for line in lines]

    return merge_paragraph_lines(text_lines)


def recognize_text_batch(
    image_paths: list[str | Path],
    config: OcrConfig | None = None,
    max_workers: int = 4,
) -> list[str]:
    """
    Run OCR on multiple images sequentially.

    Note: macOS LiveText only works on the main thread,
    so parallel execution is not possible.
    """
    if config is None:
        config = OcrConfig()

    total = len(image_paths)
    results: list[str] = []

    for i, path in enumerate(image_paths):
        try:
            text = recognize_text(path, config)
            results.append(text)
        except Exception as e:
            logger.warning("OCR失敗 - %s: %s", Path(path).name, e)
            results.append("")
        logger.info("OCR処理中: %d/%d 完了", i + 1, total)

    return results
