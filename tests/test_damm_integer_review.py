import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.meteora_damm_v2 import compute_swap_amount,calculate_liquidity
cases=json.loads((Path(__file__).parent/'fixtures/damm_integer_review_20261005.json').read_text())
@pytest.mark.parametrize('c',cases)
def test_damm_integer_boundaries(c):
    a,b,amount=(int(c[k]) for k in ('a','b','amount'))
    assert compute_swap_amount(a,b,c['buy'],amount,int(c['slippage']))=={'amount_out':int(c['out']),'min_amount_out':int(c['minimum'])}
    assert calculate_liquidity(a,b)==int(c['liquidity'])
@pytest.mark.parametrize('bad',[-1,2**64,True,1.0])
def test_invalid_balances(bad):
    with pytest.raises(ValueError):calculate_liquidity(bad,1)
    with pytest.raises(ValueError):compute_swap_amount(bad,1,True,0,0)
