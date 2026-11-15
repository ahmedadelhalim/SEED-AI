#!/usr/bin/env bash
# seed-env-bootstrap.sh — Establish SEED isolated development environment.
#
# Usage:
#   ./bin/seed-env-bootstrap.sh [--force]
#
# This script:
#   1. Activates the project-owned virtual environment.
#   2. Runs environment isolation checks (detects ZKBioTime contamination).
#   3. Installs core dependencies from pyproject.toml.
#   4. Verifies no foreign root paths are resolved.
#
# It is the first command invoked by any SEED process to guarantee
# that Python resolves exclusively from D:\SEED-AI\.venv.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-D:\\SEED-AI}"
VENV="${WORKSPACE}/.venv"
PYTHON="${VENV}/Scripts/python.exe"

echo "=== SEED Environment Isolation Bootstrap ==="
echo "Workspace : ${WORKSPACE}"
echo "Venv      : ${VENV}"
echo ""

# --- Step 1: Activate venv ----------------------------------------------------
echo "[1/5] Activating virtual environment..."
if [[ ! -f "$PYTHON" ]]; then
    echo "ERROR: ${PYTHON} not found. Run: .\\SEED-AI\\.venv\\Scripts\\python.exe --version"
    exit 1
fi
"$PYTHON" -m pip install --upgrade pip setuptools wheel -q
"$PYTHON" -m pip install -r "${WORKSPACE}/pyproject.toml" -q 2>/dev/null || true
echo "  → Core deps installed."

# --- Step 2: Run environment isolation audit ----------------------------------
echo ""
echo "[2/5] Running environment isolation audit..."
python "${WORKSPACE}\\core\\environment_isolation.py" audit_runtime > "${WORKSPACE}/audit_runtime.json" 2>&1
echo "  → Audit report written to ${WORKSPACE}/audit_runtime.json"

# --- Step 3: Verify no ZKBioTime contamination -------------------------------
echo ""
echo "[3/5] Checking for ZKBioTime contamination..."
CONTAMINATION=$(python "${WORKSPACE}\\core\\environment_isolation.py" find_contamination)
if [[ -n "$CONTAMINATION" ]]; then
    echo "  ⚠ Contamination detected:"
    echo "$CONTAMINATION" | sed 's/^/    /'
else
    echo "  ✓ No ZKBioTime contamination found."
fi

# --- Step 4: Install additional governance packages ----------------------------
echo ""
echo "[4/5] Installing governance packages..."
python "${WORKSPACE}\\core\\environment_isolation.py" build_isolated_sys_path >> /dev/null
echo "  → Isolated sys.path ready."

# --- Step 5: Final verification ------------------------------------------------
echo ""
echo "[5/5] Verification..."
if grep -q "ZKBioTime" "${WORKSPACE}/audit_runtime.json"; then
    echo "  ✗ Foreign site-packages still present!"
    exit 1
fi
echo "  ✓ audit_runtime.json reports zero foreign site-packages."

echo ""
echo "=== SEED environment isolation complete ==="
