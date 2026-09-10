<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Installation

CspoE was developed and tested on Ubuntu 22.04 LTS. Extract the release into a temporary directory, edit `CspoE.conf`, then run:

```bash
./install.sh --check
sudo ./install.sh --install
```

The installer installs Python, venv/pip, Qt runtime libraries, and the modules in `requirements-all.txt`. According to `CspoE.conf`, it can also install MySQL, Apache/PHP, and generic `cspoe-*` systemd units. It creates a dedicated service account by default and adds the invoking sudo user to its group; log out and back in before using the GUI if group membership changed.

The target must be empty. This prevents accidental replacement of an existing engine. The installer does not initialize or overwrite canonical epoch data.

Optional Cardano transaction workflows may require operator-managed `cardano-cli`. The interactive Telegram ownership check uses `cardano-signer` by default; install the configured supported version separately before enabling that service.

Continue with [Initialization](INITIALIZE.md).

