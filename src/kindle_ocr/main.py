import os
import time
import pyautogui
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import shutil
from dotenv import load_dotenv
import argparse
import subprocess
import re

# .envファイルから環境変数を読み込む
load_dotenv()

class KindleOCR:
    def __init__(self, page_turn_direction='right', region='full'):
        self.screenshot_dir = "screenshots"
        self.output_dir = "output"
        self.credentials_path = "credentials.json"  # Google Cloud認証情報のパス
        self.drive_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')  # .envファイルからフォルダIDを取得
        self.page_turn_direction = page_turn_direction  # ページ送りの方向
        self.region = region  # スクリーンショットの領域
        
        if not self.drive_folder_id:
            print("警告: .envファイルにGOOGLE_DRIVE_FOLDER_IDが設定されていません。")
            print(".envファイルを作成し、以下の形式で設定してください：")
            print("GOOGLE_DRIVE_FOLDER_ID=your_folder_id")
        
        # 古いスクリーンショットをクリーンアップ
        if os.path.exists(self.screenshot_dir):
            print("古いスクリーンショットを削除します...")
            shutil.rmtree(self.screenshot_dir)
        
        # 必要なディレクトリの作成
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Vision APIクライアントの初期化
        try:
            self.vision_client = vision.ImageAnnotatorClient(
                credentials=service_account.Credentials.from_service_account_file(self.credentials_path)
            )
        except Exception as e:
            print("Vision APIの初期化に失敗しました。")
            print("1. credentials.jsonが正しい場所にあることを確認してください。")
            print("2. Google Cloud ConsoleでVision APIが有効になっていることを確認してください。")
            raise
        
        # Google Drive APIの初期化
        try:
            self.drive_service = build('drive', 'v3', credentials=service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=['https://www.googleapis.com/auth/drive.file']
            ))
        except Exception as e:
            print("Google Drive APIの初期化に失敗しました。")
            print("1. credentials.jsonが正しい場所にあることを確認してください。")
            print("2. Google Cloud ConsoleでDrive APIが有効になっていることを確認してください。")
            print("   https://console.cloud.google.com/apis/library/drive.googleapis.com")
            raise

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
        
        # Kindleアプリのコンテンツ領域を計算
        # 上部のメニューバーとナビゲーションバーを除外
        top_margin = int(screen_height * 0.1)  # 上部の余白（メニューバー + ナビゲーションバー）
        bottom_margin = int(screen_height * 0.1)  # 下部の余白
        
        # 領域に応じて右側のマージンを設定
        if self.region == 'left':
            left_margin = int(screen_width * 0.05)  # 左側の余白
            right_margin = int(screen_width * 0.5)  # 左半分
        elif self.region == 'right':
            left_margin = int(screen_width * 0.5)  # 右半分の開始位置
            right_margin = int(screen_width * 0.95)  # 右端の余白
        else:  # 'full'
            left_margin = int(screen_width * 0.05)  # 左側の余白
            right_margin = int(screen_width * 0.95)  # 全体
        
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

    def perform_ocr(self):
        """スクリーンショットからOCRを実行"""
        print("OCR処理を開始します...")
        all_text = []
        
        # ファイル名からページ番号を抽出してソート
        def get_page_number(filename):
            # page_数字.png の形式から数字を抽出
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
            
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if texts:
                all_text.append(texts[0].description)
        
        return '\n'.join(all_text)

    def create_files(self, text):
        """テキストファイルを作成"""
        # ファイル名を生成（最初の10文字）
        filename = text[:10].strip().replace(' ', '_')
        
        # テキストファイルの作成
        txt_path = os.path.join(self.output_dir, f"{filename}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return txt_path

    def upload_to_drive(self, file_paths):
        """Google Driveにファイルをアップロード"""
        print("Google Driveへのアップロードを開始します...")
        
        try:
            for file_path in file_paths:
                file_metadata = {
                    'name': os.path.basename(file_path),
                    'parents': [self.drive_folder_id] if self.drive_folder_id else None
                }
                
                media = MediaFileUpload(file_path, resumable=True)
                self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            print("アップロードが完了しました")
        except HttpError as error:
            print("\nGoogle Drive APIエラーが発生しました:")
            if error.resp.status == 403:
                print("1. Google Cloud ConsoleでDrive APIが有効になっていることを確認してください。")
                print("   https://console.cloud.google.com/apis/library/drive.googleapis.com")
                print("2. サービスアカウントに適切な権限が付与されていることを確認してください。")
                print("3. credentials.jsonが正しいプロジェクトのものであることを確認してください。")
            else:
                print(f"エラーコード: {error.resp.status}")
                print(f"エラーメッセージ: {error.content}")
            raise
        except Exception as e:
            print(f"\n予期せぬエラーが発生しました: {str(e)}")
            raise

    def run(self):
        """メイン処理の実行"""
        try:
            self.take_screenshots()
            text = self.perform_ocr()
            txt_path = self.create_files(text)
            self.upload_to_drive([txt_path])
            print("処理が完了しました")
        except Exception as e:
            print(f"\nエラーが発生しました: {str(e)}")
            print("\nトラブルシューティング:")
            print("1. Google Cloud Consoleで必要なAPIが有効になっていることを確認してください。")
            print("2. credentials.jsonが正しい場所にあり、有効な認証情報であることを確認してください。")
            print("3. .envファイルに正しいGOOGLE_DRIVE_FOLDER_IDが設定されていることを確認してください。")
            raise

def main():
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description='Kindleの本をOCRでテキスト化します')
    parser.add_argument('--direction', '-d',
                      choices=['left', 'right'],
                      default='right',
                      help='ページ送りの方向 (left または right)')
    parser.add_argument('--region', '-r',
                      choices=['left', 'right', 'full'],
                      default='full',
                      help='スクリーンショットの領域 (left: 左半分, right: 右半分, full: 全体)')
    parser.add_argument('--start-step', '-s',
                      choices=['screenshot', 'ocr', 'create', 'upload', 'pdf'],
                      help='開始するステップ (screenshot: スクリーンショット, ocr: OCR処理, create: ファイル作成, upload: アップロード, pdf: PDF作成)')
    parser.add_argument('--end-step', '-e',
                      choices=['screenshot', 'ocr', 'create', 'upload', 'pdf'],
                      help='終了するステップ (screenshot: スクリーンショット, ocr: OCR処理, create: ファイル作成, upload: アップロード, pdf: PDF作成)')

    args = parser.parse_args()
    
    # KindleOCRのインスタンスを作成
    kindle_ocr = KindleOCR(page_turn_direction=args.direction, region=args.region)
    
    try:        
        # 通常のOCR処理
        steps = ['screenshot', 'ocr', 'create', 'upload']
        start_idx = steps.index(args.start_step) if args.start_step else 0
        end_idx = steps.index(args.end_step) if args.end_step else len(steps) - 1
        
        if start_idx <= 0:  # screenshot
            kindle_ocr.take_screenshots()
        
        if start_idx <= 1 and end_idx >= 1:  # ocr
            text = kindle_ocr.perform_ocr()
        
        if start_idx <= 2 and end_idx >= 2:  # create
            txt_path = kindle_ocr.create_files(text)
        
        if start_idx <= 3 and end_idx >= 3:  # upload
            kindle_ocr.upload_to_drive([txt_path])
        
        print("処理が完了しました")
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")
        print("\nトラブルシューティング:")
        print("1. Google Cloud Consoleで必要なAPIが有効になっていることを確認してください。")
        print("2. credentials.jsonが正しい場所にあり、有効な認証情報であることを確認してください。")
        print("3. .envファイルに正しいGOOGLE_DRIVE_FOLDER_IDが設定されていることを確認してください。")
        raise

if __name__ == "__main__":
    main()
