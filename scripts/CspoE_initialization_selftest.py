#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline checks for the configurable initialization and N-2 archive policy."""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = type("Session", (), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    sys.modules["requests"] = requests_stub

from scripts.CspoE_initialize import activate, initialization_window, reconstruct
from core.CspoE_legacy_contract import awards_for_epoch


class FakeSource:
    def __init__(self, observed: int) -> None:
        self.observed = observed
        self.evidence_calls = 0

    def observed_epoch(self) -> int:
        return self.observed

    @staticmethod
    def _evidence(epoch: int) -> dict:
        address = "stake_test1_operator"
        return {
            "epoch_info": {"epoch": epoch},
            "all_stakes": [{"stake_address": address, "amount": 1_000_000}],
            "owner_addresses": [],
            "rewards_by_stake": {address: 0},
            "blocks": [],
            "pool_history": {},
            "pool_registration_exact": True,
            "secondary_verification": {"koios": {"available": False}},
        }

    def closed_epoch_evidence(self, epoch, observed_epoch, previous_delegators=None, previous_owners=None):
        self.evidence_calls += 1
        return self._evidence(int(epoch))

    def live_epoch_evidence(self, epoch, previous_delegators=None, previous_owners=None):
        self.evidence_calls += 1
        return self._evidence(int(epoch))


def main() -> int:
    assert initialization_window(10, 13) == {
        "first_epoch": 10,
        "archive_end": 11,
        "closed_live_epoch": 12,
        "current_live_epoch": 13,
    }
    with tempfile.TemporaryDirectory(prefix="cspoe-init-selftest-") as temporary:
        root = Path(temporary)
        awards = root / "awards-does-not-exist.json"
        assert awards_for_epoch(awards, 10) == []
        empty_awards = root / "empty-awards.json"
        empty_awards.write_text("\n", encoding="utf-8")
        assert awards_for_epoch(empty_awards, 10) == []
        malformed_awards = root / "malformed-awards.json"
        malformed_awards.write_text("{not-json}\n", encoding="utf-8")
        try:
            awards_for_epoch(malformed_awards, 10)
            raise AssertionError("malformed awards must be rejected")
        except json.JSONDecodeError:
            pass
        rebuilt = root / "rebuilt"
        first_source = FakeSource(13)
        result = reconstruct(
            output=rebuilt,
            first_epoch=10,
            observed_epoch=13,
            pool_id="pool_test1",
            awards_file=awards,
            source=first_source,
        )
        assert result["window"]["archive_end"] == 11
        assert sorted(path.name for path in (rebuilt / "epochs").glob("*.json")) == [
            "epoch_10.json", "epoch_11.json"
        ]
        assert sorted(path.name for path in (rebuilt / "live").glob("*.json")) == [
            "epoch_12.json", "epoch_13.json"
        ]
        resumed_source = FakeSource(13)
        resumed = reconstruct(
            output=rebuilt,
            first_epoch=10,
            observed_epoch=13,
            pool_id="pool_test1",
            awards_file=awards,
            source=resumed_source,
        )
        assert resumed_source.evidence_calls == 0
        assert resumed["checkpoint_reused_epochs"] == [10, 11, 12, 13]
        data_root = root / "data" / "CspoE"
        (data_root / "epochs").mkdir(parents=True)
        (data_root / "live").mkdir()
        activation = activate(rebuilt, data_root=data_root, window=result["window"])
        state = json.loads((data_root / "epoch_manager_state.json").read_text(encoding="utf-8"))
        assert activation["archive_range"] == [10, 11]
        assert state["pool_first_epoch"] == 10
        assert state["last_rewards_settled_epoch"] == 11
        assert state["last_chain_finalized_epoch"] == 12
        assert state["last_collected_epoch"] == 13
    print(json.dumps({
        "ok": True,
        "test": "configurable-initialization-n-minus-two",
        "checks": [
            "POOL_FIRST_EPOCH lower bound",
            "archive ends at observed N-2",
            "closed N-1 and current N remain live",
            "activation watermarks and protection manifest",
            "durable snapshot resume without repeated API evidence",
            "missing and empty awards mean no operator bonuses",
            "malformed non-empty awards remain blocking",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
