#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline tests for pooldata, GUI model and MySQL projection."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_legacy_contract import build_legacy_snapshot
from core.data_store import PoolDataStore
from core.mysql import MySQLRepository, epoch_projection, projection_counts
from core.mysql_legacy import LegacyMySQLRepository, build_legacy_projection
from core.pooldata import PooldataExporter, atomic_write_json
from core.version import ENGINE_VERSION
from desktop.model import AdminModel

OWNER = "stake1componentowner"
DELEGATOR = "stake1componentdelegator"
POOL = "pool1componenttest"


def snapshots() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    stakes = [
        {"stake_address": OWNER, "pool_id": POOL, "amount": "1000"},
        {"stake_address": DELEGATOR, "pool_id": POOL, "amount": "9000"},
    ]
    first = build_legacy_snapshot(
        epoch=644,
        previous={},
        all_stakes=stakes,
        owner_addresses=[OWNER],
        rewards_by_stake={OWNER: 0, DELEGATOR: 0},
        blocks=[],
        awards=[],
        start_epoch=644,
    )
    second = build_legacy_snapshot(
        epoch=645,
        previous=first,
        all_stakes=stakes,
        owner_addresses=[OWNER],
        rewards_by_stake={OWNER: 70, DELEGATOR: 30},
        blocks=[{"epoch": 645, "hash": "block-645", "output": "0", "fees": "0"}],
        awards=[],
        start_epoch=644,
    )
    third = build_legacy_snapshot(
        epoch=646,
        previous=second,
        all_stakes=stakes,
        owner_addresses=[OWNER],
        rewards_by_stake={OWNER: 0, DELEGATOR: 0},
        blocks=[],
        awards=[],
        start_epoch=644,
    )
    return first, second, third


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    def execute(self, query: str, params: Any = None) -> None:
        self.connection.executions.append((" ".join(query.split()), params))

    def executemany(self, query: str, params: Any) -> None:
        for row in params:
            self.execute(query, row)

    def close(self) -> None:
        self.connection.closed_cursors += 1


class FakeConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, Any]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed_cursors = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def main() -> int:
    first, second, live_snapshot = snapshots()
    with tempfile.TemporaryDirectory(prefix="cspoe-components-") as temporary:
        data_root = Path(temporary) / "data" / "CspoE"
        archive = data_root / "epochs"
        live = data_root / "live"
        archive.mkdir(parents=True)
        live.mkdir(parents=True)
        atomic_write_json(archive / "epoch_644.json", first)
        atomic_write_json(archive / "epoch_645.json", second)
        atomic_write_json(live / "epoch_646.json", live_snapshot)
        atomic_write_json(
            data_root / "epoch_manager_state.json",
            {
                "version": ENGINE_VERSION,
                "last_collected_epoch": 646,
                "last_finalized_epoch": 645,
                "last_chain_finalized_epoch": 645,
                "last_rewards_settled_epoch": 644,
            },
        )

        store = PoolDataStore(data_root)
        assert store.latest_epoch() == 646
        assert store.snapshot(645)["pool"]["rewards"]["_epoch_"] == 100

        model = AdminModel(data_root)
        assert model.dashboard()["epoch"] == 646
        assert len(model.account_table()) == 2
        assert "Rewards stabilisées : 644" in model.dashboard_text()

        output = data_root / "pooldata"
        output.mkdir()
        (output / "pooldata_644_644.json").write_text("{}\n", encoding="utf-8")
        dry = PooldataExporter(data_root, output, prune_nb=10).export(write=False)
        assert dry["ok"] and dry["stale_files"] == ["pooldata_644_644.json"]
        written = PooldataExporter(data_root, output, prune_nb=10).export(write=True)
        assert written["written"] and written["retired_files"]
        payload = json.loads((output / "pooldata_644_645.json").read_text(encoding="utf-8"))
        assert [row["epoch"] for row in payload["history"]] == [645, 644]
        assert json.loads((output / "live.json").read_text(encoding="utf-8"))["epoch"] == 646

        counts = projection_counts(second)
        assert counts == {"accounts": 2, "blocks": 1, "bonus_awards": 0}
        assert epoch_projection(second, "archive")[0] == 645
        fake = FakeConnection()
        repository = MySQLRepository()
        repository.connection = fake
        repository.ensure_schema()
        result = repository.upsert_snapshot(second, snapshot_state="archive")
        repository.close()
        assert result["epoch"] == 645 and result["accounts"] == 2
        assert fake.commits == 2 and fake.rollbacks == 0 and fake.closed
        assert any("INSERT INTO cspoe_accounts" in query for query, _params in fake.executions)
        assert any("DELETE FROM cspoe_blocks" in query for query, _params in fake.executions)

        legacy = build_legacy_projection((first, second, live_snapshot))
        assert len(legacy["epoch"]) == 3
        assert len(legacy["stake"]) == 3
        assert len(legacy["pledge"]) == 3
        assert len(legacy["rewards"]) == 1
        assert len(legacy["owner_rewards"]) == 1
        second_delegator_roa = second["delegators"]["delegator"][0]["ROA"]
        assert legacy["stake"][1][-3:] == (
            second_delegator_roa["_lifetime_"],
            second_delegator_roa["_max_"],
            second_delegator_roa["_bonuses_included_"],
        )

        legacy_fake = FakeConnection()
        legacy_repository = LegacyMySQLRepository()
        legacy_repository.connection = legacy_fake
        legacy_result = legacy_repository.replace_projection((first, second, live_snapshot))
        legacy_repository.close()
        assert legacy_result["epochs"] == 3
        assert legacy_result["rows"]["rewards"] == 1
        assert legacy_fake.commits == 2 and legacy_fake.rollbacks == 0
        assert any("DELETE FROM `rewards`" in query for query, _params in legacy_fake.executions)
        assert any("INSERT INTO `epoch`" in query for query, _params in legacy_fake.executions)

    print(
        f"OK - CspoE {ENGINE_VERSION}: canonical store + GUI model + "
        "lossless pooldata + idempotent MySQL projections"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
