"""macOS Vision Framework を使用したOCR処理"""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import Quartz
import Vision

# 日本語文字のUnicode範囲
# - ひらがな: \u3040-\u309F
# - カタカナ: \u30A0-\u30FF
# - 漢字: \u4E00-\u9FFF, \u3400-\u4DBF
# - 全角英数・記号: \uFF00-\uFFEF
# - 句読点: \u3000-\u303F
_JP_CHARS = r"\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF00-\uFFEF\u3000-\u303F"

# 日本語文字に挟まれた空白を検出（先読み・後読みで文字を消費しない）
_JAPANESE_SPACING_PATTERN = re.compile(rf"(?<=[{_JP_CHARS}])\s+(?=[{_JP_CHARS}])")


def _remove_japanese_spaces(text: str) -> str:
    """
    日本語文字間の不要なスペースを除去する

    "わ た し" → "わたし"
    "Hello World" → "Hello World" (英語はそのまま)
    "これは OCR テスト です" → "これはOCRテストです"
    """
    return _JAPANESE_SPACING_PATTERN.sub("", text)


def recognize_text(image_path: str | Path) -> str:
    """
    macOS Vision Framework を使用して画像からテキストを認識する

    Args:
        image_path: 画像ファイルのパス

    Returns:
        認識されたテキスト

    Raises:
        ValueError: 画像の読み込みに失敗した場合
        RuntimeError: OCR処理に失敗した場合
    """
    image_path_str = str(image_path)
    image_path_bytes = image_path_str.encode("utf-8")

    # 画像を読み込む
    image_url = Quartz.CFURLCreateFromFileSystemRepresentation(
        None, image_path_bytes, len(image_path_bytes), False
    )
    image_source = Quartz.CGImageSourceCreateWithURL(image_url, None)
    if image_source is None:
        raise ValueError(f"画像を読み込めませんでした: {image_path}")

    cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)
    if cg_image is None:
        raise ValueError(f"CGImageの作成に失敗しました: {image_path}")

    # Vision リクエストハンドラを作成
    request_handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, None
    )

    # テキスト認識リクエストを作成
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["ja", "en"])
    request.setUsesLanguageCorrection_(True)

    # リクエストを実行
    success, error = request_handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError(f"OCR処理に失敗しました: {error}")

    # 結果を取得
    results = request.results()
    if not results:
        return ""

    # テキストを抽出（上から下、左から右の順序で）
    text_lines = []
    for observation in results:
        # 最も信頼度の高い候補を取得
        top_candidate = observation.topCandidates_(1)
        if top_candidate:
            line = top_candidate[0].string()
            # 日本語文字間の不要なスペースを除去
            line = _remove_japanese_spaces(line)
            text_lines.append(line)

    return "\n".join(text_lines)


def recognize_text_batch(
    image_paths: list[str | Path],
    max_workers: int = 4,
) -> list[str]:
    """
    複数の画像に対してOCRを並列実行する

    Args:
        image_paths: 画像ファイルパスのリスト
        max_workers: 並列実行するワーカー数（デフォルト: 4）

    Returns:
        認識されたテキストのリスト（画像の順序と対応）
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(recognize_text, image_paths))
