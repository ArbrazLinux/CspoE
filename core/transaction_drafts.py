# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""Offline-only Cardano command plans used by the CspoE desktop interface.

This module never starts cardano-cli, never reads key contents and never signs
or submits a transaction.  It validates operator input and stores auditable
JSON drafts with restrictive permissions.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


class DraftValidationError(ValueError):
    """Raised when an operator field cannot safely form a command plan."""


PAYMENT_ADDRESS_RE = re.compile(r"^addr(?:_test)?1[0-9a-z]{20,120}$")
TX_IN_RE = re.compile(r"^[0-9a-fA-F]{64}#[0-9]+$")
HASH_64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_KIND_RE = re.compile(r"^[a-z][a-z0-9_-]{1,48}$")


def _text(value: Any, label: str, *, maximum: int = 1024) -> str:
    result = str(value or "").strip()
    if not result:
        raise DraftValidationError(f"{label} est obligatoire")
    if len(result) > maximum or "\x00" in result or "\n" in result or "\r" in result:
        raise DraftValidationError(f"{label} contient une valeur invalide")
    return result


def _non_negative_integer(value: Any, label: str, *, maximum: int | None = None) -> int:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise DraftValidationError(f"{label} doit être un entier") from exc
    if result < 0 or (maximum is not None and result > maximum):
        raise DraftValidationError(f"{label} est hors limites")
    return result


def _network_arguments(network: str, testnet_magic: Any = None) -> list[str]:
    normalized = str(network or "").strip().lower()
    if normalized == "mainnet":
        return ["--mainnet"]
    if normalized == "testnet":
        return ["--testnet-magic", str(_non_negative_integer(testnet_magic, "magic testnet"))]
    raise DraftValidationError("le réseau doit être mainnet ou testnet")


def _preview(arguments: Iterable[str]) -> str:
    return shlex.join([str(argument) for argument in arguments])


def ada_to_lovelace(value: Any) -> int:
    raw = _text(value, "montant ADA", maximum=80).replace(" ", "").replace(",", ".")
    try:
        ada = Decimal(raw)
    except InvalidOperation as exc:
        raise DraftValidationError(f"montant ADA invalide : {value}") from exc
    if not ada.is_finite() or ada <= 0:
        raise DraftValidationError("le montant ADA doit être strictement positif")
    lovelace = ada * Decimal(1_000_000)
    if lovelace != lovelace.to_integral_value():
        raise DraftValidationError("un montant ADA ne peut pas dépasser six décimales")
    result = int(lovelace)
    if result > 45_000_000_000_000_000:
        raise DraftValidationError("montant ADA supérieur à l'offre maximale")
    return result


