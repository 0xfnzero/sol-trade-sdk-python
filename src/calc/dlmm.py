"""Native exact-in DLMM bin walk. Prices are plain Q64.64, never sqrt prices.

Only explicitly loaded arrays are traversed. Transfer fees are an outer layer
resolved by the caller from current-epoch mint state.
"""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_left, bisect_right

Q64 = 1 << 64
PRECISION = 1_000_000_000


@dataclass(frozen=True)
class DlmmStaticFee:
    base_factor: int
    power: int
    control: int
    maximum_volatility: int
    filter_period: int
    decay_period: int
    reduction_factor: int


@dataclass(frozen=True)
class DlmmVariableFee:
    volatility: int
    reference: int
    index_reference: int
    last_timestamp: int


@dataclass(frozen=True)
class DlmmBin:
    bin_id: int
    amount_x: int
    amount_y: int
    price: int
    open_order: int = 0
    processed_order: int = 0
    ask_side: int = 0


@dataclass(frozen=True)
class DlmmPool:
    active_id: int
    bin_step: int
    fee_mode: int
    static: DlmmStaticFee
    variable: DlmmVariableFee


@dataclass(frozen=True)
class DlmmQuote:
    amount_out: int
    remaining_in: int
    bins_crossed: int
    complete: bool
    missing_bin_id: int | None = None


class InsufficientDlmmArrays(ValueError):
    def __init__(self, partial: DlmmQuote):
        self.partial = partial
        super().__init__(f"Missing DLMM bin array for bin {partial.missing_bin_id}")


def _uint(v: int, bits: int) -> None:
    if type(v) is not int or not 0 <= v < 1 << bits:
        raise ValueError("DLMM unsigned integer outside range")


def _sint(v: int, bits: int) -> None:
    if type(v) is not int or not -(1 << (bits - 1)) <= v < 1 << (bits - 1):
        raise ValueError("DLMM signed integer outside range")


def _ceil(a: int, b: int) -> int:
    return (a + b - 1) // b


