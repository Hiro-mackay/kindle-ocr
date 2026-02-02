import argparse
import hashlib
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pyautogui
from PIL import Image

from .ocr import (
    OcrConfig,
    detect_text_orientation,
    recognize_text_batch,
    _merge_paragraph_lines,
)

# ロガーの設定
logger = logging.getLogger(__name__)

# === 方向設定の定数 ===
DIRECTION_AUTO = "auto"
DIRECTION_VERTICAL = "vertical"
DIRECTION_HORIZONTAL = "horizontal"
VALID_DIRECTIONS = (DIRECTION_AUTO, DIRECTION_VERTICAL, DIRECTION_HORIZONTAL)

# === リージョン設定の定数 ===
REGION_LEFT = "left"
REGION_RIGHT = "right"
REGION_FULL = "full"
VALID_REGIONS = (REGION_LEFT, REGION_RIGHT, REGION_FULL)


@dataclass
class PdfConfig:
    """PDF最適化設定"""

    garbage: int = 4  # 未使用オブジェクトの削除レベル
    deflate: bool = True  # 画像データの圧縮
    clean: bool = True  # 重複オブジェクトの削除


@dataclass
class MarginConfig:
    """マージン設定（画面サイズに対する比率）"""

    top: float = 0.1  # 上部の余白
    bottom: float = 0.05  # 下部の余白
    left: float = 0.05  # 左側の余白
    right: float = 0  # 右側の余白
    half_position: float = 0.5  # 左右分割時の中央位置

    def __post_init__(self) -> None:
        """設定値のバリデーション（すべて0.0〜1.0の範囲）"""
        for name in ("top", "bottom", "left", "right", "half_position"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")


@dataclass
class AppConfig:
    """アプリケーション設定"""

    max_pages: int = 1000  # 最大ページ数
    page_turn_delay: float = 0.6  # ページ送り後の待機時間（秒）
    kindle_activation_delay: float = 2.0  # Kindle起動後の待機時間（秒）
    screenshot_dir: Path = field(default_factory=lambda: Path("screenshots"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    margin: MarginConfig = field(default_factory=MarginConfig)
    pdf: PdfConfig = field(default_factory=PdfConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)


def get_page_turn_key(vertical_mode: bool) -> str:
    """テキスト方向に応じたページ送りキーを返す"""
    return "left" if vertical_mode else "right"


def prompt_vertical_mode(confidence: float) -> bool:
    """
    縦書きモードを使用するかユーザーに確認する

    Args:
        confidence: 検出の信頼度 (0.0-1.0)

    Returns:
        True if vertical mode, False if horizontal mode
    """
    confidence_pct = int(confidence * 100)

    print(f"\n縦書きとして検出されました（信頼度: {confidence_pct}%）")
    print("縦書きモードに切り替えますか？")
    print("  [y] 縦書き（←キーでページ送り）")
    print("  [n] 横書きのまま（→キーでページ送り）")
    print("  [Enter] 縦書きに切り替え")

    while True:
        try:
            user_input = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return True  # デフォルトは縦書きに切り替え

        if user_input == "":
            return True
        elif user_input in ("y", "yes"):
            return True
        elif user_input in ("n", "no"):
            return False
        else:
            print("y または n を入力してください")


class KindleToPDF:
    def __init__(
        self,
        direction: str = DIRECTION_AUTO,
        region: str = "full",
        output_filename: str | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.direction = direction
        self.region = region
        self.output_filename = output_filename
        self.ocr_results: dict[int, str] = {}  # ページ番号 -> OCRテキスト

        # 方向設定の初期化
        if direction == DIRECTION_VERTICAL:
            self.vertical_mode = True
        elif direction == DIRECTION_HORIZONTAL:
            self.vertical_mode = False
        else:  # auto
            self.vertical_mode = False  # デフォルトは横書き

        # 出力ディレクトリの作成
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def page_turn_key(self) -> str:
        """現在のページ送りキーを返す"""
        return get_page_turn_key(self.vertical_mode)

    def _get_output_path(self, extension: str) -> Path:
        """出力ファイルパスを生成"""
        if self.output_filename:
            filename = f"{self.output_filename}.{extension}"
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"kindle_book_{timestamp}.{extension}"
        return self.config.output_dir / filename

    def activate_kindle(self) -> None:
        """Kindleアプリを最前面に表示"""
        logger.info("Kindleアプリを最前面に表示します...")
        try:
            script = '''
            tell application "Amazon Kindle"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=False)
            time.sleep(self.config.kindle_activation_delay)
        except Exception as e:
            logger.error("Kindleアプリの起動に失敗しました: %s", e)
            logger.error("Amazon Kindleアプリがインストールされていることを確認してください。")
            raise

    def get_kindle_content_region(self) -> tuple[int, int, int, int]:
        """Kindleのコンテンツ表示領域を取得"""
        screen_width, screen_height = pyautogui.size()
        margin = self.config.margin

        top_margin = int(screen_height * margin.top)
        bottom_margin = int(screen_height * margin.bottom)

        if self.region == "left":
            left_margin = int(screen_width * margin.left)
            right_margin = int(screen_width * margin.half_position)
        elif self.region == "right":
            left_margin = int(screen_width * margin.half_position)
            right_margin = int(screen_width * (1 - margin.right))
        else:  # 'full'
            left_margin = int(screen_width * margin.left)
            right_margin = int(screen_width * (1 - margin.right))

        left = left_margin
        top = top_margin
        width = right_margin - left_margin
        height = screen_height - top_margin - bottom_margin

        logger.debug("画面サイズ: %dx%d", screen_width, screen_height)
        logger.debug(
            "計算された領域: left=%d, top=%d, width=%d, height=%d",
            left, top, width, height,
        )

        return (left, top, width, height)

    @staticmethod
    def _image_hash(image: Image.Image) -> str:
        """画像のハッシュ値を計算"""
        return hashlib.md5(image.tobytes()).hexdigest()

    def _take_screenshot(
        self, screenshot_path: Path, content_region: tuple[int, int, int, int]
    ) -> None:
        """1ページのスクリーンショットを取得"""
        x, y, width, height = content_region
        result = subprocess.run(
            [
                "screencapture",
                "-x",
                "-C",
                "-R",
                f"{x},{y},{width},{height}",
                str(screenshot_path),
            ],
            capture_output=True,
        )

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "不明なエラー"
            raise RuntimeError(f"スクリーンショットの取得に失敗しました: {error_msg}")

        if not screenshot_path.exists():
            raise RuntimeError(
                f"スクリーンショットファイルが作成されませんでした: {screenshot_path}"
            )

    def _prepare_screenshot_dir(self) -> None:
        """スクリーンショットディレクトリを準備（既存を削除して新規作成）"""
        screenshot_dir = self.config.screenshot_dir
        if screenshot_dir.exists():
            file_count = len(list(screenshot_dir.glob("*.png")))
            if file_count > 0:
                logger.info("古いスクリーンショットを削除します（%d件）...", file_count)
            shutil.rmtree(screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _capture_first_page(
        self, content_region: tuple[int, int, int, int]
    ) -> tuple[Path, str]:
        """
        最初のページをキャプチャしてハッシュを返す

        Returns:
            (screenshot_path, image_hash): スクリーンショットのパスとハッシュ値
        """
        screenshot_dir = self.config.screenshot_dir
        first_screenshot_path = screenshot_dir / "page_1.png"
        self._take_screenshot(first_screenshot_path, content_region)
        image_hash = self._image_hash(Image.open(first_screenshot_path))
        return first_screenshot_path, image_hash

    def _capture_remaining_pages(
        self,
        content_region: tuple[int, int, int, int],
        last_hash: str,
        start_page: int,
    ) -> int:
        """
        残りのページをキャプチャし、総ページ数を返す

        Args:
            content_region: スクリーンショット領域
            last_hash: 前ページの画像ハッシュ
            start_page: 開始ページ番号

        Returns:
            総ページ数
        """
        screenshot_dir = self.config.screenshot_dir
        page = start_page

        # 最初のページ送り
        pyautogui.press(self.page_turn_key)
        time.sleep(self.config.page_turn_delay)

        while True:
            screenshot_path = screenshot_dir / f"page_{page}.png"
            self._take_screenshot(screenshot_path, content_region)

            screenshot = Image.open(screenshot_path)
            current_hash = self._image_hash(screenshot)

            if current_hash == last_hash:
                logger.info("最後のページに到達しました")
                screenshot_path.unlink()
                break

            last_hash = current_hash

            pyautogui.press(self.page_turn_key)

            if page >= self.config.max_pages:
                logger.warning("最大ページ数に達しました")
                break

            page += 1
            time.sleep(self.config.page_turn_delay)

        return page - 1

    def _log_direction_info(self) -> None:
        """現在のテキスト方向設定をログ出力"""
        mode_str = "縦書き" if self.vertical_mode else "横書き"
        logger.info("テキスト方向: %s（%sキーでページ送り）", mode_str, self.page_turn_key)

    def take_screenshots(self) -> int:
        """Kindleの全ページのスクリーンショットを取得"""
        logger.info("スクリーンショットの取得を開始します...")

        self._prepare_screenshot_dir()
        self.activate_kindle()

        content_region = self.get_kindle_content_region()
        logger.info("スクリーンショット領域: %s", content_region)

        first_path, last_hash = self._capture_first_page(content_region)

        # autoモードの場合、テキスト方向を検出
        if self.direction == DIRECTION_AUTO:
            self._detect_and_apply_direction(first_path)

        self._log_direction_info()

        total_pages = self._capture_remaining_pages(content_region, last_hash, start_page=2)
        logger.info("スクリーンショットの取得が完了しました。合計%dページ", total_pages)
        return total_pages

    def _detect_text_direction(self, image_path: Path) -> tuple[str, float]:
        """
        テキスト方向を検出して結果を返す（状態変更なし）

        Returns:
            (orientation, confidence): 検出された方向と信頼度
        """
        logger.info("テキスト方向を検出中...")
        return detect_text_orientation(image_path)

    def _apply_direction_setting(self, detected: str, confidence: float) -> None:
        """
        検出結果に基づいて方向設定を適用（必要に応じてユーザーに確認）

        Args:
            detected: 検出された方向（"vertical" or "horizontal"）
            confidence: 検出の信頼度
        """
        if detected == "vertical":
            # 縦書きが検出された場合のみユーザーに確認
            self.vertical_mode = prompt_vertical_mode(confidence)
        else:
            # 横書きの場合は確認なしでそのまま
            logger.info("横書きとして検出されました")
            self.vertical_mode = False
        self.config.ocr.vertical_mode = self.vertical_mode

    def _detect_and_apply_direction(self, image_path: Path) -> None:
        """テキスト方向を検出し、設定を適用する"""
        detected, confidence = self._detect_text_direction(image_path)
        self._apply_direction_setting(detected, confidence)

    def _get_sorted_image_files(self) -> list[tuple[int, Path]]:
        """スクリーンショットファイルをページ番号順でソートして返す"""
        screenshot_dir = self.config.screenshot_dir
        files = list(screenshot_dir.glob("page_*.png"))

        def get_page_number(path: Path) -> int:
            # page_1.png -> 1
            stem = path.stem  # "page_1"
            return int(stem.split("_")[1])

        sorted_files = sorted(files, key=get_page_number)
        return [(get_page_number(f), f) for f in sorted_files]

    def detect_direction_from_screenshots(self) -> None:
        """
        既存のスクリーンショットからテキスト方向を検出する
        autoモードの場合のみ実行
        """
        if self.direction != DIRECTION_AUTO:
            return

        sorted_files = self._get_sorted_image_files()
        if not sorted_files:
            logger.warning("スクリーンショットがありません")
            return

        first_page = sorted_files[0][1]
        self._detect_and_apply_direction(first_page)

        mode_str = "縦書き" if self.vertical_mode else "横書き"
        logger.info("テキスト方向: %s モードで処理します", mode_str)

    def perform_ocr(self, max_workers: int = 4) -> None:
        """全スクリーンショットに対してOCRを並列実行"""
        ocr_config = self.config.ocr
        sorted_files = self._get_sorted_image_files()
        total = len(sorted_files)

        if total == 0:
            logger.warning("OCR対象のファイルがありません")
            return

        logger.info("OCR処理を開始します...")
        logger.info("縦書きモード: %s", ocr_config.vertical_mode)

        page_numbers = [page_num for page_num, _ in sorted_files]
        image_paths = [image_path for _, image_path in sorted_files]

        # 並列OCR実行
        results = recognize_text_batch(image_paths, config=ocr_config, max_workers=max_workers)

        # 結果をページ番号とマッピング
        for page_num, text in zip(page_numbers, results, strict=True):
            self.ocr_results[page_num] = text

        logger.info("OCR処理が完了しました（%dページ）", len(self.ocr_results))

    def create_markdown(self) -> Path:
        """OCR結果からMarkdownファイルを作成"""
        logger.info("Markdownファイルの作成を開始します...")

        md_path = self._get_output_path("md")

        # ページ順にテキストを連結
        sorted_pages = sorted(self.ocr_results.keys())
        all_lines: list[str] = []

        for page_num in sorted_pages:
            text = self.ocr_results[page_num].strip()
            if text:
                # 各ページのテキストを行に分割して追加
                all_lines.extend(text.split("\n"))

        # ページをまたぐ文章も結合（LLM RAG用に最適化）
        merged_text = _merge_paragraph_lines(all_lines)

        # Markdownファイルに書き出し
        md_path.write_text(merged_text, encoding="utf-8")

        logger.info("Markdownファイルを作成しました: %s", md_path)
        return md_path

    def create_pdf(self) -> Path:
        """スクリーンショットからテキストレイヤー付きPDFを作成"""
        logger.info("PDFの作成を開始します...")

        pdf_path = self._get_output_path("pdf")
        pdf_config = self.config.pdf

        doc = fitz.open()
        sorted_files = self._get_sorted_image_files()

        for page_num, image_path in sorted_files:
            logger.info("PDF処理中: %s", image_path.name)

            img = Image.open(image_path)

            # PDFページを作成
            page = doc.new_page(width=img.width, height=img.height)

            # 画像を挿入
            page.insert_image(page.rect, filename=str(image_path))

        logger.info("PDFの保存を開始します...")
        logger.debug(
            "最適化設定: garbage=%d, deflate=%s, clean=%s",
            pdf_config.garbage,
            pdf_config.deflate,
            pdf_config.clean,
        )

        doc.save(
            str(pdf_path),
            garbage=pdf_config.garbage,
            deflate=pdf_config.deflate,
            clean=pdf_config.clean,
        )
        doc.close()

        logger.info("PDFファイルを作成しました: %s", pdf_path)
        return pdf_path

    def _log_completion(self, md_path: Path, pdf_path: Path) -> None:
        """完了メッセージを出力"""
        logger.info("処理が完了しました:")
        logger.info("  Markdown: %s", md_path)
        logger.info("  PDF: %s", pdf_path)

    def run(self) -> tuple[Path, Path]:
        """メイン処理の実行"""
        self.take_screenshots()
        self.perform_ocr()
        md_path = self.create_markdown()
        pdf_path = self.create_pdf()
        self._log_completion(md_path, pdf_path)
        return md_path, pdf_path

    def preview_screenshot(self) -> Path:
        """
        現在のKindleページのみをスクリーンショットしてプレビュー保存

        スクリーンショット設定（マージン、リージョン）が正しいか確認するために使用。
        出力先: output/preview.png
        """
        logger.info("プレビュー用スクリーンショットを取得します...")

        self.activate_kindle()
        content_region = self.get_kindle_content_region()

        logger.info("スクリーンショット領域: %s", content_region)
        logger.info("  リージョン: %s", self.region)

        # プレビューファイルを output/ に保存
        preview_path = self.config.output_dir / "preview.png"
        self._take_screenshot(preview_path, content_region)

        logger.info("プレビューを保存しました: %s", preview_path)
        logger.info("このファイルを確認して、マージンやリージョンの設定が正しいかご確認ください。")

        return preview_path

    def run_from_screenshots(self) -> tuple[Path, Path]:
        """既存のスクリーンショットからOCR→Markdown/PDF作成"""
        screenshot_dir = self.config.screenshot_dir
        if not screenshot_dir.exists():
            raise FileNotFoundError(
                f"スクリーンショットディレクトリが存在しません: {screenshot_dir}"
            )
        if not any(screenshot_dir.glob("*.png")):
            raise FileNotFoundError(
                f"スクリーンショットディレクトリにPNGファイルがありません: {screenshot_dir}"
            )

        self.detect_direction_from_screenshots()
        self.perform_ocr()
        md_path = self.create_markdown()
        pdf_path = self.create_pdf()
        self._log_completion(md_path, pdf_path)
        return md_path, pdf_path


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
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

    # 方向設定からOCRの縦書きモードを設定
    vertical_mode = args.direction == DIRECTION_VERTICAL

    # OCR設定
    ocr_config = OcrConfig(vertical_mode=vertical_mode)

    # アプリ設定
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

        # 通常処理（スクショ→OCR→MD/PDF）
        kindle.run()

    except KeyboardInterrupt:
        print("\n処理が中断されました")
        print(f"スクリーンショット保存先: {kindle.config.screenshot_dir}")
        print("再開するには --from-screenshots オプションを使用してください")
        sys.exit(130)  # 128 + SIGINT(2)

    except FileNotFoundError as e:
        logger.error("エラー: %s", e)
        sys.exit(1)

    except RuntimeError as e:
        logger.error("エラー: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
