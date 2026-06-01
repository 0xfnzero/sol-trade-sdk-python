"""
Raydium CPMM instruction builder for Solana trading SDK.
Production-grade implementation with all constants, discriminators, and PDA derivation functions.
"""

from typing import List, Optional
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import struct

from .common import (
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
    TOKEN_PROGRAM_2022,
    WSOL_TOKEN_ACCOUNT,
    USDC_TOKEN_ACCOUNT,
    DEFAULT_SLIPPAGE,
    get_associated_token_address,
    create_associated_token_account_idempotent_instruction,
    handle_wsol,
    close_wsol,
    close_token_account_instruction,
    calculate_with_slippage_sell,
)

# ============================================
# Raydium CPMM Program ID
# ============================================

RAYDIUM_CPMM_PROGRAM_ID: Pubkey = Pubkey.from_string("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C")

# ============================================
# Raydium CPMM Constants
# ============================================

# Authority
AUTHORITY: Pubkey = Pubkey.from_string("GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL")

# Fee Rates
FEE_RATE_DENOMINATOR_VALUE: int = 1_000_000
TRADE_FEE_RATE: int = 2500
CREATOR_FEE_RATE: int = 0
PROTOCOL_FEE_RATE: int = 120000
FUND_FEE_RATE: int = 40000

# ============================================
# Instruction Discriminators
# ============================================

SWAP_BASE_IN_DISCRIMINATOR: bytes = bytes([143, 190, 90, 218, 196, 30, 51, 222])
SWAP_BASE_OUT_DISCRIMINATOR: bytes = bytes([55, 217, 98, 86, 163, 74, 180, 173])

# ============================================
# Seeds
# ============================================

POOL_SEED = b"pool"
POOL_VAULT_SEED = b"pool_vault"
OBSERVATION_STATE_SEED = b"observation"

# ============================================
# PDA Derivation Functions
# ============================================

def get_pool_pda(amm_config: Pubkey, mint1: Pubkey, mint2: Pubkey) -> Pubkey:
    """
    Derive the pool PDA for a given amm_config and two mints.
    Seeds: ["pool", amm_config, mint1, mint2]
    """
    seeds = [POOL_SEED, bytes(amm_config), bytes(mint1), bytes(mint2)]
    (pda, _) = Pubkey.find_program_address(seeds, RAYDIUM_CPMM_PROGRAM_ID)
    return pda


def get_vault_pda(pool_state: Pubkey, mint: Pubkey) -> Pubkey:
    """
    Derive the vault PDA for a given pool and mint.
    Seeds: ["pool_vault", pool_state, mint]
    """
    seeds = [POOL_VAULT_SEED, bytes(pool_state), bytes(mint)]
    (pda, _) = Pubkey.find_program_address(seeds, RAYDIUM_CPMM_PROGRAM_ID)
    return pda


def get_observation_state_pda(pool_state: Pubkey) -> Pubkey:
    """
    Derive the observation state PDA for a given pool.
    Seeds: ["observation", pool_state]
    """
    seeds = [OBSERVATION_STATE_SEED, bytes(pool_state)]
    (pda, _) = Pubkey.find_program_address(seeds, RAYDIUM_CPMM_PROGRAM_ID)
    return pda


# ============================================
# Raydium CPMM Parameters Dataclass
# ============================================

@dataclass
class RaydiumCpmmParams:
    """Parameters for Raydium CPMM protocol trading."""
    pool_state: Optional[Pubkey] = None  # If None, will derive from mints and amm_config
    amm_config: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    base_mint: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    quote_mint: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    base_reserve: int = 0
    quote_reserve: int = 0
    base_vault: Optional[Pubkey] = None
    quote_vault: Optional[Pubkey] = None
    base_token_program: Pubkey = TOKEN_PROGRAM
    quote_token_program: Pubkey = TOKEN_PROGRAM
    observation_state: Optional[Pubkey] = None

    @property
    def is_wsol(self) -> bool:
        """Check if the pool contains WSOL."""
        return self.base_mint == WSOL_TOKEN_ACCOUNT or self.quote_mint == WSOL_TOKEN_ACCOUNT

    @property
    def is_usdc(self) -> bool:
        """Check if the pool contains USDC."""
        return self.base_mint == USDC_TOKEN_ACCOUNT or self.quote_mint == USDC_TOKEN_ACCOUNT


