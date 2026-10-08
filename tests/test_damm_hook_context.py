import base64,json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey as P
from src.instruction.token2022_hook import resolve_hook_accounts
CASES=json.loads((Path(__file__).parent/'fixtures/damm_hook_context_20261009.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=['fund','claim','after_end'])
def test_executed_damm_hook_context(case):
 args=[P.from_string(case[k])if k in ['hook','mint','mint_owner','meta','meta_owner']else base64.b64decode(case[k])for k in ['hook','mint','mint_owner','mint_data','meta','meta_owner','meta_data']]+[[P.from_string(k)for k in case['execute_accounts']]]
 data=base64.b64decode(case['execute_data']);accounts={P.from_string(k):base64.b64decode(v)for k,v in case['account_data'].items()}
 got=resolve_hook_accounts(*args,data,accounts);assert [str(a.pubkey)for a in got]==case['expected_accounts']
 with pytest.raises(ValueError):resolve_hook_accounts(*args)
 with pytest.raises(ValueError):resolve_hook_accounts(*args,data,{})
 with pytest.raises(ValueError):resolve_hook_accounts(*args,data[:-1],accounts)
 for offset,value in [(86,255),(96,255),(102,33),(88,31),(122,1),(122,0),(123,255),(124,255),(125,1)]:
  mutated=list(args);b=bytearray(mutated[6]);b[offset]=value;mutated[6]=bytes(b)
  with pytest.raises(ValueError):resolve_hook_accounts(*mutated,data,accounts)
 changed=bytearray(data);changed[8]+=1
 assert resolve_hook_accounts(*args,bytes(changed),accounts)[2].pubkey != got[2].pubkey
