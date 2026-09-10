#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The production server has requests.  The isolated packaging test runtime may
# not; the fake chain source never performs HTTP, so a minimal import stub is
# sufficient and keeps the self-test offline.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = type("Session", (), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    sys.modules["requests"] = requests_stub

from core.CspoE_finalizer import CspoEFinalizer, atomic_write_json, load_json, sha256_file
from core.CspoE_legacy_contract import build_legacy_snapshot, validate_exact_legacy_shape
from core.CspoE_reward_reconciler import CspoERewardReconciler
from core.version import ENGINE_VERSION

OWNER = "stake1owner"
DELEGATOR = "stake1delegator"
POOL = "pool1rewardwindowtest"


class FakeSource:
    def __init__(self, *, visible: bool, observed: int = 647) -> None:
        self.visible = visible
        self.observed = observed

    def observed_epoch(self) -> int:
        return self.observed

    def _evidence(self, epoch: int) -> dict[str, Any]:
        stakes = [
            {"stake_address": OWNER, "pool_id": POOL, "amount": "1000"},
            {"stake_address": DELEGATOR, "pool_id": POOL, "amount": "9000"},
        ]
        rewards = {OWNER: 0, DELEGATOR: 0}
        blocks = []
        if epoch == 645:
            blocks = [{"epoch": 645, "hash": "block-645", "output": "0", "fees": "0"}]
            if self.visible:
                rewards = {OWNER: 70, DELEGATOR: 30}
        total_rewards = sum(rewards.values())
        return {
            "source": "fake",
            "epoch": epoch,
            "epoch_info": {"epoch": epoch},
            "pool_history": {
                "epoch": epoch,
                "blocks": len(blocks),
                "active_stake": "10000",
                "rewards": str(total_rewards),
            },
            "pool_registration_exact": True,
            "owner_addresses": [OWNER],
            "all_stakes": stakes,
            "stake_completion": {
                "raw_count": 2,
                "completed_count": 2,
                "recovered_zero_holders": [],
            },
            "blocks": blocks,
            "rewards_by_stake": rewards,
            "secondary_verification": {
                "koios": {
                    "available": True,
                    "blocks_count": len(blocks),
                    "blocks_match_count": True,
                }
            },
        }

    def closed_epoch_evidence(
        self,
        epoch: int,
        observed_epoch: int,
        previous_delegators: list[str] | None = None,
        previous_owners: list[str] | None = None,
    ) -> dict[str, Any]:
        del observed_epoch, previous_delegators, previous_owners
        return self._evidence(int(epoch))

    def live_epoch_evidence(
        self,
        epoch: int,
        previous_delegators: list[str] | None = None,
        previous_owners: list[str] | None = None,
    ) -> dict[str, Any]:
        del previous_delegators, previous_owners
        return self._evidence(int(epoch))


