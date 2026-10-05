"""CLMM cache-only preparation. Caller supplies pool identity and subscribed state."""

from dataclasses import dataclass
from solders.pubkey import Pubkey
from ..calc.clmm import (
    MIN_TICK,
    MAX_TICK,
    ClmmPool,
    ClmmTick,
    clmm_sqrt_price_at_tick,
    clmm_swap_exact_in,
)
from ..instruction.stonkfun import unsigned
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..instruction.common import get_associated_token_address
from ..instruction.native_hops import (
    CLMM,
    RaydiumClmmSwapV2Accounts,
    SwapV2Args,
    build_raydium_clmm_swap_v2,
)

TOKEN = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")


@dataclass(frozen=True)
class CachedClmmQuote:
    amount_in: int
    estimated_net_amount_out: int
    minimum_net_amount_out: int
    # CLMM checks the net output after Token-2022 fees.
    minimum_amount_out: int
    state_slot: int
    epoch: int
    sqrt_price_limit: int


def prepare_cached_clmm(
    snapshot,
    hint,
    context,
    unix_timestamp,
    payer,
    amount,
    slippage_bps=0,
    maximum_arrays=8,
):
    unsigned(amount)
    unsigned(unix_timestamp)
    if (
        not amount
        or isinstance(slippage_bps, bool)
        or not isinstance(slippage_bps, int)
        or not 0 <= slippage_bps < 10000
        or isinstance(maximum_arrays, bool)
        or not isinstance(maximum_arrays, int)
        or not 1 <= maximum_arrays <= 32
    ):
        raise ValueError("Invalid cached CLMM request")
    d = snapshot.get(hint.pool, context, CLMM).data
    if len(d) < 1544 or d[:8] != bytes.fromhex("f7ede3f5d7c3de46") or d[389] & 16:
        raise ValueError("Invalid or disabled CLMM pool")
    number = lambda b, o, n, signed=False: int.from_bytes(b[o : o + n], "little", signed=signed)
    key = lambda o: Pubkey.from_bytes(d[o : o + 32])
    hint.matches(key(73), key(105))
    if unix_timestamp <= number(d, 1080, 8):
        raise ValueError("CLMM pool is not open")
    config = snapshot.get(key(9), context, CLMM).data
    spacing = number(d, 235, 2)
    if (
        len(config) < 55
        or config[:8] != bytes.fromhex("daf42168cbcb2b6f")
        or not spacing
        or number(config, 51, 2) != spacing
    ):
        raise ValueError("Invalid CLMM config")
    mints = [snapshot.get(key(o), context) for o in (73, 105)]
    fees = [token_transfer_fee_for_epoch(a.data, a.owner, context.epoch) for a in mints]
    down = hint.input_mint == key(73)
    fi, fo = (fees[0], fees[1]) if down else (fees[1], fees[0])
    net_input = amount - fi.calculate(amount)
    if not net_input:
        raise ValueError("CLMM input is zero after transfer fee")
    pool = ClmmPool(
        number(d, 253, 16),
        number(d, 237, 16),
        number(d, 269, 4, True),
        spacing,
        number(config, 47, 4),
    )
    step = 60 * spacing
    start = pool.tick_current // step * step
    ticks = []
    arrays = []
    bitmap = None
    extension = None

    def bit(b, o, index):
        return bool(b[o + index // 8] & (1 << (index % 8)))

    for offset in range((MAX_TICK - MIN_TICK) // step + 2):
        next_start = start + (-offset if down else offset) * step
        if next_start > MAX_TICK or next_start + step <= MIN_TICK:
            break
        index = next_start // step
        if -512 <= index < 512:
            initialized = bit(d, 904, index + 512)
        else:
            if extension is None:
                bitmap = Pubkey.find_program_address(
                    [b"pool_tick_array_bitmap_extension", bytes(hint.pool)], CLMM
                )[0]
                extension = snapshot.get(bitmap, context, CLMM).data
                if (
                    len(extension) < 1832
                    or extension[:8] != bytes([60, 150, 36, 219, 97, 128, 139, 153])
                    or extension[8:40] != bytes(hint.pool)
                ):
                    raise ValueError("Invalid CLMM bitmap extension")
            ed = extension
            distance = -index - 513
            pos = index - 512 if index >= 512 else distance // 512 * 512 + 511 - distance % 512
            if not 0 <= pos < 7168:
                raise ValueError("CLMM bitmap index outside range")
            initialized = bit(ed, 40 if index >= 512 else 936, pos)
        if not initialized:
            continue
        address = Pubkey.find_program_address(
            [
                b"tick_array",
                bytes(hint.pool),
                next_start.to_bytes(4, "big", signed=True),
            ],
            CLMM,
        )[0]
        td = snapshot.get(address, context, CLMM).data
        if (
            len(td) < 10240
            or td[:8] != bytes([192, 155, 85, 205, 49, 249, 129, 42])
            or td[8:40] != bytes(hint.pool)
            or number(td, 40, 4, True) != next_start
        ):
            raise ValueError("Invalid CLMM tick array")
        for i in range(60):
            o = 44 + i * 168
            gross, orders, partial = (
                number(td, o + 20, 16),
                number(td, o + 124, 8),
                number(td, o + 132, 8),
            )
            if gross or orders or partial:
                tick = number(td, o, 4, True)
                if tick != next_start + i * spacing:
                    raise ValueError("CLMM tick index mismatch")
                ticks.append(ClmmTick(tick, number(td, o + 4, 16, True), gross, orders, partial))
        arrays.append(address)
        if len(arrays) > maximum_arrays:
            raise ValueError("CLMM quote exceeds array budget")
        boundary = max(next_start, MIN_TICK) if down else min(next_start + step - 1, MAX_TICK)
        limit = clmm_sqrt_price_at_tick(boundary)
        if limit >= pool.sqrt_price if down else limit <= pool.sqrt_price:
            continue
        result = clmm_swap_exact_in(
            pool, ticks, net_input, limit, d[390], d[1096:1176], unix_timestamp, down
        )
        if result.consumed == net_input:
            net = result.amount_out - fo.calculate(result.amount_out)
            minimum = net * (10000 - slippage_bps) // 10000
            if not minimum:
                raise ValueError("CLMM quote has zero protected output")
            quote = CachedClmmQuote(
                amount, net, minimum, minimum, context.slot, context.epoch, limit
            )
            a = RaydiumClmmSwapV2Accounts(
                payer,
                key(9),
                hint.pool,
                get_associated_token_address(payer, hint.input_mint, mints[0 if down else 1].owner),
                get_associated_token_address(
                    payer, hint.output_mint, mints[1 if down else 0].owner
                ),
                key(137 if down else 169),
                key(169 if down else 137),
                key(201),
                TOKEN,
                TOKEN2022,
                hint.input_mint,
                hint.output_mint,
                tuple(arrays),
                bitmap,
            )
            return (
                a,
                quote,
                build_raydium_clmm_swap_v2(a, SwapV2Args(amount, minimum, limit)),
            )
        if len(arrays) >= maximum_arrays:
            raise ValueError("CLMM quote exceeds array budget")
    raise ValueError("Insufficient CLMM liquidity in supplied snapshot")
