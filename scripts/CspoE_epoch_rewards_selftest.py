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

from notifications.events import derive_events
from notifications.templates import render
from notifications.watcher import TelegramWatcher


def snap(epoch:int, *, stake:int=100_000_000_000, prev_stake:int=90_000_000_000, delegs:int=10, prev_delegs:int=9, blocks:int=1, rewards:int=0, owners:int=0, delegator_rewards:int=0):
    return {
        'epoch': epoch,
        'pool': {'stake': {'_epoch_':stake,'_previous_':prev_stake,'_diff_':stake-prev_stake}, 'rewards': {'_epoch_':rewards}},
        'owners': {'rewards': {'_epoch_':owners}, 'owner':[{'stake_address':'stake1owner','rewards':{'_epoch_':owners}}] if owners else []},
        'delegators': {'delegsNb':delegs,'previous_delegsNb':prev_delegs,'rewards':{'_epoch_':delegator_rewards},'delegator':[{'stake_address':'stake1a','stake':{'_epoch_':stake//2},'rewards':{'_epoch_':delegator_rewards}}] if delegator_rewards else []},
        'blocks': {'epoch':blocks,'block':[]},
    }

# Enriched epoch summary deliberately excludes rewards.
events=derive_events(snap(651, blocks=2, rewards=123_000_000), snap(652))
e=[x for x in events if x.kind=='new_epoch'][0]
text=render(e,ticker='TEST')
assert 'Bilan de l’epoch <b>651</b>' in text, text
assert 'Blocs produits : <b>2</b>' in text, text
assert 'Délégateurs : <b>10</b> · +1' in text, text
assert 'rewards seront annoncées séparément' in text, text
assert '123' not in text, text

with tempfile.TemporaryDirectory() as td:
    root=Path(td); epochs=root/'epochs'; epochs.mkdir(); notes=root/'notifications'; notes.mkdir()
    previous=root/'previous.json'; current=root/'current.json'; manager=root/'epoch_manager_state.json'
    previous.write_text(json.dumps(snap(651)),encoding='utf-8')
    current.write_text(json.dumps(snap(652)),encoding='utf-8')
    # 650 was already settled before feature installation: must become silent baseline.
    (epochs/'epoch_650.json').write_text(json.dumps(snap(650,rewards=300_000_000,owners=200_000_000,delegator_rewards=100_000_000)),encoding='utf-8')
    manager.write_text(json.dumps({'last_rewards_settled_epoch':650}),encoding='utf-8')
    watcher=TelegramWatcher(ticker='TEST',token='x',chat_id='@test',state_file=notes/'telegram_state.json')
    class FakeClient:
        def __init__(self): self.sent=[]
        def send_message(self, text): self.sent.append(text)
    watcher.client=FakeClient()
    r=watcher.run(previous,current,epoch_manager_state_file=manager,epochs_dir=epochs)
    assert r['rewards']['bootstrap'] is True, r
    assert not any(m['kind']=='rewards_settled' for m in r['messages']), r
    assert json.loads((notes/'telegram_state.json').read_text())['last_rewards_settled_epoch']==650

    # Epoch 651 settles with zero rewards: cursor advances silently.
    (epochs/'epoch_651.json').write_text(json.dumps(snap(651,blocks=0,rewards=0)),encoding='utf-8')
    manager.write_text(json.dumps({'last_rewards_settled_epoch':651}),encoding='utf-8')
    r=watcher.run(previous,current,epoch_manager_state_file=manager,epochs_dir=epochs)
    assert r['rewards']['suppressed_zero_epochs']==[651], r
    assert not any(m['kind']=='rewards_settled' for m in r['messages']), r
    assert json.loads((notes/'telegram_state.json').read_text())['last_rewards_settled_epoch']==651

    # Epoch 652 settles with actual rewards: exactly one dedicated notification.
    (epochs/'epoch_652.json').write_text(json.dumps(snap(652,blocks=1,rewards=250_000_000,owners=175_000_000,delegator_rewards=75_000_000)),encoding='utf-8')
    manager.write_text(json.dumps({'last_rewards_settled_epoch':652}),encoding='utf-8')
    r=watcher.run(previous,current,epoch_manager_state_file=manager,epochs_dir=epochs)
    rm=[m for m in r['messages'] if m['kind']=='rewards_settled']
    assert len(rm)==1, r
    assert 'epoch <b>652</b>' in rm[0]['text'] and '250.00 ₳' in rm[0]['text'], rm
    # Same settled epoch must be deduplicated.
    r2=watcher.run(previous,current,epoch_manager_state_file=manager,epochs_dir=epochs)
    assert not any(m['kind']=='rewards_settled' for m in r2['messages']), r2

print('OK - enriched epoch summary + delayed rewards settlement + zero suppression + dedup')
