<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Desktop GUI

Launch from a graphical Linux session:

```bash
cd /opt/cspoe
./scripts/run_desktop.sh
```

Run it as the user logged into the desktop, without `sudo` and not through a systemd service. The launcher selects X11 or Wayland from the session and isolates the Qt plugins bundled with the CspoE virtual environment from incompatible system Qt plugins.

Diagnostic mode does not open a window:

```bash
./scripts/run_desktop.sh --diagnose
```

The GUI provides engine status, canonical pool/delegator/block/bonus data, operational controls, unsigned pool transaction drafts, and DRep vote draft tools. Data views use the same canonical files as PHP/MySQL projections.

Transaction tools are deliberately build-only: they do not read private keys, sign, or submit. Review every draft and continue with the pool's offline signing procedure.

If the launcher reports that no display is available, open a terminal from the graphical desktop and rerun it without `sudo`. For X11, `DISPLAY` must be non-empty; for Wayland, `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` must be available. The installer installs the complete Ubuntu xcb dependency set required by the PySide6 wheel.
