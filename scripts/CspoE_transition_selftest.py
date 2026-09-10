#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline acceptance tests for the daily systemd transition window."""
from __future__ import annotations

import io
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The policy test never performs HTTP. Keep it runnable in packaging
# environments where the production dependency has not been installed yet.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = type("Session", (), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    sys.modules["requests"] = requests_stub

from core.version import ENGINE_VERSION
from scripts.CspoE_transition_window import run_window


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 8, 29, hour, minute, second, tzinfo=timezone.utc)


def clock(*values: datetime):
    pending = iter(values)
    return lambda: next(pending)


class FakeManager:
    BOUNDARY_MINUTE = 21 * 60 + 45

    def __init__(self, previous: int, observations: list[int | Exception]) -> None:
        self.previous = previous
        self.observations = iter(observations)
        self.observe_calls = 0
        self.reconciled: list[tuple[int, bool]] = []
        self.data_root = Path("/tmp/cspoe-transition-selftest")

    def status(self) -> dict[str, Any]:
        return {"state": {"last_collected_epoch": self.previous}}

    def observe_epoch(self) -> int:
        self.observe_calls += 1
        value = next(self.observations)
        if isinstance(value, Exception):
            raise value
        return value

    def reconcile_reward_window(self, epoch: int, *, write: bool) -> dict[str, Any]:
        self.reconciled.append((epoch, write))
        return {"ok": True, "written": True, "observed_epoch": epoch}


def execute(manager: FakeManager, *times: datetime) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    result = run_window(
        manager,
        now_fn=clock(*times),
        sleep_fn=lambda _seconds: None,
        projections_fn=lambda _root, **_kwargs: {"ok": True},
        stdout=stdout,
        stderr=stderr,
    )
    output_rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
    error_rows = [json.loads(line) for line in stderr.getvalue().splitlines()]
    return result, output_rows, error_rows


def main() -> int:
    before = FakeManager(652, [])
    code, rows, errors = execute(before, at(20, 0))
    assert code == 0 and rows[-1]["status"] == "before_window" and not errors
    assert before.observe_calls == 0

    unchanged = FakeManager(652, [652])
    code, rows, errors = execute(unchanged, at(21, 35), at(22, 15, 1))
    assert code == 0 and rows[-1]["status"] == "no_new_epoch_in_window"
    assert unchanged.reconciled == [] and not errors

    transitioned = FakeManager(652, [652, 653])
    code, rows, errors = execute(transitioned, at(21, 35), at(21, 45))
    assert code == 0 and transitioned.reconciled == [(653, True)] and not errors
    assert rows[-1]["observed_epoch"] == 653

    unavailable = FakeManager(652, [RuntimeError("Blockfrost unavailable")])
    code, _rows, errors = execute(unavailable, at(21, 35), at(22, 15, 1))
    assert code == 1 and errors[-1]["status"] == "observation_failed_at_deadline"

    behind = FakeManager(651, [652])
    code, _rows, errors = execute(behind, at(21, 35), at(22, 15, 1))
    assert code == 1 and behind.reconciled == [(652, True)]
    assert errors[-1]["status"] == "boundary_not_observed_after_catch_up"

    print(
        f"OK - CspoE {ENGINE_VERSION}: daily no-transition success + "
        "boundary commit + API/deadline failure + catch-up guard"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
