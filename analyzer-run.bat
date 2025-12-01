@echo off
setlocal EnableDelayedExpansion

REM =============================================================================
REM NL-ProjectAnalyzer 起動スクリプト (Windows Batch版)
REM =============================================================================

REM 文字コードをUTF-8に変更（日本語・絵文字表示用）
chcp 65001 >nul

REM スクリプトが存在するディレクトリに移動
cd /d "%~dp0"

REM =============================================================================
REM ⚙️ 設定 (Configuration)
REM =============================================================================

REM project_analyzer.py があるディレクトリ（通常はこのバッチと同じ場所 "."）
set "ANALYZER_DIR=."

REM =============================================================================

REM -----------------------------------------------------------------------------
REM 1. 環境チェック
REM -----------------------------------------------------------------------------

set "ANALYZER_SCRIPT=%ANALYZER_DIR%\project_analyzer.py"

REM スクリプト本体の存在確認
if not exist "%ANALYZER_SCRIPT%" (
    echo.
    echo ❌ エラー: アナライザ本体が見つかりません。
    echo    設定されたパス: %ANALYZER_SCRIPT%
    echo    'ANALYZER_DIR' 変数が正しく設定されているか確認してください。
    pause
    exit /b 1
)

REM Pythonコマンドの検出
set "PYTHON_CMD="
set "VENV_DIR=%ANALYZER_DIR%\.venv"

REM 1. 仮想環境 (Windows)
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
) else (
    REM 2. 仮想環境 (Git Bash等で作られた場合)
    if exist "%VENV_DIR%\bin\python.exe" (
        set "PYTHON_CMD=%VENV_DIR%\bin\python.exe"
    )
)

if defined PYTHON_CMD (
    echo 🐍 仮想環境を使用します: %VENV_DIR%
) else (
    REM 3. システムPython (py launcher または python)
    python --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo ❌ エラー: Pythonが見つかりません。PythonをインストールしPATHを通してください。
        pause
        exit /b 1
    )
)

REM lizardのチェック
"%PYTHON_CMD%" -c "import lizard" >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ⚠️  注意: 'lizard' ライブラリが見つかりません。複雑度計測はスキップされます。
    echo    ^(インストール推奨: pip install lizard^)
    echo.
)

REM -----------------------------------------------------------------------------
REM 2. 解析実行
REM -----------------------------------------------------------------------------

echo 🚀 NL-ProjectAnalyzer を起動します...
echo    Target : %CD%
echo    Script : %ANALYZER_SCRIPT%

REM Pythonスクリプト実行 (%* は引数をすべて渡す)
"%PYTHON_CMD%" "%ANALYZER_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

REM -----------------------------------------------------------------------------
REM 3. 終了処理
REM -----------------------------------------------------------------------------

echo.
if %EXIT_CODE% equ 0 (
    echo ✅ 解析が正常に完了しました。
) else (
    echo ❌ 解析中にエラーが発生しました (Exit Code: %EXIT_CODE%)。
)

REM 実行完了後にウィンドウがすぐ閉じないようにする場合
REM pause

exit /b %EXIT_CODE%