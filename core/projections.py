# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Post-commit projections for pooldata files and the optional MySQL mirror."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import settings
from .data_store import PoolDataStore
from .mysql import MySQLRepository
from .mysql_legacy import LegacyMySQLRepository
from .pooldata import PooldataExporter


def refresh_projections(
    data_root: str | Path,
    *,
    write: bool,
    pooldata: bool | None = None,
    mysql: bool | None = None,
) -> dict[str, Any]:
    data_root = Path(data_root)
    use_pooldata = settings.pooldata_auto_export if pooldata is None else bool(pooldata)
    use_mysql = settings.mysql_auto_sync if mysql is None else bool(mysql)
    report: dict[str, Any] = {
        "ok": True,
        "written": write,
        "canonical_files_modified": False,
        "pooldata": {"enabled": use_pooldata, "skipped": not use_pooldata},
        "mysql": {"enabled": use_mysql, "skipped": not use_mysql},
        "errors": [],
    }
    if use_pooldata:
        try:
            report["pooldata"] = PooldataExporter(data_root).export(write=write)
        except Exception as exc:
            report["errors"].append(f"pooldata: {exc}")
            report["pooldata"] = {"enabled": True, "ok": False, "error": str(exc)}

    if use_mysql:
        try:
            store = PoolDataStore(data_root)
            rows = []
            for _epoch, path, snapshot in store.iter_snapshots(include_live=True):
                state = "archive" if path.parent == store.epochs_dir else "live"
                rows.append((snapshot, state))
            if write:
                repository = MySQLRepository()
                try:
                    written = repository.sync_snapshots(rows)
                finally:
                    repository.close()
                report["mysql"] = {
                    "enabled": True,
                    "ok": True,
                    "dry_run": False,
                    "epochs": len(written),
                    "range": [written[0]["epoch"], written[-1]["epoch"]] if written else None,
                }
                if settings.mysql_legacy_compat:
                    legacy_repository = LegacyMySQLRepository()
                    try:
                        legacy = legacy_repository.replace_projection(
                            snapshot for snapshot, _state in rows
                        )
                    finally:
                        legacy_repository.close()
                    report["mysql"]["legacy_compat"] = {
                        "ok": True,
                        "transactional_full_replace": True,
                        **legacy,
                    }
            else:
                report["mysql"] = {
                    "enabled": True,
                    "ok": True,
                    "dry_run": True,
                    "epochs": len(rows),
                    "range": [rows[0][0]["epoch"], rows[-1][0]["epoch"]] if rows else None,
                }
                if settings.mysql_legacy_compat:
                    report["mysql"]["legacy_compat"] = {
                        "ok": True,
                        "dry_run": True,
                        "epochs": len(rows),
                    }
        except Exception as exc:
            report["errors"].append(f"mysql: {exc}")
            report["mysql"] = {"enabled": True, "ok": False, "error": str(exc)}
    report["ok"] = not report["errors"]
    return report
