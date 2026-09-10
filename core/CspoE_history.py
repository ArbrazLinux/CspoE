# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Version-independent read-only history API for canonical epoch files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .data_store import DataStoreError, PoolDataStore
from .version import ENGINE_VERSION


class CspoEHistoryError(DataStoreError):
    pass


class EpochNotFound(CspoEHistoryError):
    pass


class CspoEHistory:
    def __init__(self, data_root: str | Path | None = None, *, include_live: bool = True) -> None:
        self.store = PoolDataStore(data_root)
        self.include_live = include_live

    @property
    def metadata(self) -> dict[str, Any]:
        files = self.store.all_files(include_live=self.include_live)
        epochs = sorted(files)
        return {
            "version": ENGINE_VERSION,
            "source": "canonical epoch files",
            "first_epoch": epochs[0] if epochs else None,
            "last_epoch": epochs[-1] if epochs else None,
            "epoch_count": len(epochs),
        }

    def first_epoch(self) -> int | None:
        return self.metadata["first_epoch"]

    def last_epoch(self) -> int | None:
        return self.metadata["last_epoch"]

    def epoch_count(self) -> int:
        return int(self.metadata["epoch_count"])

    def has_epoch(self, epoch: int) -> bool:
        try:
            self.store.path_for_epoch(epoch, include_live=self.include_live)
            return True
        except DataStoreError:
            return False

    def get_epoch(self, epoch: int) -> dict[str, Any]:
        try:
            return self.store.snapshot(epoch, include_live=self.include_live)
        except DataStoreError as exc:
            raise EpochNotFound(str(exc)) from exc

    def get_latest_epoch(self) -> dict[str, Any]:
        epoch = self.last_epoch()
        if epoch is None:
            raise EpochNotFound("historique vide")
        return self.get_epoch(epoch)

    def iter_epochs(
        self,
        start: int | None = None,
        end: int | None = None,
        descending: bool = False,
    ) -> Iterable[dict[str, Any]]:
        rows = list(
            self.store.iter_snapshots(
                start_epoch=start,
                end_epoch=end,
                include_live=self.include_live,
            )
        )
        if descending:
            rows.reverse()
        for _epoch, _path, snapshot in rows:
            yield snapshot

    def get_epoch_range(self, start: int, end: int, descending: bool = False) -> list[dict[str, Any]]:
        return list(self.iter_epochs(start, end, descending))

    def get_delegator_history(self, stake_address: str) -> list[dict[str, Any]]:
        result = []
        for snapshot in self.iter_epochs():
            for row in PoolDataStore.account_rows(snapshot):
                if row["role"] == "delegator" and row.get("stake_address") == stake_address:
                    result.append({"epoch": snapshot.get("epoch"), "delegator": row})
                    break
        return result

    def get_block_history(self) -> list[dict[str, Any]]:
        result = []
        for snapshot in self.iter_epochs():
            block_section = snapshot.get("blocks") or {}
            blocks = block_section.get("block", []) if isinstance(block_section, dict) else []
            result.append({"epoch": snapshot.get("epoch"), "blocks": blocks, "count": len(blocks)})
        return result

    def summary(self) -> dict[str, Any]:
        result = dict(self.metadata)
        result["latest_snapshot"] = self.get_latest_epoch() if self.epoch_count() else None
        return result
