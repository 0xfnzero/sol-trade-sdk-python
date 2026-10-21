"""Offline PumpSwap route preparation, bounded output ranking and signed builds.

Only supplied subscription accounts and candidate pools are read. A prepared
value is bound to its payer and quote context; buy/sell are quoted independently.
"""
from dataclasses import dataclass, field, replace
import struct
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from ..instruction import pumpswap_builder as ps
from ..instruction.stonkfun import unsigned
from ..serialization.v1 import V1Config, compile_v1_message, sign_v1_transaction
from .subscription_cache import PoolTradeHint
from .subscription_readiness import CacheNotReadyError
from .native_sol import settle_cached_route_with_native_sol


SOL_MINT = ps.SOL_TOKEN_ACCOUNT

def canonical(mint):
    return ps.WSOL_TOKEN_ACCOUNT if mint == SOL_MINT else mint


@dataclass(frozen=True)
class PumpSwapQuoteRequest:
    payer: Pubkey
    amount_in: int
    unix_timestamp: int
    slippage_bps: int = 100
    maximum_arrays: int = 8

    def __post_init__(self):
        unsigned(self.amount_in)
        unsigned(self.unix_timestamp)
        if (self.payer == Pubkey.default() or not self.amount_in
            or type(self.slippage_bps) is not int or not 0 <= self.slippage_bps < 10000
            or type(self.maximum_arrays) is not int or not 1 <= self.maximum_arrays <= 32):
            raise ValueError("Invalid cached PumpSwap quote request")


@dataclass(frozen=True)
class PumpSwapBuildOptions:
    recent_blockhash: object
    version: str = "v1"
    address_lookup_tables: tuple = ()
    nonce_account: Pubkey | None = None
    nonce_hash: object = None
    tip_account: Pubkey | None = None
    tip_lamports: int = 0
    config: V1Config = field(default_factory=lambda: V1Config(compute_unit_limit=300000))
    temporary_wsol_seed: str = ""
    rent_lamports: int = 0
    protocol_middleware: object = None
    transaction_middleware: object = None
    create_associated_accounts: bool = True


@dataclass(frozen=True)
class SignedPumpSwapTransaction:
    wire: bytes
    message: bytes
    signature: object
    instructions: tuple
    required_native_lamports: int
    version: str


