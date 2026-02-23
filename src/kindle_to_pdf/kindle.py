"""KindleToPDF class for capturing and converting Kindle books."""

import hashlib
import logging
import shutil
import subprocess
import time
from pathlib import Path

import pyautogui
from PIL import Image

from .config import (
    DIRECTION_AUTO,
    DIRECTION_HORIZONTAL,
    DIRECTION_VERTICAL,
    AppConfig,
    get_page_turn_key,
    prompt_vertical_mode,
)
from .ocr import detect_text_orientation, recognize_text_batch
from .output import write_markdown, write_pdf

logger = logging.getLogger(__name__)


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
        self.ocr_results: dict[int, str] = {}

        if direction == DIRECTION_VERTICAL:
            self.vertical_mode = True
        elif direction == DIRECTION_HORIZONTAL:
            self.vertical_mode = False
        else:
            self.vertical_mode = False

        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def page_turn_key(self) -> str:
        return get_page_turn_key(self.vertical_mode)

    def _get_output_path(self, extension: str) -> Path:
        if self.output_filename:
            filename = f"{self.output_filename}.{extension}"
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"kindle_book_{timestamp}.{extension}"
        return self.config.output_dir / filename

    def activate_kindle(self) -> None:
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
        screen_width, screen_height = pyautogui.size()
        margin = self.config.margin
        top = int(screen_height * margin.top)
        bottom_margin = int(screen_height * margin.bottom)

        if self.region == "left":
            left = int(screen_width * margin.left)
            right = int(screen_width * margin.half_position)
        elif self.region == "right":
            left = int(screen_width * margin.half_position)
            right = int(screen_width * (1 - margin.right))
        else:
            left = int(screen_width * margin.left)
            right = int(screen_width * (1 - margin.right))

        width = right - left
        height = screen_height - top - bottom_margin
        logger.debug("画面サイズ: %dx%d", screen_width, screen_height)
        logger.debug(
            "計算された領域: left=%d, top=%d, width=%d, height=%d",
            left, top, width, height,
        )
        return (left, top, width, height)

    @staticmethod
    def _image_hash(image: Image.Image) -> str:
        return hashlib.md5(image.tobytes()).hexdigest()

    def _take_screenshot(
        self, screenshot_path: Path, content_region: tuple[int, int, int, int]
    ) -> None:
        x, y, width, height = content_region
        result = subprocess.run(
            ["screencapture", "-x", "-C", "-R", f"{x},{y},{width},{height}", str(screenshot_path)],
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
        screenshot_dir = self.config.screenshot_dir
        if screenshot_dir.exists():
            file_count = len(list(screenshot_dir.glob("*.png")))
            if file_count > 0:
                logger.info("古いスクリーンショットを削除します（%d件）...", file_count)
            shutil.rmtree(screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _capture_remaining_pages(
        self,
        content_region: tuple[int, int, int, int],
        last_hash: str,
        start_page: int,
    ) -> int:
        screenshot_dir = self.config.screenshot_dir
        page = start_page

        pyautogui.press(self.page_turn_key)
        time.sleep(self.config.page_turn_delay)

        while True:
            screenshot_path = screenshot_dir / f"page_{page}.png"
            self._take_screenshot(screenshot_path, content_region)
            current_hash = self._image_hash(Image.open(screenshot_path))

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

    def take_screenshots(self) -> int:
        logger.info("スクリーンショットの取得を開始します...")
        self._prepare_screenshot_dir()
        self.activate_kindle()

        content_region = self.get_kindle_content_region()
        logger.info("スクリーンショット領域: %s", content_region)

        first_path = self.config.screenshot_dir / "page_1.png"
        self._take_screenshot(first_path, content_region)
        last_hash = self._image_hash(Image.open(first_path))

        if self.direction == DIRECTION_AUTO:
            self._detect_and_apply_direction(first_path)

        mode_str = "縦書き" if self.vertical_mode else "横書き"
        logger.info("テキスト方向: %s（%sキーでページ送り）", mode_str, self.page_turn_key)

        total_pages = self._capture_remaining_pages(content_region, last_hash, start_page=2)
        logger.info("スクリーンショットの取得が完了しました。合計%dページ", total_pages)
        return total_pages

    def _detect_and_apply_direction(self, image_path: Path) -> None:
        logger.info("テキスト方向を検出中...")
        detected, confidence = detect_text_orientation(image_path)
        if detected == "vertical":
            self.vertical_mode = prompt_vertical_mode(confidence)
        else:
            logger.info("横書きとして検出されました")
            self.vertical_mode = False
        self.config.ocr.vertical_mode = self.vertical_mode

    def _get_sorted_image_files(self) -> list[tuple[int, Path]]:
        files = list(self.config.screenshot_dir.glob("page_*.png"))

        def get_page_number(path: Path) -> int:
            return int(path.stem.split("_")[1])

        sorted_files = sorted(files, key=get_page_number)
        return [(get_page_number(f), f) for f in sorted_files]

    def detect_direction_from_screenshots(self) -> None:
        if self.direction != DIRECTION_AUTO:
            return
        sorted_files = self._get_sorted_image_files()
        if not sorted_files:
            logger.warning("スクリーンショットがありません")
            return
        self._detect_and_apply_direction(sorted_files[0][1])
        mode_str = "縦書き" if self.vertical_mode else "横書き"
        logger.info("テキスト方向: %s モードで処理します", mode_str)

    def perform_ocr(self, max_workers: int = 4) -> None:
        ocr_config = self.config.ocr
        sorted_files = self._get_sorted_image_files()

        if not sorted_files:
            logger.warning("OCR対象のファイルがありません")
            return

        logger.info("OCR処理を開始します...")
        logger.info("縦書きモード: %s", ocr_config.vertical_mode)

        page_numbers = [page_num for page_num, _ in sorted_files]
        image_paths = [image_path for _, image_path in sorted_files]
        results = recognize_text_batch(image_paths, config=ocr_config, max_workers=max_workers)

        for page_num, text in zip(page_numbers, results, strict=True):
            self.ocr_results[page_num] = text
        logger.info("OCR処理が完了しました（%dページ）", len(self.ocr_results))

    def create_markdown(self) -> Path:
        md_path = self._get_output_path("md")
        return write_markdown(self.ocr_results, md_path)

    def create_pdf(self) -> Path:
        pdf_path = self._get_output_path("pdf")
        sorted_files = self._get_sorted_image_files()
        return write_pdf(sorted_files, pdf_path, self.config.pdf)

    def run(self) -> tuple[Path, Path]:
        self.take_screenshots()
        self.perform_ocr()
        md_path = self.create_markdown()
        pdf_path = self.create_pdf()
        logger.info("処理が完了しました:")
        logger.info("  Markdown: %s", md_path)
        logger.info("  PDF: %s", pdf_path)
        return md_path, pdf_path

    def preview_screenshot(self) -> Path:
        logger.info("プレビュー用スクリーンショットを取得します...")
        self.activate_kindle()
        content_region = self.get_kindle_content_region()
        logger.info("スクリーンショット領域: %s", content_region)
        logger.info("  リージョン: %s", self.region)

        preview_path = self.config.output_dir / "preview.png"
        self._take_screenshot(preview_path, content_region)
        logger.info("プレビューを保存しました: %s", preview_path)
        logger.info("このファイルを確認して、マージンやリージョンの設定が正しいかご確認ください。")
        return preview_path

    def run_from_screenshots(self) -> tuple[Path, Path]:
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
        logger.info("処理が完了しました:")
        logger.info("  Markdown: %s", md_path)
        logger.info("  PDF: %s", pdf_path)
        return md_path, pdf_path
