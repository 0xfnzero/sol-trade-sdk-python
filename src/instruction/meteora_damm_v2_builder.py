"""
Meteora DAMM V2 instruction builder for Solana trading SDK.
Production-grade implementation with all constants, discriminators, and PDA derivation functions.
"""

from typing import List, Optional
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import struct

from .common import (
    TOKEN_PROGRAM,
    SOL_TOKEN_ACCOUNT,
    WSOL_TOKEN_ACCOUNT,
    USDC_TOKEN_ACCOUNT,
    DEFAULT_SLIPPAGE,
    get_associated_token_address,
    create_associated_token_account_idempotent_instruction,
    handle_wsol,
    close_wsol,
    close_token_account_instruction,
)

# ============================================
# Meteora DAMM V2 Program ID
# ============================================

METEORA_DAMM_V2_PROGRAM_ID: Pubkey = Pubkey.from_string("cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG")

# ============================================
# Meteora DAMM V2 Constants
# ============================================

# Pool Authority
AUTHORITY: Pubkey = Pubkey.from_string("HLnpSz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC")

# ============================================
# Instruction Discriminators
# ============================================

SWAP_DISCRIMINATOR: bytes = bytes([248, 198, 158, 145, 225, 117, 135, 200])
SWAP2_DISCRIMINATOR: bytes = bytes([65, 75, 63, 76, 235, 91, 91, 136])
SWAP_MODE_EXACT_IN: int = 0
SWAP_MODE_PARTIAL_FILL: int = 1
SWAP_MODE_EXACT_OUT: int = 2
SYSVAR_INSTRUCTIONS: Pubkey = Pubkey.from_string("Sysvar1nstructions1111111111111111111111111")

# ============================================
# Seeds
# ============================================

EVENT_AUTHORITY_SEED = b"__event_authority"


# ============================================
# PDA Derivation Functions
# ============================================

def get_event_authority_pda() -> Pubkey:
    """
    Derive the event authority PDA.
    Seeds: ["__event_authority"]
    """
    seeds = [EVENT_AUTHORITY_SEED]
    (pda, _) = Pubkey.find_program_address(seeds, METEORA_DAMM_V2_PROGRAM_ID)
    return pda


# ============================================
# Meteora DAMM V2 Parameters Dataclass
# ============================================

@dataclass
class MeteoraDammV2Params:
    """Parameters for Meteora DAMM V2 protocol trading."""
    pool: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    token_a_vault: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    token_b_vault: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    token_a_mint: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    token_b_mint: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    token_a_program: Pubkey = TOKEN_PROGRAM
    token_b_program: Pubkey = TOKEN_PROGRAM
    referral_token_account: Optional[Pubkey] = None
    swap_mode: int = SWAP_MODE_PARTIAL_FILL
    include_rate_limiter_sysvar: bool = False

    @property
    def is_wsol(self) -> bool:
        """Check if the pool contains WSOL."""
        return self.token_a_mint == WSOL_TOKEN_ACCOUNT or self.token_b_mint == WSOL_TOKEN_ACCOUNT

    @property
    def is_usdc(self) -> bool:
        """Check if the pool contains USDC."""
        return self.token_a_mint == USDC_TOKEN_ACCOUNT or self.token_b_mint == USDC_TOKEN_ACCOUNT


def _resolve_swap_mode(params: MeteoraDammV2Params) -> int:
    mode = params.swap_mode
    if mode not in (SWAP_MODE_EXACT_IN, SWAP_MODE_PARTIAL_FILL, SWAP_MODE_EXACT_OUT):
        raise ValueError(f"Unsupported MeteoraDammV2 swap_mode {mode}")
    return mode


def _resolve_amounts(swap_mode: int, amount_in: int, fixed_output: int) -> tuple[int, int]:
    if swap_mode == SWAP_MODE_EXACT_OUT:
        return fixed_output, amount_in
    return amount_in, fixed_output


