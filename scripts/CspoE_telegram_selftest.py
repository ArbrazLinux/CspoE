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
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from notifications.events import derive_events
from notifications.templates import render

base={
 'epoch':651,
 'pool':{'stake':{'_epoch_':100_000_000}},
 'delegators':{'delegator':[{'stake_address':'stake1alice','stake':{'_epoch_':60_000_000}},{'stake_address':'stake1bob','stake':{'_epoch_':40_000_000}}]},
 'blocks':{'block':[]},
}
cur=copy.deepcopy(base); cur['epoch']=652; cur['pool']['stake']['_epoch_']=150_000_000
cur['delegators']['delegator']=[{'stake_address':'stake1alice','stake':{'_epoch_':80_000_000}},{'stake_address':'stake1carol','stake':{'_epoch_':70_000_000}}]
cur['blocks']['block']=[{'hash':'abc','slot':123}]
e=derive_events(base,cur)
kinds=[x.kind for x in e]
assert kinds.count('new_epoch')==1,kinds
assert kinds.count('delegator_join')==1,kinds
assert kinds.count('delegator_leave')==1,kinds
assert kinds.count('delegator_stake_change')==1,kinds
assert kinds.count('pool_stake_change')==1,kinds
assert kinds.count('block')==1,kinds
assert all(render(x,ticker='TEST') for x in e)
print('OK - Telegram event derivation + templates')
e2=derive_events(base,cur,include_delegator_events=False,include_pool_stake_events=False,include_block_events=False)
k2=[x.kind for x in e2]
assert k2==['new_epoch'],k2
print('OK - snapshot watcher ownership excludes stake/delegator/block duplicates')
