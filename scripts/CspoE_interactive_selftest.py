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
import tempfile,sys,time
from hashlib import blake2b
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from notifications.subscribers import SubscriberStore
from notifications.personal import PersonalNotifier
from notifications.cip8_verification import verify_cip8, CIP8VerificationError
from notifications.cip8_python_fallback import cbor2

CHARSET="qpzry9x8gf2tvdw0s3jn54khce6mua7l"
def polymod(values):
    chk=1;gen=[0x3b6a57b2,0x26508e6d,0x1ea119fa,0x3d4233dd,0x2a1462b3]
    for v in values:
        top=chk>>25;chk=((chk&0x1ffffff)<<5)^v
        for i in range(5):
            if (top>>i)&1:chk^=gen[i]
    return chk
def hrp_expand(s):return [ord(x)>>5 for x in s]+[0]+[ord(x)&31 for x in s]
def convertbits(data,frombits,tobits,pad=True):
    acc=0;bits=0;ret=[];maxv=(1<<tobits)-1
    for v in data:
        acc=(acc<<frombits)|v;bits+=frombits
        while bits>=tobits:
            bits-=tobits;ret.append((acc>>bits)&maxv)
    if pad and bits:ret.append((acc<<(tobits-bits))&maxv)
    return ret
def bech32(hrp,raw):
    data=convertbits(raw,8,5,True);vals=hrp_expand(hrp)+data+[0]*6;pm=polymod(vals)^1
    chk=[(pm>>5*(5-i))&31 for i in range(6)]
    return hrp+'1'+''.join(CHARSET[x] for x in data+chk)

class N(PersonalNotifier):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.out=[]
    def _send(self,rec,address,key,text):
        uid=int(rec['telegram_user_id'])
        if self.store.was_delivered(uid,address,key):return False
        self.out.append((uid,address,key,text));self.store.mark_delivered(uid,address,key);return True

def snap(addr,reward):return {'epoch':650,'delegators':{'delegator':[{'stake_address':addr,'rewards':{'_epoch_':reward}}]},'owners':{'owner':[]}}

with tempfile.TemporaryDirectory() as d:
    s=SubscriberStore(Path(d)/'s.db'); s.upsert_user(1,101,'u','U')
    priv=Ed25519PrivateKey.generate();pub=priv.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    cred=blake2b(pub,digest_size=28).digest(); raw=bytes([0xE1])+cred; a=bech32('stake',raw)
    s.add_binding(1,a,True)
    assert not s.bindings(1)[0]['ownership_verified']
    assert s.recipients_for(a,'reward_alert')==[]
    ch=s.create_challenge(1,a,ttl_seconds=600,ticker='TEST')
    protected=cbor2.dumps({1:-8,'address':raw});payload=ch['payload'].encode()
    sig_struct=cbor2.dumps(['Signature1',protected,b'',payload]);sig=priv.sign(sig_struct)
    sign1=cbor2.dumps([protected,{},payload,sig]).hex();key=cbor2.dumps({1:1,3:-8,-1:6,-2:pub}).hex()
    result=verify_cip8(stake_address=a,expected_payload=ch['payload'],cose_sign1_hex=sign1,cose_key_hex=key,backend='python')
    assert result.key_hash_hex==cred.hex()
    assert s.consume_challenge(1,a);assert not s.consume_challenge(1,a)
    assert s.mark_ownership_verified(1,a,'CIP-8')
    assert s.bindings(1)[0]['ownership_verified']==1
    assert len(s.recipients_for(a,'reward_alert'))==1
    try:
        verify_cip8(stake_address=a,expected_payload=ch['payload']+'x',cose_sign1_hex=sign1,cose_key_hex=key,backend='python')
        raise AssertionError('payload mismatch accepted')
    except CIP8VerificationError:pass
    assert s.prefs(1)=={'reward_alert':True,'stake_alert':True}
    n=N(store=s,token='x',ticker='TEST')
    assert n.notify_rewards(settled_epoch=650,snapshot=snap(a,12_000_000))==1
    assert n.notify_rewards(settled_epoch=650,snapshot=snap(a,12_000_000))==0
    assert n.notify_stake_change(address=a,before=100_000_000,after=150_000_000,event_key='stake:x')==1
    assert n.notify_stake_change(address=a,before=100_000_000,after=150_000_000,event_key='stake:x')==0
    s.set_pref(1,'stake_alert',False)
    assert n.notify_stake_change(address=a,before=150_000_000,after=160_000_000,event_key='stake:y')==0
    assert s.remove_binding(1,a)
print('OK - interactive SQLite + CIP-8 ownership + challenge expiry/one-shot + verified personal delivery')
