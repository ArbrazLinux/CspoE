<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Telegram

Renseignez `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`, puis activez uniquement les services souhaités. Les watchers couvrent la transition/rewards, les blocs, les variations de stake et de délégataires, les votes DRep et les alertes techniques privées.

Le bot interactif optionnel permet aux délégataires d’associer leurs stake addresses et de consulter stake/rewards. Avec la vérification activée, l’association repose sur un challenge CIP-8 temporaire et à usage unique. Aucune seed phrase ni clé privée n’est demandée ou stockée.

Tests sans envoi :

```bash
.venv/bin/python scripts/CspoE_telegram.py --dry-run
.venv/bin/python scripts/CspoE_block_watcher.py --dry-run
.venv/bin/python scripts/CspoE_stake_watcher.py --dry-run
.venv/bin/python scripts/CspoE_drep_watcher.py --dry-run
.venv/bin/python scripts/CspoE_health.py --dry-run
```

N’activez les timers `cspoe-*` correspondants qu’après lecture des résultats.

