#!/usr/bin/env bash
# evidence-debugger installer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILL="${SCRIPT_DIR}/evidence-debugger"

# Default target directory can be overridden via TARGET_DIR or argument
TARGET_DIR="${1:-${TARGET_DIR:-"${HOME}/.gemini/antigravity/skills/evidence-debugger"}}"

echo "=== evidence-debugger installer ==="
echo "Source: ${SOURCE_SKILL}"
echo "Target: ${TARGET_DIR}"

if [ ! -d "${SOURCE_SKILL}" ]; then
  echo "Error: Skill source directory not found at ${SOURCE_SKILL}" >&2
  exit 1
fi

# Ensure Python 3.8+ is available
PYTHON_BIN=""
for cmd in python3 python py; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    if "${cmd}" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
      PYTHON_BIN="${cmd}"
      break
    fi
  fi
done

if [ -z "${PYTHON_BIN}" ]; then
  echo "Error: Python 3.8+ is required to run evidence-debugger." >&2
  exit 1
fi

echo "Using Python: $(${PYTHON_BIN} --version) (${PYTHON_BIN})"

# Create target parent directory
mkdir -p "$(dirname "${TARGET_DIR}")"

# Clean target directory if present
if [ -d "${TARGET_DIR}" ]; then
  rm -rf "${TARGET_DIR}"
fi

# Copy skill payload
cp -R "${SOURCE_SKILL}" "${TARGET_DIR}"
chmod +x "${TARGET_DIR}/scripts/ed.py"

# Write installation marker
cat <<EOF > "${TARGET_DIR}/.installed-by.json"
{
  "installed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": "${SOURCE_SKILL}",
  "python": "${PYTHON_BIN}"
}
EOF

# Run doctor check
echo "Running integrity verification..."
"${PYTHON_BIN}" "${TARGET_DIR}/scripts/ed.py" doctor

echo ""
echo "Successfully installed evidence-debugger to: ${TARGET_DIR}"
echo "Usage: python3 ${TARGET_DIR}/scripts/ed.py --root <repo> init"
