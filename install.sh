#!/bin/sh
# Install or upgrade the `ezy` command (EzyPlatform CLI) on macOS and Linux.
#   curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh
# Uses uv (https://docs.astral.sh/uv), installing it first when missing; uv also
# downloads Python when the machine has no Python 3.9+. Installs from PyPI, or
# from the latest GitHub release while the package is not on PyPI (set EZY_SOURCE
# to force a source, e.g. git+https://github.com/itsddvn/ezyplatform-cli for main).
# EZY_NO_MODIFY_PATH=1 leaves shell profiles untouched.
set -e

PKG=ezyplatform-cli
REPO=https://github.com/itsddvn/ezyplatform-cli

UV=$(command -v uv || true)
if [ -z "$UV" ]; then
  echo "Installing uv (Python tool manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  for dir in "$UV_INSTALL_DIR" "$XDG_BIN_HOME" "$HOME/.local/bin" "$HOME/.cargo/bin"; do
    if [ -n "$dir" ] && [ -x "$dir/uv" ]; then UV="$dir/uv"; break; fi
  done
  [ -n "$UV" ] || { echo "uv was installed but not found; open a new terminal and run this again." >&2; exit 1; }
fi

if [ -z "$EZY_SOURCE" ]; then
  if curl -fsS -o /dev/null "https://pypi.org/pypi/$PKG/json" 2>/dev/null; then
    EZY_SOURCE=$PKG
  else
    # releases/latest redirects to .../tag/vX.Y.Z (no API call, so no rate limit)
    TAG=$(curl -fsSIL -o /dev/null -w '%{url_effective}' "$REPO/releases/latest" | sed 's|.*/tag/||')
    case "$TAG" in v[0-9]*) ;; *) echo "no ezy release found on GitHub" >&2; exit 1 ;; esac
    EZY_SOURCE="$REPO/releases/download/$TAG/ezyplatform_cli-${TAG#v}-py3-none-any.whl"
  fi
fi

echo "Installing ezy from $EZY_SOURCE..."
"$UV" tool install --force --python ">=3.9" "$EZY_SOURCE"
[ -n "$EZY_NO_MODIFY_PATH" ] || "$UV" tool update-shell >/dev/null 2>&1 || true

BIN=$("$UV" tool dir --bin)
echo
"$BIN/ezy" --version
if command -v ezy >/dev/null 2>&1; then
  echo "Done. Next: ezy init (sets up your coding agents), then ezy new my-site --admin-url https://admin.example.com"
else
  echo "Done. Open a new terminal so 'ezy' is on your PATH, then run: ezy init"
fi
