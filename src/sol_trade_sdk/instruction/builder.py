"""
Instruction Builders for Sol Trade SDK
Implements instruction builders for various Solana trading protocols.
"""

import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import IntEnum


# ===== Constants =====

# Program IDs
PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKFJdMZzMMTrWr1Bv"
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKFRHoe4LvJhu5yQJtezhkEL5DHyJ"
BONK_PROGRAM_ID = "bonkDrS7bPzmDyFvYDJyaPa3KhoMfV3wxYXQRWYmWPTj"
RAYDIUM_AMM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM_PROGRAM_ID = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
METEORA_PROGRAM_ID = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"


# ===== Instruction Discriminators =====

class PumpFunInstruction(IntEnum):
    """PumpFun instruction discriminators"""
    CREATE = 0
    BUY = 1
    SELL = 2


class PumpSwapInstruction(IntEnum):
    """PumpSwap instruction discriminators"""
    BUY = 0
    SELL = 1


class TokenInstruction(IntEnum):
    """SPL Token instruction discriminators"""
    TRANSFER = 3
    TRANSFER_CHECKED = 12
    INITIALIZE_ACCOUNT = 1
    CLOSE_ACCOUNT = 9
    SYNC_NATIVE = 17


# ===== Account Meta =====

@dataclass
class AccountMeta:
    """Account metadata for instructions"""
    pubkey: bytes
    is_signer: bool
    is_writable: bool

    def to_list(self) -> Tuple[bytes, bool, bool]:
        return (self.pubkey, self.is_signer, self.is_writable)


# ===== Instruction =====

@dataclass
class Instruction:
    """Solana instruction"""
    program_id: bytes
    accounts: List[AccountMeta]
    data: bytes


def pubkey_to_bytes(pubkey: str) -> bytes:
    """Convert base58 pubkey string to bytes"""
    import base58
    return base58.b58decode(pubkey)


# ===== Instruction Builder Base =====

class InstructionBuilder:
    """Base class for instruction builders"""

    @staticmethod
    def create_account_meta(pubkey: bytes, is_signer: bool = False, is_writable: bool = False) -> AccountMeta:
        """Create an account metadata object"""
        return AccountMeta(pubkey=pubkey, is_signer=is_signer, is_writable=is_writable)

    @staticmethod
    def create_instruction(program_id: bytes, accounts: List[AccountMeta], data: bytes) -> Instruction:
        """Create an instruction"""
        return Instruction(program_id=program_id, accounts=accounts, data=data)


# ===== PumpFun Instruction Builder =====