# ============================================
# Raydium CPMM Calculation Functions
# ============================================

def compute_swap_amount(
    base_reserve: int,
    quote_reserve: int,
    is_base_in: bool,
    amount_in: int,
    slippage_bps: int,
) -> tuple:
    """
    Compute swap output amount for Raydium CPMM.
    Returns (amount_out, min_amount_out).
    """
    # Apply trade fee (0.25%)
    fee_rate = TRADE_FEE_RATE / FEE_RATE_DENOMINATOR_VALUE
    amount_in_after_fee = int(amount_in * (1 - fee_rate))

    if is_base_in:
        # Base -> Quote
        # out = (amount_in * quote_reserve) / (base_reserve + amount_in)
        numerator = amount_in_after_fee * quote_reserve
        denominator = base_reserve + amount_in_after_fee
        amount_out = numerator // denominator
    else:
        # Quote -> Base
        # out = (amount_in * base_reserve) / (quote_reserve + amount_in)
        numerator = amount_in_after_fee * base_reserve
        denominator = quote_reserve + amount_in_after_fee
        amount_out = numerator // denominator

    # Apply slippage
    min_amount_out = calculate_with_slippage_sell(amount_out, slippage_bps)

    return (amount_out, min_amount_out)


# ============================================
# Build Buy Instructions
# ============================================

