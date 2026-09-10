# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Near-real-time delegator and pool live-stake watcher for Telegram.

The watcher is notification-only: it reads Blockfrost, owns a separate cursor,
and never mutates canonical CspoE epoch data. Reward compounding is correlated
with canonical CspoE reward archives so automatic reward activation is not
misreported as dozens of manual delegation changes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from core.blockfrost import BlockfrostClient
from .telegram import TelegramClient
from .templates import (render_live_delegator_event, render_live_pool_stake_change,
                        render_grouped_stake_event, render_stake_address_transfer)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


def _i(value: Any) -> int:
    try: return int(value or 0)
    except (TypeError, ValueError): return 0


def _reward_rows(snapshot: dict[str, Any]) -> dict[str, int]:
    """Return positive per-stake rewards for owners + delegators."""
    out: dict[str, int] = {}
    for section, key in (("owners", "owner"), ("delegators", "delegator")):
        parent = snapshot.get(section) if isinstance(snapshot.get(section), dict) else {}
        rows = parent.get(key) if isinstance(parent.get(key), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            addr = str(row.get("stake_address") or "")
            rewards = row.get("rewards") if isinstance(row.get("rewards"), dict) else {}
            amount = _i(rewards.get("_epoch_"))
            if addr and amount > 0:
                out[addr] = amount
    return out


def _pool_reward(snapshot: dict[str, Any]) -> int:
    pool = snapshot.get("pool") if isinstance(snapshot.get("pool"), dict) else {}
    rewards = pool.get("rewards") if isinstance(pool.get("rewards"), dict) else {}
    return max(0, _i(rewards.get("_epoch_")))


class StakeDelegatorWatcher:
    def __init__(self, *, ticker: str, pool_id: str, state_file: Path,
                 blockfrost: BlockfrostClient | None = None,
                 telegram: TelegramClient | None = None,
                 delegator_change_threshold_lovelace: int = 0,
                 pool_change_threshold_lovelace: int = 0,
                 delegator_events_enabled: bool = True,
                 pool_stake_events_enabled: bool = True,
                 group_events_enabled: bool = True,
                 group_tolerance_lovelace: int = 10_000_000,
                 max_group_items: int = 8,
                 max_pages: int = 100, page_size: int = 100,
                 reward_correlation_enabled: bool = True,
                 reward_epoch_offset: int = 3,
                 reward_match_tolerance_lovelace: int = 2_000_000,
                 reward_batch_min_matches: int = 3,
                 epoch_manager_state_file: Path | None = None,
                 epochs_dir: Path | None = None,
                 stake_transfer_enabled: bool = True,
                 stake_transfer_window_seconds: int = 10_800,
                 stake_transfer_tolerance_lovelace: int = 5_000_000,
                 now: Callable[[], float] = time.time, personal_notifier: Any | None = None) -> None:
        if not pool_id:
            raise RuntimeError("BECH32_POOL_ID absent")
        self.ticker=ticker; self.pool_id=pool_id; self.state_file=state_file
        self.blockfrost=blockfrost or BlockfrostClient(pool_id=pool_id)
        self.telegram=telegram
        self.delegator_threshold=max(0,int(delegator_change_threshold_lovelace))
        self.pool_threshold=max(0,int(pool_change_threshold_lovelace))
        self.delegator_events_enabled=bool(delegator_events_enabled)
        self.pool_stake_events_enabled=bool(pool_stake_events_enabled)
        self.group_events_enabled=bool(group_events_enabled)
        self.group_tolerance=max(0,int(group_tolerance_lovelace))
        self.max_group_items=max(1,int(max_group_items))
        self.max_pages=max(1,int(max_pages)); self.page_size=max(1,min(int(page_size),100)); self.now=now
        self.reward_correlation_enabled=bool(reward_correlation_enabled)
        self.reward_epoch_offset=max(2,int(reward_epoch_offset))
        self.reward_match_tolerance=max(0,int(reward_match_tolerance_lovelace))
        self.reward_batch_min_matches=max(2,int(reward_batch_min_matches))
        self.epoch_manager_state_file=epoch_manager_state_file
        self.epochs_dir=epochs_dir
        self.stake_transfer_enabled=bool(stake_transfer_enabled)
        self.stake_transfer_window=max(60,int(stake_transfer_window_seconds))
        self.stake_transfer_tolerance=max(0,int(stake_transfer_tolerance_lovelace))
        self.personal_notifier=personal_notifier

    def _snapshot(self) -> tuple[dict[str,int], int]:
        delegators: dict[str,int] = {}
        for page in range(1,self.max_pages+1):
            rows=self.blockfrost.pool_delegators(self.pool_id,page=page,count=self.page_size,order="asc")
            if not isinstance(rows,list): raise RuntimeError("Réponse Blockfrost pool delegators invalide")
            for row in rows:
                if not isinstance(row,dict): continue
                addr=str(row.get("address") or row.get("stake_address") or "")
                if addr: delegators[addr]=_i(row.get("live_stake") or row.get("stake"))
            if len(rows)<self.page_size: break
        pool=self.blockfrost.pool(self.pool_id)
        live_stake=_i(pool.get("live_stake") if isinstance(pool,dict) else 0)
        if live_stake <= 0 and delegators: live_stake=sum(delegators.values())
        return delegators,live_stake

    def _current_epoch(self) -> int | None:
        try:
            row=self.blockfrost.epoch()
            ep=_i(row.get("epoch") if isinstance(row,dict) else None)
            if ep > 0:
                return ep
        except Exception:
            pass
        if self.epoch_manager_state_file:
            manager=_load_json(self.epoch_manager_state_file)
            for raw in (manager.get("last_collected_epoch"),
                        (manager.get("transition") or {}).get("observed_epoch") if isinstance(manager.get("transition"),dict) else None):
                ep=_i(raw)
                if ep > 0:
                    return ep
        return None

    def _reward_context(self) -> dict[str, Any]:
        base={"eligible":False,"detected":False,"reward_epoch":None,"current_epoch":None,
              "reward_total":0,"reward_accounts":0,"matches":0,"matched_amount":0}
        if not self.reward_correlation_enabled or not self.epochs_dir:
            return base
        current_epoch=self._current_epoch()
        base["current_epoch"]=current_epoch
        if not current_epoch:
            return base
        reward_epoch=int(current_epoch)-self.reward_epoch_offset
        base["reward_epoch"]=reward_epoch
        if reward_epoch < 0:
            return base
        if self.epoch_manager_state_file:
            manager=_load_json(self.epoch_manager_state_file)
            settled=_i(manager.get("last_rewards_settled_epoch"))
            if settled and reward_epoch > settled:
                return base
        snap=_load_json(Path(self.epochs_dir)/f"epoch_{reward_epoch}.json")
        if not snap:
            return base
        rewards=_reward_rows(snap); total=_pool_reward(snap)
        if not rewards or total <= 0:
            return base
        base.update({"eligible":True,"reward_total":total,"reward_accounts":len(rewards),"rewards_by_stake":rewards})
        return base

    def run(self, *, dry_run: bool=False) -> dict[str,Any]:
        state=_load_json(self.state_file)
        current, pool_live=self._snapshot()
        old_pool_id=str(state.get("pool_id") or "")
        initialized=bool(state.get("initialized"))
        pool_changed=bool(initialized and old_pool_id and old_pool_id != self.pool_id)

        baseline = (not initialized) or pool_changed
        if baseline:
            new_state={"initialized":True,"pool_id":self.pool_id,"delegators":current,
                       "pool_live_stake":pool_live,"updated_at":int(self.now())}
            if not dry_run: _atomic_json(self.state_file,new_state)
            return {"ok":True,"bootstrap":True,"pool_changed":pool_changed,
                    "previous_pool_id":old_pool_id or None,"delegators_seen":len(current),
                    "pool_live_stake":pool_live,"pending":0,"messages":[],"state":new_state}

        previous_raw=state.get("delegators") if isinstance(state.get("delegators"),dict) else {}
        previous={str(k):_i(v) for k,v in previous_raw.items()}
        prev_pool=_i(state.get("pool_live_stake"))
        now_ts=int(self.now())

        raw_changes: list[dict[str,Any]]=[]
        for addr in sorted(current.keys()-previous.keys()):
            raw_changes.append({"kind":"join","address":addr,"before":0,"after":current[addr],"raw_diff":current[addr]})
        for addr in sorted(previous.keys()-current.keys()):
            raw_changes.append({"kind":"leave","address":addr,"before":previous[addr],"after":0,"raw_diff":-previous[addr]})
        for addr in sorted(current.keys() & previous.keys()):
            before,after=previous[addr],current[addr]; diff=after-before
            if diff:
                raw_changes.append({"kind":"change","address":addr,"before":before,"after":after,"raw_diff":diff})

        # Stake-address migration correlation. Joins/leaves are held briefly instead
        # of being published immediately. A mutually-best one-to-one match within
        # the configured time and ADA tolerance becomes a single transfer event.
        membership_raw=[r for r in raw_changes if r["kind"] in {"join","leave"}]
        change_rows=[r for r in raw_changes if r["kind"] == "change"]
        pending_raw=state.get("pending_membership") if isinstance(state.get("pending_membership"),list) else []
        pending=[]
        for row in pending_raw:
            if not isinstance(row,dict):
                continue
            kind=str(row.get("kind") or "")
            addr=str(row.get("address") or "")
            if kind not in {"join","leave"} or not addr:
                continue
            pending.append({"kind":kind,"address":addr,"stake":_i(row.get("stake")),"seen_at":_i(row.get("seen_at")) or now_ts})

        transfer_events: list[dict[str,Any]]=[]
        expired_membership: list[dict[str,Any]]=[]
        if self.stake_transfer_enabled:
            present={(str(r.get("kind")),str(r.get("address"))) for r in pending}
            for row in membership_raw:
                sig=(row["kind"],row["address"])
                if sig in present:
                    continue
                stake=row["after"] if row["kind"] == "join" else row["before"]
                pending.append({"kind":row["kind"],"address":row["address"],"stake":stake,"seen_at":now_ts})
                present.add(sig)

            joins=[r for r in pending if r["kind"] == "join"]
            leaves=[r for r in pending if r["kind"] == "leave"]

            def candidates(src: dict[str,Any], others: list[dict[str,Any]]) -> list[tuple[tuple[int,int],dict[str,Any]]]:
                out=[]
                for other in others:
                    if src["address"] == other["address"]:
                        continue
                    age=abs(_i(src["seen_at"])-_i(other["seen_at"]))
                    delta=abs(_i(src["stake"])-_i(other["stake"]))
                    if age <= self.stake_transfer_window and delta <= self.stake_transfer_tolerance:
                        out.append(((delta,age),other))
                out.sort(key=lambda x:x[0])
                return out

            def unique_best(src: dict[str,Any], others: list[dict[str,Any]]) -> dict[str,Any] | None:
                c=candidates(src,others)
                if not c:
                    return None
                if len(c)>1 and c[0][0] == c[1][0]:
                    return None
                return c[0][1]

            used_join=set(); used_leave=set()
            for join in joins:
                leave=unique_best(join,leaves)
                if leave is None:
                    continue
                if unique_best(leave,joins) is not join:
                    continue
                ji=(join["kind"],join["address"],join["seen_at"])
                li=(leave["kind"],leave["address"],leave["seen_at"])
                if ji in used_join or li in used_leave:
                    continue
                used_join.add(ji); used_leave.add(li)
                transfer_events.append({
                    "kind":"transfer",
                    "from_address":leave["address"],"to_address":join["address"],
                    "before":_i(leave["stake"]),"after":_i(join["stake"]),
                    "diff":_i(join["stake"])-_i(leave["stake"]),
                    "age_seconds":abs(_i(join["seen_at"])-_i(leave["seen_at"])),
                })

            matched={("join",e["to_address"]) for e in transfer_events} | {("leave",e["from_address"]) for e in transfer_events}
            remaining=[]
            for row in pending:
                if (row["kind"],row["address"]) in matched:
                    continue
                if now_ts-_i(row["seen_at"]) >= self.stake_transfer_window:
                    if row["kind"] == "join":
                        expired_membership.append({"kind":"join","address":row["address"],"before":0,"after":_i(row["stake"]),"raw_diff":_i(row["stake"]),"diff":_i(row["stake"])})
                    else:
                        expired_membership.append({"kind":"leave","address":row["address"],"before":_i(row["stake"]),"after":0,"raw_diff":-_i(row["stake"]),"diff":-_i(row["stake"])})
                else:
                    remaining.append(row)
            pending=remaining
        else:
            expired_membership=[dict(r, diff=_i(r.get("raw_diff"))) for r in membership_raw]
            pending=[]

        # Reward-compounding correlation only concerns addresses that remain present.
        rc=self._reward_context()
        rewards=rc.get("rewards_by_stake") if isinstance(rc.get("rewards_by_stake"),dict) else {}
        exact_matches=[]
        changed_reward_rows=[]
        if rc.get("eligible"):
            for row in change_rows:
                reward=_i(rewards.get(row["address"]))
                if reward <= 0:
                    continue
                changed_reward_rows.append(row)
                if abs(_i(row["raw_diff"])-reward) <= self.reward_match_tolerance:
                    exact_matches.append(row)
            rc["matches"]=len(exact_matches)
            rc["matched_amount"]=sum(_i(rewards.get(r["address"])) for r in exact_matches)
            rc["detected"] = len(exact_matches) >= min(self.reward_batch_min_matches, max(2,len(changed_reward_rows)))

        reward_component_pool=0
        suppressed_reward_events=0
        events=list(expired_membership)
        for row in change_rows:
            kind=row["kind"]; addr=row["address"]; before=row["before"]; after=row["after"]; raw_diff=_i(row["raw_diff"])
            economic_diff=raw_diff; reward_component=0
            if rc.get("detected"):
                reward=_i(rewards.get(addr))
                if reward > 0:
                    reward_component=reward
                    economic_diff=raw_diff-reward
                    reward_component_pool += reward
                    if abs(economic_diff) < self.delegator_threshold or economic_diff == 0:
                        suppressed_reward_events += 1
                        continue
            if abs(economic_diff) < self.delegator_threshold:
                continue
            row2=dict(row); row2["diff"]=economic_diff; row2["reward_component"]=reward_component
            events.append(row2)

        if rc.get("detected"):
            reward_component_pool=_i(rc.get("reward_total"))
        raw_pool_diff=pool_live-prev_pool
        economic_pool_diff=raw_pool_diff-reward_component_pool
        personal_sent=0
        if (not dry_run) and self.personal_notifier:
            for e in events:
                key=f"personal_stake:{int(self.now())}:{e['address']}:{e['after']}:{e['kind']}"
                personal_sent += self.personal_notifier.notify_stake_change(
                    address=e["address"], before=e["before"], after=e["after"],
                    event_key=key, kind=e["kind"], reward_component=_i(e.get("reward_component")))

        messages=[]
        if self.delegator_events_enabled:
            for t in transfer_events:
                text=render_stake_address_transfer(from_address=t["from_address"],to_address=t["to_address"],
                                                   before=t["before"],after=t["after"],ticker=self.ticker,
                                                   age_seconds=t["age_seconds"])
                m=dict(t);m["text"]=text;messages.append(m)
                if not dry_run and self.telegram:self.telegram.send_message(text)
        else:
            events=[]; transfer_events=[]

        # Never emit a global stake move while a join/leave is waiting for possible
        # transfer correlation, nor on the cycle where a transfer was recognized.
        membership_unresolved=bool(pending)
        pool_event = bool(self.pool_stake_events_enabled and not membership_unresolved and not transfer_events
                          and economic_pool_diff and abs(economic_pool_diff)>=self.pool_threshold)
        event_diff=sum(_i(e.get("diff")) for e in events)
        residual=economic_pool_diff-event_diff
        grouped=bool(self.group_events_enabled and pool_event and events and abs(residual)<=self.group_tolerance)

        if grouped:
            text=render_grouped_stake_event(before=prev_pool,after=pool_live,events=events,
                                            ticker=self.ticker,delegator_count=len(current),
                                            max_items=self.max_group_items,residual=residual,
                                            diff_override=economic_pool_diff, reward_component=reward_component_pool)
            messages.append({"kind":"stake_grouped","before":prev_pool,"after":pool_live,"diff":economic_pool_diff,
                             "raw_diff":raw_pool_diff,"reward_component":reward_component_pool,
                             "delegator_events":events,"residual":residual,"text":text})
            if not dry_run and self.telegram: self.telegram.send_message(text)
        else:
            for e in events:
                text=render_live_delegator_event(kind=e["kind"],address=e["address"],before=e["before"],after=e["after"],
                                                 ticker=self.ticker,diff_override=e.get("diff"),reward_component=e.get("reward_component",0))
                m=dict(e); m["text"]=text; messages.append(m)
                if not dry_run and self.telegram: self.telegram.send_message(text)
            if pool_event:
                text=render_live_pool_stake_change(before=prev_pool,after=pool_live,ticker=self.ticker,
                                                   delegator_count=len(current),diff_override=economic_pool_diff,
                                                   reward_component=reward_component_pool)
                messages.append({"kind":"pool_stake_change","before":prev_pool,"after":pool_live,"diff":economic_pool_diff,
                                 "raw_diff":raw_pool_diff,"reward_component":reward_component_pool,
                                 "residual":residual,"text":text})
                if not dry_run and self.telegram: self.telegram.send_message(text)

        new_state={"initialized":True,"pool_id":self.pool_id,"delegators":current,
                   "pool_live_stake":pool_live,"pending_membership":pending,"updated_at":now_ts}
        if not dry_run: _atomic_json(self.state_file,new_state)
        rc_public={k:v for k,v in rc.items() if k != "rewards_by_stake"}
        rc_public["suppressed_events"]=suppressed_reward_events
        rc_public["pool_reward_neutralized"]=reward_component_pool
        transfer_diag={"enabled":self.stake_transfer_enabled,"window_seconds":self.stake_transfer_window,
                       "tolerance_lovelace":self.stake_transfer_tolerance,"matched":len(transfer_events),
                       "pending_joins":sum(1 for r in pending if r["kind"]=="join"),
                       "pending_leaves":sum(1 for r in pending if r["kind"]=="leave"),
                       "expired":len(expired_membership)}
        return {"ok":True,"bootstrap":False,"pool_changed":False,"delegators_seen":len(current),
                "pool_live_stake":pool_live,"grouped":grouped,"attribution_residual":residual,
                "stake_address_transfer":transfer_diag,"reward_correlation":rc_public,
                "personal_sent":personal_sent,"pending":len(messages),"messages":messages,"state":new_state}
