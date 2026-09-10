#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Pure reconstruction of canonical CspoE epoch snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .CspoE_chain import CspoEChainSource
from .blockfrost import BlockfrostPauseRequired
from .CspoE_legacy_contract import (
    awards_for_epoch,
    build_legacy_snapshot,
    delegator_rows,
    owner_rows,
    scan_last_rows,
    validate_exact_legacy_shape,
)
from .config import settings


class FinalizationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _diff_paths(left: Any, right: Any, path: str = "") -> list[str]:
    """Strict positional diff used for operational reports."""
    if type(left) is not type(right):
        return [path or "<root>"]
    if isinstance(left, dict):
        output: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else key
            if key not in left or key not in right:
                output.append(child)
            else:
                output.extend(_diff_paths(left[key], right[key], child))
        return output
    if isinstance(left, list):
        if len(left) != len(right):
            return [path + "#len"]
        output = []
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            output.extend(_diff_paths(left_item, right_item, f"{path}[{index}]"))
        return output
    return [] if left == right else [path]


def _int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _reward_summary(candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    rows = owner_rows(candidate) + delegator_rows(candidate)
    positive = []
    for row in rows:
        reward = row.get("rewards") if isinstance(row.get("rewards"), dict) else {}
        amount = _int(reward.get("_epoch_"), 0) or 0
        if amount > 0:
            positive.append(
                {
                    "stake_address": str(row.get("stake_address") or ""),
                    "amount": amount,
                }
            )
    pool_rewards = candidate.get("pool", {}).get("rewards", {})
    total = _int(pool_rewards.get("_epoch_"), 0) or 0
    pool_history = evidence.get("pool_history") or {}
    history_total = _int(pool_history.get("rewards"), None) if isinstance(pool_history, dict) else None
    return {
        "total": total,
        "rewarded_accounts": len(positive),
        "positive_rows": positive,
        "pool_history_rewards": history_total,
        "pool_history_rewards_match": None if history_total is None else history_total == total,
    }


def _cross_checks(
    candidate: dict[str, Any],
    evidence: dict[str, Any],
    epoch: int,
    *,
    strict_closed_history: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    info = evidence.get("epoch_info") or {}
    try:
        checks["epoch_info"] = int(info.get("epoch")) == int(epoch)
    except Exception:
        checks["epoch_info"] = False
    if not checks["epoch_info"]:
        errors.append("Blockfrost epoch_info incohérent")

    all_stakes = evidence.get("all_stakes") or []
    total = sum(int(row.get("amount", 0) or 0) for row in all_stakes if isinstance(row, dict))
    checks["epoch_stakes_count"] = len(all_stakes)
    checks["epoch_stakes_sum"] = total
    candidate_total = int(candidate["pool"]["stake"]["_epoch_"])
    checks["candidate_stake_matches_epoch_stakes"] = candidate_total == total
    if not checks["candidate_stake_matches_epoch_stakes"]:
        errors.append("pool.stake._epoch_ != somme Blockfrost epoch stakes")

    checks["blocks_match"] = candidate["blocks"]["epoch"] == len(evidence.get("blocks") or [])
    if not checks["blocks_match"]:
        errors.append("blocks.epoch != nombre de blocs Blockfrost")

    history = evidence.get("pool_history") or {}
    if history:
        if history.get("blocks") is not None:
            checks["pool_history_blocks_match"] = (
                int(history.get("blocks") or 0) == candidate["blocks"]["epoch"]
            )
            if strict_closed_history and not checks["pool_history_blocks_match"]:
                errors.append("pool_history.blocks contradit les blocs détaillés")
        if history.get("active_stake") is not None:
            checks["pool_history_active_stake_match"] = (
                int(history.get("active_stake") or 0) == total
            )
            if strict_closed_history and not checks["pool_history_active_stake_match"]:
                errors.append("pool_history.active_stake contradit les stakes détaillés")

    checks["reward_evidence"] = _reward_summary(candidate, evidence)
    secondary = ((evidence.get("secondary_verification") or {}).get("koios") or {})
    checks["koios"] = secondary
    if (
        settings.strict_secondary_check
        and secondary.get("available")
        and secondary.get("blocks_match_count") is not True
    ):
        errors.append("Koios contredit le nombre de blocs Blockfrost")
    return errors, checks


class CspoEFinalizer:
    def __init__(
        self,
        *,
        pool_id: str,
        history_dir: Path,
        awards_file: Path,
        start_epoch: int = 0,
        historical_protection_end: int = -1,
        source: Optional[CspoEChainSource] = None,
    ) -> None:
        self.pool_id = pool_id
        self.history_dir = Path(history_dir)
        self.awards_file = Path(awards_file)
        self.start_epoch = int(start_epoch)
        self.historical_protection_end = int(historical_protection_end)
        self.source = source or CspoEChainSource(pool_id)

    def _previous_context(
        self,
        epoch: int,
        history_dir: Optional[Path],
    ) -> tuple[Path, dict[str, Any], list[str], list[str]]:
        history = Path(history_dir or self.history_dir)
        previous_path = history / f"epoch_{epoch - 1}.json"
        if not previous_path.is_file():
            raise FinalizationError(f"historique précédent absent: {previous_path}")
        previous = load_json(previous_path)
        shape_errors = validate_exact_legacy_shape(
            previous,
            expected_epoch=epoch - 1,
        )
        if shape_errors:
            raise FinalizationError(f"epoch {epoch - 1} non canonique: {shape_errors[:3]}")
        previous_delegators = [
            str(row.get("stake_address") or "") for row in delegator_rows(previous)
        ]
        previous_owners = [
            str(row.get("stake_address") or "") for row in owner_rows(previous)
        ]
        return history, previous, previous_delegators, previous_owners

    def _candidate_from_evidence(
        self,
        *,
        epoch: int,
        history: Path,
        previous: dict[str, Any],
        evidence: dict[str, Any],
        strict_closed_history: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not evidence.get("pool_registration_exact"):
            raise FinalizationError("certificat/owners historiques non vérifiés")
        all_stakes = evidence.get("all_stakes")
        blocks = evidence.get("blocks")
        rewards = evidence.get("rewards_by_stake")
        if not isinstance(all_stakes, list) or not isinstance(blocks, list) or not isinstance(rewards, dict):
            raise FinalizationError("preuves Blockfrost incomplètes")

        last_delegators, last_owners = scan_last_rows(history, epoch - 1, self.start_epoch)
        awards = awards_for_epoch(self.awards_file, epoch)
        candidate = build_legacy_snapshot(
            epoch=epoch,
            previous=previous,
            all_stakes=all_stakes,
            owner_addresses=list(evidence.get("owner_addresses") or []),
            rewards_by_stake=rewards,
            blocks=blocks,
            awards=awards,
            last_delegator_rows=last_delegators,
            last_owner_rows=last_owners,
            start_epoch=self.start_epoch,
        )
        errors = validate_exact_legacy_shape(candidate, expected_epoch=epoch)
        cross_errors, cross_checks = _cross_checks(
            candidate,
            evidence,
            epoch,
            strict_closed_history=strict_closed_history,
        )
        errors.extend(cross_errors)
        return candidate, {
            "evidence": evidence,
            "validation_errors": errors,
            "cross_checks": cross_checks,
        }

    def build_candidate(
        self,
        epoch: int,
        observed_epoch: int,
        history_dir: Optional[Path] = None,
        *,
        allow_late_reconciliation: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        epoch = int(epoch)
        observed_epoch = int(observed_epoch)
        if epoch <= self.historical_protection_end:
            raise FinalizationError(f"epoch {epoch} protégé")
        if allow_late_reconciliation:
            if observed_epoch < epoch + 2:
                raise FinalizationError(
                    f"rewards non arrivées à maturité: epoch {epoch}, observé {observed_epoch}"
                )
        elif observed_epoch != epoch + 1:
            raise FinalizationError(f"transition non adjacente: {epoch}->{observed_epoch}")

        history, previous, previous_delegators, previous_owners = self._previous_context(
            epoch,
            history_dir,
        )
        try:
            evidence = self.source.closed_epoch_evidence(
                epoch,
                observed_epoch,
                previous_delegators,
                previous_owners,
            )
        except BlockfrostPauseRequired:
            raise
        except Exception as exc:
            raise FinalizationError(
                f"recollecte Blockfrost epoch {epoch} impossible: {exc}"
            ) from exc
        return self._candidate_from_evidence(
            epoch=epoch,
            history=history,
            previous=previous,
            evidence=evidence,
            strict_closed_history=True,
        )

    def build_live_candidate(
        self,
        epoch: int,
        *,
        observed_epoch: Optional[int] = None,
        history_dir: Optional[Path] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        epoch = int(epoch)
        if observed_epoch is not None and int(observed_epoch) != epoch:
            raise FinalizationError(
                f"epoch live incohérent: demandé {epoch}, observé {observed_epoch}"
            )
        history, previous, previous_delegators, previous_owners = self._previous_context(
            epoch,
            history_dir,
        )
        try:
            evidence = self.source.live_epoch_evidence(
                epoch,
                previous_delegators,
                previous_owners,
            )
        except BlockfrostPauseRequired:
            raise
        except Exception as exc:
            raise FinalizationError(
                f"collecte Blockfrost live epoch {epoch} impossible: {exc}"
            ) from exc
        return self._candidate_from_evidence(
            epoch=epoch,
            history=history,
            previous=previous,
            evidence=evidence,
            strict_closed_history=False,
        )
