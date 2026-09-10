# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from __future__ import annotations

"""Exact legacy pool_data business contract for CspoE.

The archived output of this module intentionally mirrors one legacy history
entry exactly:
    epoch / pool / owners / delegators / blocks / bonuses

No collection/audit metadata is allowed in the returned snapshot. Such data
belongs in CspoE reports, never in epoch_N.json or pooldata_X_Y.json.

The only intentional business difference from the original engine is the
validated CspoE loyalty value for external delegators. Owner loyalty remains 0
because no separate owner-loyalty rule has been defined.
"""

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Optional

LEGACY_TOP_LEVEL = ("epoch", "pool", "owners", "delegators", "blocks", "bonuses")
LEGACY_BLOCK_KEYS = (
    "time", "height", "hash", "slot", "epoch", "epoch_slot", "size", "tx_count",
    "output", "fees", "block_vrf", "op_cert", "op_cert_counter", "previous_block", "next_block",
)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _addr(row: dict[str, Any]) -> str:
    return str(row.get("stake_address") or row.get("address") or "")


def _bool_string(value: Any) -> str:
    if value in (True, "True", "true", "1", 1):
        return "True"
    return "False"


def loyalty_from_epoch_count(epoch_count: int) -> float:
    return round(min((max(int(epoch_count), 0) / 73.0) * 100.0, 100.0), 4)


def set_roa(epoch_count: int, stake_sum: int, rewards_sum: int, bonus_sum: int) -> tuple[float, float]:
    """Exact legacy setROA formula, with a zero guard for defensive use."""
    epoch_count = int(epoch_count)
    stake_sum = int(stake_sum)
    rewards_sum = int(rewards_sum)
    bonus_sum = int(bonus_sum)
    if epoch_count <= 0 or stake_sum <= 0:
        return 0, 0
    average_stake = float(stake_sum / epoch_count)
    year_count = float(epoch_count / 73)
    if rewards_sum > 0:
        lifetime = round(float(rewards_sum / average_stake * 100 / year_count), 2)
        bonus = round(float((rewards_sum + bonus_sum) / average_stake * 100 / year_count), 2)
    elif bonus_sum > 0:
        lifetime = 0
        bonus = round(float(bonus_sum / average_stake * 100 / year_count), 2)
    else:
        lifetime = 0
        bonus = 0
    return lifetime, bonus


