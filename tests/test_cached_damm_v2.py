import json,base64,hashlib
from pathlib import Path
from dataclasses import replace
import pytest,requests
from solders.pubkey import Pubkey
from src.trading.subscription_cache import AccountCacheSnapshot,CachedAccount,PoolTradeHint,CacheReadContext
from examples.damm_v2_snapshot import build
V=json.loads((Path(__file__).parents[1]/'examples/fixtures/damm_v2_buy_mainnet_20261004.json').read_text())
H=PoolTradeHint(*(Pubkey.from_string(V['legs'][0][k]) for k in ('pool','input_mint','output_mint')))
C=CacheReadContext(int(V['read_slot']),int(V['epoch']),int(V['maximum_slot_age']))
def accounts():return {Pubkey.from_string(a['pubkey']):CachedAccount(Pubkey.from_string(a['owner']),base64.b64decode(a['data']),int(a['slot']),int(a['write_version'])) for a in V['accounts']}
def test_verified_wire_without_rpc(monkeypatch):
    monkeypatch.setattr(requests,'post',lambda *a,**k:pytest.fail('RPC in preparation'))
    assert hashlib.sha256(build(V)).hexdigest()==V['expected']['wire_sha256']
@pytest.mark.parametrize('failure',['discriminator','owner','status','activation','flag','vault','stale','missing'])
def test_invalid_state(failure):
    a=accounts();p=a[H.pool];d=bytearray(p.data)
    if failure=='discriminator':d[0]^=1
    if failure=='status':d[481]=1
    if failure=='activation':d[472:480]=bytes([255])*8
    if failure=='flag':d[482]=3
    a[H.pool]=replace(p,data=bytes(d),owner=Pubkey.default() if failure=='owner' else p.owner,slot=0 if failure=='stale' else p.slot)
    if failure=='vault':
        k=Pubkey.from_string(V['accounts'][3]['pubkey']);d=bytearray(a[k].data);d[108]=2;a[k]=replace(a[k],data=bytes(d))
    if failure=='missing':del a[Pubkey.from_string(V['accounts'][1]['pubkey'])]
    with pytest.raises(ValueError):AccountCacheSnapshot(a).damm_v2(H,C,int(V['unix_timestamp']))
def test_continuity_failure():
    def broken():raise ValueError('continuity interrupted')
    with pytest.raises(ValueError,match='continuity'):AccountCacheSnapshot(accounts(),broken).damm_v2(H,C,int(V['unix_timestamp']))

@pytest.mark.parametrize('direction',['Buy','Sell'])
def test_preparation_reuses_verified_mints(direction,monkeypatch):
    from src.trading.cached_damm_v2 import prepare_explicit_damm_v2_route
    original=AccountCacheSnapshot.get
    calls=[]
    def counted(snapshot,key,context,expected_owner=None):
        calls.append(key)
        return original(snapshot,key,context,expected_owner)
    monkeypatch.setattr(AccountCacheSnapshot,'get',counted)
    hint=H if direction=='Buy' else PoolTradeHint(H.pool,H.output_mint,H.input_mint)
    route=prepare_explicit_damm_v2_route(AccountCacheSnapshot(accounts()),[hint],C,int(V['unix_timestamp']),Pubkey.from_bytes(bytes([42])*32),10000,1,direction)
    assert len(calls)==5
    assert route.legs[0].estimated_net_amount_out is None


def test_late_preparation_interruption():
    from src.trading.cached_damm_v2 import prepare_explicit_damm_v2_route
    count=0
    def guard():
        nonlocal count
        count+=1
        if count==7:raise ValueError('late continuity interruption')
    with pytest.raises(ValueError,match='late continuity'):
        prepare_explicit_damm_v2_route(AccountCacheSnapshot(accounts(),guard),[H],C,int(V['unix_timestamp']),Pubkey.from_bytes(bytes([42])*32),10000,1)


def test_invalid_preparation_direction():
    from src.trading.cached_damm_v2 import prepare_explicit_damm_v2_route
    with pytest.raises(ValueError,match='one independent'):
        prepare_explicit_damm_v2_route(AccountCacheSnapshot(accounts()),[H],C,int(V['unix_timestamp']),Pubkey.from_bytes(bytes([42])*32),10000,1,'invalid')
