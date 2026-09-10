# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Personal Telegram delivery for verified-pool subscriber bindings."""
from __future__ import annotations
from typing import Any
from .telegram import TelegramClient
from .subscribers import SubscriberStore

LOVELACE=1_000_000

def _ada(v:int)->str:
    return f"{v/LOVELACE:,.6f}".replace(","," ").rstrip("0").rstrip(".") + " ₳"

def _short(a:str)->str:
    return a if len(a)<=24 else a[:14]+"…"+a[-8:]

def _reward_rows(snapshot:dict[str,Any])->dict[str,int]:
    out={}
    for section,key in (("owners","owner"),("delegators","delegator")):
        p=snapshot.get(section) if isinstance(snapshot.get(section),dict) else {}
        for row in p.get(key,[]) if isinstance(p.get(key),list) else []:
            if not isinstance(row,dict): continue
            addr=str(row.get("stake_address") or "")
            r=row.get("rewards") if isinstance(row.get("rewards"),dict) else {}
            try: amount=int(r.get("_epoch_") or 0)
            except Exception: amount=0
            if addr and amount>0: out[addr]=amount
    return out

class PersonalNotifier:
    def __init__(self,*,store:SubscriberStore,token:str,ticker:str="POOL",require_ownership_verified:bool=True):
        self.store=store; self.token=token; self.ticker=ticker; self.require_ownership_verified=require_ownership_verified
    def _send(self,rec:dict[str,Any],address:str,key:str,text:str)->bool:
        uid=int(rec["telegram_user_id"])
        if self.store.was_delivered(uid,address,key): return False
        TelegramClient(self.token,str(rec["chat_id"])).send_message(text)
        self.store.mark_delivered(uid,address,key); return True
    def notify_stake_change(self,*,address:str,before:int,after:int,event_key:str,kind:str="change",reward_component:int=0)->int:
        diff=after-before if kind=="change" else (after if kind=="join" else -before)
        label={"join":f"🟢 Votre délégation {self.ticker} est active","leave":f"🔴 Votre délégation {self.ticker} n’est plus active"}.get(kind,f"📈 Votre stake {self.ticker} a évolué" if diff>0 else f"📉 Votre stake {self.ticker} a évolué")
        text=(f"{label}\n\n<b>Adresse :</b> <code>{_short(address)}</code>\n"
              f"<b>Variation :</b> {_ada(diff)}\n<b>Stake actuel :</b> {_ada(after)}")
        if reward_component: text += f"\n<i>Part rewards neutralisée : {_ada(reward_component)}</i>"
        return sum(self._send(r,address,event_key,text) for r in self.store.recipients_for(address,"stake_alert",require_ownership_verified=self.require_ownership_verified))
    def notify_rewards(self,*,settled_epoch:int,snapshot:dict[str,Any])->int:
        sent=0
        for address,amount in _reward_rows(snapshot).items():
            key=f"personal_reward:{settled_epoch}:{address}:{amount}"
            text=(f"💰 <b>Vos rewards {self.ticker} sont disponibles</b>\n\n"
                  f"Epoch : <b>{settled_epoch}</b>\nReward : <b>{_ada(amount)}</b>\n"
                  f"Adresse : <code>{_short(address)}</code>")
            for r in self.store.recipients_for(address,"reward_alert",require_ownership_verified=self.require_ownership_verified):
                sent += int(self._send(r,address,key,text))
        return sent
