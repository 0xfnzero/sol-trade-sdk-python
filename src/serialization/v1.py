"""Native Python V1 wire compilation, independent of Rust SDKs and RPC."""

from dataclasses import dataclass
import struct
import base58
from typing import Optional


@dataclass(frozen=True)
class V1Config:
    priority_fee: Optional[int] = None
    compute_unit_limit: Optional[int] = None
    loaded_accounts_data_size_limit: Optional[int] = None
    heap_size: Optional[int] = None


@dataclass(frozen=True)
class CompiledV1Message:
    message: bytes
    account_keys: tuple
    required_signatures: int


def compile_v1_message(payer, instructions, recent_blockhash, config=V1Config()):
    instructions = list(instructions)
    if len(instructions) > 64:
        raise ValueError("V1 supports at most 64 instructions")
    accounts = {}

    def add(key, signer, writable):
        raw = bytes(key)
        if len(raw) != 32:
            raise ValueError("Invalid V1 public key")
        prior = accounts.get(raw, (False, False))
        accounts[raw] = (signer or prior[0], writable or prior[1])

    for ix in instructions:
        add(ix.program_id, False, False)
        for a in ix.accounts:
            add(a.pubkey, a.is_signer, a.is_writable)
    add(payer, True, True)
    payer = bytes(payer)
    del accounts[payer]
    ordered = sorted(accounts)
    sw = [payer] + [k for k in ordered if accounts[k] == (True, True)]
    sr = [k for k in ordered if accounts[k] == (True, False)]
    uw = [k for k in ordered if accounts[k] == (False, True)]
    ur = [k for k in ordered if accounts[k] == (False, False)]
    keys = sw + sr + uw + ur
    required = len(sw) + len(sr)
    if len(keys) > 64 or required > 12:
        raise ValueError("V1 account/signature limit exceeded")
    indices = {k: i for i, k in enumerate(keys)}
    blockhash = (
        base58.b58decode(recent_blockhash)
        if isinstance(recent_blockhash, str)
        else bytes(recent_blockhash)
    )
    if len(blockhash) != 32:
        raise ValueError("Invalid blockhash")
    mask, values = 0, b""
    for value, bit, fmt in (
        (config.priority_fee, 3, "Q"),
        (config.compute_unit_limit, 4, "I"),
        (config.loaded_accounts_data_size_limit, 8, "I"),
        (config.heap_size, 16, "I"),
    ):
        if value is not None:
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value < (1 << (64 if fmt == "Q" else 32))
            ):
                raise ValueError("V1 config integer outside range")
            if bit == 16 and (value < 32768 or value > 262144 or value % 1024):
                raise ValueError("Invalid V1 heap size")
            mask |= bit
            values += struct.pack("<" + fmt, value)
    headers, payloads = b"", b""
    for ix in instructions:
        program = indices[bytes(ix.program_id)]
        if program == 0:
            raise ValueError("V1 fee payer cannot be a program")
        if len(ix.accounts) > 255 or len(ix.data) > 65535:
            raise ValueError("V1 instruction payload limit")
        headers += struct.pack("<BBH", program, len(ix.accounts), len(ix.data))
        payloads += bytes(indices[bytes(a.pubkey)] for a in ix.accounts) + bytes(ix.data)
    message = (
        bytes([129, required, len(sr), len(ur)])
        + struct.pack("<I", mask)
        + blockhash
        + bytes([len(instructions), len(keys)])
        + b"".join(keys)
        + values
        + headers
        + payloads
    )
    if len(message) + required * 64 > 4096:
        raise ValueError("V1 transaction exceeds 4096 bytes")
    return CompiledV1Message(message, tuple(keys), required)


def sign_v1_transaction(compiled, signers):
    """Sign via Ed25519 cryptography; signer objects expose pubkey()/sign_message()."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    m, count, keys = compiled.message, compiled.required_signatures, compiled.account_keys
    if (type(count) is not int or not 1 <= count <= min(12,len(keys)) or len(keys)>64 or
        len(m)<42+32*len(keys) or len(m)+64*count>4096 or m[0]!=129 or m[1]!=count or m[41]!=len(keys) or
        m[2]>=count or m[3]>len(keys)-count or any(m[42+32*i:74+32*i]!=bytes(k) for i,k in enumerate(keys))):
        raise ValueError("Invalid compiled V1 signer metadata")

    provided = {bytes(s.pubkey()): s for s in signers}
    signatures = []
    for key in compiled.account_keys[: compiled.required_signatures]:
        if key not in provided:
            raise ValueError("Missing V1 signer: " + base58.b58encode(key).decode())
        signature = bytes(provided[key].sign_message(compiled.message))
        Ed25519PublicKey.from_public_bytes(key).verify(signature, compiled.message)
        signatures.append(signature)
    return compiled.message + b"".join(signatures)
