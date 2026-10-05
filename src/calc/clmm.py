"""Native Raydium CLMM integer exact-in traversal, including orders/dynamic fees.

Reference semantics: solana-clmm-raydium 0.3.0 and sol-trade-sdk 5.0.6.
No float math, network requests or Rust runtime bindings.
"""

from dataclasses import dataclass
from ..instruction.stonkfun import unsigned, U64, U128, ceil

MIN_TICK = -443636
MAX_TICK = 443636
MIN_SQRT_PRICE = 4295048016
MAX_SQRT_PRICE = 79226673521066979257578248091
Q64 = 1 << 64
FACTORS = (
    0xFFFCB933BD6FB800,
    0xFFF97272373D4000,
    0xFFF2E50F5F657000,
    0xFFE5CACA7E10F000,
    0xFFCB9843D60F7000,
    0xFF973B41FA98E800,
    0xFF2EA16466C9B000,
    0xFE5DEE046A9A3800,
    0xFCBE86C7900BB000,
    0xF987A7253AC65800,
    0xF3392B0822BB6000,
    0xE7159475A2CAF000,
    0xD097F3BDFD2F2000,
    0xA9F746462D9F8000,
    0x70D869A156F31C00,
    0x31BE135F97ED3200,
    0x9AA508B5B85A500,
    0x5D6AF8DEDC582C,
    0x2216E584F5FA,
)


def clmm_sqrt_price_at_tick(tick):
    if (
        not isinstance(tick, int)
        or isinstance(tick, bool)
        or not MIN_TICK <= tick <= MAX_TICK
    ):
        raise ValueError("CLMM tick outside range")
    ratio = Q64
    for bit, factor in enumerate(FACTORS):
        if abs(tick) & (1 << bit):
            ratio = ratio * factor >> 64
    return U128 // ratio if tick > 0 else ratio


def clmm_tick_at_sqrt_price(price):
    unsigned(price, U128)
    if not MIN_SQRT_PRICE <= price < MAX_SQRT_PRICE:
        raise ValueError("CLMM price outside range")
    lo, hi = MIN_TICK, MAX_TICK
    while lo < hi:
        middle = (lo + hi + 1) // 2
        if clmm_sqrt_price_at_tick(middle) <= price:
            lo = middle
        else:
            hi = middle - 1
    return lo


def _delta(a, b, liquidity, token0, round_up):
    low, high = sorted((a, b))
    if low <= 0:
        raise ValueError("CLMM zero sqrt price")
    numerator = liquidity * (high - low) * (Q64 if token0 else 1)
    denominator = high * low if token0 else Q64
    return ceil(numerator, denominator) if round_up else numerator // denominator


@dataclass(frozen=True)
class ClmmSwapStep:
    sqrt_price: int
    amount_in: int
    amount_out: int
    fee: int


def clmm_swap_step(current, target, liquidity, remaining, fee_rate, down):
    unsigned(current, U128)
    unsigned(target, U128)
    unsigned(liquidity, U128)
    unsigned(remaining)
    unsigned(fee_rate, 999999)
    if (
        not isinstance(down, bool)
        or current <= 0
        or target <= 0
        or (target > current if down else target < current)
    ):
        raise ValueError("Invalid CLMM step")
    net = remaining * (1000000 - fee_rate) // 1000000
    needed = _delta(current, target, liquidity, down, True)
    if needed <= net:
        next_price = target
    elif liquidity == 0:
        raise ValueError("CLMM liquidity is zero")
    elif down:
        next_price = ceil(
            (liquidity << 64) * current, (liquidity << 64) + net * current
        )
    else:
        next_price = current + (net << 64) // liquidity
    amount_in = (
        needed
        if next_price == target
        else _delta(current, next_price, liquidity, down, True)
    )
    amount_out = _delta(current, next_price, liquidity, not down, False)
    fee = (
        remaining - amount_in
        if next_price != target
        else ceil(amount_in * fee_rate, 1000000 - fee_rate)
    )
    return ClmmSwapStep(
        unsigned(next_price, U128),
        unsigned(amount_in),
        unsigned(amount_out),
        unsigned(fee),
    )


