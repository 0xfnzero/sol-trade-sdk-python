import json,hashlib
from pathlib import Path
import pytest
from examples.cached_trade import build
ROOT=Path(__file__).parents[1]/'examples/fixtures'
@pytest.mark.parametrize('index',[0,1])
def test_grpc_discovered_buy_wire(index,monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *args:pytest.fail('network in preparation'))
    v=json.loads((ROOT/f'pumpfun_settled_{index}_sol_buy_20261004.json').read_text())
    route,wire=build(v)
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
    assert route.minimum_net_amount_out==int(v['expected']['minimum_out'])
    assert route.legs[0].estimated_net_amount_out==int(v['expected']['estimated_out'])
    assert route.swap_instructions[0].accounts[8].is_writable
def test_wrong_direction_and_non_pump_threshold():
    v=json.loads((ROOT/'pumpfun_current_0_sol_buy_20261004.json').read_text())
    with pytest.raises(ValueError,match='direction'):build(dict(v,trade_type='Sell'))
    with pytest.raises(ValueError,match='only supported'):build(dict(v,fixed_output_amount='1'))

def test_verified_funded_wsol_settlement_wire():
    v=json.loads((ROOT/'pumpfun_settled_funded_wsol_buy_20261004.json').read_text())
    _,wire=build(v)
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
    evidence=json.loads((ROOT/'pumpfun_settled_funded_wsol_evidence_20261004.json').read_text())
    assert evidence['verified_asset_payment'] and evidence['actual_wsol_debit']=='10000'
    assert evidence['wire_bytes']==len(wire)

@pytest.mark.parametrize('asset',['sol','wsol'])
def test_verified_funded_sell_factory_wire(asset):
    v=json.loads((ROOT/f'pumpfun_funded_1_{asset}_sell_20261004.json').read_text())
    route,wire=build(v)
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
    assert route.minimum_net_amount_out==7542 and route.legs[0].estimated_net_amount_out==7939
