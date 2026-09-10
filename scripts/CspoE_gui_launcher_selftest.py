#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline test of display checks and PySide6 plugin-path isolation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cspoe-gui-launcher-") as temporary:
        root = Path(temporary)
        scripts = root / "scripts"
        binary = root / ".venv" / "bin" / "python"
        pyside = root / "fake-pyside"
        plugins = pyside / "Qt" / "plugins"
        (plugins / "platforms").mkdir(parents=True)
        (pyside / "Qt" / "lib").mkdir(parents=True)
        binary.parent.mkdir(parents=True)
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "run_desktop.sh", scripts / "run_desktop.sh")
        (plugins / "platforms" / "libqxcb.so").touch()
        binary.write_text(
            "#!/usr/bin/env bash\n"
            "code=\"${2:-}\"\n"
            "case \"$code\" in\n"
            f"  *'Path(PySide6.__file__)'*) printf '%s\\n' '{pyside}' ;;\n"
            f"  *'QLibraryInfo'*) printf '%s\\n' '{plugins}' ;;\n"
            "  *'import json, os, PySide6'*) /usr/bin/python3 -c 'import json, os; print(json.dumps({\"ok\": True, \"qt_platform\": os.environ.get(\"QT_QPA_PLATFORM\"), \"qt_plugin_path\": os.environ.get(\"QT_PLUGIN_PATH\"), \"qpa_platform_plugin_path\": os.environ.get(\"QT_QPA_PLATFORM_PLUGIN_PATH\"), \"ld_library_path\": os.environ.get(\"LD_LIBRARY_PATH\")}, indent=2))' ;;\n"
            "  *) exit 91 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)

        clean_env = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "QT_QPA_PLATFORM"):
            clean_env.pop(name, None)
        headless = subprocess.run(
            ["bash", str(scripts / "run_desktop.sh"), "--diagnose"],
            env=clean_env, text=True, capture_output=True, check=False,
        )
        assert headless.returncode == 3
        assert "no graphical display" in headless.stderr

        graphical_env = dict(clean_env)
        graphical_env.update({
            "DISPLAY": ":99",
            "QT_PLUGIN_PATH": "/usr/lib/qt6/plugins",
            "QT_QPA_PLATFORM_PLUGIN_PATH": "/usr/lib/qt6/plugins/platforms",
        })
        diagnosed = subprocess.run(
            ["bash", str(scripts / "run_desktop.sh"), "--diagnose"],
            env=graphical_env, text=True, capture_output=True, check=False,
        )
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        assert report["qt_platform"] == "xcb"
        assert report["qt_plugin_path"] == str(plugins)
        assert report["qpa_platform_plugin_path"] == str(plugins / "platforms")
        assert report["ld_library_path"].split(":", 1)[0] == str(pyside / "Qt" / "lib")

    print(json.dumps({
        "ok": True,
        "test": "isolated-pyside6-gui-launcher-v1",
        "checks": [
            "headless session rejected before QApplication",
            "X11 selected only when DISPLAY exists",
            "system Qt plugin environment replaced by virtualenv paths",
            "virtualenv Qt libraries are prepended",
        ],
        "gui_opened": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
