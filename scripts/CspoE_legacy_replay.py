#!/usr/bin/env python3
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.CspoE_legacy_contract import (
    awards_for_epoch,
    build_legacy_snapshot,
    delegator_rows,
    loyalty_from_epoch_count,
    owner_rows,
    validate_exact_legacy_shape,
)
from core.config import settings
from core.version import ENGINE_VERSION

VERSION = ENGINE_VERSION
TEST_VERSION = "legacy-full-replay-address-index"
DEFAULT_START = settings.pool_first_epoch


class ReplayError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _history_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict) and isinstance(x.get("epoch"), int)]
    if isinstance(value, dict):
        if isinstance(value.get("history"), list):
            return [x for x in value["history"] if isinstance(x, dict) and isinstance(x.get("epoch"), int)]
        if isinstance(value.get("epoch"), int):
            return [value]
    return []


def _index_rows(rows: Iterable[dict[str, Any]], origin: str, index: dict[int, dict[str, Any]], origins: dict[int, str]) -> None:
    for row in rows:
        epoch = int(row["epoch"])
        if epoch in index:
            raise ReplayError(f"epoch {epoch} présent plusieurs fois: {origins[epoch]} et {origin}")
        index[epoch] = copy.deepcopy(row)
        origins[epoch] = origin


def load_reference(source: Path) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    """Load immutable legacy snapshots from a directory or a zip archive.

    Directory priority is pooldata_*.json. If none exist, epoch_*.json is used.
    This deliberately avoids silently mixing two reference sets.
    """
    index: dict[int, dict[str, Any]] = {}
    origins: dict[int, str] = {}
    source = source.expanduser().resolve()
    if source.is_dir():
        files = sorted(source.glob("pooldata_*.json"))
        if not files:
            files = sorted(source.glob("epoch_*.json"))
        if not files:
            raise ReplayError(f"aucun pooldata_*.json/epoch_*.json dans {source}")
        for path in files:
            try:
                value = load_json(path)
            except Exception as exc:
                raise ReplayError(f"JSON legacy invalide {path}: {exc}") from exc
            _index_rows(_history_rows(value), str(path), index, origins)
        return index, origins

    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            pool_names = sorted(n for n in zf.namelist() if Path(n).name.startswith("pooldata_") and n.endswith(".json"))
            epoch_names = sorted(n for n in zf.namelist() if Path(n).name.startswith("epoch_") and n.endswith(".json"))
            names = pool_names or epoch_names
            if not names:
                raise ReplayError(f"aucune référence historique JSON dans {source}")
            for name in names:
                try:
                    value = json.loads(zf.read(name))
                except Exception as exc:
                    raise ReplayError(f"JSON legacy invalide {source}:{name}: {exc}") from exc
                _index_rows(_history_rows(value), f"{source}:{name}", index, origins)
        return index, origins

    raise ReplayError(f"source legacy absente/non supportée: {source}")


