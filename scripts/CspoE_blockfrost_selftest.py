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
import copy, sys, json, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub=types.ModuleType('requests')
    requests_stub.Session=type('Session',(),{})
    requests_stub.RequestException=type('RequestException',(Exception,),{})
    sys.modules['requests']=requests_stub
from core.blockfrost import BlockfrostClient
from core.CspoE_legacy_contract import canonical_block
from core.version import ENGINE_VERSION
from scripts.CspoE_legacy_replay import FactSource, delegator_order_only_diff

POOL='pool1test'; OTHER='pool1other'
A='stake1a'; Z='stake1zero'; D='stake1deregistered'; G='stake1gone'; B='stake1b'

class Fake(BlockfrostClient):
    def __init__(self):
        self.pool_id=POOL
        self._delegation_cache={}
        self._stake_registration_cache={}
    def account_delegations_all(self,address,refresh=False):
        if address==Z:
            return [{'active_epoch':250,'pool_id':POOL,'tx_hash':'z0'}]
        if address==D:
            # Last delegation still targets the pool after stake-key deregistration.
            return [{'active_epoch':455,'pool_id':POOL,'tx_hash':'d0'}]
        if address==G:
            return [
                {'active_epoch':250,'pool_id':POOL,'tx_hash':'g0'},
                {'active_epoch':301,'pool_id':OTHER,'tx_hash':'g1'},
            ]
        return []
    def account_registrations_all(self,address,refresh=False):
        if address==Z:
            return [{'_cspoe_tx_epoch':200,'action':'registered','tx_hash':'zr'}]
        if address==D:
            return [
                {'_cspoe_tx_epoch':330,'action':'registered','tx_hash':'dr'},
                {'_cspoe_tx_epoch':498,'action':'deregistered','tx_hash':'dd'},
            ]
        if address==G:
            return [{'_cspoe_tx_epoch':200,'action':'registered','tx_hash':'gr'}]
        return []

f=Fake()
# Historical regression: missing from current stake distribution, still
# delegated and registered -> recover as zero in the exact previous position.
raw301=[
 {'stake_address':A,'pool_id':POOL,'amount':'10'},
 {'stake_address':B,'pool_id':POOL,'amount':'20'},
]
completed,meta=f.complete_epoch_stakes(
    301,raw301,previous_delegators=[A,Z,G,B],owner_addresses=[],pool_id=POOL
)
assert [x['stake_address'] for x in completed]==[A,Z,B],completed
assert completed[1]['amount']=='0',completed
assert meta['recovered_zero_holders']==[Z],meta
assert any(x['stake_address']==G and x['reason']=='delegated_elsewhere_or_no_delegation' for x in meta['missing_candidates_rejected']),meta

# Historical regression: a deregistration certificate is already
# on-chain in 498, but while raw epoch stakes still contain D it remains present.
raw499=[
 {'stake_address':A,'pool_id':POOL,'amount':'10'},
 {'stake_address':D,'pool_id':POOL,'amount':'1099577944'},
 {'stake_address':B,'pool_id':POOL,'amount':'20'},
]
completed499,meta499=f.complete_epoch_stakes(
    499,raw499,previous_delegators=[A,D,B],owner_addresses=[],pool_id=POOL
)
assert [x['stake_address'] for x in completed499]==[A,D,B],completed499
assert meta499['recovered_zero_holders']==[],meta499

# Later it is absent from raw epoch stakes; last delegation still targets the pool,
# but last registration state is deregistered -> real departure, no zero row.
raw500=[
 {'stake_address':A,'pool_id':POOL,'amount':'10'},
 {'stake_address':B,'pool_id':POOL,'amount':'20'},
]
completed500,meta500=f.complete_epoch_stakes(
    500,raw500,previous_delegators=[A,D,B],owner_addresses=[],pool_id=POOL
)
assert [x['stake_address'] for x in completed500]==[A,B],completed500
rej=[x for x in meta500['missing_candidates_rejected'] if x['stake_address']==D]
assert rej and rej[0]['reason']=='stake_key_deregistered',meta500
assert rej[0]['registration_tx_epoch']==498,meta500

b=canonical_block({'hash':'abc','output':None,'fees':None})
assert b['output']=='0' and b['fees']=='0',b



