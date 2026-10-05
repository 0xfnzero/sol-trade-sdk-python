from ..instruction.pumpswap_builder import PUMPSWAP_PROGRAM as PUMPSWAP
from ..instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID as PUMPFUN
from .cached_pumpfun import _prepare_cached_pumpfun_route_leg
"""Prepare one direction of a direct-instruction route from a frozen cache.

Each leg spends at most the preceding protected net credit. Conservative sizing
may leave an intermediate token balance; it never consumes an existing balance.
Buy and sell are separate calls with independently ordered pool hints.
"""

from .cached_amm_v4 import PROGRAM as AMM_V4
from dataclasses import dataclass
from solders.instruction import Instruction
from ..instruction.native_hops import CLMM, WHIRLPOOL, DLMM
from ..instruction.cached_cpmm import PROGRAM as CPMM
from ..instruction.stonkfun import (
    PROGRAM as LAUNCHLAB,
    quote_launchlab_exact_in,
    build_launchlab_curve_exact_in,
    unsigned,
)
from ..instruction.common import create_associated_token_account_idempotent_instruction


@dataclass(frozen=True)
class CachedRouteLeg:
    hint: object
    amount_in: int
    estimated_net_amount_out: int | None
    minimum_net_amount_out: int
    instruction: Instruction


@dataclass(frozen=True)
class PreparedCachedRoute:
    legs: tuple
    setup_instructions: tuple
    swap_instructions: tuple
    minimum_net_amount_out: int
    # Mint and estimated credit not spent by the next fixed-input leg.
    estimated_intermediate_residuals: tuple


def prepare_cached_route(
    snapshot,
    hints,
    context,
    unix_timestamp,
    payer,
    amount,
    slippage_bps=100,
    maximum_arrays=8,
    allow_pumpfun_native_settlement=False,
):
    hints = tuple(hints)
    unsigned(amount)
    unsigned(unix_timestamp)
    if (
        not amount
        or not 1 <= len(hints) <= 5
        or not isinstance(slippage_bps, int)
        or isinstance(slippage_bps, bool)
        or not 0 <= slippage_bps < 10000
        or not isinstance(maximum_arrays, int)
        or isinstance(maximum_arrays, bool)
        or not 1 <= maximum_arrays <= 32
    ):
        raise ValueError("Invalid cached route request")
    if len({h.pool for h in hints}) != len(hints):
        raise ValueError("Route reuses a pool and would require changed-state quoting")
    mints = [hints[0].input_mint] + [h.output_mint for h in hints]
    if len(set(mints)) != len(mints):
        raise ValueError("Route contains an asset cycle")
    for previous, current in zip(hints, hints[1:]):
        if previous.output_mint != current.input_mint:
            raise ValueError("Disconnected route")
    legs = []
    spend = amount
    for h in hints:
        program = snapshot.get(h.pool, context).owner
        if program == PUMPFUN:
            state,q,ix=_prepare_cached_pumpfun_route_leg(snapshot,h,context,payer,spend,slippage_bps,allow_pumpfun_native_settlement)
            used,estimated,minimum=q.amount_in,q.estimated_net_amount_out,q.minimum_net_amount_out
        elif program == PUMPSWAP:
            _,q,ix=snapshot.prepare_pumpswap(h,context,payer,spend,slippage_bps)
            used,estimated,minimum=q.amount_in,q.amount_out,q.minimum_amount_out
        elif program == CLMM:
            _, q, ix = snapshot.prepare_clmm(
                h, context, unix_timestamp, payer, spend, slippage_bps, maximum_arrays
            )
            used, estimated, minimum = (
                q.amount_in,
                q.estimated_net_amount_out,
                q.minimum_net_amount_out,
            )
        elif program == WHIRLPOOL:
            _, q, ix = snapshot.prepare_whirlpool(
                h, context, unix_timestamp, payer, spend, slippage_bps, maximum_arrays
            )
            used, estimated, minimum = (
                q.amount_in,
                q.estimated_net_amount_out,
                q.minimum_net_amount_out,
            )
        elif program == DLMM:
            _, q, ix = snapshot.prepare_dlmm(
                h, context, unix_timestamp, payer, spend, slippage_bps, maximum_arrays
            )
            used, estimated, minimum = (
                q.amount_in,
                q.estimated_net_amount_out,
                q.minimum_net_amount_out,
            )
        elif program == AMM_V4:
            _, q, ix = snapshot.prepare_amm_v4(h,context,unix_timestamp,payer,spend,slippage_bps)
            used, estimated, minimum = q.amount_in,q.amount_out,q.minimum_amount_out
        elif program == CPMM:
            _, q, ix = snapshot.prepare_cpmm(h, context, unix_timestamp, payer, spend, slippage_bps)
            used, estimated, minimum = q.amount_in, q.amount_out, q.minimum_amount_out
        elif program == LAUNCHLAB:
            a, state = snapshot.launchlab_curve(h, context)
            q = quote_launchlab_exact_in(state, spend, h.input_mint == a.quote_mint, slippage_bps)
            ix = build_launchlab_curve_exact_in(a, payer, q.amount_in, q.minimum_amount_out, h.input_mint == a.quote_mint)
            estimated = quote_launchlab_exact_in(
                state, spend, h.input_mint == a.quote_mint, 0
            ).minimum_amount_out
            used, minimum = q.amount_in, q.minimum_amount_out
        else:
            raise ValueError("Pool protocol has no native cached quote implementation")
        if not 0 < used <= spend or not minimum:
            raise ValueError("Route has zero output or overconsumes input")
        legs.append(CachedRouteLeg(h, used, estimated, minimum, ix))
        spend = minimum
    setup = tuple(
        create_associated_token_account_idempotent_instruction(
            payer, payer, m, snapshot.get(m, context).owner
        )
        for m in mints
    )
    residuals = tuple(
        (a.hint.output_mint, a.estimated_net_amount_out - b.amount_in)
        for a, b in zip(legs, legs[1:])
    )
    return PreparedCachedRoute(
        tuple(legs), setup, tuple(l.instruction for l in legs), spend, residuals
    )
