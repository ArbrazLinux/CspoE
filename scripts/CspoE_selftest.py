#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Run the complete offline CspoE acceptance suite."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import settings


def run(name: str, arguments: list[str]) -> dict[str, object]:
    process = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "ok": process.returncode == 0,
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="run the core offline suite")
    parser.add_argument("--legacy-source", default=None)
    parser.add_argument("--legacy-end", type=int, default=None)
    args = parser.parse_args()
    checks = [
        run("installer_config", ["scripts/CspoE_install_selftest.py"]),
        run("gui_launcher", ["scripts/CspoE_gui_launcher_selftest.py"]),
        run("blockfrost", ["scripts/CspoE_blockfrost_selftest.py"]),
        run("blockfrost_budget", ["scripts/CspoE_blockfrost_budget_selftest.py"]),
        run("initialization", ["scripts/CspoE_initialization_selftest.py"]),
        run("reward_window", ["scripts/CspoE_reward_selftest.py"]),
        run("transition_window", ["scripts/CspoE_transition_selftest.py"]),
        run("components", ["scripts/CspoE_components_selftest.py"]),
        run("transactions", ["scripts/CspoE_transaction_selftest.py"]),
    ]
    if args.legacy_source:
        if args.legacy_end is None:
            parser.error("--legacy-end is required with --legacy-source")
        checks.append(
            run(
                "legacy_replay",
                [
                    "scripts/CspoE_legacy_replay.py",
                    "--legacy-source",
                    args.legacy_source,
                    "--awards-file",
                    "data/awards.json",
                    "--start-epoch",
                    str(settings.pool_first_epoch),
                    "--end-epoch",
                    str(args.legacy_end),
                    "--mode",
                    "reference-facts",
                ],
            )
        )
    result = {"ok": all(bool(item["ok"]) for item in checks), "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
