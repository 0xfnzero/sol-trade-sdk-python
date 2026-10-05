"""AMM v4 V2 current-state exact-in preparation from a frozen cache. No RPC."""

from dataclasses import dataclass
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from ..instruction.common import TOKEN_PROGRAM, get_associated_token_address
from ..instruction.stonkfun import unsigned, ceil
from ..instruction.token_mint_state import token_transfer_fee_for_epoch

PROGRAM = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
AUTHORITY = Pubkey.from_string("5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1")


@dataclass(frozen=True)
class CachedAmmV4State:
    pool: Pubkey
    coin_mint: Pubkey
    pc_mint: Pubkey
    coin_vault: Pubkey
    pc_vault: Pubkey
    coin_reserve: int
    pc_reserve: int
    swap_fee_numerator: int
    swap_fee_denominator: int


@dataclass(frozen=True)
class AmmV4Quote:
    amount_in: int
    amount_out: int
    minimum_amount_out: int
    swap_fee: int


def cached_amm_v4(snapshot, hint, context, unix_timestamp):
    unsigned(unix_timestamp)
    d = snapshot.get(hint.pool, context, PROGRAM).data
    if len(d) != 752:
        raise ValueError("Invalid AMM v4 pool length")
    num = lambda o: int.from_bytes(d[o : o + 8], "little")
    key = lambda o: Pubkey.from_bytes(d[o : o + 32])
    if num(0) not in (1, 6, 7) or (num(0) == 7 and unix_timestamp < num(224)):
        raise ValueError("AMM v4 swap is disabled or not open")
    if (
        num(8) > 255
        or Pubkey.create_program_address([b"amm authority", bytes([num(8)])], PROGRAM)
        != AUTHORITY
    ):
        raise ValueError("AMM v4 authority nonce mismatch")
    hint.matches(key(400), key(432))
    if key(336) == key(368):
        raise ValueError("AMM v4 vaults collide")
    numerator, denominator = num(176), num(184)
    if not denominator or numerator >= denominator:
        raise ValueError("Invalid AMM v4 swap fee")
    reserves = []
    for vault_offset, mint_offset, pnl_offset, decimals_offset in [
        (336, 400, 192, 32),
        (368, 432, 200, 40),
    ]:
        mint = snapshot.get(key(mint_offset), context, TOKEN_PROGRAM)
        token_transfer_fee_for_epoch(mint.data, mint.owner, context.epoch)
        if mint.data[44] != num(decimals_offset):
            raise ValueError("AMM v4 mint decimals mismatch")
        v = snapshot.get(key(vault_offset), context, TOKEN_PROGRAM).data
        if (
            len(v) != 165
            or v[:32] != bytes(key(mint_offset))
            or v[32:64] != bytes(AUTHORITY)
            or v[108] != 1
        ):
            raise ValueError("Invalid AMM v4 vault identity or state")
        amount = int.from_bytes(v[64:72], "little")
        if num(pnl_offset) >= amount:
            raise ValueError("AMM v4 PnL exhausts vault balance")
        reserves.append(amount - num(pnl_offset))
    return CachedAmmV4State(
        hint.pool,
        key(400),
        key(432),
        key(336),
        key(368),
        *reserves,
        numerator,
        denominator
    )


def quote_cached_amm_v4_exact_in(state, amount, coin_in, slippage_bps=0):
    unsigned(amount)
    if (
        not amount
        or type(coin_in) is not bool
        or type(slippage_bps) is not int
        or not 0 <= slippage_bps < 10000
    ):
        raise ValueError("Invalid AMM v4 quote request")
    i, o = (
        (state.coin_reserve, state.pc_reserve)
        if coin_in
        else (state.pc_reserve, state.coin_reserve)
    )
    if (
        not unsigned(i)
        or not unsigned(o)
        or not unsigned(state.swap_fee_denominator)
        or unsigned(state.swap_fee_numerator) >= state.swap_fee_denominator
    ):
        raise ValueError("Invalid AMM v4 reserves or fee")
    fee = ceil(amount * state.swap_fee_numerator, state.swap_fee_denominator)
    net = amount - fee
    out = o * net // (i + net)
    return AmmV4Quote(amount, out, out * (10000 - slippage_bps) // 10000, fee)


def prepare_cached_amm_v4(
    snapshot, hint, context, unix_timestamp, payer, amount, slippage_bps=0
):
    state = cached_amm_v4(snapshot, hint, context, unix_timestamp)
    quote = quote_cached_amm_v4_exact_in(
        state, amount, hint.input_mint == state.coin_mint, slippage_bps
    )
    if not quote.minimum_amount_out:
        raise ValueError("AMM v4 quote has zero protected output")
    keys = [
        TOKEN_PROGRAM,
        state.pool,
        AUTHORITY,
        state.coin_vault,
        state.pc_vault,
        get_associated_token_address(payer, hint.input_mint, TOKEN_PROGRAM),
        get_associated_token_address(payer, hint.output_mint, TOKEN_PROGRAM),
        payer,
    ]
    ix = Instruction(
        PROGRAM,
        bytes([16]) + struct.pack("<QQ", quote.amount_in, quote.minimum_amount_out),
        [AccountMeta(k, i == 7, i in (1, 3, 4, 5, 6)) for i, k in enumerate(keys)],
    )
    return state, quote, ix
