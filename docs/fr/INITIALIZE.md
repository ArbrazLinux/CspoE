<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Initialisation

Le guide de référence est [INITIALIZE.md](../../INITIALIZE.md) (anglais).

Règle essentielle : pour une epoch courante `N`, seules les epochs jusqu’à `N-2` ont leurs rewards stabilisées et peuvent être archivées. `N-1` et `N` restent dans `live/`. Les bornes hautes sont déterminées par Blockfrost ; l’opérateur configure uniquement `POOL_FIRST_EPOCH`.

Séquence recommandée :

```bash
cd /opt/cspoe
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py \
  --write --report /tmp/cspoe-init-write.json
# En cas de suspension de quota, attendre l'heure UTC indiquée puis :
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py \
  --write --resume --report /tmp/cspoe-init-write.json
# Une fois la reconstruction terminée :
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py \
  --write --resume --activate --report /tmp/cspoe-init-activate.json
.venv/bin/python scripts/CspoE_validate_data.py
```

Pour un pool ancien, ne lancez pas d’abord une reconstruction complète en dry-run : elle consommerait le quota sans checkpoint durable, puis `--write` répéterait les appels. Le compteur `blockfrost_usage.json`, le checkpoint, les epochs validées et les caches sont conservés dans le staging. La suspension proactive intervient avant le plafond local ; les réponses Blockfrost 402, les 429 répétés et 418 suspendent aussi le processus sans insister. Le quota journalier fournisseur est régénéré à minuit UTC. Le compteur CspoE ne voit pas les requêtes d’autres applications partageant le forfait : contrôlez également le tableau de bord Blockfrost.

Si une transition d’epoch a lieu durant une suspension, la reprise étend automatiquement la cible : seules les anciennes données `live` sont retirées du staging, tandis que les archives déjà stabilisées restent réutilisées.

`awards.json` est propre à l’opérateur. Il peut être absent, vide ou égal à `[]` sans perturber la collecte ; ces trois cas signifient qu’aucun bonus n’est injecté. Un JSON non vide mais mal formé reste bloquant.

Le moteur reconstruit depuis le début le contrat `pool_data` compatible legacy à partir des faits Blockfrost. Un export historique privé peut en complément être contrôlé avec `CspoE_legacy_replay.py --mode reference-facts --legacy-source ...`; cette référence privée n’est pas nécessaire au fonctionnement et n’est pas incluse dans la release.
