# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Primary Blockfrost evidence with an optional independent Koios check."""
from __future__ import annotations

from typing import Any, Optional

from .blockfrost import BlockfrostClient
from .config import settings
from .koios import KoiosClient


class CspoEChainSource:
    def __init__(
        self,
        pool_id: Optional[str] = None,
        blockfrost: Optional[BlockfrostClient] = None,
        secondary_enabled: bool = True,
    ) -> None:
        self.pool_id = pool_id or settings.bech32_pool_id
        self.blockfrost = blockfrost or BlockfrostClient(pool_id=self.pool_id)
        self.secondary_enabled = bool(secondary_enabled)

    def health(self) -> dict[str, Any]:
        return self.blockfrost.health()

    def observed_epoch(self) -> int:
        return int(self.blockfrost.epoch()["epoch"])

    def epoch_evidence(
        self,
        epoch: int,
        observed_epoch: Optional[int] = None,
        previous_delegators: Optional[list[str]] = None,
        previous_owners: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        evidence = self.blockfrost.closed_epoch_evidence(
            epoch,
            observed_epoch,
            self.pool_id,
            previous_delegators=previous_delegators,
            previous_owners=previous_owners,
        )
        secondary: dict[str, Any] = {"available": False}
        try:
            if not self.secondary_enabled:
                raise RuntimeError("Koios check disabled for this reconstruction")
            blocks = KoiosClient(
                pool_id=self.pool_id,
                timeout=5,
                retries=0,
            ).pool_blocks(int(epoch))
            secondary = {
                "available": True,
                "blocks_count": len(blocks),
                "blocks_match_count": len(blocks)
                == len(evidence.get("blocks") or []),
            }
        except Exception as exc:
            secondary = {"available": False, "reason": str(exc)}
        evidence["secondary_verification"] = {"koios": secondary}
        return evidence

    def closed_epoch_evidence(
        self,
        epoch: int,
        observed_epoch: int,
        previous_delegators: Optional[list[str]] = None,
        previous_owners: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return self.epoch_evidence(
            epoch,
            observed_epoch,
            previous_delegators,
            previous_owners,
        )

    def live_epoch_evidence(
        self,
        epoch: Optional[int] = None,
        previous_delegators: Optional[list[str]] = None,
        previous_owners: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        live_epoch = int(epoch if epoch is not None else self.observed_epoch())
        return self.epoch_evidence(
            live_epoch,
            live_epoch,
            previous_delegators,
            previous_owners,
        )