def delegator_rows(snapshot: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    obj = snapshot.get("delegators")
    if isinstance(obj, dict) and isinstance(obj.get("delegator"), list):
        return [x for x in obj["delegator"] if isinstance(x, dict)]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def owner_rows(snapshot: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    obj = snapshot.get("owners")
    if isinstance(obj, dict) and isinstance(obj.get("owner"), list):
        return [x for x in obj["owner"] if isinstance(x, dict)]
    return []


def _row_map(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_addr(x): x for x in rows if _addr(x)}


def scan_last_rows(history_dir: Path, before_epoch: int, start_epoch: int = 0) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Last known category-specific rows before an epoch, used for comeback."""
    last_deleg: dict[str, dict[str, Any]] = {}
    last_owner: dict[str, dict[str, Any]] = {}
    for ep in range(int(start_epoch), int(before_epoch) + 1):
        path = Path(history_dir) / f"epoch_{ep}.json"
        if not path.is_file():
            continue
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in delegator_rows(snap):
            if _addr(row):
                last_deleg[_addr(row)] = copy.deepcopy(row)
        for row in owner_rows(snap):
            if _addr(row):
                last_owner[_addr(row)] = copy.deepcopy(row)
    return last_deleg, last_owner


def _series(previous_obj: dict[str, Any], current: int, *, pool_output_bug: bool = False) -> dict[str, int]:
    prev = _int(previous_obj.get("_epoch_"), 0)
    diff = int(current) - prev
    total = _int(previous_obj.get("_sum_"), 0) + int(current)
    mx = max(_int(previous_obj.get("_lifetime_max_"), 0), int(current))
    old_min = _int(previous_obj.get("_lifetime_min_"), 0)
    mn = int(current) if old_min == 0 else min(old_min, int(current))
    inputs = _int(previous_obj.get("_inputs_sum_"), 0)
    outputs = _int(previous_obj.get("_outputs_sum_"), 0)
    if diff > 0:
        inputs += diff
    elif diff < 0 and not pool_output_bug:
        outputs += diff
    # pool_output_bug intentionally reproduces legacy:
    # elif (pool_stake < 0), which never fires for a normal positive pool stake.
    return {
        "_epoch_": int(current),
        "_previous_": prev,
        "_diff_": diff,
        "_sum_": total,
        "_lifetime_max_": mx,
        "_lifetime_min_": mn,
        "_inputs_sum_": inputs,
        "_outputs_sum_": outputs,
    }



def _legacy_aggregate_minmax(previous_max: int, previous_min: int, current: int) -> tuple[int, int]:
    """Exact legacy aggregate min/max update.

    The original engine used ``if current > max`` followed by ``elif min == 0
    or current < min``. Therefore an aggregate minimum can intentionally remain
    zero while successive epochs keep setting new maxima. This behaviour is
    part of the historical pool_data contract and must not be normalised.
    """
    mx = int(previous_max)
    mn = int(previous_min)
    cur = int(current)
    if cur > mx:
        mx = cur
    elif cur < mn or mn == 0:
        mn = cur
    return mx, mn


def _awards_index(awards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for award in awards:
        if not isinstance(award, dict):
            continue
        address = str(award.get("address") or award.get("stake_address") or "")
        if address:
            out[address] = award
    return out


def _delegator_row(
    *, address: str, current_stake: int, current_reward: int, epoch: int,
    previous_row: Optional[dict[str, Any]], last_row: Optional[dict[str, Any]],
    award: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    if previous_row is not None:
        base = previous_row
        first_epoch = _int(base.get("first_epoch"), _int(base.get("since_epoch"), epoch))
        since_epoch = _int(base.get("since_epoch"), first_epoch)
        epoch_count = _int(base.get("epoch_count"), 0) + 1
        comeback = _bool_string(base.get("comeback"))
        comeback_count = _int(base.get("comeback_count"), 0)
        is_back = False
    elif last_row is not None:
        base = last_row
        first_epoch = _int(base.get("first_epoch"), _int(base.get("since_epoch"), epoch))
        since_epoch = int(epoch)
        epoch_count = _int(base.get("epoch_count"), 0) + 1
        comeback = "True"
        comeback_count = _int(base.get("comeback_count"), 0) + 1
        is_back = True
    else:
        base = {}
        first_epoch = int(epoch)
        since_epoch = int(epoch)
        epoch_count = 1
        comeback = "False"
        comeback_count = 0
        is_back = False

    prev_stake = base.get("stake") if isinstance(base.get("stake"), dict) else {}
    stake = _series(prev_stake, current_stake)
    prev_rewards = base.get("rewards") if isinstance(base.get("rewards"), dict) else {}
    rewards = {
        "_epoch_": int(current_reward),
        "_sum_": _int(prev_rewards.get("_sum_"), 0) + int(current_reward),
    }
    prev_bonus = base.get("bonuses") if isinstance(base.get("bonuses"), dict) else {}
    award = award if isinstance(award, dict) else {}
    bonus_amount = _int(award.get("amount", award.get("bonus_amount", 0)), 0)
    assets = copy.deepcopy(award.get("assets") if isinstance(award.get("assets"), list) else [])
    bonuses = {
        "amount": bonus_amount,
        "assets": assets,
        "_sum_": _int(prev_bonus.get("_sum_"), 0) + bonus_amount,
    }
    lifetime, with_bonus = set_roa(epoch_count, stake["_sum_"], rewards["_sum_"], bonuses["_sum_"])
    prev_roa = base.get("ROA") if isinstance(base.get("ROA"), dict) else {}
    roa = {
        "_lifetime_": lifetime,
        "_max_": max(prev_roa.get("_max_", 0) if isinstance(prev_roa.get("_max_", 0), (int, float)) else 0, lifetime),
        "_bonuses_included_": with_bonus,
    }
    row = {
        "stake_address": address,
        "first_epoch": first_epoch,
        "since_epoch": since_epoch,
        "epoch_count": epoch_count,
        "loyalty": loyalty_from_epoch_count(epoch_count),
        "comeback": comeback,
        "comeback_count": comeback_count,
        "stake": stake,
        "rewards": rewards,
        "ROA": roa,
        "bonuses": bonuses,
    }
    return row, is_back


def _owner_row(
    *, address: str, current_stake: int, current_reward: int, epoch: int,
    previous_row: Optional[dict[str, Any]], last_row: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    if previous_row is not None:
        base = previous_row
        first_epoch = _int(base.get("first_epoch"), _int(base.get("since_epoch"), epoch))
        since_epoch = _int(base.get("since_epoch"), first_epoch)
        epoch_count = _int(base.get("epoch_count"), 0) + 1
        comeback = _bool_string(base.get("comeback"))
        comeback_count = _int(base.get("comeback_count"), 0)
        is_back = False
    elif last_row is not None:
        base = last_row
        first_epoch = _int(base.get("first_epoch"), _int(base.get("since_epoch"), epoch))
        since_epoch = int(epoch)
        epoch_count = _int(base.get("epoch_count"), 0) + 1
        comeback = "True"
        comeback_count = _int(base.get("comeback_count"), 0) + 1
        is_back = True
    else:
        base = {}
        first_epoch = int(epoch)
        since_epoch = int(epoch)
        epoch_count = 1
        comeback = "False"
        comeback_count = 0
        is_back = False
    stake = _series(base.get("stake") if isinstance(base.get("stake"), dict) else {}, current_stake)
    prev_rewards = base.get("rewards") if isinstance(base.get("rewards"), dict) else {}
    rewards = {"_epoch_": int(current_reward), "_sum_": _int(prev_rewards.get("_sum_"), 0) + int(current_reward)}
    lifetime, _ = set_roa(epoch_count, stake["_sum_"], rewards["_sum_"], 0)
    prev_roa = base.get("ROA") if isinstance(base.get("ROA"), dict) else {}
    row = {
        "stake_address": address,
        "first_epoch": first_epoch,
        "since_epoch": since_epoch,
        "epoch_count": epoch_count,
        "loyalty": 0,
        "comeback": comeback,
        "comeback_count": comeback_count,
        "stake": stake,
        "rewards": rewards,
        "ROA": {"_lifetime_": lifetime, "_max_": max(prev_roa.get("_max_", 0) if isinstance(prev_roa.get("_max_", 0), (int, float)) else 0, lifetime)},
    }
    return row, is_back


def _aggregate_delegators(rows: list[dict[str, Any]], previous: dict[str, Any], epoch: int, start_epoch: int, back_count: int) -> dict[str, Any]:
    prev = previous.get("delegators") if isinstance(previous.get("delegators"), dict) else {}
    current_stake = sum(_int(x["stake"]["_epoch_"]) for x in rows)
    current_rewards = sum(_int(x["rewards"]["_epoch_"]) for x in rows)
    cumulative_bonus = sum(_int(x["bonuses"]["_sum_"]) for x in rows)
    stake = _series(prev.get("stake") if isinstance(prev.get("stake"), dict) else {}, current_stake)
    stake["_biggest_ever_"] = max(
        _int((prev.get("stake") or {}).get("_biggest_ever_"), 0) if isinstance(prev.get("stake"), dict) else 0,
        max((_int(x["stake"]["_epoch_"]) for x in rows), default=0),
    )
    prev_rewards = prev.get("rewards") if isinstance(prev.get("rewards"), dict) else {}
    rewards = {"_epoch_": current_rewards, "_sum_": _int(prev_rewards.get("_sum_"), 0) + current_rewards}
    pool_epoch_count = max(1, int(epoch) - int(start_epoch) + 1)
    lifetime, with_bonus = set_roa(pool_epoch_count, stake["_sum_"], rewards["_sum_"], cumulative_bonus)
    prev_roa = prev.get("ROA") if isinstance(prev.get("ROA"), dict) else {}
    n = len(rows)
    pn = _int(prev.get("delegsNb"), 0)
    mx, mn = _legacy_aggregate_minmax(
        _int(prev.get("lifetime_max_delegsNb"), 0),
        _int(prev.get("lifetime_min_delegsNb"), 0),
        n,
    )
    stake_max, stake_min = _legacy_aggregate_minmax(
        _int((prev.get("stake") or {}).get("_lifetime_max_"), 0) if isinstance(prev.get("stake"), dict) else 0,
        _int((prev.get("stake") or {}).get("_lifetime_min_"), 0) if isinstance(prev.get("stake"), dict) else 0,
        current_stake,
    )
    stake["_lifetime_max_"] = stake_max
    stake["_lifetime_min_"] = stake_min
    return {
        "delegsNb": n,
        "previous_delegsNb": pn,
        "lifetime_max_delegsNb": mx,
        "lifetime_min_delegsNb": mn,
        "back_delegs": int(back_count),
        "back_delegs_sum": _int(prev.get("back_delegs_sum"), 0) + int(back_count),
        "stake": stake,
        "rewards": rewards,
        "ROA": {
            "_lifetime_": lifetime,
            "_max_": max(prev_roa.get("_max_", 0) if isinstance(prev_roa.get("_max_", 0), (int, float)) else 0, lifetime),
            "_bonuses_included_": with_bonus,
        },
        "delegator": rows,
    }


def _aggregate_owners(rows: list[dict[str, Any]], previous: dict[str, Any], epoch: int, start_epoch: int, back_count: int) -> dict[str, Any]:
    prev = previous.get("owners") if isinstance(previous.get("owners"), dict) else {}
    current_stake = sum(_int(x["stake"]["_epoch_"]) for x in rows)
    current_rewards = sum(_int(x["rewards"]["_epoch_"]) for x in rows)
    pledge = _series(prev.get("pledge") if isinstance(prev.get("pledge"), dict) else {}, current_stake)
    pledge["_biggest_ever_"] = max(
        _int((prev.get("pledge") or {}).get("_biggest_ever_"), 0) if isinstance(prev.get("pledge"), dict) else 0,
        max((_int(x["stake"]["_epoch_"]) for x in rows), default=0),
    )
    prev_rewards = prev.get("rewards") if isinstance(prev.get("rewards"), dict) else {}
    rewards = {"_epoch_": current_rewards, "_sum_": _int(prev_rewards.get("_sum_"), 0) + current_rewards}
    pool_epoch_count = max(1, int(epoch) - int(start_epoch) + 1)
    lifetime, with_bonus = set_roa(pool_epoch_count, pledge["_sum_"], rewards["_sum_"], 0)
    prev_roa = prev.get("ROA") if isinstance(prev.get("ROA"), dict) else {}
    n = len(rows)
    pn = _int(prev.get("ownersNb"), 0)
    mx, mn = _legacy_aggregate_minmax(
        _int(prev.get("lifetime_max_ownersNb"), 0),
        _int(prev.get("lifetime_min_ownersNb"), 0),
        n,
    )
    pledge_max, pledge_min = _legacy_aggregate_minmax(
        _int((prev.get("pledge") or {}).get("_lifetime_max_"), 0) if isinstance(prev.get("pledge"), dict) else 0,
        _int((prev.get("pledge") or {}).get("_lifetime_min_"), 0) if isinstance(prev.get("pledge"), dict) else 0,
        current_stake,
    )
    pledge["_lifetime_max_"] = pledge_max
    pledge["_lifetime_min_"] = pledge_min
    return {
        "ownersNb": n,
        "previous_ownersNb": pn,
        "lifetime_max_ownersNb": mx,
        "lifetime_min_ownersNb": mn,
        "back_owners": int(back_count),
        "back_owners_sum": _int(prev.get("back_owners_sum"), 0) + int(back_count),
        "pledge": pledge,
        "rewards": rewards,
        "ROA": {
            "_lifetime_": lifetime,
            "_max_": max(prev_roa.get("_max_", 0) if isinstance(prev_roa.get("_max_", 0), (int, float)) else 0, lifetime),
            "_bonuses_included_": with_bonus,
        },
        "owner": rows,
    }


def canonical_block(raw: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "time": ("time", "block_time"),
        "height": ("height", "block_height"),
        "hash": ("hash", "block_hash"),
        "slot": ("slot", "abs_slot"),
        "epoch": ("epoch", "epoch_no"),
        "epoch_slot": ("epoch_slot",),
        "size": ("size",),
        "tx_count": ("tx_count",),
        "output": ("output",),
        "fees": ("fees",),
        "block_vrf": ("block_vrf",),
        "op_cert": ("op_cert",),
        "op_cert_counter": ("op_cert_counter",),
        "previous_block": ("previous_block",),
        "next_block": ("next_block",),
    }
    out: dict[str, Any] = {}
    for key in LEGACY_BLOCK_KEYS:
        value = None
        for src in aliases[key]:
            if src in raw:
                value = raw.get(src)
                break
        if key in ("output", "fees"):
            # Historical Blockfrost returned decimal strings and the legacy
            # JSON contains "0" for the old empty/zero values.
            if value in (None, ""):
                value = "0"
            else:
                value = str(value)
        elif value is None:
            value = ""
        out[key] = value
    return out


def _blocks(previous: dict[str, Any], raw_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    prev = previous.get("blocks") if isinstance(previous.get("blocks"), dict) else {}
    block_rows = [canonical_block(x) for x in raw_blocks if isinstance(x, dict)]
    n = len(block_rows)
    return {
        "epoch": n,
        "total_blocks": _int(prev.get("total_blocks"), 0) + n,
        "lifetime_max": max(_int(prev.get("lifetime_max"), 0), n),
        "block": block_rows,
    }


def _top_bonus(previous: dict[str, Any], awards: list[dict[str, Any]]) -> dict[str, Any]:
    prev = previous.get("bonuses") if isinstance(previous.get("bonuses"), dict) else {}
    amount = 0
    awarded: list[dict[str, Any]] = []
    asset_order: list[str] = []
    asset_amounts: dict[str, int] = {}
    asset_fingerprints: dict[str, str] = {}
    for award in awards:
        if not isinstance(award, dict):
            continue
        address = str(award.get("address") or award.get("stake_address") or "")
        bonus_amount = _int(award.get("amount", award.get("bonus_amount", 0)), 0)
        assets = copy.deepcopy(award.get("assets") if isinstance(award.get("assets"), list) else [])
        if not address:
            continue
        amount += bonus_amount
        awarded.append({"stake_address": address, "bonus_amount": bonus_amount, "assets": assets})
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if not name:
                continue
            if name not in asset_amounts:
                asset_order.append(name)
                asset_amounts[name] = 0
                asset_fingerprints[name] = str(asset.get("fingerprint") or "")
            asset_amounts[name] += _int(asset.get("amount"), 0)
    assets_out = [
        {"name": name, "amount": asset_amounts[name], "fingerprint": asset_fingerprints[name]}
        for name in asset_order
    ]
    return {
        "amount": amount,
        "_sum_": _int(prev.get("_sum_"), 0) + amount,
        "awarded_delegators": awarded,
        "assets": assets_out,
    }


def _pool(previous: dict[str, Any], owners: dict[str, Any], delegators: dict[str, Any], epoch: int, start_epoch: int, *, first_gone_legacy_bug: bool = False) -> dict[str, Any]:
    prev = previous.get("pool") if isinstance(previous.get("pool"), dict) else {}
    total_stake = _int(owners["pledge"]["_epoch_"]) + _int(delegators["stake"]["_epoch_"])
    total_rewards = _int(owners["rewards"]["_epoch_"]) + _int(delegators["rewards"]["_epoch_"])
    prev_stake = prev.get("stake") if isinstance(prev.get("stake"), dict) else {}
    stake = _series(prev_stake, total_stake, pool_output_bug=True)
    pool_max, pool_min = _legacy_aggregate_minmax(
        _int(prev_stake.get("_lifetime_max_"), 0),
        _int(prev_stake.get("_lifetime_min_"), 0),
        total_stake,
    )
    stake["_lifetime_max_"] = pool_max
    stake["_lifetime_min_"] = pool_min
    prev_rewards = prev.get("rewards") if isinstance(prev.get("rewards"), dict) else {}
    rewards = {"_epoch_": total_rewards, "_sum_": _int(prev_rewards.get("_sum_"), 0) + total_rewards}
    prev_rows = _row_map(delegator_rows(previous))
    cur_rows = _row_map(delegators["delegator"])
    gone = [row for address, row in prev_rows.items() if address not in cur_rows]
    # Legacy checkGoneAndLost used `while (i > 0)`, so the very first record
    # ever stored at index 0 was never counted. Preserve that one-time quirk.
    effective_gone = gone[1:] if first_gone_legacy_bug and gone else gone
    lost_n = len(effective_gone)
    lost_stake = sum(_int((x.get("stake") or {}).get("_epoch_"), 0) for x in effective_gone)
    prev_lost = prev.get("lost") if isinstance(prev.get("lost"), dict) else {}
    lost = {
        "lost_delegs_nb": lost_n,
        "lost_delegs_sum": _int(prev_lost.get("lost_delegs_sum"), 0) + lost_n,
        "lost_stake": lost_stake,
        "lost_stake_sum": _int(prev_lost.get("lost_stake_sum"), 0) + lost_stake,
    }
    pool_epoch_count = max(1, int(epoch) - int(start_epoch) + 1)
    lifetime, _ = set_roa(pool_epoch_count, stake["_sum_"], rewards["_sum_"], 0)
    prev_roa = prev.get("ROA") if isinstance(prev.get("ROA"), dict) else {}
    return {
        "stake": stake,
        "rewards": rewards,
        "lost": lost,
        "ROA": {"_lifetime_": lifetime, "_max_": max(prev_roa.get("_max_", 0) if isinstance(prev_roa.get("_max_", 0), (int, float)) else 0, lifetime)},
    }


def build_legacy_snapshot(
    *, epoch: int, previous: dict[str, Any], all_stakes: list[dict[str, Any]],
    owner_addresses: list[str], rewards_by_stake: dict[str, int], blocks: list[dict[str, Any]],
    awards: list[dict[str, Any]], last_delegator_rows: Optional[dict[str, dict[str, Any]]] = None,
    last_owner_rows: Optional[dict[str, dict[str, Any]]] = None, start_epoch: int = 0,
    first_gone_legacy_bug: bool = False,
) -> dict[str, Any]:
    """Build the exact archived legacy snapshot for one epoch."""
    previous = previous if isinstance(previous, dict) else {}
    last_delegator_rows = last_delegator_rows or {}
    last_owner_rows = last_owner_rows or {}
    owner_set = set(map(str, owner_addresses or []))
    prev_deleg_map = _row_map(delegator_rows(previous))
    prev_owner_map = _row_map(owner_rows(previous))
    awards_by_addr = _awards_index(awards)

    current_deleg: list[dict[str, Any]] = []
    current_owner: list[dict[str, Any]] = []
    back_delegs = 0
    back_owners = 0

    # Legacy setDelegsIndex followed Blockfrost holder-list order, while
    # setOwnersIndex followed OWNERS_STAKE_ADDRESS order. Preserve both.
    stake_by_address: dict[str, dict[str, Any]] = {}
    for raw in all_stakes:
        if not isinstance(raw, dict):
            continue
        address = _addr(raw)
        if not address:
            continue
        stake_by_address[address] = raw
        if address in owner_set:
            continue
        current_stake = _int(raw.get("amount"), 0)
        current_reward = _int(rewards_by_stake.get(address), 0)
        row, is_back = _delegator_row(
            address=address, current_stake=current_stake, current_reward=current_reward, epoch=epoch,
            previous_row=prev_deleg_map.get(address), last_row=last_delegator_rows.get(address),
            award=awards_by_addr.get(address),
        )
        current_deleg.append(row)
        back_delegs += int(is_back)

    for address in map(str, owner_addresses or []):
        raw = stake_by_address.get(address)
        if not isinstance(raw, dict):
            continue
        current_stake = _int(raw.get("amount"), 0)
        current_reward = _int(rewards_by_stake.get(address), 0)
        row, is_back = _owner_row(
            address=address, current_stake=current_stake, current_reward=current_reward, epoch=epoch,
            previous_row=prev_owner_map.get(address), last_row=last_owner_rows.get(address),
        )
        current_owner.append(row)
        back_owners += int(is_back)

    owners = _aggregate_owners(current_owner, previous, epoch, start_epoch, back_owners)
    delegators = _aggregate_delegators(current_deleg, previous, epoch, start_epoch, back_delegs)
    # Full-history replay can explicitly reproduce the one-time legacy
    # checkGoneAndLost index-0 quirk. Production continuation from the
    # Production reconstruction leaves this historical compatibility switch off.
    pool = _pool(
        previous, owners, delegators, epoch, start_epoch,
        first_gone_legacy_bug=bool(first_gone_legacy_bug),
    )
    block_obj = _blocks(previous, blocks)
    bonus_obj = _top_bonus(previous, awards)

    return {
        "epoch": int(epoch),
        "pool": pool,
        "owners": owners,
        "delegators": delegators,
        "blocks": block_obj,
        "bonuses": bonus_obj,
    }


def validate_exact_legacy_shape(
    snapshot: dict[str, Any],
    *,
    allow_loyalty: bool = True,
    expected_epoch: Optional[int] = None,
) -> list[str]:
    """Validate the exact legacy shape plus identity and aggregate invariants."""
    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return [f"snapshot must be dict, got {type(snapshot).__name__}"]
    if type(snapshot.get("epoch")) is not int:
        errors.append("epoch must be int")
    elif expected_epoch is not None and snapshot["epoch"] != int(expected_epoch):
        errors.append(
            f"epoch value must be {int(expected_epoch)}, got {snapshot['epoch']}"
        )
    if list(snapshot.keys()) != list(LEGACY_TOP_LEVEL):
        errors.append(f"top-level keys must be exactly {list(LEGACY_TOP_LEVEL)}, got {list(snapshot.keys())}")
    expected = {
        "pool": ["stake", "rewards", "lost", "ROA"],
        "owners": ["ownersNb", "previous_ownersNb", "lifetime_max_ownersNb", "lifetime_min_ownersNb", "back_owners", "back_owners_sum", "pledge", "rewards", "ROA", "owner"],
        "delegators": ["delegsNb", "previous_delegsNb", "lifetime_max_delegsNb", "lifetime_min_delegsNb", "back_delegs", "back_delegs_sum", "stake", "rewards", "ROA", "delegator"],
        "blocks": ["epoch", "total_blocks", "lifetime_max", "block"],
        "bonuses": ["amount", "_sum_", "awarded_delegators", "assets"],
    }
    for section, keys in expected.items():
        obj = snapshot.get(section)
        if not isinstance(obj, dict):
            errors.append(f"{section} must be dict")
        elif list(obj.keys()) != keys:
            errors.append(f"{section} keys differ: {list(obj.keys())}")
    owner_keys = ["stake_address", "first_epoch", "since_epoch", "epoch_count", "loyalty", "comeback", "comeback_count", "stake", "rewards", "ROA"]
    deleg_keys = owner_keys + ["bonuses"]
    for row in owner_rows(snapshot):
        if list(row.keys()) != owner_keys:
            errors.append(f"owner row keys differ for {_addr(row)}: {list(row.keys())}")
        if not isinstance(row.get("comeback"), str):
            errors.append(f"owner {_addr(row)} comeback must be legacy string")
    series8 = ["_epoch_", "_previous_", "_diff_", "_sum_", "_lifetime_max_", "_lifetime_min_", "_inputs_sum_", "_outputs_sum_"]
    series9 = series8 + ["_biggest_ever_"]
    nested_expected = {
        "pool.stake": series8, "pool.rewards": ["_epoch_", "_sum_"],
        "pool.lost": ["lost_delegs_nb", "lost_delegs_sum", "lost_stake", "lost_stake_sum"],
        "pool.ROA": ["_lifetime_", "_max_"],
        "owners.pledge": series9, "owners.rewards": ["_epoch_", "_sum_"],
        "owners.ROA": ["_lifetime_", "_max_", "_bonuses_included_"],
        "delegators.stake": series9, "delegators.rewards": ["_epoch_", "_sum_"],
        "delegators.ROA": ["_lifetime_", "_max_", "_bonuses_included_"],
    }
    for path, keys in nested_expected.items():
        cur = snapshot
        for part in path.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if not isinstance(cur, dict) or list(cur.keys()) != keys:
            errors.append(f"{path} keys differ: {list(cur.keys()) if isinstance(cur, dict) else type(cur).__name__}")
    for row in owner_rows(snapshot):
        for key, keys in (("stake", series8), ("rewards", ["_epoch_", "_sum_"]), ("ROA", ["_lifetime_", "_max_"])):
            obj = row.get(key)
            if not isinstance(obj, dict) or list(obj.keys()) != keys:
                errors.append(f"owner {_addr(row)} {key} keys differ")
    for row in delegator_rows(snapshot):
        if list(row.keys()) != deleg_keys:
            errors.append(f"delegator row keys differ for {_addr(row)}: {list(row.keys())}")
        if not isinstance(row.get("comeback"), str):
            errors.append(f"delegator {_addr(row)} comeback must be legacy string")
        if "deleg_epochCount" in row:
            errors.append(f"delegator {_addr(row)} contains non-legacy deleg_epochCount")
        for key, keys in (("stake", series8), ("rewards", ["_epoch_", "_sum_"]), ("ROA", ["_lifetime_", "_max_", "_bonuses_included_"]), ("bonuses", ["amount", "assets", "_sum_"])):
            obj = row.get(key)
            if not isinstance(obj, dict) or list(obj.keys()) != keys:
                errors.append(f"delegator {_addr(row)} {key} keys differ")

    owners_obj = snapshot.get("owners") if isinstance(snapshot.get("owners"), dict) else {}
    delegators_obj = (
        snapshot.get("delegators") if isinstance(snapshot.get("delegators"), dict) else {}
    )
    raw_owners = owners_obj.get("owner")
    raw_delegators = delegators_obj.get("delegator")
    if isinstance(raw_owners, list):
        if any(not isinstance(row, dict) for row in raw_owners):
            errors.append("owners.owner contains a non-dict row")
        if type(owners_obj.get("ownersNb")) is not int or owners_obj.get("ownersNb") != len(raw_owners):
            errors.append("owners.ownersNb does not match owners.owner length")
    if isinstance(raw_delegators, list):
        if any(not isinstance(row, dict) for row in raw_delegators):
            errors.append("delegators.delegator contains a non-dict row")
        if (
            type(delegators_obj.get("delegsNb")) is not int
            or delegators_obj.get("delegsNb") != len(raw_delegators)
        ):
            errors.append("delegators.delegsNb does not match delegators.delegator length")

    owner_addresses = [_addr(row) for row in owner_rows(snapshot)]
    delegator_addresses = [_addr(row) for row in delegator_rows(snapshot)]
    if any(not address for address in owner_addresses):
        errors.append("owners.owner contains an empty stake_address")
    if any(not address for address in delegator_addresses):
        errors.append("delegators.delegator contains an empty stake_address")
    if len(owner_addresses) != len(set(owner_addresses)):
        errors.append("owners.owner contains duplicate stake_address values")
    if len(delegator_addresses) != len(set(delegator_addresses)):
        errors.append("delegators.delegator contains duplicate stake_address values")
    if set(owner_addresses) & set(delegator_addresses):
        errors.append("a stake_address cannot be both owner and delegator")

    try:
        owner_stake = sum(_int(row["stake"]["_epoch_"]) for row in owner_rows(snapshot))
        delegator_stake = sum(
            _int(row["stake"]["_epoch_"]) for row in delegator_rows(snapshot)
        )
        owner_reward = sum(
            _int(row["rewards"]["_epoch_"]) for row in owner_rows(snapshot)
        )
        delegator_reward = sum(
            _int(row["rewards"]["_epoch_"]) for row in delegator_rows(snapshot)
        )
        if _int(owners_obj["pledge"]["_epoch_"]) != owner_stake:
            errors.append("owners.pledge._epoch_ does not match owner rows")
        if _int(delegators_obj["stake"]["_epoch_"]) != delegator_stake:
            errors.append("delegators.stake._epoch_ does not match delegator rows")
        if _int(owners_obj["rewards"]["_epoch_"]) != owner_reward:
            errors.append("owners.rewards._epoch_ does not match owner rows")
        if _int(delegators_obj["rewards"]["_epoch_"]) != delegator_reward:
            errors.append("delegators.rewards._epoch_ does not match delegator rows")
        pool = snapshot["pool"]
        if _int(pool["stake"]["_epoch_"]) != owner_stake + delegator_stake:
            errors.append("pool.stake._epoch_ does not match owners + delegators")
        if _int(pool["rewards"]["_epoch_"]) != owner_reward + delegator_reward:
            errors.append("pool.rewards._epoch_ does not match owners + delegators")
        if _int(pool["rewards"]["_sum_"]) != (
            _int(owners_obj["rewards"]["_sum_"])
            + _int(delegators_obj["rewards"]["_sum_"])
        ):
            errors.append("pool.rewards._sum_ does not match owners + delegators")
        blocks = snapshot["blocks"]
        if not isinstance(blocks["block"], list) or blocks["epoch"] != len(blocks["block"]):
            errors.append("blocks.epoch does not match blocks.block length")
    except (KeyError, TypeError):
        # Detailed structural errors above remain the authoritative diagnosis.
        pass
    return errors


def awards_for_epoch(awards_file: Path, epoch: int) -> list[dict[str, Any]]:
    """Return operator-defined awards, treating no file/no content as none.

    Bonus history is local operator data, not chain evidence.  A public CspoE
    installation must therefore work without it.  Malformed non-empty data is
    still rejected so a typo can never silently erase configured bonuses.
    """
    path = Path(awards_file)
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("awards file must contain a JSON list")
    for item in data:
        if isinstance(item, dict) and _int(item.get("epoch"), -1) == int(epoch):
            rows = item.get("awards")
            if not isinstance(rows, list):
                raise ValueError(f"awards for epoch {epoch} must be a list")
            return copy.deepcopy(rows)
    return []
