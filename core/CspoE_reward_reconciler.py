# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Transactional reward settlement and catch-up through the live epoch."""
from __future__ import annotations

import copy
import fcntl
import os
import shutil
import tempfile
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .CspoE_chain import CspoEChainSource
from .CspoE_finalizer import (
    CspoEFinalizer,
    FinalizationError,
    _diff_paths,
    atomic_write_json,
    load_json,
    sha256_file,
    utcnow,
)
from .CspoE_legacy_contract import validate_exact_legacy_shape
from .version import ENGINE_VERSION


class RewardReconciliationError(FinalizationError):
    pass


def _snapshot_hashes(root: Path, start: int, end: int) -> dict[int, str]:
    return {
        epoch: sha256_file(root / f"epoch_{epoch}.json")
        for epoch in range(start, end + 1)
        if (root / f"epoch_{epoch}.json").is_file()
    }


def _protected_manifest(path: Path) -> dict[int, str]:
    if not path.is_file():
        return {}
    result: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+epoch_(\d+)\.json", line)
        if not match:
            raise RewardReconciliationError(
                f"manifeste historique invalide: {line!r}"
            )
        result[int(match.group(2))] = match.group(1)
    return result


def _safe_symlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    os.symlink(source.resolve(), destination)


def _reward_values(snapshot: dict[str, Any], section: str) -> tuple[int, int]:
    parent = snapshot.get(section) if isinstance(snapshot.get(section), dict) else {}
    rewards = parent.get("rewards") if isinstance(parent.get("rewards"), dict) else {}
    try:
        current = int(rewards.get("_epoch_", 0) or 0)
        cumulative = int(rewards.get("_sum_", 0) or 0)
    except (TypeError, ValueError):
        return 0, -1
    return current, cumulative


def _reward_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for section in ("pool", "owners", "delegators"):
        current, cumulative = _reward_values(snapshot, section)
        output[section] = {"epoch": current, "sum": cumulative}
    return output


