# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Near-real-time DRep vote detection, isolated from canonical CspoE data."""
from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any, Callable
from core.blockfrost import BlockfrostClient
from .telegram import TelegramClient
from .templates import render_drep_vote

def _load(path: Path) -> dict[str, Any]:
    if not path.is_file(): return {}
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception: return {}

def _save(path: Path, value: dict[str, Any]):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); os.replace(tmp,path)

def _key(v): return f"{v.get('tx_hash','')}:{v.get('cert_index','')}:{v.get('proposal_id','')}"

class DRepVoteWatcher:
    def __init__(self, *, drep_id:str, ticker:str, state_file:Path, blockfrost=None, telegram=None, max_pages=10, page_size=100, now:Callable[[],float]=time.time):
        self.drep_id=drep_id; self.ticker=ticker; self.state_file=state_file; self.blockfrost=blockfrost or BlockfrostClient(); self.telegram=telegram
        self.max_pages=max(1,int(max_pages)); self.page_size=max(1,min(int(page_size),100)); self.now=now

    def _list(self,last_key=""):
        out=[]; found=False; seen=set()
        for page in range(1,self.max_pages+1):
            rows=self.blockfrost.drep_votes(self.drep_id,page=page,count=self.page_size,order="desc")
            if not isinstance(rows,list): raise RuntimeError("Réponse Blockfrost DRep votes invalide")
            for row in rows:
                if not isinstance(row,dict): continue
                k=_key(row)
                if not k or k in seen: continue
                seen.add(k)
                if last_key and k==last_key: return out,True
                out.append(row)
            if len(rows)<self.page_size: break
        return out,found

    def run(self, *, dry_run=False, bootstrap_notify=False):
        state=_load(self.state_file)
        state_drep_id=str(state.get("drep_id") or "")
        configured_drep_id=str(self.drep_id or "")
        drep_changed=bool(state_drep_id and state_drep_id != configured_drep_id)
        initialized=bool(state.get("initialized")) and not drep_changed
        legacy_state_migrated=bool(initialized and not state_drep_id)
        # v0.3.1 states did not store drep_id. Bind such an already-initialized
        # state to the currently configured DRep immediately, even if there are
        # zero votes and therefore no later event would otherwise rewrite it.
        if legacy_state_migrated:
            state=dict(state)
            state["drep_id"]=configured_drep_id
            state["updated_at"]=int(self.now())
            if not dry_run:
                _save(self.state_file,state)
        last_key=str(state.get("last_key") or "") if initialized else ""
        rows,cursor_found=self._list(last_key)
        # First run, or DRep id changed: baseline the configured DRep history.
        # An old DRep cursor must never suppress or duplicate notifications for a new DRep.
        if not initialized:
            baseline={"initialized":True,"drep_id":configured_drep_id,"last_key":_key(rows[0]) if rows else "","last_tx_hash":rows[0].get("tx_hash") if rows else None,"updated_at":int(self.now())}
            messages=[]
            if rows and bootstrap_notify:
                v=rows[0]; prop=self.blockfrost.governance_proposal(v.get("proposal_tx_hash"),v.get("proposal_cert_index",0)); tx=self.blockfrost.transaction(v.get("tx_hash")); text=render_drep_vote(v,ticker=self.ticker,proposal=prop,tx=tx); messages=[{"key":_key(v),"text":text}]
                if not dry_run and self.telegram: self.telegram.send_message(text)
            if not dry_run: _save(self.state_file,baseline)
            return {"ok":True,"bootstrap":True,"drep_changed":drep_changed,"previous_drep_id":state_drep_id or None,"votes_seen":len(rows),"pending":len(messages),"messages":messages,"state":baseline}
        # API is newest-first; send oldest unseen first.
        candidates=list(reversed(rows)); messages=[]; newest=dict(state)
        for v in candidates:
            prop={}; tx={}
            try: prop=self.blockfrost.governance_proposal(v.get("proposal_tx_hash"),v.get("proposal_cert_index",0))
            except Exception: pass
            try: tx=self.blockfrost.transaction(v.get("tx_hash"))
            except Exception: pass
            text=render_drep_vote(v,ticker=self.ticker,proposal=prop,tx=tx); k=_key(v); messages.append({"key":k,"vote":v.get("vote"),"proposal_id":v.get("proposal_id"),"text":text})
            if not dry_run and self.telegram: self.telegram.send_message(text)
            newest={"initialized":True,"drep_id":configured_drep_id,"last_key":k,"last_tx_hash":v.get("tx_hash"),"last_proposal_id":v.get("proposal_id"),"last_vote":v.get("vote"),"updated_at":int(self.now())}
            if not dry_run: _save(self.state_file,newest)
        return {"ok":True,"bootstrap":False,"cursor_found":cursor_found,"legacy_state_migrated":legacy_state_migrated,"votes_seen":len(rows),"pending":len(candidates),"messages":messages,"state":newest}
