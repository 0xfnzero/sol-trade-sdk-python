"""
SPL Token Utilities for Sol Trade SDK
High-performance token account operations.
"""

from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
import struct
import base64

# ===== Constants =====

# Instruction discriminators
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
INITIALIZE_ACCOUNT_2 = 16
SYNC_NATIVE = 17
INITIALIZE_ACCOUNT_3 = 20
INITIALIZE_MULTISIG_2 = 21
INITIALIZE_MINT_2 = 22

# Account states
ACCOUNT_UNINITIALIZED = 0
ACCOUNT_INITIALIZED = 1
ACCOUNT_FROZEN = 2

# Authority types
AUTHORITY_MINT_TOKENS = 0
AUTHORITY_FREEZE_ACCOUNT = 1
AUTHORITY_ACCOUNT_OWNER = 2
AUTHORITY_CLOSE_ACCOUNT = 3

# Account sizes
TOKEN_ACCOUNT_SIZE = 165
MINT_SIZE = 82
MULTISIG_SIZE = 355

# Program IDs
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
SYSVAR_RENT = "SysvarRent111111111111111111111111111111111"


@dataclass
class TokenAccount:
    """Token account data"""
    mint: str
    owner: str
    amount: int
    delegate: Optional[str] = None
    state: int = ACCOUNT_INITIALIZED
    is_native: Optional[int] = None
    delegated_amount: int = 0
    close_authority: Optional[str] = None

    @classmethod
    def decode(cls, data: bytes) -> "TokenAccount":
        """Decode a token account from bytes"""
        if len(data) < TOKEN_ACCOUNT_SIZE:
            raise ValueError("Invalid token account data length")

        offset = 0

        # Mint (32 bytes)
        mint = base58_encode(data[offset:offset + 32])
        offset += 32

        # Owner (32 bytes)
        owner = base58_encode(data[offset:offset + 32])
        offset += 32

        # Amount (8 bytes)
        amount = struct.unpack("<Q", data[offset:offset + 8])[0]
        offset += 8

        # Delegate (4 + 32 bytes)
        has_delegate = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        delegate = None
        if has_delegate:
            delegate = base58_encode(data[offset:offset + 32])
            offset += 32

        # State (1 byte)
        state = data[offset]
        offset += 1

        # IsNative (4 + 8 bytes)
        is_native_flag = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        is_native = None
        if is_native_flag:
            is_native = struct.unpack("<Q", data[offset:offset + 8])[0]
            offset += 8

        # DelegatedAmount (8 bytes)
        delegated_amount = struct.unpack("<Q", data[offset:offset + 8])[0]
        offset += 8

        # CloseAuthority (4 + 32 bytes)
        has_close = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        close_authority = None
        if has_close:
            close_authority = base58_encode(data[offset:offset + 32])

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


@dataclass
class Mint:
    """Token mint data"""
    mint_authority: Optional[str] = None
    supply: int = 0
    decimals: int = 0
    is_initialized: bool = False
    freeze_authority: Optional[str] = None

    @classmethod
    def decode(cls, data: bytes) -> "Mint":
        """Decode a mint from bytes"""
        if len(data) < MINT_SIZE:
            raise ValueError("Invalid mint data length")

        offset = 0

        # MintAuthority (4 + 32 bytes)
        has_authority = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        mint_authority = None
        if has_authority:
            mint_authority = base58_encode(data[offset:offset + 32])
            offset += 32

        # Supply (8 bytes)
        supply = struct.unpack("<Q", data[offset:offset + 8])[0]
        offset += 8

        # Decimals (1 byte)
        decimals = data[offset]
        offset += 1

        # IsInitialized (1 byte)
        is_initialized = bool(data[offset])
        offset += 1

        # FreezeAuthority (4 + 32 bytes)
        has_freeze = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        freeze_authority = None
        if has_freeze:
            freeze_authority = base58_encode(data[offset:offset + 32])

        return cls(
            mint_authority=mint_authority,
            supply=supply,
            decimals=decimals,
            is_initialized=is_initialized,
            freeze_authority=freeze_authority,
        )


# ===== Instruction Building =====

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


