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
import os, tempfile
from pathlib import Path
from unittest.mock import patch
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from notifications.health_watcher import CheckResult, run_health, check_timer

with tempfile.TemporaryDirectory() as td:
    state = Path(td) / "health.json"
    env = {
        "CSPOE_HEALTH_STATE_FILE": str(state),
        "CSPOE_TELEGRAM_ADMIN_ENABLED": "0",
    }
    # config module is already loaded, so patch get_setting at module scope.
    import notifications.health_watcher as hw
    real_get = hw.get_setting
    def fake_get(name, default=""):
        return env.get(name, real_get(name, default))
    seq = [
        [CheckResult("x", "Test", True, "OK", threshold=2)],
        [CheckResult("x", "Test", False, "boom", threshold=2)],
        [CheckResult("x", "Test", False, "boom", threshold=2)],
        [CheckResult("x", "Test", False, "boom", threshold=2)],
        [CheckResult("x", "Test", True, "OK", threshold=2)],
    ]
    with patch.object(hw, "get_setting", side_effect=fake_get):
        a = run_health(checks_override=lambda: seq[0]); assert a["notifications_pending"] == 0
        b = run_health(checks_override=lambda: seq[1]); assert b["notifications_pending"] == 0
        c = run_health(checks_override=lambda: seq[2]); assert c["notifications_pending"] == 1
        d = run_health(checks_override=lambda: seq[3]); assert d["notifications_pending"] == 0
        e = run_health(checks_override=lambda: seq[4]); assert e["notifications_pending"] == 1
print("OK - private health watcher thresholds + incident dedup + recovery")

# Timer regression tests: running is healthy, real failures remain unhealthy.
import notifications.health_watcher as hw2
with patch.object(hw2, "_systemctl_show", return_value={
    "LoadState":"loaded", "ActiveState":"active", "SubState":"running", "UnitFileState":"enabled"
}):
    assert check_timer("x.timer").ok is True
with patch.object(hw2, "_systemctl_show", return_value={
    "LoadState":"loaded", "ActiveState":"inactive", "SubState":"dead", "UnitFileState":"enabled"
}):
    assert check_timer("x.timer").ok is False
with patch.object(hw2, "_systemctl_show", return_value={
    "LoadState":"loaded", "ActiveState":"active", "SubState":"waiting", "UnitFileState":"disabled"
}):
    assert check_timer("x.timer").ok is False
print("OK - timer running accepted + inactive/disabled rejected")
