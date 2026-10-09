import pytest
from unittest.mock import AsyncMock, call
from solders.keypair import Keypair
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.hotpath.executor import HotPathExecutor, TransactionBuilder
from src.hotpath.state import HotPathConfig, PoolState

@pytest.mark.asyncio
async def test_cold_prefetched_expiry_uses_monotonic_seconds_after_wall_jumps_and_stop(monkeypatch):
    clock={'wall':1000000.0,'mono':100.0}
    monkeypatch.setattr('src.hotpath.state.time.time',lambda:clock['wall'])
    monkeypatch.setattr('src.hotpath.state.time.monotonic',lambda:clock['mono'])
    rpc=AsyncMock();rpc.get_latest_blockhash.return_value={'blockhash':str(Hash.from_bytes(bytes(Keypair().pubkey()))),'last_valid_block_height':100}
    executor=HotPathExecutor(rpc,HotPathConfig(cache_ttl=1.0,blockhash_refresh_interval=1000000))
    await executor.start();await executor.stop()
    account_key=str(Keypair().pubkey())
    rpc.get_multiple_accounts.return_value=[{'data':b'1','lamports':1,'owner':str(Keypair().pubkey())}]
    await executor.prefetch_accounts([account_key])
    state=executor.get_state()
    pool_key=str(Keypair().pubkey())
    state.update_pool(pool_key,PoolState(pool_key,'pumpfun',account_key,account_key,account_key,account_key,1,1,0,fetched_at=clock['wall']))
    def forbid(*args, **kwargs): pytest.fail("implicit network")
    monkeypatch.setattr("requests.post",forbid)
    payer=Keypair();ix=transfer(TransferParams(from_pubkey=payer.pubkey(),to_pubkey=Keypair().pubkey(),lamports=1))
    builder=TransactionBuilder(executor)
    for mono in (100.999,101.0):
        clock.update(mono=mono,wall=2000000.0)
        wire,error=builder.build_transaction(str(payer.pubkey()),[ix],[payer])
        assert error is None
        assert state.get_account(account_key) is not None and state.get_pool(pool_key) is not None
        tx=Transaction.from_bytes(wire)
        Ed25519PublicKey.from_public_bytes(bytes(payer.pubkey())).verify(bytes(tx.signatures[0]),bytes(tx.message))
    clock.update(mono=101.000001,wall=1.0)
    wire,error=builder.build_transaction(str(payer.pubkey()),[ix],[payer])
    assert wire is None and 'Stale blockhash' in error
    assert executor.get_state().is_data_fresh() is False
    assert state.get_account(account_key) is None and state.get_pool(pool_key) is None
    assert rpc.get_latest_blockhash.await_count==1
    assert rpc.mock_calls==[call.get_latest_blockhash(),call.get_multiple_accounts([account_key])]
