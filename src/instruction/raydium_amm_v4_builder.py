"""
Raydium AMM V4 instruction builder for Solana trading SDK.
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
    calculate_with_slippage_sell,
)

# ============================================
# Raydium AMM V4 Program ID
# ============================================

RAYDIUM_AMM_V4_PROGRAM_ID: Pubkey = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")

# ============================================
# Raydium AMM V4 Constants
# ============================================

# Authority
AUTHORITY: Pubkey = Pubkey.from_string("5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1")

# Fee Rates
TRADE_FEE_NUMERATOR: int = 25
TRADE_FEE_DENOMINATOR: int = 10000
SWAP_FEE_NUMERATOR: int = 25
SWAP_FEE_DENOMINATOR: int = 10000

# ============================================
# Instruction Discriminators
# ============================================

# Note: Raydium AMM V4 uses single-byte discriminators
SWAP_BASE_IN_DISCRIMINATOR: bytes = bytes([9])
SWAP_BASE_OUT_DISCRIMINATOR: bytes = bytes([11])

# ============================================
# Seeds
# ============================================

POOL_SEED = b"pool"
DEFAULT_PUBKEY: Pubkey = Pubkey.from_string("11111111111111111111111111111111")


# ============================================
# Raydium AMM V4 Parameters Dataclass
# ============================================

@dataclass
class RaydiumAmmV4Params:
    """Parameters for Raydium AMM V4 protocol trading."""
    amm: Pubkey = DEFAULT_PUBKEY
    coin_mint: Pubkey = DEFAULT_PUBKEY
    pc_mint: Pubkey = DEFAULT_PUBKEY
    token_coin: Pubkey = DEFAULT_PUBKEY
    token_pc: Pubkey = DEFAULT_PUBKEY
    amm_open_orders: Pubkey = DEFAULT_PUBKEY
    amm_target_orders: Pubkey = DEFAULT_PUBKEY
    serum_program: Pubkey = DEFAULT_PUBKEY
    serum_market: Pubkey = DEFAULT_PUBKEY
    serum_bids: Pubkey = DEFAULT_PUBKEY
    serum_asks: Pubkey = DEFAULT_PUBKEY
    serum_event_queue: Pubkey = DEFAULT_PUBKEY
    serum_coin_vault_account: Pubkey = DEFAULT_PUBKEY
    serum_pc_vault_account: Pubkey = DEFAULT_PUBKEY
    serum_vault_signer: Pubkey = DEFAULT_PUBKEY
    coin_reserve: int = 0
    pc_reserve: int = 0

    @property
    def is_wsol(self) -> bool:
        """Check if the pool contains WSOL."""
        return self.coin_mint == WSOL_TOKEN_ACCOUNT or self.pc_mint == WSOL_TOKEN_ACCOUNT

    @property
    def is_usdc(self) -> bool:
        """Check if the pool contains USDC."""
        return self.coin_mint == USDC_TOKEN_ACCOUNT or self.pc_mint == USDC_TOKEN_ACCOUNT


def ensure_market_accounts(params: RaydiumAmmV4Params) -> None:
    required = [
        ("amm_open_orders", params.amm_open_orders),
        ("amm_target_orders", params.amm_target_orders),
        ("serum_program", params.serum_program),
        ("serum_market", params.serum_market),
        ("serum_bids", params.serum_bids),
        ("serum_asks", params.serum_asks),
        ("serum_event_queue", params.serum_event_queue),
        ("serum_coin_vault_account", params.serum_coin_vault_account),
        ("serum_pc_vault_account", params.serum_pc_vault_account),
        ("serum_vault_signer", params.serum_vault_signer),
    ]
    for name, account in required:
        if account == DEFAULT_PUBKEY:
            raise ValueError(
                f"Raydium AMM v4 requires {name}; pass real market accounts from the AMM/market state"
            )


def _mint_matches(requested: Pubkey, expected: Pubkey) -> bool:
    return requested == expected or (
        expected == WSOL_TOKEN_ACCOUNT and requested == SOL_TOKEN_ACCOUNT
    )


def _ensure_expected_mint(label: str, requested: Pubkey, expected: Pubkey) -> None:
    if requested != DEFAULT_PUBKEY and not _mint_matches(requested, expected):
        raise ValueError(
            f"{label} must match the Raydium AMM v4 pool side ({expected}), got {requested}"
        )


# ============================================
# Raydium AMM V4 Calculation Functions
# ============================================

def compute_swap_amount(
    coin_reserve: int,
    pc_reserve: int,
    is_coin_in: bool,
    amount_in: int,
    slippage_bps: int,
) -> tuple:
    """
    Compute swap output amount for Raydium AMM V4.
    Returns (amount_out, min_amount_out).
    """
    # Apply trade fee (0.25%)
    amount_in_after_fee = amount_in - (amount_in * TRADE_FEE_NUMERATOR) // TRADE_FEE_DENOMINATOR

    if is_coin_in:
        # Coin -> PC
        # out = (amount_in * pc_reserve) / (coin_reserve + amount_in)
        numerator = amount_in_after_fee * pc_reserve
        denominator = coin_reserve + amount_in_after_fee
        amount_out = numerator // denominator
    else:
        # PC -> Coin
        # out = (amount_in * coin_reserve) / (pc_reserve + amount_in)
        numerator = amount_in_after_fee * coin_reserve
        denominator = pc_reserve + amount_in_after_fee
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
    params: RaydiumAmmV4Params,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_input_ata: bool = True,
    create_output_ata: bool = True,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
) -> List[Instruction]:
    """
    Build Raydium AMM V4 buy instructions.

    Args:
        payer: The wallet paying for the swap
        output_mint: The token mint to buy
        input_amount: Amount of SOL/USDC to spend
        params: Raydium AMM V4 protocol parameters
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
    ensure_market_accounts(params)

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Determine if coin is input (WSOL/USDC)
    is_coin_in = params.coin_mint == WSOL_TOKEN_ACCOUNT or params.coin_mint == USDC_TOKEN_ACCOUNT

    # Calculate swap amount
    _, min_amount_out = compute_swap_amount(
        params.coin_reserve,
        params.pc_reserve,
        is_coin_in,
        input_amount,
        slippage_bps,
    )

    if fixed_output_amount is not None:
        minimum_amount_out = fixed_output_amount
    else:
        minimum_amount_out = min_amount_out

    # Determine input/output mints from the pool sides
    input_mint = params.coin_mint if is_coin_in else params.pc_mint
    expected_output_mint = params.pc_mint if is_coin_in else params.coin_mint
    _ensure_expected_mint("output_mint", output_mint, expected_output_mint)
    output_mint = expected_output_mint

    # Get user token accounts
    user_source_token_account = get_associated_token_address(payer, input_mint, TOKEN_PROGRAM)
    user_destination_token_account = get_associated_token_address(payer, output_mint, TOKEN_PROGRAM)

    # Handle WSOL if needed
    if create_input_ata and input_mint == WSOL_TOKEN_ACCOUNT:
        instructions.extend(handle_wsol(payer, input_amount))
    elif create_input_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, input_mint, TOKEN_PROGRAM
            )
        )

    # Create output ATA if needed
    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, TOKEN_PROGRAM
            )
        )

    # Build instruction data (1 byte discriminator + 8 bytes amount_in + 8 bytes amount_out/min_out)
    discriminator = (
        SWAP_BASE_OUT_DISCRIMINATOR
        if fixed_output_amount is not None
        else SWAP_BASE_IN_DISCRIMINATOR
    )
    data = discriminator + struct.pack("<QQ", input_amount, minimum_amount_out)

    # Build accounts list (18 accounts)
    # Note: Raydium AMM V4 has specific account ordering
    accounts = [
        AccountMeta(TOKEN_PROGRAM, False, False),  # token_program (readonly)
        AccountMeta(params.amm, False, True),  # amm (writable)
        AccountMeta(AUTHORITY, False, False),  # authority (readonly)
        AccountMeta(params.amm_open_orders, False, True),  # amm_open_orders
        AccountMeta(params.amm_target_orders, False, True),  # amm_target_orders
        AccountMeta(params.token_coin, False, True),  # pool_coin_token_account (writable)
        AccountMeta(params.token_pc, False, True),  # pool_pc_token_account (writable)
        AccountMeta(params.serum_program, False, False),  # serum_program
        AccountMeta(params.serum_market, False, True),  # serum_market
        AccountMeta(params.serum_bids, False, True),  # serum_bids
        AccountMeta(params.serum_asks, False, True),  # serum_asks
        AccountMeta(params.serum_event_queue, False, True),  # serum_event_queue
        AccountMeta(params.serum_coin_vault_account, False, True),  # serum_coin_vault_account
        AccountMeta(params.serum_pc_vault_account, False, True),  # serum_pc_vault_account
        AccountMeta(params.serum_vault_signer, False, False),  # serum_vault_signer
        AccountMeta(user_source_token_account, False, True),  # user_source_token_account (writable)
        AccountMeta(user_destination_token_account, False, True),  # user_destination_token_account (writable)
        AccountMeta(payer, True, False),  # user_source_owner (signer)
    ]

    instructions.append(Instruction(RAYDIUM_AMM_V4_PROGRAM_ID, data, accounts))

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
    params: RaydiumAmmV4Params,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = True,
    close_output_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    output_mint: Optional[Pubkey] = None,
) -> List[Instruction]:
    """
    Build Raydium AMM V4 sell instructions.

    Args:
        payer: The wallet paying for the swap
        input_mint: The token mint to sell
        input_amount: Amount of tokens to sell
        params: Raydium AMM V4 protocol parameters
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
    ensure_market_accounts(params)

    # Validate pool contains WSOL or USDC
    if not params.is_wsol and not params.is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")

    # Determine if pc is output (WSOL/USDC)
    # For sell: is_base_in = True means we're selling PC to get Coin
    # is_base_in = False means we're selling Coin to get PC
    is_pc_out = params.pc_mint == WSOL_TOKEN_ACCOUNT or params.pc_mint == USDC_TOKEN_ACCOUNT

    # Calculate swap amount using the same direction semantics as Rust.
    _, min_amount_out = compute_swap_amount(
        params.coin_reserve,
        params.pc_reserve,
        is_pc_out,
        input_amount,
        slippage_bps,
    )

    if fixed_output_amount is not None:
        minimum_amount_out = fixed_output_amount
    else:
        minimum_amount_out = min_amount_out

    # Determine input/output mints from the pool sides
    expected_input_mint = params.coin_mint if is_pc_out else params.pc_mint
    expected_output_mint = params.pc_mint if is_pc_out else params.coin_mint
    _ensure_expected_mint("input_mint", input_mint, expected_input_mint)
    if output_mint is not None:
        _ensure_expected_mint("output_mint", output_mint, expected_output_mint)
    input_mint = expected_input_mint
    output_mint = expected_output_mint

    # Get user token accounts
    user_source_token_account = get_associated_token_address(payer, input_mint, TOKEN_PROGRAM)
    user_destination_token_account = get_associated_token_address(payer, output_mint, TOKEN_PROGRAM)

    # Create output ATA if needed for receiving SOL/USDC
    if create_output_ata and output_mint == WSOL_TOKEN_ACCOUNT:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
            )
        )
    elif create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, TOKEN_PROGRAM
            )
        )

    # Build instruction data (1 byte discriminator + 8 bytes amount_in + 8 bytes amount_out/min_out)
    discriminator = (
        SWAP_BASE_OUT_DISCRIMINATOR
        if fixed_output_amount is not None
        else SWAP_BASE_IN_DISCRIMINATOR
    )
    data = discriminator + struct.pack("<QQ", input_amount, minimum_amount_out)

    # Build accounts list (18 accounts)
    accounts = [
        AccountMeta(TOKEN_PROGRAM, False, False),  # token_program (readonly)
        AccountMeta(params.amm, False, True),  # amm (writable)
        AccountMeta(AUTHORITY, False, False),  # authority (readonly)
        AccountMeta(params.amm_open_orders, False, True),  # amm_open_orders
        AccountMeta(params.amm_target_orders, False, True),  # amm_target_orders
        AccountMeta(params.token_coin, False, True),  # pool_coin_token_account (writable)
        AccountMeta(params.token_pc, False, True),  # pool_pc_token_account (writable)
        AccountMeta(params.serum_program, False, False),  # serum_program
        AccountMeta(params.serum_market, False, True),  # serum_market
        AccountMeta(params.serum_bids, False, True),  # serum_bids
        AccountMeta(params.serum_asks, False, True),  # serum_asks
        AccountMeta(params.serum_event_queue, False, True),  # serum_event_queue
        AccountMeta(params.serum_coin_vault_account, False, True),  # serum_coin_vault_account
        AccountMeta(params.serum_pc_vault_account, False, True),  # serum_pc_vault_account
        AccountMeta(params.serum_vault_signer, False, False),  # serum_vault_signer
        AccountMeta(user_source_token_account, False, True),  # user_source_token_account (writable)
        AccountMeta(user_destination_token_account, False, True),  # user_destination_token_account (writable)
        AccountMeta(payer, True, False),  # user_source_owner (signer)
    ]

    instructions.append(Instruction(RAYDIUM_AMM_V4_PROGRAM_ID, data, accounts))

    # Close WSOL ATA if requested
    if close_output_ata and output_mint == WSOL_TOKEN_ACCOUNT:
        instructions.extend(close_wsol(payer))

    # Close token ATA if requested
    if close_input_ata:
        instructions.append(
            close_token_account_instruction(
                TOKEN_PROGRAM,
                user_source_token_account,
                payer,
                payer,
            )
        )

    return instructions


# ===== AMM Info Decoder - from Rust: src/instruction/utils/raydium_amm_v4_types.rs =====

AMM_INFO_SIZE = 752


@dataclass
class RaydiumAmmFees:
    """Fee structure for Raydium AMM"""
    min_separate_numerator: int
    min_separate_denominator: int
    trade_fee_numerator: int
    trade_fee_denominator: int
    pnl_numerator: int
    pnl_denominator: int
    swap_fee_numerator: int
    swap_fee_denominator: int


@dataclass
class RaydiumAmmOutputData:
    """Output data structure for Raydium AMM"""
    need_take_pnl_coin: int
    need_take_pnl_pc: int
    total_pnl_pc: int
    total_pnl_coin: int
    pool_open_time: int
    punish_pc_amount: int
    punish_coin_amount: int
    orderbook_to_init_time: int
    swap_coin_in_amount: int
    swap_pc_out_amount: int
    swap_take_pc_fee: int
    swap_pc_in_amount: int
    swap_coin_out_amount: int
    swap_take_coin_fee: int


@dataclass
class RaydiumAmmInfo:
    """Decoded Raydium AMM v4 info - matches Rust: src/instruction/utils/raydium_amm_v4_types.rs AmmInfo"""
    status: int
    nonce: int
    order_num: int
    depth: int
    coin_decimals: int
    pc_decimals: int
    state: int
    reset_flag: int
    min_size: int
    vol_max_cut_ratio: int
    amount_wave: int
    coin_lot_size: int
    pc_lot_size: int
    min_price_multiplier: int
    max_price_multiplier: int
    sys_decimal_value: int
    fees: RaydiumAmmFees
    output: RaydiumAmmOutputData
    token_coin: Pubkey
    token_pc: Pubkey
    coin_mint: Pubkey
    pc_mint: Pubkey
    lp_mint: Pubkey
    open_orders: Pubkey
    market: Pubkey
    serum_dex: Pubkey
    target_orders: Pubkey
    withdraw_queue: Pubkey
    token_temp_lp: Pubkey
    amm_owner: Pubkey
    lp_amount: int
    client_order_id: int


def decode_amm_info(data: bytes) -> RaydiumAmmInfo | None:
    """
    Decode Raydium AMM v4 info from account data.
    100% from Rust: src/instruction/utils/raydium_amm_v4_types.rs amm_info_decode

    Args:
        data: Raw account data (should be at least 752 bytes)

    Returns:
        RaydiumAmmInfo if successful, None if data is invalid
    """
    if len(data) < AMM_INFO_SIZE:
        return None

    try:
        offset = 0

        def read_u64():
            nonlocal offset
            val = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            return val

        # status: u64
        status = read_u64()
        # nonce: u64
        nonce = read_u64()
        # order_num: u64
        order_num = read_u64()
        # depth: u64
        depth = read_u64()
        # coin_decimals: u64
        coin_decimals = read_u64()
        # pc_decimals: u64
        pc_decimals = read_u64()
        # state: u64
        state = read_u64()
        # reset_flag: u64
        reset_flag = read_u64()
        # min_size: u64
        min_size = read_u64()
        # vol_max_cut_ratio: u64
        vol_max_cut_ratio = read_u64()
        # amount_wave: u64
        amount_wave = read_u64()
        # coin_lot_size: u64
        coin_lot_size = read_u64()
        # pc_lot_size: u64
        pc_lot_size = read_u64()
        # min_price_multiplier: u64
        min_price_multiplier = read_u64()
        # max_price_multiplier: u64
        max_price_multiplier = read_u64()
        # sys_decimal_value: u64
        sys_decimal_value = read_u64()

        # fees: Fees (8 * u64)
        fees = RaydiumAmmFees(
            min_separate_numerator=read_u64(),
            min_separate_denominator=read_u64(),
            trade_fee_numerator=read_u64(),
            trade_fee_denominator=read_u64(),
            pnl_numerator=read_u64(),
            pnl_denominator=read_u64(),
            swap_fee_numerator=read_u64(),
            swap_fee_denominator=read_u64(),
        )

        # output: OutPutData
        output = RaydiumAmmOutputData(
            need_take_pnl_coin=read_u64(),
            need_take_pnl_pc=read_u64(),
            total_pnl_pc=read_u64(),
            total_pnl_coin=read_u64(),
            pool_open_time=read_u64(),
            punish_pc_amount=read_u64(),
            punish_coin_amount=read_u64(),
            orderbook_to_init_time=read_u64(),
            swap_coin_in_amount=read_u64(),
            swap_pc_out_amount=read_u64(),
            swap_take_pc_fee=read_u64(),
            swap_pc_in_amount=read_u64(),
            swap_coin_out_amount=read_u64(),
            swap_take_coin_fee=read_u64(),
        )

        # token_coin: Pubkey
        token_coin = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token_pc: Pubkey
        token_pc = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # coin_mint: Pubkey
        coin_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # pc_mint: Pubkey
        pc_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # lp_mint: Pubkey
        lp_mint = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # open_orders: Pubkey
        open_orders = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # market: Pubkey
        market = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # serum_dex: Pubkey
        serum_dex = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # target_orders: Pubkey
        target_orders = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # withdraw_queue: Pubkey
        withdraw_queue = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # token_temp_lp: Pubkey
        token_temp_lp = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # amm_owner: Pubkey
        amm_owner = Pubkey.from_bytes(data[offset:offset + 32])
        offset += 32

        # lp_amount: u64
        lp_amount = read_u64()

        # client_order_id: u64
        client_order_id = read_u64()

        return RaydiumAmmInfo(
            status=status,
            nonce=nonce,
            order_num=order_num,
            depth=depth,
            coin_decimals=coin_decimals,
            pc_decimals=pc_decimals,
            state=state,
            reset_flag=reset_flag,
            min_size=min_size,
            vol_max_cut_ratio=vol_max_cut_ratio,
            amount_wave=amount_wave,
            coin_lot_size=coin_lot_size,
            pc_lot_size=pc_lot_size,
            min_price_multiplier=min_price_multiplier,
            max_price_multiplier=max_price_multiplier,
            sys_decimal_value=sys_decimal_value,
            fees=fees,
            output=output,
            token_coin=token_coin,
            token_pc=token_pc,
            coin_mint=coin_mint,
            pc_mint=pc_mint,
            lp_mint=lp_mint,
            open_orders=open_orders,
            market=market,
            serum_dex=serum_dex,
            target_orders=target_orders,
            withdraw_queue=withdraw_queue,
            token_temp_lp=token_temp_lp,
            amm_owner=amm_owner,
            lp_amount=lp_amount,
            client_order_id=client_order_id,
        )
    except Exception:
        return None


# ===== Async Fetch Functions - from Rust: src/instruction/utils/raydium_amm_v4.rs =====

from typing import Protocol, runtime_checkable


@runtime_checkable
class AmmInfoFetcher(Protocol):
    """Protocol for fetching AMM info from RPC"""
    async def get_account_info(self, pubkey: Pubkey) -> bytes | None:
        ...


async def fetch_amm_info(
    fetcher: AmmInfoFetcher,
    amm: Pubkey
) -> RaydiumAmmInfo | None:
    """
    Fetch AMM info from RPC.
    100% from Rust: src/instruction/utils/raydium_amm_v4.rs fetch_amm_info

    Args:
        fetcher: Object implementing AmmInfoFetcher protocol
        amm: The AMM account address

    Returns:
        RaydiumAmmInfo if successful, None if not found or invalid
    """
    data = await fetcher.get_account_info(amm)
    if data is None:
        return None
    return decode_amm_info(data)


# ============================================
# Exports
# ============================================

__all__ = [
    # Program IDs and Constants
    "RAYDIUM_AMM_V4_PROGRAM_ID",
    "AUTHORITY",
    "TRADE_FEE_NUMERATOR",
    "TRADE_FEE_DENOMINATOR",
    "SWAP_FEE_NUMERATOR",
    "SWAP_FEE_DENOMINATOR",
    # Discriminators
    "SWAP_BASE_IN_DISCRIMINATOR",
    "SWAP_BASE_OUT_DISCRIMINATOR",
    # Params
    "RaydiumAmmV4Params",
    # Calculation Functions
    "compute_swap_amount",
    # Instruction Builders
    "build_buy_instructions",
    "build_sell_instructions",
    # AMM Info Decoder
    "AMM_INFO_SIZE",
    "RaydiumAmmFees",
    "RaydiumAmmOutputData",
    "RaydiumAmmInfo",
    "decode_amm_info",
]
