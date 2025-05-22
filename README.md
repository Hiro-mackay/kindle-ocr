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

### コマンドライン引数

スクリプトは以下のコマンドライン引数をサポートしています：

```bash
python main.py [options]
```

#### オプション

- `--direction`, `-d`: ページ送りの方向を指定

  - 選択肢: `left` または `right`
  - デフォルト: `right`
  - 例: `python main.py --direction left`

- `--region`, `-r`: スクリーンショットの領域を指定

  - 選択肢: `left`（左半分）, `right`（右半分）, `full`（全体）
  - デフォルト: `full`
  - 例: `python main.py --region left`

- `--start-step`, `-s`: 処理の開始ステップを指定

  - 選択肢: `screenshot`, `ocr`, `create`, `upload`, `pdf`
  - 例: `python main.py --start-step ocr`

- `--end-step`, `-e`: 処理の終了ステップを指定
  - 選択肢: `screenshot`, `ocr`, `create`, `upload`, `pdf`
  - 例: `python main.py --end-step create`

#### 使用例

1. 左方向にページ送りして左半分のみをキャプチャ:

```bash
python main.py --direction left --region left
```

2. OCR 処理から開始してファイル作成まで実行:

```bash
python main.py --start-step ocr --end-step create
```

3. スクリーンショット取得のみを実行:

```bash
python main.py --start-step screenshot --end-step screenshot
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