@dataclass(frozen=True)
class PreparedPumpSwapTrade:
    route: object
    input_mint: Pubkey
    output_mint: Pubkey
    request: PumpSwapQuoteRequest
    context: object
    is_buy: bool
    _guard: object = field(repr=False, compare=False)

    @property
    def steps(self):
        return self.route.legs

    @property
    def minimum_output_credit(self):
        return self.route.minimum_net_amount_out

    def validate_freshness(self, current):
        self._guard()
        if current.epoch != self.context.epoch:
            raise ValueError("PumpSwap preparation epoch changed; reprepare")
        if current.slot < self.context.slot:
            raise ValueError("PumpSwap preparation is from a future slot")
        if current.slot - self.context.slot > min(current.maximum_slot_age, self.context.maximum_slot_age):
            raise ValueError("PumpSwap preparation expired; reprepare")

    def build_transaction(self, signer, current, options):
        """Sign locally; nonce/blockhash validity and middleware I/O are caller-owned."""
        self.validate_freshness(current)
        if signer.pubkey() != self.request.payer:
            raise ValueError("PumpSwap signer differs from prepared payer")
        if options.version not in ("v0", "v1"):
            raise ValueError("Choose explicit v0 or v1 transaction version")
        if (options.nonce_account is None) != (options.nonce_hash is None):
            raise ValueError("Durable nonce requires both account and hash")
        if options.version == "v1" and options.address_lookup_tables:
            raise ValueError("V1 does not accept address lookup tables")
        payer = self.request.payer
        swaps = self.route.swap_instructions
        if options.protocol_middleware is not None:
            swaps = tuple(options.protocol_middleware(swaps))
        # A middleware that changes accounts/protection is responsible for its own
        # quote semantics. Native settlement receives the same instructions as execution.
        if type(options.create_associated_accounts) is not bool:
            raise ValueError("create_associated_accounts must be boolean")
        route = self.route if options.create_associated_accounts else replace(self.route, setup_instructions=())
        if swaps != route.swap_instructions:
            legs = tuple(replace(leg, instruction=ix) for leg, ix in zip(route.legs, swaps))
            if len(swaps) != len(route.legs):
                raise ValueError("Protocol middleware must preserve route instruction count")
            route = replace(route, legs=legs, swap_instructions=swaps)
        instructions = route.setup_instructions + swaps
        required = 0
        if self.input_mint == SOL_MINT or self.output_mint == SOL_MINT:
            native = settle_cached_route_with_native_sol(
                route, payer, options.temporary_wsol_seed, options.rent_lamports,
                self.input_mint == SOL_MINT, self.output_mint == SOL_MINT)
            instructions = native.instructions
            required = native.required_lamports
        tip = unsigned(options.tip_lamports)
        if tip:
            if options.tip_account is None or options.tip_account in (Pubkey.default(), payer):
                raise ValueError("Positive tip requires a distinct non-default recipient")
            instructions = tuple(instructions) + (Instruction(ps.SYSTEM_PROGRAM, struct.pack("<IQ", 2, tip), [
                AccountMeta(payer, True, True), AccountMeta(options.tip_account, False, True)]),)
            required = unsigned(required + tip)
        if options.nonce_account is not None:
            if options.nonce_account in (Pubkey.default(), payer):
                raise ValueError("Invalid nonce account")
            nonce = Instruction(ps.SYSTEM_PROGRAM, struct.pack("<I", 4), [
                AccountMeta(options.nonce_account, False, True),
                AccountMeta(Pubkey.from_string("SysvarRecentB1ockHashes11111111111111111111"), False, False),
                AccountMeta(payer, True, False)])
            instructions = (nonce,) + tuple(instructions)
        blockhash = options.nonce_hash if options.nonce_account is not None else options.recent_blockhash
        if options.version == "v0":
            # Validate once using the shared config range/heap checks.
            compile_v1_message(payer, (), blockhash, options.config)
            budget = []
            program = Pubkey.from_string("ComputeBudget111111111111111111111111111111")
            for value, tag in ((options.config.heap_size, 1), (options.config.compute_unit_limit, 2),
                               (options.config.loaded_accounts_data_size_limit, 4)):
                if value is not None:
                    budget.append(Instruction(program, bytes([tag]) + struct.pack("<I", value), []))
            if options.config.priority_fee is not None:
                # V1 priority_fee is total lamports; V0 uses micro-lamports/CU.
                units = options.config.compute_unit_limit
                if not units:
                    raise ValueError("V0 priority fee requires a positive compute unit limit")
                micro = (options.config.priority_fee * 1000000 + units - 1) // units
                unsigned(micro)
                budget.append(Instruction(program, bytes([3]) + struct.pack("<Q", micro), []))
            offset = 1 if options.nonce_account is not None else 0
            instructions = tuple(instructions[:offset]) + tuple(budget) + tuple(instructions[offset:])
        if options.transaction_middleware is not None:
            instructions = tuple(options.transaction_middleware(tuple(instructions)))
        if options.nonce_account is not None and (not instructions or instructions[0] != nonce):
            raise ValueError("Durable nonce advance must remain the first instruction")
        if any(a.is_signer and a.pubkey != payer for ix in instructions for a in ix.accounts):
            raise ValueError("Unsupported extra transaction signer")
        if options.version == "v1":
            compiled = compile_v1_message(payer, instructions, blockhash, options.config)
            wire = sign_v1_transaction(compiled, (signer,))
            message = compiled.message
            from solders.signature import Signature
            signature = Signature.from_bytes(wire[len(message):len(message)+64])
        else:
            h = Hash.from_string(blockhash) if isinstance(blockhash, str) else blockhash
            message_v0 = MessageV0.try_compile(payer, instructions, options.address_lookup_tables, h)
            tx = VersionedTransaction(message_v0, [signer])
            # A concrete Keypair signs in the native constructor. Other solders
            # signer types can supply an empty/presigned signature, so preserve
            # verification for those inputs before returning a signed wire.
            from solders.keypair import Keypair
            if type(signer) is not Keypair:
                tx.verify_and_hash_message()
            wire = bytes(tx)
            if len(wire) > 1232:
                raise ValueError("V0 signed transaction exceeds 1232 bytes; supply ALTs or choose V1")
            from solders.message import to_bytes_versioned
            message = to_bytes_versioned(message_v0)
            signature = tx.signatures[0]
        self.validate_freshness(current)
        return SignedPumpSwapTransaction(wire, message, signature, tuple(instructions), required, options.version)


def prepare_pumpswap_trade(snapshot, hints, input_mint, output_mint, request, context, is_buy, bridge_limits=None):
    snapshot.assert_usable()
    if type(is_buy) is not bool:
        raise ValueError("PumpSwap direction must be boolean")
    hints = tuple(hints)
    if not hints or hints[0].input_mint != canonical(input_mint) or hints[-1].output_mint != canonical(output_mint):
        raise ValueError("PumpSwap route endpoints do not match request")
    if not any(snapshot.get(h.pool, context).owner == ps.PUMPSWAP_PROGRAM for h in hints):
        raise ValueError("PumpSwap route requires a PumpSwap pool")
    route = snapshot.prepare_route(hints, context, request.unix_timestamp, request.payer,
                                   request.amount_in, request.slippage_bps, request.maximum_arrays,
                                   False, bridge_limits)
    return PreparedPumpSwapTrade(route, input_mint, output_mint, request, context, is_buy, snapshot.assert_usable)


