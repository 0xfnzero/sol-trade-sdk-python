"""Native route wire parity against real deployed two-hop executions."""
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from src.instruction.pump_compact_accounts import PumpMultiHop,derive_pump_multi_hop_accounts
from src.instruction.pump_upgrade import build_pump_upgrade_instruction
CASES=json.loads((Path(__file__).parent/'fixtures/pump_routes_bank_20261009.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_native_two_hop_bank_wire(case):
 hops=[PumpMultiHop(**{k:Pubkey.from_string(v)if k in ['base_mint','quote_mint','address','base_vault','quote_vault','base_token_program','quote_token_program','creator']else v for k,v in h.items()})for h in case['hops']]
 fixed,remaining=derive_pump_multi_hop_accounts(*[Pubkey.from_string(case[k])for k in ['user','input_mint','output_mint','buyback_recipient']],hops)
 ix=build_pump_upgrade_instruction('pump_amm_multi_hop_swap',fixed,list(map(int,case['args'])),remaining=remaining)
 assert str(ix.program_id)==case['program'] and ix.data.hex()==case['data']
 assert [str(a.pubkey)for a in ix.accounts]==case['accounts']
