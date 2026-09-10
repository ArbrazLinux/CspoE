# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from __future__ import annotations
import copy, hashlib, json, os, tempfile, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
import requests
from .config import settings
from .version import USER_AGENT

class BlockfrostError(RuntimeError): pass


class BlockfrostPauseRequired(BlockfrostError):
    """Expected, resumable stop caused by a local or provider API limit."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        resume_after: Optional[str] = None,
        status_code: Optional[int] = None,
        usage: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.reason = str(reason)
        self.resume_after = resume_after
        self.status_code = status_code
        self.usage = copy.deepcopy(usage or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "message": str(self),
            "resume_after": self.resume_after,
            "status_code": self.status_code,
            "usage": copy.deepcopy(self.usage),
        }


class BlockfrostRequestBudget:
    """Durable counter and conservative daily request guard.

    The counter covers only requests emitted through this client. Blockfrost
    plan usage can be shared by other projects and applications, hence the
    configurable reserve and the provider-side 402 response remain decisive.
    """

    def __init__(
        self,
        path: Path,
        *,
        daily_budget: int,
        reserve: int = 0,
        auto_pause: bool = True,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.path = Path(path)
        self.daily_budget = max(0, int(daily_budget))
        self.reserve = max(0, int(reserve))
        self.auto_pause = bool(auto_pause)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.state = self._load()

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _next_reset(now: datetime) -> datetime:
        return (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def _fresh(self, now: datetime) -> dict[str, Any]:
        threshold = max(1, self.daily_budget - self.reserve) if self.daily_budget > 0 else 0
        return {
            "schema": 1,
            "utc_day": now.date().isoformat(),
            "requests_today": 0,
            "requests_total": 0,
            "daily_budget": self.daily_budget,
            "reserve": self.reserve,
            "proactive_threshold": threshold,
            "last_request_at": None,
            "last_path": None,
            "last_status_code": None,
            "pause": None,
            "next_utc_reset": self._next_reset(now).isoformat(),
        }

    def _load(self) -> dict[str, Any]:
        now = self._now()
        state = self._fresh(now)
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and int(loaded.get("schema", 0)) == 1:
                    state.update(loaded)
                else:
                    raise ValueError("schema absent ou incompatible")
            except (OSError, ValueError, TypeError) as exc:
                raise BlockfrostError(
                    f"compteur Blockfrost illisible; reprise refusée par sécurité: {self.path}: {exc}"
                ) from exc
        if str(state.get("utc_day")) != now.date().isoformat():
            total = int(state.get("requests_total", 0) or 0)
            state = self._fresh(now)
            state["requests_total"] = total
        state["daily_budget"] = self.daily_budget
        state["reserve"] = self.reserve
        state["proactive_threshold"] = (
            max(1, self.daily_budget - self.reserve) if self.daily_budget > 0 else 0
        )
        state["next_utc_reset"] = self._next_reset(now).isoformat()
        self.state = state
        self._save()
        return state

    def _roll_day(self) -> datetime:
        now = self._now()
        if str(self.state.get("utc_day")) != now.date().isoformat():
            total = int(self.state.get("requests_total", 0) or 0)
            self.state = self._fresh(now)
            self.state["requests_total"] = total
            self._save()
        return now

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="." + self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self) -> dict[str, Any]:
        self._roll_day()
        return copy.deepcopy(self.state)

    def ensure_allowed(self, path: str) -> None:
        now = self._roll_day()
        threshold = int(self.state.get("proactive_threshold", 0) or 0)
        used = int(self.state.get("requests_today", 0) or 0)
        if self.auto_pause and threshold > 0 and used >= threshold:
            resume_after = self._next_reset(now).isoformat()
            self.mark_pause("local_daily_budget", resume_after=resume_after)
            raise BlockfrostPauseRequired(
                "local_daily_budget",
                "plafond local Blockfrost atteint avant épuisement du quota fournisseur",
                resume_after=resume_after,
                usage=self.snapshot(),
            )

    def record(self, path: str, status_code: Optional[int]) -> None:
        now = self._roll_day()
        self.state["requests_today"] = int(self.state.get("requests_today", 0) or 0) + 1
        self.state["requests_total"] = int(self.state.get("requests_total", 0) or 0) + 1
        self.state["last_request_at"] = now.isoformat()
        self.state["last_path"] = str(path)
        self.state["last_status_code"] = status_code
        self._save()

    def mark_pause(
        self,
        reason: str,
        *,
        resume_after: Optional[str],
        status_code: Optional[int] = None,
    ) -> None:
        self.state["pause"] = {
            "reason": str(reason),
            "at": self._now().isoformat(),
            "resume_after": resume_after,
            "status_code": status_code,
        }
        self._save()

class BlockfrostClient:
    """Single Blockfrost data layer for CspoE.

    It deliberately exposes raw historical data. Business shaping belongs to
    CspoE_legacy_contract so every writer uses one and only one legacy formula.
    """
    def __init__(self, project_id: Optional[str]=None, network: Optional[str]=None,
                 timeout: int=25, pool_id: Optional[str]=None,
                 session: Optional[requests.Session]=None,
                 request_budget: Optional[BlockfrostRequestBudget]=None,
                 cache_dir: Optional[Path]=None,
                 sleep: Optional[Callable[[float], None]]=None):
        self.project_id = project_id or settings.blockfrost_project_id
        self.network = (network or settings.network or 'mainnet').lower()
        self.pool_id = pool_id or settings.bech32_pool_id
        self.base = {
            'mainnet':'https://cardano-mainnet.blockfrost.io/api/v0',
            'preview':'https://cardano-preview.blockfrost.io/api/v0',
            'preprod':'https://cardano-preprod.blockfrost.io/api/v0',
        }.get(self.network)
        if not self.base:
            raise BlockfrostError(f'Réseau Blockfrost non supporté: {self.network}')
        self.s = session or requests.Session(); self.timeout=timeout
        self.request_budget=request_budget
        self.cache_dir=Path(cache_dir) if cache_dir is not None else None
        self._sleep=sleep or time.sleep
        self.s.headers.update({'User-Agent': USER_AGENT})
        if self.project_id: self.s.headers.update({'project_id':self.project_id})
        self.page_size=max(1,min(int(settings.blockfrost_page_size),100))
        self.max_pages=max(1,int(settings.api_max_pages))
        self._pool_history_cache={}; self._pool_registration_cache={}; self._reward_cache={}; self._account_history_cache={}; self._delegation_cache={}; self._stake_registration_cache={}

    def _persistent_cache_path(self, namespace: str, key: str) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        digest=hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return self.cache_dir / namespace / f"{digest}.json"

    def _persistent_cache_load(self, namespace: str, key: str) -> Optional[Any]:
        path=self._persistent_cache_path(namespace,key)
        if path is None or not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError):
            return None

    def _persistent_cache_save(self, namespace: str, key: str, value: Any) -> None:
        path=self._persistent_cache_path(namespace,key)
        if path is None:
            return
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,temporary=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as handle:
                json.dump(value,handle,ensure_ascii=False,separators=(",",":"))
                handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary,path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def _require_auth(self):
        if not self.project_id:
            raise BlockfrostError('BLOCKFROST_PROJECT_ID non configuré dans CspoE.conf ou environnement')

    def get(self,path:str,params:Optional[Dict[str,Any]]=None)->Any:
        self._require_auth(); last=None
        for i in range(4):
            if self.request_budget is not None:
                self.request_budget.ensure_allowed(path)
            response_received=False
            try:
                r=self.s.get(self.base+path,params=params,timeout=self.timeout)
                response_received=True
                if self.request_budget is not None:
                    self.request_budget.record(path,int(r.status_code))
                if r.status_code==402:
                    resume=(datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
                    if self.request_budget is not None:
                        self.request_budget.mark_pause("provider_daily_quota",resume_after=resume,status_code=402)
                    raise BlockfrostPauseRequired(
                        "provider_daily_quota",
                        "Blockfrost a refusé la requête: quota journalier du compte dépassé (HTTP 402)",
                        resume_after=resume,status_code=402,
                        usage=self.request_budget.snapshot() if self.request_budget else {},
                    )
                if r.status_code==418:
                    if self.request_budget is not None:
                        self.request_budget.mark_pause("provider_auto_ban",resume_after=None,status_code=418)
                    raise BlockfrostPauseRequired(
                        "provider_auto_ban",
                        "Blockfrost a temporairement banni ce client (HTTP 418); vérifier le tableau de bord avant reprise",
                        status_code=418,
                        usage=self.request_budget.snapshot() if self.request_budget else {},
                    )
                if r.status_code==429:
                    try: delay=max(1.0,float(r.headers.get("Retry-After",2**i)))
                    except (TypeError,ValueError): delay=float(2**i)
                    if i<3:
                        self._sleep(min(delay,60.0)); continue
                    resume=(datetime.now(timezone.utc)+timedelta(seconds=min(delay,60.0))).isoformat()
                    if self.request_budget is not None:
                        self.request_budget.mark_pause("provider_rate_limit",resume_after=resume,status_code=429)
                    raise BlockfrostPauseRequired(
                        "provider_rate_limit",
                        "Blockfrost limite temporairement le débit (HTTP 429)",
                        resume_after=resume,status_code=429,
                        usage=self.request_budget.snapshot() if self.request_budget else {},
                    )
                if r.status_code==404: raise BlockfrostError(f'Blockfrost 404: {path}')
                r.raise_for_status(); return r.json()
            except BlockfrostError: raise
            except requests.RequestException as exc:
                last=exc
                if not response_received and self.request_budget is not None:
                    self.request_budget.record(path,None)
                if i<3: self._sleep(i+1)
        raise BlockfrostError(str(last or 'Blockfrost request failed'))

    def _paged(self,path:str,params:Optional[Dict[str,Any]]=None)->list[Any]:
        out=[]
        for page in range(1,self.max_pages+1):
            q=dict(params or {}); q.update({'page':page,'count':self.page_size})
            rows=self.get(path,q)
            if not isinstance(rows,list): raise BlockfrostError(f'Réponse paginée invalide: {path}')
            out.extend(rows)
            if len(rows)<self.page_size: return out
        raise BlockfrostError(f'Pagination > API_MAX_PAGES ({self.max_pages}) pour {path}')

    def health(self):
        try: return {'ok':True,'source':'blockfrost','epoch':int(self.epoch()['epoch'])}
        except Exception as exc: return {'ok':False,'source':'blockfrost','error':str(exc)}
    def epoch(self): return self.get('/epochs/latest')
    def epoch_info(self,epoch): return self.get(f'/epochs/{int(epoch)}')
    def pool(self,pool_id=None):
        pid=pool_id or self.pool_id
        if not pid: raise BlockfrostError('Pool ID absent')
        return self.get(f'/pools/{pid}')
    def epoch_stakes(self,epoch,page=1,count=100,pool_id=None):
        pid=pool_id or self.pool_id; return self.get(f'/epochs/{int(epoch)}/stakes/{pid}',{'page':page,'count':count})
    def epoch_pool_blocks(self,epoch,page=1,count=100,pool_id=None):
        pid=pool_id or self.pool_id; return self.get(f'/epochs/{int(epoch)}/blocks/{pid}',{'page':page,'count':count})
    def account_rewards(self,address,page=1,count=100): return self.get(f'/accounts/{address}/rewards',{'page':page,'count':count})
    def epoch_stakes_all(self,epoch,pool_id=None):
        pid=pool_id or self.pool_id; return [x for x in self._paged(f'/epochs/{int(epoch)}/stakes/{pid}') if isinstance(x,dict)]
    def epoch_pool_blocks_all(self,epoch,pool_id=None):
        pid=pool_id or self.pool_id; return self._paged(f'/epochs/{int(epoch)}/blocks/{pid}')
    def pool_history_all(self,pool_id=None,refresh=False):
        pid=pool_id or self.pool_id
        if not refresh and pid in self._pool_history_cache: return copy.deepcopy(self._pool_history_cache[pid])
        if not refresh:
            cached=self._persistent_cache_load('pool_history',pid)
            if isinstance(cached,list):
                self._pool_history_cache[pid]=cached; return copy.deepcopy(cached)
        rows=[x for x in self._paged(f'/pools/{pid}/history') if isinstance(x,dict)]
        self._persistent_cache_save('pool_history',pid,rows)
        self._pool_history_cache[pid]=rows; return copy.deepcopy(rows)
    def pool_history_epoch(self,epoch,pool_id=None):
        target=int(epoch)
        for row in self.pool_history_all(pool_id):
            try:
                if int(row.get('epoch'))==target: return copy.deepcopy(row)
            except (TypeError,ValueError): pass
        return {}
    def pool_delegators(self, pool_id=None, page=1, count=100, order="asc"):
        pid = pool_id or self.pool_id
        if not pid:
            raise BlockfrostError("Pool ID absent")
        return self.get(
            f"/pools/{pid}/delegators",
            {"page": int(page), "count": int(count), "order": str(order)},
        )

    def pool_blocks(self, pool_id=None, page=1, count=100, order='desc'):
        pid = pool_id or self.pool_id
        if not pid:
            raise BlockfrostError('Pool ID absent')
        return self.get(
            f'/pools/{pid}/blocks',
            {'page': int(page), 'count': int(count), 'order': str(order)},
        )

    def drep_votes(self, drep_id, page=1, count=100, order="desc"):
        if not drep_id:
            raise BlockfrostError("DRep ID absent")
        return self.get(
            f"/governance/dreps/{drep_id}/votes",
            {"page": int(page), "count": int(count), "order": str(order)},
        )

    def governance_proposal(self, tx_hash, cert_index):
        value = self.get(f"/governance/proposals/{tx_hash}/{int(cert_index)}")
        return value if isinstance(value, dict) else {}

    def transaction(self, tx_hash):
        value = self.get(f"/txs/{tx_hash}")
        return value if isinstance(value, dict) else {}

    def pool_updates_all(self,pool_id=None):
        pid=pool_id or self.pool_id; return [x for x in self._paged(f'/pools/{pid}/updates') if isinstance(x,dict)]
    def tx_pool_updates(self,tx_hash):
        rows=self.get(f'/txs/{tx_hash}/pool_updates'); return rows if isinstance(rows,list) else []
    def pool_registration_history(self,pool_id=None,refresh=False):
        pid=pool_id or self.pool_id
        if not refresh and pid in self._pool_registration_cache: return copy.deepcopy(self._pool_registration_cache[pid])
        if not refresh:
            cached=self._persistent_cache_load('pool_registration',pid)
            if isinstance(cached,list):
                self._pool_registration_cache[pid]=cached; return copy.deepcopy(cached)
        certs=[]
        for update in self.pool_updates_all(pid):
            tx=str(update.get('tx_hash') or ''); idx=update.get('cert_index')
            if not tx: continue
            for cert in self.tx_pool_updates(tx):
                if not isinstance(cert,dict) or str(cert.get('pool_id') or '')!=pid: continue
                if idx is not None and cert.get('cert_index') is not None:
                    try:
                        if int(cert['cert_index'])!=int(idx): continue
                    except (TypeError,ValueError): pass
                # Merge endpoint metadata (notably active_epoch) with the full
                # transaction certificate. Certificate fields win.
                c=copy.deepcopy(update); c.update(copy.deepcopy(cert)); c['tx_hash']=tx; c['action']=update.get('action'); certs.append(c)
        certs.sort(key=lambda x:(int(x.get('active_epoch',-1) or -1),str(x.get('tx_hash','')),int(x.get('cert_index',0) or 0)))
        self._persistent_cache_save('pool_registration',pid,certs)
        self._pool_registration_cache[pid]=certs; return copy.deepcopy(certs)
    def pool_registration_at_epoch(self,epoch,pool_id=None):
        target=int(epoch); eligible=[]
        for cert in self.pool_registration_history(pool_id):
            try:
                if int(cert.get('active_epoch'))<=target: eligible.append(cert)
            except (TypeError,ValueError): pass
        return copy.deepcopy(eligible[-1]) if eligible else {}
    def block(self,block_hash):
        value=self.get(f'/blocks/{block_hash}'); return value if isinstance(value,dict) else {}
    def epoch_pool_block_details(self,epoch,pool_id=None):
        result=[]
        for item in self.epoch_pool_blocks_all(epoch,pool_id):
            if isinstance(item,str): h=item
            elif isinstance(item,dict): h=str(item.get('hash') or '')
            else: h=''
            if not h: continue
            # Do not normalize/add aliases: canonical_block reproduces legacy.
            result.append(self.block(h))
        result.sort(key=lambda x:int(x.get('height') or 0)); return result
    def account_history(self,address,page=1,count=100):
        return self.get(f'/accounts/{address}/history',{'page':page,'count':count})
    def account_history_all(self,address,refresh=False):
        if not refresh and address in self._account_history_cache:
            return copy.deepcopy(self._account_history_cache[address])
        if not refresh:
            cached=self._persistent_cache_load('account_history',address)
            if isinstance(cached,list):
                self._account_history_cache[address]=cached; return copy.deepcopy(cached)
        rows=[x for x in self._paged(f'/accounts/{address}/history') if isinstance(x,dict)]
        self._persistent_cache_save('account_history',address,rows)
        self._account_history_cache[address]=rows
        return copy.deepcopy(rows)
    def account_history_at_epoch(self,address,epoch):
        target=int(epoch)
        for row in self.account_history_all(address):
            try:
                if int(row.get('active_epoch'))==target:
                    return copy.deepcopy(row)
            except (TypeError,ValueError):
                continue
        return {}
    def account_delegations(self,address,page=1,count=100):
        return self.get(f'/accounts/{address}/delegations',{'page':page,'count':count})
    def account_delegations_all(self,address,refresh=False):
        if not refresh and address in self._delegation_cache:
            return copy.deepcopy(self._delegation_cache[address])
        if not refresh:
            cached=self._persistent_cache_load('account_delegations',address)
            if isinstance(cached,list):
                self._delegation_cache[address]=cached; return copy.deepcopy(cached)
        rows=[x for x in self._paged(f'/accounts/{address}/delegations') if isinstance(x,dict)]
        rows.sort(key=lambda x:(int(x.get('active_epoch',-1) or -1),str(x.get('tx_hash') or '')))
        self._persistent_cache_save('account_delegations',address,rows)
        self._delegation_cache[address]=rows
        return copy.deepcopy(rows)
    def delegated_pool_at_epoch(self,address,epoch):
        """Return the pool whose delegation is active at *epoch*.

        Delegation history is event based, not one row per epoch.  The active
        pool at N is therefore the last delegation certificate whose
        active_epoch <= N.
        """
        target=int(epoch); eligible=[]
        for row in self.account_delegations_all(address):
            try:
                if int(row.get('active_epoch'))<=target:
                    eligible.append(row)
            except (TypeError,ValueError):
                continue
        return copy.deepcopy(eligible[-1]) if eligible else {}
    def account_registrations(self,address,page=1,count=100):
        return self.get(f'/accounts/{address}/registrations',{'page':page,'count':count})
    def _stake_registration_event_epoch(self,row):
        """Resolve the blockchain epoch containing a stake registration event.

        Blockfrost registration rows carry transaction/block metadata but not
        always an explicit epoch.  Prefer any epoch already present, otherwise
        resolve the block height/hash.  This is cached by
        account_registrations_all(), so it is not repeated for every replay
        epoch.
        """
        for key in ('_cspoe_tx_epoch','resolved_tx_epoch','tx_epoch','epoch'):
            try:
                if row.get(key) is not None:
                    return int(row.get(key))
            except (TypeError,ValueError):
                pass
        block_ref=row.get('block_height') or row.get('block')
        if block_ref is None and row.get('tx_hash'):
            tx=self.get(f"/txs/{row.get('tx_hash')}")
            if isinstance(tx,dict):
                block_ref=tx.get('block') or tx.get('block_height')
        if block_ref is None:
            raise BlockfrostError(f"Epoch du certificat stake introuvable: {row.get('tx_hash')}")
        block=self.block(block_ref)
        try:
            return int(block.get('epoch'))
        except (TypeError,ValueError):
            raise BlockfrostError(f"Epoch de bloc invalide pour certificat stake: {row.get('tx_hash')}")
    def account_registrations_all(self,address,refresh=False):
        cache=getattr(self,'_stake_registration_cache',None)
        if cache is None:
            self._stake_registration_cache={}
            cache=self._stake_registration_cache
        if not refresh and address in cache:
            return copy.deepcopy(cache[address])
        if not refresh:
            cached=self._persistent_cache_load('account_registrations',address)
            if isinstance(cached,list):
                cache[address]=cached; return copy.deepcopy(cached)
        rows=[x for x in self._paged(f'/accounts/{address}/registrations') if isinstance(x,dict)]
        enriched=[]
        for row in rows:
            item=copy.deepcopy(row)
            item['_cspoe_tx_epoch']=self._stake_registration_event_epoch(item)
            enriched.append(item)
        enriched.sort(key=lambda x:(
            int(x.get('_cspoe_tx_epoch',-1) or -1),
            int(x.get('block_height',-1) or -1),
            int(x.get('tx_slot',-1) or -1),
            str(x.get('tx_hash') or ''),
        ))
        self._persistent_cache_save('account_registrations',address,enriched)
        cache[address]=enriched
        return copy.deepcopy(enriched)
    def stake_registration_event_at_epoch(self,address,epoch):
        """Return the last stake registration/deregistration certificate included by N.

        Important: this is the certificate inclusion epoch, not a claim that
        its effect is visible in `/epochs/N/stakes`.  complete_epoch_stakes()
        consults it only when the address is already absent from that
        authoritative epoch distribution. This preserves API-observed delayed
        effects where a certificate can precede disappearance from snapshots.
        """
        target=int(epoch); eligible=[]
        for row in self.account_registrations_all(address):
            try:
                if int(row.get('_cspoe_tx_epoch'))<=target:
                    eligible.append(row)
            except (TypeError,ValueError):
                continue
        return copy.deepcopy(eligible[-1]) if eligible else {}
    @staticmethod
    def _stake_registration_state(event):
        if not isinstance(event,dict) or not event:
            return None
        action=str(event.get('action') or '').strip().lower()
        if action in ('deregistered','deregister','unregistered','unregister'):
            return False
        if action in ('registered','register'):
            return True
        if event.get('registration') is False:
            return False
        if event.get('registration') is True:
            return True
        return None
    def stake_key_registered_at_epoch(self,address,epoch):
        return self._stake_registration_state(self.stake_registration_event_at_epoch(address,epoch))
    @staticmethod
    def _insert_missing_by_previous_order(rows,missing_rows,previous_order):
        """Insert recovered holders without disturbing Blockfrost's raw order.

        The old API kept zero-stake holders in the epoch pool distribution.
        Current historical responses may omit them.  For a recovered address we
        place it relative to surviving neighbours from the previous epoch, which
        reproduces the stable holder order used by legacy setDelegsIndex.
        """
        out=[copy.deepcopy(x) for x in rows if isinstance(x,dict)]
        if not missing_rows:
            return out
        def addr(x): return str(x.get('stake_address') or x.get('address') or '')
        for recovered in missing_rows:
            a=addr(recovered)
            if not a or any(addr(x)==a for x in out):
                continue
            try: pos=previous_order.index(a)
            except ValueError:
                out.append(copy.deepcopy(recovered)); continue
            prevs=list(reversed(previous_order[:pos])); nexts=previous_order[pos+1:]
            inserted=False
            # Prefer the previous successor so the recovered row keeps its exact
            # legacy position when following rows survived.
            for n in nexts:
                for i,x in enumerate(out):
                    if addr(x)==n:
                        out.insert(i,copy.deepcopy(recovered)); inserted=True; break
                if inserted: break
            if inserted: continue
            for q in prevs:
                for i,x in enumerate(out):
                    if addr(x)==q:
                        out.insert(i+1,copy.deepcopy(recovered)); inserted=True; break
                if inserted: break
            if not inserted: out.append(copy.deepcopy(recovered))
        return out
    def complete_epoch_stakes(self,epoch,raw_stakes,previous_delegators=None,owner_addresses=None,pool_id=None):
        """Recover only *true* zero-stake holders omitted by current Blockfrost.

        Decision for an address present in N-1 but absent from
        `/epochs/N/stakes/{pool}`:

        1. last delegation event active at N must still point to this pool;
        2. if the last stake-key registration event already included by N is a
           deregistration, the absence is a real departure and the address is
           NOT reinserted;
        3. otherwise the address is preserved with amount=0.

        The registration gate is evaluated only for addresses *missing* from
        the epoch stake distribution.  Therefore a deregistration certificate
        included in epoch 498 does not erase a holder that Blockfrost still
        still reports in later snapshots; it only prevents a false zero-stake
        recovery once the holder actually disappears.
        """
        ep=int(epoch); pid=pool_id or self.pool_id
        rows=[copy.deepcopy(x) for x in (raw_stakes or []) if isinstance(x,dict)]
        existing={str(x.get('stake_address') or x.get('address') or '') for x in rows}
        previous_order=[str(x) for x in (previous_delegators or []) if x]
        candidates=[]
        for a in previous_order + [str(x) for x in (owner_addresses or []) if x]:
            if a and a not in existing and a not in candidates:
                candidates.append(a)
        recovered_deleg=[]; recovered_owner=[]; rejected=[]
        owner_set=set(str(x) for x in (owner_addresses or []) if x)
        for address in candidates:
            delegation=self.delegated_pool_at_epoch(address,ep)
            delegated_pool=str(delegation.get('pool_id') or '')
            if delegated_pool != str(pid):
                rejected.append({
                    'stake_address':address,
                    'reason':'delegated_elsewhere_or_no_delegation',
                    'delegated_pool':delegated_pool or None,
                    'delegation_active_epoch':delegation.get('active_epoch') if isinstance(delegation,dict) else None,
                })
                continue
            registration_event=self.stake_registration_event_at_epoch(address,ep)
            registration_state=self._stake_registration_state(registration_event)
            if registration_state is False:
                rejected.append({
                    'stake_address':address,
                    'reason':'stake_key_deregistered',
                    'delegated_pool':delegated_pool,
                    'delegation_active_epoch':delegation.get('active_epoch') if isinstance(delegation,dict) else None,
                    'registration_action':registration_event.get('action'),
                    'registration_tx_epoch':registration_event.get('_cspoe_tx_epoch'),
                    'registration_tx_hash':registration_event.get('tx_hash'),
                })
                continue
            row={'stake_address':address,'pool_id':pid,'amount':'0'}
            if address in owner_set:
                recovered_owner.append(row)
            else:
                recovered_deleg.append(row)
        rows=self._insert_missing_by_previous_order(rows,recovered_deleg,previous_order)
        for row in recovered_owner:
            if str(row['stake_address']) not in {str(x.get('stake_address') or '') for x in rows}:
                rows.append(row)
        return rows,{
            'raw_count':len(raw_stakes or []),
            'completed_count':len(rows),
            'recovered_zero_holders':[str(x['stake_address']) for x in recovered_deleg+recovered_owner],
            'recovery_source':'delegation_events_plus_stake_registration_state',
            'missing_candidates_rejected':rejected,
        }
    def account_rewards_all(self,address,refresh=False):
        if not refresh and address in self._reward_cache: return copy.deepcopy(self._reward_cache[address])
        if not refresh:
            cached=self._persistent_cache_load('account_rewards',address)
            if isinstance(cached,list):
                self._reward_cache[address]=cached; return copy.deepcopy(cached)
        rows=[x for x in self._paged(f'/accounts/{address}/rewards') if isinstance(x,dict)]
        self._persistent_cache_save('account_rewards',address,rows)
        self._reward_cache[address]=rows; return copy.deepcopy(rows)
    def reward_for_epoch(self,address,epoch,pool_id=None)->int:
        """Exact legacy getRewards semantics: scan from the end, return last match."""
        target=int(epoch); pid=pool_id or self.pool_id
        rows=self.account_rewards_all(address)
        for row in reversed(rows):
            try:
                if int(row.get('epoch'))!=target: continue
            except (TypeError,ValueError): continue
            # Legacy getRewards filtered only by epoch, not by pool_id.
            try: return int(row.get('amount',0) or 0)
            except (TypeError,ValueError): return 0
        return 0
    def rewards_by_stake_for_epoch(self,addresses:Iterable[str],epoch,pool_id=None):
        return {a:self.reward_for_epoch(a,int(epoch),pool_id) for a in dict.fromkeys(str(x) for x in addresses if x)}
    def closed_epoch_evidence(self,epoch:int,observed_epoch:Optional[int]=None,pool_id=None,previous_delegators=None,previous_owners=None):
        pid=pool_id or self.pool_id; ep=int(epoch)
        raw_stakes=self.epoch_stakes_all(ep,pid)
        registration=self.pool_registration_at_epoch(ep,pid)
        if not registration:
            raise BlockfrostError(f'Certificat de pool actif introuvable pour epoch {ep}')
        owner_addresses=list(map(str,registration.get('owners') or []))
        if not owner_addresses:
            raise BlockfrostError(f'Owners historiques introuvables pour epoch {ep}')
        all_stakes,stake_completion=self.complete_epoch_stakes(
            ep,raw_stakes,previous_delegators=previous_delegators,
            owner_addresses=owner_addresses,pool_id=pid,
        )
        blocks=self.epoch_pool_block_details(ep,pid)
        addresses=[str(x.get('stake_address') or '') for x in all_stakes if x.get('stake_address')]
        rewards=self.rewards_by_stake_for_epoch(addresses,ep,pid)
        return {
            'source':'blockfrost','epoch':ep,
            'observed_epoch':int(observed_epoch) if observed_epoch is not None else None,
            'epoch_info':self.epoch_info(ep),'pool_history':self.pool_history_epoch(ep,pid),
            'pool_registration':registration,'pool_registration_exact':True,
            'all_stakes':all_stakes,'owner_addresses':owner_addresses,'stake_completion':stake_completion,
            'blocks':blocks,'rewards_by_stake':rewards,
        }
