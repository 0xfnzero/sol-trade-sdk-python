from unittest.mock import Mock, call
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from solders.keypair import Keypair
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from src.hotpath.executor import TransactionBuilder
from src.serialization.v1 import compile_v1_message, sign_v1_transaction


def forbid(*args, **kwargs):
    pytest.fail('implicit network/RPC during signing')


def test_generated_key_legacy_sign_parse_tamper_and_missing_signer(monkeypatch):
    monkeypatch.setattr('requests.post', forbid)
    payer, other = Keypair(), Keypair()
    executor = Mock()
    executor.get_blockhash.return_value = (str(Hash.default()), 100, True)
    builder = TransactionBuilder(executor)
    ix = transfer(TransferParams(from_pubkey=other.pubkey(), to_pubkey=payer.pubkey(), lamports=1))
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], [other, payer])
    assert error is None
    tx = Transaction.from_bytes(wire)
    assert len(tx.signatures) == 2 and all(tx.verify_with_results())
    message = bytes(tx.message)
    for key, signature in zip(tx.message.account_keys, tx.signatures):
        Ed25519PublicKey.from_public_bytes(bytes(key)).verify(bytes(signature), message)
    tampered = bytearray(wire); tampered[-1] ^= 1
    assert not all(Transaction.from_bytes(bytes(tampered)).verify_with_results())
    failed, error = builder.build_transaction(str(payer.pubkey()), [ix], [payer])
    assert failed is None and error
    assert executor.mock_calls == [call.get_blockhash(), call.get_blockhash()]


def test_generated_key_v1_actual_signatures_and_tamper_rejection(monkeypatch):
    monkeypatch.setattr('requests.post', forbid)
    payer, other = Keypair(), Keypair()
    ix = transfer(TransferParams(from_pubkey=other.pubkey(), to_pubkey=payer.pubkey(), lamports=1))
    compiled = compile_v1_message(payer.pubkey(), [ix], Hash.default())
    wire = sign_v1_transaction(compiled, [other, payer])
    assert compiled.required_signatures == 2
    assert compiled.account_keys[0] == bytes(payer.pubkey())
    def verify(raw):
        for i, key in enumerate(compiled.account_keys[:2]):
            offset = len(compiled.message) + 64*i
            Ed25519PublicKey.from_public_bytes(key).verify(raw[offset:offset+64], raw[:len(compiled.message)])
    verify(wire)
    for index in (len(compiled.message)-1, len(compiled.message)):
        damaged = bytearray(wire); damaged[index] ^= 1
        with pytest.raises(InvalidSignature): verify(bytes(damaged))
    with pytest.raises(ValueError, match='Missing V1 signer'):
        sign_v1_transaction(compiled, [payer])

@pytest.mark.asyncio
@pytest.mark.parametrize('confirm', [True, False])
async def test_submission_timestamp_does_not_claim_unobserved_confirmation(confirm, monkeypatch):
    from src.trading.high_perf_executor import TradeExecutor, TradeConfig, ExecuteOptions
    from src.common.types import TradeType, SwqosType
    class Provider:
        async def send_transaction(self, trade, wire, wait_confirmation):
            assert wait_confirmation is False
            return 'ack'
        def get_swqos_type(self): return SwqosType.DEFAULT
    from src.swqos.clients import SwqosConfig
    observed = []
    async def observe(url, signature, **kwargs):
        observed.append(signature)
        return True, None
    monkeypatch.setattr('src.trading.high_perf_executor.poll_for_confirmation_error', observe)
    monkeypatch.setattr('src.trading.high_perf_executor.ClientFactory.create_client', lambda *args: Provider())
    executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
    executor.add_client(SwqosConfig(type=SwqosType.DEFAULT))
    result = await executor.execute(TradeType.BUY, b'', ExecuteOptions(wait_confirmation=confirm))
    assert observed == (['ack'] if confirm else [])
    assert result.success and result.submitted_at is not None
    assert (result.confirmed_at is not None) is confirm
    assert (result.confirmation_time_ms is not None) is confirm
    executor.close()