# Cache v3 -> v4 migration must reevaluate only synthetic zero rows, without
# refetching valid blocks/rewards/owners/raw stake data.
with tempfile.TemporaryDirectory() as td:
    t=Path(td); awards=t/'awards.json'; awards.write_text('[]')
    cache=t/'epoch_500.json'
    cache.write_text(json.dumps({
        'cache_version':3,
        'all_stakes':[
            {'stake_address':A,'pool_id':POOL,'amount':'10'},
            {'stake_address':D,'pool_id':POOL,'amount':'0'},
            {'stake_address':B,'pool_id':POOL,'amount':'20'},
        ],
        'owner_addresses':[],
        'rewards_by_stake':{A:1,D:2,B:3},
        'blocks':[{'hash':'cached'}],
        'stake_completion':{'recovered_zero_holders':[D]},
    }))
    fs=FactSource(mode='blockfrost',reference={},awards_file=awards,cache_dir=t,blockfrost=f)
    facts=fs.facts(500,previous_delegators=[A,D,B],previous_owners=[])
    assert facts['cache_version']==4,facts
    assert facts.get('cache_migrated_from')==3,facts
    assert [x['stake_address'] for x in facts['all_stakes']]==[A,B],facts
    assert facts['blocks']==[{'hash':'cached'}],facts
    assert facts['rewards_by_stake']=={A:1,D:2,B:3},facts

base = {
    'epoch': 1,
    'pool': {'x': 1},
    'owners': {'owner': []},
    'delegators': {
        'delegsNb': 2,
        'delegator': [
            {'stake_address': 'stakeA', 'stake': {'_epoch_': 10}, 'rewards': {'_epoch_': 2}},
            {'stake_address': 'stakeB', 'stake': {'_epoch_': 20}, 'rewards': {'_epoch_': 3}},
        ],
    },
    'blocks': {'block': [{'hash': 'h1'}, {'hash': 'h2'}]},
    'bonuses': {},
}

# A pure Blockfrost row permutation is visible in the positional audit but is
# not a business/data mismatch because rows are indexed by stake_address.
swapped = copy.deepcopy(base)
swapped['delegators']['delegator'].reverse()
pos, data = delegator_order_only_diff(swapped, base, limit=100)
assert pos and not data, (pos, data)

# A value change on the same address remains blocking after address alignment.
changed = copy.deepcopy(swapped)
changed['delegators']['delegator'][0]['stake']['_epoch_'] = 999
_, data = delegator_order_only_diff(changed, base, limit=100)
assert data, data

# Missing, duplicate and empty identities must never be normalized away.
missing = copy.deepcopy(base)
missing['delegators']['delegator'].pop()
missing['delegators']['delegsNb'] = 1
_, data = delegator_order_only_diff(missing, base, limit=100)
assert any(x['kind'] == 'delegator_stake_address_set' for x in data), data

duplicate = copy.deepcopy(base)
duplicate['delegators']['delegator'][1]['stake_address'] = 'stakeA'
_, data = delegator_order_only_diff(duplicate, base, limit=100)
assert any(x['kind'] == 'delegator_index_duplicate_address' for x in data), data
pos, data = delegator_order_only_diff(duplicate, duplicate, limit=100)
assert not pos and any(x['kind'] == 'delegator_index_duplicate_address' for x in data), data

empty = copy.deepcopy(base)
empty['delegators']['delegator'][1]['stake_address'] = ''
_, data = delegator_order_only_diff(empty, base, limit=100)
assert any(x['kind'] == 'delegator_index_missing_address' for x in data), data

bad_count = copy.deepcopy(base)
bad_count['delegators']['delegsNb'] = 99
_, data = delegator_order_only_diff(bad_count, base, limit=100)
assert any(x['kind'] == 'delegator_count_mismatch' for x in data), data

# Lists outside delegators.delegator remain positionally strict.
blocks_swapped = copy.deepcopy(base)
blocks_swapped['blocks']['block'].reverse()
_, data = delegator_order_only_diff(blocks_swapped, base, limit=100)
assert data, data

print(
    f'OK - CspoE {ENGINE_VERSION}: zero holders + deregistration + cache v4 + legacy blocks + '
    'stake_address index + strict identity/data validation'
)
