<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Configuration

Éditez `CspoE.conf` avant installation. Les paramètres obligatoires sont :

- `BLOCKFROST_PROJECT_ID` : token Blockfrost privé ;
- `BECH32_POOL_ID` : identifiant `pool1...` du pool ;
- `POOL_TICKER` : ticker d’affichage ;
- `POOL_FIRST_EPOCH` : première epoch active, généralement epoch d’enregistrement + 2 ;
- `CARDANO_NETWORK` : `mainnet`, `preview` ou `preprod`.

Les protections Blockfrost de l’initialisation sont :

- `BLOCKFROST_DAILY_BUDGET` : plafond journalier local des requêtes de l’initialisation CspoE (`45000` par défaut) ;
- `BLOCKFROST_QUOTA_RESERVE` : réserve laissée aux autres consommateurs (`2000` par défaut) ;
- `BLOCKFROST_AUTO_PAUSE` : suspension avant le plafond local, sans attendre le refus du fournisseur.

Le compteur ne couvre que cette initialisation CspoE. Le quota du forfait Blockfrost peut être partagé avec d’autres projets : contrôlez la consommation réelle dans le tableau de bord Blockfrost et adaptez ces valeurs conservatrices au forfait souscrit.

Laissez `AWARDS_FILE` vide pour utiliser `data/awards.json`. Ce fichier contient l’historique de bonus propre à l’opérateur, et non des données de chaîne. Un fichier absent, vide ou contenant `[]` est valide et signifie « aucun bonus » ; un JSON non vide mais invalide est refusé. N’activez MySQL, PHP, Telegram, DRep, le bot interactif ou le contrôle de santé qu’après avoir renseigné leurs paramètres. Les secrets peuvent aussi venir de variables d’environnement ; une valeur non vide du fichier reste prioritaire.

`CSPOE_INSTALL_DIR`, `CSPOE_SERVICE_USER` et `CSPOE_SERVICE_GROUP` définissent la cible et les droits. Gardez `CspoE.conf` hors de la racine Web avec des permissions restrictives.