@pytest.mark.asyncio
async def test_hung_parallel_lane_honors_timeout_after_winner_returns():
    import asyncio
    from src.trading.high_perf_executor import TradeExecutor, TradeConfig, ExecuteOptions
    from src.common.types import TradeType, SwqosType
    cancelled = asyncio.Event()
    class Provider:
        def __init__(self, hung): self.hung = hung
        async def send_transaction(self, *args):
            if not self.hung: return 'winner'
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        def get_swqos_type(self): return SwqosType.DEFAULT if not self.hung else SwqosType.JITO
    executor = TradeExecutor(TradeConfig(rpc_url='http://localhost:1'))
    executor._clients = {SwqosType.DEFAULT: Provider(False), SwqosType.JITO: Provider(True)}
    try:
        result = await executor.execute(TradeType.BUY, b'', ExecuteOptions(wait_confirmation=False, timeout_ms=5))
        assert result.success and result.signature == 'winner'
        await asyncio.wait_for(cancelled.wait(), 1)
        for _ in range(10): await asyncio.sleep(0)
        assert not executor._pending_submissions
    finally: executor.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('outcome', ['failed', 'deadline'])
async def test_public_executor_preserves_acknowledged_signature_on_confirmation_failure(parallel, outcome, monkeypatch):
    import asyncio
    from src.trading.high_perf_executor import TradeExecutor, TradeConfig, ExecuteOptions
    from src.common.types import TradeType, SwqosType
    from src.swqos.clients import SwqosConfig
    cancelled = asyncio.Event()
    class Provider:
        async def send_transaction(self, trade, wire, wait_confirmation):
            assert wait_confirmation is False
            return 'accepted-signature'
        def get_swqos_type(self): return SwqosType.DEFAULT
    async def observe(*args, **kwargs):
        if outcome == 'failed': return False, 'instruction failed'
        try: await asyncio.Event().wait()
        finally: cancelled.set()
    monkeypatch.setattr('src.trading.high_perf_executor.poll_for_confirmation_error', observe)
    monkeypatch.setattr('src.trading.high_perf_executor.ClientFactory.create_client', lambda *args: Provider())
    executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
    executor.add_client(SwqosConfig(type=SwqosType.DEFAULT))
    try:
        result = await executor.execute(TradeType.BUY, b'', ExecuteOptions(
            wait_confirmation=True, parallel_submit=parallel, timeout_ms=20))
        assert not result.success and result.signature == 'accepted-signature'
        assert result.confirmed_at is None and result.confirmation_time_ms is None
        assert result.error == ('instruction failed' if outcome == 'failed' else 'Execution deadline exceeded')
        if outcome == 'deadline': assert cancelled.is_set()
        await asyncio.sleep(0)  # Done callbacks run on the next loop turn.
        assert not executor._pending_submissions
    finally: executor.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('confirm', [False, True])
async def test_default_client_confirmation_is_opt_in_and_retains_failure_signature(confirm, monkeypatch):
    from src.common.types import TradeType
    from src.swqos.clients import DefaultClient, TradeError
    class Response:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self): return {'result': 'accepted-signature'}
    class Session:
        def post(self, url, **kwargs):
            assert kwargs['json']['method'] == 'sendTransaction'
            return Response()
    async def get_session(): return Session()
    observed = []
    async def observe(url, signature):
        observed.append(signature)
        return False, 'instruction failed'
    client = DefaultClient('offline://unused')
    monkeypatch.setattr(client, 'get_session', get_session)
    monkeypatch.setattr('src.trading.executor.poll_for_confirmation_error', observe)
    if confirm:
        with pytest.raises(TradeError) as failure:
            await client.send_transaction(TradeType.BUY, b'', True)
        assert failure.value.signature == 'accepted-signature'
    else:
        assert await client.send_transaction(TradeType.BUY, b'', False) == 'accepted-signature'
    assert observed == (['accepted-signature'] if confirm else [])
