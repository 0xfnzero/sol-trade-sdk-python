"""Offline all-default-pool buy/sell replay; no RPC or broadcast."""
from pathlib import Path
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from sol_trade_sdk import PumpSwapRoutingConfig, PumpSwapQuoteRequest
from examples.pumpswap_cached_prepare import load_snapshot


def replay_global_routing():
    path = Path(__file__).resolve().parents[1] / 'tests/fixtures/pumpswap_ttwo_route_accounts.json'
    data, snapshot, context = load_snapshot(path)
    config = PumpSwapRoutingConfig()
    search = data['route_search']
    endpoints = [Pubkey.from_string(search[k]) for k in ('pool', 'token_mint', 'asset_mint')]
    payer = Keypair().pubkey()
    return [config.prepare(snapshot, *endpoints,
            PumpSwapQuoteRequest(payer, 1000000 if buy else 1000000000, data['unix_timestamp']),
            context, buy) for buy in (True, False)]


if __name__ == '__main__':
    for result in replay_global_routing():
        print(result.trade.minimum_output_credit)
