"""Cache-only Orca quote/preparation from fixed or dynamic tick arrays."""

from dataclasses import dataclass
from solders.pubkey import Pubkey
from ..calc.whirlpool import (
    ClmmPool,
    ClmmTick,
    WhirlpoolAdaptiveFee,
    whirlpool_swap_exact_in,
    MIN_TICK,
    MAX_TICK,
)
from ..instruction.stonkfun import unsigned
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..instruction.common import get_associated_token_address
from ..instruction.native_hops import (
    WHIRLPOOL,
    WhirlpoolSwapV2Accounts,
    SwapV2Args,
    build_whirlpool_swap_v2,
)


@dataclass(frozen=True)
class CachedWhirlpoolQuote:
    amount_in: int
    estimated_net_amount_out: int
    minimum_net_amount_out: int
    minimum_amount_out: int
    state_slot: int
    epoch: int
    minimum_fee_rate: int
    maximum_fee_rate: int


def decode_whirlpool_ticks(data, pool, start, spacing):
    if (
        not isinstance(spacing, int)
        or isinstance(spacing, bool)
        or not 1 <= spacing <= 65535
        or not isinstance(start, int)
        or isinstance(start, bool)
        or start % (88 * spacing)
    ):
        raise ValueError("Invalid Whirlpool tick array start/spacing")
    d = bytes(data)
    fixed = d[:8] == bytes([69, 97, 189, 190, 110, 7, 66, 187])
    dynamic = d[:8] == bytes([17, 216, 246, 142, 225, 199, 218, 56])
    if not fixed and not dynamic:
        raise ValueError("Unknown Whirlpool array discriminator")
    offset = 9956 if fixed else 12
    if (
        len(d) < offset + 32
        or len(d) < 12
        or int.from_bytes(d[8:12], "little", signed=True) != start
        or d[offset : offset + 32] != bytes(pool)
    ):
        raise ValueError("Whirlpool array identity mismatch")
    ticks = []
    o = 12 if fixed else 60
    for i in range(88):
        if o >= len(d) or d[o] > 1:
            raise ValueError("Invalid or truncated Whirlpool tick tag")
        initialized = d[o] == 1
        o += 1
        if dynamic and (bool(d[44 + i // 8] & (1 << (i % 8))) != initialized):
            raise ValueError("Whirlpool tick bitmap mismatch")
        if fixed or initialized:
            if o + 112 > len(d):
                raise ValueError("Truncated Whirlpool tick")
            if initialized:
                tick = start + i * spacing
                if not MIN_TICK <= tick <= MAX_TICK:
                    raise ValueError("Whirlpool initialized tick outside range")
                ticks.append(
                    ClmmTick(
                        tick,
                        int.from_bytes(d[o : o + 16], "little", signed=True),
                        int.from_bytes(d[o + 16 : o + 32], "little"),
                    )
                )
            o += 112
    return ticks


def prepare_cached_whirlpool(
    snapshot, hint, context, unix_timestamp, payer, amount, slippage_bps=0, maximum_arrays=6
):
    unsigned(amount)
    unsigned(unix_timestamp)
    if (
        not amount
        or not isinstance(slippage_bps, int)
        or isinstance(slippage_bps, bool)
        or not 0 <= slippage_bps < 10000
        or not isinstance(maximum_arrays, int)
        or isinstance(maximum_arrays, bool)
        or not 1 <= maximum_arrays <= 32
    ):
        raise ValueError("Invalid cached Whirlpool request")
    d = snapshot.get(hint.pool, context, WHIRLPOOL).data
    if len(d) < 653 or d[:8] != bytes([63, 149, 209, 12, 225, 128, 99, 9]):
        raise ValueError("Invalid Whirlpool pool")
    key = lambda o: Pubkey.from_bytes(d[o : o + 32])
    n = lambda b, o, w, signed=False: int.from_bytes(b[o : o + w], "little", signed=signed)
    hint.matches(key(101), key(181))
    spacing = n(d, 41, 2)
    if not spacing:
        raise ValueError("Whirlpool spacing is zero")
    mints = [snapshot.get(key(o), context) for o in (101, 181)]
    fees = [token_transfer_fee_for_epoch(a.data, a.owner, context.epoch) for a in mints]
    down = hint.input_mint == key(101)
    fi, fo = (fees[0], fees[1]) if down else (fees[1], fees[0])
    net_input = amount - fi.calculate(amount)
    if not net_input:
        raise ValueError("Whirlpool input is zero after transfer fee")
    pool = ClmmPool(n(d, 65, 16), n(d, 49, 16), n(d, 81, 4, True), spacing, n(d, 45, 2))
    adaptive = None
    if n(d, 43, 2) != spacing:
        oracle = Pubkey.find_program_address([b"oracle", bytes(hint.pool)], WHIRLPOOL)[0]
        od = snapshot.get(oracle, context, WHIRLPOOL).data
        if (
            len(od) < 110
            or od[:8] != bytes([139, 194, 131, 179, 140, 179, 229, 244])
            or od[8:40] != bytes(hint.pool)
        ):
            raise ValueError("Invalid Whirlpool oracle")
        if unix_timestamp < n(od, 40, 8):
            raise ValueError("Whirlpool trade is not enabled")
        adaptive = WhirlpoolAdaptiveFee(
            n(od, 48, 2),
            n(od, 50, 2),
            n(od, 52, 2),
            n(od, 54, 4),
            n(od, 58, 4),
            n(od, 62, 2),
            n(od, 82, 8),
            n(od, 90, 8),
            n(od, 98, 4),
            n(od, 102, 4, True),
            n(od, 106, 4),
        )
    step = 88 * spacing
    shifted = pool.tick_current + (0 if down else spacing)
    start = shifted // step * step
    arrays = []
    starts = []
    ticks = []
    for i in range(min(maximum_arrays, 6)):
        st = start + (-i if down else i) * step
        if st > MAX_TICK or st + step <= MIN_TICK:
            break
        address = Pubkey.find_program_address(
            [b"tick_array", bytes(hint.pool), str(st).encode()], WHIRLPOOL
        )[0]
        td = snapshot.get(address, context, WHIRLPOOL).data
        ticks.extend(decode_whirlpool_ticks(td, hint.pool, st, spacing))
        starts.append(st)
        arrays.append(address)
        try:
            result = whirlpool_swap_exact_in(
                pool, ticks, starts, net_input, unix_timestamp, down, adaptive
            )
        except ValueError as e:
            if "requires more tick arrays" in str(e):
                continue
            raise
        if result.consumed != net_input:
            continue
        net = result.amount_out - fo.calculate(result.amount_out)
        minimum = net * (10000 - slippage_bps) // 10000
        if not minimum:
            raise ValueError("Whirlpool quote has zero protected output")
        quote = CachedWhirlpoolQuote(
            amount,
            net,
            minimum,
            minimum,
            context.slot,
            context.epoch,
            result.minimum_fee_rate,
            result.maximum_fee_rate,
        )
        while len(arrays) < 3:
            arrays.append(arrays[-1])
        a = WhirlpoolSwapV2Accounts(
            mints[0].owner,
            mints[1].owner,
            payer,
            hint.pool,
            key(101),
            key(181),
            get_associated_token_address(payer, key(101), mints[0].owner),
            key(133),
            get_associated_token_address(payer, key(181), mints[1].owner),
            key(213),
            tuple(arrays),
        )
        return a, quote, build_whirlpool_swap_v2(a, SwapV2Args(amount, minimum), down)
    raise ValueError("Whirlpool quote exceeds loaded array budget")
