#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Run one transition check and reward-window transaction."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_epoch_manager import CspoEEpochManager
from core.config import settings
from core.projections import refresh_projections


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool-id", default=settings.bech32_pool_id)
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument(
        "--no-window-check",
        action="store_true",
        help="Allow a manual transition check outside the safety window.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.pool_id:
        print(json.dumps({"ok": False, "error": "Missing BECH32_POOL_ID"}, indent=2))
        return 2

    manager = CspoEEpochManager(args.pool_id, data_root=args.data_root)
    window = manager.transition_window()
    if not args.no_window_check and window["status"] not in {
        "pre_transition",
        "security_snapshot",
        "confirmation_window",
    }:
        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "outside_transition_window",
                    "window": window,
                },
                indent=2,
            )
        )
        return 0

    status = manager.status()
    state = status.get("state") or {}
    previous_observed = state.get("last_collected_epoch")
    observed = manager.observe_epoch()
    if previous_observed is not None and observed <= int(previous_observed):
        result = {
            "ok": True,
            "skipped": True,
            "reason": "new_epoch_not_observed",
            "previous_observed_epoch": int(previous_observed),
            "observed_epoch": observed,
            "window": window,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    reconciliation = manager.reconcile_reward_window(
        observed,
        write=not args.dry_run,
    )
    projections = None
    if reconciliation.get("ok") and (args.dry_run or reconciliation.get("written")):
        projections = refresh_projections(
            args.data_root,
            write=not args.dry_run,
        )
    result = {
        "ok": bool(reconciliation.get("ok")) and (projections or {}).get("ok", True),
        "window": window,
        "previous_observed_epoch": previous_observed,
        "observed_epoch": observed,
        "reward_window": reconciliation,
        "projections": projections,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
