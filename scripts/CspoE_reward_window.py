#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Dry-run/write CLI for the CspoE reward window."""
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
    parser = argparse.ArgumentParser(
        description="Réconcilie N-2, reconstruit N-1 et génère live N. Dry-run par défaut."
    )
    parser.add_argument("--observed-epoch", type=int, default=None)
    parser.add_argument("--pool-id", default=settings.bech32_pool_id)
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--report-file", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--sync-mysql", action="store_true")
    parser.add_argument("--skip-pooldata", action="store_true")
    args = parser.parse_args()

    if not args.pool_id:
        parser.error("Set BECH32_POOL_ID or use --pool-id")
    manager = CspoEEpochManager(args.pool_id, data_root=args.data_root)
    observed_epoch = args.observed_epoch
    if observed_epoch is None:
        observed_epoch = manager.observe_epoch()
    result = manager.reconcile_reward_window(
        observed_epoch,
        write=args.write,
        report_file=args.report_file,
    )
    if result.get("ok") and (not args.write or result.get("written")):
        result["projections"] = refresh_projections(
            args.data_root,
            write=args.write,
            pooldata=not args.skip_pooldata,
            mysql=True if args.sync_mysql else None,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") and (result.get("projections") or {}).get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
