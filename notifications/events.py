# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Derive notification events from two canonical CspoE snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LOVELACE = 1_000_000


@dataclass(frozen=True)
class Event:
    key: str
    kind: str
    epoch: int
    data: dict[str, Any]


def _rows(snapshot: dict[str, Any], section: str, row_name: str) -> dict[str, dict[str, Any]]:
    obj = snapshot.get(section) if isinstance(snapshot.get(section), dict) else {}
    rows = obj.get(row_name) if isinstance(obj.get(row_name), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        address = str(row.get("stake_address") or "").strip()
        if address:
            out[address] = row
    return out


def _amount(row: dict[str, Any]) -> int:
    stake = row.get("stake") if isinstance(row.get("stake"), dict) else {}
    try:
        return int(stake.get("_epoch_", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _pool_stake(snapshot: dict[str, Any]) -> int:
    pool = snapshot.get("pool") if isinstance(snapshot.get("pool"), dict) else {}
    stake = pool.get("stake") if isinstance(pool.get("stake"), dict) else {}
    try:
        return int(stake.get("_epoch_", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _blocks(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    obj = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), dict) else {}
    rows = obj.get("block") if isinstance(obj.get("block"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        identifier = str(row.get("hash") or row.get("block") or row.get("slot") or f"row-{i}")
        out[identifier] = row
    return out


def _int_nested(obj: dict[str, Any], *keys: str) -> int:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return 0
        cur = cur.get(key)
    try:
        return int(cur or 0)
    except (TypeError, ValueError):
        return 0


def epoch_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return stable end-of-epoch facts for the Telegram summary.

    Rewards are deliberately excluded: Cardano rewards settle later (normally
    N+2) and are notified through a separate settlement event.
    """
    pool = snapshot.get("pool") if isinstance(snapshot.get("pool"), dict) else {}
    delegators = snapshot.get("delegators") if isinstance(snapshot.get("delegators"), dict) else {}
    blocks = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), dict) else {}
    stake = pool.get("stake") if isinstance(pool.get("stake"), dict) else {}
    current_stake = _int_nested(pool, "stake", "_epoch_")
    previous_stake = _int_nested(pool, "stake", "_previous_")
    if previous_stake == 0 and current_stake:
        previous_stake = current_stake - _int_nested(pool, "stake", "_diff_")
    try:
        delegator_count = int(delegators.get("delegsNb", 0) or 0)
    except (TypeError, ValueError):
        delegator_count = 0
    try:
        previous_delegator_count = int(delegators.get("previous_delegsNb", delegator_count) or 0)
    except (TypeError, ValueError):
        previous_delegator_count = delegator_count
    try:
        block_count = int(blocks.get("epoch", 0) or 0)
    except (TypeError, ValueError):
        block_count = 0
    return {
        "closed_epoch": int(snapshot.get("epoch", 0) or 0),
        "blocks": block_count,
        "stake": current_stake,
        "previous_stake": previous_stake,
        "stake_diff": current_stake - previous_stake,
        "delegators": delegator_count,
        "previous_delegators": previous_delegator_count,
        "delegators_diff": delegator_count - previous_delegator_count,
    }


def rewards_settlement_data(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract actually recorded rewards for one settled epoch."""
    total = _int_nested(snapshot, "pool", "rewards", "_epoch_")
    owners = _int_nested(snapshot, "owners", "rewards", "_epoch_")
    delegators = _int_nested(snapshot, "delegators", "rewards", "_epoch_")
    rewarded_accounts = 0
    for section, row_name in (("owners", "owner"), ("delegators", "delegator")):
        obj = snapshot.get(section) if isinstance(snapshot.get(section), dict) else {}
        rows = obj.get(row_name) if isinstance(obj.get(row_name), list) else []
        for row in rows:
            if isinstance(row, dict) and _int_nested(row, "rewards", "_epoch_") > 0:
                rewarded_accounts += 1
    return {
        "settled_epoch": int(snapshot.get("epoch", 0) or 0),
        "pool_rewards": total,
        "owners_rewards": owners,
        "delegators_rewards": delegators,
        "rewarded_accounts": rewarded_accounts,
        "blocks": _int_nested(snapshot, "blocks", "epoch"),
    }


def derive_events(previous: dict[str, Any], current: dict[str, Any], *, stake_threshold_lovelace: int = 0,
                  include_delegator_events: bool = True, include_pool_stake_events: bool = True,
                  include_block_events: bool = True) -> list[Event]:
    epoch = int(current.get("epoch", 0) or 0)
    previous_epoch = int(previous.get("epoch", 0) or 0)
    events: list[Event] = []

    if epoch != previous_epoch:
        events.append(Event(f"epoch:{epoch}", "new_epoch", epoch, {"previous_epoch": previous_epoch, "summary": epoch_summary(previous)}))

    old = _rows(previous, "delegators", "delegator")
    new = _rows(current, "delegators", "delegator")

    if include_delegator_events:
        for address in sorted(new.keys() - old.keys()):
            amount = _amount(new[address])
            events.append(Event(f"delegator_join:{epoch}:{address}", "delegator_join", epoch, {"address": address, "stake": amount}))

        for address in sorted(old.keys() - new.keys()):
            amount = _amount(old[address])
            events.append(Event(f"delegator_leave:{epoch}:{address}", "delegator_leave", epoch, {"address": address, "stake": amount}))

        for address in sorted(old.keys() & new.keys()):
            before = _amount(old[address])
            after = _amount(new[address])
            diff = after - before
            if diff and abs(diff) >= max(0, stake_threshold_lovelace):
                events.append(Event(
                    f"delegator_stake:{epoch}:{address}:{after}",
                    "delegator_stake_change",
                    epoch,
                    {"address": address, "before": before, "after": after, "diff": diff},
                ))

    if include_pool_stake_events:
        before_pool = _pool_stake(previous)
        after_pool = _pool_stake(current)
        pool_diff = after_pool - before_pool
        if pool_diff and abs(pool_diff) >= max(0, stake_threshold_lovelace):
            events.append(Event(
                f"pool_stake:{epoch}:{after_pool}",
                "pool_stake_change",
                epoch,
                {"before": before_pool, "after": after_pool, "diff": pool_diff},
            ))

    if include_block_events:
        old_blocks = _blocks(previous)
        new_blocks = _blocks(current)
        for identifier in sorted(new_blocks.keys() - old_blocks.keys()):
            events.append(Event(f"block:{epoch}:{identifier}", "block", epoch, {"block": new_blocks[identifier]}))

    return events
