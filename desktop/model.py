# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Qt-independent presentation model, kept testable on headless servers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.data_store import PoolDataStore


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def ada(lovelace: int | float) -> str:
    return f"{float(lovelace) / 1_000_000:,.2f} ADA"


class AdminModel:
    def __init__(self, data_root: str | Path | None = None) -> None:
        self.store = PoolDataStore(data_root)

    def dashboard(self) -> dict[str, Any]:
        return self.store.summary()

    def dashboard_text(self) -> str:
        summary = self.dashboard()
        state = summary.get("state") or {}
        return "\n".join(
            (
                f"Epoch live : {summary.get('epoch', '—')}",
                f"Epoch chaîne finalisée : {state.get('last_chain_finalized_epoch', '—')}",
                f"Rewards stabilisées : {state.get('last_rewards_settled_epoch', '—')}",
                "",
                f"Stake : {ada(summary.get('stake', 0))}",
                f"Rewards epoch : {ada(summary.get('rewards', 0))}",
                f"Rewards cumulées : {ada(summary.get('rewards_sum', 0))}",
                f"Blocs : {summary.get('blocks', 0)} / {summary.get('blocks_sum', 0)} cumulés",
                f"Owners : {summary.get('owners', 0)}",
                f"Délégataires : {summary.get('delegators', 0)}",
                f"ROA pool : {summary.get('roa', 0)} %",
            )
        )

    def account_table(self) -> list[list[str]]:
        snapshot = self.store.live()
        result: list[list[str]] = []
        for row in self.store.account_rows(snapshot):
            stake = _dict(row.get("stake"))
            rewards = _dict(row.get("rewards"))
            result.append(
                [
                    str(row.get("role", "")),
                    str(row.get("stake_address", "")),
                    ada(_integer(stake.get("_epoch_"))),
                    ada(_integer(rewards.get("_epoch_"))),
                    ada(_integer(rewards.get("_sum_"))),
                    str(row.get("loyalty", 0)),
                    str(row.get("epoch_count", 0)),
                ]
            )
        return result

    def latest_snapshot(self) -> dict[str, Any]:
        return self.store.live()

    def epoch_rows(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.browser_data()["epochs"]
        return rows if limit is None else rows[: max(0, int(limit))]

    def browser_data(self) -> dict[str, list[dict[str, Any]]]:
        """Load epoch, block and bonus tables in one chronological pass."""
        rows: list[dict[str, Any]] = []
        block_rows: list[dict[str, Any]] = []
        bonus_rows: list[dict[str, Any]] = []
        for epoch, path, snapshot in self.store.iter_snapshots(include_live=True):
            pool = _dict(snapshot.get("pool"))
            stake = _dict(pool.get("stake"))
            rewards = _dict(pool.get("rewards"))
            roa = _dict(pool.get("ROA"))
            owners = _dict(snapshot.get("owners"))
            delegators = _dict(snapshot.get("delegators"))
            blocks = _dict(snapshot.get("blocks"))
            bonuses = _dict(snapshot.get("bonuses"))
            rows.append(
                {
                    "epoch": epoch,
                    "state": "archive" if path.parent == self.store.epochs_dir else "live",
                    "stake": _integer(stake.get("_epoch_")),
                    "stake_diff": _integer(stake.get("_diff_")),
                    "rewards": _integer(rewards.get("_epoch_")),
                    "rewards_sum": _integer(rewards.get("_sum_")),
                    "roa": float(roa.get("_lifetime_", 0) or 0),
                    "owners": _integer(owners.get("ownersNb")),
                    "delegators": _integer(delegators.get("delegsNb")),
                    "blocks": _integer(blocks.get("epoch")),
                    "blocks_sum": _integer(blocks.get("total_blocks")),
                    "bonus": _integer(bonuses.get("amount")),
                }
            )
            for block in _rows(blocks.get("block")):
                block_rows.append({"epoch": epoch, **block})
            for award in _rows(bonuses.get("awarded_delegators")):
                bonus_rows.append(
                    {
                        "epoch": epoch,
                        "stake_address": str(
                            award.get("stake_address") or award.get("address") or ""
                        ),
                        "amount": _integer(award.get("amount")),
                        "sum": _integer(award.get("_sum_", award.get("sum", 0))),
                        "assets": _rows(award.get("assets")),
                    }
                )
        rows.reverse()
        block_rows.sort(
            key=lambda row: (_integer(row.get("epoch")), _integer(row.get("height"))),
            reverse=True,
        )
        bonus_rows.sort(
            key=lambda row: (row["epoch"], row["amount"], row["stake_address"]),
            reverse=True,
        )
        return {"epochs": rows, "blocks": block_rows, "bonuses": bonus_rows}

    def delegator_rows(self, search: str = "") -> list[dict[str, Any]]:
        needle = str(search).strip().lower()
        snapshot = self.latest_snapshot()
        result = []
        for row in self.store.account_rows(snapshot):
            if row.get("role") != "delegator":
                continue
            address = str(row.get("stake_address") or "")
            if needle and needle not in address.lower():
                continue
            stake = _dict(row.get("stake"))
            rewards = _dict(row.get("rewards"))
            bonuses = _dict(row.get("bonuses"))
            roa = _dict(row.get("ROA"))
            result.append(
                {
                    "stake_address": address,
                    "stake": _integer(stake.get("_epoch_")),
                    "stake_diff": _integer(stake.get("_diff_")),
                    "rewards": _integer(rewards.get("_epoch_")),
                    "rewards_sum": _integer(rewards.get("_sum_")),
                    "bonus": _integer(bonuses.get("amount")),
                    "bonus_sum": _integer(bonuses.get("_sum_")),
                    "loyalty": float(row.get("loyalty", 0) or 0),
                    "roa": float(roa.get("_lifetime_", 0) or 0),
                    "first_epoch": _integer(row.get("first_epoch")),
                    "since_epoch": _integer(row.get("since_epoch")),
                    "epoch_count": _integer(row.get("epoch_count")),
                    "comeback_count": _integer(row.get("comeback_count")),
                }
            )
        return sorted(result, key=lambda item: (-item["stake"], item["stake_address"]))

    def delegator_history(self, stake_address: str) -> list[dict[str, Any]]:
        address = str(stake_address).strip()
        result: list[dict[str, Any]] = []
        for epoch, _path, snapshot in self.store.iter_snapshots(include_live=True):
            match = next(
                (
                    row
                    for row in self.store.account_rows(snapshot)
                    if row.get("role") == "delegator"
                    and row.get("stake_address") == address
                ),
                None,
            )
            if match is None:
                continue
            stake = _dict(match.get("stake"))
            rewards = _dict(match.get("rewards"))
            bonuses = _dict(match.get("bonuses"))
            roa = _dict(match.get("ROA"))
            result.append(
                {
                    "epoch": epoch,
                    "stake": _integer(stake.get("_epoch_")),
                    "stake_diff": _integer(stake.get("_diff_")),
                    "rewards": _integer(rewards.get("_epoch_")),
                    "rewards_sum": _integer(rewards.get("_sum_")),
                    "bonus": _integer(bonuses.get("amount")),
                    "bonus_sum": _integer(bonuses.get("_sum_")),
                    "loyalty": float(match.get("loyalty", 0) or 0),
                    "roa": float(roa.get("_lifetime_", 0) or 0),
                }
            )
        result.reverse()
        return result

    def block_rows(self) -> list[dict[str, Any]]:
        return self.browser_data()["blocks"]

    def bonus_rows(self) -> list[dict[str, Any]]:
        return self.browser_data()["bonuses"]
