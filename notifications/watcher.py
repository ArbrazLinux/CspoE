# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Persistent deduplication and snapshot comparison for Telegram notifications."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .events import Event, derive_events, rewards_settlement_data
from .telegram import TelegramClient
from .templates import render


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON non objet: {path}")
    return value


def _atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class TelegramWatcher:
    def __init__(self, *, ticker: str, token: str, chat_id: str, state_file: Path, threshold_lovelace: int = 0,
                 include_delegator_events: bool = True, include_pool_stake_events: bool = True,
                 include_block_events: bool = True, personal_notifier: Any | None = None) -> None:
        self.ticker = ticker
        self.client = TelegramClient(token, chat_id)
        self.state_file = state_file
        self.threshold_lovelace = threshold_lovelace
        self.include_delegator_events = bool(include_delegator_events)
        self.include_pool_stake_events = bool(include_pool_stake_events)
        self.include_block_events = bool(include_block_events)
        self.personal_notifier = personal_notifier

    def _state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return {"sent": []}
        try:
            return _load(self.state_file)
        except Exception:
            return {"sent": []}

    def run(
        self,
        previous_path: Path,
        current_path: Path,
        *,
        dry_run: bool = False,
        epoch_manager_state_file: Path | None = None,
        epochs_dir: Path | None = None,
    ) -> dict[str, Any]:
        previous = _load(previous_path)
        current = _load(current_path)
        state = self._state()
        sent = set(str(x) for x in state.get("sent", []))
        events = derive_events(previous, current, stake_threshold_lovelace=self.threshold_lovelace,
                               include_delegator_events=self.include_delegator_events,
                               include_pool_stake_events=self.include_pool_stake_events,
                               include_block_events=self.include_block_events)

        rewards_bootstrap = False
        rewards_advanced: list[int] = []
        rewards_suppressed_zero: list[int] = []
        reward_events: list[Event] = []
        latest_settled: int | None = None
        baseline_initialized = bool(state.get("rewards_baseline_initialized", False))
        try:
            prior_settled = int(state.get("last_rewards_settled_epoch")) if baseline_initialized else None
        except (TypeError, ValueError):
            prior_settled = None

        if epoch_manager_state_file and epoch_manager_state_file.is_file() and epochs_dir:
            manager = _load(epoch_manager_state_file)
            raw_latest = manager.get("last_rewards_settled_epoch")
            if raw_latest in (None, "") and isinstance(manager.get("transition"), dict):
                raw_latest = manager["transition"].get("reward_settled_epoch")
            try:
                latest_settled = int(raw_latest)
            except (TypeError, ValueError):
                latest_settled = None

            # Existing installations must not replay rewards that were paid before
            # this notification feature was installed. The first observed settled
            # epoch therefore becomes a silent baseline.
            if latest_settled is not None and not baseline_initialized:
                rewards_bootstrap = True
                if not dry_run:
                    state["rewards_baseline_initialized"] = True
                    state["last_rewards_settled_epoch"] = latest_settled
            elif latest_settled is not None and prior_settled is not None and latest_settled > prior_settled:
                for settled_epoch in range(prior_settled + 1, latest_settled + 1):
                    rewards_advanced.append(settled_epoch)
                    snapshot_path = epochs_dir / f"epoch_{settled_epoch}.json"
                    if not snapshot_path.is_file():
                        continue
                    reward_data = rewards_settlement_data(_load(snapshot_path))
                    # No block/no rewards: advance the settlement cursor silently.
                    if int(reward_data.get("pool_rewards", 0) or 0) <= 0:
                        rewards_suppressed_zero.append(settled_epoch)
                        continue
                    reward_events.append(Event(
                        f"rewards_settled:{settled_epoch}",
                        "rewards_settled",
                        settled_epoch,
                        reward_data,
                    ))
                    if (not dry_run) and self.personal_notifier:
                        self.personal_notifier.notify_rewards(settled_epoch=settled_epoch, snapshot=_load(snapshot_path))
                if not dry_run:
                    state["rewards_baseline_initialized"] = True
                    state["last_rewards_settled_epoch"] = latest_settled

        events.extend(reward_events)
        pending = [event for event in events if event.key not in sent]
        messages = []
        for event in pending:
            text = render(event, ticker=self.ticker)
            messages.append({"key": event.key, "kind": event.kind, "text": text})
            if not dry_run:
                self.client.send_message(text)
                sent.add(event.key)
                state["sent"] = sorted(sent)[-2000:]
                _atomic(self.state_file, state)

        # Persist a baseline/cursor change even when no Telegram message was sent.
        if not dry_run:
            state["sent"] = sorted(sent)[-2000:]
            if latest_settled is not None and (rewards_bootstrap or rewards_advanced):
                _atomic(self.state_file, state)

        return {
            "ok": True,
            "dry_run": dry_run,
            "events_detected": len(events),
            "pending": len(pending),
            "messages": messages,
            "rewards": {
                "latest_settled_epoch": latest_settled,
                "bootstrap": rewards_bootstrap,
                "advanced_epochs": rewards_advanced,
                "suppressed_zero_epochs": rewards_suppressed_zero,
            },
        }