class PumpFunInstructionBuilder(InstructionBuilder):
    """Builder for PumpFun protocol instructions"""

    PROGRAM_ID = pubkey_to_bytes(PUMPFUN_PROGRAM_ID)

    @classmethod
    def create(
        cls,
        payer: bytes,
        mint: bytes,
        mint_authority: bytes,
        bonding_curve: bytes,
        associated_bonding_curve: bytes,
        metadata: bytes,
    ) -> Instruction:
        """
        Build a create instruction for PumpFun.
        
        Creates a new token bonding curve.
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(mint, is_signer=True, is_writable=True),
            cls.create_account_meta(mint_authority, is_signer=False, is_writable=False),
            cls.create_account_meta(bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(associated_bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(metadata, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<B", PumpFunInstruction.CREATE)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def buy(
        cls,
        payer: bytes,
        mint: bytes,
        bonding_curve: bytes,
        associated_bonding_curve: bytes,
        associated_user: bytes,
        user: bytes,
        amount: int,
        max_sol_cost: int,
    ) -> Instruction:
        """
        Build a buy instruction for PumpFun.
        
        Args:
            payer: Buyer's public key
            mint: Token mint address
            bonding_curve: Bonding curve account
            associated_bonding_curve: Bonding curve's token account
            associated_user: User's token account
            user: User's wallet
            amount: Amount of tokens to buy
            max_sol_cost: Maximum SOL willing to pay
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(mint, is_signer=False, is_writable=False),
            cls.create_account_meta(bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(associated_bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(associated_user, is_signer=False, is_writable=True),
            cls.create_account_meta(user, is_signer=False, is_writable=True),
        ]

        # Pack: discriminator (1) + amount (8) + max_sol_cost (8)
        data = struct.pack("<BQQ", PumpFunInstruction.BUY, amount, max_sol_cost)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def sell(
        cls,
        payer: bytes,
        mint: bytes,
        bonding_curve: bytes,
        associated_bonding_curve: bytes,
        associated_user: bytes,
        user: bytes,
        amount: int,
        min_sol_output: int,
    ) -> Instruction:
        """
        Build a sell instruction for PumpFun.
        
        Args:
            payer: Seller's public key
            mint: Token mint address
            bonding_curve: Bonding curve account
            associated_bonding_curve: Bonding curve's token account
            associated_user: User's token account
            user: User's wallet
            amount: Amount of tokens to sell
            min_sol_output: Minimum SOL expected to receive
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(mint, is_signer=False, is_writable=False),
            cls.create_account_meta(bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(associated_bonding_curve, is_signer=False, is_writable=True),
            cls.create_account_meta(associated_user, is_signer=False, is_writable=True),
            cls.create_account_meta(user, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<BQQ", PumpFunInstruction.SELL, amount, min_sol_output)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== PumpSwap Instruction Builder =====

class PumpSwapInstructionBuilder(InstructionBuilder):
    """Builder for PumpSwap protocol instructions"""

    PROGRAM_ID = pubkey_to_bytes(PUMPSWAP_PROGRAM_ID)

    @classmethod
    def buy(
        cls,
        payer: bytes,
        pool_state: bytes,
        pool_quote_token_account: bytes,
        pool_base_token_account: bytes,
        user_quote_token_account: bytes,
        user_base_token_account: bytes,
        amount: int,
        min_output: int,
    ) -> Instruction:
        """
        Build a buy instruction for PumpSwap.
        
        Args:
            payer: Buyer's public key
            pool_state: Pool state account
            pool_quote_token_account: Pool's quote token account
            pool_base_token_account: Pool's base token account
            user_quote_token_account: User's quote token account
            user_base_token_account: User's base token account
            amount: Amount of quote tokens to spend
            min_output: Minimum base tokens expected
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(pool_state, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_quote_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_base_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_quote_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_base_token_account, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<BQQ", PumpSwapInstruction.BUY, amount, min_output)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def sell(
        cls,
        payer: bytes,
        pool_state: bytes,
        pool_base_token_account: bytes,
        pool_quote_token_account: bytes,
        user_base_token_account: bytes,
        user_quote_token_account: bytes,
        amount: int,
        min_output: int,
    ) -> Instruction:
        """
        Build a sell instruction for PumpSwap.
        
        Args:
            payer: Seller's public key
            pool_state: Pool state account
            pool_base_token_account: Pool's base token account
            pool_quote_token_account: Pool's quote token account
            user_base_token_account: User's base token account
            user_quote_token_account: User's quote token account
            amount: Amount of base tokens to sell
            min_output: Minimum quote tokens expected
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(pool_state, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_base_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_quote_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_base_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_quote_token_account, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<BQQ", PumpSwapInstruction.SELL, amount, min_output)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Raydium AMM V4 Instruction Builder =====

class RaydiumAmmV4InstructionBuilder(InstructionBuilder):
    """Builder for Raydium AMM V4 protocol instructions"""

    PROGRAM_ID = pubkey_to_bytes(RAYDIUM_AMM_V4_PROGRAM_ID)

    @classmethod
    def swap(
        cls,
        payer: bytes,
        amm_id: bytes,
        amm_authority: bytes,
        amm_open_orders: bytes,
        amm_target_orders: bytes,
        pool_coin_token_account: bytes,
        pool_pc_token_account: bytes,
        serum_program_id: bytes,
        serum_market: bytes,
        serum_bids: bytes,
        serum_asks: bytes,
        serum_event_queue: bytes,
        serum_coin_vault: bytes,
        serum_pc_vault: bytes,
        serum_vault_signer: bytes,
        user_source_token_account: bytes,
        user_dest_token_account: bytes,
        user_wallet: bytes,
        amount_in: int,
        min_amount_out: int,
    ) -> Instruction:
        """
        Build a swap instruction for Raydium AMM V4.
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(amm_id, is_signer=False, is_writable=True),
            cls.create_account_meta(amm_authority, is_signer=False, is_writable=False),
            cls.create_account_meta(amm_open_orders, is_signer=False, is_writable=True),
            cls.create_account_meta(amm_target_orders, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_coin_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_pc_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_program_id, is_signer=False, is_writable=False),
            cls.create_account_meta(serum_market, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_bids, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_asks, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_event_queue, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_coin_vault, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_pc_vault, is_signer=False, is_writable=True),
            cls.create_account_meta(serum_vault_signer, is_signer=False, is_writable=False),
            cls.create_account_meta(user_source_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_dest_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_wallet, is_signer=False, is_writable=True),
        ]

        # Swap instruction: discriminator (1) + amount_in (8) + min_amount_out (8)
        data = struct.pack("<BQQ", 9, amount_in, min_amount_out)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Raydium CPMM Instruction Builder =====

