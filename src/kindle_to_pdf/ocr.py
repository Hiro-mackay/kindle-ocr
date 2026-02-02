"""macOS Vision Framework を使用したOCR処理"""

import Quartz
import Vision


def recognize_text(image_path: str) -> str:
    """
    macOS Vision Framework を使用して画像からテキストを認識する

    Args:
        image_path: 画像ファイルのパス

    Returns:
        認識されたテキスト
    """
    # 画像を読み込む
    image_url = Quartz.CFURLCreateFromFileSystemRepresentation(
        None, image_path.encode("utf-8"), len(image_path.encode("utf-8")), False
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
            text_lines.append(top_candidate[0].string())

    return "\n".join(text_lines)


def recognize_text_batch(image_paths: list[str]) -> list[str]:
    """
    複数の画像に対してOCRを実行する

    Args:
        image_paths: 画像ファイルパスのリスト

    Returns:
        認識されたテキストのリスト（画像の順序と対応）
    """
    return [recognize_text(path) for path in image_paths]
