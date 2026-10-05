import json,struct
from pathlib import Path
from dataclasses import replace
import pytest
from solders.pubkey import Pubkey
from src.trading.cached_pumpfun import cached_pumpfun,quote_cached_pumpfun_exact_in,decode_pumpfun_current_fees,prepare_cached_pumpfun,WSOL,PumpFunCurrentFees
from src.trading.subscription_cache import AccountCacheSnapshot,CachedAccount,PoolTradeHint,CacheReadContext
from src.instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID,FEE_PROGRAM,FEE_CONFIG,GLOBAL_ACCOUNT,get_bonding_curve_pda,get_fee_sharing_config_pda

ORACLE=json.loads((Path(__file__).parent/'fixtures/pumpfun_current_fee_oracle_2_0_0.json').read_text())
MINT=Pubkey.from_string('mtCXje1XCpF8Z3BptaJ4AngDERanJtC9grXicrHpump')
TOKEN=Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')
CTX=CacheReadContext(100,1,5)
def fee_config():
    _,bump=Pubkey.find_program_address([b'fee_config',bytes(PUMPFUN_PROGRAM_ID)],FEE_PROGRAM)
    fees=lambda values:struct.pack('<3Q',*values)
    tiers=lambda rows:struct.pack('<I',len(rows))+b''.join(int(t[0]).to_bytes(16,'little')+fees(t[1:]) for t in rows)
    c=ORACLE['fee_config']
    return bytes([143,52,146,187,219,123,76,155,bump])+bytes(32)+fees(c['flat'])+tiers(c['tiers'])+tiers(c['stable'])+fees(c['exotic'])
def fixture(v):
    pool=get_bonding_curve_pda(MINT);q=Pubkey.from_string(v['quote']);quote=WSOL if q==Pubkey.default() else q
    c=bytearray(125);c[:8]=bytes([23,183,248,55,96,216,172,96])
    for offset,amount in [(8,'1000000000000'),(16,v['vq']),(24,'800000000000'),(32,'1000000000000'),(40,v['supply']),(115,v['creator_override'])]:struct.pack_into('<Q',c,offset,int(amount))
    c[49:81]=bytes(WSOL if v['has_creator'] else Pubkey.default());c[81]=int(v['mayhem']);c[83:115]=bytes(q)
    g=bytearray(1054);g[:8]=bytes([167,232,232,177,200,108,114,127]);g[8]=1;g[1045]=1;struct.pack_into('<Q',g,1046,100)
    m=bytearray(82);m[45]=1;struct.pack_into('<Q',m,36,int(v['supply']));qm=bytearray(82);qm[45]=1
    accounts={pool:CachedAccount(PUMPFUN_PROGRAM_ID,bytes(c),100,0),GLOBAL_ACCOUNT:CachedAccount(PUMPFUN_PROGRAM_ID,bytes(g),100,0),FEE_CONFIG:CachedAccount(FEE_PROGRAM,fee_config(),100,0),MINT:CachedAccount(TOKEN,bytes(m),100,0),quote:CachedAccount(TOKEN,bytes(qm),100,0)}
    h=PoolTradeHint(pool,quote if v['buy'] else MINT,MINT if v['buy'] else quote)
    return accounts,h

@pytest.mark.parametrize('v',ORACLE['vectors'])
def test_current_quote_matches_official_oracle(v):
    a,h=fixture(v);s=cached_pumpfun(AccountCacheSnapshot(a),h,CTX)
    r=quote_cached_pumpfun_exact_in(s,int(v['amount']),v['buy'],100)
    assert r.estimated_net_amount_out==int(v['expected_out'])
    assert r.minimum_net_amount_out==int(v['expected_out'])*9900//10000
    assert r.fees.protocol_fee_bps==int(v['expected_protocol'])
    assert r.fees.creator_fee_bps==int(v['expected_creator'])

