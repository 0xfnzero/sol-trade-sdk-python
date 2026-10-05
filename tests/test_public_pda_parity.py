import pytest
from solders.pubkey import Pubkey
from src import PUMPFUN_PROGRAM,PUMPSWAP_PROGRAM,RAYDIUM_CPMM_PROGRAM,BONK_PROGRAM
from src.seed import pda
from src.instruction import pumpfun_builder as builder
from src.security.validators import validate_program_id,ValidationError

def test_public_program_identity():
    assert str(PUMPFUN_PROGRAM)==pda.PUMPFUN_PROGRAM_ID==str(builder.PUMPFUN_PROGRAM_ID)
    assert str(PUMPSWAP_PROGRAM)==pda.PUMPSWAP_PROGRAM_ID
    assert str(RAYDIUM_CPMM_PROGRAM)==pda.RAYDIUM_CPMM_PROGRAM_ID
    assert str(BONK_PROGRAM)=='LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
    for name,program in [('pumpfun',pda.PUMPFUN_PROGRAM_ID),('pumpswap',pda.PUMPSWAP_PROGRAM_ID),('raydium',pda.RAYDIUM_CPMM_PROGRAM_ID),('meteora',pda.METEORA_DAMM_V2_PROGRAM_ID)]:
        assert validate_program_id(program,name)==program
    with pytest.raises(ValidationError):validate_program_id('6EF8rrecthR5Dkzon8Nwu78hRvfCKopJFfWcCzNfXt3D','pumpfun')

def test_known_global_and_event_pd_as():
    assert str(Pubkey.from_bytes(pda.get_global_account_pda().pubkey))=='4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf'
    assert str(Pubkey.from_bytes(pda.get_event_authority_pda().pubkey))=='Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1'

@pytest.mark.parametrize('i',range(20))
def test_domain_separation_curve_and_bump(i):
    seeds=[b'fixture',bytes([i])]
    expected,bump=Pubkey.find_program_address(seeds,PUMPFUN_PROGRAM)
    assert pda.find_program_address(seeds,str(PUMPFUN_PROGRAM))==(bytes(expected),bump)
    assert pda.create_program_address(seeds+[bytes([bump])],str(PUMPFUN_PROGRAM))==bytes(expected)

def test_complete_pool_seeds_and_invalid_helpers():
    creator=Pubkey.from_bytes(bytes([42])*32);base=Pubkey.from_bytes(bytes([43])*32);quote=Pubkey.from_bytes(bytes([44])*32)
    expected,bump=Pubkey.find_program_address([b'pool',b'\x01\x01',bytes(creator),bytes(base),bytes(quote)],PUMPSWAP_PROGRAM)
    actual=pda.get_pumpswap_pool_pda(str(base),str(quote),257,str(creator))
    assert (actual.pubkey,actual.bump)==(bytes(expected),bump)
    with pytest.raises(ValueError):pda.find_program_address([bytes(33)],str(PUMPFUN_PROGRAM))
    with pytest.raises(ValueError):pda.get_fee_recipient_pda()
    with pytest.raises(ValueError):pda.get_meteora_pool_pda(str(base),str(quote))
