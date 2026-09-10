#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.config import get_setting, settings
from notifications.subscribers import SubscriberStore
from notifications.interactive_bot import InteractiveBot

def _bool(name,default=True):
    return str(get_setting(name,'1' if default else '0')).lower() in {'1','true','yes','on'}
def _int(name,default):
    try:return int(get_setting(name,str(default)) or default)
    except Exception:return int(default)

def main():
    if not _bool('CSPOE_TELEGRAM_INTERACTIVE_ENABLED',False):
        raise SystemExit('CSPOE_TELEGRAM_INTERACTIVE_ENABLED=0')
    token=get_setting('TELEGRAM_BOT_TOKEN')
    if not token:raise SystemExit('TELEGRAM_BOT_TOKEN absent')
    db=Path(get_setting('CSPOE_TELEGRAM_SUBSCRIBERS_DB',str(ROOT/'data/CspoE/notifications/subscribers.sqlite3')))
    bot=InteractiveBot(token=token,pool_id=settings.pool_id,ticker=settings.ticker,store=SubscriberStore(db),
        stake_state_file=ROOT/'data/CspoE/notifications/stake_watcher_state.json',
        epoch_manager_state_file=ROOT/'data/CspoE/epoch_manager_state.json',epochs_dir=ROOT/'data/CspoE/epochs',
        challenge_ttl_seconds=_int('CSPOE_TELEGRAM_CIP8_CHALLENGE_TTL_SECONDS',600),
        require_ownership_verified=_bool('CSPOE_TELEGRAM_REQUIRE_OWNERSHIP_VERIFICATION',True),
        cip8_backend=get_setting('CSPOE_CIP8_VERIFY_BACKEND','cardano-signer'),
        cardano_signer_path=get_setting('CSPOE_CARDANO_SIGNER','/usr/local/bin/cardano-signer'),
        cardano_signer_required_version=get_setting('CSPOE_CARDANO_SIGNER_REQUIRED_VERSION','1.35.0'))
    bot.run_forever(); return 0
if __name__=='__main__':raise SystemExit(main())