@dataclass(frozen=True)
class ClmmTick:
    tick: int
    liquidity_net: int
    liquidity_gross: int
    orders: int = 0
    partial_orders: int = 0


@dataclass(frozen=True)
class ClmmPool:
    sqrt_price: int
    liquidity: int
    tick_current: int
    tick_spacing: int
    fee_rate: int


@dataclass(frozen=True)
class ClmmSwapResult:
    consumed: int
    amount_out: int
    sqrt_price: int
    tick_current: int
    liquidity: int


def clmm_swap_exact_in(pool, ticks, amount, limit, fee_on, dynamic, timestamp, down):
    unsigned(amount)
    unsigned(timestamp)
    unsigned(pool.liquidity, U128)
    unsigned(pool.sqrt_price, U128)
    unsigned(limit, U128)
    unsigned(pool.tick_spacing, 65535)
    unsigned(pool.fee_rate, 999999)
    unsigned(fee_on, 2)
    if not isinstance(pool.tick_current, int) or isinstance(pool.tick_current, bool):
        raise ValueError("Invalid CLMM tick")
    if (
        not MIN_SQRT_PRICE <= pool.sqrt_price <= MAX_SQRT_PRICE
        or not MIN_TICK <= pool.tick_current <= MAX_TICK
        or not 1 <= pool.tick_spacing <= 65535
        or not 0 <= pool.fee_rate < 1000000
        or fee_on not in (0, 1, 2)
    ):
        raise ValueError("Invalid CLMM pool")
    if (
        not isinstance(down, bool)
        or not MIN_SQRT_PRICE <= limit <= MAX_SQRT_PRICE
        or (limit >= pool.sqrt_price if down else limit <= pool.sqrt_price)
    ):
        raise ValueError("Invalid CLMM limit")
    if not isinstance(dynamic, (bytes, bytearray, memoryview)):
        raise ValueError("Invalid CLMM dynamic fee bytes")
    d = bytes(dynamic)
    if len(d) != 80:
        raise ValueError("Invalid CLMM dynamic fee bytes")
    number = lambda o, n, signed=False: int.from_bytes(
        d[o : o + n], "little", signed=signed
    )
    input_fee = fee_on == 0 or fee_on == 1 and down or fee_on == 2 and not down
    enabled = any(d)
    group = pool.tick_current // pool.tick_spacing
    reference, volatility_reference, volatility = (
        number(14, 4, True),
        number(18, 4),
        number(22, 4),
    )
    maximum, control = number(10, 4), number(6, 4)
    if enabled:
        if (
            not number(0, 2) > 0
            or not number(2, 2) > number(0, 2)
            or not 1 <= number(4, 2) < 10000
            or not 1 <= control < 100000
            or maximum * pool.tick_spacing > 0xFFFFFFFF
        ):
            raise ValueError("Invalid CLMM dynamic fee params")
        elapsed = max(0, timestamp - number(26, 8))
        if elapsed >= number(0, 2):
            reference = group
            volatility_reference = (
                volatility * number(4, 2) // 10000 if elapsed < number(2, 2) else 0
            )
    ticks = tuple(ticks)
    if len({t.tick for t in ticks}) != len(ticks):
        raise ValueError("Duplicate CLMM tick")
    for t in ticks:
        if (
            not isinstance(t.tick, int)
            or isinstance(t.tick, bool)
            or not isinstance(t.liquidity_net, int)
            or isinstance(t.liquidity_net, bool)
            or not MIN_TICK <= t.tick <= MAX_TICK
            or t.tick % pool.tick_spacing
            or not -(1 << 127) <= t.liquidity_net < 1 << 127
        ):
            raise ValueError("Invalid CLMM tick")
        unsigned(t.liquidity_gross, U128)
    orders = [unsigned(unsigned(t.orders) + unsigned(t.partial_orders)) for t in ticks]
    current, tick, liquidity, remaining, output = (
        pool.sqrt_price,
        pool.tick_current,
        pool.liquidity,
        amount,
        0,
    )
    for _ in range(8192):
        if remaining == 0 or current == limit:
            return ClmmSwapResult(amount - remaining, output, current, tick, liquidity)
        candidates = [
            i
            for i, t in enumerate(ticks)
            if (t.liquidity_gross or orders[i])
            and (t.tick <= tick if down else t.tick > tick)
        ]
        index = (
            min(candidates, key=lambda i: -ticks[i].tick if down else ticks[i].tick)
            if candidates
            else None
        )
        next_tick = (
            ticks[index].tick if index is not None else MIN_TICK if down else MAX_TICK
        )
        next_price = clmm_sqrt_price_at_tick(next_tick)
        target = max(next_price, limit) if down else min(next_price, limit)
        fee, skipped, bound = pool.fee_rate, True, target
        if enabled:
            volatility = min(
                volatility_reference + abs(reference - group) * 10000, maximum
            )
            crossed = volatility * pool.tick_spacing
            fee = min(fee + ceil(control * crossed * crossed, 10000000000000), 100000)
            skipped = liquidity == 0 or volatility == maximum
            if not skipped:
                boundary = max(
                    MIN_TICK,
                    min(MAX_TICK, (group if down else group + 1) * pool.tick_spacing),
                )
                price = clmm_sqrt_price_at_tick(boundary)
                bound = max(target, price) if down else min(target, price)
        old_price = current
        if current != bound:
            step = clmm_swap_step(
                current, bound, liquidity, remaining, fee if input_fee else 0, down
            )
            remaining = unsigned(
                remaining - step.amount_in - (step.fee if input_fee else 0)
            )
            net = (
                step.amount_out
                if input_fee
                else step.amount_out - ceil(step.amount_out * fee, 1000000)
            )
            output = unsigned(output + net)
            current = step.sqrt_price
        if current == next_price:
            if index is None:
                break
            t = ticks[index]
            if orders[index] and remaining:
                square = current * current
                price = (square >> 64) + (1 if not down and square & (Q64 - 1) else 0)
                if not price:
                    raise ValueError("CLMM zero order price")
                fee_amount = ceil(remaining * fee, 1000000) if input_fee else 0
                available = remaining - fee_amount
                matched = available * price // Q64 if down else available * Q64 // price
                gross = min(matched, orders[index])
                if matched > orders[index]:
                    consumed = unsigned(
                        ceil(gross * Q64, price) if down else ceil(gross * price, Q64)
                    )
                    fee_amount = ceil(consumed * fee, 1000000 - fee) if input_fee else 0
                else:
                    consumed = available
                remaining = unsigned(remaining - unsigned(consumed + fee_amount))
                orders[index] -= gross
                output = unsigned(
                    output + gross - (0 if input_fee else ceil(gross * fee, 1000000))
                )
            if t.liquidity_gross and not orders[index]:
                liquidity = unsigned(
                    liquidity + (-t.liquidity_net if down else t.liquidity_net), U128
                )
            tick = (
                next_tick - 1
                if (down and not orders[index]) or (not down and orders[index])
                else next_tick
            )
        elif current != old_price:
            tick = clmm_tick_at_sqrt_price(current)
        if enabled:
            if skipped:
                boundary_tick = next_tick if current == next_price else tick
                group = boundary_tick // pool.tick_spacing
                if not down and boundary_tick % pool.tick_spacing == 0:
                    group -= 1
            group += -1 if down else 1
    if remaining and current != limit:
        raise ValueError("CLMM quote iteration budget exhausted")
    return ClmmSwapResult(amount - remaining, output, current, tick, liquidity)
