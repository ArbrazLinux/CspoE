#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Validate canonical files, state watermarks and cumulative cascades."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_legacy_contract import validate_exact_legacy_shape
from core.config import settings
from core.data_store import PoolDataStore
from core.pooldata import atomic_write_json
from core.version import ENGINE_VERSION


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_int(value: dict[str, Any], *path: str) -> int:
    current: Any = value
    for key in path:
        current = current.get(key) if isinstance(current, dict) else None
    try:
        return int(current or 0)
    except (TypeError, ValueError):
        return 0


def cascade_errors(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    previous_epoch = int(previous["epoch"])
    current_epoch = int(current["epoch"])
    errors: list[str] = []
    if current_epoch != previous_epoch + 1:
        return [f"séquence non contiguë: {previous_epoch}->{current_epoch}"]

    cumulative = (
        ("pool.stake", ("pool", "stake", "_sum_"), ("pool", "stake", "_epoch_")),
        ("pool.rewards", ("pool", "rewards", "_sum_"), ("pool", "rewards", "_epoch_")),
        ("owners.pledge", ("owners", "pledge", "_sum_"), ("owners", "pledge", "_epoch_")),
        ("owners.rewards", ("owners", "rewards", "_sum_"), ("owners", "rewards", "_epoch_")),
        ("delegators.stake", ("delegators", "stake", "_sum_"), ("delegators", "stake", "_epoch_")),
        ("delegators.rewards", ("delegators", "rewards", "_sum_"), ("delegators", "rewards", "_epoch_")),
        ("bonuses", ("bonuses", "_sum_"), ("bonuses", "amount")),
    )
    for label, total_path, epoch_path in cumulative:
        expected = nested_int(previous, *total_path) + nested_int(current, *epoch_path)
        actual = nested_int(current, *total_path)
        if actual != expected:
            errors.append(f"{label} cumul {actual} != {expected}")

    block_expected = nested_int(previous, "blocks", "total_blocks") + nested_int(
        current, "blocks", "epoch"
    )
    if nested_int(current, "blocks", "total_blocks") != block_expected:
        errors.append(
            f"blocks.total_blocks {nested_int(current, 'blocks', 'total_blocks')} != {block_expected}"
        )
    if nested_int(current, "pool", "stake", "_previous_") != nested_int(
        previous, "pool", "stake", "_epoch_"
    ):
        errors.append("pool.stake._previous_ ne correspond pas à l'epoch précédente")
    if nested_int(current, "delegators", "previous_delegsNb") != nested_int(
        previous, "delegators", "delegsNb"
    ):
        errors.append("delegators.previous_delegsNb incohérent")
    if nested_int(current, "owners", "previous_ownersNb") != nested_int(
        previous, "owners", "ownersNb"
    ):
        errors.append("owners.previous_ownersNb incohérent")
    return errors


def load_hash_manifest(path: Path) -> dict[int, str]:
    if not path.is_file():
        return {}
    result: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+epoch_(\d+)\.json", line)
        if not match:
            raise ValueError(f"ligne de manifeste invalide: {line}")
        result[int(match.group(2))] = match.group(1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(Path(settings.data_dir) / "CspoE"))
    parser.add_argument("--start-epoch", type=int, default=settings.pool_first_epoch)
    parser.add_argument("--end-epoch", type=int, default=None)
    parser.add_argument("--protected-end", type=int, default=None)
    parser.add_argument("--protected-hashes", default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    store = PoolDataStore(args.data_root)
    archive_files = store.archive_files()
    state = store.state()
    if args.start_epoch <= 0:
        parser.error("POOL_FIRST_EPOCH doit être configuré ou --start-epoch fourni")
    protected_end = (
        int(args.protected_end)
        if args.protected_end is not None
        else int(state.get("initialization_protected_end", args.start_epoch - 1))
    )
    shape_errors = []
    cascade = []
    inventory_errors = []
    state_errors = []

    if not archive_files:
        inventory_errors.append("archive vide")
        end_epoch = args.end_epoch
    else:
        settled_state = state.get("last_rewards_settled_epoch")
        end_epoch = (
            int(args.end_epoch)
            if args.end_epoch is not None
            else int(settled_state)
            if settled_state is not None
            else max(archive_files)
        )
        expected = set(range(args.start_epoch, end_epoch + 1))
        missing = sorted(expected - set(archive_files))
        extra = sorted(e for e in archive_files if e < args.start_epoch or e > end_epoch)
        if missing:
            inventory_errors.append(f"epochs archivés absents: {missing[:50]}")
        if extra:
            inventory_errors.append(f"epochs archivés hors plage: {extra[:50]}")

        for epoch in range(args.start_epoch, end_epoch + 1):
            path = archive_files.get(epoch)
            if path is None:
                continue
            snapshot = store.load_json(path)
            errors = validate_exact_legacy_shape(snapshot, expected_epoch=epoch)
            if errors:
                shape_errors.append({"epoch": epoch, "file": str(path), "errors": errors[:50]})

    live_files = store.live_files()
    collected = state.get("last_collected_epoch")
    finalized = state.get("last_chain_finalized_epoch", state.get("last_finalized_epoch"))
    settled = state.get("last_rewards_settled_epoch")
    if settled is not None and archive_files and int(settled) != max(archive_files):
        state_errors.append(
            f"last_rewards_settled_epoch={settled} mais dernière archive={max(archive_files)}"
        )
    if settled is not None and finalized is not None and int(settled) > int(finalized):
        state_errors.append("last_rewards_settled_epoch > last_chain_finalized_epoch")
    if collected is not None:
        collected = int(collected)
        expected_live = {collected}
        if finalized is not None:
            expected_live.add(int(finalized))
        missing_live = sorted(expected_live - set(live_files))
        if missing_live:
            state_errors.append(f"epochs live absentes: {missing_live}")
        stale_live = sorted(epoch for epoch in live_files if epoch not in expected_live)
        if stale_live:
            inventory_errors.append(f"copies live obsolètes: {stale_live}")
        if finalized is not None and int(finalized) >= collected:
            state_errors.append("last_chain_finalized_epoch >= last_collected_epoch")
    for epoch, path in live_files.items():
        snapshot = store.load_json(path)
        errors = validate_exact_legacy_shape(snapshot, expected_epoch=epoch)
        if errors:
            shape_errors.append({"epoch": epoch, "file": str(path), "errors": errors[:50]})

    combined_files = dict(archive_files)
    for epoch, path in live_files.items():
        if epoch in combined_files:
            inventory_errors.append(f"epoch {epoch} présente à la fois en archive et en live")
        else:
            combined_files[epoch] = path
    previous = None
    for epoch in sorted(combined_files):
        if epoch < args.start_epoch:
            continue
        snapshot = store.load_json(combined_files[epoch])
        if previous is not None:
            errors = cascade_errors(previous, snapshot)
            if errors:
                cascade.append({"epoch": epoch, "errors": errors})
        previous = snapshot

    manifest_path = Path(args.protected_hashes).expanduser().resolve() if args.protected_hashes else (
        store.data_root / "protected_epochs.sha256"
    )
    hash_manifest_errors = []
    manifest = load_hash_manifest(manifest_path)
    if manifest:
        expected_protected = set(range(args.start_epoch, protected_end + 1))
        if set(manifest) != expected_protected:
            hash_manifest_errors.append("plage du manifeste historique incomplète")
        for epoch, expected_hash in manifest.items():
            path = archive_files.get(epoch)
            if path is None:
                hash_manifest_errors.append(f"epoch protégée absente: {epoch}")
            elif sha256_file(path) != expected_hash:
                hash_manifest_errors.append(f"hash protégé modifié: epoch {epoch}")

    ok = not any((inventory_errors, state_errors, shape_errors, cascade, hash_manifest_errors))
    result = {
        "ok": ok,
        "version": ENGINE_VERSION,
        "data_root": str(store.data_root),
        "archive_range": [min(archive_files), max(archive_files)] if archive_files else None,
        "archive_count": len(archive_files),
        "live_epochs": sorted(live_files),
        "state": state,
        "inventory_errors": inventory_errors,
        "state_errors": state_errors,
        "shape_errors": shape_errors,
        "cascade_errors": cascade,
        "protected_hash_manifest": str(manifest_path) if manifest else None,
        "protected_range": [args.start_epoch, protected_end],
        "protected_hash_errors": hash_manifest_errors,
    }
    if args.report:
        atomic_write_json(Path(args.report).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
