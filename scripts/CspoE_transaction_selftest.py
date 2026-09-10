#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline tests for GUI data views and Cardano command-plan assistants."""
from __future__ import annotations

import json
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.transaction_drafts import (
    DraftStore,
    DraftValidationError,
    bonus_distribution_draft,
    drep_vote_draft,
    operational_certificate_draft,
)
from desktop.model import AdminModel


PAYMENT_A = "addr1" + "q" * 58
PAYMENT_B = "addr1" + "p" * 58
STAKE = "stake1" + "z" * 54
TX_IN = "cd" * 32 + "#0"
ACTION_ID = "ab" * 32


def snapshot(epoch: int, *, reward: int, block: bool, bonus: int) -> dict:
    account = {
        "stake_address": STAKE,
        "first_epoch": 700,
        "since_epoch": 700,
        "epoch_count": epoch - 699,
        "loyalty": 100.0,
        "comeback_count": 0,
        "stake": {"_epoch_": 5_000_000, "_diff_": 0},
        "rewards": {"_epoch_": reward, "_sum_": reward},
        "bonuses": {"amount": bonus, "_sum_": bonus, "assets": []},
        "ROA": {"_lifetime_": 3.5},
    }
    return {
        "epoch": epoch,
        "pool": {
            "stake": {"_epoch_": 5_000_000, "_diff_": 0},
            "rewards": {"_epoch_": reward, "_sum_": reward},
            "ROA": {"_lifetime_": 3.5},
        },
        "owners": {"ownersNb": 0, "owner": []},
        "delegators": {"delegsNb": 1, "delegator": [account]},
        "blocks": {
            "epoch": int(block),
            "total_blocks": int(block),
            "block": ([{"hash": "block-test", "height": 1, "slot": 2, "time": 3, "tx_count": 1, "fees": 4, "output": 5}] if block else []),
        },
        "bonuses": {
            "amount": bonus,
            "_sum_": bonus,
            "awarded_delegators": ([{"stake_address": STAKE, "amount": bonus, "_sum_": bonus, "assets": []}] if bonus else []),
        },
    }


def main() -> int:
    tests: list[str] = []

    data_tab_source = (ROOT / "desktop" / "data_tab.py").read_text(encoding="utf-8")
    assert "super().__lt__(" not in data_tab_source
    assert "self.text().casefold() < other.text().casefold()" in data_tab_source
    tests.append("qt_sort_comparator_non_recursive")

    bonus = bonus_distribution_draft(
        recipients_text=f"{PAYMENT_A} ; 1,25\n{PAYMENT_B} ; 2.000001",
        tx_in=TX_IN,
        change_address=PAYMENT_A,
        network="mainnet",
        testnet_magic=0,
        out_file="bonus-tx.raw",
    )
    assert bonus["total_lovelace"] == 3_250_001
    assert len(bonus["recipients"]) == 2
    assert "--tx-out" in bonus["commands"][0]["argv"]
    assert not bonus["executed"] and not bonus["signed"] and not bonus["submitted"]
    tests.append("bonus_exact_ada_and_unsigned_policy")

    try:
        bonus_distribution_draft(
            recipients_text=f"{STAKE} ; 1",
            tx_in=TX_IN,
            change_address=PAYMENT_A,
            network="mainnet",
            testnet_magic=0,
            out_file="bad.raw",
        )
    except DraftValidationError:
        pass
    else:
        raise AssertionError("stake_address accepted as a payment destination")
    tests.append("stake_address_payment_rejected")

    vote = drep_vote_draft(
        governance_action_tx_id=ACTION_ID,
        governance_action_index=0,
        decision="yes",
        drep_verification_key_file="drep.vkey",
        vote_file="action.vote",
        tx_in=TX_IN,
        change_address=PAYMENT_A,
        network="testnet",
        testnet_magic=42,
        transaction_out_file="vote-tx.raw",
    )
    assert len(vote["commands"]) == 2
    flattened = [argument for command in vote["commands"] for argument in command["argv"]]
    assert "--drep-verification-key-file" in flattened
    assert "--signing-key-file" not in flattened
    assert "submit" not in flattened
    tests.append("drep_vote_build_without_sign_or_submit")

    opcert = operational_certificate_draft(
        kes_verification_key_file="kes.vkey",
        cold_signing_key_file="cold.skey",
        counter_file="cold.counter",
        kes_period=123,
        out_file="opcert.cert",
    )
    assert opcert["commands"][0]["offline_only"] is True
    assert opcert["execution_policy"] == "preview_and_save_only"
    tests.append("opcert_explicit_offline_policy")

    with tempfile.TemporaryDirectory(prefix="cspoe-gui-selftest-") as temporary:
        root = Path(temporary)
        drafts = root / "drafts"
        saved = DraftStore(drafts).save(vote)
        assert stat.S_IMODE(drafts.stat().st_mode) == 0o700
        assert stat.S_IMODE(saved.stat().st_mode) == 0o600
        assert json.loads(saved.read_text(encoding="utf-8"))["kind"] == "drep_vote"
        tests.append("draft_atomic_restrictive_storage")

        data_root = root / "data" / "CspoE"
        epochs = data_root / "epochs"
        live = data_root / "live"
        epochs.mkdir(parents=True)
        live.mkdir(parents=True)
        (epochs / "epoch_700.json").write_text(
            json.dumps(snapshot(700, reward=0, block=True, bonus=0)), encoding="utf-8"
        )
        (live / "epoch_701.json").write_text(
            json.dumps(snapshot(701, reward=100, block=False, bonus=25)), encoding="utf-8"
        )
        (data_root / "epoch_manager_state.json").write_text(
            json.dumps(
                {
                    "last_collected_epoch": 701,
                    "last_chain_finalized_epoch": 700,
                    "last_rewards_settled_epoch": 699,
                }
            ),
            encoding="utf-8",
        )
        model = AdminModel(data_root)
        browser = model.browser_data()
        assert [row["epoch"] for row in browser["epochs"]] == [701, 700]
        assert len(browser["blocks"]) == 1
        assert len(browser["bonuses"]) == 1
        assert len(model.delegator_rows("stake1")) == 1
        assert len(model.delegator_history(STAKE)) == 2
        assert len(model.account_table()) == 1
        tests.append("canonical_gui_data_browser")

    print(
        json.dumps(
            {
                "ok": True,
                "test": "cspoe-gui-transaction-drafts-v1",
                "tests": tests,
                "transactions_executed": False,
                "transactions_signed": False,
                "transactions_submitted": False,
                "credentials_read": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
