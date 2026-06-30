"""
PumpSwap instruction builder - Production-grade implementation.
100% port from Rust sol-trade-sdk (src/instruction/pumpswap.rs).
"""

from __future__ import annotations

import struct
import secrets
import base64
from typing import List, Optional, Tuple
from dataclasses import dataclass

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

# ===== Program IDs - 100% from Rust: src/instruction/utils/pumpswap.rs accounts =====

PUMPSWAP_PROGRAM = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
FEE_PROGRAM = Pubkey.from_string("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")
FEE_RECIPIENT = Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV")
PUMPSWAP_GLOBAL_ACCOUNT = Pubkey.from_string("ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")
PUMPSWAP_EVENT_AUTHORITY = Pubkey.from_string("GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR")
GLOBAL_VOLUME_ACCUMULATOR = Pubkey.from_string("C2aFPdENg4A2HQsmrd5rTw5TaYBX5Ku887cWjbFKtZpw")
FEE_CONFIG = Pubkey.from_string("5PHirr8joyTMp9JMm6nW7hNDVyEYdkzDqazxPD7RaTjx")
DEFAULT_COIN_CREATOR_VAULT_AUTHORITY = Pubkey.from_string("8N3GDaZ2iwN65oxVatKTLPNooAVUJTbfiVJ1ahyqwjSk")

# Standard Solana constants
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_PROGRAM_2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
WSOL_TOKEN_ACCOUNT = Pubkey.from_string("So11111111111111111111111111111111111111112")
USDC_TOKEN_ACCOUNT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

# Mayhem fee recipients - 100% from Rust: src/instruction/utils/pumpswap.rs accounts::MAYHEM_FEE_RECIPIENTS
MAYHEM_FEE_RECIPIENTS = [
    Pubkey.from_string("GesfTA3X2arioaHp8bbKdjG9vJtskViWACZoYvxp4twS"),
    Pubkey.from_string("4budycTjhs9fD6xw62VBducVTNgMgJJ5BgtKq7mAZwn6"),
    Pubkey.from_string("8SBKzEQU4nLSzcwF4a74F2iaUDQyTfjGndn6qUWBnrpR"),
    Pubkey.from_string("4UQeTP1T39KZ9Sfxzo3WR5skgsaP6NZa87BAkuazLEKH"),
    Pubkey.from_string("8sNeir4QsLsJdYpc9RZacohhK1Y5FLU3nC5LXgYB4aa6"),
    Pubkey.from_string("Fh9HmeLNUMVCvejxCtCL2DbYaRyBFVJ5xrWkLnMH6fdk"),
    Pubkey.from_string("463MEnMeGyJekNZFQSTUABBEbLnvMTALbT6ZmsxAbAdq"),
    Pubkey.from_string("6AUH3WEHucYZyC61hqpqYUWVto5qA5hjHuNQ32GNnNxA"),
]

PROTOCOL_EXTRA_FEE_RECIPIENTS = [
    Pubkey.from_string("5YxQFdt3Tr9zJLvkFccqXVUwhdTWJQc1fFg2YPbxvxeD"),
    Pubkey.from_string("9M4giFFMxmFGXtc3feFzRai56WbBqehoSeRE5GK7gf7"),
    Pubkey.from_string("GXPFM2caqTtQYC2cJ5yJRi9VDkpsYZXzYdwYpGnLmtDL"),
    Pubkey.from_string("3BpXnfJaUTiwXnJNe7Ej1rcbzqTTQUvLShZaWazebsVR"),
    Pubkey.from_string("5cjcW9wExnJJiqgLjq7DEG75Pm6JBgE1hNv4B2vHXUW6"),
    Pubkey.from_string("EHAAiTxcdDwQ3U4bU6YcMsQGaekdzLS3B5SmYo46kJtL"),
    Pubkey.from_string("5eHhjP8JaYkz83CWwvGU2uMUXefd3AazWGx4gpcuEEYD"),
    Pubkey.from_string("A7hAgCzFw14fejgCp387JUJRMNyz4j89JKnhtKU8piqW"),
]

# Discriminators - 100% from Rust
BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
BUY_EXACT_QUOTE_IN_DISCRIMINATOR = bytes([198, 46, 21, 82, 180, 217, 232, 112])
SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
CLAIM_CASHBACK_DISCRIMINATOR = bytes([37, 58, 35, 126, 190, 53, 228, 197])

# Seeds - 100% from Rust: src/instruction/utils/pumpswap.rs seeds
POOL_V2_SEED = b"pool-v2"
POOL_SEED = b"pool"
POOL_AUTHORITY_SEED = b"pool-authority"
USER_VOLUME_ACCUMULATOR_SEED = b"user_volume_accumulator"
CREATOR_VAULT_SEED = b"creator_vault"
FEE_CONFIG_SEED = b"fee_config"
GLOBAL_VOLUME_ACCUMULATOR_SEED = b"global_volume_accumulator"

# Fee basis points
LP_FEE_BASIS_POINTS = 25
PROTOCOL_FEE_BASIS_POINTS = 5
COIN_CREATOR_FEE_BASIS_POINTS = 5
SPL_MINT_SUPPLY_OFFSET = 36
SPL_MINT_SUPPLY_LEN = 8
FEE_TIER_LEN = 16 + 8 * 3


# ===== PDA Derivation Functions - 100% from Rust =====

def get_mayhem_fee_recipient_random() -> Pubkey:
    """Get cryptographically secure random Mayhem fee recipient."""
    return secrets.choice(MAYHEM_FEE_RECIPIENTS)


def get_protocol_fee_recipient_random() -> Pubkey:
    """Protocol fee recipient fallback. Rust may use cached GlobalConfig when warmed."""
    return FEE_RECIPIENT


def get_protocol_extra_fee_recipient_random() -> Pubkey:
    """Random protocol extra fee recipient (after pool-v2; paired with quote ATA)."""
    return secrets.choice(PROTOCOL_EXTRA_FEE_RECIPIENTS)


def get_pool_v2_pda(base_mint: Pubkey) -> Pubkey:
    """Get pool v2 PDA for a base mint (seeds: ["pool-v2", base_mint])"""
    pda, _ = Pubkey.find_program_address(
        [POOL_V2_SEED, bytes(base_mint)],
        PUMPSWAP_PROGRAM,
    )
    return pda


