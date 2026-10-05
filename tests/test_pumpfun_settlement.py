from types import SimpleNamespace as S
import struct
import pytest
from solders.pubkey import Pubkey
from solders.instruction import Instruction,AccountMeta
from src.instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID
from src.instruction.common import TOKEN_PROGRAM, WSOL_TOKEN_ACCOUNT, get_associated_token_address
from src.trading.pumpfun_settlement import settle_pumpfun_native_quote

PAYER=Pubkey.new_unique()
def route(buy=True):
    mint,pool=Pubkey.new_unique(),Pubkey.new_unique()
    keys=[AccountMeta(Pubkey.new_unique(),False,False) for _ in range(27 if buy else 26)]
    for index,key in [(1,mint),(2,WSOL_TOKEN_ACCOUNT),(10,pool),(13,PAYER)]:keys[index]=AccountMeta(key,index==13,index in (10,13))
    ix=Instruction(PUMPFUN_PROGRAM_ID,bytes.fromhex('c2ab1c46684d5b2f' if buy else '5df6823ce7e940b2')+struct.pack('<QQ',10000,10000),keys)
    leg=S(hint=S(pool=pool,input_mint=WSOL_TOKEN_ACCOUNT if buy else mint,output_mint=mint if buy else WSOL_TOKEN_ACCOUNT),amount_in=10000,minimum_net_amount_out=10000,estimated_net_amount_out=11000,instruction=ix)
    return S(legs=(leg,),setup_instructions=(),swap_instructions=(ix,),minimum_net_amount_out=10000)

def test_native_buy_does_not_lock_wsol():
    ix,funding,residual=settle_pumpfun_native_quote(route(),PAYER,True,False,'',0)
    assert len(ix)==1 and funding==10000 and residual==0

def test_wsol_buy_preserves_source_and_closes_only_temporary():
    payer=PAYER
    ix,funding,residual=settle_pumpfun_native_quote(route(),payer,False,False,'p',2039280)
    ata=get_associated_token_address(payer,WSOL_TOKEN_ACCOUNT,TOKEN_PROGRAM)
    assert len(ix)==5 and funding==2039280 and residual==0
    assert ix[2].accounts[0].pubkey==ata
    assert ix[3].accounts[0].pubkey==ix[2].accounts[1].pubkey!=ata
    assert struct.unpack('<BQ',ix[2].data)==(3,10000)

def test_wsol_sell_reports_native_residual():
    ix,funding,residual=settle_pumpfun_native_quote(route(False),PAYER,False,False,'',0)
    assert struct.unpack('<IQ',ix[1].data)==(2,10000)
    assert ix[2].data==bytes([17]) and funding==0 and residual==1000

@pytest.mark.parametrize('seed,rent',[('',1),('x'*33,1),('p',0),('p',True)])
def test_invalid_input_preparation(seed,rent):
    with pytest.raises(ValueError):settle_pumpfun_native_quote(route(),PAYER,False,False,seed,rent)

def test_reject_multi_hop_and_wrong_endpoint():
    r=route();r.legs=r.legs*2
    with pytest.raises(ValueError,match='multi-hop'):settle_pumpfun_native_quote(r,Pubkey.new_unique(),True,False,'',0)
    with pytest.raises(ValueError,match='endpoint'):settle_pumpfun_native_quote(route(),PAYER,False,True,'p',1)

@pytest.mark.parametrize('condition',['wallet','protocol','quote','instruction','protection','zero','flags','encoded_amount','pool'])
def test_single_settlement_rejects_inconsistent_request(condition):
    r=route();payer=PAYER;native_input=True
    if condition=='wallet':payer=Pubkey.new_unique()
    elif condition=='protocol':
        ix=Instruction(TOKEN_PROGRAM,b'quote',[AccountMeta(PAYER,True,True)]);r.legs[0].instruction=ix;r.swap_instructions=(ix,)
    elif condition=='quote':r.legs[0].hint.output_mint=WSOL_TOKEN_ACCOUNT
    elif condition=='instruction':r.swap_instructions=(Instruction(PUMPFUN_PROGRAM_ID,b'changed',[AccountMeta(PAYER,True,True)]),)
    elif condition=='protection':r.minimum_net_amount_out=1
    elif condition=='zero':r.legs[0].amount_in=0
    elif condition=='flags':native_input=1
    elif condition=='encoded_amount':r.legs[0].amount_in=10001
    elif condition=='pool':r.legs[0].hint.pool=Pubkey.new_unique()
    with pytest.raises(ValueError):settle_pumpfun_native_quote(r,payer,native_input,False,'',0)
