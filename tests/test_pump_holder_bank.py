import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from src.instruction.pump_upgrade import build_pump_upgrade_instruction
CASES=json.loads((Path(__file__).parent/'fixtures/pump_holder_bank_20261009.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_holder_bank_wire(case):
 ix=build_pump_upgrade_instruction(case['instruction'],{k:Pubkey.from_string(v)for k,v in case['roles'].items()},list(map(int,case['args'])))
 assert str(ix.program_id)==case['program'] and ix.data.hex()==case['data']
 assert [str(a.pubkey)for a in ix.accounts]==case['accounts']