def parse_bonus_recipients(value: str) -> list[dict[str, Any]]:
    """Parse ``payment_address ; amount_ada`` lines without inferring addresses."""
    recipients: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(str(value).splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ";" in line:
            address, amount = (part.strip() for part in line.split(";", 1))
        else:
            parts = line.split()
            if len(parts) != 2:
                raise DraftValidationError(
                    f"ligne {line_number} : utiliser adresse_paiement ; montant_ADA"
                )
            address, amount = parts
        if not PAYMENT_ADDRESS_RE.fullmatch(address):
            raise DraftValidationError(
                f"ligne {line_number} : adresse de paiement addr1/addr_test1 invalide"
            )
        if address in seen:
            raise DraftValidationError(f"ligne {line_number} : adresse dupliquée")
        seen.add(address)
        lovelace = ada_to_lovelace(amount)
        recipients.append(
            {
                "payment_address": address,
                "amount_lovelace": lovelace,
                "amount_ada": f"{Decimal(lovelace) / Decimal(1_000_000):f}",
            }
        )
    if not recipients:
        raise DraftValidationError("ajouter au moins un destinataire de bonus")
    if len(recipients) > 500:
        raise DraftValidationError("un brouillon est limité à 500 destinataires")
    return recipients


def _command(role: str, arguments: list[str], *, offline_only: bool = False) -> dict[str, Any]:
    return {
        "role": role,
        "offline_only": offline_only,
        "argv": arguments,
        "preview": _preview(arguments),
    }


def _base_draft(kind: str) -> dict[str, Any]:
    return {
        "schema": "cspoe-transaction-draft-v1",
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_policy": "preview_and_save_only",
        "executed": False,
        "signed": False,
        "submitted": False,
    }


def bonus_distribution_draft(
    *,
    recipients_text: str,
    tx_in: str,
    change_address: str,
    network: str,
    testnet_magic: Any,
    out_file: str,
) -> dict[str, Any]:
    recipients = parse_bonus_recipients(recipients_text)
    normalized_tx_in = _text(tx_in, "UTxO d'entrée", maximum=100)
    if not TX_IN_RE.fullmatch(normalized_tx_in):
        raise DraftValidationError("l'UTxO doit respecter tx_hash#index")
    normalized_change = _text(change_address, "adresse de change", maximum=128)
    if not PAYMENT_ADDRESS_RE.fullmatch(normalized_change):
        raise DraftValidationError("adresse de change addr1/addr_test1 invalide")
    normalized_out = _text(out_file, "fichier de transaction non signée", maximum=512)

    arguments = ["cardano-cli", "latest", "transaction", "build", "--tx-in", normalized_tx_in]
    for recipient in recipients:
        arguments.extend(
            [
                "--tx-out",
                f"{recipient['payment_address']}+{recipient['amount_lovelace']}",
            ]
        )
    arguments.extend(["--change-address", normalized_change])
    arguments.extend(_network_arguments(network, testnet_magic))
    arguments.extend(["--out-file", normalized_out])

    draft = _base_draft("bonus_distribution")
    draft.update(
        {
            "network": str(network).lower(),
            "testnet_magic": (
                _non_negative_integer(testnet_magic, "magic testnet")
                if str(network).lower() == "testnet"
                else None
            ),
            "tx_in": normalized_tx_in,
            "change_address": normalized_change,
            "out_file": normalized_out,
            "recipients": recipients,
            "total_lovelace": sum(row["amount_lovelace"] for row in recipients),
            "commands": [_command("build_unsigned_transaction", arguments)],
            "warnings": [
                "Vérifier chaque adresse de paiement et chaque montant.",
                "Le brouillon ne sélectionne pas automatiquement les UTxO.",
                "Signer sur le dispositif prévu par l'opérateur puis soumettre séparément.",
            ],
        }
    )
    return draft


def operational_certificate_draft(
    *,
    kes_verification_key_file: str,
    cold_signing_key_file: str,
    counter_file: str,
    kes_period: Any,
    out_file: str,
) -> dict[str, Any]:
    kes_vkey = _text(kes_verification_key_file, "fichier KES vkey", maximum=512)
    cold_skey = _text(cold_signing_key_file, "fichier cold skey", maximum=512)
    counter = _text(counter_file, "fichier compteur", maximum=512)
    period = _non_negative_integer(kes_period, "période KES")
    output = _text(out_file, "fichier opcert", maximum=512)
    arguments = [
        "cardano-cli",
        "node",
        "issue-op-cert",
        "--kes-verification-key-file",
        kes_vkey,
        "--cold-signing-key-file",
        cold_skey,
        "--operational-certificate-issue-counter-file",
        counter,
        "--kes-period",
        str(period),
        "--out-file",
        output,
    ]
    draft = _base_draft("operational_certificate")
    draft.update(
        {
            "kes_verification_key_file": kes_vkey,
            "cold_signing_key_file": cold_skey,
            "counter_file": counter,
            "kes_period": period,
            "out_file": output,
            "commands": [_command("issue_operational_certificate", arguments, offline_only=True)],
            "warnings": [
                "Commande à exécuter exclusivement sur la machine hors ligne.",
                "Ne jamais copier cold.skey sur le serveur CspoE connecté.",
                "Contrôler la période KES et le compteur avant de remplacer l'opcert du nœud.",
            ],
        }
    )
    return draft


def drep_vote_draft(
    *,
    governance_action_tx_id: str,
    governance_action_index: Any,
    decision: str,
    drep_verification_key_file: str,
    vote_file: str,
    tx_in: str,
    change_address: str,
    network: str,
    testnet_magic: Any,
    transaction_out_file: str,
) -> dict[str, Any]:
    action_id = _text(governance_action_tx_id, "tx-id de l'action", maximum=64).lower()
    if not HASH_64_RE.fullmatch(action_id):
        raise DraftValidationError("le tx-id de l'action doit contenir 64 caractères hexadécimaux")
    action_index = _non_negative_integer(
        governance_action_index, "index de l'action", maximum=65535
    )
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"yes", "no", "abstain"}:
        raise DraftValidationError("le vote doit être yes, no ou abstain")
    drep_vkey = _text(drep_verification_key_file, "fichier DRep vkey", maximum=512)
    normalized_vote_file = _text(vote_file, "fichier de vote", maximum=512)
    normalized_tx_in = _text(tx_in, "UTxO d'entrée", maximum=100)
    if not TX_IN_RE.fullmatch(normalized_tx_in):
        raise DraftValidationError("l'UTxO doit respecter tx_hash#index")
    normalized_change = _text(change_address, "adresse de change", maximum=128)
    if not PAYMENT_ADDRESS_RE.fullmatch(normalized_change):
        raise DraftValidationError("adresse de change addr1/addr_test1 invalide")
    normalized_tx_out = _text(
        transaction_out_file, "transaction de vote non signée", maximum=512
    )

    vote_arguments = [
        "cardano-cli",
        "latest",
        "governance",
        "vote",
        "create",
        f"--{normalized_decision}",
        "--governance-action-tx-id",
        action_id,
        "--governance-action-index",
        str(action_index),
        "--drep-verification-key-file",
        drep_vkey,
        "--out-file",
        normalized_vote_file,
    ]
    transaction_arguments = [
        "cardano-cli",
        "latest",
        "transaction",
        "build",
        "--tx-in",
        normalized_tx_in,
        "--change-address",
        normalized_change,
        "--vote-file",
        normalized_vote_file,
        "--witness-override",
        "2",
        *_network_arguments(network, testnet_magic),
        "--out-file",
        normalized_tx_out,
    ]

    draft = _base_draft("drep_vote")
    draft.update(
        {
            "network": str(network).lower(),
            "testnet_magic": (
                _non_negative_integer(testnet_magic, "magic testnet")
                if str(network).lower() == "testnet"
                else None
            ),
            "governance_action": {"tx_id": action_id, "index": action_index},
            "decision": normalized_decision,
            "drep_verification_key_file": drep_vkey,
            "vote_file": normalized_vote_file,
            "tx_in": normalized_tx_in,
            "change_address": normalized_change,
            "transaction_out_file": normalized_tx_out,
            "commands": [
                _command("create_vote_file", vote_arguments),
                _command("build_unsigned_vote_transaction", transaction_arguments),
            ],
            "warnings": [
                "Vérifier l'identifiant, l'index et le contenu de l'action avant le vote.",
                "Le fichier produit par ce plan n'est pas signé et n'est pas soumis.",
                "La clé de signature DRep doit rester dans le processus de signature prévu.",
            ],
        }
    )
    return draft


@dataclass(frozen=True)
class DraftStore:
    directory: Path

    def __init__(self, directory: str | Path) -> None:
        object.__setattr__(self, "directory", Path(directory))

    def save(self, draft: dict[str, Any]) -> Path:
        kind = str(draft.get("kind") or "")
        if not SAFE_KIND_RE.fullmatch(kind):
            raise DraftValidationError("type de brouillon invalide")
        if draft.get("execution_policy") != "preview_and_save_only":
            raise DraftValidationError("politique d'exécution du brouillon invalide")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.directory / f"{timestamp}_{kind}.json"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=self.directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(draft, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination
