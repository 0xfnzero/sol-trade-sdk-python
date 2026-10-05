import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.whirlpool import *
V=json.loads((Path(__file__).parent/'fixtures/whirlpool_rust_5_0_6.json').read_text())
@pytest.mark.parametrize('v',V,ids=lambda v:v['case']['kind'])
def test_rust_golden(v):
    c,w=v['case'],v['expected']
    def run():
        if c['kind']=='tick':
            price=whirlpool_sqrt_price_at_tick(c['tick']);assert whirlpool_tick_at_sqrt_price(price)==c['tick'];return dict(price=str(price))
        pool=ClmmPool(int(c['current']),int(c['liquidity']),c['tick'],c['spacing'],c['fee']);ticks=[ClmmTick(t['tick'],int(t['net']),0)for t in c['ticks']];before=repr(ticks)
        r=whirlpool_swap_exact_in(pool,ticks,c['starts'],int(c['amount']),c['timestamp'],c['down'],WhirlpoolAdaptiveFee(**c['adaptive']) if c['adaptive']else None)
        assert repr(ticks)==before
        return dict(consumed=str(r.consumed),output=str(r.amount_out),fee=str(r.fee),minimum_fee=r.minimum_fee_rate,maximum_fee=r.maximum_fee_rate)
    if 'error'in w:
        with pytest.raises(ValueError):run()
    else:assert run()==w
