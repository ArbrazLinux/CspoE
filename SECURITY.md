<!--
CspoE is developped and maintained by BreizhStakePool.io 

Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2

Consider delegate your voting power to our Breizh DRep [BZH] 
drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
-->

# Security

Protect `CspoE.conf`, Telegram tokens, MySQL credentials, Cardano signing keys, and runtime data. The installer stores the PHP database configuration outside the web root and restricts its permissions.

The GUI creates unsigned transaction drafts only. It does not read signing keys, sign transactions, or submit transactions. Review drafts and use your established offline signing workflow.

The interactive Telegram bot verifies stake-address ownership with a time-limited, single-use CIP-8 challenge. It never requests a seed phrase or private key.

