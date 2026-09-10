# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

"""CIP-8 / COSE_Sign1 verification for Telegram stake ownership challenges.

No private key, seed phrase or transaction is ever requested. The verifier checks:
- exact challenge payload
- Ed25519 COSE_Sign1 signature
- COSE public key hash against the key credential of a stake1 reward address
- optional address header, when supplied by the wallet
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Any

class _CBOR:
    @staticmethod
    def _head(major:int,n:int)->bytes:
        if n < 24:return bytes([(major<<5)|n])
        if n < 256:return bytes([(major<<5)|24,n])
        if n < 65536:return bytes([(major<<5)|25])+n.to_bytes(2,"big")
        if n < 2**32:return bytes([(major<<5)|26])+n.to_bytes(4,"big")
        return bytes([(major<<5)|27])+n.to_bytes(8,"big")
    @classmethod
    def dumps(cls,obj:Any)->bytes:
        if obj is None:return b"\xf6"
        if obj is False:return b"\xf4"
        if obj is True:return b"\xf5"
        if isinstance(obj,int):
            return cls._head(0,obj) if obj>=0 else cls._head(1,-1-obj)
        if isinstance(obj,bytes):return cls._head(2,len(obj))+obj
        if isinstance(obj,str):
            b=obj.encode("utf-8");return cls._head(3,len(b))+b
        if isinstance(obj,(list,tuple)):
            return cls._head(4,len(obj))+b"".join(cls.dumps(x) for x in obj)
        if isinstance(obj,dict):
            return cls._head(5,len(obj))+b"".join(cls.dumps(k)+cls.dumps(v) for k,v in obj.items())
        raise TypeError(f"CBOR type unsupported: {type(obj).__name__}")
    @classmethod
    def loads(cls,data:bytes)->Any:
        def read_len(ai:int,pos:int)->tuple[int,int]:
            if ai<24:return ai,pos
            sizes={24:1,25:2,26:4,27:8}
            if ai not in sizes:raise CIP8VerificationError("CBOR indéfini/non supporté")
            size=sizes[ai]
            if pos+size>len(data):raise CIP8VerificationError("CBOR tronqué")
            return int.from_bytes(data[pos:pos+size],"big"),pos+size
        def parse(pos:int)->tuple[Any,int]:
            if pos>=len(data):raise CIP8VerificationError("CBOR tronqué")
            first=data[pos];pos+=1;major=first>>5;ai=first&31
            if major in (0,1):
                n,pos=read_len(ai,pos);return (n if major==0 else -1-n),pos
            if major in (2,3):
                n,pos=read_len(ai,pos)
                if pos+n>len(data):raise CIP8VerificationError("CBOR tronqué")
                raw=data[pos:pos+n];pos+=n
                return (raw if major==2 else raw.decode("utf-8")),pos
            if major==4:
                n,pos=read_len(ai,pos);out=[]
                for _ in range(n):v,pos=parse(pos);out.append(v)
                return out,pos
            if major==5:
                n,pos=read_len(ai,pos);out={}
                for _ in range(n):k,pos=parse(pos);v,pos=parse(pos);out[k]=v
                return out,pos
            if major==7 and ai==20:return False,pos
            if major==7 and ai==21:return True,pos
            if major==7 and ai==22:return None,pos
            raise CIP8VerificationError("type CBOR non supporté")
        value,pos=parse(0)
        if pos!=len(data):raise CIP8VerificationError("données CBOR supplémentaires")
        return value

cbor2=_CBOR

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("dépendance cryptography absente; installer requirements-interactive.txt") from exc


class CIP8VerificationError(ValueError):
    pass


_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_REV = {c: i for i, c in enumerate(_BECH32_CHARSET)}


def _polymod(values: list[int]) -> int:
    chk = 1
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= gen[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> bytes:
    acc = 0
    bits = 0
    out = bytearray()
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise CIP8VerificationError("bech32 invalide")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if pad:
        if bits:
            out.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise CIP8VerificationError("padding bech32 invalide")
    return bytes(out)


def decode_stake_address(address: str) -> bytes:
    if not isinstance(address, str) or not address.startswith("stake1"):
        raise CIP8VerificationError("stake address attendue")
    if address.lower() != address and address.upper() != address:
        raise CIP8VerificationError("bech32 mixte invalide")
    a = address.lower()
    pos = a.rfind("1")
    if pos < 1 or pos + 7 > len(a):
        raise CIP8VerificationError("stake address bech32 invalide")
    hrp, tail = a[:pos], a[pos + 1 :]
    try:
        values = [_BECH32_REV[c] for c in tail]
    except KeyError as exc:
        raise CIP8VerificationError("caractère bech32 invalide") from exc
    if _polymod(_hrp_expand(hrp) + values) != 1:
        raise CIP8VerificationError("checksum stake address invalide")
    raw = _convertbits(values[:-6], 5, 8, False)
    if len(raw) != 29:
        raise CIP8VerificationError("longueur stake address inattendue")
    # Shelley reward address: 1110 = key hash, 1111 = script hash.
    if (raw[0] >> 4) != 0b1110:
        raise CIP8VerificationError("seules les stake addresses à credential clé sont supportées")
    return raw


def _hex_bytes(value: str, label: str) -> bytes:
    try:
        b = bytes.fromhex(value.strip())
    except Exception as exc:
        raise CIP8VerificationError(f"{label} n'est pas un hexadécimal valide") from exc
    if not b:
        raise CIP8VerificationError(f"{label} vide")
    return b


def _map_from_protected(protected: bytes) -> dict[Any, Any]:
    if not protected:
        return {}
    try:
        m = cbor2.loads(protected)
    except Exception as exc:
        raise CIP8VerificationError("header COSE protégé invalide") from exc
    if not isinstance(m, dict):
        raise CIP8VerificationError("header COSE protégé non-map")
    return m


def _header_address(protected_map: dict[Any, Any], unprotected: dict[Any, Any]) -> bytes | None:
    # CIP-8 implementations use the text key 'address'; tolerate it in either header.
    for m in (protected_map, unprotected):
        if not isinstance(m, dict):
            continue
        for key in ("address",):
            value = m.get(key)
            if isinstance(value, bytes):
                return value
    return None


@dataclass(frozen=True)
class VerificationResult:
    stake_address: str
    public_key_hex: str
    key_hash_hex: str


def verify_cip8_python(*, stake_address: str, expected_payload: str, cose_sign1_hex: str, cose_key_hex: str) -> VerificationResult:
    stake_raw = decode_stake_address(stake_address)
    credential = stake_raw[1:]
    sign1_raw = _hex_bytes(cose_sign1_hex, "COSE_Sign1")
    key_raw = _hex_bytes(cose_key_hex, "COSE_Key")
    try:
        sign1 = cbor2.loads(sign1_raw)
        key = cbor2.loads(key_raw)
    except Exception as exc:
        raise CIP8VerificationError("CBOR CIP-8 invalide") from exc
    if not (isinstance(sign1, list) and len(sign1) == 4):
        raise CIP8VerificationError("COSE_Sign1 invalide")
    protected, unprotected, payload, signature = sign1
    if not isinstance(protected, bytes) or not isinstance(unprotected, dict) or not isinstance(signature, bytes):
        raise CIP8VerificationError("structure COSE_Sign1 invalide")
    expected = expected_payload.encode("utf-8")
    if payload is None:
        payload_for_sig = expected
    elif isinstance(payload, bytes):
        payload_for_sig = payload
    else:
        raise CIP8VerificationError("payload COSE invalide")
    if payload_for_sig != expected:
        raise CIP8VerificationError("le payload signé ne correspond pas au challenge")
    if not isinstance(key, dict):
        raise CIP8VerificationError("COSE_Key invalide")
    pub = key.get(-2)
    if not isinstance(pub, bytes) or len(pub) != 32:
        raise CIP8VerificationError("clé publique Ed25519 absente ou invalide")
    alg = key.get(3)
    if alg not in (None, -8):
        raise CIP8VerificationError("algorithme COSE_Key non EdDSA")
    pmap = _map_from_protected(protected)
    palg = pmap.get(1)
    if palg not in (None, -8):
        raise CIP8VerificationError("algorithme COSE_Sign1 non EdDSA")
    header_addr = _header_address(pmap, unprotected)
    if header_addr is not None and header_addr != stake_raw:
        raise CIP8VerificationError("l'adresse du header CIP-8 ne correspond pas à la stake address")
    key_hash = blake2b(pub, digest_size=28).digest()
    if key_hash != credential:
        raise CIP8VerificationError("la clé de signature ne correspond pas au credential de la stake address")
    sig_structure = ["Signature1", protected, b"", payload_for_sig]
    to_verify = cbor2.dumps(sig_structure)
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, to_verify)
    except InvalidSignature as exc:
        raise CIP8VerificationError("signature CIP-8 invalide") from exc
    return VerificationResult(stake_address=stake_address, public_key_hex=pub.hex(), key_hash_hex=key_hash.hex())