def transfer_instruction(
    source: bytes,
    destination: bytes,
    owner: bytes,
    amount: int,
    decimals: Optional[int] = None,
    mint: Optional[bytes] = None,
) -> Instruction:
    """
    Create a transfer instruction.

    If decimals and mint are provided, creates a checked transfer.
    Otherwise creates an unchecked transfer.
    """
    if decimals is not None and mint is not None:
        # Checked transfer
        data = struct.pack("<BQB", TRANSFER_CHECKED, amount, decimals)
        accounts = [
            AccountMeta(source, False, True),
            AccountMeta(mint, False, False),
            AccountMeta(destination, False, True),
            AccountMeta(owner, True, False),
        ]
    else:
        # Unchecked transfer
        data = struct.pack("<BQ", TRANSFER, amount)
        accounts = [
            AccountMeta(source, False, True),
            AccountMeta(destination, False, True),
            AccountMeta(owner, True, False),
        ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def close_account_instruction(
    account: bytes,
    destination: bytes,
    owner: bytes,
) -> Instruction:
    """Create a close account instruction"""
    data = bytes([CLOSE_ACCOUNT])
    accounts = [
        AccountMeta(account, False, True),
        AccountMeta(destination, False, True),
        AccountMeta(owner, True, False),
    ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def sync_native_instruction(account: bytes) -> Instruction:
    """Create a sync native instruction (for WSOL)"""
    data = bytes([SYNC_NATIVE])
    accounts = [
        AccountMeta(account, False, True),
    ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def initialize_account_instruction(
    account: bytes,
    mint: bytes,
    owner: bytes,
) -> Instruction:
    """Create an initialize account instruction"""
    data = bytes([INITIALIZE_ACCOUNT])
    accounts = [
        AccountMeta(account, False, True),
        AccountMeta(mint, False, False),
        AccountMeta(owner, True, False),
        AccountMeta(base58_decode(SYSVAR_RENT), False, False),
    ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def approve_instruction(
    source: bytes,
    delegate: bytes,
    owner: bytes,
    amount: int,
    decimals: Optional[int] = None,
    mint: Optional[bytes] = None,
) -> Instruction:
    """Create an approve instruction"""
    if decimals is not None and mint is not None:
        data = struct.pack("<BQB", APPROVE_CHECKED, amount, decimals)
        accounts = [
            AccountMeta(source, False, True),
            AccountMeta(mint, False, False),
            AccountMeta(delegate, False, False),
            AccountMeta(owner, True, False),
        ]
    else:
        data = struct.pack("<BQ", APPROVE, amount)
        accounts = [
            AccountMeta(source, False, True),
            AccountMeta(delegate, False, False),
            AccountMeta(owner, True, False),
        ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def mint_to_instruction(
    mint: bytes,
    destination: bytes,
    authority: bytes,
    amount: int,
    decimals: Optional[int] = None,
) -> Instruction:
    """Create a mint_to instruction"""
    if decimals is not None:
        data = struct.pack("<BQB", MINT_TO_CHECKED, amount, decimals)
    else:
        data = struct.pack("<BQ", MINT_TO, amount)

    accounts = [
        AccountMeta(mint, False, True),
        AccountMeta(destination, False, True),
        AccountMeta(authority, True, False),
    ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


def burn_instruction(
    source: bytes,
    mint: bytes,
    owner: bytes,
    amount: int,
    decimals: Optional[int] = None,
) -> Instruction:
    """Create a burn instruction"""
    if decimals is not None:
        data = struct.pack("<BQB", BURN_CHECKED, amount, decimals)
    else:
        data = struct.pack("<BQ", BURN, amount)

    accounts = [
        AccountMeta(source, False, True),
        AccountMeta(mint, False, True),
        AccountMeta(owner, True, False),
    ]

    return Instruction(
        program_id=base58_decode(TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=data,
    )


# ===== Associated Token Account Instructions =====

def create_associated_token_account_instruction(
    payer: bytes,
    ata: bytes,
    owner: bytes,
    mint: bytes,
    token_program: bytes = None,
) -> Instruction:
    """Create an associated token account instruction"""
    if token_program is None:
        token_program = base58_decode(TOKEN_PROGRAM_ID)

    accounts = [
        AccountMeta(payer, True, True),
        AccountMeta(ata, False, True),
        AccountMeta(owner, False, False),
        AccountMeta(mint, False, False),
        AccountMeta(base58_decode(SYSTEM_PROGRAM_ID), False, False),
        AccountMeta(token_program, False, False),
    ]

    return Instruction(
        program_id=base58_decode(ASSOCIATED_TOKEN_PROGRAM_ID),
        accounts=accounts,
        data=b"",  # No data for ATA creation
    )


# ===== Amount Helpers =====

def lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL"""
    return lamports / 1_000_000_000.0


def sol_to_lamports(sol: float) -> int:
    """Convert SOL to lamports"""
    return int(sol * 1_000_000_000)


def tokens_to_ui_amount(amount: int, decimals: int) -> float:
    """Convert raw token amount to UI amount"""
    return amount / (10 ** decimals)


def ui_amount_to_tokens(ui_amount: float, decimals: int) -> int:
    """Convert UI amount to raw token amount"""
    return int(ui_amount * (10 ** decimals))


# ===== Helpers =====

def base58_encode(data: bytes) -> str:
    """Encode bytes to base58 string"""
    import base58
    return base58.b58encode(data).decode()


def base58_decode(s: str) -> bytes:
    """Decode base58 string to bytes"""
    import base58
    return base58.b58decode(s)


# ===== WSOL Utilities =====

WSOL_MINT = "So11111111111111111111111111111111111111111"


def wrap_sol_instructions(
    owner: bytes,
    amount: int,
    wsol_account: Optional[bytes] = None,
) -> List[Instruction]:
    """
    Create instructions to wrap SOL to WSOL.

    Returns a list of instructions:
    1. Create WSOL account (if needed)
    2. Transfer SOL to WSOL account
    3. Sync native
    """
    from .seed.pda import get_associated_token_address

    instructions = []

    if wsol_account is None:
        # Use ATA for WSOL
        wsol_account = get_associated_token_address(
            base58_encode(owner),
            WSOL_MINT,
        )

    # Create account instruction (if not exists)
    create_ix = create_associated_token_account_instruction(
        payer=owner,
        ata=wsol_account,
        owner=owner,
        mint=base58_decode(WSOL_MINT),
    )

    # Transfer SOL to WSOL account
    transfer_ix = Instruction(
        program_id=base58_decode(SYSTEM_PROGRAM_ID),
        accounts=[
            AccountMeta(owner, True, True),
            AccountMeta(wsol_account, False, True),
        ],
        data=struct.pack("<BQ", 2, amount),  # System transfer instruction
    )

    # Sync native
    sync_ix = sync_native_instruction(wsol_account)

    return [create_ix, transfer_ix, sync_ix]


def unwrap_sol_instructions(
    wsol_account: bytes,
    owner: bytes,
    destination: bytes,
) -> List[Instruction]:
    """
    Create instructions to unwrap WSOL to SOL.

    Returns a list with close_account instruction.
    """
    close_ix = close_account_instruction(
        account=wsol_account,
        destination=destination,
        owner=owner,
    )

    return [close_ix]
