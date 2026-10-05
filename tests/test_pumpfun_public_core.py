"""Public parameter entry points must use the same validated instruction core."""
import asyncio
import pytest
from solders.pubkey import Pubkey
from src import PumpFunParams, USDC_TOKEN_ACCOUNT, TOKEN_PROGRAM
from src.trading.params import PumpFunParams as TradingParams
from src.trading.factory import PumpFunExecutor, _pumpfun_bonding_to_builder_params
from src.instruction.pumpfun_builder import build_buy_instructions, build_sell_instructions

def pk(n):
    return Pubkey.from_bytes(bytes([n])*32)

def params():
    return TradingParams.from_parser_trade_event(dict(
        mint=pk(2), bonding_curve=pk(1), creator=pk(3), creator_vault=pk(4),
        fee_recipient=pk(5), token_program=TOKEN_PROGRAM, quote_mint=USDC_TOKEN_ACCOUNT,
        virtual_token_reserves=1_000_000_000, virtual_quote_reserves=1_000_000_000,
        real_token_reserves=900_000_000, real_quote_reserves=50_000_000,
    ))

def test_parameter_class_identity():
    assert TradingParams is PumpFunParams

@pytest.mark.parametrize('use_defaults', [True, False])
def test_dev_trade_preserves_metadata_and_defaults(use_defaults):
    kwargs = {} if use_defaults else dict(quote_mint=USDC_TOKEN_ACCOUNT, fee_recipient=pk(5))
    p=TradingParams.from_dev_trade(pk(2),100,200,pk(3),Pubkey.default(),pk(6),pk(4),**kwargs)
    assert p.bonding_curve.account != Pubkey.default()
    assert p.observed_trade_creator == pk(3)
    assert p.token_program == TOKEN_PROGRAM
    assert p.bonding_curve.virtual_sol_reserves == (30_000_000_000 if use_defaults else 4_292_000_000)+200
    if not use_defaults:
        assert p.quote_mint == p.bonding_curve.quote_mint == USDC_TOKEN_ACCOUNT
        assert p.fee_recipient == pk(5)

@pytest.mark.parametrize('bad', [-1, 1 << 64, 1.5, True])
def test_dev_trade_rejects_invalid_amount(bad):
    with pytest.raises(ValueError):
        TradingParams.from_dev_trade(pk(2),bad,200,pk(3),pk(1),pk(6),pk(4))

@pytest.mark.parametrize('buy', [True, False])
def test_factory_curve_quote_fallback_matches_native_wire(buy, monkeypatch):
    from src.instruction import pumpfun_builder
    monkeypatch.setattr(pumpfun_builder, "get_buyback_fee_recipient_random", lambda: pumpfun_builder.BUYBACK_FEE_RECIPIENTS[0])
    p=params()
    request=vars(p).copy()
    request.pop('quote_mint')  # Full V2 curve alone still carries the quote.
    request.update(payer=pk(42), input_amount=10_000, token_amount=10_000,
                   output_mint=pk(2) if buy else USDC_TOKEN_ACCOUNT,
                   input_mint=USDC_TOKEN_ACCOUNT if buy else pk(2),
                   create_output_mint_ata=False)
    request.pop('input_mint' if buy else 'output_mint')
    mapped=_pumpfun_bonding_to_builder_params(p.bonding_curve,p.creator_vault,p.associated_bonding_curve,p.token_program,False,p.fee_recipient,None,p.observed_trade_creator)
    assert mapped.curve_quote_mint == USDC_TOKEN_ACCOUNT
    executor=PumpFunExecutor()
    prepared=asyncio.run(executor.build_buy_instructions(request) if buy else executor.build_sell_instructions(request))
    if buy:
        expected=build_buy_instructions(pk(42),pk(2),10_000,mapped,slippage_bps=100,create_output_ata=False,input_mint=USDC_TOKEN_ACCOUNT)
    else:
        expected=build_sell_instructions(pk(42),pk(2),10_000,mapped,slippage_bps=100,output_mint=USDC_TOKEN_ACCOUNT)
    assert prepared['instructions'] == expected
    assert prepared['prepared'] and not prepared['submitted'] and not prepared['confirmed']

@pytest.mark.parametrize('field', ['virtual_token_reserves','virtual_sol_reserves'])
def test_factory_rejects_fractional_curve_state(field):
    p=params();setattr(p.bonding_curve,field,1.5)
    with pytest.raises(ValueError):
        _pumpfun_bonding_to_builder_params(p.bonding_curve,p.creator_vault,p.associated_bonding_curve,p.token_program,False)

def test_default_curve_is_unknown_zero_state():
    curve = PumpFunParams().bonding_curve
    assert all(getattr(curve, f) == 0 for f in (
        'virtual_token_reserves', 'virtual_sol_reserves', 'real_token_reserves',
        'real_sol_reserves', 'token_total_supply'))
    with pytest.raises(ValueError):
        curve.get_buy_price(1)
