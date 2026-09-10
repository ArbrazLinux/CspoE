#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Validate or write the replaceable MySQL projection used by PHP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_legacy_contract import validate_exact_legacy_shape
from core.config import settings
from core.data_store import PoolDataStore
from core.mysql import MySQLRepository, SCHEMA_STATEMENTS, projection_counts
from core.mysql_legacy import (
    LEGACY_SCHEMA_STATEMENTS,
    LegacyMySQLRepository,
    build_legacy_projection,
)
from core.version import ENGINE_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Projette les snapshots canoniques dans MySQL. Dry-run par défaut."
    )
    parser.add_argument(
        "command",
        choices=("status", "schema", "sync", "legacy-schema", "legacy-sync"),
    )
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--from-epoch", type=int, default=None)
    parser.add_argument("--to-epoch", type=int, default=None)
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.command == "legacy-sync" and (
        args.from_epoch is not None or args.to_epoch is not None
    ):
        parser.error(
            "legacy-sync reconstruit obligatoirement toute la chronologie; "
            "--from-epoch/--to-epoch sont interdits"
        )

    configured = bool(settings.mysql_database and settings.mysql_user)
    if args.command == "status":
        result = {
            "ok": True,
            "version": ENGINE_VERSION,
            "configured": configured,
            "database": settings.mysql_database or None,
            "auto_sync": settings.mysql_auto_sync,
            "legacy_compat": settings.mysql_legacy_compat,
            "legacy_tables": 11,
            "credentials_exposed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command in {"schema", "legacy-schema"}:
        legacy = args.command == "legacy-schema"
        result = {
            "ok": True,
            "version": ENGINE_VERSION,
            "dry_run": not args.write,
            "schema_statements": len(LEGACY_SCHEMA_STATEMENTS if legacy else SCHEMA_STATEMENTS),
            "projection": "legacy-compatible" if legacy else "canonical",
            "existing_legacy_tables_modified": bool(legacy and args.write),
        }
        if args.write:
            repository = LegacyMySQLRepository() if legacy else MySQLRepository()
            try:
                if legacy:
                    repository.ensure_legacy_schema()
                else:
                    repository.ensure_schema()
            finally:
                repository.close()
            result["written"] = True
        else:
            result["written"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    store = PoolDataStore(args.data_root)
    selected = []
    errors = []
    for epoch, path, snapshot in store.iter_snapshots(
        args.from_epoch,
        args.to_epoch,
        include_live=args.include_live,
    ):
        validation = validate_exact_legacy_shape(snapshot, expected_epoch=epoch)
        if validation:
            errors.append({"epoch": epoch, "file": str(path), "errors": validation[:10]})
            continue
        state = "archive" if path.parent == store.epochs_dir else "live"
        selected.append((snapshot, state, path, projection_counts(snapshot)))

    legacy = args.command == "legacy-sync"
    legacy_tables = None
    if legacy and not errors and selected:
        try:
            legacy_tables = build_legacy_projection(x[0] for x in selected)
        except Exception as exc:
            errors.append({"projection": "legacy-compatible", "errors": [str(exc)]})

    result = {
        "ok": not errors and bool(selected),
        "version": ENGINE_VERSION,
        "dry_run": not args.write,
        "range": [selected[0][0]["epoch"], selected[-1][0]["epoch"]] if selected else None,
        "epochs": len(selected),
        "rows": {
            "accounts": sum(x[3]["accounts"] for x in selected),
            "blocks": sum(x[3]["blocks"] for x in selected),
            "bonus_awards": sum(x[3]["bonus_awards"] for x in selected),
        },
        "validation_errors": errors,
        "written": False,
        "canonical_files_modified": False,
        "projection": "legacy-compatible" if legacy else "canonical",
    }
    if legacy_tables is not None:
        result["legacy_rows"] = {
            name: len(rows) for name, rows in sorted(legacy_tables.items())
        }
    if args.write and result["ok"]:
        if legacy:
            repository = LegacyMySQLRepository()
            try:
                written = repository.replace_projection(x[0] for x in selected)
            finally:
                repository.close()
            result["written"] = True
            result["written_epochs"] = list(result["range"] or [])
            result["legacy_rows"] = written["rows"]
            result["transactional_full_replace"] = True
        else:
            repository = MySQLRepository()
            try:
                written = repository.sync_snapshots((x[0], x[1]) for x in selected)
            finally:
                repository.close()
            result["written"] = True
            result["written_epochs"] = [x["epoch"] for x in written]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
