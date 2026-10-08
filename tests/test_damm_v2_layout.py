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

def legacy_projection(actual, expected):
    if isinstance(expected,dict):return {k:legacy_projection(actual[k],v) for k,v in expected.items()}
    if isinstance(expected,list):
        assert len(actual) == len(expected)
        return [legacy_projection(a,e) for a,e in zip(actual,expected)]
    return actual

def test_every_pinned_rust_borsh_field():
    assert len(DATA)==1104
    assert legacy_projection(canonical(decode_meteora_pool(DATA)),FIXTURE['expected'])==FIXTURE['expected']
def test_truncated_and_extended_payload():
    assert decode_meteora_pool(DATA[:-1]) is None
    assert legacy_projection(canonical(decode_meteora_pool(DATA+bytes(32))),FIXTURE['expected'])==FIXTURE['expected']
def test_current_official_damm_v2_fields():
    f=json.loads((Path(__file__).parent/'fixtures/damm_v2_current.json').read_text())
    p=decode_meteora_pool(base64.b64decode(f['payload']))
    assert p.pool_fees.compounding_fee_bps == 321
    assert p.pool_fees.init_sqrt_price == (1<<100)+123
    assert p.dead_liquidity_fee_checkpoint == 987654321
    assert p.fee_version == p.layout_version == 1
    assert list(bytes(p.creator)) == f['expected']['creator']
    assert p.token_a_amount == 9007199254740993
    assert p.token_b_amount == 9007199254740995
    assert p.sqrt_price == (1<<64)+1234
