import json
from pathlib import Path
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from sol_trade_sdk.serialization.v1 import compile_v1_message, sign_v1_transaction, V1Config


def test_v1_rust_golden():
    payer, co = Keypair.from_seed(bytes([7]) * 32), Keypair.from_seed(bytes([8]) * 32)
    pk = lambda n: Pubkey.from_bytes(bytes([n]) * 32)
    a, b, program = pk(3), pk(4), pk(5)
    ix = [
        Instruction(
            program,
            bytes([1, 2, 3, 4]),
            [
                AccountMeta(a, False, True),
                AccountMeta(co.pubkey(), True, False),
                AccountMeta(b, False, False),
                AccountMeta(payer.pubkey(), True, True),
            ],
        ),
        Instruction(
            program, bytes([9, 8]), [AccountMeta(b, False, True), AccountMeta(a, False, False)]
        ),
    ]
    compiled = compile_v1_message(
        payer.pubkey(), ix, str(pk(6)), V1Config(5000, 300000, 1000000, 32768)
    )
    golden = json.loads((Path(__file__).parent / "fixtures/v1_rust_4_4_1.json").read_text())
    assert list(compiled.message) == golden["message"]
    assert list(sign_v1_transaction(compiled, [co, payer])) == golden["message"] + sum(
        golden["signatures"], []
    )
    with pytest.raises(ValueError, match="Missing"):
        sign_v1_transaction(compiled, [payer])
    with pytest.raises(ValueError):
        compile_v1_message(payer.pubkey(), ix, str(pk(6)), V1Config(heap_size=32769))
    with pytest.raises(ValueError):
        compile_v1_message(payer.pubkey(), ix * 33, str(pk(6)))
    with pytest.raises(ValueError, match="4096"):
        compile_v1_message(payer.pubkey(), [Instruction(program, bytes(4096), [])], str(pk(6)))