def get_pump_pool_authority_pda(mint: Pubkey) -> Pubkey:
    """Get pump pool authority PDA (seeds: ["pool-authority", mint])"""
    pda, _ = Pubkey.find_program_address(
        [POOL_AUTHORITY_SEED, bytes(mint)],
        PUMP_PROGRAM_ID,
    )
    return pda


def get_canonical_pool_pda(mint: Pubkey) -> Pubkey:
    """Get canonical pool PDA for a mint"""
    authority = get_pump_pool_authority_pda(mint)
    index = (0).to_bytes(2, 'little')
    pda, _ = Pubkey.find_program_address(
        [POOL_SEED, index, bytes(authority), bytes(mint), bytes(WSOL_TOKEN_ACCOUNT)],
        PUMPSWAP_PROGRAM,
    )
    return pda


def get_coin_creator_vault_authority(coin_creator: Pubkey) -> Pubkey:
    """Get coin creator vault authority PDA (seeds: ["creator_vault", coin_creator])"""
    pda, _ = Pubkey.find_program_address(
        [CREATOR_VAULT_SEED, bytes(coin_creator)],
        PUMPSWAP_PROGRAM,
    )
    return pda


def get_coin_creator_vault_ata(coin_creator: Pubkey, quote_mint: Pubkey) -> Pubkey:
    """Get coin creator vault ATA for the quote mint."""
    authority = get_coin_creator_vault_authority(coin_creator)
    return get_associated_token_address(authority, quote_mint, TOKEN_PROGRAM)


def get_user_volume_accumulator_pda(user: Pubkey) -> Pubkey:
    """Get user volume accumulator PDA (seeds: ["user_volume_accumulator", user])"""
    pda, _ = Pubkey.find_program_address(
        [USER_VOLUME_ACCUMULATOR_SEED, bytes(user)],
        PUMPSWAP_PROGRAM,
    )
    return pda


