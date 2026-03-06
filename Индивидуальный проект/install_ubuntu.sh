#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_EDITOR="${SCRIPT_DIR}/editor.py"

INSTALL_DIR="${HOME}/.local/share/pop-editor"
BIN_DIR="${HOME}/.local/bin"
LAUNCHER_PATH="${BIN_DIR}/pop"

if [[ ! -f "${SOURCE_EDITOR}" ]]; then
  echo "error: editor.py not found next to installer: ${SOURCE_EDITOR}" >&2
  exit 1
fi

mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"
cp "${SOURCE_EDITOR}" "${INSTALL_DIR}/editor.py"

cat > "${LAUNCHER_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

EDITOR_SCRIPT="${HOME}/.local/share/pop-editor/editor.py"

if [[ ! -f "${EDITOR_SCRIPT}" ]]; then
  echo "error: ${EDITOR_SCRIPT} not found. Re-run install_ubuntu.sh." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is not installed or not in PATH." >&2
  exit 1
fi

exec python3 "${EDITOR_SCRIPT}" "$@"
EOF

chmod +x "${LAUNCHER_PATH}"

ensure_path_line='export PATH="$HOME/.local/bin:$PATH"'
for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
  if [[ -f "${rc}" ]] && ! grep -Fq "${ensure_path_line}" "${rc}"; then
    {
      echo ""
      echo "# Added by pop installer"
      echo "${ensure_path_line}"
    } >> "${rc}"
  fi
done

if command -v python3 >/dev/null 2>&1; then
  if ! python3 -c "import blessed" >/dev/null 2>&1; then
    echo "Installing Python dependency: blessed"
    if ! python3 -m pip install --user blessed; then
      echo "warning: failed to install blessed automatically." >&2
      echo "Run manually: python3 -m pip install --user blessed" >&2
    fi
  fi
fi

echo "Installation complete."
echo "If 'pop' is not found yet, restart terminal or run:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "Usage:"
echo "  pop /home/user/1.txt"
