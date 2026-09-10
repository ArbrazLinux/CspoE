<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# MySQL et PHP

Configurez les identifiants et activez les options nécessaires :

```ini
CSPOE_INSTALL_MYSQL=1
CSPOE_MYSQL_AUTO_SYNC=1
CSPOE_MYSQL_LEGACY_COMPAT=1
MYSQL_DATABASE=cspoe
MYSQL_USER=cspoe
MYSQL_PASSWORD=secret-solide
```

`sql/schema.sql` crée la projection canonique. `CspoE_legacy_schema.sql` crée les onze tables compatibles legacy. Testez avant écriture :

```bash
.venv/bin/python scripts/CspoE_mysql_sync.py sync --include-live
.venv/bin/python scripts/CspoE_mysql_sync.py legacy-sync --include-live
.venv/bin/python scripts/CspoE_mysql_sync.py sync --include-live --write
.venv/bin/python scripts/CspoE_mysql_sync.py legacy-sync --include-live --write
```

Le JSON canonique reste la source de vérité. MySQL est une projection remplaçable et sa synchronisation ne modifie jamais les epochs.

Avec `CSPOE_INSTALL_PHP=1`, l’installateur déploie `pool.php`, `delegators.php`, `delegator.php`, `blocks.php` et `bonus.php`. Les identifiants sont stockés dans `/etc/cspoe/php-db.php`, hors racine Web et avec permissions restreintes. L’URL par défaut est `/cspoe/pool.php`.
