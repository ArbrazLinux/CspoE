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
import os,sys,tempfile,json
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from notifications.cip8_verification import verify_cip8_cardano_signer,CIP8VerificationError,cardano_signer_version

with tempfile.TemporaryDirectory() as d:
    f=Path(d)/'cardano-signer'
    f.write_text('''#!/usr/bin/env python3\nimport json,sys\na=sys.argv[1:]\nif "--version" in a: print("cardano-signer 1.35.0"); raise SystemExit(0)\nif a and a[0]=="version": print("cardano-signer 1.35.0"); raise SystemExit(0)\nif a[:2]==["verify","--cip8"]:\n data=a[a.index("--data")+1]; addr=a[a.index("--address")+1]\n ok=(data=="TEST-challenge" and addr.startswith("stake1"))\n print(json.dumps({"result":"true" if ok else "false","publicKey":"ab"*32}))\n raise SystemExit(0 if ok else 1)\nraise SystemExit(2)\n''')
    f.chmod(0o755)
    assert cardano_signer_version(str(f))=='1.35.0'
    r=verify_cip8_cardano_signer(stake_address='stake1'+'q'*30,expected_payload='TEST-challenge',cose_sign1_hex='84',cose_key_hex='a4',binary=str(f),required_version='1.35.0')
    assert r.backend=='cardano-signer' and r.backend_version=='1.35.0'
    try:
        verify_cip8_cardano_signer(stake_address='stake1'+'q'*30,expected_payload='tampered',cose_sign1_hex='84',cose_key_hex='a4',binary=str(f),required_version='1.35.0')
        raise AssertionError('tampered payload accepted')
    except CIP8VerificationError: pass
    try:
        verify_cip8_cardano_signer(stake_address='stake1'+'q'*30,expected_payload='TEST-challenge',cose_sign1_hex='84',cose_key_hex='a4',binary=str(f),required_version='9.9.9')
        raise AssertionError('wrong version accepted')
    except CIP8VerificationError: pass
print('OK - cardano-signer v1.35.0 backend + payload/address argv + version pin + failure handling')
