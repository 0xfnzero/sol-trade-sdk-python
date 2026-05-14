"""
PumpFun instruction builder for Solana trading SDK.
Production-grade implementation with all constants, discriminators, and PDA derivation functions.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
import struct
import random

from .common import (
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
    TOKEN_PROGRAM_2022,
    ASSOCIATED_TOKEN_PROGRAM,
    WSOL_TOKEN_ACCOUNT,
    DEFAULT_SLIPPAGE,
    get_associated_token_address,
    create_associated_token_account_idempotent_instruction,
    handle_wsol,
    close_wsol,
    close_token_account_instruction,
    calculate_with_slippage_buy,
    calculate_with_slippage_sell,
)

# ============================================
# PumpFun Program ID
# ============================================

PUMPFUN_PROGRAM_ID: Pubkey = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")

# ============================================
# PumpFun Constants
# ============================================

# Fee Recipient
FEE_RECIPIENT: Pubkey = Pubkey.from_string("62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV")

# Global Account
GLOBAL_ACCOUNT: Pubkey = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")

# Event Authority
EVENT_AUTHORITY: Pubkey = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

# Authority
AUTHORITY: Pubkey = Pubkey.from_string("FFWtrEQ4B4PKQoVuHYzZq8FabGkVatYzDpEVHsK5rrhF")

# Fee Program
FEE_PROGRAM: Pubkey = Pubkey.from_string("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")

# Global Volume Accumulator
GLOBAL_VOLUME_ACCUMULATOR: Pubkey = Pubkey.from_string("Hq2wp8uJ9jCPsYgNHex8RtqdvMPfVGoYwjvF1ATiwn2Y")

# Fee Config
FEE_CONFIG: Pubkey = Pubkey.from_string("8Wf5TiAheLUqBrKXeYg2JtAFFMWtKdG2BSFgqUcPVwTt")

# Mayhem Fee Recipients (use any one randomly)
MAYHEM_FEE_RECIPIENTS: List[Pubkey] = [
    Pubkey.from_string("GesfTA3X2arioaHp8bbKdjG9vJtskViWACZoYvxp4twS"),
    Pubkey.from_string("4budycTjhs9fD6xw62VBducVTNgMgJJ5BgtKq7mAZwn6"),
    Pubkey.from_string("8SBKzEQU4nLSzcwF4a74F2iaUDQyTfjGndn6qUWBnrpR"),
    Pubkey.from_string("4UQeTP1T39KZ9Sfxzo3WR5skgsaP6NZa87BAkuazLEKH"),
    Pubkey.from_string("8sNeir4QsLsJdYpc9RZacohhK1Y5FLU3nC5LXgYB4aa6"),
    Pubkey.from_string("Fh9HmeLNUMVCvejxCtCL2DbYaRyBFVJ5xrWkLnMH6fdk"),
    Pubkey.from_string("463MEnMeGyJekNZFQSTUABBEbLnvMTALbT6ZmsxAbAdq"),
    Pubkey.from_string("6AUH3WEHucYZyC61hqpqYUWVto5qA5hjHuNQ32GNnNxA"),
]

# Apr 2026 program upgrade: one recipient after bonding-curve-v2 (writable)
PROTOCOL_EXTRA_FEE_RECIPIENTS: List[Pubkey] = [
    Pubkey.from_string("5YxQFdt3Tr9zJLvkFccqXVUwhdTWJQc1fFg2YPbxvxeD"),
    Pubkey.from_string("9M4giFFMxmFGXtc3feFzRai56WbBqehoSeRE5GK7gf7"),
    Pubkey.from_string("GXPFM2caqTtQYC2cJ5yJRi9VDkpsYZXzYdwYpGnLmtDL"),
    Pubkey.from_string("3BpXnfJaUTiwXnJNe7Ej1rcbzqTTQUvLShZaWazebsVR"),
    Pubkey.from_string("5cjcW9wExnJJiqgLjq7DEG75Pm6JBgE1hNv4B2vHXUW6"),
    Pubkey.from_string("EHAAiTxcdDwQ3U4bU6YcMsQGaekdzLS3B5SmYo46kJtL"),
    Pubkey.from_string("5eHhjP8JaYkz83CWwvGU2uMUXefd3AazWGx4gpcuEEYD"),
    Pubkey.from_string("A7hAgCzFw14fejgCp387JUJRMNyz4j89JKnhtKU8piqW"),
]

BUYBACK_FEE_RECIPIENTS: List[Pubkey] = PROTOCOL_EXTRA_FEE_RECIPIENTS

# ============================================
# Instruction Discriminators
# ============================================

BUY_DISCRIMINATOR: bytes = bytes([102, 6, 61, 18, 1, 218, 235, 234])
BUY_EXACT_SOL_IN_DISCRIMINATOR: bytes = bytes([56, 252, 116, 8, 158, 223, 205, 95])
SELL_DISCRIMINATOR: bytes = bytes([51, 230, 133, 164, 1, 127, 131, 173])
BUY_V2_DISCRIMINATOR: bytes = bytes([184, 23, 238, 97, 103, 197, 211, 61])
SELL_V2_DISCRIMINATOR: bytes = bytes([93, 246, 130, 60, 231, 233, 64, 178])
BUY_EXACT_QUOTE_IN_V2_DISCRIMINATOR: bytes = bytes([194, 171, 28, 70, 104, 77, 91, 47])
CLAIM_CASHBACK_DISCRIMINATOR: bytes = bytes([37, 58, 35, 126, 190, 53, 228, 197])

# ============================================
# Seeds
# ============================================

BONDING_CURVE_SEED = b"bonding-curve"
BONDING_CURVE_V2_SEED = b"bonding-curve-v2"
CREATOR_VAULT_SEED = b"creator-vault"
USER_VOLUME_ACCUMULATOR_SEED = b"user_volume_accumulator"
GLOBAL_VOLUME_ACCUMULATOR_SEED = b"global_volume_accumulator"
FEE_CONFIG_SEED = b"fee_config"
SHARING_CONFIG_SEED = b"sharing-config"
DEFAULT_PUBKEY = Pubkey.from_string("11111111111111111111111111111111")
PHANTOM_DEFAULT_CREATOR_VAULT = Pubkey.from_string("2DR3iqRPVThyRLVJnwjPW1qiGWrp8RUFfHVjMbZyhdNc")
FEE_BASIS_POINTS = 95
CREATOR_FEE_BASIS_POINTS = 30

# ============================================
# PDA Derivation Functions
# ============================================

def get_bonding_curve_pda(mint: Pubkey) -> Pubkey:
    """
    Derive the bonding curve PDA for a given mint.
    Seeds: ["bonding-curve", mint]
    """
    seeds = [BONDING_CURVE_SEED, bytes(mint)]
    (pda, _) = Pubkey.find_program_address(seeds, PUMPFUN_PROGRAM_ID)
    return pda


def get_bonding_curve_v2_pda(mint: Pubkey) -> Pubkey:
    """
    Derive the bonding curve v2 PDA for a given mint.
    Seeds: ["bonding-curve-v2", mint]
    """
    seeds = [BONDING_CURVE_V2_SEED, bytes(mint)]
    (pda, _) = Pubkey.find_program_address(seeds, PUMPFUN_PROGRAM_ID)
    return pda


def get_creator_vault_pda(creator: Pubkey) -> Pubkey:
    """
    Derive the creator vault PDA for a given creator.
    Seeds: ["creator-vault", creator]
    """
    seeds = [CREATOR_VAULT_SEED, bytes(creator)]
    (pda, _) = Pubkey.find_program_address(seeds, PUMPFUN_PROGRAM_ID)
    return pda


def get_user_volume_accumulator_pda(user: Pubkey) -> Pubkey:
    """
    Derive the user volume accumulator PDA for a given user.
    Seeds: ["user_volume_accumulator", user]
    """
    seeds = [USER_VOLUME_ACCUMULATOR_SEED, bytes(user)]
    (pda, _) = Pubkey.find_program_address(seeds, PUMPFUN_PROGRAM_ID)
    return pda


def get_fee_sharing_config_pda(mint: Pubkey) -> Pubkey:
    """Derive the fee sharing config PDA under the Pump.fun fee program."""
    seeds = [SHARING_CONFIG_SEED, bytes(mint)]
    (pda, _) = Pubkey.find_program_address(seeds, FEE_PROGRAM)
    return pda


def get_creator(creator_vault_pda: Pubkey) -> Pubkey:
    """
    Get the creator pubkey from the creator vault PDA.
    Returns default pubkey if creator_vault_pda is default.
    """
    if creator_vault_pda == DEFAULT_PUBKEY:
        return DEFAULT_PUBKEY
    return creator_vault_pda


def get_mayhem_fee_recipient_random() -> Pubkey:
    """
    Get a random Mayhem fee recipient.
    """
    return random.choice(MAYHEM_FEE_RECIPIENTS)


def get_protocol_extra_fee_recipient_random() -> Pubkey:
    """Random protocol extra fee recipient (after bonding-curve-v2, writable)."""
    return random.choice(PROTOCOL_EXTRA_FEE_RECIPIENTS)


def get_buyback_fee_recipient_random() -> Pubkey:
    """Random PumpFun V2 buyback fee recipient."""
    return random.choice(BUYBACK_FEE_RECIPIENTS)


def _is_usable_pubkey(value: Optional[Pubkey]) -> bool:
    return value is not None and value != DEFAULT_PUBKEY and value != PHANTOM_DEFAULT_CREATOR_VAULT


def _pump_fun_fee_recipient(params: "PumpFunParams") -> Pubkey:
    if _is_usable_pubkey(params.fee_recipient):
        return params.fee_recipient
    return get_mayhem_fee_recipient_random() if params.is_mayhem_mode else FEE_RECIPIENT


def _effective_creator_for_trade(params: "PumpFunParams") -> Pubkey:
    if _is_usable_pubkey(params.observed_trade_creator):
        return params.observed_trade_creator
    if _is_usable_pubkey(params.creator):
        return params.creator
    return DEFAULT_PUBKEY


def _resolve_creator_vault_for_ix(params: "PumpFunParams", mint: Pubkey) -> Pubkey:
    if _is_usable_pubkey(params.creator_vault):
        return params.creator_vault
    if _is_usable_pubkey(params.fee_sharing_creator_vault_if_active):
        return params.fee_sharing_creator_vault_if_active
    creator = _effective_creator_for_trade(params)
    if _is_usable_pubkey(creator):
        return get_creator_vault_pda(creator)
    raise ValueError(f"creator_vault PDA derivation failed for mint {mint}")


def _resolve_creator_vault_for_sell_v2(params: "PumpFunParams", mint: Pubkey) -> Pubkey:
    if _is_usable_pubkey(params.creator_vault):
        return params.creator_vault
    if _is_usable_pubkey(params.fee_sharing_creator_vault_if_active):
        return params.fee_sharing_creator_vault_if_active
    if _is_usable_pubkey(params.creator):
        return get_creator_vault_pda(params.creator)
    raise ValueError(f"creator_vault PDA derivation failed for sell_v2 mint {mint}")


def _effective_pump_mint_token_program(mint: Pubkey, params: "PumpFunParams") -> Pubkey:
    if str(mint).endswith("pump"):
        return TOKEN_PROGRAM_2022
    if _is_usable_pubkey(params.token_program):
        return params.token_program
    return TOKEN_PROGRAM_2022


def _effective_quote_mint(params: "PumpFunParams") -> Pubkey:
    return params.quote_mint if _is_usable_pubkey(params.quote_mint) else WSOL_TOKEN_ACCOUNT


# ============================================
# PumpFun Parameters Dataclass
# ============================================

@dataclass
class PumpFunParams:
    """Parameters for PumpFun protocol trading."""
    bonding_curve_account: Optional[Pubkey] = None  # If None, will derive from mint
    virtual_token_reserves: int = 0
    virtual_sol_reserves: int = 0
    real_token_reserves: int = 0
    real_sol_reserves: int = 0
    token_total_supply: int = 0
    complete: bool = False
    creator: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    associated_bonding_curve: Optional[Pubkey] = None
    creator_vault: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    fee_sharing_creator_vault_if_active: Optional[Pubkey] = None
    observed_trade_creator: Optional[Pubkey] = None
    token_program: Pubkey = TOKEN_PROGRAM_2022
    close_token_account_when_sell: bool = False
    fee_recipient: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    quote_mint: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
    use_v2_ix: bool = False


# ============================================
# PumpFun Calculation Functions
# ============================================

def get_buy_token_amount_from_sol_amount(
    virtual_token_reserves: int,
    virtual_sol_reserves: int,
    real_token_reserves: int,
    creator: Pubkey,
    sol_amount: int,
) -> int:
    """
    Calculate the token amount received for a given SOL amount on PumpFun.
    Uses the bonding curve formula.
    """
    if sol_amount == 0 or virtual_token_reserves == 0:
        return 0

    total_fee_bps = FEE_BASIS_POINTS + (
        CREATOR_FEE_BASIS_POINTS if _is_usable_pubkey(creator) else 0
    )
    input_amount = (sol_amount * 10_000) // (total_fee_bps + 10_000)
    denominator = virtual_sol_reserves + input_amount
    if denominator == 0:
        return 0

    tokens_received = (input_amount * virtual_token_reserves) // denominator
    tokens_received = min(tokens_received, real_token_reserves)

    if tokens_received <= 100 * 1_000_000:
        tokens_received = 25_547_619 * 1_000_000 if sol_amount > 10_000_000 else 255_476 * 1_000_000

    return tokens_received


def get_sell_sol_amount_from_token_amount(
    virtual_token_reserves: int,
    virtual_sol_reserves: int,
    creator: Pubkey,
    token_amount: int,
) -> int:
    """
    Calculate the SOL amount received for a given token amount on PumpFun.
    """
    if token_amount == 0 or virtual_token_reserves == 0:
        return 0

    sol_cost = (token_amount * virtual_sol_reserves) // (virtual_token_reserves + token_amount)
    total_fee_bps = FEE_BASIS_POINTS + (
        CREATOR_FEE_BASIS_POINTS if _is_usable_pubkey(creator) else 0
    )
    fee = (sol_cost * total_fee_bps + 9_999) // 10_000
    return max(sol_cost - fee, 0)


# ============================================
# Build Buy Instructions
# ============================================

def build_buy_instructions(
    payer: Pubkey,
    output_mint: Pubkey,
    input_amount: int,
    params: PumpFunParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = True,
    create_input_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    use_exact_sol_amount: bool = True,
    use_pumpfun_v2: bool = False,
) -> List[Instruction]:
    """
    Build PumpFun buy instructions.

    Args:
        payer: The wallet paying for the swap
        output_mint: The token mint to buy
        input_amount: Amount of SOL to spend
        params: PumpFun protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_output_ata: Whether to create output token ATA if needed
        close_input_ata: Whether to close WSOL ATA after swap
        fixed_output_amount: If set, use this as exact output amount
        use_exact_sol_amount: If True, use buy_exact_sol_in instruction

    Returns:
        List of instructions for the buy operation
    """
    if use_pumpfun_v2 or params.use_v2_ix or _is_usable_pubkey(params.quote_mint):
        return build_buy_v2_instructions(
            payer=payer,
            output_mint=output_mint,
            input_amount=input_amount,
            params=params,
            slippage_bps=slippage_bps,
            create_output_ata=create_output_ata,
            create_input_ata=create_input_ata,
            fixed_output_amount=fixed_output_amount,
            use_exact_sol_amount=use_exact_sol_amount,
        )

    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Get bonding curve address
    bonding_curve_addr = params.bonding_curve_account
    if bonding_curve_addr is None:
        bonding_curve_addr = get_bonding_curve_pda(output_mint)

    creator = _effective_creator_for_trade(params)
    try:
        creator_vault_account = _resolve_creator_vault_for_ix(params, output_mint)
    except ValueError:
        creator_vault_account = params.creator_vault

    # Calculate token amount
    if fixed_output_amount is not None:
        buy_token_amount = fixed_output_amount
    else:
        buy_token_amount = get_buy_token_amount_from_sol_amount(
            params.virtual_token_reserves,
            params.virtual_sol_reserves,
            params.real_token_reserves,
            creator,
            input_amount,
        )

    # Calculate max SOL cost with slippage
    max_sol_cost = calculate_with_slippage_buy(input_amount, slippage_bps)

    # Get associated bonding curve
    associated_bonding_curve = params.associated_bonding_curve
    if associated_bonding_curve is None:
        associated_bonding_curve = get_associated_token_address(
            bonding_curve_addr, output_mint, _effective_pump_mint_token_program(output_mint, params)
        )

    # Get user token account
    user_token_account = get_associated_token_address(
        payer, output_mint, _effective_pump_mint_token_program(output_mint, params)
    )

    token_program = _effective_pump_mint_token_program(output_mint, params)

    # Create ATA if needed
    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, token_program
            )
        )

    # Get user volume accumulator
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)

    # Get bonding curve v2
    bonding_curve_v2 = get_bonding_curve_v2_pda(output_mint)

    fee_recipient = _pump_fun_fee_recipient(params)

    # Build instruction data
    track_volume = bytes([1, 1]) if params.is_cashback_coin else bytes([1, 0])

    if use_exact_sol_amount:
        # buy_exact_sol_in(spendable_sol_in: u64, min_tokens_out: u64, track_volume)
        min_tokens_out = calculate_with_slippage_sell(buy_token_amount, slippage_bps)
        data = BUY_EXACT_SOL_IN_DISCRIMINATOR + struct.pack("<QQ", input_amount, min_tokens_out) + track_volume
    else:
        # buy(token_amount: u64, max_sol_cost: u64, track_volume)
        data = BUY_DISCRIMINATOR + struct.pack("<QQ", buy_token_amount, max_sol_cost) + track_volume

    # Build accounts list
    accounts = [
        AccountMeta(GLOBAL_ACCOUNT, False, False),  # global
        AccountMeta(fee_recipient, False, True),  # fee_recipient (writable)
        AccountMeta(output_mint, False, False),  # mint (readonly)
        AccountMeta(bonding_curve_addr, False, True),  # bonding_curve (writable)
        AccountMeta(associated_bonding_curve, False, True),  # associated_bonding_curve (writable)
        AccountMeta(user_token_account, False, True),  # user_token_account (writable)
        AccountMeta(payer, True, True),  # user (signer, writable)
        AccountMeta(SYSTEM_PROGRAM, False, False),  # system_program
        AccountMeta(token_program, False, False),  # token_program
        AccountMeta(creator_vault_account, False, True),  # creator_vault (writable)
        AccountMeta(EVENT_AUTHORITY, False, False),  # event_authority
        AccountMeta(PUMPFUN_PROGRAM_ID, False, False),  # program
        AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True),  # global_volume_accumulator (writable)
        AccountMeta(user_volume_accumulator, False, True),  # user_volume_accumulator (writable)
        AccountMeta(FEE_CONFIG, False, False),  # fee_config
        AccountMeta(FEE_PROGRAM, False, False),  # fee_program
        AccountMeta(bonding_curve_v2, False, False),  # bonding_curve_v2 (readonly, remaining account)
        AccountMeta(get_protocol_extra_fee_recipient_random(), False, True),
    ]

    instructions.append(Instruction(PUMPFUN_PROGRAM_ID, data, accounts))

    return instructions


# ============================================
# Build Sell Instructions
# ============================================

def build_sell_instructions(
    payer: Pubkey,
    input_mint: Pubkey,
    input_amount: int,
    params: PumpFunParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = False,
    close_output_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    use_pumpfun_v2: bool = False,
) -> List[Instruction]:
    """
    Build PumpFun sell instructions.

    Args:
        payer: The wallet paying for the swap
        input_mint: The token mint to sell
        input_amount: Amount of tokens to sell
        params: PumpFun protocol parameters
        slippage_bps: Slippage tolerance in basis points
        create_output_ata: Whether to create WSOL ATA for receiving SOL
        close_output_ata: Whether to close WSOL ATA after swap
        close_input_ata: Whether to close token ATA after swap
        fixed_output_amount: If set, use this as exact output amount

    Returns:
        List of instructions for the sell operation
    """
    if use_pumpfun_v2 or params.use_v2_ix or _is_usable_pubkey(params.quote_mint):
        return build_sell_v2_instructions(
            payer=payer,
            input_mint=input_mint,
            input_amount=input_amount,
            params=params,
            slippage_bps=slippage_bps,
            create_output_ata=create_output_ata,
            close_input_ata=close_input_ata,
            fixed_output_amount=fixed_output_amount,
        )

    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions = []

    # Get bonding curve address
    bonding_curve_addr = params.bonding_curve_account
    if bonding_curve_addr is None:
        bonding_curve_addr = get_bonding_curve_pda(input_mint)

    creator = _effective_creator_for_trade(params)
    try:
        creator_vault_account = _resolve_creator_vault_for_ix(params, input_mint)
    except ValueError:
        creator_vault_account = params.creator_vault
    token_program = _effective_pump_mint_token_program(input_mint, params)

    # Calculate SOL amount
    sol_amount = get_sell_sol_amount_from_token_amount(
        params.virtual_token_reserves,
        params.virtual_sol_reserves,
        creator,
        input_amount,
    )

    # Calculate min SOL output with slippage
    if fixed_output_amount is not None:
        min_sol_output = fixed_output_amount
    else:
        min_sol_output = calculate_with_slippage_sell(sol_amount, slippage_bps)

    # Get associated bonding curve
    associated_bonding_curve = params.associated_bonding_curve
    if associated_bonding_curve is None:
        associated_bonding_curve = get_associated_token_address(
            bonding_curve_addr, input_mint, token_program
        )

    # Get user token account
    user_token_account = get_associated_token_address(
        payer, input_mint, token_program
    )

    # Create WSOL ATA if needed for receiving SOL
    if create_output_ata or close_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
            )
        )

    fee_recipient = _pump_fun_fee_recipient(params)

    # Build instruction data
    data = SELL_DISCRIMINATOR + struct.pack("<QQ", input_amount, min_sol_output)

    # Build accounts list
    accounts = [
        AccountMeta(GLOBAL_ACCOUNT, False, False),  # global
        AccountMeta(fee_recipient, False, True),  # fee_recipient (writable)
        AccountMeta(input_mint, False, False),  # mint (readonly)
        AccountMeta(bonding_curve_addr, False, True),  # bonding_curve (writable)
        AccountMeta(associated_bonding_curve, False, True),  # associated_bonding_curve (writable)
        AccountMeta(user_token_account, False, True),  # user_token_account (writable)
        AccountMeta(payer, True, True),  # user (signer, writable)
        AccountMeta(SYSTEM_PROGRAM, False, False),  # system_program
        AccountMeta(creator_vault_account, False, True),  # creator_vault (writable)
        AccountMeta(token_program, False, False),  # token_program
        AccountMeta(EVENT_AUTHORITY, False, False),  # event_authority
        AccountMeta(PUMPFUN_PROGRAM_ID, False, False),  # program
        AccountMeta(FEE_CONFIG, False, False),  # fee_config
        AccountMeta(FEE_PROGRAM, False, False),  # fee_program
    ]

    # Cashback: Add user_volume_accumulator if cashback coin
    if params.is_cashback_coin:
        user_volume_accumulator = get_user_volume_accumulator_pda(payer)
        accounts.append(AccountMeta(user_volume_accumulator, False, True))

    # Add bonding_curve_v2 at the end (remaining account)
    bonding_curve_v2 = get_bonding_curve_v2_pda(input_mint)
    accounts.append(AccountMeta(bonding_curve_v2, False, False))
    accounts.append(AccountMeta(get_protocol_extra_fee_recipient_random(), False, True))

    instructions.append(Instruction(PUMPFUN_PROGRAM_ID, data, accounts))

    # Close WSOL ATA if requested
    if close_output_ata:
        instructions.extend(close_wsol(payer))

    # Close token ATA if requested
    if close_input_ata or params.close_token_account_when_sell:
        instructions.append(
            close_token_account_instruction(
                token_program,
                user_token_account,
                payer,
                payer,
            )
        )

    return instructions


def build_buy_v2_instructions(
    payer: Pubkey,
    output_mint: Pubkey,
    input_amount: int,
    params: PumpFunParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = True,
    create_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
    use_exact_sol_amount: bool = True,
) -> List[Instruction]:
    """Build PumpFun V2 buy instructions."""
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions: List[Instruction] = []
    bonding_curve_addr = params.bonding_curve_account or get_bonding_curve_pda(output_mint)
    creator = _effective_creator_for_trade(params)
    creator_vault_account = _resolve_creator_vault_for_ix(params, output_mint)
    base_token_program = _effective_pump_mint_token_program(output_mint, params)
    quote_mint = _effective_quote_mint(params)
    quote_token_program = TOKEN_PROGRAM

    associated_base_bonding_curve = get_associated_token_address(
        bonding_curve_addr, output_mint, base_token_program
    )
    associated_base_user = get_associated_token_address(payer, output_mint, base_token_program)
    fee_recipient = _pump_fun_fee_recipient(params)
    buyback_fee_recipient = get_buyback_fee_recipient_random()
    associated_quote_fee_recipient = get_associated_token_address(
        fee_recipient, quote_mint, quote_token_program
    )
    associated_quote_buyback_fee_recipient = get_associated_token_address(
        buyback_fee_recipient, quote_mint, quote_token_program
    )
    associated_quote_bonding_curve = get_associated_token_address(
        bonding_curve_addr, quote_mint, quote_token_program
    )
    associated_quote_user = get_associated_token_address(payer, quote_mint, quote_token_program)
    associated_creator_vault = get_associated_token_address(
        creator_vault_account, quote_mint, quote_token_program
    )
    sharing_config = get_fee_sharing_config_pda(output_mint)
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)
    associated_user_volume_accumulator = get_associated_token_address(
        user_volume_accumulator, quote_mint, quote_token_program
    )

    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, output_mint, base_token_program
            )
        )

    if create_input_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, quote_mint, quote_token_program
            )
        )

    buy_token_amount = (
        fixed_output_amount
        if fixed_output_amount is not None
        else get_buy_token_amount_from_sol_amount(
            params.virtual_token_reserves,
            params.virtual_sol_reserves,
            params.real_token_reserves,
            creator,
            input_amount,
        )
    )
    max_sol_cost = calculate_with_slippage_buy(input_amount, slippage_bps)
    if use_exact_sol_amount:
        min_tokens_out = (
            fixed_output_amount
            if fixed_output_amount is not None
            else calculate_with_slippage_sell(buy_token_amount, slippage_bps)
        )
        data = BUY_EXACT_QUOTE_IN_V2_DISCRIMINATOR + struct.pack("<QQ", input_amount, min_tokens_out)
    else:
        data = BUY_V2_DISCRIMINATOR + struct.pack("<QQ", buy_token_amount, max_sol_cost)

    accounts = [
        AccountMeta(GLOBAL_ACCOUNT, False, False),
        AccountMeta(output_mint, False, False),
        AccountMeta(quote_mint, False, False),
        AccountMeta(base_token_program, False, False),
        AccountMeta(quote_token_program, False, False),
        AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
        AccountMeta(fee_recipient, False, True),
        AccountMeta(associated_quote_fee_recipient, False, True),
        AccountMeta(buyback_fee_recipient, False, False),
        AccountMeta(associated_quote_buyback_fee_recipient, False, True),
        AccountMeta(bonding_curve_addr, False, True),
        AccountMeta(associated_base_bonding_curve, False, True),
        AccountMeta(associated_quote_bonding_curve, False, True),
        AccountMeta(payer, True, True),
        AccountMeta(associated_base_user, False, True),
        AccountMeta(associated_quote_user, False, True),
        AccountMeta(creator_vault_account, False, True),
        AccountMeta(associated_creator_vault, False, True),
        AccountMeta(sharing_config, False, False),
        AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True),
        AccountMeta(user_volume_accumulator, False, True),
        AccountMeta(associated_user_volume_accumulator, False, True),
        AccountMeta(FEE_CONFIG, False, False),
        AccountMeta(FEE_PROGRAM, False, False),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPFUN_PROGRAM_ID, False, False),
    ]
    instructions.append(Instruction(PUMPFUN_PROGRAM_ID, data, accounts))
    return instructions


def build_sell_v2_instructions(
    payer: Pubkey,
    input_mint: Pubkey,
    input_amount: int,
    params: PumpFunParams,
    slippage_bps: int = DEFAULT_SLIPPAGE,
    create_output_ata: bool = False,
    close_input_ata: bool = False,
    fixed_output_amount: Optional[int] = None,
) -> List[Instruction]:
    """Build PumpFun V2 sell instructions."""
    if input_amount == 0:
        raise ValueError("Amount cannot be zero")

    instructions: List[Instruction] = []
    bonding_curve_addr = params.bonding_curve_account or get_bonding_curve_pda(input_mint)
    creator = _effective_creator_for_trade(params)
    creator_vault_account = _resolve_creator_vault_for_sell_v2(params, input_mint)
    base_token_program = _effective_pump_mint_token_program(input_mint, params)
    quote_mint = _effective_quote_mint(params)
    quote_token_program = TOKEN_PROGRAM

    associated_base_bonding_curve = get_associated_token_address(
        bonding_curve_addr, input_mint, base_token_program
    )
    associated_base_user = get_associated_token_address(payer, input_mint, base_token_program)
    fee_recipient = _pump_fun_fee_recipient(params)
    buyback_fee_recipient = get_buyback_fee_recipient_random()
    associated_quote_fee_recipient = get_associated_token_address(
        fee_recipient, quote_mint, quote_token_program
    )
    associated_quote_buyback_fee_recipient = get_associated_token_address(
        buyback_fee_recipient, quote_mint, quote_token_program
    )
    associated_quote_bonding_curve = get_associated_token_address(
        bonding_curve_addr, quote_mint, quote_token_program
    )
    associated_quote_user = get_associated_token_address(payer, quote_mint, quote_token_program)
    associated_creator_vault = get_associated_token_address(
        creator_vault_account, quote_mint, quote_token_program
    )
    sharing_config = get_fee_sharing_config_pda(input_mint)
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)
    associated_user_volume_accumulator = get_associated_token_address(
        user_volume_accumulator, quote_mint, quote_token_program
    )

    if create_output_ata:
        instructions.append(
            create_associated_token_account_idempotent_instruction(
                payer, payer, quote_mint, quote_token_program
            )
        )

    sol_amount = get_sell_sol_amount_from_token_amount(
        params.virtual_token_reserves,
        params.virtual_sol_reserves,
        creator,
        input_amount,
    )
    min_sol_output = (
        fixed_output_amount
        if fixed_output_amount is not None
        else calculate_with_slippage_sell(sol_amount, slippage_bps)
    )
    data = SELL_V2_DISCRIMINATOR + struct.pack("<QQ", input_amount, min_sol_output)

    accounts = [
        AccountMeta(GLOBAL_ACCOUNT, False, False),
        AccountMeta(input_mint, False, False),
        AccountMeta(quote_mint, False, False),
        AccountMeta(base_token_program, False, False),
        AccountMeta(quote_token_program, False, False),
        AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
        AccountMeta(fee_recipient, False, True),
        AccountMeta(associated_quote_fee_recipient, False, True),
        AccountMeta(buyback_fee_recipient, False, False),
        AccountMeta(associated_quote_buyback_fee_recipient, False, True),
        AccountMeta(bonding_curve_addr, False, True),
        AccountMeta(associated_base_bonding_curve, False, True),
        AccountMeta(associated_quote_bonding_curve, False, True),
        AccountMeta(payer, True, True),
        AccountMeta(associated_base_user, False, True),
        AccountMeta(associated_quote_user, False, True),
        AccountMeta(creator_vault_account, False, True),
        AccountMeta(associated_creator_vault, False, True),
        AccountMeta(sharing_config, False, False),
        AccountMeta(user_volume_accumulator, False, True),
        AccountMeta(associated_user_volume_accumulator, False, True),
        AccountMeta(FEE_CONFIG, False, False),
        AccountMeta(FEE_PROGRAM, False, False),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPFUN_PROGRAM_ID, False, False),
    ]
    instructions.append(Instruction(PUMPFUN_PROGRAM_ID, data, accounts))

    if close_input_ata or params.close_token_account_when_sell:
        instructions.append(
            close_token_account_instruction(
                base_token_program,
                associated_base_user,
                payer,
                payer,
            )
        )

    return instructions


# ============================================
# Claim Cashback Instruction
# ============================================

def claim_cashback_pumpfun_instruction(payer: Pubkey) -> Instruction:
    """
    Build instruction to claim cashback for PumpFun bonding curve.
    Transfers native lamports from UserVolumeAccumulator to user.
    """
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)

    accounts = [
        AccountMeta(payer, True, True),  # user (signer, writable)
        AccountMeta(user_volume_accumulator, False, True),  # user_volume_accumulator (writable)
        AccountMeta(SYSTEM_PROGRAM, False, False),  # system_program
        AccountMeta(EVENT_AUTHORITY, False, False),  # event_authority
        AccountMeta(PUMPFUN_PROGRAM_ID, False, False),  # program
    ]

    return Instruction(PUMPFUN_PROGRAM_ID, CLAIM_CASHBACK_DISCRIMINATOR, accounts)


# ============================================
# Async Fetch Functions - from Rust: src/instruction/utils/pumpfun.rs
# ============================================

from typing import Protocol, runtime_checkable, Tuple
import struct


@runtime_checkable
class PumpFunFetcher(Protocol):
    """Protocol for fetching data from RPC"""
    async def get_account_info(self, pubkey: Pubkey) -> bytes | None:
        ...


async def fetch_bonding_curve_account(
    fetcher: PumpFunFetcher,
    mint: Pubkey
) -> Tuple[PumpFunParams, Pubkey] | None:
    """
    Fetch bonding curve account from RPC.
    100% from Rust: src/instruction/utils/pumpfun.rs fetch_bonding_curve_account
    
    Args:
        fetcher: Object implementing PumpFunFetcher protocol
        mint: Token mint address
    
    Returns:
        Tuple of (PumpFunParams, bonding_curve_pda) if found, None if not found
    """
    bonding_curve_pda = get_bonding_curve_pda(mint)
    data = await fetcher.get_account_info(bonding_curve_pda)
    
    if data is None or len(data) == 0:
        return None
    
    # Bonding curve data starts after 8-byte discriminator
    offset = 8
    
    # virtual_token_reserves: u64
    virtual_token_reserves = struct.unpack_from('<Q', data, offset)[0]
    offset += 8
    
    # virtual_sol_reserves: u64
    virtual_sol_reserves = struct.unpack_from('<Q', data, offset)[0]
    offset += 8
    
    # real_token_reserves: u64
    real_token_reserves = struct.unpack_from('<Q', data, offset)[0]
    offset += 8
    
    # real_sol_reserves: u64
    real_sol_reserves = struct.unpack_from('<Q', data, offset)[0]
    offset += 8
    
    # token_total_supply: u64
    offset += 8  # skip
    
    # complete: bool
    complete = data[offset] == 1
    offset += 1
    
    # creator: Pubkey (32 bytes)
    creator = Pubkey.from_bytes(data[offset:offset + 32])
    offset += 32
    
    # is_mayhem_mode: bool
    is_mayhem_mode = data[offset] == 1
    offset += 1
    
    # is_cashback_coin: bool
    is_cashback_coin = data[offset] == 1
    
    params = PumpFunParams(
        bonding_curve_account=bonding_curve_pda,
        virtual_token_reserves=virtual_token_reserves,
        virtual_sol_reserves=virtual_sol_reserves,
        real_token_reserves=real_token_reserves,
        real_sol_reserves=real_sol_reserves,
        complete=complete,
        creator=creator,
        is_mayhem_mode=is_mayhem_mode,
        is_cashback_coin=is_cashback_coin,
        creator_vault=get_creator_vault_pda(creator),
        token_program=TOKEN_PROGRAM_2022,
    )
    
    return (params, bonding_curve_pda)


def get_buy_price(
    amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
    real_token_reserves: int
) -> int:
    """
    Calculate tokens received for SOL amount.
    100% from Rust: src/instruction/utils/pumpfun.rs get_buy_price
    
    Args:
        amount: SOL amount in lamports
        virtual_sol_reserves: Virtual SOL reserves
        virtual_token_reserves: Virtual token reserves
        real_token_reserves: Real token reserves
    
    Returns:
        Token amount that can be bought
    """
    if amount == 0:
        return 0
    
    n = virtual_sol_reserves * virtual_token_reserves
    i = virtual_sol_reserves + amount
    r = n // i + 1
    s = virtual_token_reserves - r
    
    return min(s, real_token_reserves)


# ============================================
# Exports
# ============================================

__all__ = [
    # Program IDs and Constants
    "PUMPFUN_PROGRAM_ID",
    "FEE_RECIPIENT",
    "GLOBAL_ACCOUNT",
    "EVENT_AUTHORITY",
    "AUTHORITY",
    "FEE_PROGRAM",
    "GLOBAL_VOLUME_ACCUMULATOR",
    "FEE_CONFIG",
    "MAYHEM_FEE_RECIPIENTS",
    "PROTOCOL_EXTRA_FEE_RECIPIENTS",
    "BUYBACK_FEE_RECIPIENTS",
    # Discriminators
    "BUY_DISCRIMINATOR",
    "BUY_EXACT_SOL_IN_DISCRIMINATOR",
    "SELL_DISCRIMINATOR",
    "BUY_V2_DISCRIMINATOR",
    "SELL_V2_DISCRIMINATOR",
    "BUY_EXACT_QUOTE_IN_V2_DISCRIMINATOR",
    "CLAIM_CASHBACK_DISCRIMINATOR",
    # PDA Functions
    "get_bonding_curve_pda",
    "get_bonding_curve_v2_pda",
    "get_creator_vault_pda",
    "get_user_volume_accumulator_pda",
    "get_fee_sharing_config_pda",
    "get_creator",
    "get_mayhem_fee_recipient_random",
    "get_protocol_extra_fee_recipient_random",
    "get_buyback_fee_recipient_random",
    # Params
    "PumpFunParams",
    # Calculation Functions
    "get_buy_token_amount_from_sol_amount",
    "get_sell_sol_amount_from_token_amount",
    # Instruction Builders
    "build_buy_instructions",
    "build_sell_instructions",
    "build_buy_v2_instructions",
    "build_sell_v2_instructions",
    "claim_cashback_pumpfun_instruction",
]
