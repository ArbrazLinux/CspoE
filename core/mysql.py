# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""MySQL projection of canonical CspoE snapshots.

The JSON archive remains the source of truth.  MySQL is a replaceable,
idempotent projection intended for PHP/web queries; it is never allowed to
modify epoch files or the epoch-manager state.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .CspoE_legacy_contract import validate_exact_legacy_shape
from .config import settings
from .data_store import PoolDataStore


class MySQLProjectionError(RuntimeError):
    pass


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS cspoe_snapshots (
      epoch INT NOT NULL PRIMARY KEY,
      snapshot_state VARCHAR(16) NOT NULL,
      snapshot_sha256 CHAR(64) NOT NULL,
      payload LONGTEXT NOT NULL,
      updated_at DATETIME(6) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cspoe_blocks (
      epoch INT NOT NULL,
      list_position INT NOT NULL,
      block_hash VARCHAR(128) NOT NULL,
      payload LONGTEXT NOT NULL,
      PRIMARY KEY (epoch, list_position),
      INDEX cspoe_blocks_hash (block_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cspoe_bonus_awards (
      epoch INT NOT NULL,
      list_position INT NOT NULL,
      stake_address VARCHAR(128) NOT NULL,
      amount BIGINT NOT NULL,
      payload LONGTEXT NOT NULL,
      PRIMARY KEY (epoch, list_position),
      INDEX cspoe_bonus_address (stake_address, epoch)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_sha256(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def epoch_projection(snapshot: dict[str, Any], snapshot_state: str) -> tuple[Any, ...]:
    epoch = _integer(snapshot.get("epoch"))
    pool = _dict(snapshot.get("pool"))
    owners = _dict(snapshot.get("owners"))
    delegators = _dict(snapshot.get("delegators"))
    blocks = _dict(snapshot.get("blocks"))
    bonuses = _dict(snapshot.get("bonuses"))
    pool_stake = _dict(pool.get("stake"))
    pool_rewards = _dict(pool.get("rewards"))
    owner_rewards = _dict(owners.get("rewards"))
    delegator_rewards = _dict(delegators.get("rewards"))
    pool_roa = _dict(pool.get("ROA"))
    return (
        epoch,
        snapshot_state,
        _integer(pool_stake.get("_epoch_")),
        _integer(pool_stake.get("_sum_")),
        _integer(pool_rewards.get("_epoch_")),
        _integer(pool_rewards.get("_sum_")),
        _integer(owner_rewards.get("_epoch_")),
        _integer(owner_rewards.get("_sum_")),
        _integer(delegator_rewards.get("_epoch_")),
        _integer(delegator_rewards.get("_sum_")),
        _integer(bonuses.get("amount")),
        _integer(bonuses.get("_sum_")),
        _integer(blocks.get("epoch")),
        _integer(blocks.get("total_blocks")),
        _integer(owners.get("ownersNb")),
        _integer(delegators.get("delegsNb")),
        _number(pool_roa.get("_lifetime_")),
    )


def account_projection(
    epoch: int,
    role: str,
    position: int,
    row: dict[str, Any],
) -> tuple[Any, ...]:
    stake = _dict(row.get("stake"))
    rewards = _dict(row.get("rewards"))
    bonuses = _dict(row.get("bonuses"))
    roa = _dict(row.get("ROA"))
    return (
        epoch,
        str(row.get("stake_address") or ""),
        role,
        position,
        _integer(row.get("first_epoch")),
        _integer(row.get("since_epoch")),
        _integer(row.get("epoch_count")),
        _number(row.get("loyalty")),
        str(row.get("comeback", "False")),
        _integer(row.get("comeback_count")),
        _integer(stake.get("_epoch_")),
        _integer(stake.get("_previous_")),
        _integer(stake.get("_diff_")),
        _integer(stake.get("_sum_")),
        _integer(stake.get("_lifetime_max_")),
        _integer(stake.get("_lifetime_min_")),
        _integer(stake.get("_inputs_sum_")),
        _integer(stake.get("_outputs_sum_")),
        _integer(rewards.get("_epoch_")),
        _integer(rewards.get("_sum_")),
        _integer(bonuses.get("amount")),
        _integer(bonuses.get("_sum_")),
        _number(roa.get("_lifetime_")),
        _number(roa.get("_max_")),
        _number(roa.get("_bonuses_included_")),
        _json(row),
    )


def projection_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    blocks = _dict(snapshot.get("blocks")).get("block", [])
    bonuses = _dict(snapshot.get("bonuses")).get("awarded_delegators", [])
    return {
        "accounts": len(PoolDataStore.account_rows(snapshot)),
        "blocks": len(blocks if isinstance(blocks, list) else []),
        "bonus_awards": len(bonuses if isinstance(bonuses, list) else []),
    }


class MySQLRepository:
    def __init__(
        self,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.connection: Any | None = None

    def connect(self) -> Any:
        if not settings.mysql_database or not settings.mysql_user:
            raise MySQLProjectionError(
                "MYSQL_DATABASE et MYSQL_USER doivent être configurés"
            )
        if self.connection_factory is None:
            try:
                import mysql.connector  # type: ignore
            except ModuleNotFoundError as exc:
                raise MySQLProjectionError(
                    "mysql-connector-python absent; installer requirements-mysql.txt"
                ) from exc
            factory = mysql.connector.connect
        else:
            factory = self.connection_factory
        try:
            self.connection = factory(
                host=settings.mysql_host,
                port=settings.mysql_port,
                database=settings.mysql_database,
                user=settings.mysql_user,
                password=settings.mysql_password,
                autocommit=False,
            )
        except Exception as exc:
            raise MySQLProjectionError(f"connexion MySQL impossible: {exc}") from exc
        return self.connection

    def _connection(self) -> Any:
        return self.connection or self.connect()

    def ensure_schema(self) -> None:
        connection = self._connection()
        cursor = connection.cursor()
        try:
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    def upsert_snapshot(self, snapshot: dict[str, Any], *, snapshot_state: str) -> dict[str, Any]:
        epoch = snapshot.get("epoch")
        if type(epoch) is not int:
            raise MySQLProjectionError("snapshot sans epoch entier")
        errors = validate_exact_legacy_shape(snapshot, expected_epoch=epoch)
        if errors:
            raise MySQLProjectionError(
                f"epoch {epoch} invalide pour MySQL: {errors[:5]}"
            )

        connection = self._connection()
        cursor = connection.cursor()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        counts = projection_counts(snapshot)
        try:
            cursor.execute(
                """
                INSERT INTO cspoe_snapshots
                  (epoch,snapshot_state,snapshot_sha256,payload,updated_at)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  snapshot_state=VALUES(snapshot_state),
                  snapshot_sha256=VALUES(snapshot_sha256),
                  payload=VALUES(payload),updated_at=VALUES(updated_at)
                """,
                (
                    epoch,
                    snapshot_state,
                    canonical_sha256(snapshot),
                    _json(snapshot),
                    now,
                ),
            )
            epoch_values = epoch_projection(snapshot, snapshot_state) + (now,)
            cursor.execute(
                """
                INSERT INTO cspoe_epochs
                  (epoch,snapshot_state,pool_stake,pool_stake_sum,pool_rewards,
                   pool_rewards_sum,owner_rewards,owner_rewards_sum,
                   delegator_rewards,delegator_rewards_sum,bonus_amount,bonus_sum,
                   blocks,blocks_sum,owners,delegators,pool_roa,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  snapshot_state=VALUES(snapshot_state),pool_stake=VALUES(pool_stake),
                  pool_stake_sum=VALUES(pool_stake_sum),pool_rewards=VALUES(pool_rewards),
                  pool_rewards_sum=VALUES(pool_rewards_sum),owner_rewards=VALUES(owner_rewards),
                  owner_rewards_sum=VALUES(owner_rewards_sum),delegator_rewards=VALUES(delegator_rewards),
                  delegator_rewards_sum=VALUES(delegator_rewards_sum),bonus_amount=VALUES(bonus_amount),
                  bonus_sum=VALUES(bonus_sum),blocks=VALUES(blocks),blocks_sum=VALUES(blocks_sum),
                  owners=VALUES(owners),delegators=VALUES(delegators),pool_roa=VALUES(pool_roa),
                  updated_at=VALUES(updated_at)
                """,
                epoch_values,
            )

            # Replace child rows so removed delegators/blocks cannot survive a
            # later reward reconciliation of the same epoch.
            for table in ("cspoe_accounts", "cspoe_blocks", "cspoe_bonus_awards"):
                cursor.execute(f"DELETE FROM {table} WHERE epoch=%s", (epoch,))

            for row in PoolDataStore.account_rows(snapshot):
                cursor.execute(
                    """
                    INSERT INTO cspoe_accounts VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                     %s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    account_projection(
                        epoch,
                        str(row.pop("role")),
                        int(row.pop("position")),
                        row,
                    ),
                )

            blocks = _dict(snapshot.get("blocks")).get("block", [])
            for position, block in enumerate(blocks if isinstance(blocks, list) else []):
                if isinstance(block, dict):
                    cursor.execute(
                        "INSERT INTO cspoe_blocks VALUES (%s,%s,%s,%s)",
                        (epoch, position, str(block.get("hash") or ""), _json(block)),
                    )

            awards = _dict(snapshot.get("bonuses")).get("awarded_delegators", [])
            for position, award in enumerate(awards if isinstance(awards, list) else []):
                if isinstance(award, dict):
                    cursor.execute(
                        "INSERT INTO cspoe_bonus_awards VALUES (%s,%s,%s,%s,%s)",
                        (
                            epoch,
                            position,
                            str(award.get("stake_address") or award.get("address") or ""),
                            _integer(award.get("amount")),
                            _json(award),
                        ),
                    )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise MySQLProjectionError(f"projection MySQL epoch {epoch}: {exc}") from exc
        finally:
            cursor.close()

        return {"epoch": epoch, "state": snapshot_state, **counts}

    def sync_snapshots(
        self,
        snapshots: Iterable[tuple[dict[str, Any], str]],
        *,
        ensure_schema: bool = True,
    ) -> list[dict[str, Any]]:
        if ensure_schema:
            self.ensure_schema()
        return [
            self.upsert_snapshot(snapshot, snapshot_state=state)
            for snapshot, state in snapshots
        ]

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
