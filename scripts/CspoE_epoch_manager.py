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

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_epoch_manager import CspoEEpochManager
from core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["status", "observe", "reconcile"],
    )
    parser.add_argument("--pool-id", default=settings.bech32_pool_id)
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--observed-epoch", type=int)
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--report-file", default=None)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Required by reconcile; reconcile is a dry-run by default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias explicite du comportement par défaut en lecture seule.",
    )
    args = parser.parse_args()

    if not args.pool_id:
        parser.error("Set BECH32_POOL_ID or use --pool-id")
    manager = CspoEEpochManager(args.pool_id, data_root=args.data_root)

    if args.command == "status":
        result = manager.status()
    elif args.command == "observe":
        result = {"ok": True, "observed_epoch": manager.observe_epoch()}
    else:
        if args.observed_epoch is None:
            parser.error("--observed-epoch is required")
        if args.write and args.dry_run:
            parser.error("--write et --dry-run sont incompatibles")
        result = manager.reconcile_reward_window(
            args.observed_epoch,
            write=args.write,
            report_file=args.report_file,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
