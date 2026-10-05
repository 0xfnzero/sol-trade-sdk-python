"""Native Orca exact-in traversal, including adaptive fee reference/spacing rules.

Integer reference: orca_whirlpools_core 2.1.1 (Rust SDK 5.0.6).
No RPC, floating point or Rust runtime bindings.
"""

from dataclasses import dataclass
from bisect import bisect_right
from .clmm import ClmmPool, ClmmTick, clmm_swap_step, MIN_TICK, MAX_TICK, Q64
from ..instruction.stonkfun import unsigned, ceil, U128

MIN_SQRT_PRICE = 4295048016
MAX_SQRT_PRICE = 79226673515401279992447579055
POSITIVE = (
    79232123823359799118286999567,
    79236085330515764027303304731,
    79244008939048815603706035061,
    79259858533276714757314932305,
    79291567232598584799939703904,
    79355022692464371645785046466,
    79482085999252804386437311141,
    79736823300114093921829183326,
    80248749790819932309965073892,
    81282483887344747381513967011,
    83390072131320151908154831281,
    87770609709833776024991924138,
    97234110755111693312479820773,
    119332217159966728226237229890,
    179736315981702064433883588727,
    407748233172238350107850275304,
    2098478828474011932436660412517,
    55581415166113811149459800483533,
    38992368544603139932233054999993551,
)
NEGATIVE = (
    18445821805675392311,
    18444899583751176498,
    18443055278223354162,
    18439367220385604838,
    18431993317065449817,
    18417254355718160513,
    18387811781193591352,
    18329067761203520168,
    18212142134806087854,
    17980523815641551639,
    17526086738831147013,
    16651378430235024244,
    15030750278693429944,
    12247334978882834399,
    8131365268884726200,
    3584323654723342297,
    696457651847595233,
    26294789957452057,
    37481735321082,
)


def whirlpool_sqrt_price_at_tick(tick):
    if not isinstance(tick, int) or isinstance(tick, bool) or not MIN_TICK <= tick <= MAX_TICK:
        raise ValueError("Whirlpool tick outside range")
    positive = tick >= 0
    ratio = 1 << (96 if positive else 64)
    for bit, factor in enumerate(POSITIVE if positive else NEGATIVE):
        if abs(tick) & (1 << bit):
            ratio = ratio * factor >> (96 if positive else 64)
    return ratio >> 32 if positive else ratio


def whirlpool_tick_at_sqrt_price(price):
    unsigned(price, U128)
    if not MIN_SQRT_PRICE <= price <= MAX_SQRT_PRICE:
        raise ValueError("Whirlpool price outside range")
    lo, hi = MIN_TICK, MAX_TICK
    while lo < hi:
        middle = (lo + hi + 1) // 2
        if whirlpool_sqrt_price_at_tick(middle) <= price:
            lo = middle
        else:
            hi = middle - 1
    return lo


@dataclass(frozen=True)
class WhirlpoolAdaptiveFee:
    filter_period: int
    decay_period: int
    reduction_factor: int
    control_factor: int
    maximum_volatility: int
    tick_group_size: int
    last_reference_timestamp: int
    last_major_swap_timestamp: int
    volatility_reference: int
    reference_group: int
    volatility: int


@dataclass(frozen=True)
class WhirlpoolSwapResult:
    consumed: int
    amount_out: int
    fee: int
    minimum_fee_rate: int
    maximum_fee_rate: int
    sqrt_price: int
    tick_current: int
    liquidity: int


