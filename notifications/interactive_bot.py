# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Telegram private interactive bot for pool delegators with CIP-8 verification."""
from __future__ import annotations
import json, re, time
from pathlib import Path
from typing import Any
import requests
from core.blockfrost import BlockfrostClient
from .telegram import TelegramClient
from .subscribers import SubscriberStore
from .cip8_verification import verify_cip8, CIP8VerificationError, cardano_signer_version

STAKE_RE=re.compile(r"^stake1[0-9a-z]{20,120}$")

def _short(a:str)->str: return a if len(a)<28 else a[:15]+"…"+a[-8:]
def _ada(v:int)->str: return f"{v/1_000_000:,.6f}".replace(","," ").rstrip("0").rstrip(".")+" ₳"

def _load(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class InteractiveBot:
    def __init__(self,*,token:str,pool_id:str,ticker:str,store:SubscriberStore,stake_state_file:Path,epoch_manager_state_file:Path,epochs_dir:Path,blockfrost:BlockfrostClient|None=None,poll_timeout:int=25,challenge_ttl_seconds:int=600,require_ownership_verified:bool=True,cip8_backend:str="cardano-signer",cardano_signer_path:str="/usr/local/bin/cardano-signer",cardano_signer_required_version:str="1.35.0"):
        self.token=token; self.pool_id=pool_id; self.ticker=ticker; self.store=store
        self.stake_state_file=stake_state_file; self.epoch_manager_state_file=epoch_manager_state_file; self.epochs_dir=epochs_dir
        self.blockfrost=blockfrost or BlockfrostClient(pool_id=pool_id); self.poll_timeout=poll_timeout
        self.challenge_ttl_seconds=max(60,int(challenge_ttl_seconds)); self.require_ownership_verified=bool(require_ownership_verified)
        self.cip8_backend=cip8_backend; self.cardano_signer_path=cardano_signer_path; self.cardano_signer_required_version=cardano_signer_required_version
    def client(self,chat_id:int)->TelegramClient:return TelegramClient(self.token,str(chat_id),timeout=max(15,self.poll_timeout+5))
    def send(self,chat_id:int,text:str,reply_markup:dict|None=None)->None:self.client(chat_id).send_message(text,reply_markup=reply_markup)
    def _is_pool_delegator(self,address:str)->bool:
        try:
            rows=self.blockfrost.account_delegations_all(address,refresh=True)
            if not rows:return False
            return str(rows[-1].get("pool_id") or "")==self.pool_id
        except Exception:return False
    def menu(self)->dict:
        return {"inline_keyboard":[
            [{"text":"💎 Mon stake","callback_data":"my_stake"},{"text":"💰 Mes rewards","callback_data":"my_rewards"}],
            [{"text":"🔔 Notifications","callback_data":"prefs"},{"text":"👛 Mes wallets","callback_data":"wallets"}],
            [{"text":"🔐 Sécurité","callback_data":"security"},{"text":"ℹ️ Aide","callback_data":"help"}]
        ]}
    def _prefs_markup(self,uid:int)->dict:
        p=self.store.prefs(uid)
        return {"inline_keyboard":[
          [{"text":("✅" if p['stake_alert'] else "❌")+" Variations stake","callback_data":"toggle:stake_alert"}],
          [{"text":("✅" if p['reward_alert'] else "❌")+" Rewards","callback_data":"toggle:reward_alert"}],
          [{"text":"⬅️ Menu","callback_data":"menu"}]]}
    def _wallets_text(self,uid:int)->str:
        rows=self.store.bindings(uid)
        if not rows:return "👛 <b>Mes wallets</b>\n\nAucune stake address associée.\nUtilisez <code>/add stake1...</code>."
        lines=["👛 <b>Mes wallets</b>",""]
        for r in rows:
            verified=bool(r.get('ownership_verified'))
            status="propriété vérifiée 🔐" if verified else "propriété à vérifier ⚠️"
            lines.append(f"• <code>{_short(r['stake_address'])}</code> · {self.ticker} ✅ · {status}")
        lines += ["","Vérification : <code>/challenge stake1...</code>","Suppression : <code>/remove stake1...</code>"]
        return "\n".join(lines)
    def _stake_text(self,uid:int)->str:
        state=_load(self.stake_state_file); deleg=state.get("delegators") if isinstance(state.get("delegators"),dict) else {}
        rows=self.store.bindings(uid)
        if not rows:return "💎 Aucun wallet associé. Utilisez <code>/add stake1...</code>."
        lines=[f"💎 <b>Mon stake {self.ticker}</b>",""]; total=0
        for r in rows:
            a=r['stake_address']; amount=int(deleg.get(a,0) or 0); total+=amount
            lock="🔐" if r.get('ownership_verified') else "⚠️"
            lines.append(f"• {lock} <code>{_short(a)}</code> : <b>{_ada(amount)}</b>")
        if len(rows)>1:lines += ["",f"Total : <b>{_ada(total)}</b>"]
        return "\n".join(lines)
    def _rewards_text(self,uid:int)->str:
        manager=_load(self.epoch_manager_state_file)
        try: ep=int(manager.get("last_rewards_settled_epoch"))
        except Exception: return "💰 Rewards : état de règlement indisponible."
        snap=_load(self.epochs_dir/f"epoch_{ep}.json")
        rows=self.store.bindings(uid)
        bindings={r['stake_address'] for r in rows}
        if not bindings:return "💰 Aucun wallet associé. Utilisez <code>/add stake1...</code>."
        found={}
        for section,key in (("owners","owner"),("delegators","delegator")):
            p=snap.get(section) if isinstance(snap.get(section),dict) else {}
            for row in p.get(key,[]) if isinstance(p.get(key),list) else []:
                if not isinstance(row,dict):continue
                a=str(row.get("stake_address") or "")
                if a not in bindings:continue
                rw=row.get("rewards") if isinstance(row.get("rewards"),dict) else {}
                found[a]=int(rw.get("_epoch_") or 0)
        verified_by={r['stake_address']:bool(r.get('ownership_verified')) for r in rows}
        lines=[f"💰 <b>Mes rewards — epoch {ep}</b>",""]
        for a in sorted(bindings):
            lock="🔐" if verified_by.get(a) else "⚠️"
            lines.append(f"• {lock} <code>{_short(a)}</code> : <b>{_ada(found.get(a,0))}</b>")
        return "\n".join(lines)
    def _security_text(self)->str:
        backend=(self.cip8_backend or "cardano-signer").strip()
        if backend.lower() in {"cardano-signer","cardano_signer","signer"}:
            try:
                version=cardano_signer_version(self.cardano_signer_path)
                signer=f"cardano-signer {version} ✅" if version==self.cardano_signer_required_version else f"cardano-signer {version} ⚠️ (attendu {self.cardano_signer_required_version})"
            except Exception as exc:
                signer=f"cardano-signer indisponible ❌ ({exc})"
        else:
            signer=f"backend {backend} ⚠️"
        ownership="obligatoire ✅" if self.require_ownership_verified else "désactivée ⚠️"
        return ("🔐 <b>Sécurité des associations</b>\n\n"
                f"Backend CIP-8 : <b>{signer}</b>\n"
                f"Vérification de propriété : <b>{ownership}</b>\n"
                f"Challenge : <b>{self.challenge_ttl_seconds}s</b>, usage unique\n\n"
                "Aucune seed phrase ni clé privée n'est demandée ou stockée.")
    def _help(self)->str:
        return (f"ℹ️ <b>Bot {self.ticker} — CspoE interactive</b>\n\n"
                f"<code>/start</code> — menu\n<code>/add stake1...</code> — associer une stake address {self.ticker}\n"
                "<code>/challenge stake1...</code> — générer un challenge de propriété CIP-8\n"
                "<code>/verify stake1... COSE_SIGN1_HEX COSE_KEY_HEX</code> — valider la signature\n"
                "<code>/remove stake1...</code> — retirer une association\n<code>/wallets</code> — associations\n"
                "<code>/monstake</code> — stake actuel\n<code>/mesrewards</code> — derniers rewards réglés\n"
                "<code>/notifications</code> — préférences\n<code>/security</code> — état de la vérification CIP-8\n<code>/stop</code> — désactiver les messages privés\n\n"
                "🔐 La vérification CIP-8 ne demande aucune seed phrase, clé privée ni transaction.")
    def _challenge_text(self,uid:int,address:str)->str:
        rows={r['stake_address']:r for r in self.store.bindings(uid)}
        if address not in rows:return "Associez d'abord cette adresse avec <code>/add stake1...</code>."
        c=self.store.create_challenge(uid,address,self.challenge_ttl_seconds,self.ticker)
        payload=str(c['payload']); payload_hex=payload.encode('utf-8').hex()
        mins=max(1,self.challenge_ttl_seconds//60)
        return (f"🔐 <b>Challenge CIP-8</b>\n\nAdresse : <code>{_short(address)}</code>\n"
                f"Valide environ <b>{mins} min</b>.\n\nTexte exact à signer :\n<code>{payload}</code>\n\n"
                f"Payload UTF-8 hex :\n<code>{payload_hex}</code>\n\n"
                "Après signature CIP-8/COSE avec votre wallet :\n"
                f"<code>/verify {address} COSE_SIGN1_HEX COSE_KEY_HEX</code>\n\n"
                "⚠️ Ne transmettez jamais votre seed phrase ni votre clé privée.")
    def _verify(self,uid:int,address:str,sign1_hex:str,key_hex:str)->str:
        c=self.store.active_challenge(uid,address)
        if not c:return "❌ Challenge absent, expiré ou déjà utilisé. Lancez <code>/challenge stake1...</code>."
        try:
            verify_cip8(stake_address=address,expected_payload=str(c['payload']),cose_sign1_hex=sign1_hex,cose_key_hex=key_hex,backend=self.cip8_backend,cardano_signer_path=self.cardano_signer_path,required_version=self.cardano_signer_required_version)
        except CIP8VerificationError as exc:
            return f"❌ Vérification CIP-8 refusée : <code>{str(exc)}</code>"
        if not self.store.consume_challenge(uid,address):return "❌ Challenge expiré ou déjà consommé."
        if not self.store.mark_ownership_verified(uid,address,"CIP-8"):
            return f"❌ Association introuvable ou non validée pour {self.ticker}."
        return f"✅ <b>Propriété vérifiée</b>\n\n<code>{_short(address)}</code>\nMéthode : CIP-8 / cardano-signer 🔐"
    def handle_message(self,msg:dict[str,Any])->None:
        chat=msg.get('chat') or {}; user=msg.get('from') or {}; chat_id=int(chat.get('id') or 0); uid=int(user.get('id') or 0)
        if not chat_id or not uid or str(chat.get('type'))!='private':return
        self.store.upsert_user(uid,chat_id,str(user.get('username') or ''),str(user.get('first_name') or ''))
        text=str(msg.get('text') or '').strip(); cmd=text.split()[0].split('@')[0].lower() if text else ''
        if cmd in {'/start','/menu'}: self.send(chat_id,f"👋 <b>Bienvenue sur le bot {self.ticker}</b>\n\nAssociez puis vérifiez votre stake address pour recevoir des notifications personnelles.",self.menu()); return
        if cmd=='/help': self.send(chat_id,self._help(),self.menu()); return
        if cmd=='/wallets': self.send(chat_id,self._wallets_text(uid),self.menu()); return
        if cmd=='/monstake': self.send(chat_id,self._stake_text(uid),self.menu()); return
        if cmd=='/mesrewards': self.send(chat_id,self._rewards_text(uid),self.menu()); return
        if cmd=='/notifications': self.send(chat_id,"🔔 <b>Notifications personnelles</b>",self._prefs_markup(uid)); return
        if cmd=='/security': self.send(chat_id,self._security_text(),self.menu()); return
        if cmd=='/stop':
            with self.store.connect() as db: db.execute("UPDATE telegram_users SET enabled=0,updated_at=? WHERE telegram_user_id=?",(int(time.time()),uid))
            self.send(chat_id,"🔕 Notifications privées désactivées. <code>/start</code> les réactive."); return
        if cmd=='/add':
            parts=text.split(maxsplit=1); a=parts[1].strip() if len(parts)>1 else ''
            if not STAKE_RE.match(a): self.send(chat_id,"Adresse invalide. Usage : <code>/add stake1...</code>"); return
            if not self._is_pool_delegator(a): self.send(chat_id,f"Cette stake address n'est pas actuellement déléguée au pool {self.ticker}, association refusée."); return
            self.store.add_binding(uid,a,True)
            self.send(chat_id,f"✅ Adresse associée : <code>{_short(a)}</code>\n\n🔐 Étape suivante : <code>/challenge {a}</code>",self.menu()); return
        if cmd=='/challenge':
            parts=text.split(maxsplit=1); a=parts[1].strip() if len(parts)>1 else ''
            if not STAKE_RE.match(a):self.send(chat_id,"Usage : <code>/challenge stake1...</code>");return
            self.send(chat_id,self._challenge_text(uid,a));return
        if cmd=='/verify':
            parts=text.split()
            if len(parts)!=4 or not STAKE_RE.match(parts[1]):
                self.send(chat_id,"Usage : <code>/verify stake1... COSE_SIGN1_HEX COSE_KEY_HEX</code>");return
            self.send(chat_id,self._verify(uid,parts[1],parts[2],parts[3]),self.menu());return
        if cmd=='/remove':
            parts=text.split(maxsplit=1); a=parts[1].strip() if len(parts)>1 else ''
            ok=self.store.remove_binding(uid,a) if a else False; self.send(chat_id,"✅ Association supprimée." if ok else "Association introuvable.",self.menu()); return
        self.send(chat_id,"Commande inconnue. Utilisez <code>/help</code>.",self.menu())
    def handle_callback(self,q:dict[str,Any])->None:
        user=q.get('from') or {}; msg=q.get('message') or {}; chat=msg.get('chat') or {}; uid=int(user.get('id') or 0); chat_id=int(chat.get('id') or 0); data=str(q.get('data') or '')
        if not uid or not chat_id:return
        self.store.upsert_user(uid,chat_id,str(user.get('username') or ''),str(user.get('first_name') or ''))
        if data.startswith('toggle:'):
            key=data.split(':',1)[1]
            if key in {'reward_alert','stake_alert'}:
                cur=self.store.prefs(uid)[key]; self.store.set_pref(uid,key,not cur); self.send(chat_id,"🔔 Préférences mises à jour.",self._prefs_markup(uid))
        elif data=='my_stake':self.send(chat_id,self._stake_text(uid),self.menu())
        elif data=='my_rewards':self.send(chat_id,self._rewards_text(uid),self.menu())
        elif data=='prefs':self.send(chat_id,"🔔 <b>Notifications personnelles</b>",self._prefs_markup(uid))
        elif data=='wallets':self.send(chat_id,self._wallets_text(uid),self.menu())
        elif data=='security':self.send(chat_id,self._security_text(),self.menu())
        elif data=='help':self.send(chat_id,self._help(),self.menu())
        elif data=='menu':self.send(chat_id,f"Menu {self.ticker}",self.menu())
        try: requests.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",json={"callback_query_id":q.get('id')},timeout=10)
        except Exception:pass
    def poll_once(self)->dict[str,Any]:
        offset=int(self.store.get_meta('update_offset','0') or 0)
        r=requests.get(f"https://api.telegram.org/bot{self.token}/getUpdates",params={'offset':offset,'timeout':self.poll_timeout,'allowed_updates':json.dumps(['message','callback_query'])},timeout=self.poll_timeout+10)
        r.raise_for_status(); payload=r.json(); rows=payload.get('result',[]) if payload.get('ok') else []
        handled=0
        for u in rows:
            try:
                if isinstance(u.get('message'),dict): self.handle_message(u['message']); handled+=1
                elif isinstance(u.get('callback_query'),dict):self.handle_callback(u['callback_query']); handled+=1
            finally:
                offset=max(offset,int(u.get('update_id',0))+1); self.store.set_meta('update_offset',str(offset))
        return {'ok':True,'updates':len(rows),'handled':handled,'next_offset':offset}
    def run_forever(self)->None:
        while True:
            try:self.poll_once()
            except Exception as e:
                print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False),flush=True); time.sleep(5)
