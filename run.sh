#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required before infra-auditor can run." >&2
    exit 1
  fi

  python3 - <<'PY'
import sys

if sys.version_info < (3, 12):
    raise SystemExit("python3.12+ is required before infra-auditor can run.")
PY
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  echo "uv not found; installing uv into the current user environment." >&2
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "Install uv manually, or install curl/wget so this script can fetch uv." >&2
    exit 1
  fi

  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv installation completed but uv is still not on PATH." >&2
    exit 1
  fi
}

load_dotenv() {
  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
  fi
}

warn_optional_tools() {
  if ! command -v aws >/dev/null 2>&1; then
    echo "warning: aws CLI not found; boto3 can still use existing environment credentials." >&2
  fi
}

require_python
ensure_uv
warn_optional_tools
uv sync
load_dotenv

HOST="${INFRA_AUDITOR_WEB_HOST:-127.0.0.1}"
PORT="${INFRA_AUDITOR_WEB_PORT:-8008}"

echo "Starting infra-auditor UI on http://${HOST}:${PORT}"
exec uv run infra-auditor serve --host "$HOST" --port "$PORT"
