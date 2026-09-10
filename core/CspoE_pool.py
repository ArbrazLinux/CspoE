# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Convenience facade over the canonical CspoE history."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .CspoE_history import CspoEHistory


class CspoEPool:
    def __init__(self, data_root: str | Path | None = None) -> None:
        self.history = CspoEHistory(data_root)

    def snapshot(self, epoch: int | None = None) -> dict[str, Any]:
        return self.history.get_epoch(epoch) if epoch is not None else self.history.get_latest_epoch()

    def pool(self, epoch: int | None = None) -> dict[str, Any]:
        return self.snapshot(epoch).get("pool", {})

    def owners(self, epoch: int | None = None) -> dict[str, Any]:
        return self.snapshot(epoch).get("owners", {})

    def delegators(self, epoch: int | None = None) -> dict[str, Any]:
        return self.snapshot(epoch).get("delegators", {})

    def blocks(self, epoch: int | None = None) -> dict[str, Any]:
        return self.snapshot(epoch).get("blocks", {})

    def bonuses(self, epoch: int | None = None) -> dict[str, Any]:
        return self.snapshot(epoch).get("bonuses", {})

    def dashboard(self, epoch: int | None = None) -> dict[str, Any]:
        snapshot = self.snapshot(epoch)
        return {
            "epoch": snapshot.get("epoch"),
            "pool": snapshot.get("pool", {}),
            "owners": snapshot.get("owners", {}),
            "delegators": snapshot.get("delegators", {}),
            "blocks": snapshot.get("blocks", {}),
            "bonuses": snapshot.get("bonuses", {}),
        }
