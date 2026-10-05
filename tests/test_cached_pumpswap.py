import json,base64
from pathlib import Path
from dataclasses import replace
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.trading.subscription_cache import CachedAccount,AccountCacheSnapshot,PoolTradeHint,CacheReadContext
cases=json.loads((Path(__file__).parent/'fixtures/cached_pumpswap_state.json').read_text())['cases']
context=CacheReadContext(100,10,0)
def fixture(c):
    accounts={Pubkey.from_string(a['address']):CachedAccount(Pubkey.from_string(a['owner']),base64.b64decode(a['data']),int(a['slot']),int(a['write_version'])) for a in c['accounts']}
    hint=PoolTradeHint(*(Pubkey.from_string(c[k]) for k in ('pool','input_mint','output_mint')))
    return accounts,hint
@pytest.mark.parametrize('c',cases)
def test_current_pumpswap_state(c):
    accounts,hint=fixture(c);s=AccountCacheSnapshot(accounts).pumpswap(hint,context)
    fee=s.fee_basis_points
    assert [str(fee.lp_fee_basis_points),str(fee.protocol_fee_basis_points),str(fee.coin_creator_fee_basis_points)]==c['expected_fees']
    assert (s.base_reserve,s.quote_reserve,s.pool.virtual_quote_reserves)==(1000000,500000,1000)
    assert bytes(s.protocol_fee_recipients[0])==bytes([8])*32
@pytest.mark.parametrize('index,offset',[(0,0),(0,243),(0,8),(1,45),(3,0),(3,108),(5,0),(5,417),(6,0),(6,8)])
def test_corrupt_pumpswap_state(index,offset):
    accounts,hint=fixture(cases[0]);address=Pubkey.from_string(cases[0]['accounts'][index]['address']);a=accounts[address];d=bytearray(a.data);d[offset]=2 if d[offset]==1 else d[offset]^255;accounts[address]=replace(a,data=bytes(d))
    with pytest.raises(ValueError): AccountCacheSnapshot(accounts).pumpswap(hint,context)
@pytest.mark.parametrize('mode',['missing','owner','stale'])
def test_unavailable_pumpswap_config(mode):
    accounts,hint=fixture(cases[0]);key=Pubkey.from_string(cases[0]['accounts'][6]['address'])
    if mode=='missing': del accounts[key]
    elif mode=='owner': accounts[key]=replace(accounts[key],owner=Pubkey.default())
    else: accounts[key]=replace(accounts[key],slot=99)
    with pytest.raises(ValueError): AccountCacheSnapshot(accounts).pumpswap(hint,context)

from sol_trade_sdk.trading.cached_trade import CachedTradeRequest
from sol_trade_sdk.trading.factory import TradeExecutorFactory
payer=Pubkey.from_bytes(bytes([42])*32)
@pytest.mark.parametrize('c',cases)
def test_prepare_independent_pumpswap_directions(c):
    accounts,hint=fixture(c);snapshot=AccountCacheSnapshot(accounts)
    for buy in (True,False):
        leg=hint if buy else PoolTradeHint(hint.pool,hint.output_mint,hint.input_mint)
        _,q,ix=snapshot.prepare_pumpswap(leg,context,payer,10000,100)
        out=int(c['expected_buy_quote' if buy else 'expected_sell_quote'])
        assert (q.amount_out,q.minimum_amount_out)==(out,out-out//100)
        assert int.from_bytes(ix.data[8:16],'little')==10000
        assert int.from_bytes(ix.data[16:24],'little')==q.minimum_amount_out
        assert bytes(ix.accounts[9].pubkey)==bytes([8])*32
        assert bytes(ix.accounts[-2].pubkey)==bytes([10])*32
        assert len(ix.accounts)==(26 if buy else 24)
        request=CachedTradeRequest(dex_type='PumpSwap',trade_type='Buy' if buy else 'Sell',snapshot=snapshot,hints=(leg,),context=context,unix_timestamp=1,payer=payer,amount=10000,recent_blockhash='11111111111111111111111111111111',slippage_bps=100)
        prepared=TradeExecutorFactory.create_cached_executor("PumpSwap").prepare(request)
        assert bytes(prepared.route.swap_instructions[0].data)==bytes(ix.data)
@pytest.mark.parametrize('index,offset,value',[(5,56,8),(5,56,16),(0,244,1),(5,57,0),(5,643,0)])
def test_unavailable_preparation_context(index,offset,value):
    accounts,hint=fixture(cases[0]);key=Pubkey.from_string(cases[0]['accounts'][index]['address']);a=accounts[key];d=bytearray(a.data)
    if offset in (57,643): d[offset:offset+32]=bytes(32)
    else: d[offset]=value
    accounts[key]=replace(a,data=bytes(d))
    if offset==56 and value==16: hint=PoolTradeHint(hint.pool,hint.output_mint,hint.input_mint)
    with pytest.raises(ValueError): AccountCacheSnapshot(accounts).prepare_pumpswap(hint,context,payer,10000,100)

def test_current_mayhem_recipient():
    accounts,hint=fixture(cases[0]);key=hint.pool;a=accounts[key];d=bytearray(a.data);d[243]=1;accounts[key]=replace(a,data=bytes(d))
    _,_,ix=AccountCacheSnapshot(accounts).prepare_pumpswap(hint,context,payer,10000,100)
    assert bytes(ix.accounts[9].pubkey)==bytes([9])*32

@pytest.mark.parametrize('direction',['buy','sell'])
def test_verified_mainnet_wire_without_rpc(direction,monkeypatch):
    import hashlib,requests
    from examples.cached_trade import build
    monkeypatch.setattr(requests,'post',lambda *a,**k:pytest.fail('RPC in hot path'))
    v=json.loads((Path(__file__).parents[1]/'examples/fixtures'/('pumpswap_'+direction+'_mainnet_20261004.json')).read_text())
    route,wire=build(v)
    assert str(route.minimum_net_amount_out)==v['expected']['minimum_amount_out']
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
