"""
PumpFun instruction builder.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List, Optional, Tuple
from dataclasses import dataclass

# Program IDs
PUMPFUN_PROGRAM = bytes.fromhex("6ef8f3d8b6e8f9e8d9c0b1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d")
EVENT_AUTHORITY = bytes.fromhex("ce6b7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6")
GLOBAL_ACCOUNT = bytes.fromhex("4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5")
GLOBAL_VOLUME_ACCUMULATOR = bytes.fromhex("8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9")
FEE_CONFIG = bytes.fromhex("9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0")
FEE_PROGRAM = bytes.fromhex("afbeeee5a0c7d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e")

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

# Discriminators
BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
BUY_EXACT_SOL_IN_DISCRIMINATOR = bytes([56, 252, 116, 8, 158, 223, 205, 95])
SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
CLAIM_CASHBACK_DISCRIMINATOR = bytes([37, 58, 35, 126, 190, 53, 228, 197])

# Seeds
BONDING_CURVE_SEED = b"bonding-curve"
BONDING_CURVE_V2_SEED = b"bonding-curve-v2"
CREATOR_VAULT_SEED = b"creator-vault"
USER_VOLUME_ACCUMULATOR_SEED = b"user_volume_accumulator"


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


def get_bonding_curve_pda(mint: bytes) -> Optional[bytes]:
    """Get bonding curve PDA for a mint"""
    # Simplified PDA derivation - would use proper Solana PDA derivation
    import hashlib
    seed = BONDING_CURVE_SEED + mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_bonding_curve_v2_pda(mint: bytes) -> Optional[bytes]:
    """Get bonding curve v2 PDA for a mint"""
    import hashlib
    seed = BONDING_CURVE_V2_SEED + mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_creator_vault_pda(creator: bytes) -> Optional[bytes]:
    """Get creator vault PDA"""
    import hashlib
    seed = CREATOR_VAULT_SEED + creator
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_user_volume_accumulator_pda(user: bytes) -> Optional[bytes]:
    """Get user volume accumulator PDA"""
    import hashlib
    seed = USER_VOLUME_ACCUMULATOR_SEED + user
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_creator(creator_vault_pda: bytes) -> bytes:
    """Get creator from creator vault PDA"""
    if creator_vault_pda == bytes(32):
        return bytes(32)
    # Check against default creator vault
    default_vault = get_creator_vault_pda(bytes(32))
    if default_vault and creator_vault_pda == default_vault:
        return bytes(32)
    return creator_vault_pda


def get_mayhem_fee_recipient_random() -> bytes:
    """
    Get cryptographically secure random Mayhem fee recipient.

    Uses secrets module for cryptographically secure random selection.
    """
    import secrets
    return secrets.choice(MAYHEM_FEE_RECIPIENTS)


class PumpFunInstructionBuilder:
    """Instruction builder for PumpFun protocol"""

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        output_mint: bytes,
        input_amount: int,
        slippage_basis_points: int,
        bonding_curve: Any,
        creator_vault: bytes,
        associated_bonding_curve: bytes,
        token_program: bytes,
        create_output_mint_ata: bool = True,
        use_exact_sol_amount: bool = True,
        fixed_output_amount: Optional[int] = None,
        is_cashback_coin: bool = False,
    ) -> List[Instruction]:
        """Build buy instructions for PumpFun"""
        from ..calc.pumpfun import get_buy_token_amount_from_sol_amount, calculate_with_slippage_sell

        if input_amount == 0:
            raise ValueError("Amount cannot be zero")

        creator = get_creator(creator_vault)

        # Calculate token amount
        if fixed_output_amount is not None:
            buy_token_amount = fixed_output_amount
        else:
            buy_token_amount = get_buy_token_amount_from_sol_amount(
                bonding_curve.virtual_token_reserves,
                bonding_curve.virtual_sol_reserves,
                bonding_curve.real_token_reserves,
                creator,
                input_amount,
            )

        max_sol_cost = input_amount

        # Get bonding curve address
        bonding_curve_addr = bonding_curve.account if bonding_curve.account != bytes(32) else get_bonding_curve_pda(output_mint)

        # Determine fee recipient
        is_mayhem_mode = bonding_curve.is_mayhem_mode
        fee_recipient = get_mayhem_fee_recipient_random() if is_mayhem_mode else FEE_RECIPIENT

        # Get user volume accumulator
        user_volume_accumulator = get_user_volume_accumulator_pda(payer)

        instructions = []

        # Build buy instruction data
        track_volume = bytes([1, 1]) if is_cashback_coin else bytes([1, 0])

        if use_exact_sol_amount:
            # buy_exact_sol_in
            min_tokens_out = calculate_with_slippage_sell(buy_token_amount, slippage_basis_points)
            data = BUY_EXACT_SOL_IN_DISCRIMINATOR + struct.pack("<Q", input_amount) + struct.pack("<Q", min_tokens_out) + track_volume
        else:
            # buy
            data = BUY_DISCRIMINATOR + struct.pack("<Q", buy_token_amount) + struct.pack("<Q", max_sol_cost) + track_volume

        # Build accounts
        bonding_curve_v2 = get_bonding_curve_v2_pda(output_mint)

        accounts = [
            AccountMeta(GLOBAL_ACCOUNT, False, False),
            AccountMeta(fee_recipient, False, True),
            AccountMeta(output_mint, False, False),
            AccountMeta(bonding_curve_addr, False, True),
            AccountMeta(associated_bonding_curve, False, True),
            AccountMeta(bytes(32), False, True),  # user_token_account (placeholder)
            AccountMeta(payer, True, True),
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
            AccountMeta(token_program, False, False),
            AccountMeta(creator_vault, False, True),
            AccountMeta(EVENT_AUTHORITY, False, False),
            AccountMeta(PUMPFUN_PROGRAM, False, False),
            AccountMeta(GLOBAL_VOLUME_ACCUMULATOR, False, True),
            AccountMeta(user_volume_accumulator, False, True),
            AccountMeta(FEE_CONFIG, False, False),
            AccountMeta(FEE_PROGRAM, False, False),
            AccountMeta(bonding_curve_v2, False, False),
        ]

        instructions.append(Instruction(PUMPFUN_PROGRAM, accounts, data))

        return instructions

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        input_mint: bytes,
        token_amount: int,
        slippage_basis_points: int,
        bonding_curve: Any,
        creator_vault: bytes,
        associated_bonding_curve: bytes,
        token_program: bytes,
        close_token_account: bool = False,
        fixed_output_amount: Optional[int] = None,
        is_cashback_coin: bool = False,
    ) -> List[Instruction]:
        """Build sell instructions for PumpFun"""
        from ..calc.pumpfun import get_sell_sol_amount_from_token_amount, calculate_with_slippage_sell

        if token_amount == 0:
            raise ValueError("Amount cannot be zero")

        creator = get_creator(creator_vault)

        # Calculate SOL amount
        sol_amount = get_sell_sol_amount_from_token_amount(
            bonding_curve.virtual_token_reserves,
            bonding_curve.virtual_sol_reserves,
            creator,
            token_amount,
        )

        min_sol_output = fixed_output_amount if fixed_output_amount is not None else calculate_with_slippage_sell(sol_amount, slippage_basis_points)

        # Get bonding curve address
        bonding_curve_addr = bonding_curve.account if bonding_curve.account != bytes(32) else get_bonding_curve_pda(input_mint)

        # Determine fee recipient
        is_mayhem_mode = bonding_curve.is_mayhem_mode
        fee_recipient = get_mayhem_fee_recipient_random() if is_mayhem_mode else FEE_RECIPIENT

        # Build sell instruction data
        data = SELL_DISCRIMINATOR + struct.pack("<Q", token_amount) + struct.pack("<Q", min_sol_output)

        # Build accounts
        accounts = [
            AccountMeta(GLOBAL_ACCOUNT, False, False),
            AccountMeta(fee_recipient, False, True),
            AccountMeta(input_mint, False, False),
            AccountMeta(bonding_curve_addr, False, True),
            AccountMeta(associated_bonding_curve, False, True),
            AccountMeta(bytes(32), False, True),  # user_token_account (placeholder)
            AccountMeta(payer, True, True),
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
            AccountMeta(creator_vault, False, True),
            AccountMeta(token_program, False, False),
            AccountMeta(EVENT_AUTHORITY, False, False),
            AccountMeta(PUMPFUN_PROGRAM, False, False),
            AccountMeta(FEE_CONFIG, False, False),
            AccountMeta(FEE_PROGRAM, False, False),
        ]

        # Add user volume accumulator for cashback
        if is_cashback_coin:
            user_volume_accumulator = get_user_volume_accumulator_pda(payer)
            accounts.append(AccountMeta(user_volume_accumulator, False, True))

        # Add bonding curve v2
        bonding_curve_v2 = get_bonding_curve_v2_pda(input_mint)
        accounts.append(AccountMeta(bonding_curve_v2, False, False))

        instructions = [Instruction(PUMPFUN_PROGRAM, accounts, data)]

        return instructions


def claim_cashback_pumpfun_instruction(payer: bytes) -> Optional[Instruction]:
    """Build claim cashback instruction for PumpFun"""
    user_volume_accumulator = get_user_volume_accumulator_pda(payer)
    if not user_volume_accumulator:
        return None

    accounts = [
        AccountMeta(payer, True, True),
        AccountMeta(user_volume_accumulator, False, True),
        AccountMeta(bytes(32), False, False),  # system program
        AccountMeta(EVENT_AUTHORITY, False, False),
        AccountMeta(PUMPFUN_PROGRAM, False, False),
    ]

    return Instruction(PUMPFUN_PROGRAM, accounts, CLAIM_CASHBACK_DISCRIMINATOR)
