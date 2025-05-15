import os
import time
import pyautogui
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from reportlab.pdfgen import canvas
import shutil
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

class KindleOCR:
    def __init__(self):
        self.screenshot_dir = "screenshots"
        self.output_dir = "output"
        self.credentials_path = "credentials.json"  # Google Cloud認証情報のパス
        self.drive_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')  # .envファイルからフォルダIDを取得
        
        if not self.drive_folder_id:
            print("警告: .envファイルにGOOGLE_DRIVE_FOLDER_IDが設定されていません。")
            print(".envファイルを作成し、以下の形式で設定してください：")
            print("GOOGLE_DRIVE_FOLDER_ID=your_folder_id")
        
        # 必要なディレクトリの作成
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Vision APIクライアントの初期化
        self.vision_client = vision.ImageAnnotatorClient(
            credentials=service_account.Credentials.from_service_account_file(self.credentials_path)
        )
        
        # Google Drive APIの初期化
        self.drive_service = build('drive', 'v3', credentials=service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=['https://www.googleapis.com/auth/drive.file']
        ))

    def take_screenshots(self):
        """Kindleの全ページのスクリーンショットを取得"""
        print("スクリーンショットの取得を開始します...")
        page = 1
        
        while True:
            # スクリーンショットを取得
            screenshot = pyautogui.screenshot()
            screenshot_path = os.path.join(self.screenshot_dir, f"page_{page}.png")
            screenshot.save(screenshot_path)
            
            # 右矢印キーを押して次のページへ
            pyautogui.press('right')
            time.sleep(2)  # ページ遷移の待機時間
            
            # 最後のページかどうかを確認（ここでは適当な条件を設定）
            if page >= 1000:  # 最大ページ数を設定
                break
                
            page += 1
            
        print(f"スクリーンショットの取得が完了しました。合計{page}ページ")

    def perform_ocr(self):
        """スクリーンショットからOCRを実行"""
        print("OCR処理を開始します...")
        all_text = []
        
        for filename in sorted(os.listdir(self.screenshot_dir)):
            if filename.endswith('.png'):
                image_path = os.path.join(self.screenshot_dir, filename)
                
                with open(image_path, 'rb') as image_file:
                    content = image_file.read()
                
                image = vision.Image(content=content)
                response = self.vision_client.text_detection(image=image)
                texts = response.text_annotations
                
                if texts:
                    all_text.append(texts[0].description)
        
        return '\n'.join(all_text)

    def create_files(self, text):
        """テキストファイルとPDFファイルを作成"""
        # ファイル名を生成（最初の10文字）
        filename = text[:10].strip().replace(' ', '_')
        
        # テキストファイルの作成
        txt_path = os.path.join(self.output_dir, f"{filename}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # PDFファイルの作成
        pdf_path = os.path.join(self.output_dir, f"{filename}.pdf")
        c = canvas.Canvas(pdf_path)
        y = 800  # 開始位置
        for line in text.split('\n'):
            if y < 50:  # ページの下端に達したら新しいページを作成
                c.showPage()
                y = 800
            c.drawString(50, y, line)
            y -= 12
        c.save()
        
        return txt_path, pdf_path

    def upload_to_drive(self, file_paths):
        """Google Driveにファイルをアップロード"""
        print("Google Driveへのアップロードを開始します...")
        
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

    def cleanup(self):
        """一時ファイルの削除"""
        print("一時ファイルを削除します...")
        shutil.rmtree(self.screenshot_dir)
        print("クリーンアップが完了しました")

    def run(self):
        """メイン処理の実行"""
        try:
            self.take_screenshots()
            text = self.perform_ocr()
            txt_path, pdf_path = self.create_files(text)
            self.upload_to_drive([txt_path, pdf_path])
            self.cleanup()
            print("処理が完了しました")
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    kindle_ocr = KindleOCR()
    kindle_ocr.run()
