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
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from notifications.templates import ada,pct_change,render_live_delegator_event,render_live_pool_stake_change,render_realtime_block,render_drep_vote

assert ada(195457713377)=="195 457.71 ₳"
assert ada(25000000,signed=True)=="+25.00 ₳"
assert pct_change(100_000_000,125_000_000)=="+25.00 %"
a=render_live_delegator_event(kind='change',address='stake1'+'x'*55,before=100_000_000,after=125_000_000)
assert '+25.00 ₳' in a and '+25.00 %' in a and 'cardanoscan.io/stakekey/' in a
b=render_live_pool_stake_change(before=100_000_000,after=90_000_000,delegator_count=31)
assert '-10.00 ₳' in b and '-10.00 %' in b and '31' in b
c=render_realtime_block({'hash':'a'*64,'height':123,'epoch':652,'slot':42,'tx_count':3,'time':1788110000})
assert 'cardanoscan.io/block/123' in c and 'Transactions' in c
d=render_drep_vote({'vote':'yes','proposal_id':'gov_action1'+'q'*50,'tx_hash':'b'*64},proposal={'governance_type':'info_action'},tx={'block_height':123})
assert 'OUI' in d and 'cardanoscan.io/govAction/' in d
print('OK - central Telegram templates + ADA/% formatting + explorer links')
