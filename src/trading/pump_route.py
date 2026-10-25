"""Select official execution from current cache state, with no guessed hop quotes."""
from ..instruction.pump_route import PumpRouteOptions, PumpRouteExecution, select_pump_route
from ..instruction.pump_compact_accounts import PUMP, AMM, WSOL, PumpMultiHop
from ..instruction.common import get_associated_token_address as ata, create_associated_token_account_idempotent_instruction as create_ata
from .cached_pumpfun import cached_pumpfun
from .cached_pumpswap import cached_pumpswap
from .cached_route import PreparedCachedRoute


def prepare_official_pump_route(snapshot, hints, context, payer, amount, options=None, native_settlement=False):
    options = options or PumpRouteOptions()
    if not hints:
        raise ValueError("Pump route requires hops")
    source, target = hints[0].input_mint, hints[-1].output_mint
    def fallback():
        return select_pump_route(options, payer, source, target, amount)
    if options.execution == PumpRouteExecution.SEQUENTIAL or options.minimum_output_amount is None or options.buyback_recipient is None or native_settlement or not 2 <= len(hints) <= 3:
        fallback()
        return None
    programs = [snapshot.get(h.pool, context).owner for h in hints]
    if any(p not in (PUMP, AMM) for p in programs):
        fallback()
        return None
    hops = []
    zero = lambda f: f.basis_points == 0 or f.maximum_fee == 0
    for i, h in enumerate(hints):
        if i and hints[i-1].output_mint != h.input_mint:
            fallback()
            return None
        if programs[i] == PUMP:
            s = cached_pumpfun(snapshot, h, context)
            hops.append(PumpMultiHop("curve", s.mint, s.quote, h.pool,
                ata(h.pool, s.mint, s.token_program), ata(h.pool, s.quote, s.quote_token_program),
                s.token_program, s.quote_token_program, s.curve.is_mayhem_mode, s.curve.is_cashback_coin, s.curve.complete))
        else:
            s = cached_pumpswap(snapshot, h, context)
            p = s.pool
            if s.disable_flags & (8 if h.input_mint == p.quote_mint else 16):
                raise ValueError("PumpSwap direction is disabled")
            if options.buyback_recipient not in s.buyback_fee_recipients:
                raise ValueError("Pump buyback recipient is not in current GlobalConfig")
            if not zero(s.base_transfer_fee) or not zero(s.quote_transfer_fee):
                fallback()
                return None
            hops.append(PumpMultiHop("pool", p.base_mint, p.quote_mint, h.pool,
                p.pool_base_token_account, p.pool_quote_token_account, s.base_token_program, s.quote_token_program,
                p.is_mayhem_mode, p.is_cashback_coin, True, p.index, p.creator))
    buy = source == hops[0].quote_mint
    currency = hops[0] if buy else hops[-1]
    if currency.venue == "curve" and currency.quote_mint == WSOL:
        fallback()  # Official curve currency settles wallet SOL, not WSOL balances.
        return None
    ix = select_pump_route(options, payer, source, target, amount, hops)
    if ix is None:
        return None
    endpoints = ((source, hops[0].quote_token_program if buy else hops[0].base_token_program, payer),
                 (target, hops[-1].base_token_program if buy else hops[-1].quote_token_program, payer),
                 (currency.quote_mint, currency.quote_token_program, options.buyback_recipient))
    setup = tuple(create_ata(payer, owner, mint, program) for mint, program, owner in endpoints)
    snapshot.assert_usable()
    return PreparedCachedRoute((), setup, (ix,), options.minimum_output_amount, (), PumpRouteExecution.OFFICIAL)