def build_buy_instructions(
    payer: Pubkey,
    output_mint: Pubkey,
    input_amount: int,
    params: RaydiumCpmmParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_input_ata: bool = True,
    create_output_ata: bool = True,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
) -> List[Instruction]:
    """
    Build Raydium CPMM buy instructions.

    Args:
        payer: The wallet paying for the swap
        output_mint: The token mint to buy
        input_amount: Amount of SOL/USDC to spend
        params: Raydium CPMM protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_input_ata: Whether to create WSOL ATA if needed
        create_output_ata: Whether to create output token ATA if needed
        close_input_ata: Whether to close WSOL ATA after swap
        fixed_output_amount: If set, use this as exact output amount

    Returns:
        List of instructions for the buy operation
    """
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Get pool state
    pool_state = params.pool_state
    if pool_state is None:
        pool_state = get_pool_pda(params.amm_config, params.base_mint, params.quote_mint)

    # Determine if base is input (WSOL/USDC)
    is_base_in = params.base_mint == WSOL_TOKEN_ACCOUNT or params.base_mint == USDC_TOKEN_ACCOUNT

    input_mint = params.base_mint if is_base_in else params.quote_mint
    input_token_program = params.base_token_program if is_base_in else params.quote_token_program
    expected_output_mint = params.quote_mint if is_base_in else params.base_mint
    output_token_program = params.quote_token_program if is_base_in else params.base_token_program
    if output_mint != expected_output_mint:
        raise ValueError(f"output_mint must match Raydium CPMM pool side {expected_output_mint}")

    if fixed_output_amount is not None:
        minimum_amount_out = fixed_output_amount
    else:
        _, min_amount_out = compute_swap_amount(
            params.base_reserve,
            params.quote_reserve,
            is_base_in,
            input_amount,
            slippage_bps,
        )
        minimum_amount_out = min_amount_out

    # Get user token accounts
    input_token_account = get_associated_token_address(payer, input_mint, input_token_program)
    output_token_account = get_associated_token_address(payer, output_mint, output_token_program)

    # Get vaults
    input_vault = params.base_vault if is_base_in else params.quote_vault
    if input_vault is None:
        input_vault = get_vault_pda(pool_state, input_mint)

    output_vault = params.quote_vault if is_base_in else params.base_vault
    if output_vault is None:
        output_vault = get_vault_pda(pool_state, output_mint)

    # Get observation state
    observation_state = params.observation_state
    if observation_state is None:
        observation_state = get_observation_state_pda(pool_state)

    # Handle input account creation/wrapping
    if create_input_ata:
        if input_mint == WSOL_TOKEN_ACCOUNT:
            instructions.extend(handle_wsol(payer, input_amount))
        else:
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

    # Build instruction data
    if fixed_output_amount is not None:
        data = SWAP_BASE_OUT_DISCRIMINATOR + struct.pack("<QQ", input_amount, fixed_output_amount)
    else:
        data = SWAP_BASE_IN_DISCRIMINATOR + struct.pack("<QQ", input_amount, minimum_amount_out)

    # Build accounts list
    accounts = [
        AccountMeta(payer, True, True),  # payer (signer, writable)
        AccountMeta(AUTHORITY, False, False),  # authority (readonly)
        AccountMeta(params.amm_config, False, False),  # amm_config (readonly)
        AccountMeta(pool_state, False, True),  # pool_state (writable)
        AccountMeta(input_token_account, False, True),  # input_token_account (writable)
        AccountMeta(output_token_account, False, True),  # output_token_account (writable)
        AccountMeta(input_vault, False, True),  # input_vault (writable)
        AccountMeta(output_vault, False, True),  # output_vault (writable)
        AccountMeta(input_token_program, False, False),  # input_token_program (readonly)
        AccountMeta(output_token_program, False, False),  # output_token_program (readonly)
        AccountMeta(input_mint, False, False),  # input_token_mint (readonly)
        AccountMeta(output_mint, False, False),  # output_token_mint (readonly)
        AccountMeta(observation_state, False, True),  # observation_state (writable)
    ]

    instructions.append(Instruction(RAYDIUM_CPMM_PROGRAM_ID, data, accounts))

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
    params: RaydiumCpmmParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = True,
    close_output_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
) -> List[Instruction]:
    """
    Build Raydium CPMM sell instructions.

    Args:
        payer: The wallet paying for the swap
        input_mint: The token mint to sell
        input_amount: Amount of tokens to sell
        params: Raydium CPMM protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_output_ata: Whether to create WSOL ATA for receiving SOL
        close_output_ata: Whether to close WSOL ATA after swap
        close_input_ata: Whether to close token ATA after swap
        fixed_output_amount: If set, use this as exact output amount

    Returns:
        List of instructions for the sell operation
    """
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Get pool state
    pool_state = params.pool_state
    if pool_state is None:
        pool_state = get_pool_pda(params.amm_config, params.base_mint, params.quote_mint)

    # Determine if quote is output (WSOL/USDC)
    is_quote_out = params.quote_mint == WSOL_TOKEN_ACCOUNT or params.quote_mint == USDC_TOKEN_ACCOUNT

    expected_input_mint = params.base_mint if is_quote_out else params.quote_mint
    input_token_program = params.base_token_program if is_quote_out else params.quote_token_program
    output_mint = params.quote_mint if is_quote_out else params.base_mint
    output_token_program = params.quote_token_program if is_quote_out else params.base_token_program
    if input_mint != expected_input_mint:
        raise ValueError(f"input_mint must match Raydium CPMM pool side {expected_input_mint}")

    if fixed_output_amount is not None:
        minimum_amount_out = fixed_output_amount
    else:
        _, min_amount_out = compute_swap_amount(
            params.base_reserve,
            params.quote_reserve,
            is_quote_out,  # Swap direction is reversed for sell
            input_amount,
            slippage_bps,
        )
        minimum_amount_out = min_amount_out

    # Get user token accounts
    output_token_account = get_associated_token_address(payer, output_mint, output_token_program)
    input_token_account = get_associated_token_address(payer, input_mint, input_token_program)

    # Get vaults
    output_vault = params.quote_vault if is_quote_out else params.base_vault
    if output_vault is None:
        output_vault = get_vault_pda(pool_state, output_mint)

    input_vault = params.base_vault if is_quote_out else params.quote_vault
    if input_vault is None:
        input_vault = get_vault_pda(pool_state, input_mint)

    # Get observation state
    observation_state = params.observation_state
    if observation_state is None:
        observation_state = get_observation_state_pda(pool_state)

    # Create output ATA if needed
    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, output_token_program
            )
        )

    # Build instruction data
    if fixed_output_amount is not None:
        data = SWAP_BASE_OUT_DISCRIMINATOR + struct.pack("<QQ", input_amount, fixed_output_amount)
    else:
        data = SWAP_BASE_IN_DISCRIMINATOR + struct.pack("<QQ", input_amount, minimum_amount_out)

    # Build accounts list
    accounts = [
        AccountMeta(payer, True, True),  # payer (signer, writable)
        AccountMeta(AUTHORITY, False, False),  # authority (readonly)
        AccountMeta(params.amm_config, False, False),  # amm_config (readonly)
        AccountMeta(pool_state, False, True),  # pool_state (writable)
        AccountMeta(input_token_account, False, True),  # input_token_account (writable)
        AccountMeta(output_token_account, False, True),  # output_token_account (writable)
        AccountMeta(input_vault, False, True),  # input_vault (writable)
        AccountMeta(output_vault, False, True),  # output_vault (writable)
        AccountMeta(input_token_program, False, False),  # input_token_program (readonly)
        AccountMeta(output_token_program, False, False),  # output_token_program (readonly)
        AccountMeta(input_mint, False, False),  # input_token_mint (readonly)
        AccountMeta(output_mint, False, False),  # output_token_mint (readonly)
        AccountMeta(observation_state, False, True),  # observation_state (writable)
    ]

    instructions.append(Instruction(RAYDIUM_CPMM_PROGRAM_ID, data, accounts))

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


