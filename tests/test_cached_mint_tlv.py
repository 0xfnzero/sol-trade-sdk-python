import base64
import json
from pathlib import Path
import pytest
from src.instruction.token_mint_state import TOKEN2022, token_transfer_fee_for_epoch

CASES = json.loads((Path(__file__).parent / 'fixtures/cached_mint_tlv_20261009.json').read_text())['cases']

@pytest.mark.parametrize('case', CASES, ids=lambda c: c['name'])
def test_cached_mint_tlv(case):
    data = base64.b64decode(case['mint_data'])
    if not case['eligible']:
        with pytest.raises(ValueError):
            token_transfer_fee_for_epoch(data, TOKEN2022, case['epoch'])
    else:
        fee = token_transfer_fee_for_epoch(data, TOKEN2022, case['epoch'])
        assert (fee.basis_points, fee.maximum_fee) == (case['basis_points'], case['maximum_fee'])
