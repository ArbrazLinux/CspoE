#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

import json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from notifications.drep_watcher import DRepVoteWatcher
class BF:
 def __init__(self): self.rows=[]
 def drep_votes(self,*a,**k): return self.rows
 def governance_proposal(self,*a): return {'governance_type':'info_action'}
 def transaction(self,*a): return {'block_height':123,'block_time':1700000000}
class TG:
 def __init__(self): self.sent=[]
 def send_message(self,t): self.sent.append(t)
def v(n,choice='yes'): return {'tx_hash':f'tx{n}','cert_index':n,'proposal_id':f'gov{n}','proposal_tx_hash':f'prop{n}','proposal_cert_index':0,'vote':choice}
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'s.json'; bf=BF(); tg=TG(); w=DRepVoteWatcher(drep_id='drep1old',ticker='TEST',state_file=p,blockfrost=bf,telegram=tg,now=lambda:1)
 r=w.run(); assert r['bootstrap'] and not r['drep_changed'] and r['pending']==0 and p.exists(); assert r['state']['drep_id']=='drep1old'
 bf.rows=[v(1)]; r=w.run(); assert r['pending']==1 and len(tg.sent)==1
 r=w.run(); assert r['pending']==0 and len(tg.sent)==1
 bf.rows=[v(3,'abstain'),v(2,'no'),v(1)]; r=w.run(); assert r['pending']==2 and len(tg.sent)==3
 # Changing configured DRep must reset the cursor and baseline the new history without notifications.
 bf.rows=[v(8,'yes'),v(7,'no')]
 w2=DRepVoteWatcher(drep_id='drep1new',ticker='TEST',state_file=p,blockfrost=bf,telegram=tg,now=lambda:2)
 r=w2.run(); assert r['bootstrap'] and r['drep_changed'] and r['previous_drep_id']=='drep1old' and r['pending']==0
 assert r['state']['drep_id']=='drep1new' and r['state']['last_key'].startswith('tx8:') and len(tg.sent)==3
 # A vote arriving after the DRep change must be notified once.
 bf.rows=[v(9,'abstain'),v(8,'yes'),v(7,'no')]
 r=w2.run(); assert not r['bootstrap'] and r['pending']==1 and len(tg.sent)==4
 r=w2.run(); assert r['pending']==0 and len(tg.sent)==4

 # Legacy v0.3.1 empty-vote state must be bound immediately to the configured DRep.
 legacy=Path(d)/'legacy.json'
 legacy.write_text(json.dumps({'initialized':True,'last_key':'','last_tx_hash':None,'updated_at':10}))
 bf.rows=[]
 wm=DRepVoteWatcher(drep_id='drep1migrated',ticker='TEST',state_file=legacy,blockfrost=bf,telegram=tg,now=lambda:11)
 r=wm.run(); assert not r['bootstrap'] and r['legacy_state_migrated'] and r['pending']==0
 stored=json.loads(legacy.read_text()); assert stored['drep_id']=='drep1migrated' and stored['updated_at']==11

print('OK - DRep watcher state binding + legacy migration + DRep change + chronological send + dedup')
