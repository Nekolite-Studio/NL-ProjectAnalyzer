# NL-ProjectAnalyzer

NL-ProjectAnalyzerは、プロジェクトのコードベースを解析し、行数、ファイルサイズ、コードの複雑度などを可視化するPython製のツールです。

詳細なHTMLレポートとCSVデータを自動生成し、プロジェクトの「健康診断」を支援します。

## 主な機能

* プロジェクト統計: 総行数、ファイル数、拡張子別の分布などを集計
* HTMLレポート生成: Chart.jsを使用したインタラクティブなグラフと、検索可能なファイル一覧テーブルを生成
* コード複雑度計測 (Optional): lizard を使用して、ファイルごとのサイクロマティック複雑度を計測し、複雑すぎるコードを可視化
* 柔軟な除外設定: .gitignore の自動読み込みに加え、専用の設定ファイル .analyzerignore で解析対象を詳細に制御
* JSONエクスポート: 複雑度が高いファイルのリストをJSON形式でクリップボードにコピー

## インストール

1. Python 3.6以上がインストールされている必要があります。
2. このリポジトリをクローンするか、スクリプトをダウンロードします。
3. （推奨）コード複雑度の計測を有効にするには、lizard をインストールします。

```bash
pip install lizard
```

## 使い方

ターミナルでスクリプトを実行します。

```bash
# カレントディレクトリを解析
python project_analyzer.py

# 特定のディレクトリを解析
python project_analyzer.py /path/to/your/project

# 出力先を指定して解析
python project_analyzer.py ./src -o ./my_reports
```

実行が完了すると、outputs/ フォルダ（または指定したフォルダ）内に以下のファイルが生成されます。

* `project_report.html`: ブラウザで閲覧する詳細レポート
* `file_stats_report.csv`: ファイルごとの詳細統計データ
* `folder_stats_report.csv`: フォルダごとの集計データ

## 定期実行・自動化のヒント

### Git Pre-commit Hook として利用する

コミットする前に自動的に解析を実行し、最新のレポートを生成するように設定できます。
.git/hooks/pre-commit ファイルを作成（または編集）し、以下のように記述します。

```bash
# .git/hooks/pre-commit

echo "Running NL-ProjectAnalyzer..."
./analyzer-run.sh -o ./docs/analysis_report

# 生成されたレポートをコミットに含める場合（任意）
# git add ./docs/analysis_report
```

実行権限を付与することを忘れないでください: `chmod +x .git/hooks/pre-commit`

## 設定ファイル (.analyzerignore)

解析から除外したいファイルやディレクトリがある場合、以下の優先順位で設定が適用されます。

1. **Global**: スクリプトと同じディレクトリにある `.analyzerignore` (全プロジェクト共通)
2. **Git**: 解析対象ディレクトリにある `.gitignore`
3. **Local**: 解析対象ディレクトリにある `.analyzerignore` (プロジェクト固有)

## 書式例

.gitignore と同様の書式が使用できます。

```ignore
# コメント
node_modules
dist
*.log
src/temp/*
```

---

※このドキュメントはGemini 3 Proによって生成されています
