"""Real bank mint layouts, including pending schedules and mint-withheld bytes."""
import base64
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.token_mint_state import token_transfer_fee_for_epoch

CASES=json.loads((Path(__file__).parent/'fixtures/token2022_bank_fee_20261008.json').read_text())['cases']

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_bank_mint_epoch_and_fee(case):
    fee=token_transfer_fee_for_epoch(base64.b64decode(case['data']),Pubkey.from_string(case['owner']),int(case['epoch']))
    assert fee.basis_points==case['basis_points']
    assert fee.maximum_fee==int(case['maximum_fee'])
    for sample in case['samples']:
        assert fee.calculate(int(sample['amount']))==int(sample['fee'])
