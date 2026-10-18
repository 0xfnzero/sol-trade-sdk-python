"""One real failed Buy, shared byte-for-byte with Rust/Go/Node fixtures."""
import base64
import json
import os
from dataclasses import replace
from pathlib import Path

import base58
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction import pumpswap_builder as ps

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/pumpswap_reported_failure.json').read_text())
PAYER = Keypair.from_seed(bytes([7]) * 32).pubkey()


def key(i):
    return Pubkey.from_string(FIXTURE['instruction_accounts'][i])


def pool():
    accounts = {a['address']: base64.b64decode(a['data_base64']) for a in FIXTURE['accounts']}
    state = ps.decode_pool_account(accounts[str(key(0))])
    return ps.PumpSwapParams(
        pool=key(0), base_mint=key(3), quote_mint=key(4),
        pool_base_token_account=key(7), pool_quote_token_account=key(8),
        pool_base_token_reserves=int.from_bytes(accounts[str(key(7))][64:72], 'little'),
        pool_quote_token_reserves=int.from_bytes(accounts[str(key(8))][64:72], 'little'),
        virtual_quote_reserves=state.virtual_quote_reserves,
        coin_creator=state.coin_creator,
        coin_creator_vault_authority=ps.get_coin_creator_vault_authority(state.coin_creator),
        coin_creator_vault_ata=ps.get_coin_creator_vault_ata(state.coin_creator, key(4), key(12)),
        base_token_program=key(11), quote_token_program=key(12),
        protocol_fee_recipient_override=key(9), protocol_extra_fee_recipient_override=key(24),
    )


def request(p=None, cls=ps.BuildBuyParams, **kwargs):
    p = p or pool()
    return cls(payer=PAYER, protocol_params=p, input_amount=1_000_000,
               fixed_output_amount=1_000_000, slippage_basis_points=100,
               input_mint=p.quote_mint, output_mint=p.base_mint,
               create_output_mint_ata=False, **kwargs)


def test_reported_failure_original_payload_and_correct_creator_accounts():
    original = base58.b58decode(FIXTURE['instruction_data_base58'])
    args = replace(request(create_input_mint_ata=False),
                   input_amount=int.from_bytes(original[16:24], 'little'),
                   fixed_output_amount=int.from_bytes(original[8:16], 'little'))
    ix = ps.build_buy_instructions(args)[0]
    assert bytes(ix.data) == original
    assert FIXTURE['error'] == {'InstructionError': [5, {'Custom': 3007}]}
    assert key(17) == key(18) == Pubkey.default()
    assert str(ix.accounts[17].pubkey) == FIXTURE['correct_creator_vault_ata']
    assert str(ix.accounts[18].pubkey) == FIXTURE['correct_creator_vault_authority']
    for i in (0, 3, 4, 7, 8, 11, 12):
        assert ix.accounts[i].pubkey == key(i)


@pytest.mark.parametrize('change', [
    {'coin_creator_vault_ata': Pubkey.default()}, {'coin_creator_vault_authority': Pubkey.default()},
    {'coin_creator_vault_ata': Pubkey.default(), 'coin_creator_vault_authority': Pubkey.default()},
    {'coin_creator': None}, {'coin_creator_vault_ata': None},
    {'coin_creator_vault_ata': ps.get_coin_creator_vault_ata(pool().coin_creator, key(4), ps.TOKEN_PROGRAM_2022)},
    {'pool_quote_token_account': key(7)},
    {'protocol_fee_recipient_override': Pubkey.default()}, {'protocol_extra_fee_recipient_override': Pubkey.default()},
])
def test_reported_failure_rejects_bad_accounts_in_both_entrypoints(change):
    for cls, build in [(ps.BuildBuyParams, ps.build_buy_instructions), (ps.BuildSellParams, ps.build_sell_instructions)]:
        with pytest.raises(ValueError, match='PumpSwap'):
            build(request(replace(pool(), **change), cls))


@pytest.mark.parametrize('mayhem', [False, True])
@pytest.mark.parametrize('buy', [False, True])
def test_reported_failure_keeps_current_fee_recipients(mayhem, buy):
    p = replace(pool(), is_mayhem_mode=mayhem)
    cls, build = (ps.BuildBuyParams, ps.build_buy_instructions) if buy else (ps.BuildSellParams, ps.build_sell_instructions)
    args = replace(request(p, cls), fixed_output_amount=None,
                   input_mint=p.quote_mint if buy else p.base_mint,
                   output_mint=p.base_mint if buy else p.quote_mint)
    ix = next(ix for ix in build(args) if ix.program_id == ps.PUMPSWAP_PROGRAM)
    assert ix.accounts[9].pubkey == key(9)
    assert ix.accounts[-2].pubkey == key(24)
    assert ix.accounts[10].pubkey == ps.get_associated_token_address(key(9), p.quote_mint, p.quote_token_program)
    assert ix.accounts[-1].pubkey == ps.get_associated_token_address(key(24), p.quote_mint, p.quote_token_program)


@pytest.mark.parametrize('cls,build', [(ps.BuildBuyParams, ps.build_buy_instructions), (ps.BuildSellParams, ps.build_sell_instructions)])
def test_reported_failure_rejects_partial_endpoints(cls, build):
    for args in [replace(request(cls=cls), input_mint=None), replace(request(cls=cls), output_mint=None),
                 replace(request(cls=cls), input_mint=None, output_mint=None, input_token_program=ps.TOKEN_PROGRAM)]:
        with pytest.raises(ValueError, match='endpoint mints'):
            build(args)


def test_reported_failure_cross_language_export():
    ix = ps.build_buy_instructions(request(create_input_mint_ata=False))[0]
    assert ps.build_sell_instructions(request(cls=ps.BuildSellParams))[0] == ix
    # Pump AMM IDL marks global_volume_accumulator readonly in both Buy forms.
    assert not ix.accounts[19].is_writable
    exact_in = replace(request(create_input_mint_ata=False), fixed_output_amount=None)
    assert not ps.build_buy_instructions(exact_in)[0].accounts[19].is_writable
    directory = os.environ.get('PUMPSWAP_FIXTURE_EXPORT_DIR')
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / 'python.json').write_text(json.dumps({
            'program': str(ix.program_id), 'payer': str(PAYER), 'data_base64': base64.b64encode(ix.data).decode(),
            'accounts': [{'pubkey': str(a.pubkey), 'is_signer': a.is_signer, 'is_writable': a.is_writable} for a in ix.accounts],
        }, indent=2))
