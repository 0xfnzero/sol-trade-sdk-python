"""Ordered subscription state and parser identity adaptation; never accesses RPC.

Use a separate cache per chosen fork. Freeze a snapshot before preparing a trade;
account freshness is bounded, not a guarantee of an atomic on-chain bank snapshot.
"""

from dataclasses import dataclass
from threading import RLock
from solders.pubkey import Pubkey
from ..instruction.stonkfun import (
    PROGRAM,
    LaunchLabAccountBytes,
    decode_stonkfun_curve,
    decode_launchlab_curve,
    quote_launchlab_exact_in,
    build_stonkfun_curve_exact_in,
    unsigned,
)
from ..instruction.token_mint_state import token_transfer_fee_for_epoch

PROTOCOLS = {
    "PumpFun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "MeteoraDammV2": "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG",
    "PumpSwap": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
    "LaunchLab": str(PROGRAM),
    "RaydiumCpmm": "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "RaydiumClmm": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "OrcaWhirlpool": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "MeteoraDlmm": "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
    "RaydiumAmmV4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
}


@dataclass(frozen=True)
class CachedAccount:
    owner: Pubkey
    data: bytes
    slot: int
    write_version: int

    def __post_init__(self):
        unsigned(self.slot)
        unsigned(self.write_version)
        if not isinstance(self.owner, Pubkey) or not isinstance(
            self.data, (bytes, bytearray, memoryview)
        ):
            raise ValueError("Invalid cached account owner or bytes")
        object.__setattr__(self, "data", bytes(self.data))


@dataclass(frozen=True)
class CacheReadContext:
    slot: int
    epoch: int
    maximum_slot_age: int

    def __post_init__(self):
        for value in (self.slot, self.epoch, self.maximum_slot_age):
            unsigned(value)


@dataclass(frozen=True)
class PoolTradeHint:
    pool: Pubkey
    input_mint: Pubkey
    output_mint: Pubkey

    def __post_init__(self):
        if (
            any(k == Pubkey.default() for k in (self.pool, self.input_mint, self.output_mint))
            or self.input_mint == self.output_mint
        ):
            raise ValueError("Missing or identical pool/mint identity")

    @classmethod
    def from_route_leg(cls, leg):
        field = lambda name: leg[name] if isinstance(leg, dict) else getattr(leg, name)
        if PROTOCOLS.get(field("protocol")) != field("program"):
            raise ValueError("Unsupported or mismatched route protocol")
        if not field("input_mint") or not field("output_mint"):
            raise ValueError("Route mints are unresolved")
        return cls(*(Pubkey.from_string(field(n)) for n in ("pool", "input_mint", "output_mint")))

    def matches(self, base, quote):
        if {self.input_mint, self.output_mint} != {base, quote} or base == quote:
            raise ValueError("Route mint identity mismatch")


