import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from src import SOL_TOKEN_ACCOUNT,WSOL_TOKEN_ACCOUNT,USDC_TOKEN_ACCOUNT,TOKEN_PROGRAM
from src.instruction.pumpfun_builder import PumpFunParams,build_buy_instructions,build_sell_instructions,BUY_EXACT_SOL_IN_DISCRIMINATOR,BUY_EXACT_QUOTE_IN_V2_DISCRIMINATOR,SELL_DISCRIMINATOR,SELL_V2_DISCRIMINATOR
CASES=json.loads((Path(__file__).parent/'fixtures/pumpfun_layout_rust_5_0_6.json').read_text())['cases']
KEYS=dict(default=Pubkey.default(),SOL=SOL_TOKEN_ACCOUNT,WSOL=WSOL_TOKEN_ACCOUNT,USDC=USDC_TOKEN_ACCOUNT)
def pk(n):return Pubkey.from_bytes(bytes([n])*32)
@pytest.mark.parametrize('buy',[True,False])
@pytest.mark.parametrize('case',CASES)
def test_pinned_layout(case,buy):
    p=PumpFunParams(bonding_curve_account=pk(1),virtual_token_reserves=1000000000,virtual_sol_reserves=1000000000,real_token_reserves=900000000,creator=pk(3),creator_vault=pk(4),token_program=TOKEN_PROGRAM,fee_recipient=pk(5),quote_mint=KEYS[case['quote']],curve_quote_mint=KEYS[case['curve_quote']])
    def build():
        if buy:return build_buy_instructions(payer=pk(42),input_mint=KEYS[case['settlement']],output_mint=pk(2),input_amount=10000,create_output_ata=False,params=p)
        return build_sell_instructions(payer=pk(42),input_mint=pk(2),output_mint=KEYS[case['settlement']],input_amount=10000,params=p)
    if case['error'] or case['strict_endpoint_error']:
        with pytest.raises(ValueError,match='does not match'):build()
        return
    ix=next(i for i in build() if str(i.program_id)=='6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P')
    expected=(BUY_EXACT_QUOTE_IN_V2_DISCRIMINATOR if case['v2'] else BUY_EXACT_SOL_IN_DISCRIMINATOR) if buy else (SELL_V2_DISCRIMINATOR if case['v2'] else SELL_DISCRIMINATOR)
    assert bytes(ix.data[:8])==bytes(expected)
