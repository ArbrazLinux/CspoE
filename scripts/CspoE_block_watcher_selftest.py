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
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from notifications.block_watcher import PoolBlockWatcher

class FakeBF:
    def __init__(self, hashes, details):
        self.hashes=list(hashes); self.details=details
    def pool_blocks(self, page=1, count=100, order='desc'):
        assert order == 'desc'
        start=(page-1)*count
        return self.hashes[start:start+count]
    def block(self, h):
        return dict(self.details[h])

class FakeTG:
    def __init__(self): self.messages=[]
    def send_message(self, text): self.messages.append(text); return {'ok':True}

def b(h,height,epoch=652,slot=1):
    return {'hash':h,'height':height,'epoch':epoch,'slot':slot,'time':1000+height,'tx_count':2}

with tempfile.TemporaryDirectory() as td:
    state=Path(td)/'state.json'; tg=FakeTG()
    bf=FakeBF(['h10','h9'], {'h10':b('h10',10),'h9':b('h9',9)})
    w=PoolBlockWatcher(ticker='TEST',state_file=state,blockfrost=bf,telegram=tg,now=lambda:1234)
    r=w.run()
    assert r['bootstrap'] is True and r['pending']==0, r
    assert tg.messages==[], tg.messages
    saved=json.loads(state.read_text()); assert saved['last_hash']=='h10',saved

    bf.hashes=['h12','h11','h10','h9']; bf.details.update({'h11':b('h11',11,slot=11),'h12':b('h12',12,slot=12)})
    r=w.run(); assert r['pending']==2,r
    assert len(tg.messages)==2,tg.messages
    saved=json.loads(state.read_text()); assert saved['last_hash']=='h12' and saved['last_height']==12,saved

    before=len(tg.messages); r=w.run(); assert r['pending']==0,r
    assert len(tg.messages)==before,tg.messages

print('OK - realtime block watcher bootstrap + chronological send + dedup')