class AccountCacheSnapshot:
    def damm_v2(self,hint,context,unix_timestamp):
        from .cached_damm_v2 import cached_damm_v2
        return cached_damm_v2(self,hint,context,unix_timestamp)

    def __init__(self, accounts, continuity_guard=None):
        self.__accounts = dict(accounts)
        self.__continuity_guard = continuity_guard

    def assert_usable(self):
        if self.__continuity_guard is not None: self.__continuity_guard()

    def get_observation(self, key, context):
        """Include explicit closed observations; unknown or stale keys error."""
        self.assert_usable()
        a = self.__accounts.get(key)
        if a is None: raise ValueError(f"Missing cached account: {key}")
        if a.slot > context.slot or context.slot-a.slot > context.maximum_slot_age: raise ValueError("Cached account is future or stale")
        return a

    def get_optional(self, key, context, expected_owner=None):
        """Observed zero-lamport tombstone is absent; an unobserved key errors."""
        self.assert_usable()
        a=self.__accounts.get(key)
        if a is None:raise ValueError(f'Missing cached account: {key}')
        if a.slot>context.slot or context.slot-a.slot>context.maximum_slot_age:raise ValueError('Cached account is future or stale')
        if not a.data:return None
        if expected_owner is not None and a.owner!=expected_owner:raise ValueError('Cached account owner mismatch')
        return a

    def get(self, key, context, expected_owner=None):
        self.assert_usable()
        a = self.__accounts.get(key)
        if a is None:
            raise ValueError(f"Missing cached account: {key}")
        if expected_owner is not None and a.owner != expected_owner:
            raise ValueError("Cached account owner mismatch")
        if a.slot > context.slot or context.slot - a.slot > context.maximum_slot_age:
            raise ValueError("Cached account is future or stale")
        if not a.data:
            raise ValueError("Cached account is closed")
        return a

    def prepare_pumpswap(self,hint,context,payer,amount,slippage_bps=0):
        from .cached_pumpswap import prepare_cached_pumpswap
        return prepare_cached_pumpswap(self,hint,context,payer,amount,slippage_bps)

    def pumpswap(self, hint, context):
        from .cached_pumpswap import cached_pumpswap
        return cached_pumpswap(self, hint, context)

    def stonkfun_curve(self, hint, context):
        return self._launchlab_state(hint, context, True)

    def launchlab_curve(self, hint, context):
        return self._launchlab_state(hint, context, False)

    def _launchlab_state(self, hint, context, strict):
        pool = self.get(hint.pool, context, PROGRAM)
        d = pool.data
        if len(d) < 429 or d[:8] != bytes.fromhex("f7ede3f5d7c3de46"):
            raise ValueError("Invalid cached LaunchLab pool")
        key = lambda o: Pubkey.from_bytes(d[o : o + 32])
        hint.matches(key(205), key(237))
        global_key, platform_key = key(141), key(173)
        g, p = self.get(global_key, context, PROGRAM), self.get(platform_key, context, PROGRAM)
        base, quote = self.get(key(205), context), self.get(key(237), context)
        accounts, state = (decode_stonkfun_curve if strict else decode_launchlab_curve)(
            LaunchLabAccountBytes(hint.pool, pool.owner, pool.data),
            LaunchLabAccountBytes(global_key, g.owner, g.data),
            LaunchLabAccountBytes(platform_key, p.owner, p.data),
            base.owner,
            quote.owner,
            token_transfer_fee_for_epoch(base.data, base.owner, context.epoch),
            token_transfer_fee_for_epoch(quote.data, quote.owner, context.epoch),
        )
        if (
            state.curve_type != 0
            or sum((state.trade_fee_rate, state.platform_fee_rate, state.creator_fee_rate))
            >= 1000000
        ):
            raise ValueError("Invalid cached LaunchLab curve or fee configuration")
        return accounts, state

    def amm_v4(self, hint, context, unix_timestamp):
        from .cached_amm_v4 import cached_amm_v4

        return cached_amm_v4(self, hint, context, unix_timestamp)

    def prepare_amm_v4(self, hint, context, unix_timestamp, payer, amount, slippage_bps=0):
        from .cached_amm_v4 import prepare_cached_amm_v4

        return prepare_cached_amm_v4(
            self, hint, context, unix_timestamp, payer, amount, slippage_bps
        )

    def cpmm(self, hint, context, unix_timestamp):
        from ..instruction.cached_cpmm import PROGRAM as cpmm_program, AUTHORITY, CachedCpmmState

        unsigned(unix_timestamp)
        pool = self.get(hint.pool, context, cpmm_program)
        d = pool.data
        if (
            len(d) < 637
            or d[:8] != bytes.fromhex("f7ede3f5d7c3de46")
            or d[329] & 4
            or d[390] not in (0, 1)
        ):
            raise ValueError("Invalid or disabled cached CPMM pool")
        key = lambda o: Pubkey.from_bytes(d[o : o + 32])
        number = lambda b, o: int.from_bytes(b[o : o + 8], "little")
        hint.matches(key(168), key(200))
        opened = number(d, 373)
        if unix_timestamp < opened:
            raise ValueError("CPMM pool is not open")
        config = self.get(key(8), context, cpmm_program).data
        if len(config) < 236 or config[:8] != bytes.fromhex("daf42168cbcb2b6f"):
            raise ValueError("Invalid cached CPMM config")
        trade, protocol, fund, creator = (number(config, o) for o in (12, 20, 28, 108))
        enabled = bool(d[390])
        if (
            trade + (creator if enabled else 0) >= 1000000
            or protocol + fund > 1000000
            or d[389] > 2
        ):
            raise ValueError("Invalid CPMM fee configuration")

        def reserve(vault, mint, program, offsets):
            v = self.get(vault, context, program).data
            if len(v) < 165 or v[:32] != bytes(mint) or v[32:64] != bytes(AUTHORITY) or v[108] != 1:
                raise ValueError("Invalid cached CPMM vault")
            return unsigned(number(v, 64) - sum(number(d, o) for o in offsets))

        base = self.get(key(168), context, key(232))
        quote = self.get(key(200), context, key(264))
        return CachedCpmmState(
            hint.pool,
            key(8),
            key(168),
            key(200),
            key(72),
            key(104),
            key(232),
            key(264),
            key(296),
            reserve(key(72), key(168), key(232), (341, 357, 397)),
            reserve(key(104), key(200), key(264), (349, 365, 405)),
            trade,
            protocol,
            fund,
            creator,
            d[389],
            enabled,
            token_transfer_fee_for_epoch(base.data, base.owner, context.epoch),
            token_transfer_fee_for_epoch(quote.data, quote.owner, context.epoch),
            opened,
        )

    def prepare_cpmm(self, hint, context, unix_timestamp, payer, amount, slippage_bps=0):
        from ..instruction.cached_cpmm import quote_cached_cpmm_exact_in, build_cached_cpmm_exact_in

        state = self.cpmm(hint, context, unix_timestamp)
        base_in = hint.input_mint == state.base_mint
        result = quote_cached_cpmm_exact_in(state, amount, base_in, slippage_bps)
        if not result.minimum_amount_out:
            raise ValueError("CPMM quote has zero protected output")
        return (
            state,
            result,
            build_cached_cpmm_exact_in(
                state, payer, result.amount_in, result.minimum_amount_out, base_in
            ),
        )

    def prepare_clmm(
        self, hint, context, unix_timestamp, payer, amount, slippage_bps=0, maximum_arrays=8
    ):
        from .cached_clmm import prepare_cached_clmm

        return prepare_cached_clmm(
            self, hint, context, unix_timestamp, payer, amount, slippage_bps, maximum_arrays
        )

    def prepare_route(
        self, hints, context, unix_timestamp, payer, amount, slippage_bps=100, maximum_arrays=8, allow_pumpfun_native_settlement=False
    ):
        from .cached_route import prepare_cached_route

        return prepare_cached_route(
            self, hints, context, unix_timestamp, payer, amount, slippage_bps, maximum_arrays, allow_pumpfun_native_settlement
        )

    def prepare_dlmm(
        self, hint, context, unix_timestamp, payer, amount, slippage_bps=0, maximum_arrays=8
    ):
        from .cached_dlmm import prepare_cached_dlmm

        return prepare_cached_dlmm(
            self, hint, context, unix_timestamp, payer, amount, slippage_bps, maximum_arrays
        )

    def prepare_whirlpool(
        self, hint, context, unix_timestamp, payer, amount, slippage_bps=0, maximum_arrays=6
    ):
        from .cached_whirlpool import prepare_cached_whirlpool

        return prepare_cached_whirlpool(
            self, hint, context, unix_timestamp, payer, amount, slippage_bps, maximum_arrays
        )

    def prepare_stonkfun_curve(self, hint, context, payer, amount, slippage_bps=0):
        accounts, state = self.stonkfun_curve(hint, context)
        buy = hint.input_mint == accounts.quote_mint
        result = quote_launchlab_exact_in(state, amount, buy, slippage_bps)
        instruction = build_stonkfun_curve_exact_in(
            accounts, payer, result.amount_in, result.minimum_amount_out, buy
        )
        return accounts, result, instruction