class RaydiumCpmmInstructionBuilder(InstructionBuilder):
    """Builder for Raydium CPMM protocol instructions"""

    PROGRAM_ID = pubkey_to_bytes(RAYDIUM_CPMM_PROGRAM_ID)

    @classmethod
    def swap(
        cls,
        payer: bytes,
        pool_id: bytes,
        pool_authority: bytes,
        pool_token_a_account: bytes,
        pool_token_b_account: bytes,
        user_source_token_account: bytes,
        user_dest_token_account: bytes,
        amount_in: int,
        min_amount_out: int,
    ) -> Instruction:
        """
        Build a swap instruction for Raydium CPMM.
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(pool_id, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_authority, is_signer=False, is_writable=False),
            cls.create_account_meta(pool_token_a_account, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_token_b_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_source_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_dest_token_account, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<BQQ", 1, amount_in, min_amount_out)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Meteora Instruction Builder =====

class MeteoraInstructionBuilder(InstructionBuilder):
    """Builder for Meteora protocol instructions"""

    PROGRAM_ID = pubkey_to_bytes(METEORA_PROGRAM_ID)

    @classmethod
    def swap(
        cls,
        payer: bytes,
        pool_id: bytes,
        pool_authority: bytes,
        pool_token_a_account: bytes,
        pool_token_b_account: bytes,
        user_source_token_account: bytes,
        user_dest_token_account: bytes,
        amount_in: int,
        min_amount_out: int,
    ) -> Instruction:
        """
        Build a swap instruction for Meteora.
        """
        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(pool_id, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_authority, is_signer=False, is_writable=False),
            cls.create_account_meta(pool_token_a_account, is_signer=False, is_writable=True),
            cls.create_account_meta(pool_token_b_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_source_token_account, is_signer=False, is_writable=True),
            cls.create_account_meta(user_dest_token_account, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<QQ", amount_in, min_amount_out)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Token Instruction Builder =====

class TokenInstructionBuilder(InstructionBuilder):
    """Builder for SPL Token instructions"""

    PROGRAM_ID = pubkey_to_bytes(TOKEN_PROGRAM_ID)

    @classmethod
    def transfer(
        cls,
        source: bytes,
        destination: bytes,
        owner: bytes,
        amount: int,
    ) -> Instruction:
        """
        Build a transfer instruction for SPL Token.
        """
        accounts = [
            cls.create_account_meta(source, is_signer=False, is_writable=True),
            cls.create_account_meta(destination, is_signer=False, is_writable=True),
            cls.create_account_meta(owner, is_signer=True, is_writable=False),
        ]

        data = struct.pack("<BQ", TokenInstruction.TRANSFER, amount)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def transfer_checked(
        cls,
        source: bytes,
        mint: bytes,
        destination: bytes,
        owner: bytes,
        amount: int,
        decimals: int,
    ) -> Instruction:
        """
        Build a transfer_checked instruction for SPL Token.
        """
        accounts = [
            cls.create_account_meta(source, is_signer=False, is_writable=True),
            cls.create_account_meta(mint, is_signer=False, is_writable=False),
            cls.create_account_meta(destination, is_signer=False, is_writable=True),
            cls.create_account_meta(owner, is_signer=True, is_writable=False),
        ]

        data = struct.pack("<BQB", TokenInstruction.TRANSFER_CHECKED, amount, decimals)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def close_account(
        cls,
        account: bytes,
        destination: bytes,
        owner: bytes,
    ) -> Instruction:
        """
        Build a close_account instruction for SPL Token.
        """
        accounts = [
            cls.create_account_meta(account, is_signer=False, is_writable=True),
            cls.create_account_meta(destination, is_signer=False, is_writable=True),
            cls.create_account_meta(owner, is_signer=True, is_writable=False),
        ]

        data = struct.pack("<B", TokenInstruction.CLOSE_ACCOUNT)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)

    @classmethod
    def sync_native(cls, account: bytes) -> Instruction:
        """
        Build a sync_native instruction for SPL Token.
        Used for WSOL accounts.
        """
        accounts = [
            cls.create_account_meta(account, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<B", TokenInstruction.SYNC_NATIVE)

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Associated Token Account Instruction Builder =====

class AssociatedTokenInstructionBuilder(InstructionBuilder):
    """Builder for Associated Token Account instructions"""

    PROGRAM_ID = pubkey_to_bytes(ASSOCIATED_TOKEN_PROGRAM_ID)

    @classmethod
    def create_associated_token_account(
        cls,
        payer: bytes,
        associated_token: bytes,
        owner: bytes,
        mint: bytes,
    ) -> Instruction:
        """
        Build a create_associated_token_account instruction.
        """
        system_program = pubkey_to_bytes(SYSTEM_PROGRAM_ID)
        token_program = pubkey_to_bytes(TOKEN_PROGRAM_ID)

        accounts = [
            cls.create_account_meta(payer, is_signer=True, is_writable=True),
            cls.create_account_meta(associated_token, is_signer=False, is_writable=True),
            cls.create_account_meta(owner, is_signer=False, is_writable=False),
            cls.create_account_meta(mint, is_signer=False, is_writable=False),
            cls.create_account_meta(system_program, is_signer=False, is_writable=False),
            cls.create_account_meta(token_program, is_signer=False, is_writable=False),
        ]

        return cls.create_instruction(cls.PROGRAM_ID, accounts, b"")


# ===== System Instruction Builder =====

class SystemInstructionBuilder(InstructionBuilder):
    """Builder for System Program instructions"""

    PROGRAM_ID = pubkey_to_bytes(SYSTEM_PROGRAM_ID)

    @classmethod
    def transfer(
        cls,
        from_pubkey: bytes,
        to_pubkey: bytes,
        lamports: int,
    ) -> Instruction:
        """
        Build a transfer instruction for System Program.
        """
        accounts = [
            cls.create_account_meta(from_pubkey, is_signer=True, is_writable=True),
            cls.create_account_meta(to_pubkey, is_signer=False, is_writable=True),
        ]

        data = struct.pack("<QQ", 2, lamports)  # Transfer instruction = 2

        return cls.create_instruction(cls.PROGRAM_ID, accounts, data)


# ===== Convenience exports =====

__all__ = [
    "AccountMeta",
    "Instruction",
    "InstructionBuilder",
    "PumpFunInstructionBuilder",
    "PumpSwapInstructionBuilder",
    "RaydiumAmmV4InstructionBuilder",
    "RaydiumCpmmInstructionBuilder",
    "MeteoraInstructionBuilder",
    "TokenInstructionBuilder",
    "AssociatedTokenInstructionBuilder",
    "SystemInstructionBuilder",
    "pubkey_to_bytes",
]
