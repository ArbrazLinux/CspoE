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
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.blockfrost import BlockfrostClient
from core.config import get_setting,settings
from notifications.drep_watcher import DRepVoteWatcher
from notifications.telegram import TelegramClient
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--bootstrap-notify',action='store_true'); ap.add_argument('--state-file',default=str(Path(settings.data_dir)/'CspoE'/'notifications'/'drep_watcher_state.json')); a=ap.parse_args()
    enabled=get_setting('CSPOE_TELEGRAM_DREP_ENABLED',get_setting('CSPOE_TELEGRAM_ENABLED','0')).lower() in {'1','true','yes','on'}
    drep_id=get_setting('CSPOE_DREP_ID'); token=get_setting('TELEGRAM_BOT_TOKEN'); chat=get_setting('TELEGRAM_CHAT_ID')
    if not drep_id: raise SystemExit('CSPOE_DREP_ID non configuré')
    if not enabled and not a.dry_run: print(json.dumps({'ok':True,'skipped':True,'reason':'telegram_drep_disabled'},indent=2)); return 0
    tg=None if a.dry_run else TelegramClient(token,chat)
    w=DRepVoteWatcher(drep_id=drep_id,ticker=settings.pool_ticker,state_file=Path(a.state_file),blockfrost=BlockfrostClient(),telegram=tg,max_pages=int(get_setting('CSPOE_TELEGRAM_DREP_MAX_PAGES','10') or 10))
    r=w.run(dry_run=a.dry_run,bootstrap_notify=a.bootstrap_notify); r.update({'chat_id':chat,'drep_id':drep_id,'state_file':a.state_file}); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
