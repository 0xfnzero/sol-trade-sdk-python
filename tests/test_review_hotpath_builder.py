from unittest.mock import Mock, call
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.compute_budget import ID as COMPUTE_BUDGET
from src.hotpath.executor import TransactionBuilder


def setup_builder():
    executor = Mock()
    executor.get_blockhash.return_value = ('11111111111111111111111111111111', 100, True)
    payer = Keypair()
    ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=Pubkey.new_unique(), lamports=1))
    return TransactionBuilder(executor), executor, payer, ix


def test_cached_builder_signs_and_encodes_compute_budget():
    builder, executor, payer, ix = setup_builder()
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], [payer], {'compute_unit_limit': 1400000, 'compute_unit_price': 1000000})
    assert error is None
    tx = Transaction.from_bytes(wire)
    assert all(tx.verify_with_results())
    assert str(tx.message.recent_blockhash) == executor.get_blockhash.return_value[0]
    instructions = tx.message.instructions
    assert len(instructions) == 3
    assert tx.message.account_keys[instructions[0].program_id_index] == COMPUTE_BUDGET
    assert int.from_bytes(instructions[0].data[1:], 'little') == 1400000
    assert int.from_bytes(instructions[1].data[1:], 'little') == 1000000
    assert executor.mock_calls == [call.get_blockhash()]


def test_optional_budget_and_byte_signer():
    builder, _, payer, ix = setup_builder()
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], [bytes(payer)])
    assert error is None
    tx = Transaction.from_bytes(wire)
    assert len(tx.message.instructions) == 1
    assert all(tx.verify_with_results())


def test_stale_hash_returns_error():
    builder, executor, payer, ix = setup_builder()
    executor.get_blockhash.return_value = (None, 0, False)
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], [payer])
    assert wire is None and 'Stale blockhash' in error


@pytest.mark.parametrize('gas', [{'compute_unit_limit': -1, 'compute_unit_price': 1}, {'compute_unit_limit': 1, 'compute_unit_price': 1 << 64}])
def test_invalid_budget_returns_error(gas):
    builder, _, payer, ix = setup_builder()
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], [payer], gas)
    assert wire is None and 'Invalid compute budget' in error


@pytest.mark.parametrize("missing", ["empty", "wrong_payer", "instruction_signer"])
def test_missing_required_instruction_signer_returns_error_without_panicking(missing):
    builder, _, payer, _ = setup_builder()
    other = Keypair()
    ix = transfer(TransferParams(from_pubkey=other.pubkey(), to_pubkey=payer.pubkey(), lamports=1))
    signers = {"empty": [], "wrong_payer": [other], "instruction_signer": [payer]}[missing]
    wire, error = builder.build_transaction(str(payer.pubkey()), [ix], signers)
    assert wire is None and error
    assert "signer" in error.lower() or "fee payer" in error.lower()