# ===== Pool State Decoder - from Rust: src/instruction/utils/raydium_cpmm_types.rs =====

RAYDIUM_CPMM_POOL_STATE_SIZE = 629


@dataclass
class RaydiumCPMMpoolState:
    """Decoded Raydium CPMM pool state - matches Rust: src/instruction/utils/raydium_cpmm_types.rs PoolState"""
    amm_config: Pubkey
    pool_creator: Pubkey
    token0_vault: Pubkey
    token1_vault: Pubkey
    lp_mint: Pubkey
    token0_mint: Pubkey
    token1_mint: Pubkey
    token0_program: Pubkey
    token1_program: Pubkey
    observation_key: Pubkey
    auth_bump: int
    status: int
    lp_mint_decimals: int
    mint0_decimals: int
    mint1_decimals: int
    lp_supply: int
    protocol_fees_token0: int
    protocol_fees_token1: int
    fund_fees_token0: int
    fund_fees_token1: int
    open_time: int
    recent_epoch: int


def decode_raydium_cpmm_pool_state(data: bytes) -> RaydiumCPMMpoolState | None:
    """
    Decode a Raydium CPMM pool state from account data.
    100% from Rust: src/instruction/utils/raydium_cpmm_types.rs pool_state_decode

    Args:
        data: Raw account data (should be at least 629 bytes)

    Returns:
        RaydiumCPMMpoolState if successful, None if data is invalid
    """
    if len(data) < RAYDIUM_CPMM_POOL_STATE_SIZE:
        return None

    try:
        offset = 0

        # amm_config: Pubkey
        amm_config = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # pool_creator: Pubkey
        pool_creator = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token0_vault: Pubkey
        token0_vault = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token1_vault: Pubkey
        token1_vault = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # lp_mint: Pubkey
        lp_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token0_mint: Pubkey
        token0_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token1_mint: Pubkey
        token1_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token0_program: Pubkey
        token0_program = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token1_program: Pubkey
        token1_program = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # observation_key: Pubkey
        observation_key = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # auth_bump: u8
        auth_bump = data[offset]
        offset += 1

        # status: u8
        status = data[offset]
        offset += 1

        # lp_mint_decimals: u8
        lp_mint_decimals = data[offset]
        offset += 1

        # mint0_decimals: u8
        mint0_decimals = data[offset]
        offset += 1

        # mint1_decimals: u8
        mint1_decimals = data[offset]
        offset += 1

        # lp_supply: u64
        lp_supply = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # protocol_fees_token0: u64
        protocol_fees_token0 = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # protocol_fees_token1: u64
        protocol_fees_token1 = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # fund_fees_token0: u64
        fund_fees_token0 = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # fund_fees_token1: u64
        fund_fees_token1 = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # open_time: u64
        open_time = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # recent_epoch: u64
        recent_epoch = struct.unpack_from('<Q', data, offset)[0]

        return RaydiumCPMMpoolState(
            amm_config=amm_config,
            pool_creator=pool_creator,
            token0_vault=token0_vault,
            token1_vault=token1_vault,
            lp_mint=lp_mint,
            token0_mint=token0_mint,
            token1_mint=token1_mint,
            token0_program=token0_program,
            token1_program=token1_program,
            observation_key=observation_key,
            auth_bump=auth_bump,
            status=status,
            lp_mint_decimals=lp_mint_decimals,
            mint0_decimals=mint0_decimals,
            mint1_decimals=mint1_decimals,
            lp_supply=lp_supply,
            protocol_fees_token0=protocol_fees_token0,
            protocol_fees_token1=protocol_fees_token1,
            fund_fees_token0=fund_fees_token0,
            fund_fees_token1=fund_fees_token1,
            open_time=open_time,
            recent_epoch=recent_epoch,
        )
    except Exception:
        return None


