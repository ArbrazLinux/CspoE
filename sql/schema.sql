-- CspoE is developped and maintained by BreizhStakePool.io 
--
-- Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
-- Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
-- donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
--
-- Consider delegate your voting power to our Breizh DRep [BZH] 
-- drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

-- Stable, version-independent web projection. Canonical JSON files remain the
-- source of truth. Existing bzh_*_v5 tables are intentionally left untouched.
CREATE TABLE IF NOT EXISTS cspoe_snapshots (
  epoch INT NOT NULL PRIMARY KEY,
  snapshot_state VARCHAR(16) NOT NULL,
  snapshot_sha256 CHAR(64) NOT NULL,
  payload LONGTEXT NOT NULL,
  updated_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cspoe_epochs (
  epoch INT NOT NULL PRIMARY KEY,
  snapshot_state VARCHAR(16) NOT NULL,
  pool_stake BIGINT NOT NULL,
  pool_stake_sum BIGINT NOT NULL,
  pool_rewards BIGINT NOT NULL,
  pool_rewards_sum BIGINT NOT NULL,
  owner_rewards BIGINT NOT NULL,
  owner_rewards_sum BIGINT NOT NULL,
  delegator_rewards BIGINT NOT NULL,
  delegator_rewards_sum BIGINT NOT NULL,
  bonus_amount BIGINT NOT NULL,
  bonus_sum BIGINT NOT NULL,
  blocks INT NOT NULL,
  blocks_sum INT NOT NULL,
  owners INT NOT NULL,
  delegators INT NOT NULL,
  pool_roa DECIMAL(18,6) NOT NULL,
  updated_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cspoe_accounts (
  epoch INT NOT NULL,
  stake_address VARCHAR(128) NOT NULL,
  account_role VARCHAR(16) NOT NULL,
  list_position INT NOT NULL,
  first_epoch INT NOT NULL,
  since_epoch INT NOT NULL,
  epoch_count INT NOT NULL,
  loyalty DECIMAL(18,6) NOT NULL,
  comeback VARCHAR(8) NOT NULL,
  comeback_count INT NOT NULL,
  stake_epoch BIGINT NOT NULL,
  stake_previous BIGINT NOT NULL,
  stake_diff BIGINT NOT NULL,
  stake_sum BIGINT NOT NULL,
  stake_lifetime_max BIGINT NOT NULL,
  stake_lifetime_min BIGINT NOT NULL,
  stake_inputs_sum BIGINT NOT NULL,
  stake_outputs_sum BIGINT NOT NULL,
  rewards_epoch BIGINT NOT NULL,
  rewards_sum BIGINT NOT NULL,
  bonus_amount BIGINT NOT NULL,
  bonus_sum BIGINT NOT NULL,
  roa_lifetime DECIMAL(18,6) NOT NULL,
  roa_max DECIMAL(18,6) NOT NULL,
  roa_bonus DECIMAL(18,6) NOT NULL,
  payload LONGTEXT NOT NULL,
  PRIMARY KEY (epoch, account_role, stake_address),
  INDEX cspoe_accounts_address (stake_address, epoch),
  INDEX cspoe_accounts_epoch_role (epoch, account_role, list_position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cspoe_blocks (
  epoch INT NOT NULL,
  list_position INT NOT NULL,
  block_hash VARCHAR(128) NOT NULL,
  payload LONGTEXT NOT NULL,
  PRIMARY KEY (epoch, list_position),
  INDEX cspoe_blocks_hash (block_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cspoe_bonus_awards (
  epoch INT NOT NULL,
  list_position INT NOT NULL,
  stake_address VARCHAR(128) NOT NULL,
  amount BIGINT NOT NULL,
  payload LONGTEXT NOT NULL,
  PRIMARY KEY (epoch, list_position),
  INDEX cspoe_bonus_address (stake_address, epoch)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
