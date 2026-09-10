# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Read-only access to the canonical CspoE archive and live snapshot."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .config import settings

EPOCH_FILE_RE = re.compile(r"^epoch_(\d+)\.json$")


class DataStoreError(RuntimeError):
    pass


class PoolDataStore:
    """Small canonical store used by the GUI, exports and public API helpers.

    ``epochs`` is authoritative for reward-settled epochs through N-2.
    ``live`` contains the reward-pending closed N-1 and current N snapshots and
    is consulted only when no settled archive exists for the same epoch.
    """

    def __init__(self, data_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root or Path(settings.data_dir) / "CspoE")
        self.epochs_dir = self.data_root / "epochs"
        self.live_dir = self.data_root / "live"
        self.state_file = self.data_root / "epoch_manager_state.json"

    @staticmethod
    def load_json(path: Path, *, required: bool = True) -> Any:
        if not path.is_file():
            if required:
                raise DataStoreError(f"fichier absent: {path}")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DataStoreError(f"JSON invalide: {path}: {exc}") from exc

    @staticmethod
    def epoch_files(directory: Path) -> dict[int, Path]:
        result: dict[int, Path] = {}
        if not directory.is_dir():
            return result
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            match = EPOCH_FILE_RE.fullmatch(path.name)
            if match:
                result[int(match.group(1))] = path
        return result

    def state(self) -> dict[str, Any]:
        value = self.load_json(self.state_file, required=False)
        return value if isinstance(value, dict) else {}

    def archive_files(self) -> dict[int, Path]:
        return self.epoch_files(self.epochs_dir)

    def live_files(self) -> dict[int, Path]:
        return self.epoch_files(self.live_dir)

    def all_files(self, *, include_live: bool = True) -> dict[int, Path]:
        result = self.archive_files()
        if include_live:
            for epoch, path in self.live_files().items():
                result.setdefault(epoch, path)
        return dict(sorted(result.items()))

    def path_for_epoch(self, epoch: int, *, include_live: bool = True) -> Path:
        epoch = int(epoch)
        archive = self.epochs_dir / f"epoch_{epoch}.json"
        if archive.is_file():
            return archive
        live = self.live_dir / f"epoch_{epoch}.json"
        if include_live and live.is_file():
            return live
        raise DataStoreError(f"epoch {epoch} absente")

    def snapshot(self, epoch: int, *, include_live: bool = True) -> dict[str, Any]:
        value = self.load_json(self.path_for_epoch(epoch, include_live=include_live))
        if not isinstance(value, dict):
            raise DataStoreError(f"snapshot epoch {epoch}: objet JSON attendu")
        return value

    def latest_epoch(self, *, include_live: bool = True) -> int | None:
        state = self.state()
        if include_live and state.get("last_collected_epoch") is not None:
            epoch = int(state["last_collected_epoch"])
            if (self.live_dir / f"epoch_{epoch}.json").is_file():
                return epoch
        files = self.all_files(include_live=include_live)
        return max(files) if files else None

    def live(self) -> dict[str, Any]:
        epoch = self.latest_epoch(include_live=True)
        if epoch is None:
            return {}
        return self.snapshot(epoch)

    def iter_snapshots(
        self,
        start_epoch: int | None = None,
        end_epoch: int | None = None,
        *,
        include_live: bool = True,
    ) -> Iterable[tuple[int, Path, dict[str, Any]]]:
        for epoch, path in self.all_files(include_live=include_live).items():
            if start_epoch is not None and epoch < int(start_epoch):
                continue
            if end_epoch is not None and epoch > int(end_epoch):
                continue
            value = self.load_json(path)
            if not isinstance(value, dict):
                raise DataStoreError(f"snapshot non objet: {path}")
            yield epoch, path, value

    @staticmethod
    def account_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for role, container, key in (
            ("owner", snapshot.get("owners"), "owner"),
            ("delegator", snapshot.get("delegators"), "delegator"),
        ):
            values = container.get(key, []) if isinstance(container, dict) else []
            for position, row in enumerate(values if isinstance(values, list) else []):
                if isinstance(row, dict):
                    rows.append({"role": role, "position": position, **row})
        return rows

    def summary(self) -> dict[str, Any]:
        epoch = self.latest_epoch(include_live=True)
        if epoch is None:
            return {"epoch": None, "state": self.state()}
        snapshot = self.snapshot(epoch)
        pool = snapshot.get("pool") if isinstance(snapshot.get("pool"), dict) else {}
        stake = pool.get("stake") if isinstance(pool.get("stake"), dict) else {}
        rewards = pool.get("rewards") if isinstance(pool.get("rewards"), dict) else {}
        blocks = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), dict) else {}
        delegators = snapshot.get("delegators") if isinstance(snapshot.get("delegators"), dict) else {}
        owners = snapshot.get("owners") if isinstance(snapshot.get("owners"), dict) else {}
        bonuses = snapshot.get("bonuses") if isinstance(snapshot.get("bonuses"), dict) else {}
        return {
            "epoch": epoch,
            "state": self.state(),
            "stake": int(stake.get("_epoch_", 0) or 0),
            "rewards": int(rewards.get("_epoch_", 0) or 0),
            "rewards_sum": int(rewards.get("_sum_", 0) or 0),
            "blocks": int(blocks.get("epoch", 0) or 0),
            "blocks_sum": int(blocks.get("total_blocks", 0) or 0),
            "delegators": int(delegators.get("delegsNb", 0) or 0),
            "owners": int(owners.get("ownersNb", 0) or 0),
            "bonus": int(bonuses.get("amount", 0) or 0),
            "roa": (pool.get("ROA") or {}).get("_lifetime_", 0),
        }