def _build_account_metas(
    params: MeteoraDammV2Params,
    payer: Pubkey,
    input_token_account: Pubkey,
    output_token_account: Pubkey,
    event_authority: Pubkey,
) -> List[AccountMeta]:
    accounts = [
        AccountMeta(AUTHORITY, False, False),
        AccountMeta(params.pool, False, True),
        AccountMeta(input_token_account, False, True),
        AccountMeta(output_token_account, False, True),
        AccountMeta(params.token_a_vault, False, True),
        AccountMeta(params.token_b_vault, False, True),
        AccountMeta(params.token_a_mint, False, False),
        AccountMeta(params.token_b_mint, False, False),
        AccountMeta(payer, True, False),
        AccountMeta(params.token_a_program, False, False),
        AccountMeta(params.token_b_program, False, False),
    ]
    accounts.append(AccountMeta(params.referral_token_account, False, True) if params.referral_token_account is not None else AccountMeta(METEORA_DAMM_V2_PROGRAM_ID, False, False))
    accounts.extend(
        [
            AccountMeta(event_authority, False, False),
            AccountMeta(METEORA_DAMM_V2_PROGRAM_ID, False, False),
        ]
    )
    if params.include_rate_limiter_sysvar:
        accounts.append(AccountMeta(SYSVAR_INSTRUCTIONS, False, False))
    return accounts


DEFAULT_PUBKEY: Pubkey = Pubkey.from_string("11111111111111111111111111111111")


def _mint_matches(requested: Pubkey, expected: Pubkey) -> bool:
    return requested == expected or (
        expected == WSOL_TOKEN_ACCOUNT and requested == SOL_TOKEN_ACCOUNT
    )


def _ensure_expected_mint(label: str, requested: Pubkey, expected: Pubkey) -> None:
    if requested != DEFAULT_PUBKEY and not _mint_matches(requested, expected):
        raise ValueError(
            f"{label} must match the Meteora DAMM v2 pool side ({expected}), got {requested}"
        )


# ============================================
# Build Buy Instructions
# ============================================

def build_buy_instructions(
    payer: Pubkey,
    output_mint: Pubkey,
    input_amount: int,
    params: MeteoraDammV2Params,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_input_ata: bool = True,
    create_output_ata: bool = True,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    input_mint: Optional[Pubkey] = None,
) -> List[Instruction]:
    """
    Build Meteora DAMM V2 buy instructions.

    Args:
        payer: The wallet paying for the swap
        output_mint: The token mint to buy
        input_amount: Amount of SOL/USDC to spend
        params: Meteora DAMM V2 protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_input_ata: Whether to create WSOL ATA if needed
        create_output_ata: Whether to create output token ATA if needed
        close_input_ata: Whether to close WSOL ATA after swap
        fixed_output_amount: MUST be set for Meteora DAMM V2 swaps

    Returns:
        List of instructions for the buy operation
    """
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Determine if token A is input (WSOL/USDC)
    is_a_in = params.token_a_mint == WSOL_TOKEN_ACCOUNT or params.token_a_mint == USDC_TOKEN_ACCOUNT

    # Meteora DAMM V2 requires fixed_output_amount
    if fixed_output_amount is None:
        raise ValueError("fixed_output_amount must be set for MeteoraDammV2 swap")

    swap_mode = _resolve_swap_mode(params)
    amount_0, amount_1 = _resolve_amounts(swap_mode, input_amount, fixed_output_amount)

    # Determine input/output mints and programs from the pool sides
    expected_input_mint = params.token_a_mint if is_a_in else params.token_b_mint
    expected_output_mint = params.token_b_mint if is_a_in else params.token_a_mint
    if input_mint is not None:
        _ensure_expected_mint("input_mint", input_mint, expected_input_mint)
    _ensure_expected_mint("output_mint", output_mint, expected_output_mint)
    input_mint = expected_input_mint
    output_mint = expected_output_mint

    input_token_program = params.token_a_program if is_a_in else params.token_b_program
    output_token_program = params.token_b_program if is_a_in else params.token_a_program

    # Get user token accounts
    input_token_account = get_associated_token_address(payer, input_mint, input_token_program)
    output_token_account = get_associated_token_address(payer, output_mint, output_token_program)

    # Get event authority PDA
    event_authority = get_event_authority_pda()

    # Handle input account creation/wrapping
    if create_input_ata and input_mint == WSOL_TOKEN_ACCOUNT:
        instructions.extend(handle_wsol(payer, input_amount))
    elif create_input_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, input_mint, input_token_program
            )
        )

    # Create output ATA if needed
    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, output_token_program
            )
        )

    # Build swap2 instruction data
    data = SWAP2_DISCRIMINATOR + struct.pack("<QQB", amount_0, amount_1, swap_mode)
    accounts = _build_account_metas(
        params, payer, input_token_account, output_token_account, event_authority
    )

    instructions.append(Instruction(METEORA_DAMM_V2_PROGRAM_ID, data, accounts))

    # Close WSOL ATA if requested
    if close_input_ata and input_mint == WSOL_TOKEN_ACCOUNT:
        instructions.extend(close_wsol(payer))

    return instructions


