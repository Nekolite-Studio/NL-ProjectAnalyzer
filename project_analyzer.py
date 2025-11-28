import os
import sys
import fnmatch
import string
import statistics
import math
import csv
import json
import argparse
from datetime import datetime
from collections import Counter, defaultdict

# ==========================================
# オプショナル依存関係の読み込み
# ==========================================
try:
    import lizard
    HAS_LIZARD = True
except ImportError:
    HAS_LIZARD = False

# ==========================================
# 定数・初期設定
# ==========================================

TOOL_NAME = "NL-ProjectAnalyzer"
REPO_URL = "https://github.com/Nekolite-Studio/NL-ProjectAnalyzer"
VERSION = "1.3.1"

# バイナリとして扱う（テキスト解析をスキップする）拡張子
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', 
    '.exe', '.dll', '.so', '.bin', '.dat', '.mp3', '.mp4', '.avi', '.mov',
    '.woff', '.woff2', '.ttf', '.eot'
}

BLOCK_SIZE = 4096

# ==========================================
# クラス定義
# ==========================================

class IgnoreMatcher:
    """
    複数のソース（グローバル設定、.gitignore、ローカル設定）からの
    除外パターンを管理し、パスが除外対象か判定するクラス
    """
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.patterns = []
        
        # 1. グローバル設定（スクリプトと同じ場所にある .analyzerignore）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        global_ignore = os.path.join(script_dir, '.analyzerignore')
        if os.path.exists(global_ignore):
            self.load_patterns(global_ignore)

        # 2. プロジェクトの .gitignore
        git_ignore = os.path.join(root_dir, '.gitignore')
        if os.path.exists(git_ignore):
            self.load_patterns(git_ignore)

        # 3. プロジェクト固有設定 (.analyzerignore)
        local_ignore = os.path.join(root_dir, '.analyzerignore')
        if os.path.exists(local_ignore):
            self.load_patterns(local_ignore)

    def load_patterns(self, filepath):
        """ファイルを読み込み、パターンリストに追加する"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    self.patterns.append(line)
        except Exception as e:
            print(f"Warning: Failed to load ignore file {filepath}: {e}", file=sys.stderr)

    def is_ignored(self, path):
        """
        指定されたパス（絶対パスまたはルートからの相対パス）が
        除外パターンに一致するか判定する
        """
        # 相対パスに変換（判定の基準とするため）
        try:
            rel_path = os.path.relpath(path, self.root_dir)
        except ValueError:
            rel_path = path

        # Windowsパスの修正
        rel_path = rel_path.replace(os.sep, '/')
        name = os.path.basename(path)

        for pattern in self.patterns:
            clean_pattern = pattern.rstrip('/')
            
            # 1. 名前だけでマッチ (例: *.log, node_modules)
            if fnmatch.fnmatch(name, clean_pattern):
                return True
            
            # 2. パス全体でマッチ (例: src/temp/*)
            if fnmatch.fnmatch(rel_path, clean_pattern):
                return True
                
            # 3. ディレクトリ配下のマッチ (例: dist/ が指定された場合 dist/app.js も除外)
            if pattern.endswith('/') or os.path.isdir(os.path.join(self.root_dir, pattern)):
                 if rel_path.startswith(clean_pattern + '/'):
                     return True
                     
        return False


class FileStats:
    def __init__(self, filepath=None, root_dir=None):
        self.filepath = filepath
        if filepath and root_dir:
            try:
                self.relpath = os.path.relpath(filepath, root_dir)
            except ValueError:
                self.relpath = filepath
        else:
            self.relpath = filepath

        self.filename = os.path.basename(filepath) if filepath else ""
        self.count = 0
        self.size = 0
        self.disk_usage = 0
        self.char_count = 0
        self.char_count_no_space = 0
        self.line_count = 0
        self.word_counter = Counter()
        self.lines_lengths = []
        self.extensions = Counter()
        self.skipped = False
        self.stats_summary = {}
        
        # 複雑度関連 (lizard導入時のみ有効)
        self.complexity_avg = 0
        self.complexity_max = 0
        self.functions_count = 0

    def add(self, other):
        """集計データの合算"""
        self.count += other.count
        self.size += other.size
        self.disk_usage += other.disk_usage
        self.char_count += other.char_count
        self.char_count_no_space += other.char_count_no_space
        self.line_count += other.line_count
        self.word_counter.update(other.word_counter)
        self.lines_lengths.extend(other.lines_lengths)
        self.extensions.update(other.extensions)
        
        if other.complexity_max > self.complexity_max:
            self.complexity_max = other.complexity_max
            
        if other.skipped:
            self.skipped += 1

    def to_dict(self):
        """JSONシリアライズ用"""
        data = {
            "path": self.relpath,
            "name": self.filename,
            "ext": list(self.extensions.keys())[0] if self.extensions else "",
            "size": self.size,
            "lines": self.line_count,
            "chars": self.char_count,
            "words": sum(self.word_counter.values()),
            "avg_line_len": self.stats_summary.get('mean', 0),
            "is_binary": self.skipped
        }
        
        if HAS_LIZARD and not self.skipped and self.functions_count > 0:
            data["complexity_avg"] = self.complexity_avg
            data["complexity_max"] = self.complexity_max
        else:
            data["complexity_avg"] = 0
            data["complexity_max"] = 0
        
        return data

# ==========================================
# ユーティリティ関数
# ==========================================

def is_binary_file(filepath):
    """バイナリファイルかどうかを判定"""
    _, ext = os.path.splitext(filepath)
    if ext.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\0' in chunk:
                return True
    except Exception:
        return True
    return False

def get_list_stats(num_list):
    """数値リストの統計情報を取得"""
    if not num_list:
        return {"min": 0, "max": 0, "mean": 0, "median": 0}
    
    data = sorted(num_list)
    return {
        "min": data[0], 
        "max": data[-1], 
        "mean": round(statistics.mean(data), 2), 
        "median": statistics.median(data)
    }

def analyze_complexity(filepath, stats_obj):
    """lizardを使用してサイクロマティック複雑度を計測"""
    if not HAS_LIZARD or stats_obj.skipped:
        return

    try:
        analysis = lizard.analyze_file(filepath)
        stats_obj.functions_count = len(analysis.function_list)
        
        if stats_obj.functions_count > 0:
            stats_obj.complexity_avg = round(analysis.average_cyclomatic_complexity, 2)
            # 関数ごとの最大複雑度を取得
            stats_obj.complexity_max = max([f.cyclomatic_complexity for f in analysis.function_list])
    except Exception as e:
        # 解析失敗時は静かに無視
        pass

def calculate_stats(filepath, root_dir):
    """単一ファイルの統計情報を計算"""
    stats = FileStats(filepath, root_dir)
    stats.count = 1
    
    try:
        st = os.stat(filepath)
        stats.size = st.st_size
        if hasattr(st, 'st_blocks'):
            stats.disk_usage = st.st_blocks * 512
        else:
            stats.disk_usage = math.ceil(stats.size / BLOCK_SIZE) * BLOCK_SIZE

        _, ext = os.path.splitext(filepath)
        stats.extensions[ext.lower() or 'no_ext'] += 1

        if is_binary_file(filepath):
            stats.skipped = True
            return stats

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            stats.skipped = True
            return stats

        stats.char_count = len(content)
        stats.char_count_no_space = len(content.translate(str.maketrans('', '', string.whitespace)))
        lines = content.splitlines()
        stats.line_count = len(lines)
        stats.lines_lengths = [len(line) for line in lines]
        
        words = content.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation))).split()
        stats.word_counter.update(words)
        
        stats.stats_summary = get_list_stats(stats.lines_lengths)
        
        # 複雑度計測
        analyze_complexity(filepath, stats)

    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
    
    return stats

def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

# ==========================================
# レポート出力処理
# ==========================================

def save_csv_reports(file_details_list, folder_stats_map, output_dir):
    # 1. ファイル詳細レポート
    csv_file = os.path.join(output_dir, 'file_stats_report.csv')
    headers = [
        'FilePath', 'FileName', 'Extension', 'Size', 'Lines', 'Chars', 
        'Complexity(Avg)', 'Complexity(Max)', 'IsBinary'
    ]
    
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for s in file_details_list:
                row = [
                    s.relpath, s.filename, list(s.extensions.keys())[0], s.size,
                    s.line_count, s.char_count,
                    s.complexity_avg if HAS_LIZARD else '-', 
                    s.complexity_max if HAS_LIZARD else '-',
                    s.skipped
                ]
                writer.writerow(row)
    except Exception as e:
        print(f"CSV Error: {e}")

    # 2. フォルダ集計レポート
    folder_csv_file = os.path.join(output_dir, 'folder_stats_report.csv')
    f_headers = ['Directory', 'Files', 'TotalSize', 'TotalLines']
    try:
        with open(folder_csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(f_headers)
            for folder_abs, stats in sorted(folder_stats_map.items()):
                row = [folder_abs, stats.count, stats.size, stats.line_count]
                writer.writerow(row)
    except Exception as e:
        print(f"CSV Error: {e}")

def save_html_report(total_stats, file_details_list, output_dir, target_dir_display, project_name):
    """グラフ付きHTMLレポートを出力"""
    html_file = os.path.join(output_dir, 'project_report.html')
    
    ext_data = dict(total_stats.extensions.most_common())
    top_files_by_lines = sorted(file_details_list, key=lambda x: x.line_count, reverse=True)[:20]
    file_list_json = json.dumps([f.to_dict() for f in file_details_list])
    
    complexity_enabled_js = "true" if HAS_LIZARD else "false"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{TOOL_NAME} Report - {project_name}</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f4f9; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ text-align: center; color: #2c3e50; margin-bottom: 5px; }}
            .subtitle {{ text-align: center; color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
            .path-info {{ text-align: center; color: #666; margin-bottom: 20px; word-break: break-all; background: #fff; padding: 10px; border-radius: 4px; border: 1px solid #ddd; }}
            .summary-cards {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin-bottom: 30px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); flex: 1; min-width: 200px; text-align: center; }}
            .card h3 {{ margin: 0 0 10px 0; color: #7f8c8d; font-size: 0.9em; }}
            .card .value {{ font-size: 1.8em; font-weight: bold; color: #2c3e50; }}
            .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .chart-box {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; font-size: 0.9em; }}
            th {{ background-color: #34495e; color: white; cursor: pointer; }}
            th button {{ background: transparent; border: 1px solid #fff; color: #fff; border-radius: 4px; cursor: pointer; margin-left: 5px; font-size: 0.8em; }}
            th button:hover {{ background: rgba(255,255,255,0.2); }}
            tr:hover {{ background-color: #f1f1f1; }}
            .search-box {{ width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
            .footer {{ text-align: center; margin-top: 40px; font-size: 0.8em; color: #999; }}
            .footer a {{ color: #3498db; text-decoration: none; }}
            .badge-complexity {{ padding: 2px 6px; border-radius: 4px; font-size: 0.85em; font-weight: bold; color: white; }}
            .comp-low {{ background-color: #27ae60; }}
            .comp-med {{ background-color: #f39c12; }}
            .comp-high {{ background-color: #e74c3c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 {TOOL_NAME} Report</h1>
            <div class="subtitle">Project: <strong>{project_name}</strong></div>
            <p class="path-info">{target_dir_display}</p>
            
            <div class="summary-cards">
                <div class="card"><h3>Files</h3><div class="value">{total_stats.count:,}</div></div>
                <div class="card"><h3>Total Lines</h3><div class="value">{total_stats.line_count:,}</div></div>
                <div class="card"><h3>Total Size</h3><div class="value">{format_size(total_stats.size)}</div></div>
                <div class="card"><h3>Total Chars</h3><div class="value">{total_stats.char_count:,}</div></div>
            </div>

            <div class="charts-grid">
                <div class="chart-box">
                    <canvas id="extChart"></canvas>
                </div>
                <div class="chart-box">
                    <canvas id="linesChart"></canvas>
                </div>
            </div>

            <div class="chart-box" style="margin-bottom: 30px;">
                <h3>📂 File Details</h3>
                <input type="text" id="searchInput" class="search-box" placeholder="Search by filename or path..." onkeyup="filterTable()">
                <div style="max-height: 600px; overflow-y: auto;">
                    <table id="fileTable">
                        <thead>
                            <tr>
                                <th onclick="sortTable('path')">File Path</th>
                                <th onclick="sortTable('ext')">Ext</th>
                                <th onclick="sortTable('lines')">Lines</th>
                                <th onclick="sortTable('size')">Size</th>
                                {f'<th><span onclick="sortTable(\'complexity\')">Complexity (Max)</span> <button onclick="copyComplexityJson()" title="Copy JSON">📋</button></th>' if HAS_LIZARD else ''}
                            </tr>
                        </thead>
                        <tbody id="tableBody"></tbody>
                    </table>
                </div>
            </div>
            
            <div class="footer">
                Generated by <a href="{REPO_URL}" target="_blank">{TOOL_NAME}</a> v{VERSION}
            </div>
        </div>

        <script>
            // Data Injection
            const extData = {json.dumps(ext_data)};
            const topFilesLines = {json.dumps([{'name': f.filename, 'value': f.line_count} for f in top_files_by_lines])};
            let allFiles = {file_list_json};
            const complexityEnabled = {complexity_enabled_js};

            // Extension Chart (Pie)
            new Chart(document.getElementById('extChart'), {{
                type: 'doughnut',
                data: {{
                    labels: Object.keys(extData),
                    datasets: [{{
                        data: Object.values(extData),
                        backgroundColor: [
                            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#C9CBCF'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{ title: {{ display: true, text: 'File Extensions Distribution' }} }}
                }}
            }});

            // Lines Chart (Bar)
            new Chart(document.getElementById('linesChart'), {{
                type: 'bar',
                data: {{
                    labels: topFilesLines.map(d => d.name),
                    datasets: [{{
                        label: 'Lines of Code',
                        data: topFilesLines.map(d => d.value),
                        backgroundColor: '#36A2EB'
                    }}]
                }},
                options: {{
                    responsive: true,
                    indexAxis: 'y',
                    plugins: {{ title: {{ display: true, text: 'Top 20 Files by Lines' }} }}
                }}
            }});

            // Render Table
            const tableBody = document.getElementById('tableBody');
            
            function getComplexityBadge(score) {{
                if (!score) return '-';
                let cls = 'comp-low';
                if (score > 20) cls = 'comp-high';
                else if (score > 10) cls = 'comp-med';
                return `<span class="badge-complexity ${{cls}}">${{score}}</span>`;
            }}

            function renderTable(data) {{
                tableBody.innerHTML = '';
                data.forEach(f => {{
                    let compCell = '';
                    if (complexityEnabled) {{
                        compCell = `<td>${{getComplexityBadge(f.complexity_max)}}</td>`;
                    }}
                    
                    const row = `<tr>
                        <td>${{f.path}}</td>
                        <td>${{f.ext}}</td>
                        <td>${{f.lines.toLocaleString()}}</td>
                        <td>${{f.size.toLocaleString()}} B</td>
                        ${{compCell}}
                    </tr>`;
                    tableBody.innerHTML += row;
                }});
            }}
            renderTable(allFiles);

            // Filter
            function filterTable() {{
                const input = document.getElementById('searchInput');
                const filter = input.value.toLowerCase();
                const filtered = allFiles.filter(f => f.path.toLowerCase().includes(filter));
                renderTable(filtered);
            }}

            // Simple Sort
            let sortDir = 1;
            function sortTable(key) {{
                sortDir *= -1;
                allFiles.sort((a, b) => {{
                    let valA = a[key];
                    let valB = b[key];
                    
                    // Special map for complexity
                    if (key === 'complexity') {{
                        valA = a.complexity_max || 0;
                        valB = b.complexity_max || 0;
                    }}

                    if (valA < valB) return -1 * sortDir;
                    if (valA > valB) return 1 * sortDir;
                    return 0;
                }});
                renderTable(allFiles);
            }}

            // JSON Copy Function
            function copyComplexityJson() {{
                // 複雑度1以上のファイルを抽出し、複雑度昇順(Ascending)にソート
                const dataToCopy = allFiles
                    .filter(f => f.complexity_max > 0)
                    .sort((a, b) => a.complexity_max - b.complexity_max)
                    .map(f => ({{
                        path: f.path,
                        lines: f.lines,
                        complexity: f.complexity_max
                    }}));
                
                if (dataToCopy.length === 0) {{
                    alert("複雑度データがありません。");
                    return;
                }}

                const jsonStr = JSON.stringify(dataToCopy, null, 2);
                
                const textArea = document.createElement("textarea");
                textArea.value = jsonStr;
                document.body.appendChild(textArea);
                textArea.select();
                try {{
                    document.execCommand('copy');
                    alert(`Copied ${{dataToCopy.length}} file records to clipboard!`);
                }} catch (err) {{
                    console.error('Copy failed', err);
                    alert('コピーに失敗しました。');
                }}
                document.body.removeChild(textArea);
            }}
        </script>
    </body>
    </html>
    """
    
    try:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"  -> HTMLレポート出力: {html_file}")
    except Exception as e:
        print(f"HTML書き込みエラー: {e}")

