#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Rebuild a pool history from its first active epoch and activate it safely."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_chain import CspoEChainSource
from core.blockfrost import (
    BlockfrostClient,
    BlockfrostPauseRequired,
    BlockfrostRequestBudget,
)
from core.CspoE_finalizer import CspoEFinalizer, atomic_write_json
from core.CspoE_legacy_contract import awards_for_epoch, build_legacy_snapshot, validate_exact_legacy_shape
from core.config import settings
from core.version import ENGINE_VERSION


class InitializationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_valid_snapshot(path: Path, epoch: int) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InitializationError(f"checkpoint epoch illisible: {path}: {exc}") from exc
    errors = validate_exact_legacy_shape(value, expected_epoch=epoch)
    if errors:
        raise InitializationError(f"checkpoint epoch {epoch} non canonique: {errors[:5]}")
    return value


def _checkpoint_update(path: Path | None, state: dict[str, Any] | None, **changes: Any) -> None:
    if path is None or state is None:
        return
    state.update(changes)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(path, state)


def initialization_window(first_epoch: int, observed_epoch: int) -> dict[str, int]:
    first_epoch = int(first_epoch)
    observed_epoch = int(observed_epoch)
    if first_epoch <= 0:
        raise InitializationError(
            "POOL_FIRST_EPOCH doit être la première epoch active du pool "
            "(habituellement epoch d'enregistrement + 2)"
        )
    settled = observed_epoch - 2
    if settled < first_epoch:
        raise InitializationError(
            f"historique insuffisant: première epoch {first_epoch}, epoch observée {observed_epoch}"
        )
    return {
        "first_epoch": first_epoch,
        "archive_end": settled,
        "closed_live_epoch": observed_epoch - 1,
        "current_live_epoch": observed_epoch,
    }


