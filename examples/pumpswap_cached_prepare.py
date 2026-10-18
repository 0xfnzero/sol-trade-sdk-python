"""Offline captured PumpSwap state -> independently quoted buy/sell -> signed wire.

python -m examples.pumpswap_cached_prepare [buy|sell] [amount] [snapshot.json] [v0|v1]
Historical fixtures, ephemeral signer and blockhash; never submits or calls RPC.
"""
import base64
import json
from pathlib import Path
import sys
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.hash import Hash
from sol_trade_sdk import (
    AccountCacheSnapshot, CachedAccount, CacheReadContext, PoolTradeHint,
    PumpSwapQuoteRequest, PumpSwapRouteSearch, PumpSwapBuildOptions,
    prepare_pumpswap_trade, prepare_best_pumpswap_trade,
)


def load_snapshot(path):
    data = json.loads(Path(path).read_text())
    snapshot = AccountCacheSnapshot({Pubkey.from_string(a['address']): CachedAccount(
        Pubkey.from_string(a['owner']), base64.b64decode(a['data_base64'], validate=True),
        a['slot'], a.get('write_version', 0)) for a in data['accounts']})
    context = CacheReadContext(data['slot'], data['epoch'], data['maximum_slot_age'])
    return data, snapshot, context


def prepare_fixture(path, is_buy, amount, payer):
    data, snapshot, context = load_snapshot(path)
    request = PumpSwapQuoteRequest(payer, amount, data['unix_timestamp'])
    if 'route_search' in data:
        s = data['route_search']
        hints = tuple(PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ('pool','input_mint','output_mint'))) for h in s['conversion_pools'])
        search = PumpSwapRouteSearch(*(Pubkey.from_string(s[k]) for k in ('pool','token_mint','asset_mint')), hints)
        trade = prepare_best_pumpswap_trade(snapshot, search, request, context, is_buy).trade
    else:
        hints = tuple(PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ('pool','input_mint','output_mint'))) for h in data['buy_steps' if is_buy else 'sell_steps'])
        trade = prepare_pumpswap_trade(snapshot, hints, hints[0].input_mint, hints[-1].output_mint, request, context, is_buy)
    return trade, context


def main():
    args = sys.argv[1:]
    direction = args[0] if args else 'buy'
    if direction not in ('buy', 'sell'):
        raise ValueError('Choose buy or sell')
    amount = int(args[1]) if len(args)>1 else (10000 if direction=='buy' else 1000000000)
    path = args[2] if len(args)>2 else Path(__file__).resolve().parents[1]/'tests/fixtures/pumpswap_ttwo_accounts.json'
    version = args[3] if len(args)>3 else 'v1'
    signer = Keypair()
    trade, context = prepare_fixture(path, direction=='buy', amount, signer.pubkey())
    for leg in trade.steps:
        print(f'{leg.hint.pool}: {leg.hint.input_mint} -> {leg.hint.output_mint}, input={leg.amount_in}, protected={leg.minimum_net_amount_out}')
    signed = trade.build_transaction(signer, context, PumpSwapBuildOptions(
        Hash.default(), version=version, temporary_wsol_seed='offline-pumpswap-demo', rent_lamports=2039280))
    assert signed.signature.verify(signer.pubkey(), signed.message)
    print(f'{direction}: protected={trade.minimum_output_credit}; signed {version} bytes={len(signed.wire)}; no RPC/broadcast')


if __name__ == '__main__':
    main()
