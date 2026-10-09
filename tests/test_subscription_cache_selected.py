import base64
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import CachedAccount, CacheReadContext, PoolTradeHint, SubscriptionAccountCache
from sol_trade_sdk.trading.subscription_readiness import SubscriptionReadiness

K = lambda n: Pubkey.from_bytes(bytes([n])*32)
CTX = CacheReadContext(10,0,0)
A = lambda v,data=b'one': CachedAccount(K(9),data,10,v)

def test_selected_isolation_optional_freshness_and_unknown_keys():
    c=SubscriptionAccountCache(); source=bytearray(b'one')
    c.update_many([(K(1),A(1,source)),(K(2),A(1)),(K(3),A(1,b''))])
    s=c.snapshot([K(1),K(1),K(3)]); source[:]=b'bad'; c.update(K(1),A(2,b'two'))
    assert s.get(K(1),CTX).data==b'one'
    assert s.get_optional(K(3),CTX) is None
    for read in [lambda:s.get_optional(K(2),CTX),lambda:c.snapshot([K(4)]),lambda:c.snapshot([]).get(K(1),CTX)]:
        with pytest.raises(ValueError,match='Missing'): read()
    for context in [CacheReadContext(9,0,0),CacheReadContext(11,0,0)]:
        with pytest.raises(ValueError,match='future or stale'):s.get(K(1),context)
    with pytest.raises(ValueError,match='owner'):s.get(K(1),CTX,K(8))

def test_dynamic_iterator_materializes_before_reading_versions():
    c=SubscriptionAccountCache();c.update_many([(K(1),A(1)),(K(2),A(1))])
    def keys():
        yield K(1)
        c.update_many([(K(1),A(2)),(K(2),A(2))])
        yield K(2)
        yield K(1)
    s=c.snapshot(keys());assert s.get(K(1),CTX).write_version==s.get(K(2),CTX).write_version==2

def test_selected_fork_and_readiness_guards():
    c=SubscriptionAccountCache();c.update(K(1),A(1));r=SubscriptionReadiness('fork',[str(K(1))])
    with pytest.raises(ValueError):c.ready_snapshot(r,[K(1)])
    r.mark_validated([str(K(1))],0,'fork');s=c.ready_snapshot(r,[K(1)]);r.interrupt('disconnected')
    with pytest.raises(ValueError,match='disconnected'):s.get(K(1),CTX)
    plain=c.snapshot([K(1)])
    with pytest.raises(ValueError,match='Conflicting'):c.update(K(1),A(1,b'conflict'))
    with pytest.raises(ValueError,match='Conflicting'):plain.get(K(1),CTX)
    with pytest.raises(ValueError,match='Conflicting'):c.snapshot([K(1)])

def test_real_cpmm_six_dependencies_quote_build_parity_and_each_omission_fails():
    f=json.loads((Path(__file__).parents[1]/'examples/fixtures/cpmm_mainnet_20261002.json').read_text());names=['pool','config','base_mint','quote_mint','base_vault','quote_vault'];c=SubscriptionAccountCache();keys=[]
    for name in names:
        v=f[name];key=Pubkey.from_string(v['pubkey']);keys.append(key);c.update(key,CachedAccount(Pubkey.from_string(v['owner']),base64.b64decode(v['data']),int(v['slot']),int(v['write_version'])))
    c.update(K(7),A(1));h=PoolTradeHint(keys[0],keys[2 if f['base_in'] else 3],keys[3 if f['base_in'] else 2]);ctx=CacheReadContext(int(f['read_slot']),int(f['epoch']),int(f['maximum_slot_age']))
    def prepare(s):return s.prepare_cpmm(h,ctx,int(f['unix_timestamp']),Pubkey.from_string(f['payer']),int(f['amount']),f['slippage_bps'])
    assert prepare(c.snapshot(keys))==prepare(c.snapshot())
    for omitted in keys:
        with pytest.raises(ValueError,match='Missing'):prepare(c.snapshot(k for k in keys if k!=omitted))
    r=SubscriptionReadiness('fork',map(str,keys));r.mark_validated(map(str,keys),0,'fork');assert prepare(c.ready_snapshot(r,keys))==prepare(c.snapshot())