# ============================================
# Build Sell Instructions
# ============================================

def build_sell_instructions(
    payer: Pubkey,
    input_mint: Pubkey,
    input_amount: int,
    params: MeteoraDammV2Params,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = True,
    close_output_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    output_mint: Optional[Pubkey] = None,
) -> List[Instruction]:
    """
    Build Meteora DAMM V2 sell instructions.

    Args:
        payer: The wallet paying for the swap
        input_mint: The token mint to sell
        input_amount: Amount of tokens to sell
        params: Meteora DAMM V2 protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_output_ata: Whether to create WSOL ATA for receiving SOL
        close_output_ata: Whether to close WSOL ATA after swap
        close_input_ata: Whether to close token ATA after swap
        fixed_output_amount: MUST be set for Meteora DAMM V2 swaps

    Returns:
        List of instructions for the sell operation
    """
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Determine if token B is output (WSOL/USDC)
    is_a_in = params.token_b_mint == WSOL_TOKEN_ACCOUNT or params.token_b_mint == USDC_TOKEN_ACCOUNT

    # Meteora DAMM V2 requires fixed_output_amount
    if fixed_output_amount is None:
        raise ValueError("fixed_output_amount must be set for MeteoraDammV2 swap")

    swap_mode = _resolve_swap_mode(params)
    amount_0, amount_1 = _resolve_amounts(swap_mode, input_amount, fixed_output_amount)

    # Determine input/output mints from the pool sides
    expected_input_mint = params.token_a_mint if is_a_in else params.token_b_mint
    expected_output_mint = params.token_b_mint if is_a_in else params.token_a_mint
    _ensure_expected_mint("input_mint", input_mint, expected_input_mint)
    if output_mint is not None:
        _ensure_expected_mint("output_mint", output_mint, expected_output_mint)
    input_mint = expected_input_mint
    output_mint = expected_output_mint

    # Get token programs based on direction
    input_token_program = params.token_a_program if is_a_in else params.token_b_program
    output_token_program = params.token_b_program if is_a_in else params.token_a_program

    # Get user token accounts
    input_token_account = get_associated_token_address(payer, input_mint, input_token_program)
    output_token_account = get_associated_token_address(payer, output_mint, output_token_program)

    # Get event authority PDA
    event_authority = get_event_authority_pda()

    # Create output ATA if needed
    if create_output_ata and output_mint == WSOL_TOKEN_ACCOUNT:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
            )
        )
    elif create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, output_token_program
            )
        )

    # Build swap2 instruction data
    data = SWAP2_DISCRIMINATOR + struct.pack("<QQB", amount_0, amount_1, swap_mode)
    accounts = _build_account_metas(
        params, payer, input_token_account, output_token_account, event_authority
    )

    instructions.append(Instruction(METEORA_DAMM_V2_PROGRAM_ID, data, accounts))

    # Close WSOL ATA if requested
    if close_output_ata and output_mint == WSOL_TOKEN_ACCOUNT:
        instructions.extend(close_wsol(payer))

    # Close token ATA if requested
    if close_input_ata:
        instructions.append(
            close_token_account_instruction(
                input_token_program,
                input_token_account,
                payer,
                payer,
            )
        )

    return instructions


# ===== Pool State Decoder - from Rust: src/instruction/utils/meteora_damm_v2_types.rs =====

METEORA_POOL_SIZE = 1104


@dataclass
class MeteoraBaseFeeStruct:
    cliff_fee_numerator: int
    fee_scheduler_mode: int
    padding_0: bytes
    number_of_period: int
    period_frequency: int
    reduction_factor: int
    padding_1: int

@dataclass
class MeteoraDynamicFeeStruct:
    initialized: int
    padding: bytes
    max_volatility_accumulator: int
    variable_fee_control: int
    bin_step: int
    filter_period: int
    decay_period: int
    reduction_factor: int
    last_update_timestamp: int
    bin_step_u128: int
    sqrt_price_reference: int
    volatility_accumulator: int
    volatility_reference: int

@dataclass
class MeteoraPoolFeesStruct:
    base_fee: MeteoraBaseFeeStruct
    protocol_fee_percent: int
    partner_fee_percent: int
    referral_fee_percent: int
    padding_0: bytes
    dynamic_fee: MeteoraDynamicFeeStruct
    padding_1: list[int]
    # Current meanings of previously reserved bytes; legacy overlays stay available.
    compounding_fee_bps: int = 0
    init_sqrt_price: int = 0