def get_associated_token_address(owner: Pubkey, mint: Pubkey, token_program: Pubkey = TOKEN_PROGRAM) -> Pubkey:
    """Get associated token address"""
    pda, _ = Pubkey.find_program_address(
        [bytes(owner), bytes(token_program), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )
    return pda


def get_user_volume_accumulator_wsol_ata(user: Pubkey) -> Pubkey:
    """Get WSOL ATA of UserVolumeAccumulator"""
    accumulator = get_user_volume_accumulator_pda(user)
    return get_associated_token_address(accumulator, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)


def get_user_volume_accumulator_quote_ata(user: Pubkey, quote_mint: Pubkey, quote_token_program: Pubkey) -> Pubkey:
    """Get quote-mint ATA of UserVolumeAccumulator"""
    accumulator = get_user_volume_accumulator_pda(user)
    return get_associated_token_address(accumulator, quote_mint, quote_token_program)


# ===== Params Dataclasses =====

@dataclass
class PumpSwapFeeBasisPoints:
    lp_fee_basis_points: int = LP_FEE_BASIS_POINTS
    protocol_fee_basis_points: int = PROTOCOL_FEE_BASIS_POINTS
    coin_creator_fee_basis_points: int = COIN_CREATOR_FEE_BASIS_POINTS


@dataclass
class PumpSwapFeeTier:
    market_cap_lamports_threshold: int
    fees: PumpSwapFeeBasisPoints


@dataclass
class PumpSwapFeeConfig:
    flat_fees: PumpSwapFeeBasisPoints
    fee_tiers: list[PumpSwapFeeTier]
    stable_fee_tiers: list[PumpSwapFeeTier]


def legacy_fee_basis_points(has_coin_creator: bool) -> PumpSwapFeeBasisPoints:
    return PumpSwapFeeBasisPoints(
        LP_FEE_BASIS_POINTS,
        PROTOCOL_FEE_BASIS_POINTS,
        COIN_CREATOR_FEE_BASIS_POINTS if has_coin_creator else 0,
    )


@dataclass
class PumpSwapParams:
    """Parameters for PumpSwap operations"""
    pool: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    pool_base_token_account: Pubkey
    pool_quote_token_account: Pubkey
    pool_base_token_reserves: int
    pool_quote_token_reserves: int
    coin_creator_vault_ata: Pubkey
    coin_creator_vault_authority: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    coin_creator: Pubkey | None = None
    cashback_fee_basis_points: int = 0
    fee_basis_points: PumpSwapFeeBasisPoints | None = None
    pool_creator: Pubkey | None = None
    base_mint_supply: int | None = None


@dataclass
class BuildBuyParams:
    """Parameters for building buy instructions"""
    payer: Pubkey
    input_amount: int
    slippage_basis_points: int
    protocol_params: PumpSwapParams
    create_input_mint_ata: bool = True
    close_input_mint_ata: bool = False
    create_output_mint_ata: bool = True
    use_exact_quote_amount: bool = True
    fixed_output_amount: Optional[int] = None


@dataclass
class BuildSellParams:
    """Parameters for building sell instructions"""
    payer: Pubkey
    input_amount: int
    slippage_basis_points: int
    protocol_params: PumpSwapParams
    create_output_mint_ata: bool = True
    close_output_mint_ata: bool = False
    close_input_mint_ata: bool = False
    fixed_output_amount: Optional[int] = None


# ===== WSOL Manager - 100% from Rust =====

def handle_wsol(owner: Pubkey, amount: int) -> List[Instruction]:
    """Create WSOL ATA and wrap SOL"""
    wsol_ata = get_associated_token_address(owner, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)
    instructions = []
    
    # Create ATA (idempotent)
    create_ata_ix = create_associated_token_account_idempotent(
        owner, owner, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
    )
    instructions.append(create_ata_ix)
    
    # Transfer SOL to WSOL ATA
    transfer_ix = Instruction(
        SYSTEM_PROGRAM,
        struct.pack("<Q", amount) + struct.pack("<Q", 12),  # Transfer instruction
        [
            AccountMeta(owner, True, True),
            AccountMeta(wsol_ata, False, True),
        ]
    )
    instructions.append(transfer_ix)
    
    # Sync native
    sync_ix = Instruction(
        TOKEN_PROGRAM,
        bytes([17]),  # sync_native discriminator
        [AccountMeta(wsol_ata, False, True)]
    )
    instructions.append(sync_ix)
    
    return instructions


def handle_wsol_for_mint(owner: Pubkey, mint: Pubkey, token_program: Pubkey, amount: int) -> List[Instruction]:
    if mint == WSOL_TOKEN_ACCOUNT:
        return handle_wsol(owner, amount)
    return [create_associated_token_account_idempotent(owner, owner, mint, token_program)]


def close_wsol(owner: Pubkey) -> Instruction:
    """Close WSOL ATA and reclaim rent"""
    wsol_ata = get_associated_token_address(owner, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)
    return Instruction(
        TOKEN_PROGRAM,
        bytes([9]) + bytes(8),  # close_account discriminator
        [
            AccountMeta(wsol_ata, False, True),
            AccountMeta(owner, False, True),
            AccountMeta(owner, True, False),
        ]
    )


def close_wsol_for_mint(owner: Pubkey, mint: Pubkey, token_program: Pubkey) -> Instruction | None:
    if mint != WSOL_TOKEN_ACCOUNT:
        return None
    ata = get_associated_token_address(owner, mint, token_program)
    return Instruction(
        token_program,
        bytes([9]) + bytes(8),
        [
            AccountMeta(ata, False, True),
            AccountMeta(owner, False, True),
            AccountMeta(owner, True, False),
        ],
    )


def create_associated_token_account_idempotent(
    payer: Pubkey, owner: Pubkey, mint: Pubkey, token_program: Pubkey
) -> Instruction:
    """Create ATA if not exists (idempotent)"""
    ata = get_associated_token_address(owner, mint, token_program)
    
    return Instruction(
        ASSOCIATED_TOKEN_PROGRAM,
        bytes([1]),  # Idempotent discriminator
        [
            AccountMeta(payer, True, True),
            AccountMeta(ata, False, True),
            AccountMeta(owner, False, False),
            AccountMeta(mint, False, False),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(token_program, False, False),
            AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
            AccountMeta(RENT, False, False),
        ]
    )


# ===== Instruction Builders - 100% from Rust =====

def _effective_fee_basis_points(pp: PumpSwapParams) -> PumpSwapFeeBasisPoints:
    has_coin_creator = (
        pp.coin_creator != Pubkey.default()
        if pp.coin_creator is not None
        else pp.coin_creator_vault_authority != DEFAULT_COIN_CREATOR_VAULT_AUTHORITY
    )
    base = pp.fee_basis_points or legacy_fee_basis_points(has_coin_creator)
    return PumpSwapFeeBasisPoints(
        base.lp_fee_basis_points,
        base.protocol_fee_basis_points,
        (base.coin_creator_fee_basis_points if has_coin_creator else 0)
        + pp.cashback_fee_basis_points,
    )


def _should_add_pool_v2(pp: PumpSwapParams) -> bool:
    return pp.coin_creator is None or pp.coin_creator != Pubkey.default()


def decode_mint_supply(data: bytes) -> int | None:
    """Decode SPL mint supply from a mint account."""
    end = SPL_MINT_SUPPLY_OFFSET + SPL_MINT_SUPPLY_LEN
    if len(data) < end:
        return None
    return int.from_bytes(data[SPL_MINT_SUPPLY_OFFSET:end], "little")


def _decode_fees(data: bytes, offset: int) -> PumpSwapFeeBasisPoints | None:
    if len(data) < offset + 24:
        return None
    return PumpSwapFeeBasisPoints(
        int.from_bytes(data[offset:offset + 8], "little"),
        int.from_bytes(data[offset + 8:offset + 16], "little"),
        int.from_bytes(data[offset + 16:offset + 24], "little"),
    )


def _decode_fee_tiers(data: bytes, offset: int) -> tuple[list[PumpSwapFeeTier], int] | None:
    if len(data) < offset + 4:
        return None
    length = int.from_bytes(data[offset:offset + 4], "little")
    offset += 4
    byte_len = length * FEE_TIER_LEN
    if len(data) < offset + byte_len:
        return None

    tiers: list[PumpSwapFeeTier] = []
    for _ in range(length):
        threshold = int.from_bytes(data[offset:offset + 16], "little")
        offset += 16
        fees = _decode_fees(data, offset)
        if fees is None:
            return None
        offset += 24
        tiers.append(PumpSwapFeeTier(threshold, fees))
    return tiers, offset


def decode_fee_config(data: bytes) -> PumpSwapFeeConfig | None:
    """Decode PumpSwap FeeConfig account data."""
    try:
        offset = 8  # discriminator
        offset += 1  # bump
        offset += 32  # admin
        flat_fees = _decode_fees(data, offset)
        if flat_fees is None:
            return None
        offset += 24

        decoded_fee_tiers = _decode_fee_tiers(data, offset)
        if decoded_fee_tiers is None:
            return None
        fee_tiers, offset = decoded_fee_tiers

        decoded_stable_fee_tiers = _decode_fee_tiers(data, offset)
        if decoded_stable_fee_tiers is None:
            return None
        stable_fee_tiers, _ = decoded_stable_fee_tiers

        return PumpSwapFeeConfig(flat_fees, fee_tiers, stable_fee_tiers)
    except Exception:
        return None


async def fetch_fee_config(fetcher: PoolFetcher) -> PumpSwapFeeConfig | None:
    data = await _fetch_account_data(fetcher, FEE_CONFIG)
    if data is None:
        return None
    return decode_fee_config(data)


def is_canonical_pump_pool(base_mint: Pubkey, pool_creator: Pubkey) -> bool:
    return get_pump_pool_authority_pda(base_mint) == pool_creator


def pool_market_cap_lamports(
    base_mint_supply: int,
    base_reserve: int,
    quote_reserve: int,
) -> int | None:
    if base_reserve == 0:
        return None
    return (quote_reserve * base_mint_supply) // base_reserve


def calculate_fee_tier(
    fee_tiers: list[PumpSwapFeeTier],
    market_cap_lamports: int,
) -> PumpSwapFeeBasisPoints | None:
    if not fee_tiers:
        return None
    first = fee_tiers[0]
    if market_cap_lamports < first.market_cap_lamports_threshold:
        return first.fees
    for tier in reversed(fee_tiers):
        if market_cap_lamports >= tier.market_cap_lamports_threshold:
            return tier.fees
    return first.fees


def compute_pumpswap_fee_basis_points(
    fee_config: PumpSwapFeeConfig | None,
    pool_creator: Pubkey,
    base_mint: Pubkey,
    base_mint_supply: int | None,
    base_reserve: int,
    quote_reserve: int,
) -> PumpSwapFeeBasisPoints:
    if fee_config is None:
        return legacy_fee_basis_points(True)

    if not is_canonical_pump_pool(base_mint, pool_creator):
        return fee_config.flat_fees

    if base_mint_supply is None:
        return legacy_fee_basis_points(True)

    market_cap = pool_market_cap_lamports(base_mint_supply, base_reserve, quote_reserve)
    if market_cap is None:
        return legacy_fee_basis_points(True)

    return calculate_fee_tier(fee_config.fee_tiers, market_cap) or fee_config.flat_fees


def _extract_account_data(value) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    data = getattr(value, "data", None)
    if data is not None:
        return _extract_account_data(data)
    inner = getattr(value, "value", None)
    if inner is not None:
        return _extract_account_data(inner)
    if isinstance(value, dict):
        if "data" in value:
            return _extract_account_data(value["data"])
        if "value" in value:
            return _extract_account_data(value["value"])
    if isinstance(value, (list, tuple)) and value:
        first = value[0]
        if isinstance(first, str):
            try:
                return base64.b64decode(first)
            except Exception:
                return first.encode()
        return _extract_account_data(first)
    return None


def _extract_token_amount(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    amount = getattr(value, "amount", None)
    if amount is not None:
        return int(amount)
    inner = getattr(value, "value", None)
    if inner is not None:
        return _extract_token_amount(inner)
    if isinstance(value, dict):
        if "amount" in value:
            return int(value["amount"])
        if "value" in value:
            return _extract_token_amount(value["value"])
    return None


async def _fetch_account_data(fetcher: PoolFetcher, pubkey: Pubkey) -> bytes | None:
    return _extract_account_data(await fetcher.get_account_info(pubkey))


async def _fetch_token_balance(fetcher: PoolFetcher, pubkey: Pubkey) -> int | None:
    return _extract_token_amount(await fetcher.get_token_account_balance(pubkey))


def build_buy_instructions(params: BuildBuyParams) -> List[Instruction]:
    """
    Build buy instructions for PumpSwap.
    100% port from Rust: src/instruction/pumpswap.rs build_buy_instructions
    """
    from ..calc.pumpswap import (
        PumpSwapFeeBasisPoints as CalcPumpSwapFeeBasisPoints,
        buy_quote_input_internal_with_fees,
        calculate_with_slippage_sell,
        sell_base_input_internal_with_fees,
    )
    
    if params.input_amount == 0:
        raise ValueError("Amount cannot be zero")
    
    pp = params.protocol_params
    
    # Check if pool contains WSOL or USDC
    is_wsol = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.base_mint == WSOL_TOKEN_ACCOUNT
    is_usdc = pp.quote_mint == USDC_TOKEN_ACCOUNT or pp.base_mint == USDC_TOKEN_ACCOUNT
    if not is_wsol and not is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")
    
    quote_is_wsol_or_usdc = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.quote_mint == USDC_TOKEN_ACCOUNT
    input_stable_mint = pp.quote_mint if quote_is_wsol_or_usdc else pp.base_mint
    input_stable_token_program = pp.quote_token_program if quote_is_wsol_or_usdc else pp.base_token_program
    output_trade_mint = pp.base_mint if quote_is_wsol_or_usdc else pp.quote_mint
    output_trade_token_program = pp.base_token_program if quote_is_wsol_or_usdc else pp.quote_token_program
    
    fee_basis_points = _effective_fee_basis_points(pp)
    
    # Calculate trade amounts
    if quote_is_wsol_or_usdc:
        result = buy_quote_input_internal_with_fees(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            CalcPumpSwapFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            ),
        )
        token_amount = result["base"]
        sol_amount = result["max_quote"]
    else:
        result = sell_base_input_internal_with_fees(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            CalcPumpSwapFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            ),
        )
        token_amount = result["min_quote"]
        sol_amount = params.input_amount
    
    # Override token amount if fixed output is specified
    if params.fixed_output_amount is not None:
        token_amount = params.fixed_output_amount
    
    # Get user token accounts
    user_base_token_account = get_associated_token_address(params.payer, pp.base_mint, pp.base_token_program)
    user_quote_token_account = get_associated_token_address(params.payer, pp.quote_mint, pp.quote_token_program)
    
    # Determine fee recipient
    if pp.is_mayhem_mode:
        fee_recipient = get_mayhem_fee_recipient_random()
    else:
        fee_recipient = get_protocol_fee_recipient_random()
    fee_recipient_ata = get_associated_token_address(fee_recipient, pp.quote_mint, TOKEN_PROGRAM)
    
    # Build instructions
    instructions: List[Instruction] = []
    
    # Handle WSOL wrapping if needed
    # CRITICAL FIX: Use input_amount when use_exact_quote_amount=true (buy_exact_quote_in mode)
    # to avoid "insufficient funds" when buying MAX
    if params.create_input_mint_ata:
        wrap_amount = params.input_amount
        if not params.use_exact_quote_amount:
            wrap_amount = sol_amount
        instructions.extend(handle_wsol_for_mint(params.payer, input_stable_mint, input_stable_token_program, wrap_amount))
    
    # Create output token ATA if needed
    if params.create_output_mint_ata:
        instructions.append(create_associated_token_account_idempotent(
            params.payer, params.payer, output_trade_mint, output_trade_token_program
        ))
    
    # Build accounts array
    accounts = [
        AccountMeta(pp.pool, False, True),
        AccountMeta(params.payer, True, True),
        AccountMeta(PUMPSWAP_GLOBAL_ACCOUNT, False, False),
        AccountMeta(pp.base_mint, False, False),
        AccountMeta(pp.quote_mint, False, False),
        AccountMeta(user_base_token_account, False, True),
        AccountMeta(user_quote_token_account, False, True),
        AccountMeta(pp.pool_base_token_account, False, True),
        AccountMeta(pp.pool_quote_token_account, False, True),
        AccountMeta(fee_recipient, False, False),
        AccountMeta(fee_recipient_ata, False, True),
        AccountMeta(pp.base_token_program, False, False),
        AccountMeta(pp.quote_token_program, False, False),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
        AccountMeta(PUMPSWAP_EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPSWAP_PROGRAM, False, False),
        AccountMeta(pp.coin_creator_vault_ata, False, True),
        AccountMeta(pp.coin_creator_vault_authority, False, False),
    ]
    
    # Add volume accumulator accounts for quote buy
    if quote_is_wsol_or_usdc:
        accounts.append(AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True))
        user_volume_accumulator = get_user_volume_accumulator_pda(params.payer)
        accounts.append(AccountMeta(user_volume_accumulator, False, True))
    
    # Add fee config and program
    accounts.extend([
        AccountMeta(FEE_CONFIG, False, False),
        AccountMeta(FEE_PROGRAM, False, False),
    ])
    
    # Add cashback WSOL ATA if needed
    if pp.is_cashback_coin:
        wsol_ata = get_user_volume_accumulator_wsol_ata(params.payer)
        accounts.append(AccountMeta(wsol_ata, False, True))
    
    if _should_add_pool_v2(pp):
        pool_v2 = get_pool_v2_pda(pp.base_mint)
        accounts.append(AccountMeta(pool_v2, False, False))
    protocol_extra = get_protocol_extra_fee_recipient_random()
    accounts.append(AccountMeta(protocol_extra, False, False))
    accounts.append(
        AccountMeta(get_associated_token_address(protocol_extra, pp.quote_mint, TOKEN_PROGRAM), False, True)
    )

    # Build instruction data
    track_volume = 1 if pp.is_cashback_coin else 0
    if params.fixed_output_amount is not None:
        data = BUY_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", sol_amount) + bytes([track_volume])
    elif quote_is_wsol_or_usdc and params.use_exact_quote_amount:
        # buy_exact_quote_in(spendable_quote_in, min_base_amount_out, track_volume)
        min_base_amount_out = calculate_with_slippage_sell(token_amount, params.slippage_basis_points)
        data = BUY_EXACT_QUOTE_IN_DISCRIMINATOR + struct.pack("<Q", params.input_amount) + struct.pack("<Q", min_base_amount_out) + bytes([track_volume])
    elif quote_is_wsol_or_usdc:
        # buy(token_amount, max_quote, track_volume)
        data = BUY_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", sol_amount) + bytes([track_volume])
    else:
        data = SELL_DISCRIMINATOR + struct.pack("<Q", sol_amount) + struct.pack("<Q", token_amount)
    
    instructions.append(Instruction(PUMPSWAP_PROGRAM, data, accounts))
    
    # Close WSOL ATA if requested
    if params.close_input_mint_ata:
        instructions.append(close_wsol(params.payer))
    
    return instructions


