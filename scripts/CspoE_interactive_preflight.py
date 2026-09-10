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
import argparse, json, os, sqlite3, stat, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.config import CONF_PATH, get_setting, settings
from notifications.cip8_verification import cardano_signer_version, CIP8VerificationError
from notifications.subscribers import SubscriberStore

def b(name, default=False):
    return str(get_setting(name,'1' if default else '0')).strip().lower() in {'1','true','yes','on'}
def i(name, default):
    try:return int(get_setting(name,str(default)) or default)
    except Exception:return default

def check(*, initialize_db:bool=True)->dict:
    checks=[]
    def add(key,ok,detail,critical=True):checks.append({'key':key,'ok':bool(ok),'detail':str(detail),'critical':bool(critical)})
    enabled=b('CSPOE_TELEGRAM_INTERACTIVE_ENABLED',False)
    add('interactive_enabled',enabled,'enabled' if enabled else 'disabled',True)
    token=get_setting('TELEGRAM_BOT_TOKEN')
    add('telegram_token',bool(token),'présent' if token else 'absent',True)
    add('pool_id',bool(settings.pool_id),settings.pool_id or 'absent',True)
    backend=(get_setting('CSPOE_CIP8_VERIFY_BACKEND','cardano-signer') or '').strip().lower()
    add('cip8_backend',backend in {'cardano-signer','cardano_signer','signer'},backend or 'absent',True)
    require=b('CSPOE_TELEGRAM_REQUIRE_OWNERSHIP_VERIFICATION',True)
    add('ownership_required',require,'obligatoire' if require else 'désactivée',True)
    ttl=i('CSPOE_TELEGRAM_CIP8_CHALLENGE_TTL_SECONDS',600)
    add('challenge_ttl',60 <= ttl <= 3600,f'{ttl}s',True)
    signer=get_setting('CSPOE_CARDANO_SIGNER','/usr/local/bin/cardano-signer')
    expected=get_setting('CSPOE_CARDANO_SIGNER_REQUIRED_VERSION','1.35.0')
    try:
        version=cardano_signer_version(signer)
        add('cardano_signer',version==expected,f'{signer} version={version}, attendue={expected}',True)
    except Exception as exc:add('cardano_signer',False,str(exc),True)
    if CONF_PATH and CONF_PATH.exists():
        mode=stat.S_IMODE(CONF_PATH.stat().st_mode)
        secure=(mode & 0o077)==0
        add('config_permissions',secure,f'{CONF_PATH} mode={mode:03o}',True)
    else:add('config_permissions',False,'CspoE.conf introuvable',True)
    dbp=Path(get_setting('CSPOE_TELEGRAM_SUBSCRIBERS_DB',str(ROOT/'data/CspoE/notifications/subscribers.sqlite3')))
    try:
        dbp.parent.mkdir(parents=True,exist_ok=True)
        if not os.access(dbp.parent,os.W_OK): raise PermissionError(f'répertoire non inscriptible: {dbp.parent}')
        if initialize_db:
            store=SubscriberStore(dbp)
            with store.connect() as db:
                row=db.execute('PRAGMA quick_check').fetchone(); qc=str(row[0]) if row else ''
            if dbp.exists(): dbp.chmod(0o600)
            add('subscriber_db',qc=='ok',f'{dbp} quick_check={qc}',True)
        else:
            add('subscriber_db',True,f'{dbp.parent} inscriptible; initialisation non demandée',True)
    except Exception as exc:add('subscriber_db',False,str(exc),True)
    failed=[x for x in checks if x['critical'] and not x['ok']]
    return {'ok':not failed,'checks_total':len(checks),'checks_failed':len(failed),'checks':checks}

def main():
    ap=argparse.ArgumentParser(description='Préflight sécurisé du bot Telegram interactif CspoE')
    ap.add_argument('--no-init-db',action='store_true')
    ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); r=check(initialize_db=not a.no_init_db)
    if a.json: print(json.dumps(r,ensure_ascii=False,indent=2))
    else:
        for c in r['checks']:print(('OK  ' if c['ok'] else 'FAIL'),c['key'], '-', c['detail'])
        print('OK - interactive preflight' if r['ok'] else 'FAIL - interactive preflight')
    return 0 if r['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