def whirlpool_swap_exact_in(
    pool, ticks, array_starts, amount, timestamp, down, adaptive=None, limit=0
):
    unsigned(amount)
    unsigned(timestamp)
    unsigned(pool.sqrt_price, U128)
    unsigned(pool.liquidity, U128)
    unsigned(pool.tick_spacing, 65535)
    unsigned(pool.fee_rate, 65535)
    if (
        not amount
        or not pool.tick_spacing
        or not isinstance(down, bool)
        or not isinstance(pool.tick_current, int)
        or isinstance(pool.tick_current, bool)
        or not MIN_TICK <= pool.tick_current <= MAX_TICK
        or not MIN_SQRT_PRICE <= pool.sqrt_price <= MAX_SQRT_PRICE
    ):
        raise ValueError("Invalid Whirlpool pool/input")
    starts = sorted(array_starts)
    step = 88 * pool.tick_spacing
    if (
        not 1 <= len(starts) <= 6
        or any(
            not isinstance(s, int) or isinstance(s, bool) or s % step
            or s > MAX_TICK or s + step <= MIN_TICK
            for s in starts
        )
        or any(b - a != step for a, b in zip(starts, starts[1:]))
    ):
        raise ValueError("Invalid Whirlpool tick array sequence")
    lower = max(starts[0], MIN_TICK)
    upper = min(starts[-1] + step - 1, MAX_TICK)
    unsigned(limit, U128)
    limit = limit or (MIN_SQRT_PRICE if down else MAX_SQRT_PRICE)
    if not MIN_SQRT_PRICE <= limit <= MAX_SQRT_PRICE or (
        limit >= pool.sqrt_price if down else limit <= pool.sqrt_price
    ):
        raise ValueError("Invalid Whirlpool price limit")
    ticks = tuple(ticks)
    for t in ticks:
        if (
            not isinstance(t.tick, int)
            or isinstance(t.tick, bool)
            or not lower <= t.tick <= upper
            or t.tick % pool.tick_spacing
            or not isinstance(t.liquidity_net, int)
            or isinstance(t.liquidity_net, bool)
            or not -(1 << 127) <= t.liquidity_net < 1 << 127
        ):
            raise ValueError("Invalid Whirlpool tick")
    ordered_ticks = ticks if all(a.tick < b.tick for a, b in zip(ticks, ticks[1:])) else tuple(sorted(ticks, key=lambda t: t.tick))
    if any(a.tick == b.tick for a, b in zip(ordered_ticks, ordered_ticks[1:])):
        raise ValueError("Duplicate Whirlpool tick")
    tick_indices = tuple(t.tick for t in ordered_ticks)
    cached_index = cached_price = None
    group = reference = volatility_reference = maximum = control = 0
    group_size = 1
    lower_group = upper_group = None
    if adaptive is not None:
        a = adaptive
        for v in (a.filter_period, a.decay_period, a.reduction_factor, a.tick_group_size):
            unsigned(v, 65535)
        for v in (a.control_factor, a.maximum_volatility, a.volatility_reference, a.volatility):
            unsigned(v, 0xFFFFFFFF)
        unsigned(a.last_reference_timestamp)
        unsigned(a.last_major_swap_timestamp)
        if (
            not a.tick_group_size
            or a.reduction_factor > 10000
            or a.volatility_reference > a.maximum_volatility
            or a.maximum_volatility * a.tick_group_size > 0xFFFFFFFF
            or not isinstance(a.reference_group, int)
            or isinstance(a.reference_group, bool)
            or not -(1 << 31) <= a.reference_group < 1 << 31
        ):
            raise ValueError("Invalid Whirlpool adaptive fee")
        last = max(a.last_reference_timestamp, a.last_major_swap_timestamp)
        if timestamp < last:
            raise ValueError("Whirlpool timestamp predates adaptive reference")
        group_size = a.tick_group_size
        group = pool.tick_current // group_size
        reference = a.reference_group
        volatility_reference = a.volatility_reference
        maximum = a.maximum_volatility
        control = a.control_factor
        if timestamp - a.last_reference_timestamp > 3600 or timestamp - last >= a.decay_period:
            reference = group
            volatility_reference = 0
        elif timestamp - last >= a.filter_period:
            reference = group
            volatility_reference = a.volatility * a.reduction_factor // 10000
        if volatility_reference > maximum:
            raise ValueError("Invalid Whirlpool volatility reference")
        distance = ceil(maximum - volatility_reference, 10000)
        lower_group = (
            reference - distance if (reference - distance) * group_size > MIN_TICK else None
        )
        upper_group = (
            reference + distance if (reference + distance + 1) * group_size < MAX_TICK else None
        )
    current, tick, liquidity, remaining, output, fees = (
        pool.sqrt_price,
        pool.tick_current,
        pool.liquidity,
        amount,
        0,
        0,
    )
    minimum_fee = maximum_fee = pool.fee_rate
    first = True
    for _ in range(8192):
        if not remaining or current == limit:
            return WhirlpoolSwapResult(
                amount - remaining, output, fees, minimum_fee, maximum_fee, current, tick, liquidity
            )
        if tick < lower if down else tick >= upper:
            raise ValueError("Whirlpool quote requires more tick arrays")
        position = bisect_right(tick_indices, tick) - (1 if down else 0)
        next_tick = ordered_ticks[position] if 0 <= position < len(ordered_ticks) else None
        next_index = next_tick.tick if next_tick else lower if down else upper
        if next_index != cached_index:
            cached_index = next_index
            cached_price = whirlpool_sqrt_price_at_tick(next_index)
        next_price = cached_price
        target = max(next_price, limit) if down else min(next_price, limit)
        fee = pool.fee_rate
        bound = target
        skipped = False
        if adaptive is not None:
            volatility = min(volatility_reference + abs(reference - group) * 10000, maximum)
            crossed = volatility * group_size
            fee = min(fee + min(ceil(control * crossed * crossed, 10000000000000), 100000), 100000)
            skipped = not control or not liquidity
            if not skipped and lower_group is not None and group < lower_group:
                skipped = True
                bound = (
                    target
                    if down
                    else min(target, whirlpool_sqrt_price_at_tick(lower_group * group_size))
                )
            elif not skipped and upper_group is not None and group > upper_group:
                skipped = True
                bound = (
                    max(target, whirlpool_sqrt_price_at_tick((upper_group + 1) * group_size))
                    if down
                    else target
                )
            elif not skipped:
                boundary = max(MIN_TICK, min(MAX_TICK, (group if down else group + 1) * group_size))
                price = whirlpool_sqrt_price_at_tick(boundary)
                bound = max(target, price) if down else min(target, price)
        minimum_fee = fee if first else min(minimum_fee, fee)
        maximum_fee = fee if first else max(maximum_fee, fee)
        first = False
        old = current
        result = clmm_swap_step(current, bound, liquidity, remaining, fee, down)
        remaining = unsigned(remaining - result.amount_in - result.fee)
        output = unsigned(output + result.amount_out)
        fees = unsigned(fees + result.fee)
        current = result.sqrt_price
        if current == next_price:
            if next_tick:
                liquidity = unsigned(
                    liquidity + (-next_tick.liquidity_net if down else next_tick.liquidity_net),
                    U128,
                )
            tick = next_index - 1 if down else next_index
        elif current != old:
            tick = whirlpool_tick_at_sqrt_price(current)
        if adaptive is not None:
            if skipped:
                ti = next_index if current == next_price else whirlpool_tick_at_sqrt_price(current)
                on_boundary = ti % group_size == 0 and current == whirlpool_sqrt_price_at_tick(ti)
                last_group = ti // group_size - (1 if not down and on_boundary else 0)
                if last_group < group if down else last_group > group:
                    group = last_group
            group += -1 if down else 1
    raise ValueError("Whirlpool quote iteration budget exhausted")
