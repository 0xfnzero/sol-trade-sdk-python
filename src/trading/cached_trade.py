from .subscription_readiness import CacheNotReadyError
from .route_candidates import iterate_candidate_routes
"""High-level native cache -> independent buy/sell -> V1. No implicit RPC."""

from dataclasses import dataclass, field, replace
from typing import Any
import base58
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from ..instruction.common import SYSTEM_PROGRAM
from ..instruction.stonkfun import unsigned
from ..serialization.v1 import V1Config, compile_v1_message, sign_v1_transaction
from .native_sol import settle_cached_route_with_native_sol

PROGRAMS = {
    "PumpFun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "MeteoraDammV2": "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG",
    "PumpSwap": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
    "RaydiumAmmV4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "LaunchLab": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
    "Bonk": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
    "StonkFun": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
    "RaydiumCpmm": "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "RaydiumClmm": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "OrcaWhirlpool": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "MeteoraDlmm": "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
}


@dataclass(frozen=True)
class CachedTradeRequest:
    dex_type: Any
    trade_type: Any
    snapshot: Any
    hints: tuple
    context: Any
    unix_timestamp: int
    payer: Any
    amount: int
    recent_blockhash: str
    slippage_bps: int = 100
    maximum_arrays: int = 8
    v1_config: V1Config = field(
        default_factory=lambda: V1Config(
            compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024
        )
    )
    native_input: bool = False
    native_output: bool = False
    temporary_wsol_seed: str = ""
    rent_lamports: int = 0
    tip_account: Any = None
    tip_lamports: int = 0
    candidates: tuple = ()
    input_mint: Any = None
    output_mint: Any = None
    fixed_output_amount: int | None = None


@dataclass(frozen=True)
class PreparedCachedTrade:
    route: Any
    instructions: tuple
    compiled: Any
    required_native_lamports: int
    estimated_native_residual_lamports: int = 0


def value(v):
    return getattr(v, "value", v)


