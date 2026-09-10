<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Exploitation

Commandes utiles depuis le répertoire installé :

```bash
.venv/bin/python scripts/CspoE_epoch_manager.py status
.venv/bin/python scripts/CspoE_validate_data.py
.venv/bin/python scripts/CspoE_reward_window.py
.venv/bin/python scripts/CspoE_pooldata_export.py
.venv/bin/python scripts/CspoE_mysql_sync.py sync --include-live
systemctl list-timers 'cspoe-*'
journalctl -u cspoe-transition.service -n 100 --no-pager
```

Testez toujours la fenêtre de rewards sans écriture. L’écriture reconstruit les epochs non stabilisées, valide la cascade et l’archive protégée, sauvegarde les cibles, puis met à jour fichiers et état transactionnellement. Les projections peuvent être rejouées sans modifier les données canoniques.

Avant une mise à jour, sauvegardez `CspoE.conf`, `data/` et MySQL. Installez une nouvelle release dans un répertoire séparé pour la valider.
