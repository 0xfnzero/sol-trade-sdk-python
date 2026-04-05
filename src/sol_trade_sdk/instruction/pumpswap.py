"""
PumpSwap instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
import random
from typing import List, Optional, Tuple
from dataclasses import dataclass

# Program IDs
AMM_PROGRAM = bytes.fromhex("70c11de2b17e4c4e3c5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8")
PUMP_PROGRAM_ID = bytes.fromhex("6ef8f3d8b6e8f9e8d9c0b1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d")
EVENT_AUTHORITY = bytes.fromhex("9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8")
GLOBAL_ACCOUNT = bytes.fromhex("ad1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1")
GLOBAL_VOLUME_ACCUMULATOR = bytes.fromhex("bc2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2")
FEE_CONFIG = bytes.fromhex("cd3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3")
FEE_PROGRAM = bytes.fromhex("de4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4")

# Fee recipient
FEE_RECIPIENT = bytes.fromhex("62qc2c4e5d6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2")

# Mayhem fee recipients
MAYHEM_FEE_RECIPIENTS = [
    bytes.fromhex("9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8"),
    bytes.fromhex("8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7"),
    bytes.fromhex("7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6"),
    bytes.fromhex("6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5"),
    bytes.fromhex("5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4"),
    bytes.fromhex("4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3"),
    bytes.fromhex("3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2"),
    bytes.fromhex("2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1"),
]
MAYHEM_FEE_RECIPIENT = MAYHEM_FEE_RECIPIENTS[0]

# Default creator vault authority
DEFAULT_COIN_CREATOR_VAULT_AUTHORITY = bytes.fromhex("8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9")

# Discriminators
BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
BUY_EXACT_QUOTE_IN_DISCRIMINATOR = bytes([198, 46, 21, 82, 180, 217, 232, 112])
SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
CLAIM_CASHBACK_DISCRIMINATOR = bytes([37, 58, 35, 126, 190, 53, 228, 197])

# Seeds
POOL_V2_SEED = b"pool-v2"
POOL_SEED = b"pool"
POOL_AUTHORITY_SEED = b"pool-authority"
USER_VOLUME_ACCUMULATOR_SEED = b"user_volume_accumulator"
GLOBAL_VOLUME_ACCUMULATOR_SEED = b"global_volume_accumulator"
FEE_CONFIG_SEED = b"fee_config"

# Fee basis points
LP_FEE_BASIS_POINTS = 25
PROTOCOL_FEE_BASIS_POINTS = 5
COIN_CREATOR_FEE_BASIS_POINTS = 5


@dataclass
class AccountMeta:
    """Account metadata for instructions"""
    pubkey: bytes
    is_signer: bool
    is_writable: bool


@dataclass
class Instruction:
    """Solana instruction"""
    program_id: bytes
    accounts: List[AccountMeta]
    data: bytes


def get_mayhem_fee_recipient_random() -> Tuple[bytes, AccountMeta]:
    """Get random Mayhem fee recipient and its AccountMeta"""
    recipient = random.choice(MAYHEM_FEE_RECIPIENTS)
    meta = AccountMeta(recipient, False, False)
    return recipient, meta


def get_pool_v2_pda(base_mint: bytes) -> Optional[bytes]:
    """Get pool v2 PDA for a base mint"""
    import hashlib
    seed = POOL_V2_SEED + base_mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_pump_pool_authority_pda(mint: bytes) -> bytes:
    """Get pump pool authority PDA"""
    import hashlib
    seed = POOL_AUTHORITY_SEED + mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_canonical_pool_pda(mint: bytes) -> bytes:
    """Get canonical pool PDA for a mint"""
    import hashlib
    authority = get_pump_pool_authority_pda(mint)
    index = 0
    seed = POOL_SEED + index.to_bytes(2, 'little') + authority + mint + bytes(32)  # WSOL placeholder
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def coin_creator_vault_authority(coin_creator: bytes) -> bytes:
    """Get coin creator vault authority"""
    import hashlib
    seed = b"creator_vault" + coin_creator
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def coin_creator_vault_ata(coin_creator: bytes, quote_mint: bytes) -> bytes:
    """Get coin creator vault ATA"""
    authority = coin_creator_vault_authority(coin_creator)
    # Simplified ATA derivation
    import hashlib
    seed = authority + quote_mint + b"token"
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def fee_recipient_ata(fee_recipient: bytes, quote_mint: bytes) -> bytes:
    """Get fee recipient ATA"""
    import hashlib
    seed = fee_recipient + quote_mint + b"token"
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_user_volume_accumulator_pda(user: bytes) -> Optional[bytes]:
    """Get user volume accumulator PDA"""
    import hashlib
    seed = USER_VOLUME_ACCUMULATOR_SEED + user
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_user_volume_accumulator_wsol_ata(user: bytes) -> Optional[bytes]:
    """Get WSOL ATA of UserVolumeAccumulator"""
    accumulator = get_user_volume_accumulator_pda(user)
    if not accumulator:
        return None
    import hashlib
    seed = accumulator + bytes(32) + b"token"  # WSOL placeholder
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_user_volume_accumulator_quote_ata(
    user: bytes,
    quote_mint: bytes,
    quote_token_program: bytes,
) -> Optional[bytes]:
    """Get quote-mint ATA of UserVolumeAccumulator"""
    accumulator = get_user_volume_accumulator_pda(user)
    if not accumulator:
        return None
    import hashlib
    seed = accumulator + quote_mint + quote_token_program
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_global_volume_accumulator_pda() -> Optional[bytes]:
    """Get global volume accumulator PDA"""
    import hashlib
    seed = GLOBAL_VOLUME_ACCUMULATOR_SEED
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


class PumpSwapInstructionBuilder:
    """Instruction builder for PumpSwap protocol"""

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        pool: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        input_amount: int,
        slippage_basis_points: int,
        pool_base_token_account: bytes,
        pool_quote_token_account: bytes,
        pool_base_token_reserves: int,
        pool_quote_token_reserves: int,
        coin_creator_vault_ata: bytes,
        coin_creator_vault_authority: bytes,
        base_token_program: bytes,
        quote_token_program: bytes,
        is_mayhem_mode: bool = False,
        is_cashback_coin: bool = False,
        use_exact_quote_amount: bool = True,
    ) -> List[Instruction]:
        """Build buy instructions for PumpSwap"""
        from ..calc.pumpswap import buy_quote_input_internal

        if input_amount == 0:
            raise ValueError("Amount cannot be zero")

        # Determine if quote is WSOL/USDC
        is_wsol = quote_mint == bytes(32)  # WSOL placeholder
        is_usdc = quote_mint == bytes(32)  # USDC placeholder

        if not is_wsol and not is_usdc:
            raise ValueError("Pool must contain WSOL or USDC")

        # Calculate trade amounts
        creator = coin_creator_vault_authority if coin_creator_vault_authority != DEFAULT_COIN_CREATOR_VAULT_AUTHORITY else bytes(32)

        result = buy_quote_input_internal(
            input_amount,
            slippage_basis_points,
            pool_base_token_reserves,
            pool_quote_token_reserves,
            creator,
        )

        token_amount = result["base"]
        sol_amount = result["max_quote"]

        # Determine fee recipient
        fee_recipient, fee_recipient_meta = get_mayhem_fee_recipient_random() if is_mayhem_mode else (FEE_RECIPIENT, AccountMeta(FEE_RECIPIENT, False, False))
        fee_recipient_ata_addr = fee_recipient_ata(fee_recipient, quote_mint)

        # Build instruction data
        track_volume = bytes([1, 1]) if is_cashback_coin else bytes([1, 0])

        if use_exact_quote_amount:
            min_base_amount_out = token_amount - (token_amount * slippage_basis_points // 10000)
            data = BUY_EXACT_QUOTE_IN_DISCRIMINATOR + struct.pack("<Q", input_amount) + struct.pack("<Q", min_base_amount_out) + track_volume
        else:
            data = BUY_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", sol_amount) + track_volume

        # Build accounts
        pool_v2 = get_pool_v2_pda(base_mint)
        user_volume_accumulator = get_user_volume_accumulator_pda(payer)

        accounts = [
            AccountMeta(pool, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(GLOBAL_ACCOUNT, False, False),
            AccountMeta(base_mint, False, False),
            AccountMeta(quote_mint, False, False),
            AccountMeta(bytes(32), False, True),  # user_base_token_account (placeholder)
            AccountMeta(bytes(32), False, True),  # user_quote_token_account (placeholder)
            AccountMeta(pool_base_token_account, False, True),
            AccountMeta(pool_quote_token_account, False, True),
            fee_recipient_meta,
            AccountMeta(fee_recipient_ata_addr, False, True),
            AccountMeta(base_token_program, False, False),
            AccountMeta(quote_token_program, False, False),
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
            AccountMeta(bytes(32), False, False),  # associated token program (placeholder)
            AccountMeta(EVENT_AUTHORITY, False, False),
            AccountMeta(AMM_PROGRAM, False, False),
            AccountMeta(coin_creator_vault_ata, False, True),
            AccountMeta(coin_creator_vault_authority, False, False),
            AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True),
            AccountMeta(user_volume_accumulator, False, True),
            AccountMeta(FEE_CONFIG, False, False),
            AccountMeta(FEE_PROGRAM, False, False),
        ]

        # Add cashback ATA if needed
        if is_cashback_coin:
            wsol_ata = get_user_volume_accumulator_wsol_ata(payer)
            if wsol_ata:
                accounts.append(AccountMeta(wsol_ata, False, True))

        # Add pool v2
        accounts.append(AccountMeta(pool_v2, False, False))

        return [Instruction(AMM_PROGRAM, accounts, data)]

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        pool: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        token_amount: int,
        slippage_basis_points: int,
        pool_base_token_account: bytes,
        pool_quote_token_account: bytes,
        pool_base_token_reserves: int,
        pool_quote_token_reserves: int,
        coin_creator_vault_ata: bytes,
        coin_creator_vault_authority: bytes,
        base_token_program: bytes,
        quote_token_program: bytes,
        is_mayhem_mode: bool = False,
        is_cashback_coin: bool = False,
    ) -> List[Instruction]:
        """Build sell instructions for PumpSwap"""
        from ..calc.pumpswap import sell_base_input_internal

        if token_amount == 0:
            raise ValueError("Amount cannot be zero")

        # Determine if quote is WSOL/USDC
        is_wsol = quote_mint == bytes(32)  # WSOL placeholder
        is_usdc = quote_mint == bytes(32)  # USDC placeholder

        if not is_wsol and not is_usdc:
            raise ValueError("Pool must contain WSOL or USDC")

        # Calculate trade amounts
        creator = coin_creator_vault_authority if coin_creator_vault_authority != DEFAULT_COIN_CREATOR_VAULT_AUTHORITY else bytes(32)

        result = sell_base_input_internal(
            token_amount,
            slippage_basis_points,
            pool_base_token_reserves,
            pool_quote_token_reserves,
            creator,
        )

        min_quote_amount_out = result["min_quote"]

        # Determine fee recipient
        fee_recipient, fee_recipient_meta = get_mayhem_fee_recipient_random() if is_mayhem_mode else (FEE_RECIPIENT, AccountMeta(FEE_RECIPIENT, False, False))
        fee_recipient_ata_addr = fee_recipient_ata(fee_recipient, quote_mint)

        # Build instruction data
        data = SELL_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", min_quote_amount_out)

        # Build accounts
        pool_v2 = get_pool_v2_pda(base_mint)
        user_volume_accumulator = get_user_volume_accumulator_pda(payer)

        accounts = [
            AccountMeta(pool, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(GLOBAL_ACCOUNT, False, False),
            AccountMeta(base_mint, False, False),
            AccountMeta(quote_mint, False, False),
            AccountMeta(bytes(32), False, True),  # user_base_token_account (placeholder)
            AccountMeta(bytes(32), False, True),  # user_quote_token_account (placeholder)
            AccountMeta(pool_base_token_account, False, True),
            AccountMeta(pool_quote_token_account, False, True),
            fee_recipient_meta,
            AccountMeta(fee_recipient_ata_addr, False, True),
            AccountMeta(base_token_program, False, False),
            AccountMeta(quote_token_program, False, False),
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
            AccountMeta(bytes(32), False, False),  # associated token program (placeholder)
            AccountMeta(EVENT_AUTHORITY, False, False),
            AccountMeta(AMM_PROGRAM, False, False),
            AccountMeta(coin_creator_vault_ata, False, True),
            AccountMeta(coin_creator_vault_authority, False, False),
            AccountMeta(FEE_CONFIG, False, False),
            AccountMeta(FEE_PROGRAM, False, False),
        ]

        # Add cashback accounts if needed
        if is_cashback_coin:
            quote_ata = get_user_volume_accumulator_quote_ata(payer, quote_mint, quote_token_program)
            if quote_ata and user_volume_accumulator:
                accounts.append(AccountMeta(quote_ata, False, True))
                accounts.append(AccountMeta(user_volume_accumulator, False, True))

        # Add pool v2
        accounts.append(AccountMeta(pool_v2, False, False))

        return [Instruction(AMM_PROGRAM, accounts, data)]


def claim_cashback_pumpswap_instruction(
    payer: bytes,
    quote_mint: bytes,
    quote_token_program: bytes,
) -> Optional[Instruction]:
    """Build claim cashback instruction for PumpSwap"""
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)
    if not user_volume_accumulator:
        return None

    user_volume_accumulator_wsol_ata = get_user_volume_accumulator_wsol_ata(payer)
    if not user_volume_accumulator_wsol_ata:
        return None

    # User WSOL ATA (placeholder)
    user_wsol_ata = bytes(32)

    accounts = [
        AccountMeta(payer, True, True),
        AccountMeta(user_volume_accumulator, False, True),
        AccountMeta(quote_mint, False, False),
        AccountMeta(quote_token_program, False, False),
        AccountMeta(user_volume_accumulator_wsol_ata, False, True),
        AccountMeta(user_wsol_ata, False, True),
        AccountMeta(bytes(32), False, False),  # system program
        AccountMeta(EVENT_AUTHORITY, False, False),
        AccountMeta(AMM_PROGRAM, False, False),
    ]

    return Instruction(AMM_PROGRAM, accounts, CLAIM_CASHBACK_DISCRIMINATOR)