def build_sell_instructions(params: BuildSellParams) -> List[Instruction]:
    """
    Build sell instructions for PumpSwap.
    100% port from Rust: src/instruction/pumpswap.rs build_sell_instructions
    """
    from ..calc.pumpswap import (
        PumpSwapFeeBasisPoints as CalcPumpSwapFeeBasisPoints,
        buy_quote_input_internal_with_fees,
        sell_base_input_internal_with_fees,
    )
    
    if params.input_amount == 0:
        raise ValueError("Amount cannot be zero")
    
    pp = params.protocol_params
    
    # Check if pool contains WSOL or USDC
    is_wsol = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.base_mint == WSOL_TOKEN_ACCOUNT
    is_usdc = pp.quote_mint == USDC_TOKEN_ACCOUNT or pp.base_mint == USDC_TOKEN_ACCOUNT
    if not is_wsol and not is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")
    
    quote_is_wsol_or_usdc = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.quote_mint == USDC_TOKEN_ACCOUNT
    output_stable_mint = pp.quote_mint if quote_is_wsol_or_usdc else pp.base_mint
    output_stable_token_program = pp.quote_token_program if quote_is_wsol_or_usdc else pp.base_token_program
    
    fee_basis_points = _effective_fee_basis_points(pp)
    
    # Calculate trade amounts
    token_amount = params.input_amount
    sol_amount = 0
    
    if quote_is_wsol_or_usdc:
        result = sell_base_input_internal_with_fees(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            CalcPumpSwapFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            ),
        )
        sol_amount = result["min_quote"]
    else:
        result = buy_quote_input_internal_with_fees(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            CalcPumpSwapFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            ),
        )
        token_amount = result["max_quote"]
        sol_amount = result["base"]
    
    # Override sol amount if fixed output is specified
    if params.fixed_output_amount is not None:
        sol_amount = params.fixed_output_amount
    
    # Get user token accounts
    user_base_token_account = get_associated_token_address(params.payer, pp.base_mint, pp.base_token_program)
    user_quote_token_account = get_associated_token_address(params.payer, pp.quote_mint, pp.quote_token_program)
    
    # Determine fee recipient
    if pp.is_mayhem_mode:
        fee_recipient = get_mayhem_fee_recipient_random()
    else:
        fee_recipient = get_protocol_fee_recipient_random()
    fee_recipient_ata = get_associated_token_address(fee_recipient, pp.quote_mint, TOKEN_PROGRAM)
    
    # Build instructions
    instructions: List[Instruction] = []
    
    # Create WSOL/USDC ATA if needed for receiving
    if params.create_output_mint_ata:
        instructions.append(create_associated_token_account_idempotent(
            params.payer, params.payer, output_stable_mint, output_stable_token_program
        ))
    
    # Build accounts array
    accounts = [
        AccountMeta(pp.pool, False, True),
        AccountMeta(params.payer, True, True),
        AccountMeta(PUMPSWAP_GLOBAL_ACCOUNT, False, False),
        AccountMeta(pp.base_mint, False, False),
        AccountMeta(pp.quote_mint, False, False),
        AccountMeta(user_base_token_account, False, True),
        AccountMeta(user_quote_token_account, False, True),
        AccountMeta(pp.pool_base_token_account, False, True),
        AccountMeta(pp.pool_quote_token_account, False, True),
        AccountMeta(fee_recipient, False, False),
        AccountMeta(fee_recipient_ata, False, True),
        AccountMeta(pp.base_token_program, False, False),
        AccountMeta(pp.quote_token_program, False, False),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
        AccountMeta(PUMPSWAP_EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPSWAP_PROGRAM, False, False),
        AccountMeta(pp.coin_creator_vault_ata, False, True),
        AccountMeta(pp.coin_creator_vault_authority, False, False),
    ]
    
    # Add volume accumulator accounts for non-quote sell
    if not quote_is_wsol_or_usdc:
        accounts.append(AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True))
        user_volume_accumulator = get_user_volume_accumulator_pda(params.payer)
        accounts.append(AccountMeta(user_volume_accumulator, False, True))
    
    # Add fee config and program
    accounts.extend([
        AccountMeta(FEE_CONFIG, False, False),
        AccountMeta(FEE_PROGRAM, False, False),
    ])
    
    # Add cashback accounts if needed
    if pp.is_cashback_coin:
        quote_ata = get_user_volume_accumulator_quote_ata(params.payer, pp.quote_mint, pp.quote_token_program)
        user_volume_accumulator = get_user_volume_accumulator_pda(params.payer)
        accounts.extend([
            AccountMeta(quote_ata, False, True),
            AccountMeta(user_volume_accumulator, False, True),
        ])
    
    if _should_add_pool_v2(pp):
        pool_v2 = get_pool_v2_pda(pp.base_mint)
        accounts.append(AccountMeta(pool_v2, False, False))
    protocol_extra = get_protocol_extra_fee_recipient_random()
    accounts.append(AccountMeta(protocol_extra, False, False))
    accounts.append(
        AccountMeta(get_associated_token_address(protocol_extra, pp.quote_mint, TOKEN_PROGRAM), False, True)
    )

    # Build instruction data
    if quote_is_wsol_or_usdc:
        data = SELL_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", sol_amount)
    else:
        data = BUY_DISCRIMINATOR + struct.pack("<Q", sol_amount) + struct.pack("<Q", token_amount)
    
    instructions.append(Instruction(PUMPSWAP_PROGRAM, data, accounts))
    
    # Close WSOL ATA if requested
    if params.close_output_mint_ata:
        close_ix = close_wsol_for_mint(params.payer, output_stable_mint, output_stable_token_program)
        if close_ix is not None:
            instructions.append(close_ix)
    
    # Close base token account if requested
    if params.close_input_mint_ata:
        input_token_account = user_base_token_account if quote_is_wsol_or_usdc else user_quote_token_account
        close_ix = Instruction(
            pp.base_token_program if quote_is_wsol_or_usdc else pp.quote_token_program,
            bytes([9]) + bytes(8),  # close_account discriminator
            [
                AccountMeta(input_token_account, False, True),
                AccountMeta(params.payer, False, True),
                AccountMeta(params.payer, True, False),
            ]
        )
        instructions.append(close_ix)
    
    return instructions


