<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Configuration

Edit `CspoE.conf` before installation. Required values are:

- `BLOCKFROST_PROJECT_ID`: private Blockfrost project token;
- `BECH32_POOL_ID`: the pool's `pool1...` identifier;
- `POOL_TICKER`: display ticker;
- `POOL_FIRST_EPOCH`: first active pool epoch, normally registration epoch + 2;
- `CARDANO_NETWORK`: `mainnet`, `preview`, or `preprod`.

Blockfrost initialization safeguards are:

- `BLOCKFROST_DAILY_BUDGET`: local daily ceiling for CspoE initialization requests (default `45000`);
- `BLOCKFROST_QUOTA_RESERVE`: requests kept in reserve for other consumers (default `2000`);
- `BLOCKFROST_AUTO_PAUSE`: stop before the local ceiling instead of waiting for a provider refusal.

These counters cover only this CspoE initialization. Blockfrost plan quotas can be shared by other projects, so verify actual usage in the Blockfrost dashboard and adjust the conservative values to the subscribed plan.

Leave `AWARDS_FILE` empty to use `data/awards.json`. This is operator-owned bonus history, not chain data. A missing file, an empty file, or `[]` is valid and means no bonuses; malformed non-empty JSON is rejected. Enable MySQL, PHP, Telegram, DRep, interactive bot, or health services only after filling their associated settings. Secrets can also be supplied through environment variables; a non-empty configuration value has priority.

`CSPOE_INSTALL_DIR`, `CSPOE_SERVICE_USER`, and `CSPOE_SERVICE_GROUP` control installation and service ownership. Keep `CspoE.conf` outside the web root and restrict access.
