# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Exact legacy MySQL projection reconstructed from canonical snapshots.

The eleven unprefixed tables reproduce the historical web-facing contract.
They are deliberately opt-in because their generic names may already be used
by a production site.  A sync rebuilds the complete projection in one InnoDB
transaction, which also makes delayed N-2 reward corrections deterministic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .CspoE_legacy_contract import validate_exact_legacy_shape
from .mysql import MySQLProjectionError, MySQLRepository


LEGACY_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS `epoch` (
      `epoch_number` INT UNSIGNED NOT NULL,
      `pool_stake` BIGINT UNSIGNED DEFAULT 0, `pool_stake_previous` BIGINT UNSIGNED DEFAULT 0,
      `pool_stake_sum` BIGINT UNSIGNED DEFAULT 0, `pool_stake_diff` BIGINT DEFAULT 0,
      `pool_stake_inputs_sum` BIGINT UNSIGNED DEFAULT 0, `pool_stake_outputs_sum` BIGINT DEFAULT 0,
      `pool_stake_max` BIGINT UNSIGNED DEFAULT 0, `pool_stake_min` BIGINT UNSIGNED DEFAULT 0,
      `biggest_single_owner_pledge` BIGINT UNSIGNED DEFAULT 0,
      `biggest_single_delegator_stake` BIGINT UNSIGNED DEFAULT 0,
      `pool_rewards` BIGINT UNSIGNED DEFAULT 0, `pool_rewards_sum` BIGINT UNSIGNED DEFAULT 0,
      `pool_ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `pool_ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT NULL,
      `owners_nb` INT UNSIGNED NOT NULL DEFAULT 1,
      `pledge` BIGINT UNSIGNED DEFAULT 0, `pledge_previous` BIGINT UNSIGNED DEFAULT 0,
      `pledge_sum` BIGINT UNSIGNED DEFAULT 0, `pledge_diff` BIGINT DEFAULT 0,
      `pledge_inputs_sum` BIGINT UNSIGNED DEFAULT 0, `pledge_outputs_sum` BIGINT DEFAULT 0,
      `pledge_max` BIGINT UNSIGNED DEFAULT 0, `pledge_min` BIGINT UNSIGNED DEFAULT 0,
      `owners_rewards` BIGINT UNSIGNED DEFAULT 0, `owners_rewards_sum` BIGINT UNSIGNED DEFAULT 0,
      `owners_ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `owners_ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `delegators_nb` INT UNSIGNED DEFAULT 0, `delegators_back_count` INT UNSIGNED DEFAULT 0,
      `delegators_back_sum` INT UNSIGNED DEFAULT 0, `delegators_lost_count` INT UNSIGNED DEFAULT 0,
      `delegators_lost_sum` INT UNSIGNED DEFAULT 0,
      `delegators_stake` BIGINT UNSIGNED DEFAULT 0,
      `delegators_stake_previous` BIGINT UNSIGNED DEFAULT 0,
      `delegators_stake_diff` BIGINT DEFAULT 0, `delegators_stake_sum` BIGINT UNSIGNED DEFAULT 0,
      `delegators_stake_inputs_sum` BIGINT UNSIGNED DEFAULT 0,
      `delegators_stake_outputs_sum` BIGINT DEFAULT 0,
      `delegators_stake_max` BIGINT UNSIGNED DEFAULT 0,
      `delegators_stake_min` BIGINT UNSIGNED DEFAULT 0,
      `delegators_lost_stake` BIGINT DEFAULT 0, `delegators_lost_stake_sum` BIGINT DEFAULT 0,
      `delegators_rewards` BIGINT UNSIGNED DEFAULT 0,
      `delegators_rewards_sum` BIGINT UNSIGNED DEFAULT 0,
      `delegators_ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `delegators_ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `delegators_ROA_bonusincluded` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `blocks` INT UNSIGNED DEFAULT 0, `blocks_sum` INT UNSIGNED DEFAULT 0,
      `bonuses` BIGINT UNSIGNED DEFAULT 0, `bonuses_sum` BIGINT UNSIGNED DEFAULT 0,
      PRIMARY KEY (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `delegator` (
      `stake_address` VARCHAR(128) NOT NULL, `first_epoch` INT NOT NULL DEFAULT 0,
      `since_epoch` INT UNSIGNED DEFAULT 0, `gone_epoch` INT UNSIGNED DEFAULT 0,
      `epoch_count` INT UNSIGNED NOT NULL DEFAULT 1,
      `loyalty` DECIMAL(10,2) UNSIGNED DEFAULT 0.00, `comeback` TINYINT NOT NULL DEFAULT 0,
      `comeback_count` INT UNSIGNED DEFAULT 0, `stake` BIGINT UNSIGNED DEFAULT 0,
      `stake_sum` BIGINT UNSIGNED DEFAULT 0, `stake_previous` BIGINT UNSIGNED DEFAULT 0,
      `stake_diff` BIGINT DEFAULT 0, `inputs_sum` BIGINT UNSIGNED DEFAULT 0,
      `outputs_sum` BIGINT DEFAULT 0, `stake_max` BIGINT UNSIGNED DEFAULT 0,
      `stake_min` BIGINT UNSIGNED DEFAULT 0, `rewards` BIGINT UNSIGNED DEFAULT 0,
      `rewards_sum` BIGINT UNSIGNED DEFAULT 0, `bonus` BIGINT UNSIGNED DEFAULT 0,
      `bonus_sum` BIGINT UNSIGNED DEFAULT 0,
      `ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `ROA_bonus_included` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      PRIMARY KEY (`stake_address`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `owner` (
      `stake_address` VARCHAR(128) NOT NULL, `since_epoch` INT UNSIGNED DEFAULT 0,
      `gone_epoch` INT UNSIGNED DEFAULT 0, `epoch_count` INT UNSIGNED DEFAULT 1,
      `loyalty` DECIMAL(10,2) UNSIGNED DEFAULT 0.00, `pledge` BIGINT UNSIGNED DEFAULT 0,
      `pledge_sum` BIGINT UNSIGNED DEFAULT 0, `pledge_previous` BIGINT UNSIGNED DEFAULT 0,
      `pledge_diff` BIGINT DEFAULT NULL, `pledge_max` BIGINT UNSIGNED DEFAULT 0,
      `pledge_min` BIGINT UNSIGNED DEFAULT 0, `rewards` BIGINT UNSIGNED DEFAULT 0,
      `rewards_sum` BIGINT UNSIGNED DEFAULT 0, `inputs_sum` BIGINT UNSIGNED DEFAULT 0,
      `outputs_sum` BIGINT DEFAULT 0, `ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      PRIMARY KEY (`stake_address`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `blocks` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `hash` VARCHAR(64) NOT NULL,
      `height` BIGINT UNSIGNED NOT NULL, `absolute_slot` BIGINT UNSIGNED NOT NULL,
      `epoch_slot` BIGINT UNSIGNED NOT NULL, `time` TIMESTAMP NOT NULL,
      `previous_block_hash` VARCHAR(64) NOT NULL, `next_block_hash` VARCHAR(64) NOT NULL,
      `tx_count` INT UNSIGNED NOT NULL, `fees` BIGINT UNSIGNED NOT NULL,
      `value` BIGINT UNSIGNED NOT NULL,
      PRIMARY KEY (`epoch_epoch_number`,`hash`), KEY `fk_blocks_epoch_idx` (`epoch_epoch_number`),
      CONSTRAINT `fk_blocks_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `bonus` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `delegator_stake_address` VARCHAR(128) NOT NULL,
      `amount` BIGINT UNSIGNED DEFAULT 0, `sum` BIGINT UNSIGNED DEFAULT 0,
      PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
      KEY `fk_bonus_epoch_idx` (`epoch_epoch_number`),
      KEY `fk_bonus_delegator_idx` (`delegator_stake_address`),
      CONSTRAINT `fk_bonus_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
      CONSTRAINT `fk_bonus_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `gone_delegators` (
      `delegator_stake_address` VARCHAR(128) NOT NULL, `epoch_epoch_number` INT UNSIGNED NOT NULL,
      `first_epoch` INT UNSIGNED NOT NULL DEFAULT 0, `since_epoch` INT NOT NULL DEFAULT 0,
      `gone_count` INT UNSIGNED NOT NULL DEFAULT 1, `lost_stake` BIGINT NOT NULL DEFAULT 0,
      `back_count` INT UNSIGNED NOT NULL DEFAULT 0, `lost_stake_sum` BIGINT NOT NULL DEFAULT 0,
      PRIMARY KEY (`delegator_stake_address`,`epoch_epoch_number`,`back_count`),
      KEY `fk_gone_delegators_epoch_idx` (`epoch_epoch_number`),
      KEY `fk_gone_delegators_delegator_idx` (`delegator_stake_address`),
      CONSTRAINT `fk_gone_delegators_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
      CONSTRAINT `fk_gone_delegators_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `owner_rewards` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `owner_stake_address` VARCHAR(128) NOT NULL,
      `amount` BIGINT UNSIGNED DEFAULT 0, `sum` BIGINT UNSIGNED DEFAULT 0,
      PRIMARY KEY (`epoch_epoch_number`,`owner_stake_address`),
      KEY `fk_owner_rewards_epoch_idx` (`epoch_epoch_number`),
      KEY `fk_owner_rewards_owner_idx` (`owner_stake_address`),
      CONSTRAINT `fk_owner_rewards_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`),
      CONSTRAINT `fk_owner_rewards_owner` FOREIGN KEY (`owner_stake_address`) REFERENCES `owner` (`stake_address`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `pledge` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `owner_stake_address` VARCHAR(128) NOT NULL,
      `amount` BIGINT UNSIGNED DEFAULT 0, `sum` BIGINT UNSIGNED DEFAULT 0,
      `previous` BIGINT UNSIGNED DEFAULT 0, `diff` BIGINT DEFAULT 0,
      `inputs_sum` BIGINT UNSIGNED DEFAULT 0, `outputs_sum` BIGINT DEFAULT 0,
      `max` BIGINT UNSIGNED DEFAULT 0, `min` BIGINT UNSIGNED DEFAULT 0,
      `ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00, `ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      PRIMARY KEY (`epoch_epoch_number`,`owner_stake_address`),
      KEY `fk_pledge_epoch_idx` (`epoch_epoch_number`), KEY `fk_pledge_owner_idx` (`owner_stake_address`),
      CONSTRAINT `fk_pledge_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`),
      CONSTRAINT `fk_pledge_owner` FOREIGN KEY (`owner_stake_address`) REFERENCES `owner` (`stake_address`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `rewards` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `delegator_stake_address` VARCHAR(128) NOT NULL,
      `amount` BIGINT UNSIGNED DEFAULT 0, `sum` BIGINT UNSIGNED DEFAULT 0,
      PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
      KEY `fk_rewards_delegator_idx` (`delegator_stake_address`), KEY `fk_rewards_epoch_idx` (`epoch_epoch_number`),
      CONSTRAINT `fk_rewards_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
      CONSTRAINT `fk_rewards_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `stake` (
      `epoch_epoch_number` INT UNSIGNED NOT NULL, `delegator_stake_address` VARCHAR(128) NOT NULL,
      `amount` BIGINT UNSIGNED DEFAULT 0, `sum` BIGINT UNSIGNED DEFAULT 0,
      `previous` BIGINT UNSIGNED DEFAULT 0, `diff` BIGINT DEFAULT 0,
      `inputs_sum` BIGINT UNSIGNED DEFAULT 0, `outputs_sum` BIGINT DEFAULT 0,
      `max` BIGINT UNSIGNED DEFAULT 0, `min` BIGINT UNSIGNED DEFAULT 0,
      `ROA_current` DECIMAL(10,2) UNSIGNED DEFAULT 0.00, `ROA_max` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      `ROA_bonusincluded` DECIMAL(10,2) UNSIGNED DEFAULT 0.00,
      PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
      KEY `fk_stake_delegator_idx` (`delegator_stake_address`), KEY `fk_stake_epoch_idx` (`epoch_epoch_number`),
      CONSTRAINT `fk_stake_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
      CONSTRAINT `fk_stake_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS `assets` (
      `epoch_epoch_number` INT NOT NULL, `delegator_stake_address` VARCHAR(128) NOT NULL,
      `name` VARCHAR(64) NOT NULL, `amount` INT NOT NULL DEFAULT 0,
      `policyID` VARCHAR(64) NOT NULL, `name_hash` VARCHAR(64) NOT NULL,
      `fingerprint` VARCHAR(64) NOT NULL,
      PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`,`fingerprint`),
      KEY `fk_assets_epoch_idx` (`epoch_epoch_number`), KEY `fk_assets_delegator_idx` (`delegator_stake_address`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)


LEGACY_DELETE_ORDER = (
    "assets", "bonus", "rewards", "owner_rewards", "pledge", "stake",
    "gone_delegators", "blocks", "owner", "delegator", "epoch",
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(container: Any, key: str) -> list[dict[str, Any]]:
    values = _dict(container).get(key, [])
    return [row for row in values if isinstance(row, dict)] if isinstance(values, list) else []


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> int:
    return int(str(value).strip().lower() in {"1", "true", "yes", "on"})


def _epoch_row(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    pool, owners, delegators = map(_dict, (snapshot.get("pool"), snapshot.get("owners"), snapshot.get("delegators")))
    bonuses, blocks = _dict(snapshot.get("bonuses")), _dict(snapshot.get("blocks"))
    ps, pr, pl, proa = map(_dict, (pool.get("stake"), pool.get("rewards"), pool.get("lost"), pool.get("ROA")))
    op, ore, oroa = map(_dict, (owners.get("pledge"), owners.get("rewards"), owners.get("ROA")))
    ds, dr, droa = map(_dict, (delegators.get("stake"), delegators.get("rewards"), delegators.get("ROA")))
    return (
        _int(snapshot.get("epoch")), _int(ps.get("_epoch_")), _int(ps.get("_previous_")),
        _int(ps.get("_sum_")), _int(ps.get("_diff_")), _int(ps.get("_inputs_sum_")),
        _int(ps.get("_outputs_sum_")), _int(ps.get("_lifetime_max_")), _int(ps.get("_lifetime_min_")),
        _int(op.get("_biggest_ever_")), _int(ds.get("_biggest_ever_")),
        _int(pr.get("_epoch_")), _int(pr.get("_sum_")), _float(proa.get("_lifetime_")), _float(proa.get("_max_")),
        _int(owners.get("ownersNb")), _int(op.get("_epoch_")), _int(op.get("_previous_")),
        _int(op.get("_sum_")), _int(op.get("_diff_")), _int(op.get("_inputs_sum_")),
        _int(op.get("_outputs_sum_")), _int(op.get("_lifetime_max_")), _int(op.get("_lifetime_min_")),
        _int(ore.get("_epoch_")), _int(ore.get("_sum_")), _float(oroa.get("_lifetime_")), _float(oroa.get("_max_")),
        _int(delegators.get("delegsNb")), _int(delegators.get("back_delegs")),
        _int(delegators.get("back_delegs_sum")), _int(pl.get("lost_delegs_nb")), _int(pl.get("lost_delegs_sum")),
        _int(ds.get("_epoch_")), _int(ds.get("_previous_")), _int(ds.get("_diff_")), _int(ds.get("_sum_")),
        _int(ds.get("_inputs_sum_")), _int(ds.get("_outputs_sum_")), _int(ds.get("_lifetime_max_")),
        _int(ds.get("_lifetime_min_")), _int(pl.get("lost_stake")), _int(pl.get("lost_stake_sum")),
        _int(dr.get("_epoch_")), _int(dr.get("_sum_")), _float(droa.get("_lifetime_")),
        _float(droa.get("_max_")), _float(droa.get("_bonuses_included_")),
        _int(blocks.get("epoch")), _int(blocks.get("total_blocks")),
        _int(bonuses.get("amount")), _int(bonuses.get("_sum_")),
    )


def _account_series(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return tuple(map(_dict, (row.get("stake"), row.get("rewards"), row.get("ROA"), row.get("bonuses"))))  # type: ignore[return-value]


def build_legacy_projection(snapshots: Iterable[dict[str, Any]]) -> dict[str, list[tuple[Any, ...]]]:
    ordered = sorted(snapshots, key=lambda item: _int(item.get("epoch")))
    if not ordered:
        raise MySQLProjectionError("aucun snapshot à projeter vers le schéma legacy")
    seen_epochs: set[int] = set()
    tables: dict[str, list[tuple[Any, ...]]] = {name: [] for name in LEGACY_DELETE_ORDER}
    owner_last: dict[str, tuple[int, dict[str, Any]]] = {}
    delegator_last: dict[str, tuple[int, dict[str, Any]]] = {}
    owner_active: set[str] = set()
    delegator_active: set[str] = set()
    owner_gone: dict[str, int] = {}
    delegator_gone: dict[str, int] = {}
    lost_totals: dict[str, int] = {}
    previous_delegators: dict[str, dict[str, Any]] = {}

    for snapshot in ordered:
        epoch = _int(snapshot.get("epoch"))
        if epoch in seen_epochs:
            raise MySQLProjectionError(f"epoch dupliqué dans la projection legacy: {epoch}")
        seen_epochs.add(epoch)
        errors = validate_exact_legacy_shape(snapshot, expected_epoch=epoch)
        if errors:
            raise MySQLProjectionError(f"epoch {epoch} invalide pour MySQL legacy: {errors[:5]}")
        tables["epoch"].append(_epoch_row(snapshot))

        current_owners: set[str] = set()
        for row in _rows(snapshot.get("owners"), "owner"):
            address = str(row.get("stake_address") or "")
            if not address:
                continue
            current_owners.add(address)
            owner_last[address] = (epoch, row)
            stake, rewards, roa, _bonuses = _account_series(row)
            tables["pledge"].append((
                epoch, address, _int(stake.get("_epoch_")), _int(stake.get("_sum_")),
                _int(stake.get("_previous_")), _int(stake.get("_diff_")), _int(stake.get("_inputs_sum_")),
                _int(stake.get("_outputs_sum_")), _int(stake.get("_lifetime_max_")),
                _int(stake.get("_lifetime_min_")), _float(roa.get("_lifetime_")), _float(roa.get("_max_")),
            ))
            if _int(rewards.get("_epoch_")) > 0:
                tables["owner_rewards"].append((epoch, address, _int(rewards.get("_epoch_")), _int(rewards.get("_sum_"))))
        for address in owner_active - current_owners:
            owner_gone[address] = epoch - 1
        for address in current_owners:
            owner_gone.pop(address, None)
        owner_active = current_owners

        current_delegators: dict[str, dict[str, Any]] = {}
        for row in _rows(snapshot.get("delegators"), "delegator"):
            address = str(row.get("stake_address") or "")
            if not address:
                continue
            current_delegators[address] = row
            delegator_last[address] = (epoch, row)
            stake, rewards, roa, bonuses = _account_series(row)
            tables["stake"].append((
                epoch, address, _int(stake.get("_epoch_")), _int(stake.get("_sum_")),
                _int(stake.get("_previous_")), _int(stake.get("_diff_")), _int(stake.get("_inputs_sum_")),
                _int(stake.get("_outputs_sum_")), _int(stake.get("_lifetime_max_")),
                _int(stake.get("_lifetime_min_")), _float(roa.get("_lifetime_")), _float(roa.get("_max_")),
                _float(roa.get("_bonuses_included_")),
            ))
            if _int(rewards.get("_epoch_")) > 0:
                tables["rewards"].append((epoch, address, _int(rewards.get("_epoch_")), _int(rewards.get("_sum_"))))
            if _int(bonuses.get("amount")) > 0:
                tables["bonus"].append((epoch, address, _int(bonuses.get("amount")), _int(bonuses.get("_sum_"))))
                assets = bonuses.get("assets", [])
                for asset in assets if isinstance(assets, list) else []:
                    if isinstance(asset, dict):
                        tables["assets"].append((
                            epoch, address, str(asset.get("name") or ""), _int(asset.get("amount")),
                            str(asset.get("policyID") or ""), str(asset.get("name_hash") or ""),
                            str(asset.get("fingerprint") or ""),
                        ))

        for address in previous_delegators.keys() - current_delegators.keys():
            previous = previous_delegators[address]
            stake = _dict(previous.get("stake"))
            lost = _int(stake.get("_epoch_"))
            lost_totals[address] = lost_totals.get(address, 0) + lost
            last_active_epoch = epoch - 1
            back_count = _int(previous.get("comeback_count"))
            tables["gone_delegators"].append((
                address, last_active_epoch, _int(previous.get("first_epoch")),
                _int(previous.get("since_epoch")), back_count + 1, lost,
                back_count, lost_totals[address],
            ))
            delegator_gone[address] = last_active_epoch
        for address in current_delegators:
            delegator_gone.pop(address, None)
        previous_delegators = current_delegators
        delegator_active = set(current_delegators)

        blocks = _dict(snapshot.get("blocks")).get("block", [])
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            timestamp = _int(block.get("time"))
            moment = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
            tables["blocks"].append((
                epoch, str(block.get("hash") or ""), _int(block.get("height")), _int(block.get("slot")),
                _int(block.get("epoch_slot")), moment, str(block.get("previous_block") or ""),
                str(block.get("next_block") or ""), _int(block.get("tx_count")),
                _int(block.get("fees")), _int(block.get("output")),
            ))

    for address, (_epoch, row) in sorted(owner_last.items()):
        stake, rewards, roa, _bonuses = _account_series(row)
        tables["owner"].append((
            address, _int(row.get("since_epoch")), owner_gone.get(address, 0), _int(row.get("epoch_count")),
            _float(row.get("loyalty")), _int(stake.get("_epoch_")), _int(stake.get("_sum_")),
            _int(stake.get("_previous_")), _int(stake.get("_diff_")), _int(stake.get("_lifetime_max_")),
            _int(stake.get("_lifetime_min_")), _int(rewards.get("_epoch_")), _int(rewards.get("_sum_")),
            _int(stake.get("_inputs_sum_")), _int(stake.get("_outputs_sum_")),
            _float(roa.get("_lifetime_")), _float(roa.get("_max_")),
        ))
    for address, (_epoch, row) in sorted(delegator_last.items()):
        stake, rewards, roa, bonuses = _account_series(row)
        tables["delegator"].append((
            address, _int(row.get("first_epoch")), _int(row.get("since_epoch")),
            delegator_gone.get(address, 0), _int(row.get("epoch_count")), _float(row.get("loyalty")),
            _bool(row.get("comeback")), _int(row.get("comeback_count")),
            _int(stake.get("_epoch_")), _int(stake.get("_sum_")), _int(stake.get("_previous_")),
            _int(stake.get("_diff_")), _int(stake.get("_inputs_sum_")), _int(stake.get("_outputs_sum_")),
            _int(stake.get("_lifetime_max_")), _int(stake.get("_lifetime_min_")),
            _int(rewards.get("_epoch_")), _int(rewards.get("_sum_")),
            _int(bonuses.get("amount")), _int(bonuses.get("_sum_")),
            _float(roa.get("_lifetime_")), _float(roa.get("_max_")), _float(roa.get("_bonuses_included_")),
        ))
    return tables


INSERTS = {
    "epoch": "INSERT INTO `epoch` VALUES (" + ",".join(["%s"] * 52) + ")",
    "delegator": "INSERT INTO `delegator` VALUES (" + ",".join(["%s"] * 23) + ")",
    "owner": "INSERT INTO `owner` VALUES (" + ",".join(["%s"] * 17) + ")",
    "blocks": "INSERT INTO `blocks` VALUES (" + ",".join(["%s"] * 11) + ")",
    "bonus": "INSERT INTO `bonus` VALUES (%s,%s,%s,%s)",
    "gone_delegators": "INSERT INTO `gone_delegators` VALUES (" + ",".join(["%s"] * 8) + ")",
    "owner_rewards": "INSERT INTO `owner_rewards` VALUES (%s,%s,%s,%s)",
    "pledge": "INSERT INTO `pledge` VALUES (" + ",".join(["%s"] * 12) + ")",
    "rewards": "INSERT INTO `rewards` VALUES (%s,%s,%s,%s)",
    "stake": "INSERT INTO `stake` VALUES (" + ",".join(["%s"] * 13) + ")",
    "assets": "INSERT INTO `assets` VALUES (" + ",".join(["%s"] * 7) + ")",
}


class LegacyMySQLRepository(MySQLRepository):
    """Opt-in writer for the exact historical eleven-table contract."""

    def ensure_legacy_schema(self) -> None:
        connection = self._connection()
        cursor = connection.cursor()
        try:
            for statement in LEGACY_SCHEMA_STATEMENTS:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    def replace_projection(self, snapshots: Iterable[dict[str, Any]], *, ensure_schema: bool = True) -> dict[str, Any]:
        tables = build_legacy_projection(snapshots)
        if ensure_schema:
            self.ensure_legacy_schema()
        connection = self._connection()
        cursor = connection.cursor()
        try:
            for table in LEGACY_DELETE_ORDER:
                cursor.execute(f"DELETE FROM `{table}`")
            for table in ("epoch", "delegator", "owner", "blocks", "bonus", "gone_delegators", "owner_rewards", "pledge", "rewards", "stake", "assets"):
                if tables[table]:
                    cursor.executemany(INSERTS[table], tables[table])
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise MySQLProjectionError(f"projection MySQL legacy: {exc}") from exc
        finally:
            cursor.close()
        return {"epochs": len(tables["epoch"]), "rows": {name: len(rows) for name, rows in sorted(tables.items())}}
