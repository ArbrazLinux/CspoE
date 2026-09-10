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
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from notifications.health_watcher import run_health

p = argparse.ArgumentParser(description="CspoE private technical health watcher")
p.add_argument("--dry-run", action="store_true")
args = p.parse_args()
try:
    out = run_health(dry_run=args.dry_run)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0)
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
    raise SystemExit(1)
