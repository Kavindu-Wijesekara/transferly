#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${HOME}/.transferly"
APP_CODE_DIR="${APP_DIR}/app"
VENV_DIR="${APP_DIR}/venv"
CONFIG_DIR="${HOME}/.config/transferly"
LOG_DIR="${CONFIG_DIR}/logs"
BIN_DIR="${HOME}/.local/bin"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

install_system_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo_cmd=""
    if [ "${EUID}" -ne 0 ]; then sudo_cmd="sudo"; fi
    ${sudo_cmd} apt-get update
    ${sudo_cmd} apt-get install -y python3 python3-venv python3-pip aria2 rclone rsync git
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip aria2 rclone rsync git
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed python python-pip aria2 rclone rsync git
  else
    echo "Unsupported OS. Install python3, aria2, rclone, rsync, and git manually." >&2
    exit 1
  fi
}

install_system_deps
mkdir -p "${APP_CODE_DIR}" "${CONFIG_DIR}" "${LOG_DIR}" "${BIN_DIR}"
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude 'venv' "${REPO_DIR}/" "${APP_CODE_DIR}/"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_CODE_DIR}/requirements.txt"
cat > "${BIN_DIR}/tsf" <<'EOF'
#!/usr/bin/env bash
PYTHONPATH="${HOME}/.transferly/app" exec "${HOME}/.transferly/venv/bin/python" -m transferly.cli "$@"
EOF
chmod +x "${BIN_DIR}/tsf"
"${BIN_DIR}/tsf" --version
cat <<EOF
Transferly installed successfully.
Command: ${BIN_DIR}/tsf
App: ${APP_CODE_DIR}
Config: ${CONFIG_DIR}
Logs: ${LOG_DIR}
EOF