@dataclass
class MeteoraPoolMetrics:
    total_lp_a_fee: int
    total_lp_b_fee: int
    total_protocol_a_fee: int
    total_protocol_b_fee: int
    total_partner_a_fee: int
    total_partner_b_fee: int
    total_position: int
    padding: int

@dataclass
class MeteoraRewardInfo:
    initialized: int
    reward_token_flag: int
    padding_0: bytes
    padding_1: bytes
    mint: Pubkey
    vault: Pubkey
    funder: Pubkey
    reward_duration: int
    reward_duration_end: int
    reward_rate: int
    reward_per_token_stored: bytes
    last_update_time: int
    cumulative_seconds_with_empty_liquidity_reward: int

@dataclass
class MeteoraPool:
    pool_fees: MeteoraPoolFeesStruct
    token_a_mint: Pubkey
    token_b_mint: Pubkey
    token_a_vault: Pubkey
    token_b_vault: Pubkey
    whitelisted_vault: Pubkey
    partner: Pubkey
    liquidity: int
    padding: int
    protocol_a_fee: int
    protocol_b_fee: int
    partner_a_fee: int
    partner_b_fee: int
    sqrt_min_price: int
    sqrt_max_price: int
    sqrt_price: int
    activation_point: int
    activation_type: int
    pool_status: int
    token_a_flag: int
    token_b_flag: int
    collect_fee_mode: int
    pool_type: int
    padding_0: bytes
    fee_a_per_liquidity: bytes
    fee_b_per_liquidity: bytes
    permanent_lock_liquidity: int
    metrics: MeteoraPoolMetrics
    padding_1: list[int]
    reward_infos: list[MeteoraRewardInfo]
    dead_liquidity_fee_checkpoint: int = 0
    fee_version: int = 0
    creator: Pubkey = Pubkey.default()
    token_a_amount: int = 0
    token_b_amount: int = 0
    layout_version: int = 0


