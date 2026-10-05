import json
from dataclasses import astuple
from pathlib import Path
import pytest
from sol_trade_sdk import calc
from sol_trade_sdk.calc import pumpswap as dict_calc
cases=json.loads((Path(__file__).parent/'fixtures/pumpswap_rust_5_0_6.json').read_text())['cases']
funcs=[calc.buy_base_input_internal_with_fees,calc.buy_quote_input_internal_with_fees,calc.sell_base_input_internal_with_fees,calc.sell_quote_input_internal_with_fees]
@pytest.mark.parametrize('c',cases)
def test_pinned_rust_pumpswap(c):
    args=[int(c[k]) for k in ('amount','slippage','base_reserve','quote_reserve','virtual')]
    fees=calc.PumpSwapFeeBasisPoints(*(int(n) for n in c['fees']))
    for i,fn in enumerate(funcs):
        if c['results'][i] is None:
            with pytest.raises(ValueError): fn(*args,fees)
        else: assert [str(v) for v in astuple(fn(*args,fees))]==c['results'][i]
        compatibility = getattr(dict_calc,fn.__name__)
        if c['results'][i] is None:
            with pytest.raises(ValueError): compatibility(*args,fees)
        else: assert [str(v) for v in compatibility(*args,fees).values()]==c['results'][i]

def test_common_boundaries():
    maximum=(1<<64)-1
    assert calc.compute_fee(maximum,10000)==maximum
    assert calc.ceil_div(maximum,2)==9223372036854775808
    assert calc.calculate_with_slippage_buy(maximum,100)==maximum
    assert calc.calculate_with_slippage_sell(maximum,100)==18262276632972456099
    assert calc.calculate_with_slippage_sell(0,maximum)==0
    assert calc.calculate_with_slippage_sell(10000,maximum)==1
    for invalid in (-1,True,1.0,1<<64):
        with pytest.raises((ValueError,TypeError)): calc.calculate_with_slippage_buy(1,invalid)
