#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Audit that the distributable tree is generic and free of runtime data."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = "CspoE is developped and maintained by BreizhStakePool.io"
FORBIDDEN_TEXT = (
    "/home/" + "bzh",
    "/var/www/" + "CspoE",
    "breizh-" + "CspoE",
    "@" + "bzhtest",
    "@" + "bzhpool",
)


def config_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def main() -> int:
    errors: list[str] = []
    files = [path for path in ROOT.rglob("*") if path.is_file()]
    for path in files:
        relative = path.relative_to(ROOT)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            errors.append(f"compiled cache included: {relative}")
        if path.name.endswith((".bak", ".bak2")) or path.name == ".venv":
            errors.append(f"backup/runtime file included: {relative}")
        if path.suffix == ".json":
            if relative != Path("data/awards.json"):
                errors.append(f"runtime/test JSON included: {relative}")
            continue
        data = path.read_bytes()
        if b"\0" in data:
            errors.append(f"unexpected binary file: {relative}")
            continue
        text = data.decode("utf-8")
        if HEADER not in text:
            errors.append(f"release header missing: {relative}")
        for needle in FORBIDDEN_TEXT:
            if needle in text:
                errors.append(f"personal reference {needle!r}: {relative}")

    config = config_values(ROOT / "CspoE.conf")
    for key in ("BLOCKFROST_PROJECT_ID", "BECH32_POOL_ID", "MYSQL_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID", "CSPOE_DREP_ID"):
        if config.get(key):
            errors.append(f"public config value must be empty: {key}")
    if config.get("POOL_TICKER") != "YOUR_POOL":
        errors.append("POOL_TICKER public placeholder missing")
    if config.get("POOL_FIRST_EPOCH") != "0":
        errors.append("POOL_FIRST_EPOCH public placeholder must be 0")

    required = (
        "install.sh", "README.md", "INITIALIZE.md", "release.log",
        "core/CspoE_reward_reconciler.py", "desktop/app.py",
        "scripts/CspoE_install_selftest.py",
        "scripts/CspoE_gui_launcher_selftest.py",
        "scripts/CspoE_blockfrost_budget_selftest.py",
        "sql/schema.sql", "CspoE_legacy_schema.sql",
        "php/pool.php", "notifications/interactive_bot.py",
        "systemd/cspoe-transition.service.in", "systemd/cspoe-transition.timer",
    )
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f"required release component missing: {name}")

    awards = json.loads((ROOT / "data" / "awards.json").read_text(encoding="utf-8"))
    if awards != []:
        errors.append("public data/awards.json must be an empty list")
    result = {
        "ok": not errors,
        "files": len(files),
        "personal_configuration_present": False if not errors else None,
        "runtime_epoch_data_present": any("epoch_" in path.name and path.suffix == ".json" for path in files),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
