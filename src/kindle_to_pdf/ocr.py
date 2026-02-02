"""macOS OCR処理（ocrmac + LiveText）"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from ocrmac import ocrmac

logger = logging.getLogger(__name__)

# 日本語文字のUnicode範囲
_JP_CHARS = r"\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF00-\uFFEF\u3000-\u303F"

# 日本語文字に挟まれた空白を検出
_JAPANESE_SPACING_PATTERN = re.compile(rf"(?<=[{_JP_CHARS}])\s+(?=[{_JP_CHARS}])")


@dataclass
class OcrConfig:
    """OCR設定"""

    framework: str = "livetext"  # "livetext" or "vision"
    languages: list[str] = field(default_factory=lambda: ["ja", "en"])
    vertical_mode: bool = False  # 縦書きモード（右→左、上→下にソート）
    recognition_level: str = "accurate"  # "fast" or "accurate"（visionのみ）


def _remove_japanese_spaces(text: str) -> str:
    """
    日本語文字間の不要なスペースを除去する

    "わ た し" → "わたし"
    "Hello World" → "Hello World" (英語はそのまま)
    """
    return _JAPANESE_SPACING_PATTERN.sub("", text)


def detect_text_orientation(
    image_path: str | Path,
    framework: str = "livetext",
) -> tuple[str, float]:
    """
    画像のテキスト方向を自動検出する

    Args:
        image_path: 画像ファイルのパス
        framework: OCRエンジン（"livetext" or "vision"）

    Returns:
        (orientation, confidence):
            orientation: "vertical" or "horizontal"
            confidence: 信頼度 (0.0-1.0)
    """
    try:
        ocr_instance = ocrmac.OCR(
            str(image_path),
            framework=framework,
            language_preference=["ja", "en"],
        )
        results = ocr_instance.recognize()
    except Exception:
        return ("horizontal", 0.0)

    if len(results) < 3:
        return ("horizontal", 0.0)

    # 方法1: テキストブロックのx座標の流れを見る
    # 縦書き: 読み進めるとx座標が減少（右から左）
    # 横書き: 読み進めるとy座標が減少（上から下）

    # y座標でソート（上から下の読み順を仮定）
    sorted_by_y = sorted(results, key=lambda r: -r[2][1])
    x_coords = [r[2][0] for r in sorted_by_y]

    # x座標が減少している割合を計算
    decreasing_count = sum(
        1 for i in range(len(x_coords) - 1) if x_coords[i] > x_coords[i + 1]
    )
    decreasing_ratio = decreasing_count / (len(x_coords) - 1)

    # 方法2: バウンディングボックスのアスペクト比
    # 縦書きの行は縦長になりやすい
    vertical_boxes = 0
    for _text, _conf, bbox in results:
        _x, _y, width, height = bbox
        if height > width * 1.2:  # 縦長
            vertical_boxes += 1
    vertical_ratio = vertical_boxes / len(results)

    # 両方の指標を組み合わせて判定
    # x座標減少率が高い、またはバウンディングボックスが縦長なら縦書き
    combined_score = (decreasing_ratio * 0.6) + (vertical_ratio * 0.4)

    if combined_score > 0.5:
        return ("vertical", combined_score)
    else:
        return ("horizontal", 1.0 - combined_score)


def _sort_for_vertical(
    results: list[tuple[str, float, tuple[float, float, float, float]]],
) -> list[tuple[str, float, tuple[float, float, float, float]]]:
    """
    縦書き用にソート（右から左、上から下）

    bbox: (x, y, width, height) - 左下原点の正規化座標
    """
    # x座標が大きい順（右から左）→ y座標が大きい順（上から下）
    return sorted(results, key=lambda item: (-item[2][0], -item[2][1]))


def _sort_for_horizontal(
    results: list[tuple[str, float, tuple[float, float, float, float]]],
) -> list[tuple[str, float, tuple[float, float, float, float]]]:
    """
    横書き用にソート（上から下、左から右）

    bbox: (x, y, width, height) - 左下原点の正規化座標
    """
    # y座標が大きい順（上から下）→ x座標が小さい順（左から右）
    return sorted(results, key=lambda item: (-item[2][1], item[2][0]))


def recognize_text(
    image_path: str | Path,
    config: OcrConfig | None = None,
) -> str:
    """
    macOS OCRでテキストを認識する

    Args:
        image_path: 画像ファイルのパス
        config: OCR設定（デフォルト: LiveText + 日本語/英語）

    Returns:
        認識されたテキスト

    Raises:
        RuntimeError: OCR処理に失敗した場合
    """
    if config is None:
        config = OcrConfig()

    image_path_str = str(image_path)

    try:
        # OCR実行
        ocr_instance = ocrmac.OCR(
            image_path_str,
            framework=config.framework,
            language_preference=config.languages,
            recognition_level=config.recognition_level,
        )
        results = ocr_instance.recognize()
    except Exception as e:
        raise RuntimeError(f"OCR処理に失敗しました: {e}") from e

    if not results:
        return ""

    # 縦書き/横書きに応じてソート
    if config.vertical_mode:
        sorted_results = _sort_for_vertical(results)
    else:
        sorted_results = _sort_for_horizontal(results)

    # テキストを抽出して連結
    text_lines = []
    for text, _confidence, _bbox in sorted_results:
        # 日本語文字間の不要なスペースを除去
        cleaned_text = _remove_japanese_spaces(text)
        text_lines.append(cleaned_text)

    return "\n".join(text_lines)


def recognize_text_batch(
    image_paths: list[str | Path],
    config: OcrConfig | None = None,
    max_workers: int = 4,
) -> list[str]:
    """
    複数の画像に対してOCRを並列実行する

    Args:
        image_paths: 画像ファイルパスのリスト
        config: OCR設定
        max_workers: 並列実行するワーカー数（デフォルト: 4）

    Returns:
        認識されたテキストのリスト（画像の順序と対応）
    """
    if config is None:
        config = OcrConfig()

    total = len(image_paths)
    results: dict[int, str] = {}
    completed_count = 0

    def _recognize_with_index(args: tuple[int, str | Path]) -> tuple[int, str]:
        idx, path = args
        try:
            text = recognize_text(path, config)
            return (idx, text)
        except Exception as e:
            logger.warning("OCR失敗 - %s: %s", Path(path).name, e)
            return (idx, "")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_recognize_with_index, (i, path)): i
            for i, path in enumerate(image_paths)
        }

        for future in as_completed(futures):
            idx, text = future.result()
            results[idx] = text
            completed_count += 1
            logger.info("OCR処理中: %d/%d 完了", completed_count, total)

    # インデックス順に結果を返す
    return [results[i] for i in range(total)]