def seed_workspace(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    data_root = root / "data" / "CspoE"
    archive = data_root / "epochs"
    live = data_root / "live"
    reports = data_root / "finalization_reports"
    state = data_root / "epoch_manager_state.json"
    awards = root / "data" / "awards.json"
    archive.mkdir(parents=True)
    live.mkdir(parents=True)
    reports.mkdir(parents=True)
    awards.parent.mkdir(parents=True, exist_ok=True)
    awards.write_text("[]\n", encoding="utf-8")

    stakes = [
        {"stake_address": OWNER, "pool_id": POOL, "amount": "1000"},
        {"stake_address": DELEGATOR, "pool_id": POOL, "amount": "9000"},
    ]
    seed = build_legacy_snapshot(
        epoch=644,
        previous={},
        all_stakes=stakes,
        owner_addresses=[OWNER],
        rewards_by_stake={OWNER: 0, DELEGATOR: 0},
        blocks=[],
        awards=[],
        start_epoch=644,
    )
    assert not validate_exact_legacy_shape(seed)
    atomic_write_json(archive / "epoch_644.json", seed)

    provisional_source = FakeSource(visible=False)
    finalizer = CspoEFinalizer(
        pool_id=POOL,
        history_dir=archive,
        awards_file=awards,
        start_epoch=644,
        historical_protection_end=644,
        source=provisional_source,
    )
    epoch_645, meta_645 = finalizer.build_candidate(645, 646)
    assert not meta_645["validation_errors"]
    assert epoch_645["pool"]["rewards"]["_epoch_"] == 0
    atomic_write_json(archive / "epoch_645.json", epoch_645)
    epoch_646, meta_646 = finalizer.build_candidate(646, 647)
    assert not meta_646["validation_errors"]
    atomic_write_json(archive / "epoch_646.json", epoch_646)
    atomic_write_json(
        state,
        {
            "version": ENGINE_VERSION,
            "last_collected_epoch": 647,
            "last_finalized_epoch": 646,
            "last_chain_finalized_epoch": 646,
            "last_rewards_settled_epoch": 644,
            "transition": {"status": "confirmed"},
        },
    )
    return data_root, archive, live, reports, state


def reconciler_for(
    root: Path,
    source: FakeSource,
    *,
    cls: type[CspoERewardReconciler] = CspoERewardReconciler,
) -> CspoERewardReconciler:
    data_root = root / "data" / "CspoE"
    return cls(
        pool_id=POOL,
        data_root=data_root,
        live_dir=data_root / "live",
        archive_dir=data_root / "epochs",
        state_file=data_root / "epoch_manager_state.json",
        awards_file=root / "data" / "awards.json",
        reports_dir=data_root / "finalization_reports",
        start_epoch=644,
        historical_protection_end=644,
        source=source,
    )


def test_late_reward_cascade_and_idempotence() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-reward-test-") as temporary:
        root = Path(temporary)
        data_root, archive, live, _reports, state = seed_workspace(root)
        protected_hash = sha256_file(archive / "epoch_644.json")
        before_645 = sha256_file(archive / "epoch_645.json")
        before_646 = sha256_file(archive / "epoch_646.json")
        source = FakeSource(visible=True)
        reconciler = reconciler_for(root, source)

        dry = reconciler.reconcile(
            647,
            write=False,
            report_file=data_root / "dry.json",
        )
        assert dry["ok"] and dry["dry_run"] and not dry["written"], dry
        assert dry["reward_settlement"]["epochs"][0]["evidence"]["total"] == 100, dry
        assert dry["cascade"]["reward_snapshots"]["645"]["pool"] == {
            "epoch": 100,
            "sum": 100,
        }
        assert dry["cascade"]["reward_snapshots"]["646"]["pool"] == {
            "epoch": 0,
            "sum": 100,
        }
        assert dry["cascade"]["reward_snapshots"]["647"]["pool"] == {
            "epoch": 0,
            "sum": 100,
        }
        assert all(
            check["ok"] for check in dry["cascade"]["continuity_checks"]
        )
        assert sha256_file(archive / "epoch_645.json") == before_645
        assert sha256_file(archive / "epoch_646.json") == before_646
        assert not (live / "epoch_647.json").exists()

        written = reconciler.reconcile(
            647,
            write=True,
            report_file=data_root / "write.json",
        )
        assert written["ok"] and written["written"] and written["state_updated"], written
        assert written["backup_dir"] and Path(written["backup_dir"]).is_dir(), written
        epoch_645 = load_json(archive / "epoch_645.json")
        epoch_646 = load_json(live / "epoch_646.json")
        epoch_647 = load_json(live / "epoch_647.json")
        assert epoch_645["pool"]["rewards"] == {"_epoch_": 100, "_sum_": 100}
        assert epoch_646["pool"]["rewards"] == {"_epoch_": 0, "_sum_": 100}
        assert epoch_647["pool"]["rewards"] == {"_epoch_": 0, "_sum_": 100}
        assert not (archive / "epoch_646.json").exists()
        assert sha256_file(archive / "epoch_644.json") == protected_hash
        current_state = load_json(state)
        assert current_state["last_rewards_settled_epoch"] == 645
        assert current_state["last_chain_finalized_epoch"] == 646
        assert current_state["last_collected_epoch"] == 647

        repeat = reconciler.reconcile(
            647,
            write=False,
            report_file=data_root / "repeat.json",
        )
        assert repeat["ok"] and repeat["dry_run"], repeat
        changed = [
            target for target in repeat["cascade"]["targets"] if target["changed"]
        ]
        assert not changed, changed


def test_missing_reward_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-reward-gate-") as temporary:
        root = Path(temporary)
        data_root, archive, _live, _reports, _state = seed_workspace(root)
        before = {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
        }
        result = reconciler_for(root, FakeSource(visible=False)).reconcile(
            647,
            write=False,
            report_file=data_root / "missing.json",
        )
        assert not result["ok"] and not result["written"], result
        assert any("non visibles" in error for error in result["validation_errors"]), result
        assert before == {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
        }


def test_multi_epoch_catch_up_and_live_retirement() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-catch-up-") as temporary:
        root = Path(temporary)
        data_root, archive, live, _reports, _state = seed_workspace(root)
        first_source = FakeSource(visible=True, observed=647)
        first = reconciler_for(root, first_source).reconcile(
            647,
            write=True,
            report_file=data_root / "first.json",
        )
        assert first["ok"] and (live / "epoch_647.json").is_file(), first

        catch_up_source = FakeSource(visible=True, observed=649)
        catch_up = reconciler_for(root, catch_up_source).reconcile(
            649,
            write=True,
            report_file=data_root / "catch-up.json",
        )
        assert catch_up["ok"] and catch_up["written"], catch_up
        assert catch_up["window"]["catch_up"], catch_up
        assert catch_up["window"]["rebuilt_from_epoch"] == 646, catch_up
        assert catch_up["window"]["rewards_settled_through"] == 647, catch_up
        assert (archive / "epoch_647.json").is_file()
        assert not (archive / "epoch_648.json").exists()
        assert (live / "epoch_648.json").is_file()
        assert (live / "epoch_649.json").is_file()
        assert not (live / "epoch_646.json").exists()
        assert not (live / "epoch_647.json").exists()
        assert str(live / "epoch_647.json") in catch_up["retired_live_targets"]


class FailingReconciler(CspoERewardReconciler):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_writes = 0

    def _write_payload(self, path: Path, payload: dict[str, Any]) -> None:
        if path.name.startswith("epoch_"):
            self.target_writes += 1
            if self.target_writes == 2:
                raise RuntimeError("injected write failure")
        super()._write_payload(path, payload)


class FailingStateReconciler(CspoERewardReconciler):
    def _write_payload(self, path: Path, payload: dict[str, Any]) -> None:
        if Path(path) == self.state_file:
            raise RuntimeError("injected state failure")
        super()._write_payload(path, payload)


def test_transaction_rollback() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-reward-rollback-") as temporary:
        root = Path(temporary)
        data_root, archive, live, _reports, state = seed_workspace(root)
        before = {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
            "state": sha256_file(state),
        }
        reconciler = reconciler_for(root, FakeSource(visible=True), cls=FailingReconciler)
        try:
            reconciler.reconcile(
                647,
                write=True,
                report_file=data_root / "rollback.json",
            )
        except RuntimeError as exc:
            assert "injected" in str(exc)
        else:
            raise AssertionError("the injected failure did not abort the transaction")
        assert before == {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
            "state": sha256_file(state),
        }
        assert not (live / "epoch_647.json").exists()


def test_report_is_part_of_rollback() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-report-rollback-") as temporary:
        root = Path(temporary)
        data_root, archive, live, _reports, state = seed_workspace(root)
        report = data_root / "existing-report.json"
        atomic_write_json(report, {"sentinel": True})
        before = {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
            "state": sha256_file(state),
            "report": sha256_file(report),
        }
        reconciler = reconciler_for(
            root,
            FakeSource(visible=True),
            cls=FailingStateReconciler,
        )
        try:
            reconciler.reconcile(647, write=True, report_file=report)
        except RuntimeError as exc:
            assert "state" in str(exc)
        else:
            raise AssertionError("the injected state failure did not abort the transaction")
        assert before == {
            644: sha256_file(archive / "epoch_644.json"),
            645: sha256_file(archive / "epoch_645.json"),
            646: sha256_file(archive / "epoch_646.json"),
            "state": sha256_file(state),
            "report": sha256_file(report),
        }
        assert load_json(report) == {"sentinel": True}
        assert not (live / "epoch_647.json").exists()


def test_report_cannot_overwrite_epoch_data() -> None:
    with tempfile.TemporaryDirectory(prefix="cspoe-report-path-") as temporary:
        root = Path(temporary)
        _data_root, archive, _live, _reports, _state = seed_workspace(root)
        protected = archive / "epoch_645.json"
        before = sha256_file(protected)
        reconciler = reconciler_for(root, FakeSource(visible=True))
        try:
            reconciler.reconcile(647, write=False, report_file=protected)
        except Exception as exc:
            assert "destination de rapport interdite" in str(exc)
        else:
            raise AssertionError("an epoch file was accepted as report destination")
        assert sha256_file(protected) == before


def main() -> int:
    test_late_reward_cascade_and_idempotence()
    test_missing_reward_gate()
    test_multi_epoch_catch_up_and_live_retirement()
    test_transaction_rollback()
    test_report_is_part_of_rollback()
    test_report_cannot_overwrite_epoch_data()
    print(
        f"OK - CspoE {ENGINE_VERSION}: delayed N-2 rewards + N-1/N cascade + "
        "stake_address rebuild + idempotence + transactional rollback"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
