#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Build the lossless pooldata projection. Dry-run by default."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import settings
from core.pooldata import PooldataExporter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--prune-nb", type=int, default=settings.prune_nb)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        result = PooldataExporter(
            args.data_root,
            args.output_dir,
            prune_nb=args.prune_nb,
        ).export(write=args.write)
    except Exception as exc:
        result = {"ok": False, "written": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