def _retire(path: Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = path.parent / "retired" / f"{label}-{stamp}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise InitializationError(f"destination de retrait déjà présente: {target}")
    shutil.move(str(path), str(target))
    return target


def _first_candidate(
    *, source: CspoEChainSource, awards_file: Path,
    first_epoch: int, observed_epoch: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = source.closed_epoch_evidence(first_epoch, observed_epoch, [], [])
    if not evidence.get("pool_registration_exact"):
        raise InitializationError("certificat/owners historiques non vérifiés")
    candidate = build_legacy_snapshot(
        epoch=first_epoch,
        previous={},
        all_stakes=list(evidence.get("all_stakes") or []),
        owner_addresses=list(evidence.get("owner_addresses") or []),
        rewards_by_stake=dict(evidence.get("rewards_by_stake") or {}),
        blocks=list(evidence.get("blocks") or []),
        awards=awards_for_epoch(awards_file, first_epoch),
        last_delegator_rows={},
        last_owner_rows={},
        start_epoch=first_epoch,
    )
    errors = validate_exact_legacy_shape(candidate, expected_epoch=first_epoch)
    stake_sum = sum(
        int(row.get("amount", 0) or 0)
        for row in evidence.get("all_stakes") or [] if isinstance(row, dict)
    )
    if int(candidate["pool"]["stake"]["_epoch_"]) != stake_sum:
        errors.append("pool.stake._epoch_ != somme Blockfrost epoch stakes")
    if int(candidate["blocks"]["epoch"]) != len(evidence.get("blocks") or []):
        errors.append("blocks.epoch != nombre de blocs Blockfrost")
    reward_total = int(candidate["pool"]["rewards"]["_epoch_"])
    if int(candidate["blocks"]["epoch"]) > 0 and reward_total <= 0:
        errors.append(
            f"rewards de l'epoch initiale {first_epoch} non visibles malgré des blocs"
        )
    pool_history = evidence.get("pool_history") or {}
    if isinstance(pool_history, dict) and pool_history:
        if pool_history.get("blocks") is not None and int(pool_history["blocks"] or 0) != int(candidate["blocks"]["epoch"]):
            errors.append("pool_history.blocks contredit les blocs détaillés")
        if pool_history.get("active_stake") is not None and int(pool_history["active_stake"] or 0) != stake_sum:
            errors.append("pool_history.active_stake contredit les stakes détaillés")
        if pool_history.get("rewards") is not None and int(pool_history["rewards"] or 0) != reward_total:
            errors.append("pool_history.rewards contredit les rewards des comptes")
    if errors:
        raise InitializationError(f"epoch initiale {first_epoch} non canonique: {errors[:10]}")
    return candidate, {
        "epoch": first_epoch,
        "stake_rows": len(evidence.get("all_stakes") or []),
        "blocks": len(evidence.get("blocks") or []),
        "owners": len(evidence.get("owner_addresses") or []),
    }


def reconstruct(
    *, output: Path, first_epoch: int, observed_epoch: int,
    pool_id: str, awards_file: Path, source: CspoEChainSource,
    checkpoint_path: Path | None = None,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    window = initialization_window(first_epoch, observed_epoch)
    archive_dir = output / "epochs"
    live_dir = output / "live"
    archive_dir.mkdir(parents=True, exist_ok=True)
    live_dir.mkdir(parents=True, exist_ok=True)

    # Existing snapshots are durable checkpoints. A hole followed by a later
    # archive file is rejected because the cumulative legacy contract must be
    # rebuilt strictly in order.
    missing_seen = False
    for epoch in range(first_epoch, window["archive_end"] + 1):
        present = (archive_dir / f"epoch_{epoch}.json").is_file()
        if not present:
            missing_seen = True
        elif missing_seen:
            raise InitializationError(f"checkpoint non contigu: epoch_{epoch}.json après une lacune")

    evidence_summary: dict[str, Any] = {}
    reused_epochs: list[int] = []
    first_path = archive_dir / f"epoch_{first_epoch}.json"
    if first_path.is_file():
        _load_valid_snapshot(first_path, first_epoch)
        reused_epochs.append(first_epoch)
    else:
        first, first_meta = _first_candidate(
            source=source,
            awards_file=awards_file,
            first_epoch=first_epoch,
            observed_epoch=observed_epoch,
        )
        atomic_write_json(first_path, first)
        evidence_summary[str(first_epoch)] = first_meta
        _checkpoint_update(
            checkpoint_path, checkpoint,
            status="running", phase="archive", last_completed_epoch=first_epoch,
        )
    finalizer = CspoEFinalizer(
        pool_id=pool_id,
        history_dir=archive_dir,
        awards_file=awards_file,
        start_epoch=first_epoch,
        historical_protection_end=first_epoch - 1,
        source=source,
    )

    for epoch in range(first_epoch + 1, window["archive_end"] + 1):
        path = archive_dir / f"epoch_{epoch}.json"
        if path.is_file():
            _load_valid_snapshot(path, epoch)
            reused_epochs.append(epoch)
            _checkpoint_update(
                checkpoint_path, checkpoint,
                status="running", phase="archive", last_completed_epoch=epoch,
            )
            continue
        print(f"CspoE initialization: settled epoch {epoch}", file=sys.stderr)
        candidate, metadata = finalizer.build_candidate(
            epoch, observed_epoch, history_dir=archive_dir, allow_late_reconciliation=True
        )
        errors = list(metadata.get("validation_errors") or [])
        reward_evidence = metadata.get("cross_checks", {}).get("reward_evidence") or {}
        blocks = int(candidate["blocks"]["epoch"])
        if blocks > 0 and int(reward_evidence.get("total", 0) or 0) <= 0:
            errors.append(f"rewards de l'epoch {epoch} non visibles malgré {blocks} bloc(s)")
        if errors:
            raise InitializationError(f"epoch {epoch} invalide: {errors[:10]}")
        atomic_write_json(path, candidate)
        evidence_summary[str(epoch)] = {
            "stake_rows": metadata.get("cross_checks", {}).get("epoch_stakes_count"),
            "blocks": blocks,
            "reward_total": reward_evidence.get("total", 0),
        }
        _checkpoint_update(
            checkpoint_path, checkpoint,
            status="running", phase="archive", last_completed_epoch=epoch,
        )

    closed_epoch = window["closed_live_epoch"]
    closed_history_path = archive_dir / f"epoch_{closed_epoch}.json"
    closed_live_path = live_dir / f"epoch_{closed_epoch}.json"
    if closed_live_path.is_file():
        _load_valid_snapshot(closed_live_path, closed_epoch)
        reused_epochs.append(closed_epoch)
        if closed_history_path.is_file():
            if sha256_file(closed_history_path) != sha256_file(closed_live_path):
                raise InitializationError(f"checkpoint divergent pour epoch {closed_epoch}")
        else:
            shutil.copy2(closed_live_path, closed_history_path)
    elif closed_history_path.is_file():
        _load_valid_snapshot(closed_history_path, closed_epoch)
        reused_epochs.append(closed_epoch)
    else:
        closed, metadata = finalizer.build_candidate(
            closed_epoch, observed_epoch, history_dir=archive_dir
        )
        errors = list(metadata.get("validation_errors") or [])
        if errors:
            raise InitializationError(f"epoch live fermée {closed_epoch} invalide: {errors[:10]}")
        atomic_write_json(closed_history_path, closed)
    _checkpoint_update(
        checkpoint_path, checkpoint,
        status="running", phase="closed_live", last_completed_epoch=closed_epoch,
    )

    current_epoch = window["current_live_epoch"]
    current_live_path = live_dir / f"epoch_{current_epoch}.json"
    if current_live_path.is_file():
        _load_valid_snapshot(current_live_path, current_epoch)
        reused_epochs.append(current_epoch)
    else:
        current, metadata = finalizer.build_live_candidate(
            current_epoch, observed_epoch=observed_epoch, history_dir=archive_dir
        )
        errors = list(metadata.get("validation_errors") or [])
        if errors:
            raise InitializationError(f"epoch live {current_epoch} invalide: {errors[:10]}")
        atomic_write_json(current_live_path, current)
    if closed_live_path.is_file():
        closed_history_path.unlink(missing_ok=True)
    else:
        os.replace(closed_history_path, closed_live_path)
    _checkpoint_update(
        checkpoint_path, checkpoint,
        status="completed", phase="completed", last_completed_epoch=current_epoch,
    )

    archive_hashes = {
        str(epoch): sha256_file(archive_dir / f"epoch_{epoch}.json")
        for epoch in range(first_epoch, window["archive_end"] + 1)
    }
    live_hashes = {
        str(epoch): sha256_file(live_dir / f"epoch_{epoch}.json")
        for epoch in (closed_epoch, current_epoch)
    }
    return {
        "window": window,
        "archive_epochs": len(archive_hashes),
        "archive_sha256": archive_hashes,
        "live_sha256": live_hashes,
        "evidence_summary": evidence_summary,
        "checkpoint_reused_epochs": sorted(set(reused_epochs)),
    }


def _activation_state(window: dict[str, int]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": ENGINE_VERSION,
        "pool_first_epoch": window["first_epoch"],
        "initialization_protected_end": window["archive_end"],
        "last_collected_epoch": window["current_live_epoch"],
        "last_finalized_epoch": window["closed_live_epoch"],
        "last_chain_finalized_epoch": window["closed_live_epoch"],
        "last_rewards_settled_epoch": window["archive_end"],
        "updated_at": now,
        "transition": {
            "status": "initialized",
            "source_epoch": window["closed_live_epoch"],
            "observed_epoch": window["current_live_epoch"],
            "confirmed_at": now,
            "reward_settled_epoch": window["archive_end"],
        },
        "reward_reconciliation": {
            "status": "initialized",
            "window": [window["archive_end"], window["current_live_epoch"]],
            "last_rewards_settled_epoch": window["archive_end"],
            "last_chain_finalized_epoch": window["closed_live_epoch"],
            "updated_at": now,
        },
    }


def _write_manifest(path: Path, source_dir: Path, first: int, last: int) -> None:
    lines = [
        "# CspoE is developped and maintained by BreizhStakePool.io ",
        "#",
        "# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].",
        "# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748",
        "# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2",
        "#",
        "# Consider delegate your voting power to our Breizh DRep [BZH] ",
        "# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h",
        "",
    ] + [
        f"{sha256_file(source_dir / f'epoch_{epoch}.json')}  epoch_{epoch}.json"
        for epoch in range(first, last + 1)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".protected.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def activate(reconstructed: Path, *, data_root: Path, window: dict[str, int]) -> dict[str, Any]:
    archive = data_root / "epochs"
    live = data_root / "live"
    state_file = data_root / "epoch_manager_state.json"
    manifest = data_root / "protected_epochs.sha256"
    if archive.is_dir() and any(archive.iterdir()):
        raise InitializationError("activation refusée: l'archive canonique n'est pas vide")
    if live.is_dir() and any(live.iterdir()):
        raise InitializationError("activation refusée: le répertoire live n'est pas vide")
    if state_file.exists():
        raise InitializationError("activation refusée: epoch_manager_state.json existe déjà")

    expected_archive = list(range(window["first_epoch"], window["archive_end"] + 1))
    expected_live = [window["closed_live_epoch"], window["current_live_epoch"]]
    required = [reconstructed / "epochs" / f"epoch_{e}.json" for e in expected_archive]
    required += [reconstructed / "live" / f"epoch_{e}.json" for e in expected_live]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise InitializationError(f"reconstruction incomplète: {missing[:20]}")

    data_root.mkdir(parents=True, exist_ok=True)
    stage_archive = data_root / f".epochs-initialize-{os.getpid()}"
    stage_live = data_root / f".live-initialize-{os.getpid()}"
    shutil.copytree(reconstructed / "epochs", stage_archive)
    shutil.copytree(reconstructed / "live", stage_live)
    retired: list[str] = []
    installed: list[Path] = []
    try:
        for target, label in ((archive, "empty-epochs"), (live, "empty-live")):
            if target.exists():
                retired.append(str(_retire(target, label)))
        os.replace(stage_archive, archive)
        installed.append(archive)
        os.replace(stage_live, live)
        installed.append(live)
        _write_manifest(manifest, archive, window["first_epoch"], window["archive_end"])
        atomic_write_json(state_file, _activation_state(window))
    except Exception:
        failed = data_root / f"failed-initialization-{os.getpid()}"
        failed.mkdir(parents=True, exist_ok=True)
        for path in (state_file, manifest, *installed, stage_archive, stage_live):
            if path.exists():
                shutil.move(str(path), str(failed / path.name))
        raise

    return {
        "activated": True,
        "archive": str(archive),
        "archive_range": [window["first_epoch"], window["archive_end"]],
        "live_epochs": expected_live,
        "state_file": str(state_file),
        "protected_manifest": str(manifest),
        "retired_empty_directories": retired,
    }


def _awards_fingerprint(path: Path) -> str:
    if not path.is_file():
        return "no-awards"
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return "no-awards"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InitializationError(f"awards JSON invalide: {path}: {exc}") from exc
    if not isinstance(value, list):
        raise InitializationError(f"awards doit contenir une liste JSON: {path}")
    if not value:
        return "no-awards"
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_checkpoint(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InitializationError(f"checkpoint illisible: {path}: {exc}") from exc
    if not isinstance(value, dict) or int(value.get("schema", 0)) != 1:
        raise InitializationError(f"checkpoint incompatible: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruit l'historique depuis POOL_FIRST_EPOCH. L'epoch N-2 est "
            "la dernière archive; N-1 et N restent live. Dry-run par défaut."
        )
    )
    parser.add_argument("--pool-first-epoch", type=int, default=settings.pool_first_epoch)
    parser.add_argument("--pool-id", default=settings.bech32_pool_id)
    parser.add_argument("--awards-file", default=settings.awards_file)
    parser.add_argument(
        "--output-dir",
        default=str(Path(settings.data_dir) / "CspoE" / "init" / "reconstructed"),
    )
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--report", default=None)
    parser.add_argument("--koios-check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--resume", action="store_true",
        help="reprend le staging/checkpoint existant sans répéter les epochs validées",
    )
    parser.add_argument("--replace-staging", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    if args.activate and not args.write:
        parser.error("--activate exige --write")
    if args.resume and not args.write:
        parser.error("--resume exige --write")
    if args.resume and args.replace_staging:
        parser.error("--resume et --replace-staging sont incompatibles")
    if args.pool_first_epoch <= 0:
        parser.error("POOL_FIRST_EPOCH doit être configuré")
    if not args.pool_id:
        parser.error("BECH32_POOL_ID doit être configuré")
    awards_file = Path(args.awards_file).expanduser().resolve()

    retained_previous = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    checkpoint_path: Path | None = None
    checkpoint: dict[str, Any] | None = None
    budget: BlockfrostRequestBudget | None = None
    try:
        if args.write:
            output = Path(args.output_dir).expanduser().resolve()
            if output.exists() and any(output.iterdir()):
                if args.replace_staging:
                    retained_previous = _retire(output, "reconstructed")
                elif not args.resume:
                    raise InitializationError(
                        f"sortie non vide: {output}; utiliser --resume pour poursuivre "
                        "ou --replace-staging pour recommencer"
                    )
            output.mkdir(parents=True, exist_ok=True)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="cspoe-initialize-dry-run-")
            output = Path(temporary.name)

        checkpoint_path = output / "initialization_checkpoint.json"
        if args.resume:
            if not checkpoint_path.is_file():
                raise InitializationError(f"--resume sans checkpoint: {checkpoint_path}")
            checkpoint = _read_checkpoint(checkpoint_path)
            if int(checkpoint.get("pool_first_epoch", -1)) != int(args.pool_first_epoch):
                raise InitializationError("POOL_FIRST_EPOCH diffère du checkpoint")
            if str(checkpoint.get("pool_id")) != str(args.pool_id):
                raise InitializationError("BECH32_POOL_ID diffère du checkpoint")
            if str(checkpoint.get("awards_fingerprint")) != _awards_fingerprint(awards_file):
                raise InitializationError(
                    "awards.json a changé depuis le début de la reconstruction; "
                    "utiliser --replace-staging pour éviter une histoire incohérente"
                )

        budget = BlockfrostRequestBudget(
            output / "blockfrost_usage.json",
            daily_budget=settings.blockfrost_daily_budget,
            reserve=settings.blockfrost_quota_reserve,
            auto_pause=settings.blockfrost_auto_pause,
        )
        usage_at_start = budget.snapshot()
        print(
            "CspoE initialization: Blockfrost local usage "
            f"{usage_at_start['requests_today']}/"
            f"{usage_at_start['proactive_threshold']} before safety pause; "
            f"counter={output / 'blockfrost_usage.json'}",
            file=sys.stderr,
        )

        def make_source() -> CspoEChainSource:
            client = BlockfrostClient(
                pool_id=args.pool_id,
                request_budget=budget,
                cache_dir=output / "blockfrost_cache",
            )
            return CspoEChainSource(
                args.pool_id,
                blockfrost=client,
                secondary_enabled=args.koios_check,
            )

        source = make_source()
        if checkpoint is None:
            observed = int(source.observed_epoch())
            checkpoint = {
                "schema": 1,
                "version": ENGINE_VERSION,
                "status": "running",
                "phase": "starting",
                "pool_id": str(args.pool_id),
                "pool_first_epoch": int(args.pool_first_epoch),
                "target_observed_epoch": observed,
                "window": initialization_window(args.pool_first_epoch, observed),
                "awards_file": str(awards_file),
                "awards_fingerprint": _awards_fingerprint(awards_file),
                "last_completed_epoch": args.pool_first_epoch - 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _checkpoint_update(checkpoint_path, checkpoint)
        else:
            observed = int(checkpoint["target_observed_epoch"])

        retargeted: list[dict[str, int]] = [
            dict(item) for item in (checkpoint.get("retargeted") or [])
            if isinstance(item, dict)
        ]
        while True:
            reconstruction = reconstruct(
                output=output,
                first_epoch=args.pool_first_epoch,
                observed_epoch=observed,
                pool_id=args.pool_id,
                awards_file=awards_file,
                source=source,
                checkpoint_path=checkpoint_path,
                checkpoint=checkpoint,
            )
            observed_after = int(source.observed_epoch())
            if observed_after == observed:
                break
            if observed_after < observed:
                raise InitializationError(
                    f"epoch Blockfrost a reculé pendant l'initialisation: {observed}->{observed_after}"
                )
            # A quota pause can span an epoch boundary. Preserve the completed
            # archive, retire only stale live/cache data, and extend the target.
            previous_target = observed
            for component, label in (
                (output / "live", f"live-target-{previous_target}"),
                (output / "blockfrost_cache", f"blockfrost-cache-target-{previous_target}"),
            ):
                if component.exists():
                    _retire(component, label)
            observed = observed_after
            retargeted.append({"from": previous_target, "to": observed})
            _checkpoint_update(
                checkpoint_path, checkpoint,
                status="running", phase="retargeted",
                target_observed_epoch=observed,
                window=initialization_window(args.pool_first_epoch, observed),
                retargeted=retargeted,
            )
            source = make_source()

        _checkpoint_update(
            checkpoint_path, checkpoint,
            status="completed", phase="completed",
            target_observed_epoch=observed,
            window=reconstruction["window"],
            pause=None,
            request_usage=budget.snapshot(),
        )
        result: dict[str, Any] = {
            "ok": True,
            "version": ENGINE_VERSION,
            "dry_run": not args.write,
            "source_of_truth": "Blockfrost",
            "pool_first_epoch": args.pool_first_epoch,
            "network_observed_epoch": observed,
            "archive_policy": "only epochs with settled rewards: through N-2",
            "live_policy": "closed N-1 plus current N",
            "reconstruction": reconstruction,
            "output_dir": str(output) if args.write else "temporary",
            "checkpoint": str(checkpoint_path) if args.write else "temporary",
            "resumed": bool(args.resume),
            "retargeted_after_epoch_change": retargeted,
            "blockfrost_request_usage": budget.snapshot(),
            "awards_policy": "operator-defined; missing, empty, or [] means no awards",
            "previous_staging_retained": str(retained_previous) if retained_previous else None,
            "existing_canonical_epochs_modified": False,
            "activation": None,
        }
        if args.activate:
            result["activation"] = activate(
                output,
                data_root=Path(args.data_root).expanduser().resolve(),
                window=reconstruction["window"],
            )
        if args.report:
            atomic_write_json(Path(args.report).expanduser().resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BlockfrostPauseRequired as exc:
        if checkpoint_path is not None and checkpoint is not None:
            _checkpoint_update(
                checkpoint_path, checkpoint,
                status="paused", phase=str(checkpoint.get("phase") or "unknown"),
                pause=exc.as_dict(),
                request_usage=budget.snapshot() if budget else exc.usage,
            )
        resumable = bool(args.write and checkpoint_path and checkpoint_path.is_file())
        resume_parts = [
            ".venv/bin/python", "scripts/CspoE_initialize.py", "--write", "--resume",
            "--pool-first-epoch", str(args.pool_first_epoch),
            "--pool-id", str(args.pool_id),
            "--awards-file", str(awards_file),
            "--output-dir", str(output),
            "--data-root", str(Path(args.data_root).expanduser().resolve()),
        ]
        if args.koios_check:
            resume_parts.append("--koios-check")
        if args.activate:
            resume_parts.append("--activate")
        if args.report:
            resume_parts.extend(["--report", str(Path(args.report).expanduser().resolve())])
        result = {
            "ok": False,
            "paused": True,
            "resumable": resumable,
            "exit_code": 75,
            "version": ENGINE_VERSION,
            "dry_run": not args.write,
            "pause": exc.as_dict(),
            "checkpoint": str(checkpoint_path) if resumable else None,
            "resume_command": " ".join(map(shlex.quote, resume_parts)) if resumable else None,
            "message": (
                "Initialisation suspendue proprement. Attendre resume_after (UTC), "
                "vérifier le quota dans le tableau de bord Blockfrost, puis relancer "
                "la commande de reprise. Les epochs déjà validées ne seront pas retéléchargées."
            ),
            "existing_canonical_epochs_modified": False,
        }
        if args.report:
            atomic_write_json(Path(args.report).expanduser().resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 75
    except Exception as exc:
        result = {
            "ok": False,
            "version": ENGINE_VERSION,
            "dry_run": not args.write,
            "error": str(exc),
            "existing_canonical_epochs_modified": False,
        }
        if args.report:
            atomic_write_json(Path(args.report).expanduser().resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