def build_claim_cashback_instruction(
    payer: Pubkey, quote_mint: Pubkey, quote_token_program: Pubkey
) -> Instruction:
    """Build claim cashback instruction for PumpSwap"""
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)
    user_volume_accumulator_wsol_ata = get_user_volume_accumulator_wsol_ata(payer)
    user_wsol_ata = get_associated_token_address(payer, quote_mint, quote_token_program)
    
    accounts = [
        AccountMeta(payer, True, True),
        AccountMeta(user_volume_accumulator, False, True),
        AccountMeta(quote_mint, False, False),
        AccountMeta(quote_token_program, False, False),
        AccountMeta(user_volume_accumulator_wsol_ata, False, True),
        AccountMeta(user_wsol_ata, False, True),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(PUMPSWAP_EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPSWAP_PROGRAM, False, False),
    ]
    
    return Instruction(PUMPSWAP_PROGRAM, CLAIM_CASHBACK_DISCRIMINATOR, accounts)


# ===== Pool Types and Decoding - from Rust: src/instruction/utils/pumpswap_types.rs =====

from dataclasses import dataclass

# Pool size in bytes (244 bytes as per pump-public-docs)
POOL_SIZE = 244


@dataclass
class PumpSwapPool:
    """PumpSwap Pool structure - matches Rust: src/instruction/utils/pumpswap_types.rs"""
    pool_bump: int
    index: int
    creator: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    lp_mint: Pubkey
    pool_base_token_account: Pubkey
    pool_quote_token_account: Pubkey
    lp_supply: int
    coin_creator: Pubkey
    is_mayhem_mode: bool
    is_cashback_coin: bool


