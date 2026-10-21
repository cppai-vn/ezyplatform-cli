#!/bin/sh
# Install or upgrade the `ezy` command (EzyPlatform CLI).
#   curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh
# Uses uv, then pipx, then pip --user. Installs from PyPI, or from GitHub when
# the package is not on PyPI (set EZY_SOURCE to force a source).
set -e

PKG=ezyplatform-cli
GIT="git+https://github.com/itsddvn/ezyplatform-cli"

if [ -z "$EZY_SOURCE" ]; then
  if curl -fsS -o /dev/null "https://pypi.org/pypi/$PKG/json" 2>/dev/null; then
    EZY_SOURCE=$PKG
  else
    EZY_SOURCE=$GIT
  fi
fi

if command -v uv >/dev/null 2>&1; then
  uv tool install --force --python ">=3.9" "$EZY_SOURCE"
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "$EZY_SOURCE"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user --upgrade "$EZY_SOURCE"
else
  echo "ezy needs Python 3.9+. Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

echo
if command -v ezy >/dev/null 2>&1; then
  ezy --version
  echo "Done. Start with: ezy init my-site --admin-url https://admin.example.com"
else
  echo "Installed, but 'ezy' is not on PATH yet. Open a new terminal (or run: uv tool update-shell)."
fi
