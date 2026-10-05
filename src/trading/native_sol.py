"""Explicit native SOL settlement for one cached route, using a new temporary WSOL account.

Rent is supplied from cold initialization; seed must be unique per transaction.
Existing WSOL ATAs are neither funded nor closed. Plain WSOL routes skip this helper.
"""

from dataclasses import dataclass
from hashlib import sha256
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from ..instruction.common import (
    TOKEN_PROGRAM,
    WSOL_TOKEN_ACCOUNT,
    ASSOCIATED_TOKEN_PROGRAM,
    SYSTEM_PROGRAM,
    get_associated_token_address,
)
from ..instruction.stonkfun import unsigned


@dataclass(frozen=True)
class NativeSolRoute:
    instructions: tuple
    temporary_wsol_account: Pubkey
    required_lamports: int
    minimum_net_amount_out: int


def settle_cached_route_with_native_sol(
    route, payer, seed, rent_lamports, native_input=False, native_output=False
):
    if (
        not isinstance(native_input, bool)
        or not isinstance(native_output, bool)
        or native_input == native_output
    ):
        raise ValueError("Choose exactly one native SOL endpoint")
    if not 1 <= len(route.legs) <= 5 or len(route.swap_instructions) != len(route.legs):
        raise ValueError("Invalid native SOL route instructions")
    for i, (leg, ix) in enumerate(zip(route.legs, route.swap_instructions)):
        if ix != leg.instruction:
            raise ValueError("Native SOL instruction differs from quoted leg")
        unsigned(leg.amount_in)
        unsigned(leg.minimum_net_amount_out)
        if not leg.amount_in or not leg.minimum_net_amount_out:
            raise ValueError("Invalid native SOL amount or protection")
        if i and (route.legs[i-1].hint.output_mint != leg.hint.input_mint
                  or leg.amount_in > route.legs[i-1].minimum_net_amount_out):
            raise ValueError("Native SOL route exceeds protected intermediate credit")
    unsigned(route.minimum_net_amount_out)
    if route.minimum_net_amount_out != route.legs[-1].minimum_net_amount_out:
        raise ValueError("Native SOL protection differs from quoted leg")
    mint = route.legs[0].hint.input_mint if native_input else route.legs[-1].hint.output_mint
    if mint != WSOL_TOKEN_ACCOUNT:
        raise ValueError("Native SOL endpoint must quote through WSOL")
    if not isinstance(seed, str) or not 1 <= len(seed.encode("utf8")) <= 32:
        raise ValueError("Temporary WSOL seed must contain 1..32 UTF-8 bytes")
    unsigned(rent_lamports)
    if not rent_lamports:
        raise ValueError("Supply current token-account rent from cold initialization")
    funding = route.legs[0].amount_in if native_input else 0
    required = unsigned(rent_lamports + funding)
    temporary = Pubkey.from_bytes(
        sha256(bytes(payer) + seed.encode() + bytes(TOKEN_PROGRAM)).digest()
    )
    old = get_associated_token_address(payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)
    if temporary == old:
        raise ValueError("Temporary account collides with existing WSOL ATA")
    encoded_seed = seed.encode()
    create_data = (
        struct.pack("<I", 3)
        + bytes(payer)
        + struct.pack("<Q", len(encoded_seed))
        + encoded_seed
        + struct.pack("<QQ", required, 165)
        + bytes(TOKEN_PROGRAM)
    )
    create = Instruction(
        SYSTEM_PROGRAM,
        create_data,
        [AccountMeta(payer, True, True), AccountMeta(temporary, False, True)],
    )
    initialize = Instruction(
        TOKEN_PROGRAM,
        bytes([18]) + bytes(payer),
        [AccountMeta(temporary, False, True), AccountMeta(WSOL_TOKEN_ACCOUNT, False, False)],
    )
    sync = Instruction(TOKEN_PROGRAM, bytes([17]), [AccountMeta(temporary, False, True)])
    setup = [
        ix
        for ix in route.setup_instructions
        if not (
            ix.program_id == ASSOCIATED_TOKEN_PROGRAM
            and len(ix.accounts) > 1
            and ix.accounts[1].pubkey == old
        )
    ]
    swaps = []
    replaced = False
    for ix in route.swap_instructions:
        if not any(a.pubkey == payer and a.is_signer for a in ix.accounts):
            raise ValueError("Native SOL route belongs to a different wallet")
        keys = []
        for a in ix.accounts:
            replacement = temporary if a.pubkey == old else a.pubkey
            replaced = replaced or replacement != a.pubkey
            keys.append(AccountMeta(replacement, a.is_signer, a.is_writable))
        swaps.append(Instruction(ix.program_id, ix.data, keys))
    if not replaced:
        raise ValueError("Native SOL route does not use the wallet WSOL account")
    close = Instruction(
        TOKEN_PROGRAM,
        bytes([9]),
        [
            AccountMeta(temporary, False, True),
            AccountMeta(payer, False, True),
            AccountMeta(payer, True, False),
        ],
    )
    return NativeSolRoute(
        tuple([create, initialize, sync] + setup + swaps + [close]),
        temporary,
        required,
        route.minimum_net_amount_out,
    )
