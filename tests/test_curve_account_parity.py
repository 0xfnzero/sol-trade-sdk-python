import json
from pathlib import Path
import pytest
from src.common.bonding_curve import BondingCurveAccount, decode_bonding_curve_account
FIXTURE = json.loads((Path(__file__).parent/'fixtures/curve_account_rust_5_0_6.json').read_text())
@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda c:c['name'])
def test_pinned_rust_curve_math(case):
    fields = ['virtual_token_reserves','virtual_sol_reserves','real_token_reserves','real_sol_reserves','token_total_supply']
    curve = BondingCurveAccount(**{f:int(case[f]) for f in fields})
    amount,fee = int(case['amount']),int(case['fee_basis_points'])
    actual = {'buy':curve.get_buy_price(amount),'sell':curve.get_sell_price(amount,fee),'market_cap':curve.get_market_cap_sol(),'buyout':curve.get_buy_out_price(amount,fee),'final_market_cap':curve.get_final_market_cap_sol(fee)}
    assert actual == {f:int(case[f]) for f in actual}
def test_full_curve_layout_and_legacy_body_offsets():
    layout = FIXTURE['layout'];account=bytes.fromhex(layout['account_hex'])
    for data in [account,account+bytes(36),account[8:]]:
        curve=decode_bonding_curve_account(data)
        fields=['virtual_token_reserves','virtual_sol_reserves','real_token_reserves','real_sol_reserves','token_total_supply']
        assert [getattr(curve,f) for f in fields]==[int(v) for v in layout['reserves']]
        assert curve.quote_mint.hex()==layout['quote_hex']
        assert curve.creator.hex()==layout['creator_hex']
        assert curve.is_cashback_coin
    for data in [account[:83],account[8:83]]:
        assert decode_bonding_curve_account(data).real_sol_reserves==456
@pytest.mark.parametrize('index',[0,48,81,82])
def test_bad_discriminator_and_borsh_boolean(index):
    data=bytearray.fromhex(FIXTURE['layout']['account_hex']);data[index]=255
    assert decode_bonding_curve_account(data) is None
@pytest.mark.parametrize('length',[0,74,82,84,106,107,108,114])
def test_truncated_curve(length):
    assert decode_bonding_curve_account(bytes.fromhex(FIXTURE['layout']['account_hex'])[:length]) is None
def test_complete_and_integer_errors():
    curve=BondingCurveAccount(complete=True)
    with pytest.raises(ValueError,match='complete'):curve.get_buy_price(0)
    with pytest.raises(ValueError,match='complete'):curve.get_sell_price(0)
    for value in [-1,1<<64,1.5,True]:
        with pytest.raises(ValueError,match='u64'):BondingCurveAccount().get_buy_price(value)

def test_invalid_and_mutated_reserves_are_rejected():
    for value in [-1,1<<64,1.5,True]:
        with pytest.raises(ValueError,match='u64'):BondingCurveAccount(virtual_sol_reserves=value)
    curve=BondingCurveAccount();curve.virtual_token_reserves=-1
    with pytest.raises(ValueError,match='u64'):curve.get_buy_price(1)
    with pytest.raises(ValueError,match='u64'):curve.get_sell_price(1)
    with pytest.raises(ValueError,match='u64'):curve.get_market_cap_sol()

@pytest.mark.parametrize('as_pubkey', [False, True])
def test_quote_aware_reconstruction_and_transition(as_pubkey):
    from solders.pubkey import Pubkey
    from src import USDC_TOKEN_ACCOUNT, WSOL_TOKEN_ACCOUNT, SOL_TOKEN_ACCOUNT
    from src.instruction.pumpfun_builder import get_bonding_curve_pda, get_creator_vault_pda
    convert = (lambda p:p) if as_pubkey else bytes
    mint, creator = Pubkey.from_bytes(bytes([2])*32), Pubkey.from_bytes(bytes([3])*32)
    curve = BondingCurveAccount.from_dev_trade_with_quote_mint(
        bytes(32),convert(mint),100,200,convert(creator),False,True,convert(USDC_TOKEN_ACCOUNT))
    assert bytes(curve.account) == bytes(get_bonding_curve_pda(mint))
    assert curve.virtual_quote_reserves() == 4_292_000_200
    assert curve.real_quote_reserves() == 200
    assert bytes(curve.effective_quote_mint()) == bytes(USDC_TOKEN_ACCOUNT)
    assert curve.get_creator_vault_pda() == get_creator_vault_pda(creator)
    curve.with_quote_mint(convert(SOL_TOKEN_ACCOUNT))
    assert curve.virtual_sol_reserves == 30_000_000_200
    assert bytes(curve.quote_mint) == bytes(WSOL_TOKEN_ACCOUNT)
    curve.virtual_sol_reserves=123
    curve.with_quote_mint(convert(USDC_TOKEN_ACCOUNT))
    assert curve.virtual_sol_reserves == 123

def test_dev_trade_validation_and_saturation():
    with pytest.raises(ValueError):
        BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), True, 0, bytes(32))
    with pytest.raises(ValueError):
        BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 793_100_000_000_001, 0, bytes(32))
    with pytest.raises(ValueError):
        BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, (1<<64)-1, bytes(32))
    from src import USDC_TOKEN_ACCOUNT
    curve=BondingCurveAccount(virtual_sol_reserves=(1<<64)-1, real_sol_reserves=(1<<64)-1)
    curve.with_quote_mint(USDC_TOKEN_ACCOUNT)
    assert curve.virtual_sol_reserves == (1<<64)-1
