<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Interface graphique

Depuis une session Linux graphique :

```bash
cd /opt/cspoe
./scripts/run_desktop.sh
```

Lancez-le avec l’utilisateur connecté au bureau, sans `sudo` et jamais depuis un service systemd. Le lanceur choisit X11 ou Wayland selon la session et isole les plugins Qt fournis par le virtualenv CspoE des plugins Qt système incompatibles.

Le diagnostic suivant n’ouvre aucune fenêtre :

```bash
./scripts/run_desktop.sh --diagnose
```

Le GUI présente l’état du moteur, les données pool/délégataires/blocs/bonus, les commandes d’exploitation, des brouillons de transactions pool et les outils de brouillon de vote DRep. Les vues lisent les mêmes données canoniques que les projections PHP/MySQL.

Les outils de transaction construisent uniquement des brouillons non signés : aucune clé privée n’est lue, aucune signature ni soumission n’est effectuée. Vérifiez chaque brouillon et utilisez votre procédure de signature hors ligne.

Si le lanceur signale l’absence d’affichage, ouvrez un terminal depuis le bureau graphique et relancez sans `sudo`. Sous X11, `DISPLAY` doit être renseigné ; sous Wayland, `WAYLAND_DISPLAY` et `XDG_RUNTIME_DIR` doivent être disponibles. L’installateur installe désormais l’ensemble des dépendances xcb Ubuntu requises par la distribution PySide6.
