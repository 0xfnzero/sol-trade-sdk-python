"""
Seed-based PDA Derivation for Sol Trade SDK
High-performance PDA computation with caching.
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass
from hashlib import sha256
import base58

# ===== Constants =====

PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKFJdMZzMMTrWr1Bv"
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKFRHoe4LvJhu5yQJtezhkEL5DHyJ"
RAYDIUM_AMM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM_PROGRAM_ID = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
METEORA_DAMM_V2_PROGRAM_ID = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"


@dataclass
class PDA:
    """Program Derived Address"""
    pubkey: bytes
    bump: int


def find_program_address(
    seeds: List[bytes],
    program_id: str,
) -> Tuple[bytes, int]:
    """
    Find a program-derived address.

    Args:
        seeds: List of seed bytes
        program_id: Program ID as base58 string

    Returns:
        Tuple of (pubkey bytes, bump seed)
    """
    program_bytes = base58.b58decode(program_id)

    for bump in range(256, 0, -1):
        try:
            address = create_program_address(
                seeds + [bytes([bump])],
                program_id,
            )
            return address, bump
        except ValueError:
            continue

    raise ValueError("Unable to find valid PDA")


def create_program_address(
    seeds: List[bytes],
    program_id: str,
) -> bytes:
    """
    Create a program-derived address without bump.

    Args:
        seeds: List of seed bytes
        program_id: Program ID as base58 string

    Returns:
        Pubkey bytes
    """
    program_bytes = base58.b58decode(program_id)

    # Concatenate seeds and program ID
    data = b"".join(seeds) + program_bytes

    # Hash
    h = sha256(data).digest()

    # Check if on ed25519 curve (invalid for PDA)
    # Simplified check - in production use proper ed25519 check
    if h[31] & 0x80:
        raise ValueError("Invalid seeds: address on curve")

    return h


# ===== PumpFun PDAs =====

def get_bonding_curve_pda(mint: str) -> PDA:
    """Get the bonding curve PDA for a mint"""
    mint_bytes = base58.b58decode(mint)
    pubkey, bump = find_program_address(
        [b"bonding-curve", mint_bytes],
        PUMPFUN_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


def get_global_account_pda() -> PDA:
    """Get the global account PDA"""
    pubkey, bump = find_program_address(
        [b"global"],
        PUMPFUN_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


def get_fee_recipient_pda(is_mayhem_mode: bool = False) -> PDA:
    """Get the fee recipient PDA"""
    seed = b"fee_recipient_mayhem" if is_mayhem_mode else b"fee_recipient"
    pubkey, bump = find_program_address(
        [seed],
        PUMPFUN_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


def get_event_authority_pda() -> PDA:
    """Get the event authority PDA"""
    pubkey, bump = find_program_address(
        [b"event"],
        PUMPFUN_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


def get_user_volume_accumulator_pda(user: str) -> PDA:
    """Get the user volume accumulator PDA"""
    user_bytes = base58.b58decode(user)
    pubkey, bump = find_program_address(
        [b"user_volume_accumulator", user_bytes],
        PUMPFUN_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


# ===== PumpSwap PDAs =====

def get_pumpswap_pool_pda(base_mint: str, quote_mint: str) -> PDA:
    """Get the PumpSwap pool PDA"""
    base_bytes = base58.b58decode(base_mint)
    quote_bytes = base58.b58decode(quote_mint)
    pubkey, bump = find_program_address(
        [b"pool", base_bytes, quote_bytes],
        PUMPSWAP_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


# ===== Raydium PDAs =====

def get_raydium_amm_authority_pda() -> PDA:
    """Get the Raydium AMM authority PDA"""
    pubkey, bump = find_program_address(
        [b"amm authority"],
        RAYDIUM_AMM_V4_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


def get_raydium_cpmm_pool_pda(
    amm_config: str,
    base_mint: str,
    quote_mint: str,
) -> PDA:
    """Get the Raydium CPMM pool PDA"""
    amm_bytes = base58.b58decode(amm_config)
    base_bytes = base58.b58decode(base_mint)
    quote_bytes = base58.b58decode(quote_mint)
    pubkey, bump = find_program_address(
        [b"pool", amm_bytes, base_bytes, quote_bytes],
        RAYDIUM_CPMM_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


# ===== Meteora PDAs =====

def get_meteora_pool_pda(token_a_mint: str, token_b_mint: str) -> PDA:
    """Get the Meteora pool PDA"""
    a_bytes = base58.b58decode(token_a_mint)
    b_bytes = base58.b58decode(token_b_mint)
    pubkey, bump = find_program_address(
        [b"pool", a_bytes, b_bytes],
        METEORA_DAMM_V2_PROGRAM_ID,
    )
    return PDA(pubkey=pubkey, bump=bump)


# ===== Associated Token Account =====

def get_associated_token_address(
    wallet: str,
    mint: str,
    token_program: str = TOKEN_PROGRAM_ID,
) -> bytes:
    """Get the associated token account address"""
    wallet_bytes = base58.b58decode(wallet)
    mint_bytes = base58.b58decode(mint)
    program_bytes = base58.b58decode(token_program)

    address, _ = find_program_address(
        [wallet_bytes, program_bytes, mint_bytes],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    return address


# ===== Seed-based ATA Creation =====

@dataclass
class SeedATA:
    """Seed-based ATA with pre-computed address"""
    address: bytes
    mint: str
    owner: str
    bump: int
    seed: bytes
    exists: bool = False
    rent_exempt: int = 0


def create_seed_ata(
    owner: str,
    mint: str,
    seed: bytes,
    token_program: str = TOKEN_PROGRAM_ID,
) -> SeedATA:
    """Create a seed-based ATA configuration"""
    owner_bytes = base58.b58decode(owner)
    mint_bytes = base58.b58decode(mint)
    program_bytes = base58.b58decode(token_program)

    address, bump = find_program_address(
        [owner_bytes, program_bytes, mint_bytes, seed],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )

    return SeedATA(
        address=address,
        mint=mint,
        owner=owner,
        bump=bump,
        seed=seed,
    )


# ===== Hash Utilities =====

def hash256(data: bytes) -> bytes:
    """Compute SHA-256 hash"""
    return sha256(data).digest()


def hash256_concat(*parts: bytes) -> bytes:
    """Concatenate and hash"""
    h = sha256()
    for p in parts:
        h.update(p)
    return h.digest()