@dataclass(frozen=True)
class PumpSwapRouteSearch:
    pool: Pubkey
    token_mint: Pubkey
    asset_mint: Pubkey
    conversion_pools: tuple = ()
    maximum_conversion_hops: int = 2
    maximum_search_nodes: int = 512
    bridge_slippage_bps: int = 100
    maximum_bridge_price_impact_bps: int = 100


@dataclass(frozen=True)
class PumpSwapRouteRejection:
    pools: tuple
    reason: str


@dataclass(frozen=True)
class PumpSwapRouteSelection:
    trade: PreparedPumpSwapTrade
    routes_evaluated: int
    rejected_routes: tuple


def prepare_best_pumpswap_trade(snapshot, search, request, context, is_buy, *, _topology=None):
    if any(type(v) is not int or not 0 <= v < 10000 for v in
           (search.bridge_slippage_bps, search.maximum_bridge_price_impact_bps)):
        raise ValueError("Invalid bridge limits")
    if (len(search.conversion_pools) > 128 or type(search.maximum_conversion_hops) is not int
        or not 0 <= search.maximum_conversion_hops <= 3 or type(search.maximum_search_nodes) is not int
        or not 1 <= search.maximum_search_nodes <= 4096):
        raise ValueError("Invalid PumpSwap route search limits (128 candidates, 3 hops, 4096 nodes maximum)")
    token, asset = canonical(search.token_mint), canonical(search.asset_mint)
    if token == asset:
        raise ValueError("PumpSwap token and payment asset must differ")
    raw = snapshot.get(search.pool, context, ps.PUMPSWAP_PROGRAM).data
    if raw[:8] != bytes([241,154,109,4,17,177,109,188]):
        raise ValueError("Invalid cached PumpSwap pool discriminator")
    pool = ps.decode_pool(raw[8:])
    if pool is None or token not in (pool.base_mint, pool.quote_mint):
        raise ValueError("Token does not belong to selected PumpSwap pool")
    other = pool.quote_mint if token == pool.base_mint else pool.base_mint
    anchor = PoolTradeHint(search.pool, other if is_buy else token, token if is_buy else other)
    snapshot.pumpswap(anchor, context)
    candidates, adjacency = _topology if _topology is not None else _build_pumpswap_topology(search.conversion_pools)
    if search.pool in candidates:
        raise ValueError("Conversion candidates must not reuse selected PumpSwap pool")
    start, target = (asset, other) if is_buy else (other, asset)
    paths, remaining = [], search.maximum_search_nodes
    def walk(mint, path, visited):
        nonlocal remaining
        if not remaining:
            raise ValueError("PumpSwap route search budget exhausted; incomplete search")
        remaining -= 1
        if mint == target:
            paths.append(path)
            return
        if len(path) == search.maximum_conversion_hops:
            return
        for hint in adjacency.get(mint, ()):
            out = hint.output_mint if mint == hint.input_mint else hint.input_mint
            if out == token or out in visited:
                continue
            walk(out, path + (replace(hint, input_mint=mint, output_mint=out),), visited | {out})
    walk(start, (), {start})
    if not paths:
        raise ValueError("No conversion path within supplied candidates and hop limit")
    best, best_key, rejections = None, None, []
    for path in paths:
        path = path + (anchor,) if is_buy else (anchor,) + path
        source, target = (search.asset_mint, search.token_mint) if is_buy else (search.token_mint, search.asset_mint)
        try:
            trade = prepare_pumpswap_trade(snapshot, path, source, target, request, context, is_buy,
                (search.pool, search.bridge_slippage_bps, search.maximum_bridge_price_impact_bps))
        except CacheNotReadyError:
            raise
        except ValueError as error:
            rejections.append(PumpSwapRouteRejection(tuple(h.pool for h in path), str(error)))
            continue
        key = (-trade.minimum_output_credit, len(path), tuple(bytes(h.pool) for h in path))
        if best is None or key < best_key:
            best, best_key = trade, key
    if best is None:
        raise ValueError("No executable PumpSwap route: " + rejections[0].reason)
    return PumpSwapRouteSelection(best, len(paths), tuple(rejections))


def _build_pumpswap_topology(pools):
    candidates = {}
    for hint in pools:
        a, b = canonical(hint.input_mint), canonical(hint.output_mint)
        if a == b or Pubkey.default() in (a, b, hint.pool):
            raise ValueError("Invalid conversion pool identity")
        old = candidates.get(hint.pool)
        if old and {old.input_mint, old.output_mint} != {a, b}:
            raise ValueError("Conflicting conversion mint pairs for pool")
        candidates[hint.pool] = replace(hint, input_mint=a, output_mint=b)
    adjacency = {}
    for address, hint in sorted(candidates.items(), key=lambda item: bytes(item[0])):
        for mint in (hint.input_mint, hint.output_mint):
            adjacency.setdefault(mint, []).append(hint)
    return candidates, {mint: tuple(edges) for mint, edges in adjacency.items()}
