import base64, json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.token_mint_state import token_transfer_fee_for_epoch
CASES=json.loads((Path(__file__).parent/'fixtures/token_hook_bank_20261008.json').read_text())['cases']
@pytest.mark.parametrize('case', CASES, ids=lambda c:c['name'])
def test_actual_bank_hook_mint(case):
 data=base64.b64decode(case['data']);owner=Pubkey.from_string(case['owner'])
 if case['reject_hook']:
  with pytest.raises(ValueError,match='hook'):token_transfer_fee_for_epoch(data,owner,0)
 else:assert token_transfer_fee_for_epoch(data,owner,0).calculate(10001)==0
