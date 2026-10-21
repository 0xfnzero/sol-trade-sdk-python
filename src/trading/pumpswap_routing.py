"""Instance-owned offline bridge registry; account snapshots remain caller supplied."""
from dataclasses import replace
from solders.pubkey import Pubkey
from ..stock_catalog import screened_stock_catalog
from .subscription_cache import PoolTradeHint
from .pumpswap_preparation import _build_pumpswap_topology, canonical, PumpSwapRouteSearch, prepare_best_pumpswap_trade


def _canonical_pools(pools):
    result = {}
    for h in pools:
        a, b = canonical(h.input_mint), canonical(h.output_mint)
        if a == b or Pubkey.default() in (a, b, h.pool):
            raise ValueError('Invalid bridge identity')
        old = result.get(h.pool)
        if old and {old.input_mint, old.output_mint} != {a, b}:
            raise ValueError('Conflicting bridge identity')
        if not old:
            result[h.pool] = replace(h, input_mint=a, output_mint=b)
    if len(result) > 128:
        raise ValueError('At most 128 bridge pools')
    return tuple(result.values())


class PumpSwapRoutingConfig:
    """None loads defaults; an empty sequence enables custom-only configuration."""
    def __init__(self, pools=None):
        if pools is None:
            key = Pubkey.from_string
            pools = [PoolTradeHint(key('58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2'),
                key('So11111111111111111111111111111111111111112'), key('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'))]
            pools += [PoolTradeHint(key(p['pool']), key(p['quote_mint']), key(p['mint'])) for p in screened_stock_catalog()['pools']]
        self._pools = _canonical_pools(pools)
        self._topology = _build_pumpswap_topology(self._pools)
        self.bridge_slippage_bps = 100
        self.maximum_bridge_price_impact_bps = 100
        self.maximum_conversion_hops = 2
        self.maximum_search_nodes = 512
        self.maximum_arrays = 6

    @property
    def conversion_pools(self):
        return self._pools

    def extend_pools(self, pools):
        merged = _canonical_pools((*self._pools, *pools))
        topology = _build_pumpswap_topology(merged)
        self._pools, self._topology = merged, topology

    def prepare(self, snapshot, pool, token_mint, asset_mint, request, context, is_buy):
        search = PumpSwapRouteSearch(pool, token_mint, asset_mint, self._pools,
            self.maximum_conversion_hops, self.maximum_search_nodes,
            self.bridge_slippage_bps, self.maximum_bridge_price_impact_bps)
        return prepare_best_pumpswap_trade(snapshot, search, replace(request, maximum_arrays=self.maximum_arrays), context, is_buy, _topology=self._topology)
