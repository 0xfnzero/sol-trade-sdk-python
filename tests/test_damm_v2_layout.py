import base64,json
from dataclasses import fields,is_dataclass
from pathlib import Path
from solders.pubkey import Pubkey
from src.instruction.meteora_damm_v2_builder import decode_meteora_pool
FIXTURE=json.loads((Path(__file__).parent/'fixtures/damm_v2_layout_rust_5_0_6.json').read_text())
DATA=base64.b64decode(FIXTURE['payload'])
def canonical(v):
    if isinstance(v,Pubkey):return list(bytes(v))
    if is_dataclass(v):return {f.name:canonical(getattr(v,f.name)) for f in fields(v)}
    if isinstance(v,bytes):return list(v)
    if isinstance(v,list):return [canonical(x) for x in v]
    if isinstance(v,int) and v>2**53-1:return str(v)
    return v

def test_every_pinned_rust_borsh_field():
    assert len(DATA)==1104
    assert canonical(decode_meteora_pool(DATA))==FIXTURE['expected']
def test_truncated_and_extended_payload():
    assert decode_meteora_pool(DATA[:-1]) is None
    assert canonical(decode_meteora_pool(DATA+bytes(32)))==FIXTURE['expected']