def discover_legacy_source(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    candidates = (
        ROOT / "data" / "CspoE" / "legacy_reference",
        ROOT / "data" / "CspoE" / "pooldata",
    )
    for path in candidates:
        if path.exists():
            return path
    raise ReplayError("référence legacy introuvable; utiliser --legacy-source")


def discover_awards(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    if settings.awards_file:
        return Path(settings.awards_file)
    # Absence is a valid public/operator configuration: no local bonuses.
    return ROOT / "data" / "awards.json"


def strict_diff(actual: Any, expected: Any, path: str = "", limit: int = 100) -> list[dict[str, Any]]:
    """Strict JSON diff: type, dictionary key order, list order and scalar value."""
    diffs: list[dict[str, Any]] = []

    def add(kind: str, p: str, a: Any, e: Any) -> None:
        if len(diffs) < limit:
            diffs.append({"path": p or "$", "kind": kind, "actual": a, "expected": e})

    def walk(a: Any, e: Any, p: str) -> None:
        if len(diffs) >= limit:
            return
        if type(a) is not type(e):
            add("type", p, type(a).__name__, type(e).__name__)
            return
        if isinstance(a, dict):
            ak, ek = list(a.keys()), list(e.keys())
            if ak != ek:
                add("dict_key_order_or_set", p, ak, ek)
            for key in ek:
                np = f"{p}.{key}" if p else key
                if key not in a:
                    add("missing_key", np, None, e[key])
                elif key in e:
                    walk(a[key], e[key], np)
            for key in ak:
                if key not in e:
                    np = f"{p}.{key}" if p else key
                    add("extra_key", np, a[key], None)
            return
        if isinstance(a, list):
            if len(a) != len(e):
                add("list_length", p, len(a), len(e))
            for i, (av, ev) in enumerate(zip(a, e)):
                walk(av, ev, f"{p}[{i}]")
            return
        if a != e:
            add("value", p, a, e)

    walk(actual, expected, path)
    return diffs



def delegator_address_index(
    snapshot: dict[str, Any], *, side: str
) -> tuple[dict[str, dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Build the authoritative delegator index keyed by ``stake_address``.

    Array positions are retained only as an order audit.  Missing/invalid
    addresses, duplicates, and a declared count inconsistent with the list are
    blocking data errors: they must never be hidden by order normalization.
    """
    problems: list[dict[str, Any]] = []
    delegators = snapshot.get("delegators")
    if not isinstance(delegators, dict):
        return {}, [], [{
            "path": "delegators",
            "kind": "delegator_index_invalid_container",
            "side": side,
            "actual": type(delegators).__name__,
            "expected": "dict",
        }]

    rows = delegators.get("delegator")
    if not isinstance(rows, list):
        return {}, [], [{
            "path": "delegators.delegator",
            "kind": "delegator_index_invalid_container",
            "side": side,
            "actual": type(rows).__name__,
            "expected": "list",
        }]

    declared_count = delegators.get("delegsNb")
    if type(declared_count) is not int or declared_count != len(rows):
        problems.append({
            "path": "delegators.delegsNb",
            "kind": "delegator_count_mismatch",
            "side": side,
            "actual": declared_count,
            "expected": len(rows),
        })

    index: dict[str, dict[str, Any]] = {}
    positions: dict[str, int] = {}
    order: list[str] = []
    for position, row in enumerate(rows):
        path = f"delegators.delegator[{position}]"
        if not isinstance(row, dict):
            problems.append({
                "path": path,
                "kind": "delegator_index_invalid_row",
                "side": side,
                "actual": type(row).__name__,
                "expected": "dict with a unique non-empty stake_address",
            })
            continue
        address = row.get("stake_address")
        if not isinstance(address, str) or not address:
            problems.append({
                "path": f"{path}.stake_address",
                "kind": "delegator_index_missing_address",
                "side": side,
                "actual": address,
                "expected": "unique non-empty string",
            })
            continue
        if address in index:
            problems.append({
                "path": f"{path}.stake_address",
                "kind": "delegator_index_duplicate_address",
                "side": side,
                "actual": {"stake_address": address, "positions": [positions[address], position]},
                "expected": "one row per stake_address",
            })
            continue
        index[address] = row
        positions[address] = position
        order.append(address)
    return index, order, problems


def delegator_order_normalized(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Return a deep copy where only delegators.delegator is ordered by stake_address.

    The legacy engine copied the raw order returned by Blockfrost's epoch-stakes
    endpoint. That order is not a Cardano/business datum and is not stable across
    historical re-queries. All other list ordering (owners, blocks, bonuses, etc.)
    remains strict.
    """
    out = copy.deepcopy(snapshot)
    delegators = out.get("delegators")
    if not isinstance(delegators, dict):
        return out
    rows = delegators.get("delegator")
    if not isinstance(rows, list):
        return out

    index, _order, problems = delegator_address_index(out, side="normalized")
    if problems:
        return out
    delegators["delegator"] = [index[address] for address in sorted(index)]
    return out


def delegator_order_only_diff(actual: dict[str, Any], expected: dict[str, Any], limit: int = 100) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Return (positional_diffs, data_diffs).

    data_diffs compares every field/type/key/list strictly after aligning only the
    delegator list by stake_address. Therefore a non-empty positional diff with an
    empty data diff means the complete delegator records are identical and only
    their array positions differ.
    """
    positional = strict_diff(actual, expected, limit=limit)
    actual_index, _actual_order, actual_problems = delegator_address_index(actual, side="actual")
    expected_index, _expected_order, expected_problems = delegator_address_index(expected, side="expected")
    index_problems = actual_problems + expected_problems
    if index_problems:
        return positional, index_problems[:limit]
    if not positional:
        return [], []

    actual_addresses = set(actual_index)
    expected_addresses = set(expected_index)
    address_set_diff: list[dict[str, Any]] = []
    if actual_addresses != expected_addresses:
        address_set_diff.append({
            "path": "delegators.delegator",
            "kind": "delegator_stake_address_set",
            "actual": {
                "missing": sorted(expected_addresses - actual_addresses),
                "extra": sorted(actual_addresses - expected_addresses),
            },
            "expected": "identical stake_address set",
        })
    data = strict_diff(
        delegator_order_normalized(actual),
        delegator_order_normalized(expected),
        limit=max(0, limit - len(address_set_diff)),
    )
    return positional, (address_set_diff + data)[:limit]

def reference_facts(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract only external/per-epoch facts, never cumulative business state."""
    all_stakes: list[dict[str, Any]] = []
    owners: list[str] = []
    rewards: dict[str, int] = {}
    for row in owner_rows(snapshot):
        address = str(row.get("stake_address") or "")
        if not address:
            continue
        owners.append(address)
        stake = row.get("stake") if isinstance(row.get("stake"), dict) else {}
        rew = row.get("rewards") if isinstance(row.get("rewards"), dict) else {}
        all_stakes.append({"stake_address": address, "amount": str(int(stake.get("_epoch_", 0) or 0))})
        rewards[address] = int(rew.get("_epoch_", 0) or 0)
    for row in delegator_rows(snapshot):
        address = str(row.get("stake_address") or "")
        if not address:
            continue
        stake = row.get("stake") if isinstance(row.get("stake"), dict) else {}
        rew = row.get("rewards") if isinstance(row.get("rewards"), dict) else {}
        all_stakes.append({"stake_address": address, "amount": str(int(stake.get("_epoch_", 0) or 0))})
        rewards[address] = int(rew.get("_epoch_", 0) or 0)
    blocks_obj = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), dict) else {}
    blocks = copy.deepcopy(blocks_obj.get("block") if isinstance(blocks_obj.get("block"), list) else [])
    return {"all_stakes": all_stakes, "owner_addresses": owners, "rewards_by_stake": rewards, "blocks": blocks}


@dataclass
class FactSource:
    mode: str
    reference: dict[int, dict[str, Any]]
    awards_file: Path
    cache_dir: Optional[Path] = None
    refresh_cache: bool = False
    blockfrost: Optional[Any] = None

    def facts(self, epoch: int, previous_delegators=None, previous_owners=None) -> dict[str, Any]:
        if self.mode == "reference-facts":
            facts = reference_facts(self.reference[epoch])
        elif self.mode == "blockfrost":
            if self.blockfrost is None:
                raise ReplayError("BlockfrostClient absent")
            cache = self.cache_dir / f"epoch_{epoch}.json" if self.cache_dir else None
            cached = load_json(cache) if cache and cache.is_file() and not self.refresh_cache else None
            # cache_version=4 adds stake-key registration/deregistration state to the zero-holder decision.
            # Older code could falsely keep a deregistered address at zero forever;
            # v2 used account history; v1 cached the incomplete current stake set.
            if isinstance(cached, dict) and cached.get("cache_version") == 4:
                facts = cached
            elif isinstance(cached, dict) and cached.get("cache_version") == 3:
                # Fast deterministic migration from v6.3.8 cache.  v3 already
                # contains valid owners/rewards/blocks and the Blockfrost epoch
                # stake rows, but some zero holders may have been artificially
                # reinserted using delegation history alone.  Remove only those
                # synthetic rows and replay the new registration-aware decision.
                old_completion = cached.get("stake_completion") if isinstance(cached.get("stake_completion"), dict) else {}
                old_recovered = {str(x) for x in (old_completion.get("recovered_zero_holders") or []) if x}
                raw_stakes = [
                    copy.deepcopy(row) for row in (cached.get("all_stakes") or [])
                    if isinstance(row, dict)
                    and str(row.get("stake_address") or row.get("address") or "") not in old_recovered
                ]
                completed, completion = self.blockfrost.complete_epoch_stakes(
                    epoch, raw_stakes,
                    previous_delegators=previous_delegators,
                    owner_addresses=cached.get("owner_addresses") or [],
                    pool_id=self.blockfrost.pool_id,
                )
                facts = copy.deepcopy(cached)
                facts["cache_version"] = 4
                facts["all_stakes"] = completed
                facts["stake_completion"] = completion
                facts["cache_migrated_from"] = 3
                if cache:
                    dump_json(cache, facts)
            else:
                evidence = self.blockfrost.closed_epoch_evidence(
                    epoch, epoch + 1, previous_delegators=previous_delegators, previous_owners=previous_owners
                )
                facts = {
                    "cache_version": 4,
                    "all_stakes": evidence.get("all_stakes") or [],
                    "owner_addresses": evidence.get("owner_addresses") or [],
                    "rewards_by_stake": evidence.get("rewards_by_stake") or {},
                    "blocks": evidence.get("blocks") or [],
                    "stake_completion": evidence.get("stake_completion") or {},
                }
                if cache:
                    dump_json(cache, facts)
        else:
            raise ReplayError(f"mode inconnu: {self.mode}")
        facts["awards"] = awards_for_epoch(self.awards_file, epoch)
        return facts


def adjusted_expected(snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply the one and only accepted difference: delegator loyalty."""
    expected = copy.deepcopy(snapshot)
    anomalies = []
    for i, row in enumerate(delegator_rows(expected)):
        original = row.get("loyalty")
        if original not in (0, 0.0):
            anomalies.append({"row": i, "stake_address": row.get("stake_address"), "legacy_loyalty": original})
        row["loyalty"] = loyalty_from_epoch_count(int(row.get("epoch_count", 0) or 0))
    return expected, anomalies


def run(args: argparse.Namespace) -> dict[str, Any]:
    awards_file = discover_awards(args.awards_file)
    legacy_source: Optional[Path] = None
    reference: dict[int, dict[str, Any]] = {}
    origins: dict[int, str] = {}
    if args.mode == "reference-facts":
        legacy_source = discover_legacy_source(args.legacy_source)
        reference, origins = load_reference(legacy_source)
    replay_epochs = list(range(args.start_epoch, args.end_epoch + 1))
    expected_epochs = list(range(args.start_epoch, args.end_epoch + 1))
    missing = [e for e in replay_epochs if e not in reference]
    if args.mode == "reference-facts" and missing:
        raise ReplayError(f"epochs legacy manquants: {missing[:20]}{'...' if len(missing)>20 else ''}")

    output_tmp = None
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_tmp = tempfile.mkdtemp(prefix="cspoe_legacy_replay_")
        output_dir = Path(output_tmp)

    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else ROOT / "data" / "CspoE" / "replay_cache" / "blockfrost"
    bf = None
    if args.mode == "blockfrost":
        from core.blockfrost import BlockfrostClient

        cache_dir.mkdir(parents=True, exist_ok=True)
        bf = BlockfrostClient(project_id=args.blockfrost_project_id or None, pool_id=args.pool_id or None)

    fact_source = FactSource(
        mode=args.mode,
        reference=reference,
        awards_file=awards_file,
        cache_dir=cache_dir if args.mode == "blockfrost" else None,
        refresh_cache=args.refresh_cache,
        blockfrost=bf,
    )

    previous: dict[str, Any] = {}
    last_delegator_rows: dict[str, dict[str, Any]] = {}
    last_owner_rows: dict[str, dict[str, Any]] = {}
    first_gone_pending = args.mode == "reference-facts"
    first_gone_consumed_epoch = None
    mismatches = []
    order_only_mismatches = []
    shape_errors = []
    legacy_loyalty_anomalies = []
    data_exact_matches = 0
    positional_exact_matches = 0
    loyalty_exception_count = 0

    for epoch in replay_epochs:
        expected_raw = reference.get(epoch)
        previous_deleg_order=[str(x.get('stake_address') or '') for x in delegator_rows(previous)]
        previous_owner_order=[str(x.get('stake_address') or '') for x in owner_rows(previous)]
        facts = fact_source.facts(epoch, previous_deleg_order, previous_owner_order)
        current_owner_set = set(map(str, facts.get("owner_addresses") or []))
        current_deleg_set = {
            str(x.get("stake_address") or x.get("address") or "")
            for x in facts.get("all_stakes") or []
            if isinstance(x, dict)
            and str(x.get("stake_address") or x.get("address") or "")
            and str(x.get("stake_address") or x.get("address") or "") not in current_owner_set
        }
        previous_deleg_set = {str(x.get("stake_address") or "") for x in delegator_rows(previous)}
        gone_now = previous_deleg_set - current_deleg_set

        candidate = build_legacy_snapshot(
            epoch=epoch,
            previous=previous,
            all_stakes=facts.get("all_stakes") or [],
            owner_addresses=facts.get("owner_addresses") or [],
            rewards_by_stake={str(k): int(v or 0) for k, v in (facts.get("rewards_by_stake") or {}).items()},
            blocks=facts.get("blocks") or [],
            awards=facts.get("awards") or [],
            last_delegator_rows=last_delegator_rows,
            last_owner_rows=last_owner_rows,
            start_epoch=args.start_epoch,
            first_gone_legacy_bug=first_gone_pending,
        )
        if first_gone_pending and gone_now:
            first_gone_pending = False
            first_gone_consumed_epoch = epoch

        if epoch >= args.start_epoch:
            se = validate_exact_legacy_shape(candidate, expected_epoch=epoch)
            if se:
                shape_errors.append({"epoch": epoch, "errors": se[: args.max_diffs]})

            if args.mode == "reference-facts" and expected_raw is not None:
                expected, anomalies = adjusted_expected(expected_raw)
                if anomalies:
                    legacy_loyalty_anomalies.append({"epoch": epoch, "rows": anomalies})
                loyalty_exception_count += len(delegator_rows(expected))
                positional_diffs, data_diffs = delegator_order_only_diff(
                    candidate, expected, limit=args.max_diffs
                )
                if data_diffs:
                    mismatches.append({
                        "epoch": epoch,
                        "reference_origin": origins.get(epoch),
                        "diffs": data_diffs,
                        "positional_diffs": positional_diffs,
                    })
                    if args.stop_on_first_mismatch:
                        dump_json(output_dir / f"epoch_{epoch}.json", candidate)
                        break
                else:
                    data_exact_matches += 1
                    if positional_diffs:
                        order_only_mismatches.append({
                            "epoch": epoch,
                            "reference_origin": origins.get(epoch),
                            "diffs": positional_diffs,
                        })
                        if args.require_delegator_order and args.stop_on_first_mismatch:
                            dump_json(output_dir / f"epoch_{epoch}.json", candidate)
                            break
                    else:
                        positional_exact_matches += 1
            elif not se:
                data_exact_matches += 1
                positional_exact_matches += 1

        # Persist the complete replay (including warm-up epochs) when requested.
        dump_json(output_dir / f"epoch_{epoch}.json", candidate)
        for row in delegator_rows(candidate):
            address = str(row.get("stake_address") or "")
            if address:
                last_delegator_rows[address] = copy.deepcopy(row)
        for row in owner_rows(candidate):
            address = str(row.get("stake_address") or "")
            if address:
                last_owner_rows[address] = copy.deepcopy(row)
        previous = candidate

    processed = data_exact_matches + len(mismatches)
    ok = (
        processed == len(expected_epochs)
        and not mismatches
        and not shape_errors
        and not legacy_loyalty_anomalies
        and (not args.require_delegator_order or not order_only_mismatches)
    )
    report = {
        "ok": ok,
        "version": VERSION,
        "test_version": TEST_VERSION,
        "mode": args.mode,
        "contract": (
            "exact legacy pool_data structure/types/values; delegators are matched by stake_address "
            "because legacy copied Blockfrost response order; only delegators[*].loyalty is recalculated"
        ),
        "delegator_order_policy": (
            "audited separately; all non-delegator list ordering remains strict; "
            "use --require-delegator-order to make historical API row order blocking"
        ),
        "delegator_identity_key": "stake_address",
        "delegator_index_policy": (
            "stake_address is authoritative; array position is non-authoritative; "
            "missing/duplicate addresses and list/count inconsistencies are blocking"
        ),
        "reference_source": str(legacy_source) if legacy_source else None,
        "awards_file": str(awards_file),
        "range": [args.start_epoch, args.end_epoch],
        "epochs_reconstructed_from": args.start_epoch,
        "epochs_reconstructed": len(replay_epochs),
        "epochs_expected": len(expected_epochs),
        "epochs_processed": processed,
        "exact_matches": data_exact_matches,
        "data_exact_matches": data_exact_matches,
        "positional_exact_matches": positional_exact_matches,
        "order_only_mismatch_epochs_total": len(order_only_mismatches),
        "order_only_mismatch_epochs": [x["epoch"] for x in order_only_mismatches],
        "order_only_mismatches": order_only_mismatches[: args.max_diffs],
        "loyalty_exception_rows": loyalty_exception_count,
        "legacy_loyalty_must_be_zero": True,
        "legacy_loyalty_anomalies": legacy_loyalty_anomalies[: args.max_diffs],
        "first_gone_index0_quirk_consumed_epoch": first_gone_consumed_epoch,
        "shape_errors": shape_errors[: args.max_diffs],
        "mismatch_epochs_total": len(mismatches),
        "first_mismatch_epoch": mismatches[0]["epoch"] if mismatches else None,
        "mismatches": mismatches[: args.max_diffs],
        "blockfrost_cache_dir": str(cache_dir) if args.mode == "blockfrost" else None,
        "reconstructed_output_dir": str(output_dir) if args.output_dir else "temporary",
    }
    if args.report:
        dump_json(Path(args.report).expanduser().resolve(), report)
    if output_tmp and not args.keep_temporary_output:
        shutil.rmtree(output_tmp, ignore_errors=True)
    return report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Reconstruit séquentiellement tout l'historique CspoE au contrat pool_data legacy "
            "et compare strictement chaque champ. Les délégateurs sont alignés par stake_address; "
            "leur ordre Blockfrost historique est audité séparément. Seule loyalty est recalculée."
        )
    )
    p.add_argument("--legacy-source", default=None, help="répertoire pooldata_*.json/epoch_*.json ou archive ZIP; auto-détection sinon")
    p.add_argument("--awards-file", default=None)
    p.add_argument("--start-epoch", type=int, default=DEFAULT_START)
    p.add_argument("--end-epoch", type=int, default=None)
    p.add_argument("--mode", choices=("reference-facts", "blockfrost"), default="blockfrost")
    p.add_argument("--pool-id", default=settings.bech32_pool_id)
    p.add_argument("--blockfrost-project-id", default=None, help="déconseillé en ligne de commande; préférer CspoE.conf/env")
    p.add_argument("--cache-dir", default=None)
    p.add_argument("--refresh-cache", action="store_true")
    p.add_argument("--output-dir", default=None, help="conserver les 400 snapshots reconstruits")
    p.add_argument("--keep-temporary-output", action="store_true")
    p.add_argument("--report", default=None)
    p.add_argument("--max-diffs", type=int, default=50)
    p.add_argument("--stop-on-first-mismatch", action="store_true")
    p.add_argument(
        "--require-delegator-order",
        action="store_true",
        help=(
            "rend l'ordre historique exact de delegators.delegator bloquant. "
            "Par défaut cet ordre est audité séparément car il dépend de l'ordre de réponse Blockfrost."
        ),
    )
    return p


def main() -> int:
    args = parser().parse_args()
    if args.start_epoch <= 0:
        print(json.dumps({"ok": False, "error": "POOL_FIRST_EPOCH/start_epoch doit être > 0"}, ensure_ascii=False, indent=2))
        return 2
    if args.end_epoch is None:
        if args.mode == "reference-facts":
            print(json.dumps({"ok": False, "error": "--end-epoch requis en mode reference-facts"}, ensure_ascii=False, indent=2))
            return 2
        from core.blockfrost import BlockfrostClient
        args.end_epoch = int(BlockfrostClient(project_id=args.blockfrost_project_id or None, pool_id=args.pool_id or None).epoch()["epoch"]) - 2
    if args.end_epoch < args.start_epoch:
        print(json.dumps({"ok": False, "error": "plage invalide"}, ensure_ascii=False, indent=2))
        return 2
    try:
        result = run(args)
    except Exception as exc:
        result = {"ok": False, "version": VERSION, "test_version": TEST_VERSION, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