# ===== Async Fetch Functions - from Rust: src/instruction/utils/raydium_cpmm.rs =====

from typing import Protocol, runtime_checkable


@runtime_checkable
class RaydiumCpmmPoolFetcher(Protocol):
    """Protocol for fetching Raydium CPMM pool data from RPC"""
    async def get_account_info(self, pubkey: Pubkey) -> bytes | None:
        ...


async def fetch_pool_state(
    fetcher: RaydiumCpmmPoolFetcher,
    pool_address: Pubkey
) -> RaydiumCPMMpoolState | None:
    """
    Fetch a Raydium CPMM pool state from RPC.
    100% from Rust: src/instruction/utils/raydium_cpmm.rs fetch_pool_state

    Args:
        fetcher: Object implementing RaydiumCpmmPoolFetcher protocol
        pool_address: The pool account address

    Returns:
        RaydiumCPMMpoolState if successful, None if not found or invalid
    """
    data = await fetcher.get_account_info(pool_address)
    if data is None or len(data) < 8:
        return None
    return decode_raydium_cpmm_pool_state(data[8:])


# ============================================
# Exports
# ============================================

__all__ = [
    # Program IDs and Constants
    "RAYDIUM_CPMM_PROGRAM_ID",
    "AUTHORITY",
    "FEE_RATE_DENOMINATOR_VALUE",
    "TRADE_FEE_RATE",
    "CREATOR_FEE_RATE",
    "PROTOCOL_FEE_RATE",
    "FUND_FEE_RATE",
    # Discriminators
    "SWAP_BASE_IN_DISCRIMINATOR",
    "SWAP_BASE_OUT_DISCRIMINATOR",
    # PDA Functions
    "get_pool_pda",
    "get_vault_pda",
    "get_observation_state_pda",
    # Params
    "RaydiumCpmmParams",
    # Calculation Functions
    "compute_swap_amount",
    # Instruction Builders
    "build_buy_instructions",
    "build_sell_instructions",
]
