"""Token-2022 terminator behavior cross-checked with the official SPL oracle."""
import base64
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from src.instruction.token2022_hook import resolve_hook_accounts
CASES=json.loads((Path(__file__).parent/'fixtures/hook_mint_tlv_20261009.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_hook_mint_tlv_terminator(case):
 args=[Pubkey.from_string(case[k])if k in ['hook','mint','mint_owner','meta','meta_owner']else base64.b64decode(case[k])for k in ['hook','mint','mint_owner','mint_data','meta','meta_owner','meta_data']]+[[Pubkey.from_string(k)for k in case['execute_accounts']]]
 data=base64.b64decode(case['execute_data']);accounts={Pubkey.from_string(k):base64.b64decode(v)for k,v in case['account_data'].items()}
 if case['expected_active']:
  assert [str(a.pubkey)for a in resolve_hook_accounts(*args,data,accounts)]==case['expected_accounts']
 else:
  with pytest.raises(ValueError,match='Active Hook program mismatch'):resolve_hook_accounts(*args,data,accounts)