def decode_pool(data: bytes) -> PumpSwapPool | None:
    """
    Decode a PumpSwap pool from account data.
    Uses simple byte-level deserialization matching Borsh layout.
    
    Args:
        data: Raw account data (should be at least 244 bytes)
    
    Returns:
        PumpSwapPool if successful, None if data is invalid
    """
    if len(data) < POOL_SIZE:
        return None
    
    try:
        import struct
        
        offset = 0
        
        # pool_bump: u8
        pool_bump = data[offset]
        offset += 1
        
        # index: u16
        index = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # creator: Pubkey (32 bytes)
        creator = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # base_mint: Pubkey
        base_mint = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # quote_mint: Pubkey
        quote_mint = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # lp_mint: Pubkey
        lp_mint = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # pool_base_token_account: Pubkey
        pool_base_token_account = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # pool_quote_token_account: Pubkey
        pool_quote_token_account = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # lp_supply: u64
        lp_supply = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # coin_creator: Pubkey
        coin_creator = Pubkey.from_bytes(data[offset:offset+32])
        offset += 32
        
        # is_mayhem_mode: bool
        is_mayhem_mode = data[offset] == 1
        offset += 1
        
        # is_cashback_coin: bool
        is_cashback_coin = data[offset] == 1
        
        return PumpSwapPool(
            pool_bump=pool_bump,
            index=index,
            creator=creator,
            base_mint=base_mint,
            quote_mint=quote_mint,
            lp_mint=lp_mint,
            pool_base_token_account=pool_base_token_account,
            pool_quote_token_account=pool_quote_token_account,
            lp_supply=lp_supply,
            coin_creator=coin_creator,
            is_mayhem_mode=is_mayhem_mode,
            is_cashback_coin=is_cashback_coin,
        )
    except Exception:
        return None


