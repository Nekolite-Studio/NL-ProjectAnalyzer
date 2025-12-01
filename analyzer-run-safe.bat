@echo off
setlocal EnableDelayedExpansion

REM =============================================================================
REM NL-ProjectAnalyzer Startup Script (Safe Mode)
REM 
REM Overview:
REM   Wrapper script to execute project_analyzer.py.
REM   Place this script in the root directory of your project.
REM
REM Usage:
REM   analyzer-run-safe.bat [Options]
REM =============================================================================

REM Change to the directory where this script is located
cd /d "%~dp0"

REM =============================================================================
REM [CONFIGURATION]
REM =============================================================================

REM Specify the directory where 'project_analyzer.py' is located.
REM Default: "." (Same directory as this script)
set "ANALYZER_DIR=."

REM =============================================================================

REM -----------------------------------------------------------------------------
REM 1. Environment Check
REM -----------------------------------------------------------------------------

set "ANALYZER_SCRIPT=%ANALYZER_DIR%\project_analyzer.py"

REM Verify if the script exists
if not exist "%ANALYZER_SCRIPT%" (
    echo [ERROR] Analyzer script not found.
    echo         Path: %ANALYZER_SCRIPT%
    echo         Please check the 'ANALYZER_DIR' variable in this script.
    exit /b 1
)

REM Detect Python command
REM Priority:
REM 1. .venv in analyzer directory
REM 2. System python

set "PYTHON_CMD="
set "VENV_DIR=%ANALYZER_DIR%\.venv"

REM Check for virtual environment (Windows Standard)
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
) else (
    REM Check for virtual environment (Posix-like on Windows)
    if exist "%VENV_DIR%\bin\python.exe" (
        set "PYTHON_CMD=%VENV_DIR%\bin\python.exe"
    )
)

if defined PYTHON_CMD (
    echo [INFO] Using virtual environment: %VENV_DIR%
) else (
    REM Fallback to system python
    python --version >NUL 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo [ERROR] Python not found. Please install Python 3.6 or higher.
        exit /b 1
    )
)

REM Check for lizard library (Informational only)
"%PYTHON_CMD%" -c "import lizard" >NUL 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [WARNING] 'lizard' library not found. Complexity analysis will be skipped.
    echo           (Recommended install: pip install lizard)
    echo.
)

REM -----------------------------------------------------------------------------
REM 2. Execution
REM -----------------------------------------------------------------------------

echo [INFO] Starting NL-ProjectAnalyzer...
echo        Target : %CD%
echo        Script : %ANALYZER_SCRIPT%

REM Execute project_analyzer.py
REM "%*" passes all arguments provided to this batch script directly to Python
"%PYTHON_CMD%" "%ANALYZER_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

REM -----------------------------------------------------------------------------
REM 3. Completion
REM -----------------------------------------------------------------------------

echo.
if %EXIT_CODE% EQU 0 (
    echo [SUCCESS] Analysis completed successfully.
) else (
    echo [FAILURE] Analysis failed with errors (Exit Code: %EXIT_CODE%).
)

exit /b %EXIT_CODE%