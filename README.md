# Kindle OCR Automation

Kindle の本を自動的にスクリーンショット撮影し、OCR でテキスト化して Google Drive にアップロードするツールです。

## 機能

- Kindle の全ページを自動でスクリーンショット
- Google Cloud Vision API を使用した OCR 処理
- テキストファイルと PDF ファイルの生成
- Google Drive への自動アップロード
- 一時ファイルの自動クリーンアップ

## セットアップ

1. 必要なパッケージのインストール:

```bash
# uvを使用してインストール
uv pip install -e .
```

2. Google Cloud Platform の設定:

   - Google Cloud Platform でプロジェクトを作成
   - Vision API と Drive API を有効化
   - サービスアカウントを作成し、認証情報（JSON）をダウンロード
   - ダウンロードした認証情報を`credentials.json`としてプロジェクトのルートディレクトリに配置

3. 環境変数の設定:
   - プロジェクトのルートディレクトリに`.env`ファイルを作成
   - 以下の形式で設定を記述:
     ```env
     # Google DriveのフォルダID
     GOOGLE_DRIVE_FOLDER_ID=your_folder_id
     ```
   - `.env`ファイルは Git にコミットしないでください（セキュリティのため）

## 使用方法

1. Kindle アプリを開き、対象の本を表示
2. スクリプトを実行:

```bash
python main.py
```

## 注意事項

- スクリプト実行中は Kindle アプリを操作しないでください
- スクリーンショットの取得中は画面を変更しないでください
- Google Cloud Platform の API 使用量に応じて課金が発生します
- 本の著作権に注意してください
- `.env`ファイルには機密情報が含まれるため、Git にコミットしないでください

## 出力ファイル

- テキストファイル（.txt）
- PDF ファイル（.pdf）
- ファイル名は OCR テキストの最初の 10 文字から自動生成されます
