import base64
import json
import os
from pathlib import Path

import pytest
from solders.hash import Hash
from solders.keypair import Keypair
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction

from src.hotpath.executor import HotPathExecutor, TransactionBuilder, ExecuteOptions
from src.hotpath.state import HotPathConfig, PrefetchedData
from src.common.types import TradeType, SwqosType
from src.swqos.clients import JitoClient


@pytest.mark.asyncio
@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('trade_type', [TradeType.BUY, TradeType.SELL])
async def test_native_provider_ack_is_preserved_without_attribute_type(parallel, trade_type, monkeypatch):
    import time
    payer = Keypair.from_seed(bytes(range(32)))
    recipient = Keypair.from_seed(bytes(range(32, 64))).pubkey()
    blockhash = os.environ.get('SDK_BANK_BLOCKHASH', str(Hash.default()))
    executor = HotPathExecutor(None, HotPathConfig(enable_prefetch=False))
    executor.state._current_data = PrefetchedData(blockhash=blockhash, fetched_at=time.time())
    instruction = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=recipient, lamports=100_000))
    wire, error = TransactionBuilder(executor).build_transaction(str(payer.pubkey()), [instruction], [payer])
    assert error is None
    parsed = Transaction.from_bytes(wire)
    assert all(parsed.verify_with_results())
    assert parsed.message.recent_blockhash == Hash.from_string(blockhash)
    assert parsed.message.instructions[0].data == (2).to_bytes(4, 'little') + (100_000).to_bytes(8, 'little')
    signed = str(parsed.signatures[0])
    calls = []
    async def send(trade, raw, wait):
        assert trade == trade_type and raw == wire and wait is False
        calls.append(raw)
        return signed
    providers = [JitoClient('offline://unused', 'offline://unused') for _ in range(2 if parallel else 1)]
    for provider in providers:
        assert not hasattr(provider, 'swqos_type')
        monkeypatch.setattr(provider, 'send_transaction', send)
        executor.add_swqos_client(provider)
    result = await executor.execute(trade_type, wire, ExecuteOptions(parallel_submit=parallel))
    assert result.success and result.signature == signed and result.swqos_type == SwqosType.JITO
    assert calls
    executor.remove_swqos_client(SwqosType.JITO)
    assert not executor._swqos_clients
    output = os.environ.get('SDK_BANK_EXPORT')
    if output and not parallel and trade_type == TradeType.BUY:
        Path(output).write_text(json.dumps(dict(sdk='trade-python', wire=base64.b64encode(wire).decode(),
            payer=str(payer.pubkey()), recipient=str(recipient), lamports=100_000, blockhash=blockhash)))
