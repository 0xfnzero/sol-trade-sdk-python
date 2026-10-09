import pytest
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.keypair import Keypair
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction, VersionedTransaction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from src import TradingClient, TradeConfig, TradeType, DurableNonceInfo
from solders.errors import SignerError
from solders.message import to_bytes_versioned

@pytest.mark.parametrize('alt', [False, True])
@pytest.mark.parametrize('nonce', [False, True])
def test_actual_builder_wire_resolves_account_roles_and_signatures_without_rpc(alt, nonce, monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('implicit RPC during build')
    monkeypatch.setattr('requests.post', forbidden)
    payer, other = Keypair(), Keypair()
    nonce_account = Keypair().pubkey()
    blockhash = str(Hash.from_bytes(bytes(Keypair().pubkey())))
    client = TradingClient(payer, TradeConfig(rpc_url='http://localhost:1'))
    monkeypatch.setattr(client.client, 'get_latest_blockhash', forbidden)
    recipient = other.pubkey()
    table = AddressLookupTableAccount(Keypair().pubkey(), [recipient, nonce_account, payer.pubkey()]) if alt else None
    info = DurableNonceInfo(nonce_account, payer.pubkey(), blockhash, blockhash) if nonce else None
    ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=recipient, lamports=7))
    wired = client._build_wired_instructions([ix], TradeType.BUY, None, False, info, None, None)
    tx = client._build_transaction(wired, blockhash, table)
    parsed = VersionedTransaction.from_bytes(bytes(tx)) if alt else Transaction.from_bytes(bytes(tx))
    message = parsed.message
    message_bytes = to_bytes_versioned(message) if alt else bytes(message)
    Ed25519PublicKey.from_public_bytes(bytes(payer.pubkey())).verify(bytes(parsed.signatures[0]), message_bytes)
    keys = list(message.account_keys)
    if alt:
        assert len(message.address_table_lookups) == 1
        keys.extend(table.addresses[i] for lookup in message.address_table_lookups for i in lookup.writable_indexes)
        keys.extend(table.addresses[i] for lookup in message.address_table_lookups for i in lookup.readonly_indexes)
    assert keys[0] == payer.pubkey()
    assert keys[message.instructions[-1].accounts[1]] == recipient
    assert int.from_bytes(message.instructions[-1].data[4:12], 'little') == 7
    if nonce:
        advance = message.instructions[0]
        assert bytes(advance.data) == b'\x04\0\0\0'
        assert keys[advance.accounts[0]] == nonce_account and keys[advance.accounts[2]] == payer.pubkey()
    damaged = bytearray(message_bytes); damaged[-1] ^= 1
    with pytest.raises(InvalidSignature):
        Ed25519PublicKey.from_public_bytes(bytes(payer.pubkey())).verify(bytes(parsed.signatures[0]), bytes(damaged))
    extra = transfer(TransferParams(from_pubkey=other.pubkey(), to_pubkey=payer.pubkey(), lamports=1))
    with pytest.raises(SignerError): client._build_transaction([extra], blockhash, table)
    invalid = DurableNonceInfo(nonce_account, other.pubkey(), blockhash, blockhash)
    with pytest.raises(SignerError):
        client._build_transaction(client._build_wired_instructions([ix], TradeType.BUY, None, False, invalid, None, None), blockhash, table)
    import asyncio
    asyncio.run(client.close())
