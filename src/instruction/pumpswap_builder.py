"""
PumpSwap instruction builder - Production-grade implementation.
100% port from Rust sol-trade-sdk (src/instruction/pumpswap.rs).
"""

import struct
import secrets
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


# ===== PDA Derivation Functions - 100% from Rust =====

def get_mayhem_fee_recipient_random() -> Pubkey:
    """Get cryptographically secure random Mayhem fee recipient."""
    return secrets.choice(MAYHEM_FEE_RECIPIENTS)


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

def build_buy_instructions(params: BuildBuyParams) -> List[Instruction]:
    """
    Build buy instructions for PumpSwap.
    100% port from Rust: src/instruction/pumpswap.rs build_buy_instructions
    """
    from ..calc.pumpswap import buy_quote_input_internal, calculate_with_slippage_sell
    
    if params.input_amount == 0:
        raise ValueError("Amount cannot be zero")
    
    pp = params.protocol_params
    
    # Check if pool contains WSOL or USDC
    is_wsol = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.base_mint == WSOL_TOKEN_ACCOUNT
    is_usdc = pp.quote_mint == USDC_TOKEN_ACCOUNT or pp.base_mint == USDC_TOKEN_ACCOUNT
    if not is_wsol and not is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")
    
    quote_is_wsol_or_usdc = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.quote_mint == USDC_TOKEN_ACCOUNT
    
    # Determine if has coin creator
    has_coin_creator = pp.coin_creator_vault_authority != DEFAULT_COIN_CREATOR_VAULT_AUTHORITY
    
    # Calculate trade amounts
    if quote_is_wsol_or_usdc:
        result = buy_quote_input_internal(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            has_coin_creator,
        )
        token_amount = result["base"]
        sol_amount = result["max_quote"]
    else:
        raise ValueError("Invalid configuration for operation")
    
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
        fee_recipient = FEE_RECIPIENT
    fee_recipient_ata = get_associated_token_address(fee_recipient, pp.quote_mint, TOKEN_PROGRAM)
    
    # Build instructions
    instructions: List[Instruction] = []
    
    # Handle WSOL wrapping if needed
    # CRITICAL FIX: Use input_amount when use_exact_quote_amount=true (buy_exact_quote_in mode)
    # to avoid "insufficient funds" when buying MAX
    if params.create_input_mint_ata and quote_is_wsol_or_usdc:
        wrap_amount = params.input_amount
        if not params.use_exact_quote_amount:
            wrap_amount = sol_amount
        instructions.extend(handle_wsol(params.payer, wrap_amount))
    
    # Create output token ATA if needed
    if params.create_output_mint_ata:
        instructions.append(create_associated_token_account_idempotent(
            params.payer, params.payer, pp.base_mint, pp.base_token_program
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
    
    # Add pool v2 PDA
    pool_v2 = get_pool_v2_pda(pp.base_mint)
    accounts.append(AccountMeta(pool_v2, False, False))
    protocol_extra = get_protocol_extra_fee_recipient_random()
    accounts.append(AccountMeta(protocol_extra, False, False))
    accounts.append(
        AccountMeta(get_associated_token_address(protocol_extra, pp.quote_mint, TOKEN_PROGRAM), False, True)
    )

    # Build instruction data
    if params.use_exact_quote_amount:
        # buy_exact_quote_in(spendable_quote_in, min_base_amount_out, track_volume)
        min_base_amount_out = calculate_with_slippage_sell(token_amount, params.slippage_basis_points)
        track_volume = bytes([1, 1]) if pp.is_cashback_coin else bytes([1, 0])
        data = BUY_EXACT_QUOTE_IN_DISCRIMINATOR + struct.pack("<Q", params.input_amount) + struct.pack("<Q", min_base_amount_out) + track_volume
    else:
        # buy(token_amount, max_quote, track_volume)
        track_volume = bytes([1, 1]) if pp.is_cashback_coin else bytes([1, 0])
        data = BUY_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", sol_amount) + track_volume
    
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
    from ..calc.pumpswap import sell_base_input_internal
    
    if params.input_amount == 0:
        raise ValueError("Amount cannot be zero")
    
    pp = params.protocol_params
    
    # Check if pool contains WSOL or USDC
    is_wsol = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.base_mint == WSOL_TOKEN_ACCOUNT
    is_usdc = pp.quote_mint == USDC_TOKEN_ACCOUNT or pp.base_mint == USDC_TOKEN_ACCOUNT
    if not is_wsol and not is_usdc:
        raise ValueError("Pool must contain WSOL or USDC")
    
    quote_is_wsol_or_usdc = pp.quote_mint == WSOL_TOKEN_ACCOUNT or pp.quote_mint == USDC_TOKEN_ACCOUNT
    
    # Determine if has coin creator
    has_coin_creator = pp.coin_creator_vault_authority != DEFAULT_COIN_CREATOR_VAULT_AUTHORITY
    
    # Calculate trade amounts
    token_amount = params.input_amount
    sol_amount = 0
    
    if quote_is_wsol_or_usdc:
        result = sell_base_input_internal(
            params.input_amount,
            params.slippage_basis_points,
            pp.pool_base_token_reserves,
            pp.pool_quote_token_reserves,
            has_coin_creator,
        )
        sol_amount = result["min_quote"]
    
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
        fee_recipient = FEE_RECIPIENT
    fee_recipient_ata = get_associated_token_address(fee_recipient, pp.quote_mint, TOKEN_PROGRAM)
    
    # Build instructions
    instructions: List[Instruction] = []
    
    # Create WSOL/USDC ATA if needed for receiving
    if params.create_output_mint_ata and quote_is_wsol_or_usdc:
        instructions.append(create_associated_token_account_idempotent(
            params.payer, params.payer, pp.quote_mint, pp.quote_token_program
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
    
    # Add pool v2 PDA
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
        data = SELL_DISCRIMINATOR + struct.pack("<Q", sol_amount) + struct.pack("<Q", token_amount)
    
    instructions.append(Instruction(PUMPSWAP_PROGRAM, data, accounts))
    
    # Close WSOL ATA if requested
    if params.close_output_mint_ata and quote_is_wsol_or_usdc:
        instructions.append(close_wsol(params.payer))
    
    # Close base token account if requested
    if params.close_input_mint_ata:
        close_ix = Instruction(
            pp.base_token_program,
            bytes([9]) + bytes(8),  # close_account discriminator
            [
                AccountMeta(user_base_token_account, False, True),
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
    data = await fetcher.get_account_info(pool_address)
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
        base_balance = await fetcher.get_token_account_balance(pool.pool_base_token_account)
        quote_balance = await fetcher.get_token_account_balance(pool.pool_quote_token_account)
        
        if base_balance is None or quote_balance is None:
            return None
        
        return (base_balance, quote_balance)
    except Exception:
        return None


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
    data = await fetcher.get_account_info(pool_v2)
    if data is not None and len(data) >= 8:
        pool = decode_pool(data[8:])
        if pool is not None and pool.base_mint == mint:
            return (pool_v2, pool)

    # 2. Try canonical pool PDA
    canonical = get_canonical_pool_pda(mint)
    data = await fetcher.get_account_info(canonical)
    if data is not None and len(data) >= 8:
        pool = decode_pool(data[8:])
        if pool is not None and pool.base_mint == mint:
            return (canonical, pool)

    return None


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
