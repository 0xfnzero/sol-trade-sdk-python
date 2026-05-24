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
SWAP_MODE_PARTIAL_FILL: int = 1

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

    @property
    def is_wsol(self) -> bool:
        """Check if the pool contains WSOL."""
        return self.token_a_mint == WSOL_TOKEN_ACCOUNT or self.token_b_mint == WSOL_TOKEN_ACCOUNT

    @property
    def is_usdc(self) -> bool:
        """Check if the pool contains USDC."""
        return self.token_a_mint == USDC_TOKEN_ACCOUNT or self.token_b_mint == USDC_TOKEN_ACCOUNT


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

    minimum_amount_out = fixed_output_amount

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
    data = (
        SWAP2_DISCRIMINATOR
        + struct.pack("<QQB", input_amount, minimum_amount_out, SWAP_MODE_PARTIAL_FILL)
    )

    # Build accounts list (13 accounts)
    accounts = [
        AccountMeta(AUTHORITY, False, False),  # pool_authority (readonly)
        AccountMeta(params.pool, False, True),  # pool (writable)
        AccountMeta(input_token_account, False, True),  # input_token_account (writable)
        AccountMeta(output_token_account, False, True),  # output_token_account (writable)
        AccountMeta(params.token_a_vault, False, True),  # token_a_vault (writable)
        AccountMeta(params.token_b_vault, False, True),  # token_b_vault (writable)
        AccountMeta(params.token_a_mint, False, False),  # token_a_mint (readonly)
        AccountMeta(params.token_b_mint, False, False),  # token_b_mint (readonly)
        AccountMeta(payer, True, False),  # user_transfer_authority (signer)
        AccountMeta(params.token_a_program, False, False),  # token_a_program (readonly)
        AccountMeta(params.token_b_program, False, False),  # token_b_program (readonly)
        AccountMeta(event_authority, False, False),  # event_authority (readonly)
        AccountMeta(METEORA_DAMM_V2_PROGRAM_ID, False, False),  # program (readonly)
    ]

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

    minimum_amount_out = fixed_output_amount

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
    data = (
        SWAP2_DISCRIMINATOR
        + struct.pack("<QQB", input_amount, minimum_amount_out, SWAP_MODE_PARTIAL_FILL)
    )

    # Build accounts list (13 accounts)
    accounts = [
        AccountMeta(AUTHORITY, False, False),  # pool_authority (readonly)
        AccountMeta(params.pool, False, True),  # pool (writable)
        AccountMeta(input_token_account, False, True),  # input_token_account (writable)
        AccountMeta(output_token_account, False, True),  # output_token_account (writable)
        AccountMeta(params.token_a_vault, False, True),  # token_a_vault (writable)
        AccountMeta(params.token_b_vault, False, True),  # token_b_vault (writable)
        AccountMeta(params.token_a_mint, False, False),  # token_a_mint (readonly)
        AccountMeta(params.token_b_mint, False, False),  # token_b_mint (readonly)
        AccountMeta(payer, True, False),  # user_transfer_authority (signer)
        AccountMeta(params.token_a_program, False, False),  # token_a_program (readonly)
        AccountMeta(params.token_b_program, False, False),  # token_b_program (readonly)
        AccountMeta(event_authority, False, False),  # event_authority (readonly)
        AccountMeta(METEORA_DAMM_V2_PROGRAM_ID, False, False),  # program (readonly)
    ]

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
    """Base fee structure for Meteora"""
    cliff_fee_numerator: int
    fee_scheduler_mode: int
    number_of_period: int
    period_frequency: int
    reduction_factor: int


@dataclass
class MeteoraDynamicFeeStruct:
    """Dynamic fee structure for Meteora"""
    initialized: int
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
    """Pool fees structure for Meteora"""
    base_fee: MeteoraBaseFeeStruct
    protocol_fee_percent: int
    partner_fee_percent: int
    referral_fee_percent: int
    dynamic_fee: MeteoraDynamicFeeStruct


@dataclass
class MeteoraPoolMetrics:
    """Pool metrics for Meteora"""
    total_lp_a_fee: int
    total_lp_b_fee: int
    total_protocol_a_fee: int
    total_protocol_b_fee: int
    total_partner_a_fee: int
    total_partner_b_fee: int
    total_position: int


@dataclass
class MeteoraRewardInfo:
    """Reward info for Meteora pool"""
    initialized: int
    reward_token_flag: int
    mint: Pubkey
    vault: Pubkey
    funder: Pubkey
    reward_duration: int
    reward_duration_end: int
    reward_rate: int


