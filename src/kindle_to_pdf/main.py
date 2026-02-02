import argparse
import hashlib
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pyautogui
from PIL import Image

from .ocr import recognize_text

# ロガーの設定
logger = logging.getLogger(__name__)


@dataclass
class PdfConfig:
    """PDF最適化設定"""

    garbage: int = 4  # 未使用オブジェクトの削除レベル
    deflate: bool = True  # 画像データの圧縮
    clean: bool = True  # 重複オブジェクトの削除


@dataclass
class MarginConfig:
    """マージン設定（画面サイズに対する比率）"""

    top: float = 0.12  # 上部の余白
    bottom: float = 0.04  # 下部の余白
    left: float = 0.05  # 左側の余白
    right: float = 0.05  # 右側の余白
    half_position: float = 0.5  # 左右分割時の中央位置


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


class KindleToPDF:
    def __init__(
        self,
        page_turn_direction: str = "right",
        region: str = "full",
        output_filename: str | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.page_turn_direction = page_turn_direction
        self.region = region
        self.output_filename = output_filename
        self.ocr_results: dict[int, str] = {}  # ページ番号 -> OCRテキスト

        # 出力ディレクトリの作成
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

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

    def take_screenshots(self) -> int:
        """Kindleの全ページのスクリーンショットを取得"""
        logger.info("スクリーンショットの取得を開始します...")
        logger.info("ページ送りの方向: %s", self.page_turn_direction)

        screenshot_dir = self.config.screenshot_dir
        if screenshot_dir.exists():
            logger.info("古いスクリーンショットを削除します...")
            shutil.rmtree(screenshot_dir)

        screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.activate_kindle()

        content_region = self.get_kindle_content_region()
        logger.info("スクリーンショット領域: %s", content_region)

        page = 1
        last_hash: str | None = None

        while True:
            screenshot_path = screenshot_dir / f"page_{page}.png"

            x, y, width, height = content_region
            subprocess.run(
                [
                    "screencapture",
                    "-x",
                    "-C",
                    "-R",
                    f"{x},{y},{width},{height}",
                    str(screenshot_path),
                ],
                check=False,
            )

            screenshot = Image.open(screenshot_path)
            current_hash = self._image_hash(screenshot)

            if last_hash is not None and current_hash == last_hash:
                logger.info("最後のページに到達しました")
                screenshot_path.unlink()
                break

            last_hash = current_hash

            pyautogui.press(self.page_turn_direction)

            if page >= self.config.max_pages:
                logger.warning("最大ページ数に達しました")
                break

            page += 1
            time.sleep(self.config.page_turn_delay)

        total_pages = page - 1
        logger.info("スクリーンショットの取得が完了しました。合計%dページ", total_pages)
        return total_pages

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

    def perform_ocr(self) -> None:
        """全スクリーンショットに対してOCRを実行"""
        logger.info("OCR処理を開始します...")

        sorted_files = self._get_sorted_image_files()
        total = len(sorted_files)

        for i, (page_num, image_path) in enumerate(sorted_files, 1):
            logger.info("OCR処理中: %s (%d/%d)", image_path.name, i, total)

            try:
                text = recognize_text(str(image_path))
                self.ocr_results[page_num] = text
            except Exception as e:
                logger.warning("OCR失敗 - %s: %s", image_path.name, e)
                self.ocr_results[page_num] = ""

        logger.info("OCR処理が完了しました。%dページ", len(self.ocr_results))

    def create_markdown(self) -> Path:
        """OCR結果からMarkdownファイルを作成"""
        logger.info("Markdownファイルの作成を開始します...")

        md_path = self._get_output_path("md")

        # ページ順にテキストを連結
        sorted_pages = sorted(self.ocr_results.keys())
        all_text = []

        for page_num in sorted_pages:
            text = self.ocr_results[page_num].strip()
            if text:
                all_text.append(text)

        # Markdownファイルに書き出し
        md_path.write_text("\n\n".join(all_text), encoding="utf-8")

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

            # OCRテキストがあれば透明テキストレイヤーとして追加
            if page_num in self.ocr_results and self.ocr_results[page_num]:
                text = self.ocr_results[page_num]
                # 透明テキストを追加（検索可能にするため）
                text_rect = fitz.Rect(0, 0, img.width, img.height)
                page.insert_textbox(
                    text_rect,
                    text,
                    fontsize=1,
                    color=(1, 1, 1),  # 白色（背景に溶け込む）
                    opacity=0,  # 完全に透明
                )

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

    def run(self) -> tuple[Path, Path]:
        """メイン処理の実行"""
        self.take_screenshots()
        self.perform_ocr()
        md_path = self.create_markdown()
        pdf_path = self.create_pdf()
        logger.info("処理が完了しました:")
        logger.info("  Markdown: %s", md_path)
        logger.info("  PDF: %s", pdf_path)
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
        choices=["left", "right"],
        default="right",
        help="ページ送りの方向 (left または right)",
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
        "--verbose",
        "-v",
        action="store_true",
        help="詳細なログを出力",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    kindle = KindleToPDF(
        page_turn_direction=args.direction,
        region=args.region,
        output_filename=args.output,
    )

    if args.from_screenshots:
        # 既存のスクリーンショットから処理
        screenshot_dir = kindle.config.screenshot_dir
        if not screenshot_dir.exists():
            raise FileNotFoundError("スクリーンショットディレクトリが存在しません")
        if not any(screenshot_dir.glob("*.png")):
            raise FileNotFoundError("スクリーンショットディレクトリにPNGファイルがありません")

        kindle.perform_ocr()
        md_path = kindle.create_markdown()
        pdf_path = kindle.create_pdf()
        logger.info("処理が完了しました:")
        logger.info("  Markdown: %s", md_path)
        logger.info("  PDF: %s", pdf_path)
        return

    if args.screenshot_only:
        # スクリーンショットのみ
        kindle.take_screenshots()
        logger.info("スクリーンショットの取得が完了しました")
        return

    # 通常処理（スクショ→OCR→MD/PDF）
    kindle.run()


if __name__ == "__main__":
    main()
