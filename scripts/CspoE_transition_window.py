#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Poll Blockfrost in the safety window, then commit one reward window.

The systemd timer intentionally runs every day because Blockfrost remains the
source of truth for the observed epoch.  A day without an epoch transition is
therefore a normal successful outcome, not a failed service.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_epoch_manager import CspoEEpochManager
from core.config import settings
from core.projections import refresh_projections

WINDOW_START_SECOND = 21 * 3600 + 35 * 60
WINDOW_DEADLINE_SECOND = 22 * 3600 + 15 * 60


def _emit(payload: dict[str, Any], stream: TextIO) -> None:
    print(json.dumps(payload, ensure_ascii=False), file=stream)


def run_window(
    manager: CspoEEpochManager,
    *,
    now_fn: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    projections_fn: Callable[..., dict[str, Any]] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one daily observation window.

    Dependencies are injectable so the time-window policy can be tested
    offline without sleeping or contacting Blockfrost.
    """

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleep_fn or time.sleep
    projections_fn = projections_fn or refresh_projections
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    state = manager.status().get("state") or {}
    previous_observed = state.get("last_collected_epoch")
    observed_successfully = False
    last_observed: int | None = None
    last_error: str | None = None
    catch_up_completed = False
    waiting_reported = False

    while True:
        now = now_fn()
        seconds = now.hour * 3600 + now.minute * 60 + now.second

        # A manual invocation outside the timer window must never remain asleep
        # for hours.  The systemd timer itself starts exactly at 21:35 UTC.
        if seconds < WINDOW_START_SECOND:
            _emit(
                {
                    "ok": True,
                    "status": "before_window",
                    "at": now.isoformat(),
                    "window_start": "21:35 UTC",
                },
                stdout,
            )
            return 0

        if seconds > WINDOW_DEADLINE_SECOND:
            if catch_up_completed:
                _emit(
                    {
                        "ok": False,
                        "status": "boundary_not_observed_after_catch_up",
                        "at": now.isoformat(),
                        "previous_observed_epoch": previous_observed,
                        "last_observed_epoch": last_observed,
                        "last_error": last_error,
                    },
                    stderr,
                )
                return 1
            if last_error is not None:
                _emit(
                    {
                        "ok": False,
                        "status": "observation_failed_at_deadline",
                        "at": now.isoformat(),
                        "previous_observed_epoch": previous_observed,
                        "last_observed_epoch": last_observed,
                        "error": last_error,
                    },
                    stderr,
                )
                return 1
            if observed_successfully:
                _emit(
                    {
                        "ok": True,
                        "status": "no_new_epoch_in_window",
                        "at": now.isoformat(),
                        "previous_observed_epoch": previous_observed,
                        "observed_epoch": last_observed,
                    },
                    stdout,
                )
                return 0
            _emit(
                {
                    "ok": False,
                    "status": "deadline_reached_without_observation",
                    "at": now.isoformat(),
                    "previous_observed_epoch": previous_observed,
                },
                stderr,
            )
            return 1

        try:
            observed = int(manager.observe_epoch())
            observed_successfully = True
            last_observed = observed
            last_error = None
            if previous_observed is not None and observed <= int(previous_observed):
                if not waiting_reported:
                    _emit(
                        {
                            "ok": True,
                            "status": "waiting_for_new_epoch",
                            "at": now.isoformat(),
                            "previous_observed_epoch": int(previous_observed),
                            "observed_epoch": observed,
                        },
                        stdout,
                    )
                    waiting_reported = True
                sleep_fn(30)
                continue

            waiting_reported = False
            reconciliation = manager.reconcile_reward_window(observed, write=True)
            projections = None
            if reconciliation.get("ok") and reconciliation.get("written"):
                projections = projections_fn(manager.data_root, write=True)
            _emit(
                {
                    "at": now.isoformat(),
                    "previous_observed_epoch": previous_observed,
                    "observed_epoch": observed,
                    "reward_window": reconciliation,
                    "projections": projections,
                },
                stdout,
            )
            if reconciliation.get("ok") and reconciliation.get("written"):
                if not (projections or {}).get("ok", True):
                    return 1
                # A machine that missed an earlier transition can be caught up
                # at 21:35 while the next boundary is still ahead. Keep polling
                # in that case so the 21:45 transition is not skipped.
                if seconds < manager.BOUNDARY_MINUTE * 60:
                    previous_observed = observed
                    catch_up_completed = True
                    _emit(
                        {
                            "ok": True,
                            "status": "catch_up_complete_waiting_for_boundary",
                            "previous_observed_epoch": previous_observed,
                        },
                        stdout,
                    )
                    sleep_fn(30)
                    continue
                return 0
        except Exception as exc:
            last_error = str(exc)
            _emit({"ok": False, "error": last_error}, stderr)
        sleep_fn(30)


def main() -> int:
    pool = os.getenv("BECH32_POOL_ID") or settings.bech32_pool_id
    if not pool:
        print(json.dumps({"ok": False, "error": "Missing BECH32_POOL_ID"}))
        return 2
    manager = CspoEEpochManager(pool)
    return run_window(manager)


if __name__ == "__main__":
    raise SystemExit(main())
