# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""CIP-8 verification backends for Telegram stake ownership.

Production backend: cardano-signer v1.35.0.
Fallback/self-test backend: the bundled Python verifier from v1.2.
"""
from __future__ import annotations
import json, os, re, subprocess
from dataclasses import dataclass
from pathlib import Path

class CIP8VerificationError(ValueError):
    pass

@dataclass(frozen=True)
class VerificationResult:
    stake_address: str
    public_key_hex: str = ""
    key_hash_hex: str = ""
    backend: str = "cardano-signer"
    backend_version: str = ""

_VERSION_RE = re.compile(r"(?:cardano-signer\s+)?v?(\d+\.\d+\.\d+)", re.I)

def _clean_hex(value: str, label: str) -> str:
    value=(value or "").strip()
    if not value or len(value)%2:
        raise CIP8VerificationError(f"{label} hexadécimal invalide")
    try: bytes.fromhex(value)
    except ValueError as exc: raise CIP8VerificationError(f"{label} hexadécimal invalide") from exc
    return value

def cardano_signer_version(binary: str) -> str:
    p=Path(binary)
    if not p.is_file() or not os.access(p, os.X_OK):
        raise CIP8VerificationError(f"cardano-signer introuvable/non exécutable: {binary}")
    for args in ([binary,"--version"],[binary,"version"],[binary,"help"]):
        try:
            cp=subprocess.run(args,capture_output=True,text=True,timeout=10,check=False)
        except OSError as exc: raise CIP8VerificationError(f"impossible d'exécuter cardano-signer: {exc}") from exc
        text=(cp.stdout or "")+"\n"+(cp.stderr or "")
        m=_VERSION_RE.search(text)
        if m:return m.group(1)
    raise CIP8VerificationError("version de cardano-signer indéterminable")

def verify_cip8_cardano_signer(*,stake_address:str,expected_payload:str,cose_sign1_hex:str,cose_key_hex:str,binary:str="/usr/local/bin/cardano-signer",required_version:str="1.35.0") -> VerificationResult:
    sign1=_clean_hex(cose_sign1_hex,"COSE_Sign1"); key=_clean_hex(cose_key_hex,"COSE_Key")
    if not stake_address.startswith("stake1"):
        raise CIP8VerificationError("stake address mainnet attendue")
    version=cardano_signer_version(binary)
    if required_version and version != required_version:
        raise CIP8VerificationError(f"cardano-signer {version} détecté; version requise {required_version}")
    # No shell: all Telegram/user-controlled values are passed as argv elements.
    cmd=[binary,"verify","--cip8","--cose-sign1",sign1,"--cose-key",key,
         "--data",expected_payload,"--address",stake_address,"--json-extended"]
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=20,check=False)
    except subprocess.TimeoutExpired as exc: raise CIP8VerificationError("timeout cardano-signer") from exc
    except OSError as exc: raise CIP8VerificationError(f"échec cardano-signer: {exc}") from exc
    stdout=(cp.stdout or "").strip(); stderr=(cp.stderr or "").strip()
    parsed={}
    if stdout:
        try: parsed=json.loads(stdout)
        except json.JSONDecodeError: parsed={}
    ok=cp.returncode==0 and str(parsed.get("result","")).lower()=="true"
    if not ok:
        detail=stderr or stdout or f"exit={cp.returncode}"
        if len(detail)>500: detail=detail[:500]+"…"
        raise CIP8VerificationError(f"cardano-signer a refusé la preuve: {detail}")
    return VerificationResult(stake_address=stake_address,public_key_hex=str(parsed.get("publicKey") or ""),backend="cardano-signer",backend_version=version)

def verify_cip8(*,stake_address:str,expected_payload:str,cose_sign1_hex:str,cose_key_hex:str,backend:str="cardano-signer",cardano_signer_path:str="/usr/local/bin/cardano-signer",required_version:str="1.35.0") -> VerificationResult:
    mode=(backend or "cardano-signer").strip().lower()
    if mode in {"cardano-signer","cardano_signer","signer"}:
        return verify_cip8_cardano_signer(stake_address=stake_address,expected_payload=expected_payload,cose_sign1_hex=cose_sign1_hex,cose_key_hex=cose_key_hex,binary=cardano_signer_path,required_version=required_version)
    if mode=="python":
        from .cip8_python_fallback import verify_cip8_python
        try:
            r=verify_cip8_python(stake_address=stake_address,expected_payload=expected_payload,cose_sign1_hex=cose_sign1_hex,cose_key_hex=cose_key_hex)
        except Exception as exc:
            raise CIP8VerificationError(str(exc)) from exc
        return VerificationResult(stake_address=r.stake_address,public_key_hex=r.public_key_hex,key_hash_hex=r.key_hash_hex,backend="python")
    raise CIP8VerificationError(f"backend CIP-8 inconnu: {backend}")
