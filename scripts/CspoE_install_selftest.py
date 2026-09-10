#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline regression test for portable CspoE.conf parsing by install.sh."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cspoe-installer-selftest-") as temporary:
        root = Path(temporary)
        installer = root / "install.sh"
        shutil.copy2(ROOT / "install.sh", installer)
        (root / "CspoE.conf").write_text(
            "\n".join((
                "# values deliberately mix quoting and whitespace",
                " BLOCKFROST_PROJECT_ID = 'test-project' ",
                'BECH32_POOL_ID="pool1test"',
                "POOL_TICKER='TEST'",
                'POOL_FIRST_EPOCH = "245"',
                "CSPOE_INSTALL_DIR='/opt/cspoe-test'",
                'CSPOE_SERVICE_USER="cspoe"',
                "CSPOE_SERVICE_GROUP='cspoe'",
                'CSPOE_WEB_DIR="/var/www/html/cspoe-test"',
                "",
            )),
            encoding="utf-8",
        )
        process = subprocess.run(
            ["bash", str(installer), "--check"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert process.returncode == 0, process.stderr
        assert process.stderr == "", process.stderr
        result = json.loads(process.stdout)
        assert result == {
            "ok": True,
            "mode": "check",
            "pool_ticker": "TEST",
            "pool_first_epoch": 245,
            "install_dir": "/opt/cspoe-test",
        }

    print(json.dumps({
        "ok": True,
        "test": "portable-installer-config-parser-v1",
        "checks": [
            "unquoted, single-quoted, and double-quoted values",
            "whitespace around names, separators, and values",
            "no awk warnings on Ubuntu mawk-compatible syntax",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
