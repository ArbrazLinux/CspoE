<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Architecture

CspoE has one canonical data path. Blockfrost facts are shaped by `core/CspoE_legacy_contract.py`; all consumers read those canonical epoch files through `PoolDataStore`.

- `epochs/` contains only reward-settled snapshots through observed epoch `N-2`.
- `live/` contains the closed reward-pending `N-1` and current `N` snapshots.
- the transition reconciler rebuilds unsettled epochs sequentially and commits files plus state transactionally;
- MySQL, pooldata, PHP, GUI, and Telegram are projections or read-only consumers and cannot redefine canonical business values.

Delegator and owner identity is keyed by `stake_address`; array position is presentation order only.

