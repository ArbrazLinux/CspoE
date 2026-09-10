<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Initialization

See the authoritative [root initialization guide](../../INITIALIZE.md).

The key rule is: with current epoch `N`, only epochs through `N-2` have settled rewards and may be archived. `N-1` and `N` remain live. The upper boundaries are queried from Blockfrost; operators configure only `POOL_FIRST_EPOCH`.

For an old or large pool, use durable `--write` staging from the first run. Every Blockfrost HTTP attempt is counted in `blockfrost_usage.json`; completed epochs and reusable account histories remain on disk. A local safety ceiling pauses the process before the configured budget. Provider responses 402, repeated 429, and 418 also stop it without hammering the API. Resume with `--write --resume` after the indicated UTC time. See the root guide for the exact sequence and awards-file policy.