def _cascade_check(
    previous: dict[str, Any],
    current: dict[str, Any],
    previous_epoch: int,
    current_epoch: int,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    sections: dict[str, Any] = {}
    for section in ("pool", "owners", "delegators"):
        _previous_current, previous_sum = _reward_values(previous, section)
        current_reward, current_sum = _reward_values(current, section)
        expected_sum = previous_sum + current_reward
        valid = previous_sum >= 0 and current_sum == expected_sum
        sections[section] = {
            "previous_sum": previous_sum,
            "current_epoch_reward": current_reward,
            "expected_sum": expected_sum,
            "actual_sum": current_sum,
            "ok": valid,
        }
        if not valid:
            errors.append(
                f"cascade rewards {section} invalide {previous_epoch}->{current_epoch}: "
                f"{current_sum} != {previous_sum} + {current_reward}"
            )
    return errors, {
        "from_epoch": previous_epoch,
        "to_epoch": current_epoch,
        "sections": sections,
        "ok": not errors,
    }


class CspoERewardReconciler:
    """Rebuild every unsettled epoch, closed N-1, and live N in one commit."""

    def __init__(
        self,
        *,
        pool_id: str,
        data_root: Path,
        live_dir: Path,
        archive_dir: Path,
        state_file: Path,
        awards_file: Path,
        reports_dir: Path,
        start_epoch: int = 0,
        historical_protection_end: int = -1,
        source: Optional[CspoEChainSource] = None,
    ) -> None:
        self.pool_id = pool_id
        self.data_root = Path(data_root)
        self.live_dir = Path(live_dir)
        self.archive_dir = Path(archive_dir)
        self.state_file = Path(state_file)
        self.awards_file = Path(awards_file)
        self.reports_dir = Path(reports_dir)
        self.start_epoch = int(start_epoch)
        self.historical_protection_end = int(historical_protection_end)
        self.source = source or CspoEChainSource(pool_id)
        self.lock_file = self.data_root / "reward_reconciliation.lock"
        self.protected_manifest = self.data_root / "protected_epochs.sha256"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_file.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RewardReconciliationError(
                    "une autre réconciliation rewards est déjà active"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return {}
        try:
            value = load_json(self.state_file)
        except Exception as exc:
            raise RewardReconciliationError(
                f"état CspoE illisible: {self.state_file}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise RewardReconciliationError("état CspoE invalide: objet JSON attendu")
        return value

    def _prepare_history(self, workspace: Path, through_epoch: int) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        missing: list[str] = []
        for epoch in range(self.start_epoch, through_epoch + 1):
            source = self.archive_dir / f"epoch_{epoch}.json"
            if not source.is_file():
                missing.append(str(source))
                continue
            _safe_symlink(source, workspace / source.name)
        if missing:
            raise RewardReconciliationError(
                "historique préalable incomplet: " + ", ".join(missing[:10])
            )

    def _write_payload(self, path: Path, payload: dict[str, Any]) -> None:
        """Override point used by rollback self-tests."""
        atomic_write_json(path, payload)

    def _state_after(
        self,
        before: dict[str, Any],
        *,
        settled_epoch: int,
        finalized_epoch: int,
        observed_epoch: int,
        rebuilt_from_epoch: int,
        report_file: Path,
        changed_targets: list[str],
    ) -> dict[str, Any]:
        state = copy.deepcopy(before)
        state.update(
            {
                "version": ENGINE_VERSION,
                "last_collected_epoch": observed_epoch,
                "last_finalized_epoch": finalized_epoch,
                "last_chain_finalized_epoch": finalized_epoch,
                "last_rewards_settled_epoch": settled_epoch,
                "updated_at": utcnow(),
            }
        )
        state["transition"] = {
            "status": "confirmed",
            "source_epoch": finalized_epoch,
            "observed_epoch": observed_epoch,
            "confirmed_at": utcnow(),
            "finalization_report": str(report_file),
            "reward_settled_epoch": settled_epoch,
        }
        state["reward_reconciliation"] = {
            "status": "confirmed",
            "window": [rebuilt_from_epoch, observed_epoch],
            "last_rewards_settled_epoch": settled_epoch,
            "last_chain_finalized_epoch": finalized_epoch,
            "changed_targets": changed_targets,
            "report": str(report_file),
            "updated_at": utcnow(),
        }
        return state

    def _target_report(
        self,
        *,
        role: str,
        path: Path,
        candidate_path: Path,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        exists = path.is_file()
        before = load_json(path) if exists else None
        before_hash = sha256_file(path) if exists else None
        candidate_hash = sha256_file(candidate_path)
        return {
            "role": role,
            "path": str(path),
            "existed_before": exists,
            "before_sha256": before_hash,
            "candidate_sha256": candidate_hash,
            "changed": before_hash != candidate_hash,
            "differences": (
                _diff_paths(before, candidate)[:500]
                if before is not None
                else ["<missing>"]
            ),
        }

    @staticmethod
    def _write_report(report_file: Path, result: dict[str, Any]) -> None:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(report_file, result)

    def _validate_report_path(self, report_file: Path) -> None:
        resolved_report = report_file.resolve(strict=False)
        protected_paths = {
            self.state_file.resolve(strict=False),
            self.awards_file.resolve(strict=False),
            self.lock_file.resolve(strict=False),
        }
        data_directories = (
            self.archive_dir.resolve(strict=False),
            self.live_dir.resolve(strict=False),
        )
        if resolved_report in protected_paths or any(
            resolved_report == directory or directory in resolved_report.parents
            for directory in data_directories
        ):
            raise RewardReconciliationError(
                f"destination de rapport interdite dans les données CspoE: {report_file}"
            )

    @staticmethod
    def _watermark(state: dict[str, Any], key: str) -> Optional[int]:
        value = state.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise RewardReconciliationError(
                f"watermark invalide: {key}={value!r}"
            ) from exc

    def reconcile(
        self,
        observed_epoch: Optional[int] = None,
        *,
        write: bool = False,
        report_file: Optional[Path] = None,
    ) -> dict[str, Any]:
        with self._lock():
            network_epoch = int(self.source.observed_epoch())
            if observed_epoch is not None and int(observed_epoch) != network_epoch:
                raise RewardReconciliationError(
                    f"epoch observé incohérent: demandé {observed_epoch}, "
                    f"Blockfrost {network_epoch}"
                )
            observed_epoch = network_epoch
            settled_through = observed_epoch - 2
            finalized_epoch = observed_epoch - 1
            if finalized_epoch <= self.historical_protection_end:
                raise RewardReconciliationError(
                    "la première transition exploitable doit observer au moins "
                    f"l'epoch {self.historical_protection_end + 2}"
                )

            state_before = self._read_state()
            previous_settled = self._watermark(
                state_before,
                "last_rewards_settled_epoch",
            )
            if previous_settled is not None and previous_settled > settled_through:
                raise RewardReconciliationError(
                    f"watermark rewards futur: {previous_settled} > {settled_through}"
                )
            if previous_settled is None:
                requested_start = self.historical_protection_end + 1
            elif previous_settled == settled_through:
                requested_start = settled_through
            else:
                requested_start = previous_settled + 1
            rebuild_start = max(requested_start, self.historical_protection_end + 1)
            seed_epoch = rebuild_start - 1

            report_file = Path(report_file) if report_file else (
                self.reports_dir
                / f"reward_window_{rebuild_start}_{observed_epoch}.json"
            )
            self._validate_report_path(report_file)
            report_file.parent.mkdir(parents=True, exist_ok=True)

            protected_before = _snapshot_hashes(
                self.archive_dir,
                self.start_epoch,
                self.historical_protection_end,
            )
            protected_expected = self.historical_protection_end - self.start_epoch + 1
            if len(protected_before) != protected_expected:
                raise RewardReconciliationError(
                    "plage historique protégée incomplète avant réconciliation"
                )
            manifest_hashes = _protected_manifest(self.protected_manifest)
            if manifest_hashes and manifest_hashes != protected_before:
                raise RewardReconciliationError(
                    "la plage historique ne correspond plus au manifeste d'initialisation"
                )

            with tempfile.TemporaryDirectory(
                prefix="cspoe-reward-window-"
            ) as temporary:
                root = Path(temporary)
                work_history = root / "epochs"
                work_live = root / "live"
                work_live.mkdir(parents=True, exist_ok=True)
                self._prepare_history(work_history, seed_epoch)

                finalizer = CspoEFinalizer(
                    pool_id=self.pool_id,
                    history_dir=work_history,
                    awards_file=self.awards_file,
                    start_epoch=self.start_epoch,
                    historical_protection_end=self.historical_protection_end,
                    source=self.source,
                )

                errors: list[str] = []
                candidates: dict[int, dict[str, Any]] = {
                    seed_epoch: load_json(work_history / f"epoch_{seed_epoch}.json")
                }
                source_reports: dict[str, Any] = {}
                settlement_reports: list[dict[str, Any]] = []
                targets: list[tuple[str, Path, Path, dict[str, Any]]] = []

                seed_errors = validate_exact_legacy_shape(
                    candidates[seed_epoch],
                    expected_epoch=seed_epoch,
                )
                errors.extend(seed_errors)

                for epoch in range(rebuild_start, settled_through + 1):
                    if errors:
                        break
                    candidate, metadata = finalizer.build_candidate(
                        epoch,
                        observed_epoch,
                        history_dir=work_history,
                        allow_late_reconciliation=True,
                    )
                    local_errors = list(metadata.get("validation_errors") or [])
                    reward_evidence = (
                        metadata.get("cross_checks", {}).get("reward_evidence") or {}
                    )
                    blocks = int(candidate["blocks"]["epoch"])
                    reward_total = int(reward_evidence.get("total", 0) or 0)
                    if blocks > 0 and reward_total <= 0:
                        local_errors.append(
                            f"rewards de l'epoch {epoch} non visibles malgré {blocks} bloc(s)"
                        )
                    if (
                        reward_evidence.get("pool_history_rewards") is not None
                        and reward_evidence.get("pool_history_rewards_match") is not True
                    ):
                        local_errors.append(
                            f"pool_history.rewards contredit les rewards des comptes à l'epoch {epoch}"
                        )
                    settlement_reports.append(
                        {
                            "epoch": epoch,
                            "blocks": blocks,
                            "evidence": reward_evidence,
                            "ready": not local_errors,
                            "validation_errors": local_errors,
                        }
                    )
                    errors.extend(local_errors)
                    candidates[epoch] = candidate
                    source_reports[str(epoch)] = metadata.get("cross_checks") or {}
                    atomic_write_json(work_history / f"epoch_{epoch}.json", candidate)
                    targets.append(
                        (
                            "rewards_settled_archive",
                            self.archive_dir / f"epoch_{epoch}.json",
                            work_history / f"epoch_{epoch}.json",
                            candidate,
                        )
                    )

                finalized_candidate: Optional[dict[str, Any]] = None
                if not errors:
                    finalized_candidate, metadata = finalizer.build_candidate(
                        finalized_epoch,
                        observed_epoch,
                        history_dir=work_history,
                    )
                    errors.extend(metadata.get("validation_errors") or [])
                    candidates[finalized_epoch] = finalized_candidate
                    source_reports[str(finalized_epoch)] = (
                        metadata.get("cross_checks") or {}
                    )
                    atomic_write_json(
                        work_history / f"epoch_{finalized_epoch}.json",
                        finalized_candidate,
                    )
                    targets.append(
                        (
                            "chain_finalized_rewards_pending_live",
                            self.live_dir / f"epoch_{finalized_epoch}.json",
                            work_history / f"epoch_{finalized_epoch}.json",
                            finalized_candidate,
                        )
                    )

                live_candidate: Optional[dict[str, Any]] = None
                if not errors and finalized_candidate is not None:
                    live_candidate, metadata = finalizer.build_live_candidate(
                        observed_epoch,
                        observed_epoch=observed_epoch,
                        history_dir=work_history,
                    )
                    errors.extend(metadata.get("validation_errors") or [])
                    candidates[observed_epoch] = live_candidate
                    source_reports[str(observed_epoch)] = (
                        metadata.get("cross_checks") or {}
                    )
                    atomic_write_json(
                        work_live / f"epoch_{observed_epoch}.json",
                        live_candidate,
                    )
                    targets.append(
                        (
                            "current_live",
                            self.live_dir / f"epoch_{observed_epoch}.json",
                            work_live / f"epoch_{observed_epoch}.json",
                            live_candidate,
                        )
                    )

                cascade_checks: list[dict[str, Any]] = []
                if not errors and live_candidate is not None:
                    sequence = sorted(candidates)
                    for previous_epoch, current_epoch in zip(sequence, sequence[1:]):
                        cascade_errors, cascade = _cascade_check(
                            candidates[previous_epoch],
                            candidates[current_epoch],
                            previous_epoch,
                            current_epoch,
                        )
                        errors.extend(cascade_errors)
                        cascade_checks.append(cascade)

                protected_after_build = _snapshot_hashes(
                    self.archive_dir,
                    self.start_epoch,
                    self.historical_protection_end,
                )
                protected_unchanged = protected_before == protected_after_build
                if not protected_unchanged:
                    errors.append(
                        "plage historique protégée modifiée pendant le dry-run: "
                        f"{self.start_epoch}..{self.historical_protection_end}"
                    )

                target_reports = [
                    self._target_report(
                        role=role,
                        path=path,
                        candidate_path=candidate_path,
                        candidate=candidate,
                    )
                    for role, path, candidate_path, candidate in targets
                ]
                all_candidates_valid = (
                    not errors
                    and finalized_candidate is not None
                    and live_candidate is not None
                    and len(targets) >= 2
                )
                result: dict[str, Any] = {
                    "ok": all_candidates_valid,
                    "version": ENGINE_VERSION,
                    "mode": "reward_window_reconciliation",
                    "window": {
                        "rebuilt_from_epoch": rebuild_start,
                        "rewards_settled_through": settled_through,
                        "chain_finalized_epoch": finalized_epoch,
                        "live_epoch": observed_epoch,
                        "catch_up": rebuild_start < settled_through,
                    },
                    "previous_rewards_settled_epoch": previous_settled,
                    "network_observed_epoch": network_epoch,
                    "dry_run": not write,
                    "all_candidates_valid": all_candidates_valid,
                    "reward_settlement": {
                        "range": (
                            [rebuild_start, settled_through]
                            if rebuild_start <= settled_through
                            else []
                        ),
                        "epochs": settlement_reports,
                        "ready": all(item["ready"] for item in settlement_reports),
                    },
                    "cascade": {
                        "policy": "full sequential rebuild; never add a reward delta in place",
                        "seed_epoch": seed_epoch,
                        "reward_snapshots": {
                            str(epoch): _reward_snapshot(candidates[epoch])
                            for epoch in sorted(candidates)
                        },
                        "continuity_checks": cascade_checks,
                        "targets": target_reports,
                    },
                    "validation_errors": errors,
                    "historical_protection": {
                        "range": [self.start_epoch, self.historical_protection_end],
                        "unchanged": protected_unchanged,
                        "manifest": str(self.protected_manifest) if manifest_hashes else None,
                        "manifest_verified": bool(manifest_hashes),
                    },
                    "source_reports": source_reports,
                    "written": False,
                    "backup_dir": None,
                    "state_updated": False,
                    "report_file": str(report_file),
                    "timestamp": utcnow(),
                }

                if not all_candidates_valid:
                    self._write_report(report_file, result)
                    return result

                network_after_build = int(self.source.observed_epoch())
                result["network_observed_epoch_after_build"] = network_after_build
                if network_after_build != observed_epoch:
                    result["ok"] = False
                    result["validation_errors"].append(
                        "transition réseau pendant la reconstruction: "
                        f"{observed_epoch}->{network_after_build}"
                    )
                    self._write_report(report_file, result)
                    return result

                if write:
                    self._commit(
                        result=result,
                        report_file=report_file,
                        state_before=state_before,
                        targets=targets,
                        target_reports=target_reports,
                        protected_before=protected_before,
                        rebuilt_from_epoch=rebuild_start,
                        settled_epoch=settled_through,
                        finalized_epoch=finalized_epoch,
                        observed_epoch=observed_epoch,
                    )
                else:
                    self._write_report(report_file, result)
                return result

    def _commit(
        self,
        *,
        result: dict[str, Any],
        report_file: Path,
        state_before: dict[str, Any],
        targets: list[tuple[str, Path, Path, dict[str, Any]]],
        target_reports: list[dict[str, Any]],
        protected_before: dict[int, str],
        rebuilt_from_epoch: int,
        settled_epoch: int,
        finalized_epoch: int,
        observed_epoch: int,
    ) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = (
            self.data_root
            / "reconciliation_backups"
            / f"reward-window-{rebuilt_from_epoch}-{observed_epoch}-{stamp}"
        )
        backup_dir.mkdir(parents=True, exist_ok=False)
        changed = [entry for entry in target_reports if entry["changed"]]
        target_by_path = {
            str(path): (role, path, candidate)
            for role, path, _candidate_path, candidate in targets
        }

        original_state_exists = self.state_file.is_file()
        state_backup: Optional[Path]
        if original_state_exists:
            state_backup = backup_dir / "state" / self.state_file.name
            state_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.state_file, state_backup)
        else:
            state_backup = None

        original_report_exists = report_file.is_file()
        report_backup: Optional[Path]
        if original_report_exists:
            report_backup = backup_dir / "report" / report_file.name
            report_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_file, report_backup)
        else:
            report_backup = None

        backup_paths: dict[str, Optional[Path]] = {}
        for entry in changed:
            target = Path(entry["path"])
            if target.is_file():
                category = "live" if target.parent == self.live_dir else "epochs"
                backup = backup_dir / category / target.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backup_paths[str(target)] = backup
            else:
                backup_paths[str(target)] = None

        obsolete_live = [
            path
            for path in sorted(self.live_dir.glob("epoch_*.json"))
            if path.name
            not in {
                f"epoch_{finalized_epoch}.json",
                f"epoch_{observed_epoch}.json",
            }
        ]
        retired_live: list[tuple[Path, Path]] = []
        obsolete_archive = [
            path
            for path in sorted(self.archive_dir.glob("epoch_*.json"))
            if path.stem.startswith("epoch_")
            and int(path.stem.removeprefix("epoch_")) > settled_epoch
        ]
        retired_archive: list[tuple[Path, Path]] = []

        try:
            for target in obsolete_live:
                backup = backup_dir / "retired_live" / target.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(backup))
                retired_live.append((target, backup))

            for target in obsolete_archive:
                backup = backup_dir / "retired_archive" / target.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(backup))
                retired_archive.append((target, backup))

            for entry in changed:
                _role, target, candidate = target_by_path[entry["path"]]
                self._write_payload(target, candidate)

            post_write_mismatches = []
            for entry in target_reports:
                target = Path(entry["path"])
                actual = sha256_file(target) if target.is_file() else None
                if actual != entry["candidate_sha256"]:
                    post_write_mismatches.append(
                        {
                            "path": str(target),
                            "expected": entry["candidate_sha256"],
                            "actual": actual,
                        }
                    )
            if post_write_mismatches:
                raise RewardReconciliationError(
                    f"hash post-write invalide: {post_write_mismatches}"
                )

            protected_after_write = _snapshot_hashes(
                self.archive_dir,
                self.start_epoch,
                self.historical_protection_end,
            )
            if protected_after_write != protected_before:
                raise RewardReconciliationError(
                    "plage historique protégée modifiée après écriture"
                )

            changed_paths = [entry["path"] for entry in changed]
            state_after = self._state_after(
                state_before,
                settled_epoch=settled_epoch,
                finalized_epoch=finalized_epoch,
                observed_epoch=observed_epoch,
                rebuilt_from_epoch=rebuilt_from_epoch,
                report_file=report_file,
                changed_targets=changed_paths,
            )
            result.update(
                {
                    "written": True,
                    "dry_run": False,
                    "backup_dir": str(backup_dir),
                    "state_updated": True,
                    "changed_targets": changed_paths,
                    "retired_live_targets": [str(path) for path, _backup in retired_live],
                    "retired_unsettled_archive_targets": [
                        str(path) for path, _backup in retired_archive
                    ],
                    "post_write_hashes": {
                        entry["path"]: sha256_file(Path(entry["path"]))
                        for entry in target_reports
                    },
                }
            )
            self._write_report(report_file, result)
            self._write_payload(self.state_file, state_after)
        except Exception:
            for entry in changed:
                target = Path(entry["path"])
                backup = backup_paths.get(str(target))
                if backup is not None and backup.is_file():
                    atomic_write_json(target, load_json(backup))
                elif backup is None and target.exists():
                    target.unlink()
            if original_state_exists and state_backup and state_backup.is_file():
                atomic_write_json(self.state_file, load_json(state_backup))
            elif not original_state_exists and self.state_file.exists():
                self.state_file.unlink()
            if original_report_exists and report_backup and report_backup.is_file():
                shutil.copy2(report_backup, report_file)
            elif not original_report_exists and report_file.exists():
                report_file.unlink()
            for target, backup in retired_live:
                if backup.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(backup), str(target))
            for target, backup in retired_archive:
                if backup.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(backup), str(target))
            raise
