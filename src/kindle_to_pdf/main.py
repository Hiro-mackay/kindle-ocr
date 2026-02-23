"""CLI entry point for kindle-to-pdf."""

import argparse
import logging
import sys

from .config import DIRECTION_VERTICAL, AppConfig, OcrConfig
from .kindle import KindleToPDF

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kindleの本をスクリーンショット→OCR→Markdown/PDFに変換します"
    )
    parser.add_argument(
        "--direction",
        "-d",
        choices=["auto", "vertical", "horizontal"],
        default="auto",
        help="テキスト方向 (auto: 自動検出, vertical: 縦書き/←送り, horizontal: 横書き/→送り)",
    )
    parser.add_argument(
        "--region",
        "-r",
        choices=["left", "right", "full"],
        default="full",
        help="スクリーンショットの領域 (left: 左半分, right: 右半分, full: 全体)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="出力ファイル名（拡張子なし）",
    )
    parser.add_argument(
        "--screenshot-only",
        "-so",
        action="store_true",
        help="スクリーンショットの取得のみを実行",
    )
    parser.add_argument(
        "--from-screenshots",
        "-fs",
        action="store_true",
        help="既存のスクリーンショットからOCR→Markdown/PDF作成",
    )
    parser.add_argument(
        "--preview",
        "-p",
        action="store_true",
        help="現在のKindleページのみをスクリーンショットして設定を確認",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="詳細なログを出力",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    vertical_mode = args.direction == DIRECTION_VERTICAL
    ocr_config = OcrConfig(vertical_mode=vertical_mode)
    app_config = AppConfig(ocr=ocr_config)

    kindle = KindleToPDF(
        direction=args.direction,
        region=args.region,
        output_filename=args.output,
        config=app_config,
    )

    try:
        if args.preview:
            kindle.preview_screenshot()
            return

        if args.from_screenshots:
            kindle.run_from_screenshots()
            return

        if args.screenshot_only:
            kindle.take_screenshots()
            logger.info("スクリーンショットの取得が完了しました")
            return

        kindle.run()

    except KeyboardInterrupt:
        print("\n処理が中断されました")
        print(f"スクリーンショット保存先: {kindle.config.screenshot_dir}")
        print("再開するには --from-screenshots オプションを使用してください")
        sys.exit(130)

    except FileNotFoundError as e:
        logger.error("エラー: %s", e)
        sys.exit(1)

    except RuntimeError as e:
        logger.error("エラー: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
