#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline checks for durable Blockfrost quota suspension and reset."""
from __future__ import annotations

import json
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = type("Session", (), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    sys.modules["requests"] = requests_stub

from core.blockfrost import BlockfrostClient, BlockfrostPauseRequired, BlockfrostRequestBudget


class Response:
    def __init__(self, status: int, payload=None, headers=None):
        self.status_code = status
        self.payload = payload if payload is not None else {"ok": True}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def client(session, budget, sleeps=None):
    return BlockfrostClient(
        project_id="test",
        session=session,
        request_budget=budget,
        sleep=(lambda delay: sleeps.append(delay)) if sleeps is not None else (lambda delay: None),
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cspoe-budget-selftest-") as temporary:
        root = Path(temporary)
        now = [datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)]
        budget = BlockfrostRequestBudget(
            root / "usage.json", daily_budget=3, reserve=1, clock=lambda: now[0]
        )
        session = Session([Response(200), Response(200), Response(200)])
        bf = client(session, budget)
        bf.get("/one")
        bf.get("/two")
        try:
            bf.get("/three")
            raise AssertionError("proactive pause expected")
        except BlockfrostPauseRequired as exc:
            assert exc.reason == "local_daily_budget"
        assert session.calls == 2
        assert budget.snapshot()["requests_today"] == 2
        assert json.loads((root / "usage.json").read_text())["requests_total"] == 2

        now[0] = datetime(2026, 9, 10, 0, 1, tzinfo=timezone.utc)
        bf.get("/after-reset")
        assert budget.snapshot()["requests_today"] == 1

        quota_budget = BlockfrostRequestBudget(root / "quota.json", daily_budget=100)
        quota_session = Session([Response(402)])
        try:
            client(quota_session, quota_budget).get("/quota")
            raise AssertionError("HTTP 402 pause expected")
        except BlockfrostPauseRequired as exc:
            assert exc.reason == "provider_daily_quota" and exc.status_code == 402
        assert quota_session.calls == 1

        rate_budget = BlockfrostRequestBudget(root / "rate.json", daily_budget=100)
        rate_session = Session([Response(429, headers={"Retry-After": "1"}), Response(200)])
        sleeps = []
        assert client(rate_session, rate_budget, sleeps).get("/rate") == {"ok": True}
        assert rate_session.calls == 2 and sleeps == [1.0]
        assert rate_budget.snapshot()["requests_today"] == 2

    print(json.dumps({
        "ok": True,
        "test": "blockfrost-durable-request-budget-v1",
        "checks": [
            "every HTTP attempt is counted and persisted",
            "local reserve pauses before the configured ceiling",
            "daily counter resets at midnight UTC",
            "HTTP 402 stops without retry",
            "HTTP 429 respects Retry-After before a bounded retry",
        ],
        "network_requests_executed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
