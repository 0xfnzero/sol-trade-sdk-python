from dataclasses import dataclass


@dataclass(frozen=True)
class PumpV3QuoteState:
    virtual_base: int
    virtual_quote: int
    remaining_base: int
    real_quote: int
    curve_base_balance: int
    migration_fee: int = 0
    protocol_bps: int = 0
    creator_bps: int = 0
    complete: bool = False
    mayhem: bool = False


@dataclass(frozen=True)
class PumpV3Quote:
    curve_base: int = 0
    curve_quote: int = 0
    pool_base: int = 0
    pool_quote: int = 0
    protocol_fee: int = 0
    creator_fee: int = 0

    @property
    def base_out(self):
        return self.curve_base + self.pool_base

    @property
    def quote_in(self):
        return self.curve_quote + self.pool_quote + self.protocol_fee + self.creator_fee


def _validate(s, amount):
    for value in (
        s.virtual_base,
        s.virtual_quote,
        s.remaining_base,
        s.real_quote,
        s.curve_base_balance,
        s.migration_fee,
        s.protocol_bps,
        s.creator_bps,
        amount,
    ):
        if type(value) is not int or not 0 <= value <= 2**64 - 1:
            raise ValueError("Expected u64 state and amount")
    if s.complete:
        raise ValueError("BondingCurveComplete")
    if (
        s.virtual_base <= s.remaining_base
        or s.virtual_quote == 0
        or s.protocol_bps + s.creator_bps > 10000
    ):
        raise ValueError("Invalid curve reserves or fee rates")


def _fee(n, bps):
    return (n * bps + 9999) // 10000


def _net(budget, s):
    n = budget * 10000 // (10000 + s.protocol_bps + s.creator_bps)
    cost = n + _fee(n, s.protocol_bps) + _fee(n, s.creator_bps)
    return n - max(0, cost - budget)


def _curve_cost(n, s):
    return 0 if n == 0 else n * s.virtual_quote // (s.virtual_base - n) + 1


def _pool(s, curve_quote):
    base = s.curve_base_balance - s.remaining_base
    quote = s.real_quote + curve_quote - s.migration_fee
    if base <= 0 or quote <= 0:
        raise ValueError("Empty pool-to-be; fetch actual curve base vault balance")
    return base, quote


def _result(cb, cq, pb, pq, s):
    out = PumpV3Quote(
        cb,
        cq,
        pb,
        pq,
        _fee(cq, s.protocol_bps) + _fee(pq, s.protocol_bps),
        _fee(cq, s.creator_bps) + _fee(pq, s.creator_bps),
    )
    if out.base_out > 2**64 - 1 or out.quote_in > 2**64 - 1:
        raise ValueError("Quote exceeds u64")
    return out


def quote_pump_buy_v3_exact_out(
    s: PumpV3QuoteState, amount: int, partial_fill: bool = False
) -> PumpV3Quote:
    """Resolved curve fee rates; migration_fee is zero for token quotes. No RPC."""
    _validate(s, amount)
    cb = min(amount, s.remaining_base)
    cq = _curve_cost(cb, s)
    if amount <= s.remaining_base:
        return _result(cb, cq, 0, 0, s)
    if s.mayhem:
        if not partial_fill:
            raise ValueError("NotEnoughTokensToBuy")
        return _result(cb, cq, 0, 0, s)
    base, quote = _pool(s, cq)
    pb = amount - cb
    if pb >= base:
        raise ValueError("NotEnoughTokensToBuy")
    pq = (quote * pb + base - pb - 1) // (base - pb)
    return _result(cb, cq, pb, pq, s)


def quote_pump_buy_v3_exact_in(s: PumpV3QuoteState, budget: int) -> PumpV3Quote:
    _validate(s, budget)
    net = _net(budget, s)
    if net <= 1:
        return PumpV3Quote()
    tokens = (net - 1) * s.virtual_base // (s.virtual_quote + net - 1)
    cb = min(tokens, s.remaining_base)
    cq = _curve_cost(cb, s)
    if tokens <= s.remaining_base or s.mayhem:
        return _result(cb, cq, 0, 0, s)
    left = budget - cq - _fee(cq, s.protocol_bps) - _fee(cq, s.creator_bps)
    if left <= 0 or _net(left, s) <= 1:
        return _result(cb, cq, 0, 0, s)
    base, quote = _pool(s, cq)
    leg = _net(left, s)
    pb = (leg - 1) * base // (quote + leg - 1)
    if pb == 0:
        return _result(cb, cq, 0, 0, s)
    # Exact-in spends the net remainder; dust which cannot buy a token stays with the user.
    return _result(cb, cq, pb, leg, s)


def pump_coin_initial_quote_reserves(
    seed,
    quote_base,
    effective_quote,
    initial_base,
    initial_real,
    quote_supply,
    depth,
    max_depth,
):
    """Migrated Q uses base vault and quote vault + signed virtual reserves."""
    if (
        any(
            type(n) is not int or not 0 <= n < 2**64
            for n in (seed, quote_base, initial_base, initial_real, quote_supply)
        )
        or effective_quote <= 0
        or initial_base <= initial_real
        or not 0 <= depth < max_depth
    ):
        raise ValueError("Invalid Pump quote state or CurveDepthExceeded")
    reserves = seed * quote_base // effective_quote
    if (
        not 1 <= reserves < 2**64
        or reserves * initial_real // (initial_base - initial_real) > quote_supply
    ):
        raise ValueError("QuoteReservesOutOfRange")
    return reserves
