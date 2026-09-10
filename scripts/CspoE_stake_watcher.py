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
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.config import get_setting, settings
from core.blockfrost import BlockfrostClient
from notifications.telegram import TelegramClient
from notifications.stake_watcher import StakeDelegatorWatcher
from notifications.subscribers import SubscriberStore
from notifications.personal import PersonalNotifier

def _bool(name,default=True):
    return get_setting(name,'1' if default else '0').lower() in {'1','true','yes','on'}
def _int(name,default=0):
    try:return int(get_setting(name,str(default)) or default)
    except (TypeError,ValueError):return int(default)
def _ada_lovelace(name,default='0'):
    try:
        from decimal import Decimal
        return int(Decimal(get_setting(name,default) or default) * Decimal(1_000_000))
    except Exception:
        return int(Decimal(default) * Decimal(1_000_000))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    if not _bool('CSPOE_TELEGRAM_STAKE_WATCHER_ENABLED',True):
        print(json.dumps({'ok':True,'disabled':True},ensure_ascii=False,indent=2)); return 0
    token=get_setting('TELEGRAM_BOT_TOKEN'); chat=get_setting('TELEGRAM_CHAT_ID')
    tg=None if args.dry_run else TelegramClient(token=token,chat_id=chat)
    personal=None
    if (not args.dry_run) and _bool('CSPOE_TELEGRAM_INTERACTIVE_ENABLED',False):
        db=Path(get_setting('CSPOE_TELEGRAM_SUBSCRIBERS_DB',str(ROOT/'data/CspoE/notifications/subscribers.sqlite3')))
        personal=PersonalNotifier(store=SubscriberStore(db),token=token,ticker=settings.ticker)
    state_file=Path(get_setting('CSPOE_STAKE_WATCHER_STATE_FILE',str(ROOT/'data'/'CspoE'/'notifications'/'stake_watcher_state.json')))
    watcher=StakeDelegatorWatcher(ticker=settings.ticker,pool_id=settings.pool_id,state_file=state_file,
        blockfrost=BlockfrostClient(pool_id=settings.pool_id),telegram=tg,
        delegator_change_threshold_lovelace=_ada_lovelace('CSPOE_DELEGATOR_CHANGE_THRESHOLD_ADA','0'),
        pool_change_threshold_lovelace=_ada_lovelace('CSPOE_POOL_STAKE_CHANGE_THRESHOLD_ADA','0'),
        delegator_events_enabled=_bool('CSPOE_TELEGRAM_DELEGATOR_EVENTS_ENABLED',True),
        pool_stake_events_enabled=_bool('CSPOE_TELEGRAM_POOL_STAKE_EVENTS_ENABLED',True),
        group_events_enabled=_bool('CSPOE_TELEGRAM_STAKE_GROUP_EVENTS_ENABLED',True),
        group_tolerance_lovelace=_ada_lovelace('CSPOE_STAKE_GROUP_TOLERANCE_ADA','10'),
        max_group_items=_int('CSPOE_STAKE_GROUP_MAX_ITEMS',8),
        reward_correlation_enabled=_bool('CSPOE_REWARD_STAKE_CORRELATION_ENABLED',True),
        reward_epoch_offset=_int('CSPOE_REWARD_STAKE_EPOCH_OFFSET',3),
        reward_match_tolerance_lovelace=_ada_lovelace('CSPOE_REWARD_STAKE_MATCH_TOLERANCE_ADA','2'),
        reward_batch_min_matches=_int('CSPOE_REWARD_STAKE_MIN_MATCHES',3),
        epoch_manager_state_file=ROOT/'data'/'CspoE'/'epoch_manager_state.json',
        epochs_dir=ROOT/'data'/'CspoE'/'epochs',
        stake_transfer_enabled=_bool('CSPOE_STAKE_ADDRESS_TRANSFER_ENABLED',True),
        stake_transfer_window_seconds=_int('CSPOE_STAKE_ADDRESS_TRANSFER_WINDOW_MINUTES',180)*60,
        stake_transfer_tolerance_lovelace=_ada_lovelace('CSPOE_STAKE_ADDRESS_TRANSFER_TOLERANCE_ADA','5'),
        max_pages=_int('CSPOE_STAKE_WATCHER_MAX_PAGES',100), personal_notifier=personal)
    result=watcher.run(dry_run=args.dry_run)
    result.update({'dry_run':args.dry_run,'chat_id':chat,'pool_id':settings.pool_id,'state_file':str(state_file)})
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
