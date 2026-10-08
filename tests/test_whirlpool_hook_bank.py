import base64,json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.token2022_hook import resolve_hook_accounts
from sol_trade_sdk.instruction.native_hops import WhirlpoolSwapV2Accounts,SwapV2Args,build_whirlpool_swap_v2_with_hooks
FIXTURE=json.loads((Path(__file__).parent/'fixtures/whirlpool_hook_bank_20261008.json').read_text())
P=Pubkey.from_string

def inputs(r):
    return [P(r['hook']),P(r['mint']),P(r['mint_owner']),base64.b64decode(r['mint_data']),P(r['meta']),P(r['meta_owner']),base64.b64decode(r['meta_data']),list(map(P,r['execute_accounts']))]

@pytest.mark.parametrize('case',FIXTURE['cases'])
def test_hook_wire_matches_executed_bank(case):
    r=case['resolver'];extra=resolve_hook_accounts(*inputs(r));a=WhirlpoolSwapV2Accounts(**{k:tuple(map(P,v))if k=='tick_arrays'else P(v)for k,v in case['accounts'].items()});i=0 if str(a.mint_a)==r['mint']else 1
    ix=build_whirlpool_swap_v2_with_hooks(a,SwapV2Args(case['amount'],case['minimum']),case['direction'],extra if i==0 else (),extra if i==1 else ())
    assert base64.b64encode(ix.data).decode()==case['expected']['data']
    assert [dict(key=str(m.pubkey),signer=m.is_signer,writable=m.is_writable)for m in ix.accounts]==case['expected']['accounts']

@pytest.mark.parametrize('r',FIXTURE['rewards'])
def test_hook_source_dependent_resolution(r):
    got=resolve_hook_accounts(*inputs(r));assert list(map(lambda m:str(m.pubkey),got))==r['expected_accounts']
    for mode in ['owner','mint_owner','truncated','count','seed_index','encoding','signer','padding']:
        a=inputs(r)
        if mode=='owner':a[5]=Pubkey.default()
        if mode=='mint_owner':a[2]=Pubkey.default()
        b=bytearray(a[6])
        if mode=='truncated':b=b[:-1]
        if mode=='count':b[12]=255
        if mode=='seed_index':b[53]=255
        if mode=='encoding':b[51]=2
        if mode=='signer':b[49]=1
        if mode=='padding':b[55]=3
        a[6]=bytes(b)
        with pytest.raises(ValueError):resolve_hook_accounts(*a)
