# Kindle OCR

Kindle の本を自動的にスクリーンショット撮影し、OCR でテキスト化して Markdown と PDF に変換するツールです（macOS 専用）。

NotebookLM などの RAG ツールへの入力に最適化されています。

## 機能

- Kindle の全ページを自動でスクリーンショット
- macOS Vision Framework による高精度 OCR（日本語対応）
- **Markdown 出力**（RAG/NotebookLM 用）
- **テキストレイヤー付き PDF 出力**（検索可能）
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
# 基本的な使用法（スクショ → OCR → Markdown + PDF）
kindle-pdf --output "書籍名"

# または直接実行
python src/kindle_to_pdf/main.py --output "書籍名"
```

## 出力ファイル

```
output/
├── 書籍名.md    # NotebookLM用（純粋なOCRテキスト）
└── 書籍名.pdf   # 確認用（画像＋透明テキストレイヤー）
```

## コマンドライン引数

| オプション           | 短縮形 | 説明                                   | デフォルト     |
| -------------------- | ------ | -------------------------------------- | -------------- |
| `--output`           | `-o`   | 出力ファイル名（拡張子なし）           | タイムスタンプ |
| `--direction`        | `-d`   | ページ送り方向 (`left`/`right`)        | `right`        |
| `--region`           | `-r`   | キャプチャ領域 (`left`/`right`/`full`) | `full`         |
| `--screenshot-only`  | `-so`  | スクショのみ（OCR なし）               | -              |
| `--from-screenshots` | `-fs`  | 既存スクショから OCR 処理              | -              |

## 使用例

```bash
# 右方向ページ送りで全画面キャプチャ
kindle-pdf --output "機械学習入門"

# 見開き表示の右ページのみキャプチャ
kindle-pdf --output "技術書" --region right

# 既存のスクリーンショットから再処理
kindle-pdf --from-screenshots --output "再処理"

# スクリーンショットのみ取得（OCRは後で実行）
kindle-pdf --screenshot-only
```

## 注意事項

- スクリプト実行中は Kindle アプリを操作しないでください
- スクリーンショットの取得中は画面を変更しないでください
- 本の著作権に注意してください
- macOS 専用（Vision Framework を使用）
