"""macOS OCR処理（ocrmac + LiveText）"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from ocrmac import ocrmac

logger = logging.getLogger(__name__)

# === 型エイリアス ===
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

# === 日本語文字のUnicode範囲 ===
_JP_CHARS = r"\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF00-\uFFEF\u3000-\u303F"

# 日本語文字に挟まれた空白を検出
_JAPANESE_SPACING_PATTERN = re.compile(rf"(?<=[{_JP_CHARS}])\s+(?=[{_JP_CHARS}])")



@dataclass
class OcrConfig:
    """OCR設定"""

    languages: list[str] = field(default_factory=lambda: ["ja", "en"])
    vertical_mode: bool = False  # 縦書きモード（右→左、上→下にソート）


def _remove_japanese_spaces(text: str) -> str:
    """
    日本語文字間の不要なスペースを除去する

    "わ た し" → "わたし"
    "Hello World" → "Hello World" (英語はそのまま)
    """
    return _JAPANESE_SPACING_PATTERN.sub("", text)


def _create_ocr_instance(
    image_path: str | Path,
    languages: list[str] | None = None,
) -> ocrmac.OCR:
    """
    OCRインスタンスを生成する（LiveText使用）

    Args:
        image_path: 画像ファイルのパス
        languages: 言語設定（デフォルト: ["ja", "en"]）

    Returns:
        設定済みのOCRインスタンス
    """
    if languages is None:
        languages = ["ja", "en"]
    return ocrmac.OCR(
        str(image_path),
        framework="livetext",
        language_preference=languages,
    )


def detect_text_orientation(image_path: str | Path) -> tuple[str, float]:
    """
    画像のテキスト方向を自動検出する

    Args:
        image_path: 画像ファイルのパス

    Returns:
        (orientation, confidence):
            orientation: "vertical" or "horizontal"
            confidence: 信頼度 (0.0-1.0)
    """
    try:
        ocr_instance = _create_ocr_instance(image_path)
        results: OcrResults = ocr_instance.recognize()
    except Exception:
        return ("horizontal", 0.0)

    if len(results) < MIN_RESULTS_FOR_DETECTION:
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
        if height > width * ASPECT_RATIO_THRESHOLD:
            vertical_boxes += 1
    vertical_ratio = vertical_boxes / len(results)

    # 両方の指標を組み合わせて判定
    # x座標減少率が高い、またはバウンディングボックスが縦長なら縦書き
    combined_score = (decreasing_ratio * X_TREND_WEIGHT) + (vertical_ratio * ASPECT_RATIO_WEIGHT)

    if combined_score > VERTICAL_THRESHOLD:
        return ("vertical", combined_score)
    else:
        return ("horizontal", 1.0 - combined_score)


def _group_by_line_horizontal(results: OcrResults) -> list[list[OcrResult]]:
    """
    横書き用：Y座標が近いテキストを同じ行としてグループ化

    bbox: (x, y, width, height) - 左下原点の正規化座標
    Y座標が大きいほど上にある
    """
    if not results:
        return []

    # Y座標（中心）でソート（上から下）
    sorted_results = sorted(results, key=lambda r: -r[2][1])

    lines: list[list[OcrResult]] = []
    current_line: list[OcrResult] = [sorted_results[0]]
    current_y = sorted_results[0][2][1]

    for result in sorted_results[1:]:
        y = result[2][1]
        # Y座標が近い場合は同じ行
        if abs(y - current_y) <= LINE_THRESHOLD_HORIZONTAL:
            current_line.append(result)
        else:
            # 新しい行を開始
            lines.append(current_line)
            current_line = [result]
            current_y = y

    lines.append(current_line)

    # 各行内をX座標でソート（左から右）
    for line in lines:
        line.sort(key=lambda r: r[2][0])

    return lines


def _group_by_line_vertical(results: OcrResults) -> list[list[OcrResult]]:
    """
    縦書き用：X座標が近いテキストを同じ列としてグループ化

    bbox: (x, y, width, height) - 左下原点の正規化座標
    X座標が大きいほど右にある（縦書きでは右から左に読む）
    """
    if not results:
        return []

    # X座標でソート（右から左）
    sorted_results = sorted(results, key=lambda r: -r[2][0])

    columns: list[list[OcrResult]] = []
    current_column: list[OcrResult] = [sorted_results[0]]
    current_x = sorted_results[0][2][0]

    for result in sorted_results[1:]:
        x = result[2][0]
        # X座標が近い場合は同じ列
        if abs(x - current_x) <= LINE_THRESHOLD_VERTICAL:
            current_column.append(result)
        else:
            # 新しい列を開始
            columns.append(current_column)
            current_column = [result]
            current_x = x

    columns.append(current_column)

    # 各列内をY座標でソート（上から下）
    for column in columns:
        column.sort(key=lambda r: -r[2][1])

    return columns


def _merge_line_text(line: list[OcrResult]) -> str:
    """
    行内のテキストを結合する

    日本語文字同士はスペースなしで結合
    """
    texts = [result[0] for result in line]
    merged = "".join(texts)
    # 日本語文字間の不要なスペースを除去
    return _remove_japanese_spaces(merged)


# === 改行ルール（LLM RAG処理用に最適化） ===
# 改行する箇所：読点、箇条書き、項番、章タイトル
# それ以外は結合

# 箇条書きパターン
_BULLET_PATTERN = re.compile(r"^[・･●■▶▷◆◇○◎★☆\-‐－―]+")

# 項番パターン（1. 1-1 1.1 (1) ① など）
_NUMBERED_PATTERN = re.compile(
    r"^([0-9]+[\.\-][0-9]*|"
    r"\([0-9]+\)|"
    r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|"
    r"[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]|"
    r"[a-z]\)|"
    r"[A-Z]\.)"
)

# 章タイトルパターン
_CHAPTER_PATTERN = re.compile(
    r"^(第[0-9一二三四五六七八九十百千]+[章節編部話回]|"
    r"Chapter\s*[0-9]+|CHAPTER\s*[0-9]+|"
    r"Section\s*[0-9]+|SECTION\s*[0-9]+|"
    r"はじめに|おわりに|まとめ|序章|終章|"
    r"目次|索引|参考文献|付録|あとがき|謝辞|著者紹介)$",
    re.IGNORECASE
)


def _should_break_before(line: str) -> bool:
    """この行の前で改行すべきかを判定"""
    stripped = line.strip()
    if not stripped:
        return False

    # 箇条書き
    if _BULLET_PATTERN.match(stripped):
        return True

    # 項番
    if _NUMBERED_PATTERN.match(stripped):
        return True

    # 章タイトル
    if _CHAPTER_PATTERN.match(stripped):
        return True

    return False


def _should_break_after(line: str) -> bool:
    """この行の後で改行すべきかを判定"""
    stripped = line.strip()
    if not stripped:
        return True

    # 読点「。」で終わる
    if stripped.endswith("。"):
        return True

    # 章タイトル
    if _CHAPTER_PATTERN.match(stripped):
        return True

    return False


def _should_keep_line_break(current_line: str, next_line: str | None) -> bool:
    """
    現在の行の後に改行を保持すべきかを判定

    LLM RAG処理用に最適化：
    - 読点「。」の後 → 改行
    - 箇条書き・項番・章の前 → 改行
    - それ以外 → 結合

    Args:
        current_line: 現在の行
        next_line: 次の行（なければNone）

    Returns:
        True: 改行を保持, False: 次の行と結合
    """
    # 次の行がない場合は改行を保持
    if next_line is None:
        return True

    next_stripped = next_line.strip()

    # 次の行が空の場合は改行を保持
    if not next_stripped:
        return True

    # 現在の行の後で改行すべき
    if _should_break_after(current_line):
        return True

    # 次の行の前で改行すべき
    if _should_break_before(next_stripped):
        return True

    # それ以外はすべて結合
    return False


def _merge_paragraph_lines(lines: list[str]) -> str:
    """
    文章の途中の改行を削除し、段落単位で結合する

    Args:
        lines: 行のリスト

    Returns:
        段落単位で結合されたテキスト
    """
    if not lines:
        return ""

    result_parts: list[str] = []
    current_paragraph: list[str] = []

    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else None

        current_paragraph.append(line)

        if _should_keep_line_break(line, next_line):
            # 段落を結合して追加
            result_parts.append("".join(current_paragraph))
            current_paragraph = []

    # 残りがあれば追加
    if current_paragraph:
        result_parts.append("".join(current_paragraph))

    return "\n".join(result_parts)


def recognize_text(
    image_path: str | Path,
    config: OcrConfig | None = None,
) -> str:
    """
    macOS LiveTextでテキストを認識する

    Args:
        image_path: 画像ファイルのパス
        config: OCR設定（デフォルト: 日本語/英語）

    Returns:
        認識されたテキスト

    Raises:
        RuntimeError: OCR処理に失敗した場合
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

    # 縦書き/横書きに応じて行をグループ化
    if config.vertical_mode:
        lines = _group_by_line_vertical(results)
    else:
        lines = _group_by_line_horizontal(results)

    # 各行のテキストを結合
    text_lines = [_merge_line_text(line) for line in lines]

    # 文章途中の改行を削除し、段落単位で結合
    return _merge_paragraph_lines(text_lines)


def recognize_text_batch(
    image_paths: list[str | Path],
    config: OcrConfig | None = None,
    max_workers: int = 4,  # 互換性のため残すが使用しない
) -> list[str]:
    """
    複数の画像に対してOCRを実行する

    注意: macOSのLiveTextはメインスレッドでのみ動作するため、
    シーケンシャル実行を行う。

    Args:
        image_paths: 画像ファイルパスのリスト
        config: OCR設定
        max_workers: 互換性のため残すが使用しない

    Returns:
        認識されたテキストのリスト（画像の順序と対応）
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
