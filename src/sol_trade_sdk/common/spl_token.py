"""
SPL Token utilities.

Provides helpers for SPL Token program interactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
import struct


# SPL Token program ID
TOKEN_PROGRAM_ID = bytes([
    0x06, 0xdd, 0xf5, 0xe0, 0xd7, 0x7e, 0xf0, 0x8f,
    0x0d, 0xdf, 0x43, 0x21, 0x66, 0x4e, 0x6f, 0x8e,
    0x22, 0x11, 0xaf, 0x7f, 0x4f, 0x86, 0x49, 0x09,
    0x2d, 0x8d, 0x69, 0x8e, 0xca, 0xea, 0x6a, 0x0e
])

# Associated Token Account program ID
ASSOCIATED_TOKEN_PROGRAM_ID = bytes([
    0x8c, 0x97, 0x25, 0x8f, 0x4e, 0x24, 0x89, 0x03,
    0x3a, 0x1c, 0x71, 0x67, 0xdd, 0x3d, 0x99, 0xdd,
    0x07, 0x2d, 0x89, 0x94, 0xcb, 0x0b, 0x9b, 0x68,
    0xa3, 0x77, 0x77, 0xfd, 0x62, 0x2d, 0xd3, 0x70
])

# Token program instructions
class TokenInstruction:
    """SPL Token instruction types."""
    INITIALIZE_MINT = 0
    INITIALIZE_ACCOUNT = 1
    INITIALIZE_MULTISIG = 2
    TRANSFER = 3
    APPROVE = 4
    REVOKE = 5
    SET_AUTHORITY = 6
    MINT_TO = 7
    BURN = 8
    CLOSE_ACCOUNT = 9
    FREEZE_ACCOUNT = 10
    THAW_ACCOUNT = 11
    TRANSFER_CHECKED = 12
    APPROVE_CHECKED = 13
    MINT_TO_CHECKED = 14
    BURN_CHECKED = 15
    INITIALIZE_ACCOUNT2 = 16
    SYNC_NATIVE = 17
    INITIALIZE_ACCOUNT3 = 18
    INITIALIZE_MULTISIG2 = 19
    INITIALIZE_MINT2 = 20


@dataclass
class TokenAccount:
    """SPL Token account data."""
    mint: bytes  # 32 bytes
    owner: bytes  # 32 bytes
    amount: int
    delegate: Optional[bytes] = None
    state: int = 0  # 0=Uninitialized, 1=Initialized, 2=Frozen
    is_native: Optional[int] = None
    delegated_amount: int = 0
    close_authority: Optional[bytes] = None

    @classmethod
    def from_bytes(cls, data: bytes) -> "TokenAccount":
        """Deserialize token account from bytes."""
        if len(data) < 165:
            raise ValueError("Invalid token account data")

        mint = data[0:32]
        owner = data[32:64]
        amount = int.from_bytes(data[64:72], 'little')

        # Parse optional fields
        delegate_option = int.from_bytes(data[72:76], 'little')
        delegate = data[76:108] if delegate_option else None

        state = data[108]

        is_native_option = int.from_bytes(data[109:113], 'little')
        is_native = int.from_bytes(data[113:121], 'little') if is_native_option else None

        delegated_amount = int.from_bytes(data[121:129], 'little')

        close_authority_option = int.from_bytes(data[129:133], 'little')
        close_authority = data[133:165] if close_authority_option else None

        return cls(
            mint=mint,
            owner=owner,
            amount=amount,
            delegate=delegate,
            state=state,
            is_native=is_native,
            delegated_amount=delegated_amount,
            close_authority=close_authority,
        )

    def to_bytes(self) -> bytes:
        """Serialize token account to bytes."""
        data = bytearray(165)

        data[0:32] = self.mint
        data[32:64] = self.owner
        data[64:72] = self.amount.to_bytes(8, 'little')

        if self.delegate:
            data[72:76] = (1).to_bytes(4, 'little')
            data[76:108] = self.delegate
        else:
            data[72:76] = (0).to_bytes(4, 'little')

        data[108] = self.state

        if self.is_native is not None:
            data[109:113] = (1).to_bytes(4, 'little')
            data[113:121] = self.is_native.to_bytes(8, 'little')
        else:
            data[109:113] = (0).to_bytes(4, 'little')

        data[121:129] = self.delegated_amount.to_bytes(8, 'little')

        if self.close_authority:
            data[129:133] = (1).to_bytes(4, 'little')
            data[133:165] = self.close_authority
        else:
            data[129:133] = (0).to_bytes(4, 'little')

        return bytes(data)


@dataclass
class Mint:
    """SPL Token mint data."""
    mint_authority: Optional[bytes]
    supply: int
    decimals: int
    is_initialized: bool
    freeze_authority: Optional[bytes]

    @classmethod
    def from_bytes(cls, data: bytes) -> "Mint":
        """Deserialize mint from bytes."""
        if len(data) < 82:
            raise ValueError("Invalid mint data")

        mint_authority_option = data[0]
        mint_authority = data[1:33] if mint_authority_option else None

        supply = int.from_bytes(data[33:41], 'little')
        decimals = data[41]
        is_initialized = data[42] == 1

        freeze_authority_option = data[43]
        freeze_authority = data[44:76] if freeze_authority_option else None

        return cls(
            mint_authority=mint_authority,
            supply=supply,
            decimals=decimals,
            is_initialized=is_initialized,
            freeze_authority=freeze_authority,
        )


class TokenInstructionBuilder:
    """Build SPL Token instructions."""

    @staticmethod
    def initialize_mint(
        decimals: int,
        mint_authority: bytes,
        freeze_authority: Optional[bytes] = None,
    ) -> bytes:
        """Build InitializeMint instruction."""
        data = bytearray()
        data.append(TokenInstruction.INITIALIZE_MINT)
        data.append(decimals)
        data.extend(mint_authority)
        data.append(1 if freeze_authority else 0)
        if freeze_authority:
            data.extend(freeze_authority)
        return bytes(data)

    @staticmethod
    def initialize_account() -> bytes:
        """Build InitializeAccount instruction."""
        return bytes([TokenInstruction.INITIALIZE_ACCOUNT])

    @staticmethod
    def transfer(amount: int) -> bytes:
        """Build Transfer instruction."""
        data = bytearray()
        data.append(TokenInstruction.TRANSFER)
        data.extend(amount.to_bytes(8, 'little'))
        return bytes(data)

    @staticmethod
    def transfer_checked(amount: int, decimals: int) -> bytes:
        """Build TransferChecked instruction."""
        data = bytearray()
        data.append(TokenInstruction.TRANSFER_CHECKED)
        data.extend(amount.to_bytes(8, 'little'))
        data.append(decimals)
        return bytes(data)

    @staticmethod
    def mint_to(amount: int) -> bytes:
        """Build MintTo instruction."""
        data = bytearray()
        data.append(TokenInstruction.MINT_TO)
        data.extend(amount.to_bytes(8, 'little'))
        return bytes(data)

    @staticmethod
    def burn(amount: int) -> bytes:
        """Build Burn instruction."""
        data = bytearray()
        data.append(TokenInstruction.BURN)
        data.extend(amount.to_bytes(8, 'little'))
        return bytes(data)

    @staticmethod
    def approve(amount: int) -> bytes:
        """Build Approve instruction."""
        data = bytearray()
        data.append(TokenInstruction.APPROVE)
        data.extend(amount.to_bytes(8, 'little'))
        return bytes(data)

    @staticmethod
    def revoke() -> bytes:
        """Build Revoke instruction."""
        return bytes([TokenInstruction.REVOKE])

    @staticmethod
    def close_account() -> bytes:
        """Build CloseAccount instruction."""
        return bytes([TokenInstruction.CLOSE_ACCOUNT])

    @staticmethod
    def sync_native() -> bytes:
        """Build SyncNative instruction."""
        return bytes([TokenInstruction.SYNC_NATIVE])


class TokenUtil:
    """SPL Token utility functions."""

    @staticmethod
    def get_associated_token_address(
        wallet: bytes,
        mint: bytes,
    ) -> bytes:
        """
        Derive associated token account address.

        Args:
            wallet: Wallet public key
            mint: Token mint

        Returns:
            Associated token account address
        """
        # PDA derivation: [wallet, token_program, mint]
        # In real implementation, use proper PDA derivation
        import hashlib
        seeds = wallet + TOKEN_PROGRAM_ID + mint
        return hashlib.sha256(seeds).digest()

    @staticmethod
    def calculate_rent_exempt_lamports(data_size: int) -> int:
        """
        Calculate rent-exempt lamports for account size.

        Args:
            data_size: Account data size in bytes

        Returns:
            Lamports required for rent exemption
        """
        # Solana rent calculation (simplified)
        # 128 bytes metadata + data_size
        # ~0.00000348 SOL per byte per year
        # Rent exempt = 2 years of rent
        total_size = 128 + data_size
        return total_size * 3480  # Approximate

    @staticmethod
    def amount_to_ui_amount(amount: int, decimals: int) -> float:
        """Convert raw amount to UI amount."""
        return amount / (10 ** decimals)

    @staticmethod
    def ui_amount_to_amount(ui_amount: float, decimals: int) -> int:
        """Convert UI amount to raw amount."""
        return int(ui_amount * (10 ** decimals))

    @staticmethod
    def is_valid_token_account(data: bytes) -> bool:
        """Check if account data is valid token account."""
        if len(data) != 165:
            return False

        try:
            account = TokenAccount.from_bytes(data)
            return account.state != 0  # Not uninitialized
        except Exception:
            return False

    @staticmethod
    def is_valid_mint(data: bytes) -> bool:
        """Check if account data is valid mint."""
        if len(data) < 82:
            return False

        try:
            mint = Mint.from_bytes(data)
            return mint.is_initialized
        except Exception:
            return False


# Common token constants
NATIVE_MINT = bytes([
    0x06, 0xdd, 0xf5, 0xe0, 0xd7, 0x7e, 0xf0, 0x8f,
    0x0d, 0xdf, 0x43, 0x21, 0x66, 0x4e, 0x6f, 0x8e,
    0x22, 0x11, 0xaf, 0x7f, 0x4f, 0x86, 0x49, 0x09,
    0x2d, 0x8d, 0x69, 0x8e, 0xca, 0xea, 0x6a, 0x0e
])  # Wrapped SOL

TOKEN_ACCOUNT_SIZE = 165
MINT_SIZE = 82
MULTISIG_SIZE = 355


def get_token_program_id() -> bytes:
    """Get SPL Token program ID."""
    return TOKEN_PROGRAM_ID


def get_associated_token_program_id() -> bytes:
    """Get Associated Token Account program ID."""
    return ASSOCIATED_TOKEN_PROGRAM_ID