class SubscriptionAccountCache:
    def __init__(self):
        self.__accounts = {}
        self.__lock = RLock()
        self.__conflicted = False

    def _assert_no_conflict(self):
        with self.__lock:
            if self.__conflicted:
                raise ValueError("Conflicting cached account version; create a new cache for the explicitly selected fork")

    def update(self, key, account):
        return bool(self.update_many([(key, account)]))

    def update_many(self, updates):
        """Atomic batch: reject all changes on a conflicting equal version."""
        with self.__lock:
            self._assert_no_conflict()
            # Stage only touched identities; do not copy the subscription map
            # for every incoming account. Commit after the entire batch validates.
            pending = {}
            changed = 0
            for key, a in updates:
                unsigned(a.slot)
                unsigned(a.write_version)
                owned = CachedAccount(a.owner, bytes(a.data), a.slot, a.write_version)
                old = pending.get(key, self.__accounts.get(key))
                version = (a.slot, a.write_version)
                if old is not None:
                    previous = (old.slot, old.write_version)
                    if version < previous:
                        continue
                    if version == previous:
                        if owned != old:
                            self.__conflicted = True
                            raise ValueError(
                                "Conflicting cached account version; select a fork explicitly"
                            )
                        continue
                pending[key] = owned
                changed += 1
            self.__accounts.update(pending)
            return changed

    def update_from_parser(self, event):
        a = event.account
        return self.update(
            Pubkey.from_string(a.pubkey),
            CachedAccount(
                Pubkey.from_string(a.owner),
                bytes(a.data) if a.lamports else b"",
                event.metadata.slot,
                event.write_version,
            ),
        )

    def _snapshot_accounts(self, keys):
        if keys is None:
            return self.__accounts
        self._assert_no_conflict()
        selected = {}
        for key in keys:
            account = self.__accounts.get(key)
            if account is None:
                raise ValueError(f"Missing cached account: {key}")
            selected[key] = account
        return selected

    def ready_snapshot(self, readiness, keys=None):
        """Freeze pre-discovered dependency keys with the same continuity gate."""
        # Exhaust dynamic iterables before reading versions or readiness state.
        keys = None if keys is None else tuple(dict.fromkeys(keys))
        with self.__lock:
            self._assert_no_conflict()
            ready_guard = readiness.guard()
            def check():
                self._assert_no_conflict()
                ready_guard()
            return AccountCacheSnapshot(self._snapshot_accounts(keys), check)

    def snapshot(self, keys=None):
        """O(selected keys), or O(all keys) when omitted; account bytes are immutable."""
        keys = None if keys is None else tuple(dict.fromkeys(keys))
        with self.__lock:
            return AccountCacheSnapshot(self._snapshot_accounts(keys), self._assert_no_conflict)
