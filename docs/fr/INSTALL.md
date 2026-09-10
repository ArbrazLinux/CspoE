<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Installation

CspoE a été développé et testé sous Ubuntu 22.04 LTS. Décompressez la release dans un répertoire temporaire, configurez `CspoE.conf`, puis lancez :

```bash
./install.sh --check
sudo ./install.sh --install
```

L’installateur installe Python, venv/pip, les bibliothèques d’exécution Qt et `requirements-all.txt`. Selon la configuration, il peut aussi installer MySQL, Apache/PHP et les unités systemd génériques `cspoe-*`. Il crée par défaut un compte de service et ajoute l’utilisateur sudo à son groupe ; reconnectez-vous avant d’utiliser le GUI si les groupes ont changé.

La cible doit être vide, afin de ne jamais remplacer accidentellement un moteur existant. L’installation ne lance pas l’initialisation et n’écrase aucune donnée canonique.

Les transactions Cardano peuvent nécessiter un `cardano-cli` géré par l’opérateur. Le bot interactif utilise par défaut `cardano-signer` pour CIP-8 ; installez séparément la version configurée avant d’activer ce service.

Poursuivez avec [Initialisation](INITIALIZE.md).

