<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# CspoE initialization

Initialization reconstructs the complete canonical history from `POOL_FIRST_EPOCH`, which must be the pool's first **active** epoch (normally two epochs after registration). It queries the current Blockfrost epoch and derives every upper boundary automatically.

If the observed network epoch is `N`:

- `POOL_FIRST_EPOCH .. N-2` is reconstructed sequentially and archived;
- `N-1` is reconstructed as closed but reward-pending data in `live/`;
- `N` is collected as the current snapshot in `live/`.

`N-1` is intentionally not archived because its rewards are not yet final. At the next transition it becomes `N-2`, is fully recollected with rewards, validated, and only then archived. Cumulative values, departures, returns, list identities, blocks, and rewards are rebuilt in sequence rather than patched in place.

## Before running

Set these values in `CspoE.conf`:

```ini
BLOCKFROST_PROJECT_ID=...
BECH32_POOL_ID=pool1...
POOL_TICKER=...
POOL_FIRST_EPOCH=...
BLOCKFROST_DAILY_BUDGET=45000
BLOCKFROST_QUOTA_RESERVE=2000
BLOCKFROST_AUTO_PAUSE=1
```

`BLOCKFROST_DAILY_BUDGET` is a local CspoE ceiling, not a reading of the provider account. Keep a reserve because Blockfrost quotas may be shared by other projects and applications. Check the current plan limit and actual usage in the Blockfrost dashboard before starting.

Blockfrost documents the current [daily and rate-limit behavior](https://blockfrost.dev/start-building) and [plan/shared-project rules](https://blockfrost.dev/overview/plans-and-billing). Plan allowances can change; CspoE therefore does not hard-code an asserted provider quota.

`awards.json` is operator-owned bonus history; it is not obtained from the chain. `AWARDS_FILE` may point to a custom file. A missing file, a whitespace-only file, or `[]` is valid and means no awards. Populate it before reconstruction only when the operator has historical bonuses to include. A malformed non-empty file is rejected rather than silently ignored.

## Safe sequence

For an old pool, start directly with durable staging **without activation**. A full dry-run uses temporary storage, cannot be resumed, and would consume the same API history again during the write run.

```bash
cd /opt/cspoe
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py \
  --write --report /tmp/cspoe-initialize-write.json
```

The initializer stores each completed epoch, reusable Blockfrost histories, `blockfrost_usage.json`, and `initialization_checkpoint.json`. If the JSON result contains `"paused": true`, the process ended safely with exit code `75`. Wait until the reported `resume_after` time (UTC), verify account usage in the Blockfrost dashboard, then continue:

```bash
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py --write --resume \
  --report /tmp/cspoe-initialize-write.json
```

Already validated epochs are not downloaded again. The persisted high-level account and pool cache also avoids repeating expensive history pagination after a restart. Every actual HTTP attempt, including retries, is counted. The process pauses proactively at `daily budget - reserve`; HTTP 402 pauses until the next midnight UTC, repeated HTTP 429 pauses for the indicated cooldown, and HTTP 418 requires checking the Blockfrost dashboard before resuming.

The local counter cannot see traffic emitted by other applications. Therefore a provider-side 402 remains authoritative even when CspoE's count is lower.

Activate only after reviewing a successful staging report:

```bash
sudo -u cspoe .venv/bin/python scripts/CspoE_initialize.py \
  --write --resume --activate \
  --report /tmp/cspoe-initialize-activate.json
```

Activation is refused when canonical epoch files or an engine state already exist. It installs the archive, both live snapshots, a protected SHA-256 manifest, and coherent reward/finalization watermarks.

Use `--replace-staging` only to deliberately retire the checkpoint and restart the entire reconstruction. It is not needed for normal activation.

## Verification

```bash
.venv/bin/python scripts/CspoE_validate_data.py
.venv/bin/python scripts/CspoE_epoch_manager.py status
.venv/bin/python scripts/CspoE_mysql_sync.py sync --include-live
```

If the network epoch advances during a quota suspension, resume automatically retargets the reconstruction. Stable archived epochs are preserved; only obsolete staged `live/` snapshots and their time-dependent cache are retired. The final archive still ends at the new `N-2`, with the new `N-1` and `N` left live.

## Optional legacy-reference audit

Initialization rebuilds the legacy-compatible `pool_data` contract directly from chain facts. If an operator also owns an older private export, it can be audited separately without bundling it in the public release:

```bash
.venv/bin/python scripts/CspoE_legacy_replay.py \
  --mode reference-facts --legacy-source /private/history \
  --start-epoch FIRST_ACTIVE_EPOCH --end-epoch LAST_REFERENCE_EPOCH \
  --awards-file data/awards.json
```

This audit is optional and never replaces the configured Blockfrost initialization path.
