import argparse
import os
import re
import shutil
import subprocess
import time

import fitz  # PyMuPDF
import pyautogui
from PIL import Image

from .ocr import recognize_text

# PDFの最適化設定
PDF_GARBAGE = 4  # 未使用オブジェクトの削除レベル
PDF_DEFLATE = True  # 画像データの圧縮
PDF_CLEAN = True  # 重複オブジェクトの削除

# マージン設定（画面サイズに対する比率）
TOP_MARGIN = 0.12  # 上部の余白
BOTTOM_MARGIN = 0.04  # 下部の余白
LEFT_MARGIN = 0.05  # 左側の余白
RIGHT_MARGIN = 0.05  # 右側の余白
HALF_POSITION = 0.5  # 左右分割時の中央位置


class KindleToPDF:
    def __init__(
        self,
        page_turn_direction="right",
        region="full",
        output_filename=None,
    ):
        self.screenshot_dir = "screenshots"
        self.output_dir = "output"
        self.page_turn_direction = page_turn_direction
        self.region = region
        self.output_filename = output_filename
        self.ocr_results: dict[int, str] = {}  # ページ番号 -> OCRテキスト

        # 出力ディレクトリの作成
        os.makedirs(self.output_dir, exist_ok=True)

    def activate_kindle(self):
        """Kindleアプリを最前面に表示"""
        print("Kindleアプリを最前面に表示します...")
        try:
            script = '''
            tell application "Amazon Kindle"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script])
            time.sleep(2)
        except Exception as e:
            print(f"Kindleアプリの起動に失敗しました: {e!s}")
            print("Amazon Kindleアプリがインストールされていることを確認してください。")
            raise

    def get_kindle_content_region(self):
        """Kindleのコンテンツ表示領域を取得"""
        screen_width, screen_height = pyautogui.size()

        top_margin = int(screen_height * TOP_MARGIN)
        bottom_margin = int(screen_height * BOTTOM_MARGIN)

        if self.region == "left":
            left_margin = int(screen_width * LEFT_MARGIN)
            right_margin = int(screen_width * HALF_POSITION)
        elif self.region == "right":
            left_margin = int(screen_width * HALF_POSITION)
            right_margin = int(screen_width * (1 - RIGHT_MARGIN))
        else:  # 'full'
            left_margin = int(screen_width * LEFT_MARGIN)
            right_margin = int(screen_width * (1 - RIGHT_MARGIN))

        left = left_margin
        top = top_margin
        width = right_margin - left_margin
        height = screen_height - top_margin - bottom_margin

        print(f"画面サイズ: {screen_width}x{screen_height}")
        print(f"計算された領域: left={left}, top={top}, width={width}, height={height}")

        return (left, top, width, height)

    def take_screenshots(self):
        """Kindleの全ページのスクリーンショットを取得"""
        print("スクリーンショットの取得を開始します...")
        print(f"ページ送りの方向: {self.page_turn_direction}")

        if os.path.exists(self.screenshot_dir):
            print("古いスクリーンショットを削除します...")
            shutil.rmtree(self.screenshot_dir)

        os.makedirs(self.screenshot_dir, exist_ok=True)

        self.activate_kindle()

        content_region = self.get_kindle_content_region()
        print(f"スクリーンショット領域: {content_region}")

        page = 1
        last_screenshot = None

        while True:
            screenshot_path = os.path.join(self.screenshot_dir, f"page_{page}.png")

            x, y, width, height = content_region
            cmd = f'screencapture -x -C -R {x},{y},{width},{height} "{screenshot_path}"'
            subprocess.run(cmd, shell=True)

            screenshot = Image.open(screenshot_path)

            if last_screenshot is not None:
                if screenshot.tobytes() == last_screenshot.tobytes():
                    print("最後のページに到達しました")
                    os.remove(screenshot_path)
                    break

            last_screenshot = screenshot

            pyautogui.press(self.page_turn_direction)

            if page >= 1000:
                print("最大ページ数に達しました")
                break

            page += 1
            time.sleep(0.6)

        print(f"スクリーンショットの取得が完了しました。合計{page - 1}ページ")

    def _get_sorted_image_files(self) -> list[tuple[int, str]]:
        """スクリーンショットファイルをページ番号順でソートして返す"""

        def get_page_number(filename):
            match = re.search(r"page_(\d+)\.png", filename)
            if match:
                return int(match.group(1))
            return 0

        files = [f for f in os.listdir(self.screenshot_dir) if f.endswith(".png")]
        sorted_files = sorted(files, key=get_page_number)

        return [(get_page_number(f), f) for f in sorted_files]

    def perform_ocr(self):
        """全スクリーンショットに対してOCRを実行"""
        print("\nOCR処理を開始します...")

        sorted_files = self._get_sorted_image_files()
        total = len(sorted_files)

        for i, (page_num, filename) in enumerate(sorted_files, 1):
            image_path = os.path.join(self.screenshot_dir, filename)
            print(f"OCR処理中: {filename} ({i}/{total})")

            try:
                text = recognize_text(image_path)
                self.ocr_results[page_num] = text
            except Exception as e:
                print(f"  警告: OCR失敗 - {e!s}")
                self.ocr_results[page_num] = ""

        print(f"OCR処理が完了しました。{len(self.ocr_results)}ページ")

    def create_markdown(self) -> str:
        """OCR結果からMarkdownファイルを作成"""
        print("\nMarkdownファイルの作成を開始します...")

        if self.output_filename:
            md_path = os.path.join(self.output_dir, f"{self.output_filename}.md")
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            md_path = os.path.join(self.output_dir, f"kindle_book_{timestamp}.md")

        # ページ順にテキストを連結
        sorted_pages = sorted(self.ocr_results.keys())
        all_text = []

        for page_num in sorted_pages:
            text = self.ocr_results[page_num].strip()
            if text:
                all_text.append(text)

        # Markdownファイルに書き出し
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_text))

        print(f"Markdownファイルを作成しました: {md_path}")
        return md_path

    def create_pdf(self) -> str:
        """スクリーンショットからテキストレイヤー付きPDFを作成"""
        print("\nPDFの作成を開始します...")

        if self.output_filename:
            pdf_path = os.path.join(self.output_dir, f"{self.output_filename}.pdf")
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            pdf_path = os.path.join(self.output_dir, f"kindle_book_{timestamp}.pdf")

        doc = fitz.open()
        sorted_files = self._get_sorted_image_files()

        for page_num, filename in sorted_files:
            image_path = os.path.join(self.screenshot_dir, filename)
            print(f"PDF処理中: {filename}")

            img = Image.open(image_path)

            # PDFページを作成
            page = doc.new_page(width=img.width, height=img.height)

            # 画像を挿入
            page.insert_image(page.rect, filename=image_path)

            # OCRテキストがあれば透明テキストレイヤーとして追加
            if page_num in self.ocr_results and self.ocr_results[page_num]:
                text = self.ocr_results[page_num]
                # 透明テキストを追加（検索可能にするため）
                # フォントサイズを小さくし、透明度を0に設定
                text_rect = fitz.Rect(0, 0, img.width, img.height)
                page.insert_textbox(
                    text_rect,
                    text,
                    fontsize=1,
                    color=(1, 1, 1),  # 白色（背景に溶け込む）
                    opacity=0,  # 完全に透明
                )

        print("\nPDFの保存を開始します...")
        print("最適化設定:")
        print(f"  garbage={PDF_GARBAGE}: 未使用オブジェクトの削除")
        print(f"  deflate={PDF_DEFLATE}: 画像データの圧縮")
        print(f"  clean={PDF_CLEAN}: 重複オブジェクトの削除")

        doc.save(pdf_path, garbage=PDF_GARBAGE, deflate=PDF_DEFLATE, clean=PDF_CLEAN)
        doc.close()

        print(f"PDFファイルを作成しました: {pdf_path}")
        return pdf_path

    def run(self):
        """メイン処理の実行"""
        try:
            self.take_screenshots()
            self.perform_ocr()
            md_path = self.create_markdown()
            pdf_path = self.create_pdf()
            print("\n処理が完了しました:")
            print(f"  Markdown: {md_path}")
            print(f"  PDF: {pdf_path}")
        except Exception as e:
            print(f"\nエラーが発生しました: {e!s}")
            raise


def main():
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

    args = parser.parse_args()

    kindle = KindleToPDF(
        page_turn_direction=args.direction,
        region=args.region,
        output_filename=args.output,
    )

    try:
        if args.from_screenshots:
            # 既存のスクリーンショットから処理
            if not os.path.exists(kindle.screenshot_dir):
                raise FileNotFoundError("スクリーンショットディレクトリが存在しません")
            if not any(f.endswith(".png") for f in os.listdir(kindle.screenshot_dir)):
                raise FileNotFoundError("スクリーンショットディレクトリにPNGファイルがありません")

            kindle.perform_ocr()
            md_path = kindle.create_markdown()
            pdf_path = kindle.create_pdf()
            print("\n処理が完了しました:")
            print(f"  Markdown: {md_path}")
            print(f"  PDF: {pdf_path}")
            return

        if args.screenshot_only:
            # スクリーンショットのみ
            kindle.take_screenshots()
            print("\nスクリーンショットの取得が完了しました")
            return

        # 通常処理（スクショ→OCR→MD/PDF）
        kindle.run()

    except Exception as e:
        print(f"\nエラーが発生しました: {e!s}")
        raise


if __name__ == "__main__":
    main()
