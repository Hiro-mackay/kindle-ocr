# Kindle OCR Automation

Kindle の本を自動的にスクリーンショット撮影し、OCR でテキスト化して Google Drive にアップロードするツールです。

## 機能

### vision_api_ocr

Google Cloud Vision API を使用して OCR 処理を行うツールです。

- Kindle の全ページを自動でスクリーンショット
- Google Cloud Vision API を使用した OCR 処理
- テキストファイルと PDF ファイルの生成
- Google Drive への自動アップロード
- 一時ファイルの自動クリーンアップ

### kindle_to_pdf

Kindle の本を高品質な PDF に変換するツールです。

- Kindle の全ページを自動でスクリーンショット
- 高品質な PDF ファイルの生成（高 DPI 対応）
- スクリーンショットのみの取得も可能
- ページ送りの方向とスクリーンショット領域のカスタマイズ
- 一時ファイルの自動クリーンアップ

## セットアップ

1. 必要なパッケージのインストール:

```bash
# uvを使用してインストール
uv pip install -e .
```

2. Google Cloud Platform の設定（vision_api_ocr を使用する場合のみ）:

   - Google Cloud Platform でプロジェクトを作成
   - Vision API と Drive API を有効化
   - サービスアカウントを作成し、認証情報（JSON）をダウンロード
   - ダウンロードした認証情報を`credentials.json`としてプロジェクトのルートディレクトリに配置

3. 環境変数の設定（vision_api_ocr を使用する場合のみ）:
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

### vision_api_ocr の実行

```bash
python src/vision_api_ocr/main.py
```

### kindle_to_pdf の実行

```bash
python src/kindle_to_pdf/main.py
```

### コマンドライン引数

両方のスクリプトは以下のコマンドライン引数をサポートしています：

```bash
python src/[tool_name]/main.py [options]
```

#### 共通オプション

- `--direction`, `-d`: ページ送りの方向を指定

  - 選択肢: `left` または `right`
  - デフォルト: `right`
  - 例: `python src/kindle_to_pdf/main.py --direction left`

- `--region`, `-r`: スクリーンショットの領域を指定

  - 選択肢: `left`（左半分）, `right`（右半分）, `full`（全体）
  - デフォルト: `full`
  - 例: `python src/kindle_to_pdf/main.py --region left`

#### vision_api_ocr 固有のオプション

- `--start-step`, `-s`: 処理の開始ステップを指定

  - 選択肢: `screenshot`, `ocr`, `create`, `upload`, `pdf`
  - 例: `python src/vision_api_ocr/main.py --start-step ocr`

- `--end-step`, `-e`: 処理の終了ステップを指定
  - 選択肢: `screenshot`, `ocr`, `create`, `upload`, `pdf`
  - 例: `python src/vision_api_ocr/main.py --end-step create`

#### kindle_to_pdf 固有のオプション

- `--screenshot-only`, `-S`: スクリーンショットの取得のみを実行し、PDF は作成しない

  - フラグオプション（値を指定する必要なし）
  - 例: `python src/kindle_to_pdf/main.py --screenshot-only`

#### 使用例

- 左方向にページ送りして左半分のみをキャプチャ:

```bash
python src/kindle_to_pdf/main.py --direction left --region left
```

- スクリーンショットの取得のみを実行:

```bash
python src/kindle_to_pdf/main.py --screenshot-only
```

## 注意事項

- スクリプト実行中は Kindle アプリを操作しないでください
- スクリーンショットの取得中は画面を変更しないでください
- vision_api_ocr を使用する場合、Google Cloud Platform の API 使用量に応じて課金が発生します
- 本の著作権に注意してください
- `.env`ファイルには機密情報が含まれるため、Git にコミットしないでください

## 出力ファイル

### vision_api_ocr

- テキストファイル（.txt）
- PDF ファイル（.pdf）
- ファイル名は OCR テキストの最初の 10 文字から自動生成されます

### kindle_to_pdf

- 高品質な PDF ファイル（.pdf）
- ファイル名はタイムスタンプから自動生成されます（--output オプションで指定可能）
