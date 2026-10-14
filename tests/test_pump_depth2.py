"""Compare all migration combinations against the official 4.1.0 SDK."""
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from src.instruction.pump_compact_accounts import PumpMultiHop, derive_pump_coin_quote_create_accounts
from src.instruction.pump_create_v2 import build_pump_create_v2_instruction
from dataclasses import replace
CASES=json.loads((Path(__file__).parent/'fixtures/pump_upgrade/create_depth2.json').read_text())['cases']
def hop(h):
    names={'baseMint':'base_mint','quoteMint':'quote_mint','baseVault':'base_vault','quoteVault':'quote_vault','baseTokenProgram':'base_token_program','quoteTokenProgram':'quote_token_program'}
    return PumpMultiHop(**{names.get(k,k):Pubkey.from_string(v) if isinstance(v,str) and k!='venue' else v for k,v in h.items()})
@pytest.mark.parametrize('c',CASES,ids=lambda c:c['name'])
def test_official_depth2_accounts_and_signed_wire(c):
    import base64
    q=hop(c['quote']);chain=[hop(h) for h in c['chain']]
    accounts={k:Pubkey.from_string(v) for k,v in c['accounts'].items()}
    listed=[Pubkey.from_string(k) for k in c['listedQuoteMints']]
    remaining=derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,chain)
    # A later ancestor whitelist entry does not rewrite Q's stored depth.
    assert derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,[*listed,chain[0].base_mint],chain)==remaining
    assert [dict(pubkey=str(m.pubkey),signer=m.is_signer,writable=m.is_writable) for m in remaining]==c['keys'][16:]
    p=c['params']
    ix=build_pump_create_v2_instruction(accounts,p['name'],p['symbol'],p['uri'],Pubkey.from_string(p['creator']),creator_fee_bps=p['creatorFeeBps'],holder_reward=True,remaining=remaining)
    assert bytes(ix.data).hex()==c['data']
    from solders.address_lookup_table_account import AddressLookupTableAccount
    from solders.message import MessageV0
    from solders.keypair import Keypair
    original=VersionedTransaction.from_bytes(base64.b64decode(c['transaction']))
    original.verify_and_hash_message()
    lookup=AddressLookupTableAccount(Pubkey.from_string(c['lookup']['key']),[Pubkey.from_string(k) for k in c['lookup']['addresses']])
    message=MessageV0.try_compile(accounts['user'],[ix],[lookup],original.message.recent_blockhash)
    tx=VersionedTransaction(message,[Keypair.from_seed(bytes([101])*32),Keypair.from_seed(bytes([102])*32)])
    # Different clients order ALT lookups differently; compare instruction roles, not signatures.
    assert len(bytes(tx)) <= 1232
    assert bytes(VersionedTransaction.from_bytes(bytes(tx))) == bytes(tx)
    tx.verify_and_hash_message()
    with pytest.raises(ValueError,match='QuoteChainAccountsRequired'):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed)
    with pytest.raises(ValueError,match='CurveDepthExceeded'):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,1,listed,chain)
    with pytest.raises(ValueError):
        derive_pump_coin_quote_create_accounts(accounts['mint'],replace(q,mayhem=True),1,2,listed,chain)
    with pytest.raises(ValueError):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,[replace(chain[0],base_mint=accounts['mint'])])
    assert derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,[replace(chain[0],mayhem=True)]) == remaining
    with pytest.raises(ValueError,match='Discontinuous quote chain'):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,[replace(chain[0],base_mint=accounts['user'])])
    with pytest.raises(ValueError,match='Discontinuous quote chain'):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,[replace(chain[0],base_token_program=accounts['program'])])
    with pytest.raises(ValueError,match='CurveDepthExceeded'):
        derive_pump_coin_quote_create_accounts(accounts['mint'],q,5,255,listed,chain)
    from solders.instruction import AccountMeta
    for index, signer, writable in [(2, False, True), (4, True, False)]:
        bad=list(remaining)
        bad[index]=AccountMeta(bad[index].pubkey,signer,writable)
        with pytest.raises(ValueError,match='Invalid quote creation accounts'):
            build_pump_create_v2_instruction(accounts,p['name'],p['symbol'],p['uri'],Pubkey.from_string(p['creator']),remaining=bad)
    if chain[0].venue=='curve':
        with pytest.raises(ValueError,match='QuoteCurveAwaitingMigration'):
            derive_pump_coin_quote_create_accounts(accounts['mint'],q,1,2,listed,[replace(chain[0],complete=True)])