@dataclass
class MeteoraPool:
    """Decoded Meteora DAMM v2 pool - matches Rust: src/instruction/utils/meteora_damm_v2_types.rs Pool"""
    pool_fees: MeteoraPoolFeesStruct
    token_a_mint: Pubkey
    token_b_mint: Pubkey
    token_a_vault: Pubkey
    token_b_vault: Pubkey
    whitelisted_vault: Pubkey
    partner: Pubkey
    liquidity: int
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
    permanent_lock_liquidity: int
    metrics: MeteoraPoolMetrics
    reward_infos: list  # List of MeteoraRewardInfo


def decode_meteora_pool(data: bytes) -> MeteoraPool | None:
    """
    Decode a Meteora DAMM v2 pool from account data.
    100% from Rust: src/instruction/utils/meteora_damm_v2_types.rs pool_decode

    Args:
        data: Raw account data (should be at least 1104 bytes)

    Returns:
        MeteoraPool if successful, None if data is invalid
    """
    if len(data) < METEORA_POOL_SIZE:
        return None

    try:
        offset = 0

        # pool_fees: PoolFeesStruct
        # BaseFeeStruct
        cliff_fee_numerator = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        fee_scheduler_mode = data[offset]
        offset += 1
        offset += 5  # padding_0
        number_of_period = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        period_frequency = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        reduction_factor = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        offset += 8  # padding_1

        base_fee = MeteoraBaseFeeStruct(
            cliff_fee_numerator=cliff_fee_numerator,
            fee_scheduler_mode=fee_scheduler_mode,
            number_of_period=number_of_period,
            period_frequency=period_frequency,
            reduction_factor=reduction_factor,
        )

        protocol_fee_percent = data[offset]
        offset += 1
        partner_fee_percent = data[offset]
        offset += 1
        referral_fee_percent = data[offset]
        offset += 1
        offset += 5  # padding_0

        # DynamicFeeStruct
        initialized = data[offset]
        offset += 1
        offset += 7  # padding
        max_volatility_accumulator = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        variable_fee_control = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        bin_step = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        filter_period = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        decay_period = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        reduction_factor = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        last_update_timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        bin_step_u128 = struct.unpack_from('<QQ', data, offset)
        offset += 16
        sqrt_price_reference = struct.unpack_from('<QQ', data, offset)
        offset += 16
        volatility_accumulator = struct.unpack_from('<QQ', data, offset)
        offset += 16
        volatility_reference = struct.unpack_from('<QQ', data, offset)
        offset += 16

        dynamic_fee = MeteoraDynamicFeeStruct(
            initialized=initialized,
            max_volatility_accumulator=max_volatility_accumulator,
            variable_fee_control=variable_fee_control,
            bin_step=bin_step,
            filter_period=filter_period,
            decay_period=decay_period,
            reduction_factor=reduction_factor,
            last_update_timestamp=last_update_timestamp,
            bin_step_u128=bin_step_u128[0] + (bin_step_u128[1] << 64),
            sqrt_price_reference=sqrt_price_reference[0] + (sqrt_price_reference[1] << 64),
            volatility_accumulator=volatility_accumulator[0] + (volatility_accumulator[1] << 64),
            volatility_reference=volatility_reference[0] + (volatility_reference[1] << 64),
        )

        offset += 16  # padding_1 for PoolFeesStruct

        pool_fees = MeteoraPoolFeesStruct(
            base_fee=base_fee,
            protocol_fee_percent=protocol_fee_percent,
            partner_fee_percent=partner_fee_percent,
            referral_fee_percent=referral_fee_percent,
            dynamic_fee=dynamic_fee,
        )

        # token_a_mint: Pubkey
        token_a_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token_b_mint: Pubkey
        token_b_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token_a_vault: Pubkey
        token_a_vault = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token_b_vault: Pubkey
        token_b_vault = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # whitelisted_vault: Pubkey
        whitelisted_vault = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # partner: Pubkey
        partner = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # liquidity: u128
        liquidity_lo = struct.unpack_from('<Q', data, offset)[0]
        liquidity_hi = struct.unpack_from('<Q', data, offset + 8)[0]
        liquidity = liquidity_lo + (liquidity_hi << 64)
        offset += 16

        offset += 16  # padding

        # protocol_a_fee: u64
        protocol_a_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # protocol_b_fee: u64
        protocol_b_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # partner_a_fee: u64
        partner_a_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # partner_b_fee: u64
        partner_b_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # sqrt_min_price: u128
        sqrt_min_price_lo = struct.unpack_from('<Q', data, offset)[0]
        sqrt_min_price_hi = struct.unpack_from('<Q', data, offset + 8)[0]
        sqrt_min_price = sqrt_min_price_lo + (sqrt_min_price_hi << 64)
        offset += 16

        # sqrt_max_price: u128
        sqrt_max_price_lo = struct.unpack_from('<Q', data, offset)[0]
        sqrt_max_price_hi = struct.unpack_from('<Q', data, offset + 8)[0]
        sqrt_max_price = sqrt_max_price_lo + (sqrt_max_price_hi << 64)
        offset += 16

        # sqrt_price: u128
        sqrt_price_lo = struct.unpack_from('<Q', data, offset)[0]
        sqrt_price_hi = struct.unpack_from('<Q', data, offset + 8)[0]
        sqrt_price = sqrt_price_lo + (sqrt_price_hi << 64)
        offset += 16

        # activation_point: u64
        activation_point = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # activation_type: u8
        activation_type = data[offset]
        offset += 1

        # pool_status: u8
        pool_status = data[offset]
        offset += 1

        # token_a_flag: u8
        token_a_flag = data[offset]
        offset += 1

        # token_b_flag: u8
        token_b_flag = data[offset]
        offset += 1

        # collect_fee_mode: u8
        collect_fee_mode = data[offset]
        offset += 1

        # pool_type: u8
        pool_type = data[offset]
        offset += 1

        offset += 2  # padding_0

        offset += 32  # fee_a_per_liquidity
        offset += 32  # fee_b_per_liquidity

        # permanent_lock_liquidity: u128
        permanent_lock_liquidity_lo = struct.unpack_from('<Q', data, offset)[0]
        permanent_lock_liquidity_hi = struct.unpack_from('<Q', data, offset + 8)[0]
        permanent_lock_liquidity = permanent_lock_liquidity_lo + (permanent_lock_liquidity_hi << 64)
        offset += 16

        # metrics: PoolMetrics
        total_lp_a_fee = struct.unpack_from('<QQ', data, offset)
        offset += 16
        total_lp_b_fee = struct.unpack_from('<QQ', data, offset)
        offset += 16
        total_protocol_a_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        total_protocol_b_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        total_partner_a_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        total_partner_b_fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        total_position = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        offset += 8  # padding

        metrics = MeteoraPoolMetrics(
            total_lp_a_fee=total_lp_a_fee[0] + (total_lp_a_fee[1] << 64),
            total_lp_b_fee=total_lp_b_fee[0] + (total_lp_b_fee[1] << 64),
            total_protocol_a_fee=total_protocol_a_fee,
            total_protocol_b_fee=total_protocol_b_fee,
            total_partner_a_fee=total_partner_a_fee,
            total_partner_b_fee=total_partner_b_fee,
            total_position=total_position,
        )

        offset += 80  # padding_1

        # reward_infos: [RewardInfo; 2] - simplified
        reward_infos = []
        for _ in range(2):
            reward_initialized = data[offset]
            offset += 1
            reward_token_flag = data[offset]
            offset += 1
            offset += 14  # padding
            reward_mint = Pubkey.from_bytes(data[offset:offset + 32])
            offset += 32
            reward_vault = Pubkey.from_bytes(data[offset:offset + 32])
            offset += 32
            reward_funder = Pubkey.from_bytes(data[offset:offset + 32])
            offset += 32
            reward_duration = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            reward_duration_end = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            reward_rate = struct.unpack_from('<QQ', data, offset)
            offset += 16
            offset += 32  # reward_per_token_stored
            offset += 8  # last_update_time
            offset += 8  # cumulative_seconds_with_empty_liquidity_reward

            reward_infos.append(MeteoraRewardInfo(
                initialized=reward_initialized,
                reward_token_flag=reward_token_flag,
                mint=reward_mint,
                vault=reward_vault,
                funder=reward_funder,
                reward_duration=reward_duration,
                reward_duration_end=reward_duration_end,
                reward_rate=reward_rate[0] + (reward_rate[1] << 64),
            ))

        return MeteoraPool(
            pool_fees=pool_fees,
            token_a_mint=token_a_mint,
            token_b_mint=token_b_mint,
            token_a_vault=token_a_vault,
            token_b_vault=token_b_vault,
            whitelisted_vault=whitelisted_vault,
            partner=partner,
            liquidity=liquidity,
            protocol_a_fee=protocol_a_fee,
            protocol_b_fee=protocol_b_fee,
            partner_a_fee=partner_a_fee,
            partner_b_fee=partner_b_fee,
            sqrt_min_price=sqrt_min_price,
            sqrt_max_price=sqrt_max_price,
            sqrt_price=sqrt_price,
            activation_point=activation_point,
            activation_type=activation_type,
            pool_status=pool_status,
            token_a_flag=token_a_flag,
            token_b_flag=token_b_flag,
            collect_fee_mode=collect_fee_mode,
            pool_type=pool_type,
            permanent_lock_liquidity=permanent_lock_liquidity,
            metrics=metrics,
            reward_infos=reward_infos,
        )
    except Exception:
        return None


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
