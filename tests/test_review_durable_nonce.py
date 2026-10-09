from types import SimpleNamespace
from unittest.mock import Mock, call
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.system_program import advance_nonce_account, AdvanceNonceAccountParams, transfer, TransferParams, ID
from solders.transaction import Transaction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.nonce_cache import fetch_nonce_info
from src.hotpath.executor import TransactionBuilder

@pytest.mark.asyncio
@pytest.mark.parametrize("gas",[True,False])
async def test_cached_nonce_is_first_despite_compute_budget_and_real_signatures(monkeypatch,gas):
    payer, authority, nonce = Keypair(), Keypair(), Keypair().pubkey()
    nonce_hash = Hash.from_bytes(bytes(Keypair().pubkey()))
    data = (1).to_bytes(4,'little')*2 + bytes(authority.pubkey()) + bytes(nonce_hash) + bytes(8)
    class ColdRPC:
        async def get_account_info(self, *args, **kwargs):
            return SimpleNamespace(value=SimpleNamespace(data=data,owner=Pubkey.default(),executable=False))
    info = await fetch_nonce_info(ColdRPC(), nonce)
    assert info is not None
    def forbid(*args, **kwargs): pytest.fail('implicit RPC')
    monkeypatch.setattr('requests.post',forbid)
    executor = Mock(); executor.get_blockhash.return_value = (info.nonce_hash,0,True)
    builder = TransactionBuilder(executor)
    instructions = [advance_nonce_account(AdvanceNonceAccountParams(nonce_pubkey=nonce,authorized_pubkey=authority.pubkey()))]
    wire,error = builder.build_transaction(str(payer.pubkey()),instructions,[authority,payer],{'compute_unit_limit':200000,'compute_unit_price':1} if gas else None)
    assert error is None
    tx = Transaction.from_bytes(wire)
    first = tx.message.instructions[0]
    assert tx.message.account_keys[first.program_id_index] == ID
    assert bytes(first.data) == bytes([4,0,0,0])
    assert tx.message.account_keys[first.accounts[0]] == nonce
    assert tx.message.account_keys[first.accounts[2]] == authority.pubkey()
    assert tx.message.recent_blockhash == nonce_hash and len(instructions) == 1
    for key,signature in zip(tx.message.account_keys,tx.signatures):
        Ed25519PublicKey.from_public_bytes(bytes(key)).verify(bytes(signature),bytes(tx.message))
    failed,error = builder.build_transaction(str(payer.pubkey()),instructions,[payer])
    assert failed is None and error
    assert executor.mock_calls == [call.get_blockhash(),call.get_blockhash()]
