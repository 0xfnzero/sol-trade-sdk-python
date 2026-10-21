import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import PumpSwapRoutingConfig, PoolTradeHint
from examples.pumpswap_global_routing import replay_global_routing


def test_defaults_merge_atomically():
    c = PumpSwapRoutingConfig()
    pools = c.conversion_pools
    assert len(pools) == 64
    c.extend_pools(pools + tuple(PoolTradeHint(h.pool,h.output_mint,h.input_mint) for h in pools))
    assert len(c.conversion_pools) == 64
    h = pools[0]
    extra = PoolTradeHint(Pubkey.new_unique(), h.input_mint,h.output_mint)
    with pytest.raises(ValueError,match='Conflicting'):
        c.extend_pools((extra,PoolTradeHint(h.pool,h.input_mint,extra.pool)))
    assert len(c.conversion_pools) == 64
    c.extend_pools((extra,))
    assert len(c.conversion_pools) == 65
    assert PumpSwapRoutingConfig([]).conversion_pools == ()


def test_all_defaults_partial_cache_buy_sell():
    assert [r.trade.minimum_output_credit for r in replay_global_routing()] == [47932572,19264527]


def test_usdc_starts_directly_and_bridge_slippage_is_independent():
    from pathlib import Path
    from solders.keypair import Keypair
    from sol_trade_sdk import PumpSwapQuoteRequest
    from examples.pumpswap_cached_prepare import load_snapshot
    data, snapshot, context = load_snapshot(Path(__file__).parent/'fixtures/pumpswap_ttwo_route_accounts.json')
    endpoints = [Pubkey.from_string(data['route_search'][k]) for k in ('pool','token_mint')]
    usdc = Pubkey.from_string('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')
    config = PumpSwapRoutingConfig()
    request = PumpSwapQuoteRequest(Keypair().pubkey(),1000000,data['unix_timestamp'],500)
    trade = config.prepare(snapshot,*endpoints,usdc,request,context,True).trade
    assert len(trade.steps) == 2
    assert trade.steps[0].hint.input_mint == usdc
    config.bridge_slippage_bps = 0
    tighter = config.prepare(snapshot,*endpoints,usdc,request,context,True).trade
    assert tighter.steps[0].minimum_net_amount_out > trade.steps[0].minimum_net_amount_out
    assert tighter.minimum_output_credit > trade.minimum_output_credit
    config.maximum_bridge_price_impact_bps = 10000
    with pytest.raises(ValueError,match='bridge limits'):
        config.prepare(snapshot,*endpoints,usdc,request,context,True)


def test_bridge_impact_rejects_large_order_and_respects_configured_tolerance():
    from pathlib import Path
    from solders.keypair import Keypair
    from examples.pumpswap_cached_prepare import load_snapshot
    data, snapshot, context = load_snapshot(Path(__file__).parent/'fixtures/pumpswap_ttwo_route_accounts.json')
    h = next(h for h in data['route_search']['conversion_pools'] if h['pool']=='58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2')
    hint = next(p for p in PumpSwapRoutingConfig().conversion_pools if str(p.pool)==h['pool'])
    anchor = Pubkey.from_string(data['route_search']['pool'])
    payer = Keypair().pubkey()
    with pytest.raises(ValueError,match='impact'):
        snapshot.prepare_route((hint,),context,data['unix_timestamp'],payer,10**12,
                               bridge_limits=(anchor,100,0))
    assert snapshot.prepare_route((hint,),context,data['unix_timestamp'],payer,10**12,
                                  bridge_limits=(anchor,100,9999)).minimum_net_amount_out > 0


def test_probes_do_not_build_instructions_and_topology_is_reused():
    from pathlib import Path
    from unittest.mock import patch
    from solders.keypair import Keypair
    from sol_trade_sdk import PumpSwapQuoteRequest
    from sol_trade_sdk.trading import cached_route, pumpswap_preparation
    from examples.pumpswap_cached_prepare import load_snapshot
    data, snapshot, context = load_snapshot(Path(__file__).parent/'fixtures/pumpswap_ttwo_route_accounts.json')
    config = PumpSwapRoutingConfig()
    endpoints = [Pubkey.from_string(data['route_search'][k]) for k in ('pool', 'token_mint', 'asset_mint')]
    request = PumpSwapQuoteRequest(Keypair().pubkey(), 1000000, data['unix_timestamp'])
    # Restrict to the executed path so counts do not include failed alternative candidates.
    selected = config.prepare(snapshot, *endpoints, request, context, True).trade
    hints = tuple(step.hint for step in selected.steps)
    with patch.object(cached_route, 'create_associated_token_account_idempotent_instruction', wraps=cached_route.create_associated_token_account_idempotent_instruction) as ata, \
         patch.object(snapshot, 'prepare_amm_v4', wraps=snapshot.prepare_amm_v4) as amm, \
         patch.object(snapshot, 'prepare_dlmm', wraps=snapshot.prepare_dlmm) as dlmm, \
         patch.object(snapshot, 'prepare_pumpswap', wraps=snapshot.prepare_pumpswap) as pump:
        prepared = snapshot.prepare_route(hints, context, data['unix_timestamp'], request.payer, 1000000,
                                          bridge_limits=(endpoints[0], 100, 100))
        assert prepared.minimum_net_amount_out == 47932572
        assert (ata.call_count, amm.call_count, dlmm.call_count, pump.call_count) == (4, 1, 1, 1)
    with patch.object(pumpswap_preparation, '_build_pumpswap_topology', side_effect=AssertionError('rebuilt in hot path')):
        assert config.prepare(snapshot, *endpoints, request, context, True).trade.minimum_output_credit == 47932572
        from dataclasses import replace
        changed = config.prepare(snapshot, *endpoints, replace(request, amount_in=2000000), context, True).trade
        assert changed.minimum_output_credit != selected.minimum_output_credit
