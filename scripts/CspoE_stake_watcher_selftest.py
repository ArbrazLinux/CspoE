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
import json, tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from notifications.stake_watcher import StakeDelegatorWatcher

M=1_000_000
class BF:
    def __init__(self,snaps,epoch=649): self.snaps=snaps; self.i=0; self.current_epoch=epoch
    def pool_delegators(self,pool_id=None,page=1,count=100,order='asc'):
        rows=self.snaps[self.i][0]; return rows if page==1 else []
    def pool(self,pool_id=None): return {'live_stake':str(self.snaps[self.i][1])}
    def epoch(self): return {'epoch':self.current_epoch}
class TG:
    def __init__(self): self.msg=[]
    def send_message(self,t): self.msg.append(t); return {'ok':True}

def reward_archive(root:Path, epoch:int, rewards:dict[str,int]):
    rows=[]
    for addr,ada in rewards.items():
        rows.append({'stake_address':addr,'rewards':{'_epoch_':ada*M}})
    snap={'epoch':epoch,'pool':{'rewards':{'_epoch_':sum(rewards.values())*M}},
          'owners':{'owner':[]},'delegators':{'delegator':rows}}
    (root/f'epoch_{epoch}.json').write_text(json.dumps(snap),encoding='utf-8')

def main():
    A='stake1aaa';B='stake1bbb';C='stake1ccc';D='stake1ddd'
    # Existing intelligent grouping behavior.
    snaps=[([{'address':A,'live_stake':'100000000'},{'address':B,'live_stake':'200000000'}],300000000),
           ([{'address':A,'live_stake':'125000000'},{'address':C,'live_stake':'50000000'}],175000000),
           ([{'address':A,'live_stake':'125000000'},{'address':C,'live_stake':'60000000'}],205000000)]
    with tempfile.TemporaryDirectory() as td:
        bf=BF(snaps);tg=TG();p=Path(td)/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=p,blockfrost=bf,telegram=tg,
                                 delegator_change_threshold_lovelace=10*M,pool_change_threshold_lovelace=20*M,
                                 group_tolerance_lovelace=10*M,reward_correlation_enabled=False,stake_transfer_enabled=False)
        r=w.run(); assert r['bootstrap'] and r['pending']==0
        bf.i=1; r=w.run(); assert r['pending']==1 and r['grouped'], r
        r=w.run(); assert r['pending']==0
        bf.i=2; r=w.run(); assert not r['grouped'] and r['attribution_residual']==20*M, r
        assert r['pending']==2, r
        w2=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1other',state_file=p,blockfrost=bf,telegram=tg,reward_correlation_enabled=False,stake_transfer_enabled=False)
        r=w2.run(); assert r['bootstrap'] and r['pool_changed'] and r['pending']==0

    # Stake-address transfer: leave first, then near-identical join within 3h -> one public transfer.
    with tempfile.TemporaryDirectory() as td:
        clock=[1000]
        now=lambda: clock[0]
        snaps=[([{'address':A,'live_stake':str(100*M)},{'address':B,'live_stake':str(200*M)}],300*M),
               ([{'address':B,'live_stake':str(200*M)}],200*M),
               ([{'address':B,'live_stake':str(200*M)},{'address':C,'live_stake':str(98*M)}],298*M)]
        bf=BF(snaps);tg=TG();state=Path(td)/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=state,blockfrost=bf,telegram=tg,
            delegator_change_threshold_lovelace=1*M,pool_change_threshold_lovelace=1*M,
            reward_correlation_enabled=False,stake_transfer_enabled=True,stake_transfer_window_seconds=3*3600,
            stake_transfer_tolerance_lovelace=5*M,now=now)
        assert w.run()['bootstrap']
        bf.i=1;clock[0]+=600
        r=w.run(); assert r['pending']==0 and r['stake_address_transfer']['pending_leaves']==1, r
        assert tg.msg==[], r
        bf.i=2;clock[0]+=1800
        r=w.run(); assert r['stake_address_transfer']['matched']==1, r
        assert r['pending']==1 and r['messages'][0]['kind']=='transfer', r
        assert r['messages'][0]['from_address']==A and r['messages'][0]['to_address']==C, r
        assert len(tg.msg)==1 and 'Transfert de stake' in tg.msg[0], tg.msg

    # Symmetric order: join first, old address disappears later.
    with tempfile.TemporaryDirectory() as td:
        clock=[2000];now=lambda:clock[0]
        snaps=[([{'address':A,'live_stake':str(100*M)}],100*M),
               ([{'address':A,'live_stake':str(100*M)},{'address':C,'live_stake':str(102*M)}],202*M),
               ([{'address':C,'live_stake':str(102*M)}],102*M)]
        bf=BF(snaps);tg=TG();state=Path(td)/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=state,blockfrost=bf,telegram=tg,
            reward_correlation_enabled=False,stake_transfer_enabled=True,stake_transfer_window_seconds=3*3600,
            stake_transfer_tolerance_lovelace=5*M,now=now)
        assert w.run()['bootstrap']
        bf.i=1;clock[0]+=300;r=w.run();assert r['pending']==0 and r['stake_address_transfer']['pending_joins']==1,r
        bf.i=2;clock[0]+=900;r=w.run();assert r['pending']==1 and r['messages'][0]['kind']=='transfer',r

    # Non-matching amounts stay pending, then expire into ordinary leave + join.
    with tempfile.TemporaryDirectory() as td:
        clock=[3000];now=lambda:clock[0]
        snaps=[([{'address':A,'live_stake':str(100*M)}],100*M),
               ([],0),
               ([{'address':C,'live_stake':str(90*M)}],90*M)]
        bf=BF(snaps);tg=TG();state=Path(td)/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=state,blockfrost=bf,telegram=tg,
            reward_correlation_enabled=False,stake_transfer_enabled=True,stake_transfer_window_seconds=3600,
            stake_transfer_tolerance_lovelace=5*M,now=now)
        assert w.run()['bootstrap']
        bf.i=1;clock[0]+=60;assert w.run()['pending']==0
        bf.i=2;clock[0]+=60;assert w.run()['pending']==0
        clock[0]+=3601;r=w.run();assert r['stake_address_transfer']['matched']==0,r
        kinds=sorted(m['kind'] for m in r['messages']);assert kinds==['join','leave'],r

    # Reward batch: 4 simultaneous reward-shaped changes must produce zero Telegram posts.
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); epochs=root/'epochs';epochs.mkdir(); manager=root/'epoch_manager_state.json'
        manager.write_text(json.dumps({'last_rewards_settled_epoch':650}),encoding='utf-8')
        reward_archive(epochs,650,{A:10,B:20,C:30,D:40})
        base=[{'address':A,'live_stake':str(100*M)},{'address':B,'live_stake':str(200*M)},
              {'address':C,'live_stake':str(300*M)},{'address':D,'live_stake':str(400*M)}]
        rewarded=[{'address':A,'live_stake':str(110*M)},{'address':B,'live_stake':str(220*M)},
                  {'address':C,'live_stake':str(330*M)},{'address':D,'live_stake':str(440*M)}]
        bf=BF([(base,1000*M),(rewarded,1100*M)],epoch=652);tg=TG();state=root/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=state,blockfrost=bf,telegram=tg,
            delegator_change_threshold_lovelace=1*M,pool_change_threshold_lovelace=1*M,
            reward_match_tolerance_lovelace=1*M,reward_batch_min_matches=3,
            epoch_manager_state_file=manager,epochs_dir=epochs)
        assert w.run()['bootstrap']
        bf.i=1;bf.current_epoch=653
        r=w.run(); assert r['reward_correlation']['detected'] is True, r
        assert r['reward_correlation']['suppressed_events']==4, r
        assert r['reward_correlation']['pool_reward_neutralized']==100*M, r
        assert r['pending']==0 and tg.msg==[], r

    # Same batch plus a real +50 ADA manual increase on A: only the real residual is notified.
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); epochs=root/'epochs';epochs.mkdir(); manager=root/'epoch_manager_state.json'
        manager.write_text(json.dumps({'last_rewards_settled_epoch':650}),encoding='utf-8')
        reward_archive(epochs,650,{A:10,B:20,C:30,D:40})
        base=[{'address':A,'live_stake':str(100*M)},{'address':B,'live_stake':str(200*M)},
              {'address':C,'live_stake':str(300*M)},{'address':D,'live_stake':str(400*M)}]
        mixed=[{'address':A,'live_stake':str(160*M)},{'address':B,'live_stake':str(220*M)},
               {'address':C,'live_stake':str(330*M)},{'address':D,'live_stake':str(440*M)}]
        bf=BF([(base,1000*M),(mixed,1150*M)],epoch=652);tg=TG();state=root/'state.json'
        w=StakeDelegatorWatcher(ticker='TEST',pool_id='pool1test',state_file=state,blockfrost=bf,telegram=tg,
            delegator_change_threshold_lovelace=1*M,pool_change_threshold_lovelace=1*M,
            group_tolerance_lovelace=1*M,reward_match_tolerance_lovelace=1*M,reward_batch_min_matches=3,
            epoch_manager_state_file=manager,epochs_dir=epochs)
        assert w.run()['bootstrap']
        bf.i=1;bf.current_epoch=653
        r=w.run(); assert r['reward_correlation']['detected'] is True, r
        assert r['reward_correlation']['suppressed_events']==3, r
        assert r['pending']==1 and r['grouped'], r
        assert r['messages'][0]['diff']==50*M, r
        assert r['messages'][0]['reward_component']==100*M, r

    print('OK - stake-address transfer correlation + intelligent grouping + reward suppression + residual preservation + dedup')
if __name__=='__main__':main()
