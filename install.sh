#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${HOME}/.transferly"
CONFIG_DIR="${HOME}/.config/transferly"
BIN_DIR="${HOME}/.local/bin"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${APP_DIR}/venv"

mkdir -p "${APP_DIR}" "${CONFIG_DIR}" "${BIN_DIR}"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'venv' \
  "${REPO_DIR}/" "${APP_DIR}/app/"

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/app/requirements.txt"

cat > "${BIN_DIR}/tsf" <<'EOF'
#!/usr/bin/env bash
PYTHONPATH="${HOME}/.transferly/app" exec "${HOME}/.transferly/venv/bin/python" -m transferly.cli "$@"
EOF
chmod +x "${BIN_DIR}/tsf"

echo "Transferly installed. Run: tsf"
echo "App: ${APP_DIR}"
echo "Config: ${CONFIG_DIR}"