def find_pool_by_mint(mint: Pubkey) -> Pubkey:
    """
    Find a PumpSwap pool by mint (simplified version).
    
    Search order matches @pump-fun/pump-swap-sdk:
    1. Pool v2 PDA ["pool-v2", base_mint]
    
    For full implementation with RPC lookups, use a client that can fetch accounts.
    
    Args:
        mint: The token mint to find a pool for
    
    Returns:
        The pool v2 PDA for the mint
    """
    return get_pool_v2_pda(mint)


def get_fee_config_pda() -> Pubkey:
    """
    Get the fee config PDA.
    Seeds: ["fee_config", PUMPSWAP_PROGRAM], owner: FEE_PROGRAM
    100% from Rust: src/instruction/utils/pumpswap.rs get_fee_config_pda
    """
    pda, _ = Pubkey.find_program_address(
        [FEE_CONFIG_SEED, bytes(PUMPSWAP_PROGRAM)],
        FEE_PROGRAM,
    )
    return pda


def get_global_volume_accumulator_pda() -> Pubkey:
    """
    Get the global volume accumulator PDA.
    Seeds: ["global_volume_accumulator"], owner: PUMPSWAP_PROGRAM
    100% from Rust: src/instruction/utils/pumpswap.rs get_global_volume_accumulator_pda
    """
    pda, _ = Pubkey.find_program_address(
        [GLOBAL_VOLUME_ACCUMULATOR_SEED],
        PUMPSWAP_PROGRAM,
    )
    return pda


# ===== Async Fetch Functions - from Rust: src/instruction/utils/pumpswap.rs =====
# These functions require an async RPC client and are provided as utilities

from typing import Protocol, runtime_checkable


@runtime_checkable
class PoolFetcher(Protocol):
    """Protocol for fetching pool data from RPC"""
    async def get_account_info(self, pubkey: Pubkey) -> bytes | None:
        ...
    
    async def get_token_account_balance(self, pubkey: Pubkey) -> int | None:
        ...


async def fetch_pool(fetcher: PoolFetcher, pool_address: Pubkey) -> PumpSwapPool | None:
    """
    Fetch a PumpSwap pool from RPC.
    100% from Rust: src/instruction/utils/pumpswap.rs fetch_pool

    Args:
        fetcher: Object implementing PoolFetcher protocol
        pool_address: The pool account address

    Returns:
        PumpSwapPool if successful, None if not found or invalid
    """
    data = await _fetch_account_data(fetcher, pool_address)
    if data is None or len(data) < 8:
        return None
    return decode_pool(data[8:])


async def get_token_balances(
    fetcher: PoolFetcher,
    pool: PumpSwapPool
) -> tuple[int, int] | None:
    """
    Get token balances for a pool's token accounts.
    100% from Rust: src/instruction/utils/pumpswap.rs get_token_balances

    Args:
        fetcher: Object implementing PoolFetcher protocol
        pool: The PumpSwap pool

    Returns:
        Tuple of (base_balance, quote_balance) if successful, None if error
    """
    try:
        base_balance = await _fetch_token_balance(fetcher, pool.pool_base_token_account)
        quote_balance = await _fetch_token_balance(fetcher, pool.pool_quote_token_account)
        
        if base_balance is None or quote_balance is None:
            return None
        
        return (base_balance, quote_balance)
    except Exception:
        return None


async def params_from_pool_data(
    fetcher: PoolFetcher,
    pool_address: Pubkey,
    pool: PumpSwapPool,
    fee_basis_points: PumpSwapFeeBasisPoints | None = None,
    cashback_fee_basis_points: int = 0,
) -> PumpSwapParams:
    """
    Build PumpSwap params from a decoded pool using explicit cold-path RPC reads.

    `fee_basis_points` is optional. When provided, it is trusted and no FeeConfig
    discovery is needed for fee math. When omitted, this helper fetches FeeConfig
    and mint supply before trading; instruction builders remain params-only.
    """
    balances = await get_token_balances(fetcher, pool)
    if balances is None:
        raise ValueError("Failed to read pool token balances")
    base_balance, quote_balance = balances

    base_token_program_ata = get_associated_token_address(
        pool_address,
        pool.base_mint,
        TOKEN_PROGRAM,
    )
    quote_token_program_ata = get_associated_token_address(
        pool_address,
        pool.quote_mint,
        TOKEN_PROGRAM,
    )
    base_token_program = (
        TOKEN_PROGRAM
        if pool.pool_base_token_account == base_token_program_ata
        else TOKEN_PROGRAM_2022
    )
    quote_token_program = (
        TOKEN_PROGRAM
        if pool.pool_quote_token_account == quote_token_program_ata
        else TOKEN_PROGRAM_2022
    )

    base_mint_supply = None
    mint_data = await _fetch_account_data(fetcher, pool.base_mint)
    if mint_data is not None:
        base_mint_supply = decode_mint_supply(mint_data)

    effective_fees = fee_basis_points
    if effective_fees is None:
        fee_config = await fetch_fee_config(fetcher)
        effective_fees = compute_pumpswap_fee_basis_points(
            fee_config,
            pool.creator,
            pool.base_mint,
            base_mint_supply,
            base_balance,
            quote_balance,
        )

    creator_fee_basis_points = (
        0
        if pool.coin_creator == Pubkey.default()
        else effective_fees.coin_creator_fee_basis_points
    )
    effective_fees = PumpSwapFeeBasisPoints(
        effective_fees.lp_fee_basis_points,
        effective_fees.protocol_fee_basis_points,
        creator_fee_basis_points,
    )

    return PumpSwapParams(
        pool=pool_address,
        base_mint=pool.base_mint,
        quote_mint=pool.quote_mint,
        pool_base_token_account=pool.pool_base_token_account,
        pool_quote_token_account=pool.pool_quote_token_account,
        pool_base_token_reserves=base_balance,
        pool_quote_token_reserves=quote_balance,
        coin_creator_vault_ata=get_coin_creator_vault_ata(pool.coin_creator, pool.quote_mint),
        coin_creator_vault_authority=get_coin_creator_vault_authority(pool.coin_creator),
        base_token_program=base_token_program,
        quote_token_program=quote_token_program,
        is_mayhem_mode=pool.is_mayhem_mode,
        is_cashback_coin=pool.is_cashback_coin,
        coin_creator=pool.coin_creator,
        cashback_fee_basis_points=cashback_fee_basis_points,
        fee_basis_points=effective_fees,
        pool_creator=pool.creator,
        base_mint_supply=base_mint_supply,
    )