def decode_meteora_pool(data: bytes) -> MeteoraPool | None:
    """Decode current DAMM v2 fields and legacy overlays; allow trailing extensions."""
    if len(data)<METEORA_POOL_SIZE:return None
    offset=0
    def take(size):
        nonlocal offset
        v=bytes(data[offset:offset+size]);offset+=size;return v
    def read_BaseFeeStruct():
        return MeteoraBaseFeeStruct(
            cliff_fee_numerator=int.from_bytes(take(8),"little"),
            fee_scheduler_mode=int.from_bytes(take(1),"little"),
            padding_0=take(5),
            number_of_period=int.from_bytes(take(2),"little"),
            period_frequency=int.from_bytes(take(8),"little"),
            reduction_factor=int.from_bytes(take(8),"little"),
            padding_1=int.from_bytes(take(8),"little"),
        )
    def read_DynamicFeeStruct():
        return MeteoraDynamicFeeStruct(
            initialized=int.from_bytes(take(1),"little"),
            padding=take(7),
            max_volatility_accumulator=int.from_bytes(take(4),"little"),
            variable_fee_control=int.from_bytes(take(4),"little"),
            bin_step=int.from_bytes(take(2),"little"),
            filter_period=int.from_bytes(take(2),"little"),
            decay_period=int.from_bytes(take(2),"little"),
            reduction_factor=int.from_bytes(take(2),"little"),
            last_update_timestamp=int.from_bytes(take(8),"little"),
            bin_step_u128=int.from_bytes(take(16),"little"),
            sqrt_price_reference=int.from_bytes(take(16),"little"),
            volatility_accumulator=int.from_bytes(take(16),"little"),
            volatility_reference=int.from_bytes(take(16),"little"),
        )
    def read_PoolFeesStruct():
        return MeteoraPoolFeesStruct(
            base_fee=read_BaseFeeStruct(),
            protocol_fee_percent=int.from_bytes(take(1),"little"),
            partner_fee_percent=int.from_bytes(take(1),"little"),
            referral_fee_percent=int.from_bytes(take(1),"little"),
            padding_0=take(5),
            dynamic_fee=read_DynamicFeeStruct(),
            padding_1=[int.from_bytes(take(8),"little") for _ in range(2)],
        )
    def read_PoolMetrics():
        return MeteoraPoolMetrics(
            total_lp_a_fee=int.from_bytes(take(16),"little"),
            total_lp_b_fee=int.from_bytes(take(16),"little"),
            total_protocol_a_fee=int.from_bytes(take(8),"little"),
            total_protocol_b_fee=int.from_bytes(take(8),"little"),
            total_partner_a_fee=int.from_bytes(take(8),"little"),
            total_partner_b_fee=int.from_bytes(take(8),"little"),
            total_position=int.from_bytes(take(8),"little"),
            padding=int.from_bytes(take(8),"little"),
        )
    def read_RewardInfo():
        return MeteoraRewardInfo(
            initialized=int.from_bytes(take(1),"little"),
            reward_token_flag=int.from_bytes(take(1),"little"),
            padding_0=take(6),
            padding_1=take(8),
            mint=Pubkey.from_bytes(take(32)),
            vault=Pubkey.from_bytes(take(32)),
            funder=Pubkey.from_bytes(take(32)),
            reward_duration=int.from_bytes(take(8),"little"),
            reward_duration_end=int.from_bytes(take(8),"little"),
            reward_rate=int.from_bytes(take(16),"little"),
            reward_per_token_stored=take(32),
            last_update_time=int.from_bytes(take(8),"little"),
            cumulative_seconds_with_empty_liquidity_reward=int.from_bytes(take(8),"little"),
        )
    def read_Pool():
        return MeteoraPool(
            pool_fees=read_PoolFeesStruct(),
            token_a_mint=Pubkey.from_bytes(take(32)),
            token_b_mint=Pubkey.from_bytes(take(32)),
            token_a_vault=Pubkey.from_bytes(take(32)),
            token_b_vault=Pubkey.from_bytes(take(32)),
            whitelisted_vault=Pubkey.from_bytes(take(32)),
            partner=Pubkey.from_bytes(take(32)),
            liquidity=int.from_bytes(take(16),"little"),
            padding=int.from_bytes(take(16),"little"),
            protocol_a_fee=int.from_bytes(take(8),"little"),
            protocol_b_fee=int.from_bytes(take(8),"little"),
            partner_a_fee=int.from_bytes(take(8),"little"),
            partner_b_fee=int.from_bytes(take(8),"little"),
            sqrt_min_price=int.from_bytes(take(16),"little"),
            sqrt_max_price=int.from_bytes(take(16),"little"),
            sqrt_price=int.from_bytes(take(16),"little"),
            activation_point=int.from_bytes(take(8),"little"),
            activation_type=int.from_bytes(take(1),"little"),
            pool_status=int.from_bytes(take(1),"little"),
            token_a_flag=int.from_bytes(take(1),"little"),
            token_b_flag=int.from_bytes(take(1),"little"),
            collect_fee_mode=int.from_bytes(take(1),"little"),
            pool_type=int.from_bytes(take(1),"little"),
            padding_0=take(2),
            fee_a_per_liquidity=take(32),
            fee_b_per_liquidity=take(32),
            permanent_lock_liquidity=int.from_bytes(take(16),"little"),
            metrics=read_PoolMetrics(),
            padding_1=[int.from_bytes(take(8),"little") for _ in range(10)],
            reward_infos=[read_RewardInfo() for _ in range(2)],
        )
    pool = read_Pool()
    pool.pool_fees.compounding_fee_bps = int.from_bytes(data[46:48], "little")
    pool.pool_fees.init_sqrt_price = int.from_bytes(data[144:160], "little")
    pool.dead_liquidity_fee_checkpoint = int.from_bytes(data[400:408], "little")
    pool.fee_version = data[478]
    pool.creator = Pubkey.from_bytes(data[640:672])
    pool.token_a_amount = int.from_bytes(data[672:680], "little")
    pool.token_b_amount = int.from_bytes(data[680:688], "little")
    pool.layout_version = data[688]
    return pool

# ============================================
# Exports
# ============================================

__all__ = [
    # Program IDs and Constants
    "METEORA_DAMM_V2_PROGRAM_ID",
    "AUTHORITY",
    # Discriminators
    "SWAP_DISCRIMINATOR",
    # PDA Functions
    "get_event_authority_pda",
    # Params
    "MeteoraDammV2Params",
    # Instruction Builders
    "build_buy_instructions",
    "build_sell_instructions",
    # Pool State Decoder
    "METEORA_POOL_SIZE",
    "MeteoraBaseFeeStruct",
    "MeteoraDynamicFeeStruct",
    "MeteoraPoolFeesStruct",
    "MeteoraPoolMetrics",
    "MeteoraRewardInfo",
    "MeteoraPool",
    "decode_meteora_pool",
]
