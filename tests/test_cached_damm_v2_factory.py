import base64,hashlib,json
from pathlib import Path
from dataclasses import replace
import pytest
from solders.pubkey import Pubkey
from src.trading.cached_trade import CachedTradeRequest,prepare_cached_trade
from src.trading.factory import TradeExecutorFactory
from src.trading.subscription_cache import AccountCacheSnapshot,CachedAccount,PoolTradeHint,CacheReadContext
from examples.cached_damm_v2 import build
ROOT=Path(__file__).parents[1]/'examples/fixtures'
V=json.loads((ROOT/'cached_damm_v2_wsol_buy_20261004.json').read_text())
def request():
    h=PoolTradeHint(*(Pubkey.from_string(V['legs'][0][k]) for k in ('pool','input_mint','output_mint')))
    accounts={Pubkey.from_string(a['pubkey']):CachedAccount(Pubkey.from_string(a['owner']),base64.b64decode(a['data']),int(a['slot']),int(a['write_version'])) for a in V['accounts']}
    return CachedTradeRequest('MeteoraDammV2','Buy',AccountCacheSnapshot(accounts),(h,),CacheReadContext(int(V['read_slot']),int(V['epoch']),int(V['maximum_slot_age'])),int(V['unix_timestamp']),Pubkey.from_string(V['payer']),int(V['amount']),V['recent_blockhash'],fixed_output_amount=int(V['fixed_output_amount']))
@pytest.mark.parametrize('native',[False,True])
def test_factory_wire_for_explicit_endpoints(native,monkeypatch):
    import requests
    monkeypatch.setattr(requests,'post',lambda *a,**kw:pytest.fail('network in preparation'))
    v=json.loads((ROOT/f"cached_damm_v2_{'sol' if native else 'wsol'}_buy_20261004.json").read_text())
    assert hashlib.sha256(build(v)).hexdigest()==v['expected']['wire_sha256']
@pytest.mark.parametrize('sell',[False,True])
def test_direction_and_unknown_estimate(sell):
    r=request()
    if sell:
        h=r.hints[0];r=replace(r,trade_type='Sell',hints=(PoolTradeHint(h.pool,h.output_mint,h.input_mint),))
    p=TradeExecutorFactory.create_cached_executor('MeteoraDammV2').prepare(r)
    assert p.route.legs[0].estimated_net_amount_out is None
    assert p.route.minimum_net_amount_out==r.fixed_output_amount
    assert len(p.route.swap_instructions)==1
    assert p.required_native_lamports==0
    assert not any(str(i.program_id)=='11111111111111111111111111111111' for i in p.instructions)
@pytest.mark.parametrize('minimum',[None,0,-1,1<<64,1.5,True])
def test_missing_or_invalid_threshold(minimum):
    with pytest.raises(ValueError):prepare_cached_trade(replace(request(),fixed_output_amount=minimum))
def test_unquoted_multihop_is_rejected():
    r=request()
    with pytest.raises(ValueError,match='one independent'):prepare_cached_trade(replace(r,hints=r.hints+r.hints))
def test_simulation_evidence_is_not_fabricated():
    v=json.loads((ROOT/'cached_damm_v2_simulations_20261004.json').read_text())
    assert not v['broadcast']
    by_name={r['fixture']:r for r in v['records']}
    assert by_name['cached_damm_v2_sol_buy_20261004.json']['response']['result']['value']['err'] is None
    assert by_name['cached_damm_v2_wsol_buy_20261004.json']['response']['result']['value']['err'] is not None


def test_funded_wsol_positive_simulation_evidence():
    records=json.loads((ROOT/'cached_damm_v2_simulations_20261004.json').read_text())['records']
    r=next(r for r in records if r['fixture']=='cached_damm_v2_funded_wsol_buy_20261004.json')
    assert r['response']['result']['value']['err'] is None
    a=r['input_account_validation']
    assert a['initialized'] and a['wallet_on_curve'] and a['ata_matches']
    assert int(a['wsol_amount'])>=10000 and int(a['wallet_lamports'])>=3000000

@pytest.mark.parametrize('slippage',[-1,10000,10001,1.5,True])
def test_explicit_threshold_still_rejects_invalid_slippage(slippage):
    with pytest.raises(ValueError,match='slippage'):
        prepare_cached_trade(replace(request(),slippage_bps=slippage))