def prepare_cached_trade(r):
    direction = value(r.trade_type)
    dex = value(r.dex_type)
    if direction not in ("Buy", "Sell"):
        raise ValueError("Cached trade requires independent Buy or Sell")
    if r.snapshot is None: raise ValueError("Missing frozen account snapshot")
    r.snapshot.assert_usable()
    if not r.hints:
        if not r.candidates or r.input_mint is None or r.output_mint is None:
            raise ValueError("Provide explicit hints or candidate pools and endpoint mints")
        failures = []
        for hints in iterate_candidate_routes(r.candidates, r.input_mint, r.output_mint):
            r.snapshot.assert_usable()
            try: return prepare_cached_trade(replace(r, hints=hints, candidates=()))
            except CacheNotReadyError: raise
            except ValueError as error: failures.append(error)
        error = ValueError("No candidate route passed current state validation and quoting")
        error.failures = tuple(failures)
        raise error from failures[-1]
    if dex not in PROGRAMS or not r.hints:
        raise ValueError("Unsupported cached trade protocol or empty path")
    anchor = r.hints[-1 if direction == "Buy" else 0]
    if str(r.snapshot.get(anchor.pool, r.context).owner) != PROGRAMS[dex]:
        raise ValueError("Trade protocol does not match anchor pool")
    if dex in ("StonkFun", "LaunchLab", "Bonk"):
        accounts, _ = (r.snapshot.stonkfun_curve if dex == "StonkFun" else r.snapshot.launchlab_curve)(anchor, r.context)
        token = anchor.output_mint if direction == "Buy" else anchor.input_mint
        if token != accounts.base_mint:
            raise ValueError("LaunchLab anchor direction does not match independent trade type")
    state_native=False
    if dex == 'PumpFun':
        from .cached_pumpfun import cached_pumpfun
        state=cached_pumpfun(r.snapshot,anchor,r.context)
        state_native=str(state.quote)=='So11111111111111111111111111111111111111112'
        if state.mint!=(anchor.output_mint if direction=='Buy' else anchor.input_mint):raise ValueError('PumpFun anchor direction does not match independent trade type')
    if dex == "MeteoraDammV2":
        from .cached_damm_v2 import prepare_explicit_damm_v2_route
        route = prepare_explicit_damm_v2_route(r.snapshot, r.hints, r.context, r.unix_timestamp,
                                             r.payer, r.amount, r.fixed_output_amount, direction)
    else:
        if r.fixed_output_amount is not None:
            raise ValueError("fixed_output_amount is only supported by explicit DAMM v2 preparation")
        route = r.snapshot.prepare_route(
            r.hints,
            r.context,
            r.unix_timestamp,
            r.payer,
            r.amount,
            r.slippage_bps,
            r.maximum_arrays,
            state_native,
        )
    if type(r.native_input) is not bool or type(r.native_output) is not bool:
        raise ValueError("Native endpoint flags must be boolean")
    instructions = route.setup_instructions + route.swap_instructions
    required = 0
    native_residual=0
    if state_native:
        from .pumpfun_settlement import settle_pumpfun_native_quote
        instructions,required,native_residual=settle_pumpfun_native_quote(route,r.payer,r.native_input,r.native_output,r.temporary_wsol_seed,r.rent_lamports)
        if direction=='Sell' and len(route.legs)>1:
            # The curve's surplus stays SOL; only protected credit is wrapped.
            wsol_residual=route.legs[0].minimum_net_amount_out-route.legs[1].amount_in
            route=replace(route,estimated_intermediate_residuals=((route.legs[0].hint.output_mint,wsol_residual),)+route.estimated_intermediate_residuals[1:])
    elif r.native_input or r.native_output:
        n = settle_cached_route_with_native_sol(
            route,
            r.payer,
            r.temporary_wsol_seed,
            r.rent_lamports,
            r.native_input,
            r.native_output,
        )
        instructions = n.instructions
        required = n.required_lamports
    tip = unsigned(r.tip_lamports)
    if tip or r.tip_account is not None:
        if (
            not tip
            or not isinstance(r.tip_account, Pubkey)
            or r.tip_account in (Pubkey.default(), r.payer)
        ):
            raise ValueError("Provide a positive tip and a distinct non-default recipient")
        required = unsigned(required + tip)
        instructions = (
            Instruction(
                SYSTEM_PROGRAM,
                struct.pack("<IQ", 2, tip),
                [AccountMeta(r.payer, True, True), AccountMeta(r.tip_account, False, True)],
            ),
        ) + tuple(instructions)
    config = replace(
        r.v1_config,
        compute_unit_limit=(
            r.v1_config.compute_unit_limit if r.v1_config.compute_unit_limit is not None else 300000
        ),
        loaded_accounts_data_size_limit=(
            r.v1_config.loaded_accounts_data_size_limit
            if r.v1_config.loaded_accounts_data_size_limit is not None
            else 64 * 1024 * 1024
        ),
    )
    compiled = compile_v1_message(r.payer, instructions, r.recent_blockhash, config)
    r.snapshot.assert_usable()
    return PreparedCachedTrade(route, tuple(instructions), compiled, required, native_residual)


class CachedTradeExecutor:
    """Caller-supplied raw-wire transport; submission does not mean confirmed."""

    def __init__(self, dex_type):
        self.dex_type = value(dex_type)

    def prepare(self, request):
        if value(request.dex_type) != self.dex_type:
            raise ValueError("Factory/request protocol mismatch")
        return prepare_cached_trade(request)

    async def execute(self, request, signers, submit):
        if not callable(submit):
            raise ValueError("Provide a raw-wire submission transport")
        prepared = self.prepare(request)
        wire = sign_v1_transaction(prepared.compiled, signers)
        o = len(prepared.compiled.message)
        signature = base58.b58encode(wire[o : o + 64]).decode()
        request.snapshot.assert_usable()
        returned = await submit(bytes(wire), value(request.trade_type))
        if returned != signature:
            raise ValueError("Submission signature does not match signed V1 transaction")
        return dict(
            signature=signature,
            submitted=True,
            confirmed=False,
            minimum_net_amount_out=prepared.route.minimum_net_amount_out,
        )
