#!/usr/bin/env bash
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'CspoE GUI: virtualenv absent: %s\n' "$PYTHON_BIN" >&2
  printf 'Run ./install.sh --install first, or create .venv with requirements-gui.txt.\n' >&2
  exit 2
fi

PYSIDE_DIR="$("$PYTHON_BIN" -c 'from pathlib import Path; import PySide6; print(Path(PySide6.__file__).resolve().parent)')" || {
  printf 'CspoE GUI: PySide6 is not importable from %s\n' "$PYTHON_BIN" >&2
  exit 2
}
QT_PLUGIN_DIR="$("$PYTHON_BIN" -c 'from PySide6.QtCore import QLibraryInfo; enum = getattr(QLibraryInfo, "LibraryPath", QLibraryInfo); print(QLibraryInfo.path(enum.PluginsPath))')" || {
  printf 'CspoE GUI: unable to resolve the PySide6 Qt plugin directory.\n' >&2
  exit 2
}
QT_LIBRARY_DIR="$PYSIDE_DIR/Qt/lib"
[[ -f "$QT_PLUGIN_DIR/platforms/libqxcb.so" ]] || {
  printf 'CspoE GUI: PySide6 xcb plugin absent: %s\n' "$QT_PLUGIN_DIR/platforms/libqxcb.so" >&2
  exit 2
}

# Never mix Ubuntu's Qt plugins with the Qt version bundled in PySide6. A
# system QT_PLUGIN_PATH is a common source of native version mismatches and
# segmentation faults.
export QT_PLUGIN_PATH="$QT_PLUGIN_DIR"
export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_DIR/platforms"
if [[ -d "$QT_LIBRARY_DIR" ]]; then
  export LD_LIBRARY_PATH="$QT_LIBRARY_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

PLATFORM="${QT_QPA_PLATFORM:-}"
if [[ -z "$PLATFORM" ]]; then
  if [[ -n "${DISPLAY:-}" ]]; then
    PLATFORM="xcb"
  elif [[ -n "${WAYLAND_DISPLAY:-}" && -n "${XDG_RUNTIME_DIR:-}" ]]; then
    PLATFORM="wayland"
  else
    printf 'CspoE GUI: no graphical display is available.\n' >&2
    printf 'Launch this command as the logged-in desktop user from a graphical terminal; do not use sudo or a systemd service.\n' >&2
    exit 3
  fi
  export QT_QPA_PLATFORM="$PLATFORM"
fi

case "$PLATFORM" in
  xcb)
    [[ -n "${DISPLAY:-}" ]] || {
      printf 'CspoE GUI: QT_QPA_PLATFORM=xcb but DISPLAY is empty.\n' >&2
      printf 'Open a terminal inside the graphical session and run the launcher without sudo.\n' >&2
      exit 3
    }
    ;;
  wayland*)
    [[ -n "${WAYLAND_DISPLAY:-}" && -n "${XDG_RUNTIME_DIR:-}" ]] || {
      printf 'CspoE GUI: Wayland selected but WAYLAND_DISPLAY/XDG_RUNTIME_DIR is unavailable.\n' >&2
      exit 3
    }
    ;;
  offscreen|minimal)
    # Explicitly accepted for automated smoke tests, not interactive use.
    ;;
esac

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"

if [[ "${1:-}" == "--diagnose" ]]; then
  exec "$PYTHON_BIN" -c 'import json, os, PySide6; print(json.dumps({"ok": True, "pyside6": PySide6.__version__, "qt_platform": os.environ.get("QT_QPA_PLATFORM"), "display": os.environ.get("DISPLAY"), "wayland_display": os.environ.get("WAYLAND_DISPLAY"), "qt_plugin_path": os.environ.get("QT_PLUGIN_PATH"), "qpa_platform_plugin_path": os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH")}, indent=2))'
fi
exec "$PYTHON_BIN" -m desktop.app
