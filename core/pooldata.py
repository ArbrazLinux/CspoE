# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Lossless pooldata file projection for static/PHP consumers."""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .CspoE_legacy_contract import validate_exact_legacy_shape
from .config import settings
from .data_store import PoolDataStore

POOLDATA_RE = re.compile(r"^pooldata_(\d+)_(\d+)\.json$")


class PooldataExportError(RuntimeError):
    pass


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class PooldataExporter:
    def __init__(
        self,
        data_root: str | Path | None = None,
        output_dir: str | Path | None = None,
        *,
        prune_nb: int | None = None,
    ) -> None:
        self.store = PoolDataStore(data_root)
        self.output_dir = Path(output_dir or self.store.data_root / "pooldata")
        self.prune_nb = int(prune_nb or settings.prune_nb)
        if self.prune_nb <= 0:
            raise PooldataExportError("PRUNE_NB doit être strictement positif")

    def build(self) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
        files = self.store.archive_files()
        if not files:
            raise PooldataExportError("aucun epoch archivé")
        epochs = sorted(files)
        expected = list(range(epochs[0], epochs[-1] + 1))
        missing = sorted(set(expected) - set(epochs))
        if missing:
            raise PooldataExportError(f"archive non contiguë; epochs absents: {missing[:20]}")

        snapshots: dict[int, dict[str, Any]] = {}
        for epoch, path in files.items():
            value = self.store.load_json(path)
            if not isinstance(value, dict):
                raise PooldataExportError(f"snapshot non objet: {path}")
            errors = validate_exact_legacy_shape(value, expected_epoch=epoch)
            if errors:
                raise PooldataExportError(f"epoch {epoch} invalide: {errors[:5]}")
            snapshots[epoch] = value

        output: dict[str, dict[str, Any]] = {}
        first = epochs[0]
        for start in range(first, epochs[-1] + 1, self.prune_nb):
            present = [e for e in epochs if start <= e < start + self.prune_nb]
            if not present:
                continue
            end = present[-1]
            name = f"pooldata_{start}_{end}.json"
            output[name] = {"history": [snapshots[e] for e in reversed(present)]}

        latest_epoch = self.store.latest_epoch(include_live=True)
        latest = self.store.snapshot(latest_epoch) if latest_epoch is not None else None
        if latest is not None:
            errors = validate_exact_legacy_shape(latest, expected_epoch=latest_epoch)
            if errors:
                raise PooldataExportError(f"live {latest_epoch} invalide: {errors[:5]}")
        return output, latest

    def export(self, *, write: bool = False) -> dict[str, Any]:
        payloads, latest = self.build()
        existing = {
            path.name
            for path in self.output_dir.glob("pooldata_*.json")
            if path.is_file() and POOLDATA_RE.fullmatch(path.name)
        } if self.output_dir.is_dir() else set()
        expected = set(payloads)
        stale = sorted(existing - expected)
        retired = []
        if write:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in payloads.items():
                atomic_write_json(self.output_dir / name, payload)
            if latest is not None:
                atomic_write_json(self.output_dir / "live.json", latest)
            if stale:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                retired_dir = self.output_dir / "retired" / timestamp
                retired_dir.mkdir(parents=True, exist_ok=True)
                for name in stale:
                    source = self.output_dir / name
                    target = retired_dir / name
                    shutil.move(str(source), str(target))
                    retired.append(str(target))
        ranges = []
        for name, payload in payloads.items():
            rows = payload["history"]
            ranges.append({
                "file": str(self.output_dir / name),
                "range": [rows[-1]["epoch"], rows[0]["epoch"]],
                "epochs": len(rows),
            })
        return {
            "ok": True,
            "dry_run": not write,
            "prune_nb": self.prune_nb,
            "files": len(payloads),
            "epochs": sum(x["epochs"] for x in ranges),
            "ranges": ranges,
            "stale_files": stale,
            "retired_files": retired,
            "latest_epoch": latest.get("epoch") if latest else None,
            "written": write,
            "business_values_recalculated": False,
            "canonical_files_modified": False,
        }
