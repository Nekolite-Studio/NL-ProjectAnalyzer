#!/bin/bash

# =============================================================================
# NL-ProjectAnalyzer Startup Script
# 
# Overview:
#   Wrapper script to execute project_analyzer.py.
#   Place this script in the root directory of your project.
#
# Usage:
#   ./analyzer-run-safe.sh [Options]
# =============================================================================

# Uncomment the following line to stop the script if an error occurs
# set -e

# Change to the directory where this script is located
cd "$(dirname "$0")"

# =============================================================================
# [CONFIGURATION]
# =============================================================================

# Specify the directory where 'project_analyzer.py' is located.
# Default: "." (Same directory as this script)
# Examples: "/usr/local/bin/nl-analyzer" or "../shared-tools"
ANALYZER_DIR="."

# =============================================================================

# -----------------------------------------------------------------------------
# 1. Environment Check
# -----------------------------------------------------------------------------

# Construct path to the analyzer script
ANALYZER_SCRIPT="${ANALYZER_DIR}/project_analyzer.py"

# Verify if the script exists
if [ ! -f "$ANALYZER_SCRIPT" ]; then
    echo "[ERROR] Analyzer script not found."
    echo "        Path: $ANALYZER_SCRIPT"
    echo "        Please check the 'ANALYZER_DIR' variable in this script."
    exit 1
fi

# Detect Python command
# Priority:
# 1. .venv in analyzer directory
# 2. System python3
# 3. System python

PYTHON_CMD=""
VENV_DIR="${ANALYZER_DIR}/.venv"

# Check for virtual environment
if [ -f "${VENV_DIR}/bin/python" ]; then
    PYTHON_CMD="${VENV_DIR}/bin/python"
elif [ -f "${VENV_DIR}/Scripts/python" ]; then
    # Windows (Git Bash etc.)
    PYTHON_CMD="${VENV_DIR}/Scripts/python"
elif [ -f "${VENV_DIR}/Scripts/python.exe" ]; then
    # Windows (Direct Exe)
    PYTHON_CMD="${VENV_DIR}/Scripts/python.exe"
fi

if [ -n "$PYTHON_CMD" ]; then
    echo "[INFO] Using virtual environment: ${VENV_DIR}"
else
    # Fallback to system python
    if command -v python3 &>/dev/null; then
        PYTHON_CMD=python3
    elif command -v python &>/dev/null; then
        PYTHON_CMD=python
    else
        echo "[ERROR] Python not found. Please install Python 3.6 or higher."
        exit 1
    fi
fi

# Check for lizard library (Informational only)
if ! $PYTHON_CMD -c "import lizard" &>/dev/null; then
    echo "[WARNING] 'lizard' library not found. Complexity analysis will be skipped."
    echo "          (Recommended install: pip install lizard)"
    echo ""
fi

# -----------------------------------------------------------------------------
# 2. Execution
# -----------------------------------------------------------------------------

echo "[INFO] Starting NL-ProjectAnalyzer..."
echo "       Target : $(pwd)"
echo "       Script : $ANALYZER_SCRIPT"

# Execute project_analyzer.py
# "$@" passes arguments provided to this shell script directly to the Python script
$PYTHON_CMD "$ANALYZER_SCRIPT" "$@"

EXIT_CODE=$?

# -----------------------------------------------------------------------------
# 3. Completion
# -----------------------------------------------------------------------------

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "[SUCCESS] Analysis completed successfully."
else
    echo ""
    echo "[FAILURE] Analysis failed with errors (Exit Code: $EXIT_CODE)."
fi

exit $EXIT_CODE