def print_report(total_stats, target_dir_display, duration):
    print("=" * 60)
    print(f" {TOOL_NAME} v{VERSION} Report")
    print(f" Target: {target_dir_display}")
    print("=" * 60)
    print(f"  Files Analyzed       : {total_stats.count:,}")
    print(f"  Total Size           : {format_size(total_stats.size)}")
    print(f"  Total Lines          : {total_stats.line_count:,}")
    if HAS_LIZARD:
        print(f"  Cyclomatic Complexity: Enabled (lizard found)")
    else:
        print(f"  Cyclomatic Complexity: Disabled")
    print(f"  Execution Time       : {duration:.2f} sec")
    print("=" * 60)
    
    # 複雑度計測が無効な場合の推奨メッセージ
    if not HAS_LIZARD:
        print("\n【推奨】複雑度計測が無効になっています。")
        print("以下のコマンドでライブラリをインストールすると、コードの複雑度を計測できます:")
        print("  pip install lizard")
        print("=" * 60)

# ==========================================
# メイン処理 (CLI)
# ==========================================

def main():
    parser = argparse.ArgumentParser(description=f"{TOOL_NAME} - Codebase Statistics & Analysis Tool")
    parser.add_argument("target_dir", nargs="?", default=".", help="Target directory to analyze")
    parser.add_argument("-o", "--output", help="Output directory for reports")
    args = parser.parse_args()

    start_time = datetime.now()
    
    # 1. パス解決
    target_dir_abs = os.path.abspath(args.target_dir)
    if not os.path.exists(target_dir_abs):
        print(f"Error: Directory not found: {target_dir_abs}")
        sys.exit(1)

    project_name = os.path.basename(target_dir_abs)
    if not project_name: 
        project_name = "Root"

    # 2. 出力先設定
    if args.output:
        output_dir = os.path.abspath(args.output)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = start_time.strftime("%y%m%d-%H%M%S")
        output_dir_name = f"{project_name}_{timestamp}"
        output_dir = os.path.join(script_dir, "outputs", output_dir_name)

    os.makedirs(output_dir, exist_ok=True)

    print(f"{TOOL_NAME} v{VERSION}")
    print(f"Target : {target_dir_abs}")
    print(f"Output : {output_dir}\n")

    # 3. 除外設定の読み込み
    ignore_matcher = IgnoreMatcher(target_dir_abs)
    
    # 4. 解析実行
    total_stats = FileStats()
    all_file_details = []
    folder_stats_map = defaultdict(FileStats)
    
    print(f"Scanning files...")

    for root, dirs, files in os.walk(target_dir_abs):
        dirs[:] = [d for d in dirs if not ignore_matcher.is_ignored(os.path.join(root, d))]
        
        for file in files:
            filepath = os.path.join(root, file)
            
            if ignore_matcher.is_ignored(filepath):
                continue
            
            file_stats = calculate_stats(filepath, target_dir_abs)
            
            total_stats.add(file_stats)
            all_file_details.append(file_stats)
            folder_stats_map[root].add(file_stats)
            
            if total_stats.count % 100 == 0:
                print(f"\r  Files analyzed: {total_stats.count}", end="")

    duration = (datetime.now() - start_time).total_seconds()
    print(f"\nAnalysis Complete!")
    
    print_report(total_stats, target_dir_abs, duration)
    
    # 5. レポート保存
    save_csv_reports(all_file_details, folder_stats_map, output_dir)
    save_html_report(total_stats, all_file_details, output_dir, target_dir_abs, project_name)
    
    print(f"\nReports saved to:\n{output_dir}")

if __name__ == "__main__":
    main()