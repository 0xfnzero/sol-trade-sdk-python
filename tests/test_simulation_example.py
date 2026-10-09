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

def test_signed_simulation_request_enables_crypto_and_preserves_hash(monkeypatch):
    # This tests request construction against a mock RPC, not live bank execution.
    from solders.keypair import Keypair
    from solders.hash import Hash
    from solders.system_program import transfer, TransferParams
    from solders.transaction import Transaction
    payer = Keypair()
    tx = Transaction.new_signed_with_payer(
        [transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=Keypair().pubkey(), lamports=1))],
        payer.pubkey(), [payer], Hash.default())
    wire = bytes(tx)
    assert all(tx.verify_with_results())
    response = {'result': {'value': {'err': None, 'logs': [], 'unitsConsumed': 150}}}
    calls = []
    def post(_url, **kwargs):
        request = kwargs['json']; calls.append(request)
        assert request['method'] == 'simulateTransaction'
        assert request['params'][1]['sigVerify'] is True
        assert request['params'][1]['replaceRecentBlockhash'] is False
        parsed = Transaction.from_bytes(base64.b64decode(request['params'][0]))
        assert parsed.message.recent_blockhash == Hash.default()
        assert all(parsed.verify_with_results())
        class Response:
            def raise_for_status(self): pass
            def json(self): return response
        return Response()
    monkeypatch.setattr('examples._simulation.requests.post', post)
    assert simulate(wire, 0, verify_signatures=True) == response
    assert len(calls) == 1

def test_signed_durable_nonce_simulation_preserves_original_hash(monkeypatch):
    # Mock request validation only: this does not assert nonce-account bank state.
    from solders.keypair import Keypair
    from solders.hash import Hash
    from solders.system_program import advance_nonce_account, AdvanceNonceAccountParams
    from solders.transaction import Transaction
    payer = Keypair()
    nonce_hash = Hash.from_bytes(bytes(Keypair().pubkey()))
    advance = advance_nonce_account(AdvanceNonceAccountParams(nonce_pubkey=Keypair().pubkey(), authorized_pubkey=payer.pubkey()))
    tx = Transaction.new_signed_with_payer([advance], payer.pubkey(), [payer], nonce_hash)
    calls = []
    def post(_url, **kwargs):
        request = kwargs['json']; calls.append(request)
        assert request['params'][1]['sigVerify'] is True
        assert request['params'][1]['replaceRecentBlockhash'] is False
        decoded = Transaction.from_bytes(base64.b64decode(request['params'][0]))
        assert decoded.message.recent_blockhash == nonce_hash
        assert bytes(decoded.message.instructions[0].data) == bytes([4,0,0,0])
        assert all(decoded.verify_with_results())
        class Response:
            def raise_for_status(self): pass
            def json(self): return {'result': {'value': {'err': None}}}
        return Response()
    monkeypatch.setattr('examples._simulation.requests.post', post)
    simulate(bytes(tx), 0, verify_signatures=True)
    assert len(calls) == 1
