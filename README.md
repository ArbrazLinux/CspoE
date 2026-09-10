<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# CspoE — Cardano Stake Pool Operations Engine

CspoE reconstructs and maintains a Cardano stake pool's epoch history from Blockfrost. It preserves the established `pool_data` contract, tracks delegators by `stake_address`, reconciles delayed rewards, and exposes the resulting data through JSON, MySQL, PHP pages, a desktop GUI, and Telegram notifications.

The release includes:

- transactional epoch collection with the `N-2` reward-settlement rule;
- full initialization from the pool's configurable first active epoch;
- resumable initialization with durable Blockfrost request accounting and quota-safe suspension;
- canonical and legacy-compatible MySQL projections;
- read-only PHP pool, delegator, block, and bonus pages;
- a PySide6 administration and data GUI with unsigned transaction drafts;
- Telegram pool, block, stake, DRep, health, and optional interactive notifications;
- generic systemd units and an automated installer.

This version was developed and tested on Linux Ubuntu 22.04 LTS.

## Quick start

1. Extract the archive and edit `CspoE.conf`.
2. Set `BLOCKFROST_PROJECT_ID`, `BECH32_POOL_ID`, `POOL_TICKER`, and `POOL_FIRST_EPOCH`. The latter is the first **active** pool epoch, normally registration epoch + 2.
3. Check and install:

```bash
./install.sh --check
sudo ./install.sh --install
```

4. Initialize explicitly from the installed directory:

```bash
cd /opt/cspoe
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py --write --activate \
  --report /tmp/cspoe-initialize.json
```

If the command reports `"paused": true`, wait until the reported UTC reset,
check the Blockfrost dashboard, then rerun it with `--write --resume --activate`.
Validated epochs and cached history are reused. Operator bonuses are optional:
a missing, empty, or `[]` awards file means no bonuses.

5. Validate and inspect:

```bash
.venv/bin/python scripts/CspoE_validate_data.py
.venv/bin/python scripts/CspoE_epoch_manager.py status
./scripts/run_desktop.sh
```

The GUI must be launched without `sudo` from the logged-in graphical session. Use `./scripts/run_desktop.sh --diagnose` to inspect the selected display backend and isolated PySide6 plugin path.

The installer never initializes automatically. Read [INITIALIZE.md](INITIALIZE.md) before activation and see [docs/README.md](docs/README.md) for the complete English/French documentation.
