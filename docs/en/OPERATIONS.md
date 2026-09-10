<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Operations

Useful commands from the installation directory:

```bash
.venv/bin/python scripts/CspoE_epoch_manager.py status
.venv/bin/python scripts/CspoE_validate_data.py
.venv/bin/python scripts/CspoE_reward_window.py
.venv/bin/python scripts/CspoE_pooldata_export.py
.venv/bin/python scripts/CspoE_mysql_sync.py sync --include-live
systemctl list-timers 'cspoe-*'
journalctl -u cspoe-transition.service -n 100 --no-pager
```

Run the reward window without write first. A write reconciles every unsettled snapshot, verifies the reward cascade and protected archive, writes backups, then atomically updates data and state. Projection failures do not modify canonical files and can be retried.

Before upgrades, back up `CspoE.conf`, `data/`, and MySQL. Never replace a working installation with the public installer; stage and validate a new directory.
