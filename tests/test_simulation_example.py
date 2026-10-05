import base64
import json
import pytest
from examples._simulation import validate_simulation_response,simulate

@pytest.mark.parametrize('response',[{},None,{'result':None},{'result':{'value':None}},{'result':{'value':{}}},{'error':{'code':-1}}])
def test_rejects_missing_execution_result(response):
    with pytest.raises(ValueError):validate_simulation_response(response)

def test_explicit_null_error():
    assert validate_simulation_response({'result':{'value':{'err':None}}}) is None

def test_simulates_only_and_preserves_failed_wire(monkeypatch,tmp_path):
    wire=bytes([1,2,3,255]);response={'result':{'value':{'err':{'InstructionError':[0,'failure']},'innerInstructions':[]}}}
    def post(_url,**kwargs):
        v=kwargs['json'];assert v['method']=='simulateTransaction'
        assert v['params'][0]==base64.b64encode(wire).decode()
        assert v['params'][1]['minContextSlot']==123
        assert v['params'][1]['sigVerify'] is False
        assert kwargs['timeout']==30
        class R:
            def raise_for_status(self):pass
            def json(self):return response
        return R()
    monkeypatch.setattr('examples._simulation.requests.post',post)
    path=tmp_path/'simulation.json'
    with pytest.raises(SystemExit):simulate(wire,123,path)
    saved=json.loads(path.read_text());assert base64.b64decode(saved['wire'])==wire and saved['response']==response
