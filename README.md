# Kindle to PDF

Kindle の本を自動的にスクリーンショット撮影し、高品質な PDF に変換するツールです（macOS専用）。

## 機能

- Kindle の全ページを自動でスクリーンショット
- 高品質な PDF ファイルの生成
- スクリーンショットのみの取得も可能
- ページ送りの方向とスクリーンショット領域のカスタマイズ
- 最終ページの自動検出

## セットアップ

```bash
# uvを使用してインストール
uv pip install -e .
```

## 使用方法

1. Kindle アプリを開き、対象の本を表示
2. スクリプトを実行:

```bash
# 基本的な使用法
python src/kindle_to_pdf/main.py

# または、インストール後はコマンドで実行
kindle-pdf
```

### コマンドライン引数

```bash
python src/kindle_to_pdf/main.py [options]
```

- `--direction`, `-d`: ページ送りの方向を指定
  - 選択肢: `left` または `right`
  - デフォルト: `right`

- `--region`, `-r`: スクリーンショットの領域を指定
  - 選択肢: `left`（左半分）, `right`（右半分）, `full`（全体）
  - デフォルト: `full`

- `--output`, `-o`: 出力PDFのファイル名（拡張子なし）

- `--screenshot-only`, `-so`: スクリーンショットの取得のみを実行し、PDF は作成しない

- `--from-screenshots`, `-fs`: 既存のスクリーンショットからPDFを作成（スクリーンショットの取得をスキップ）

### 使用例

```bash
# 左方向にページ送りして左半分のみをキャプチャ
python src/kindle_to_pdf/main.py --direction left --region left

# スクリーンショットの取得のみを実行
python src/kindle_to_pdf/main.py --screenshot-only

# 既存のスクリーンショットからPDFを作成
python src/kindle_to_pdf/main.py --from-screenshots

# 出力ファイル名を指定
python src/kindle_to_pdf/main.py --output my_book
```

## 注意事項

- スクリプト実行中は Kindle アプリを操作しないでください
- スクリーンショットの取得中は画面を変更しないでください
- 本の著作権に注意してください

## 出力ファイル

- PDF ファイル: `output/` ディレクトリに保存
- ファイル名はタイムスタンプから自動生成されます（`--output` オプションで指定可能）
