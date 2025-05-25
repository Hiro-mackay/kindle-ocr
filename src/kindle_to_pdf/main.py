import os
import time
import pyautogui
from PIL import Image
import fitz  # PyMuPDF
import shutil
from dotenv import load_dotenv
import argparse
import subprocess
import re
from pathlib import Path

# .envファイルから環境変数を読み込む
load_dotenv()

# PDFの最適化設定
PDF_GARBAGE = 4  # 未使用オブジェクトの削除レベル
PDF_DEFLATE = True  # 画像データの圧縮
PDF_CLEAN = True  # 重複オブジェクトの削除

# マージン設定（画面サイズに対する比率）
TOP_MARGIN = 0.12      # 上部の余白
BOTTOM_MARGIN = 0.04   # 下部の余白
LEFT_MARGIN = 0.02    # 左側の余白
RIGHT_MARGIN = 0.12   # 右側の余白
HALF_POSITION = 0.5   # 左右分割時の中央位置

class KindleToPDF:
    def __init__(self, page_turn_direction='right', region='full', dpi=300, output_filename=None):
        self.screenshot_dir = "screenshots"
        self.output_dir = "output"
        self.page_turn_direction = page_turn_direction  # ページ送りの方向
        self.region = region  # スクリーンショットの領域
        self.dpi = dpi  # 画像のDPI設定
        self.output_filename = output_filename  # 出力PDFのファイル名
        
        # 出力ディレクトリの作成
        os.makedirs(self.output_dir, exist_ok=True)

    def activate_kindle(self):
        """Kindleアプリを最前面に表示"""
        print("Kindleアプリを最前面に表示します...")
        try:
            # AppleScriptを使用してKindleアプリを起動し、最前面に表示
            script = '''
            tell application "Amazon Kindle"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', script])
            time.sleep(2)  # アプリが最前面に表示されるのを待つ
        except Exception as e:
            print(f"Kindleアプリの起動に失敗しました: {str(e)}")
            print("Amazon Kindleアプリがインストールされていることを確認してください。")
            raise

    def get_kindle_content_region(self):
        """Kindleのコンテンツ表示領域を取得"""
        # 画面のサイズを取得
        screen_width, screen_height = pyautogui.size()
        
        # マージンから座標を計算
        top_margin = int(screen_height * TOP_MARGIN)
        bottom_margin = int(screen_height * BOTTOM_MARGIN)
        
        # 領域に応じて左右のマージンを設定
        if self.region == 'left':
            left_margin = int(screen_width * LEFT_MARGIN)
            right_margin = int(screen_width * HALF_POSITION)
        elif self.region == 'right':
            left_margin = int(screen_width * HALF_POSITION)
            right_margin = int(screen_width * RIGHT_MARGIN)
        else:  # 'full'
            left_margin = int(screen_width * LEFT_MARGIN)
            right_margin = int(screen_width * RIGHT_MARGIN)
        
        # コンテンツ領域の座標を計算
        left = left_margin
        top = top_margin
        width = right_margin - left_margin
        height = screen_height - top_margin - bottom_margin
        
        return (left, top, width, height)

    def take_screenshots(self):
        """Kindleの全ページのスクリーンショットを取得"""
        print("スクリーンショットの取得を開始します...")
        print(f"ページ送りの方向: {self.page_turn_direction}")
        
        # 古いスクリーンショットをクリーンアップ
        if os.path.exists(self.screenshot_dir):
            print("古いスクリーンショットを削除します...")
            shutil.rmtree(self.screenshot_dir)
        
        # スクリーンショットディレクトリの作成
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Kindleアプリを最前面に表示
        self.activate_kindle()
        
        # コンテンツ領域を取得
        content_region = self.get_kindle_content_region()
        print(f"スクリーンショット領域: {content_region}")
        
        page = 1
        last_screenshot = None
        
        while True:
            # 高画質スクリーンショットを取得
            screenshot_path = os.path.join(self.screenshot_dir, f"page_{page}.png")
            
            # screencaptureコマンドを使用して高画質スクリーンショットを取得
            # -x: 音を消す
            # -C: カーソルを表示しない
            # -R: 指定した領域をキャプチャ
            x, y, width, height = content_region
            cmd = f'screencapture -x -C -R {x},{y},{width},{height} "{screenshot_path}"'
            subprocess.run(cmd, shell=True)
            
            # スクリーンショットを読み込んで比較用に保存
            screenshot = Image.open(screenshot_path)
            
            # 最後のページかどうかを確認
            if last_screenshot is not None:
                # 前のページと同じ画像かどうかを確認
                if screenshot.tobytes() == last_screenshot.tobytes():
                    print("最後のページに到達しました")
                    # 最後の重複したスクリーンショットを削除
                    os.remove(screenshot_path)
                    break
            
            # 現在のスクリーンショットを保存
            last_screenshot = screenshot
            
            # 指定された方向にページを送る
            pyautogui.press(self.page_turn_direction)
            
            # 最大ページ数に達した場合
            if page >= 1000:  # 最大ページ数を設定
                print("最大ページ数に達しました")
                break
                
            page += 1
            
            time.sleep(0.6)  # ページ遷移の待機時間
            
        print(f"スクリーンショットの取得が完了しました。合計{page}ページ")

    def create_pdf(self):
        """スクリーンショットからPDFを作成"""
        print("PDFの作成を開始します...")
        
        # 出力ファイル名の設定
        if self.output_filename:
            pdf_path = os.path.join(self.output_dir, f"{self.output_filename}.pdf")
        else:
            # タイムスタンプを使用してファイル名を生成
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            pdf_path = os.path.join(self.output_dir, f"kindle_book_{timestamp}.pdf")
        
        # 新しいPDFドキュメントを作成
        doc = fitz.open()
        
        # ファイル名からページ番号を抽出してソート
        def get_page_number(filename):
            match = re.search(r'page_(\d+)\.png', filename)
            if match:
                return int(match.group(1))
            return 0
        
        # ファイルをページ番号でソート
        files = sorted(
            [f for f in os.listdir(self.screenshot_dir) if f.endswith('.png')],
            key=get_page_number
        )
        
        for filename in files:
            image_path = os.path.join(self.screenshot_dir, filename)
            print(f"処理中: {filename}")
            
            # 画像を開く
            img = Image.open(image_path)
            
            # 画像を一時ファイルとして保存（高品質設定）
            temp_img_path = os.path.join(self.screenshot_dir, f"temp_{filename}")
            img.save(temp_img_path, format='PNG', quality=100, optimize=False)
            
            # 高品質なPDFページを作成
            page = doc.new_page(width=img.width, height=img.height)
            
            # 画像をPDFページに挿入
            page.insert_image(page.rect, filename=temp_img_path)
            
            # 画像をテキストレイヤーとして追加
            page.insert_text((10, 10), " ", fontsize=1)  # 最小のテキストを追加してテキストレイヤーを確保
            
            # 一時ファイルを削除
            os.remove(temp_img_path)
        
        # PDFの保存設定を表示
        print("\nPDFの保存を開始します...")
        print("最適化設定:")
        print(f"-garbage={PDF_GARBAGE}: 未使用オブジェクトの削除")
        print(f"-deflate={PDF_DEFLATE}: 画像データの圧縮")
        print(f"-clean={PDF_CLEAN}: 重複オブジェクトの削除")
        
        # PDFを保存（高品質設定）
        doc.save(pdf_path, garbage=PDF_GARBAGE, deflate=PDF_DEFLATE, clean=PDF_CLEAN)
        doc.close()
        
        return pdf_path

    def run(self):
        """メイン処理の実行"""
        try:
            self.take_screenshots()
            pdf_path = self.create_pdf()
            print(f"処理が完了しました。PDFファイル: {pdf_path}")
        except Exception as e:
            print(f"\nエラーが発生しました: {str(e)}")
            raise

def main():
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description='Kindleの本をスクリーンショットからPDFに変換します')
    parser.add_argument('--direction', '-d',
                      choices=['left', 'right'],
                      default='right',
                      help='ページ送りの方向 (left または right)')
    parser.add_argument('--region', '-r',
                      choices=['left', 'right', 'full'],
                      default='full',
                      help='スクリーンショットの領域 (left: 左半分, right: 右半分, full: 全体)')
    parser.add_argument('--dpi', '-p',
                      type=int,
                      default=300,
                      help='画像のDPI設定 (デフォルト: 300)')
    parser.add_argument('--output', '-o',
                      help='出力PDFのファイル名（拡張子なし）')
    parser.add_argument('--screenshot-only', '-so',
                      action='store_true',
                      help='スクリーンショットの取得のみを実行し、PDFは作成しない')
    parser.add_argument('--from-screenshots', '-fs',
                      action='store_true',
                      help='既存のスクリーンショットからPDFを作成（スクリーンショットの取得をスキップ）')

    args = parser.parse_args()
    
    # KindleToPDFのインスタンスを作成
    kindle_to_pdf = KindleToPDF(
        page_turn_direction=args.direction,
        region=args.region,
        dpi=args.dpi,
        output_filename=args.output
    )
    
    try:        
        # 既存のスクリーンショットからPDFを作成する場合
        if args.from_screenshots:
            if not os.path.exists(kindle_to_pdf.screenshot_dir):
                raise Exception("スクリーンショットディレクトリが存在しません")
            if not any(f.endswith('.png') for f in os.listdir(kindle_to_pdf.screenshot_dir)):
                raise Exception("スクリーンショットディレクトリにPNGファイルが存在しません")
            pdf_path = kindle_to_pdf.create_pdf()
            print(f"PDFファイルが作成されました: {pdf_path}")
            return

        # スクリーンショットの取得
        kindle_to_pdf.take_screenshots()
        
        # screenshot-onlyオプションが指定されていない場合のみPDFを作成
        if not args.screenshot_only:
            pdf_path = kindle_to_pdf.create_pdf()
            print(f"PDFファイルが作成されました: {pdf_path}")
        
        print("処理が完了しました")
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        raise

if __name__ == "__main__":
    main() 