async def params_from_pool_address(
    fetcher: PoolFetcher,
    pool_address: Pubkey,
    fee_basis_points: PumpSwapFeeBasisPoints | None = None,
    cashback_fee_basis_points: int = 0,
) -> PumpSwapParams:
    pool = await fetch_pool(fetcher, pool_address)
    if pool is None:
        raise ValueError("PumpSwap pool account not found or invalid")
    return await params_from_pool_data(
        fetcher,
        pool_address,
        pool,
        fee_basis_points=fee_basis_points,
        cashback_fee_basis_points=cashback_fee_basis_points,
    )


async def find_by_mint(
    fetcher: PoolFetcher,
    mint: Pubkey
) -> tuple[Pubkey, PumpSwapPool] | None:
    """
    Find a PumpSwap pool by mint with full RPC lookup.
    100% from Rust: src/instruction/utils/pumpswap.rs find_by_mint

    Search order:
    1. Pool v2 PDA ["pool-v2", base_mint]
    2. Canonical pool PDA

    Args:
        fetcher: Object implementing PoolFetcher protocol
        mint: The token mint to find a pool for

    Returns:
        Tuple of (pool_address, pool) if found, None if not found
    """
    # 1. Try v2 PDA
    pool_v2 = get_pool_v2_pda(mint)
    data = await _fetch_account_data(fetcher, pool_v2)
    if data is not None and len(data) >= 8:
        pool = decode_pool(data[8:])
        if pool is not None and pool.base_mint == mint:
            return (pool_v2, pool)

    # 2. Try canonical pool PDA
    canonical = get_canonical_pool_pda(mint)
    data = await _fetch_account_data(fetcher, canonical)
    if data is not None and len(data) >= 8:
        pool = decode_pool(data[8:])
        if pool is not None and pool.base_mint == mint:
            return (canonical, pool)

    return None


async def params_from_mint(
    fetcher: PoolFetcher,
    mint: Pubkey,
    fee_basis_points: PumpSwapFeeBasisPoints | None = None,
    cashback_fee_basis_points: int = 0,
) -> PumpSwapParams:
    found = await find_by_mint(fetcher, mint)
    if found is None:
        raise ValueError("No pool found for mint")
    pool_address, pool = found
    return await params_from_pool_data(
        fetcher,
        pool_address,
        pool,
        fee_basis_points=fee_basis_points,
        cashback_fee_basis_points=cashback_fee_basis_points,
    )


# ===== Pool Size Constants - from Rust: src/instruction/utils/pumpswap.rs =====

# Pool data size for SPL Token (8 discriminator + 244 data)
POOL_DATA_LEN_SPL = 8 + 244
# Pool data size for Token2022
POOL_DATA_LEN_T22 = 643


@runtime_checkable
class ProgramAccountsFetcher(Protocol):
    """Protocol for fetching program accounts from RPC"""
    async def get_program_accounts(
        self,
        program_id: Pubkey,
        filters: list[dict] | None = None
    ) -> list[tuple[Pubkey, bytes]]:
        ...


async def find_by_base_mint(
    fetcher: ProgramAccountsFetcher,
    base_mint: Pubkey
) -> tuple[Pubkey, PumpSwapPool] | None:
    """
    Find a PumpSwap pool by base mint using getProgramAccounts.
    100% from Rust: src/instruction/utils/pumpswap.rs find_by_base_mint
    
    base_mint offset: 8(discriminator) + 1(bump) + 2(index) + 32(creator) = 43

    Args:
        fetcher: Object implementing ProgramAccountsFetcher protocol
        base_mint: The base mint to search for

    Returns:
        Tuple of (pool_address, pool) if found, None if not found
    """
    # base_mint offset: 8(discriminator) + 1(bump) + 2(index) + 32(creator) = 43
    memcmp_offset = 43

    filters = [
        {"memcmp": {"offset": memcmp_offset, "bytes": str(base_mint)}}
    ]

    try:
        results = await fetcher.get_program_accounts(PUMPSWAP_PROGRAM, filters)

        if not results:
            return None

        # Decode and sort by lp_supply (highest first)
        pools: list[tuple[Pubkey, PumpSwapPool]] = []
        for pubkey, data in results:
            if len(data) > 8:
                pool = decode_pool(data[8:])
                if pool is not None:
                    pools.append((pubkey, pool))

        if not pools:
            return None

        # Sort by lp_supply descending
        pools.sort(key=lambda x: x[1].lp_supply, reverse=True)

        return pools[0]
    except Exception:
        return None


async def find_by_quote_mint(
    fetcher: ProgramAccountsFetcher,
    quote_mint: Pubkey
) -> tuple[Pubkey, PumpSwapPool] | None:
    """
    Find a PumpSwap pool by quote mint using getProgramAccounts.
    100% from Rust: src/instruction/utils/pumpswap.rs find_by_quote_mint
    
    quote_mint offset: 8 + 1 + 2 + 32 + 32 = 75

    Args:
        fetcher: Object implementing ProgramAccountsFetcher protocol
        quote_mint: The quote mint to search for

    Returns:
        Tuple of (pool_address, pool) if found, None if not found
    """
    # quote_mint offset: 8 + 1 + 2 + 32 + 32 = 75
    memcmp_offset = 75

    filters = [
        {"memcmp": {"offset": memcmp_offset, "bytes": str(quote_mint)}}
    ]

    try:
        results = await fetcher.get_program_accounts(PUMPSWAP_PROGRAM, filters)

        if not results:
            return None

        # Decode and sort by lp_supply (highest first)
        pools: list[tuple[Pubkey, PumpSwapPool]] = []
        for pubkey, data in results:
            if len(data) > 8:
                pool = decode_pool(data[8:])
                if pool is not None:
                    pools.append((pubkey, pool))

        if not pools:
            return None

        # Sort by lp_supply descending
        pools.sort(key=lambda x: x[1].lp_supply, reverse=True)

        return pools[0]
    except Exception:
        return None
