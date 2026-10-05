import pytest
import json
from pathlib import Path
from sol_trade_sdk.swqos.clients import create_cached_wire_submit,_signature_from_serialized_transaction
import base64,asyncio

SUBMIT_CASES=json.loads((Path(__file__).parent/'fixtures/review10_bad_submit.json').read_text())
@pytest.mark.parametrize('case',SUBMIT_CASES,ids=lambda c:c['name'])
def test_submit_validation(case):
    raw=base64.b64decode(case['wire'])
    if case['valid']:_signature_from_serialized_transaction(raw)
    else:
        with pytest.raises(Exception):_signature_from_serialized_transaction(raw)

def test_cached_transport_signature_mismatch():
    class Client:
        async def send_transaction(self,*args):return 'wrong'
    with pytest.raises(Exception,match='signature'):
        asyncio.run(create_cached_wire_submit(Client())(base64.b64decode(SUBMIT_CASES[0]['wire']),'Buy'))
from examples.cached_trade import build

@pytest.mark.parametrize('dex',['LaunchLab','Bonk'])
def test_generic_launchlab_cached_trade(dex):
    v=json.loads((Path(__file__).parents[1]/'examples/fixtures/review10_launchlab_generic.json').read_text())
    v['dex_type']=dex
    route,wire=build(v)
    assert len(route.legs)==3 and wire[0]==129

def test_stonkfun_attribution_stays_strict():
    v=json.loads((Path(__file__).parents[1]/'examples/fixtures/review10_launchlab_generic.json').read_text())
    v['dex_type']='StonkFun'
    with pytest.raises(ValueError,match='identity'):build(v)
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from dataclasses import replace
from sol_trade_sdk import compile_v1_message,sign_v1_transaction

def test_v1_signer_metadata_integrity():
    payer=Keypair();c=compile_v1_message(payer.pubkey(),[],str(Pubkey.default()))
    assert len(sign_v1_transaction(c,[payer]))==len(c.message)+64
    with pytest.raises(ValueError,match='metadata'):sign_v1_transaction(replace(c,required_signatures=0),[])
    message=bytearray(c.message);message[42]^=1
    with pytest.raises(ValueError,match='metadata'):sign_v1_transaction(replace(c,message=bytes(message)),[payer])
    message=bytearray(c.message);message[1]=2
    with pytest.raises(ValueError,match='metadata'):sign_v1_transaction(replace(c,message=bytes(message)),[payer])
from sol_trade_sdk import CachedAccount,AccountCacheSnapshot,CacheReadContext

def test_snapshot_owns_direct_account_bytes():
    key=Pubkey.new_unique();data=bytearray(b'one')
    account=CachedAccount(key,data,100,1)
    snapshot=AccountCacheSnapshot({key:account})
    data[0]=0
    assert snapshot.get(key,CacheReadContext(100,0,0)).data==b'one'

@pytest.mark.parametrize('slot,version',[(-1,0),(0,-1),(1<<64,0)])
def test_direct_account_rejects_invalid_versions(slot,version):
    with pytest.raises(ValueError):CachedAccount(Pubkey.new_unique(),b'one',slot,version)
