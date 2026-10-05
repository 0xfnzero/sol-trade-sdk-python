import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.calc import get_buy_token_amount_from_sol_amount as buy, get_sell_sol_amount_from_token_amount as sell
from sol_trade_sdk.calc import pumpfun
from sol_trade_sdk.instruction import pumpfun_builder
cases=json.loads((Path(__file__).parent/"fixtures/pumpfun_rust_5_0_6.json").read_text())["cases"]
@pytest.mark.parametrize("c",cases)
def test_pinned_rust_curve(c):
    vt,vq,rt,a=(int(c[k]) for k in ("virtual_token","virtual_quote","real_token","amount"))
    creator=bytes([1 if c["has_creator"] else 0])*32
    assert buy(a,vq,vt,rt,c["has_creator"])==int(c["buy"])
    assert sell(a,vq,vt,c["has_creator"])==int(c["sell"])
    assert pumpfun.get_buy_token_amount_from_sol_amount(vt,vq,rt,creator,a)==int(c["buy"])
    assert pumpfun.get_sell_sol_amount_from_token_amount(vt,vq,creator,a)==int(c["sell"])
    assert pumpfun_builder.get_buy_token_amount_from_sol_amount(vt,vq,rt,Pubkey.from_bytes(creator),a)==int(c["buy"])