@pytest.mark.parametrize('failure',['owner','stale','complete','missing-fee','bump','gate','override','partial'])
def test_invalid_snapshot_rejected(failure):
    a,h=fixture(ORACLE['vectors'][0])
    if failure=='owner':a[FEE_CONFIG]=replace(a[FEE_CONFIG],owner=Pubkey.default())
    elif failure=='stale':a[FEE_CONFIG]=replace(a[FEE_CONFIG],slot=94)
    elif failure=='missing-fee':del a[FEE_CONFIG]
    else:
        k=FEE_CONFIG if failure=='bump' else GLOBAL_ACCOUNT if failure=='gate' else h.pool
        d=bytearray(a[k].data)
        if failure=='bump':d[8]^=1
        elif failure=='complete':d[48]=1
        elif failure=='gate':d[1045]=2
        elif failure=='override':struct.pack_into('<Q',d,115,101)
        elif failure=='partial':d=d[:120]
        a[k]=replace(a[k],data=bytes(d))
    with pytest.raises(ValueError):cached_pumpfun(AccountCacheSnapshot(a),h,CTX)

def test_corrupt_vectors_and_integer_inputs():
    d=bytearray(fee_config());struct.pack_into('<I',d,65,0xffffffff)
    with pytest.raises(ValueError):decode_pumpfun_current_fees(bytes(d),WSOL,1)
    with pytest.raises(ValueError):decode_pumpfun_current_fees(fee_config(),WSOL,True)
    a,h=fixture(ORACLE['vectors'][0]);s=cached_pumpfun(AccountCacheSnapshot(a),h,CTX)
    for amount in (True,-1,1<<64,1):
        with pytest.raises(ValueError):quote_cached_pumpfun_exact_in(s,amount,True)

@pytest.mark.parametrize('buy',[True,False])
def test_invalid_creator_rate_rejected_even_when_creator_is_absent(buy):
    v=next(v for v in ORACLE['vectors'] if not v['has_creator'] and v['buy']==buy)
    a,h=fixture(v);s=cached_pumpfun(AccountCacheSnapshot(a),h,CTX)
    for protocol,creator in [(0,10001),(9999,2),(10001,0)]:
        bad=replace(s,**{'buy_fees' if buy else 'sell_fees':PumpFunCurrentFees(protocol,creator)})
        with pytest.raises(ValueError): quote_cached_pumpfun_exact_in(bad,int(v['amount']),buy)

@pytest.mark.parametrize('buy',[True,False])
def test_v2_preparation_and_observed_absence(buy,monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *args:pytest.fail('network during preparation'))
    v=next(v for v in ORACLE['vectors'] if v['has_creator'] and v['quote']==str(WSOL) and v['buy']==buy)
    a,h=fixture(v);token2022=Pubkey.from_string('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb');a[MINT]=replace(a[MINT],owner=token2022)
    g=bytearray(a[GLOBAL_ACCOUNT].data);g[41:73]=bytes(WSOL);g[741:773]=bytes(WSOL);a[GLOBAL_ACCOUNT]=replace(a[GLOBAL_ACCOUNT],data=bytes(g))
    config=get_fee_sharing_config_pda(MINT);a[config]=CachedAccount(Pubkey.default(),b'',100,0)
    snapshot=AccountCacheSnapshot(a)
    _,q,ix=prepare_cached_pumpfun(snapshot,h,CTX,WSOL,int(v['amount']),100)
    assert struct.unpack_from('<2Q',ix.data,8)==(int(v['amount']),q.minimum_net_amount_out)
    assert ix.accounts[6].pubkey==WSOL and ix.accounts[8].pubkey==WSOL
    assert ix.accounts[8].is_writable
    reads=[]
    original=snapshot.get
    def observe(key,*args,**kwargs):
        reads.append(key)
        return original(key,*args,**kwargs)
    monkeypatch.setattr(snapshot,'get',observe)
    route=snapshot.prepare_route([h],CTX,0,WSOL,int(v['amount']),100,8,True)
    assert reads.count(FEE_CONFIG)==1
    assert route.swap_instructions==(ix,)
    assert route.minimum_net_amount_out==q.minimum_net_amount_out
    with pytest.raises(ValueError,match='closed'):snapshot.get(config,CTX)
    del a[config]
    with pytest.raises(ValueError,match='Missing cached'):prepare_cached_pumpfun(AccountCacheSnapshot(a),h,CTX,WSOL,int(v['amount']))