def dlmm_swap_exact_in(
    pool: DlmmPool,
    bins: list[DlmmBin],
    loaded_arrays: list[int],
    amount: int,
    timestamp: int,
    swap_for_y: bool,
    support_orders: bool = True,
    strict: bool = True,
    exhaustive: bool = False,
) -> DlmmQuote:
    _uint(amount, 64)
    _uint(timestamp, 63)
    if not all(type(v) is bool for v in (swap_for_y, support_orders, strict, exhaustive)):
        raise ValueError("DLMM flags must be boolean")
    sp, vp = pool.static, pool.variable
    _sint(pool.active_id, 32)
    _uint(pool.bin_step, 16)
    if (
        not -443636 <= pool.active_id <= 443636
        or pool.bin_step == 0
        or type(pool.fee_mode) is not int
        or pool.fee_mode not in (0, 1)
    ):
        raise ValueError("Invalid DLMM pool")
    for v, bits in (
        (sp.base_factor, 16),
        (sp.power, 8),
        (sp.control, 32),
        (sp.maximum_volatility, 32),
        (sp.filter_period, 16),
        (sp.decay_period, 16),
        (sp.reduction_factor, 16),
        (vp.volatility, 32),
        (vp.reference, 32),
        (vp.last_timestamp, 63),
    ):
        _uint(v, bits)
    _sint(vp.index_reference, 32)
    if sp.power > 18 or sp.reduction_factor > 10000 or vp.last_timestamp > timestamp:
        raise ValueError("Invalid DLMM fee/time state")
    loaded = set()
    for i in loaded_arrays:
        _sint(i, 64)
        if i in loaded or i * 70 > 443636 or (i + 1) * 70 <= -443636:
            raise ValueError("Invalid/duplicate DLMM array")
        loaded.add(i)
    by_id = {}
    seen = set()
    live_ids = []
    for b in bins:
        _sint(b.bin_id, 32)
        if not -443636 <= b.bin_id <= 443636 or b.bin_id in seen or b.bin_id // 70 not in loaded:
            raise ValueError("Invalid/duplicate/unloaded DLMM bin")
        seen.add(b.bin_id)
        for v, bits in (
            (b.amount_x, 64),
            (b.amount_y, 64),
            (b.price, 128),
            (b.open_order, 64),
            (b.processed_order, 64),
            (b.ask_side, 8),
        ):
            _uint(v, bits)
        if b.price == 0:
            if b.amount_x or b.amount_y or b.open_order or b.processed_order:
                raise ValueError("Zero DLMM price with liquidity")
        else:
            by_id[b.bin_id] = b
            relevant = support_orders and (
                (swap_for_y and b.ask_side == 0) or (not swap_for_y and b.ask_side != 0)
            )
            if (b.amount_y if swap_for_y else b.amount_x) or (
                relevant and (b.processed_order or b.open_order)
            ):
                live_ids.append(b.bin_id)
    live_ids.sort()
    ref, index = vp.reference, vp.index_reference
    elapsed = timestamp - vp.last_timestamp
    if elapsed >= sp.filter_period:
        index = pool.active_id
        ref = vp.volatility * sp.reduction_factor // 10000 if elapsed < sp.decay_period else 0
    fee_input = pool.fee_mode == 0 or not swap_for_y
    step = -1 if swap_for_y else 1
    base_rate = sp.base_factor * pool.bin_step * 10 * 10**sp.power

    # Stop at the current array's edge even if the next live bin is farther
    # away: the next loop must check whether that intervening array is loaded.
    def advance_empty(current):
        position = bisect_left(live_ids, current) - 1 if swap_for_y else bisect_right(live_ids, current)
        array = current // 70
        if 0 <= position < len(live_ids) and live_ids[position] // 70 == array:
            return live_ids[position]
        return array * 70 - 1 if swap_for_y else (array + 1) * 70

    current, remaining, total, crossed = pool.active_id, amount, 0, 0
    lo, hi = (min(loaded) * 70, max(loaded) * 70 + 69) if loaded else (0, -1)
    while remaining and -443636 <= current <= 443636:
        if current // 70 not in loaded:
            if exhaustive:
                if current < lo or current > hi:
                    break
                current = current // 70 * 70 - 1 if swap_for_y else (current // 70 + 1) * 70
                continue
            partial = DlmmQuote(total, remaining, crossed, False, current)
            if strict:
                raise InsufficientDlmmArrays(partial)
            return partial
        b = by_id.get(current)
        if b is None:
            current = advance_empty(current)
            continue
        reserve = b.amount_y if swap_for_y else b.amount_x
        relevant = support_orders and (
            (swap_for_y and b.ask_side == 0) or (not swap_for_y and b.ask_side != 0)
        )
        tiers = (reserve, b.processed_order if relevant else 0, b.open_order if relevant else 0)
        if not any(tiers):
            current = advance_empty(current)
            continue
        volatility = min(ref + abs(index - current) * 10000, sp.maximum_volatility)
        variable = _ceil((volatility * pool.bin_step) ** 2 * sp.control, 100_000_000_000)
        rate = min(base_rate + variable, 100_000_000)
        left = remaining - _ceil(remaining * rate, PRECISION) if fee_input else remaining
        used, out = 0, 0
        numerator, denominator = (Q64, b.price) if swap_for_y else (b.price, Q64)
        for r in tiers:
            if not left:
                break
            if not r:
                continue
            needed = _ceil(r * numerator, denominator)
            if left >= needed:
                consumed, produced = needed, r
            else:
                consumed = left
                produced = left * denominator // numerator
            left -= consumed
            used += consumed
            out += produced
        total += out if fee_input else out - _ceil(out * rate, PRECISION)
        if total >= 1 << 64:
            raise ValueError("DLMM output overflows u64")
        if left:
            remaining -= _ceil(used * PRECISION, PRECISION - rate) if fee_input else used
            crossed += 1
            current += step
        else:
            return DlmmQuote(total, 0, crossed + 1, True)
    return DlmmQuote(total, remaining, crossed + 1, True)
