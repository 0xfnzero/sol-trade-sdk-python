"""Repeatable native offline signed-wire tests; historical account fixtures only."""
import json
import socket
import struct
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.hash import Hash
from solders.transaction import VersionedTransaction
from solders.address_lookup_table_account import AddressLookupTableAccount
from sol_trade_sdk import (
    CacheReadContext, PoolTradeHint, PumpSwapRouteSearch, PumpSwapBuildOptions,
    prepare_best_pumpswap_trade,
)
from sol_trade_sdk.instruction import pumpswap_builder as ps
from sol_trade_sdk.trading.pumpswap_preparation import SOL_MINT
from examples.pumpswap_cached_prepare import prepare_fixture, load_snapshot

FIXTURES = Path(__file__).parent / 'fixtures'
DIRECT = FIXTURES / 'pumpswap_ttwo_accounts.json'
FULL = FIXTURES / 'pumpswap_ttwo_route_accounts.json'


def decode_v1(wire):
    """Independent small wire reader: header/config, keys, instructions, signature."""
    assert wire[0] == 129 and wire[1] == 1
    mask = int.from_bytes(wire[4:8], 'little')
    count, nkeys = wire[40:42]
    keys = tuple(Pubkey.from_bytes(wire[42+32*i:74+32*i]) for i in range(nkeys))
    cursor = 42 + 32*nkeys
    for bit, width in ((3,8),(4,4),(8,4),(16,4)):
        if mask & bit:
            cursor += width
    headers = [struct.unpack_from('<BBH', wire, cursor+4*i) for i in range(count)]
    cursor += 4*count
    instructions = []
    for program, naccounts, length in headers:
        accounts = tuple(keys[i] for i in wire[cursor:cursor+naccounts])
        cursor += naccounts
        data = wire[cursor:cursor+length]
        cursor += length
        instructions.append((keys[program], accounts, data))
    assert len(wire) == cursor + 64
    return wire[:cursor], keys, tuple(instructions)


@pytest.mark.parametrize('path,amount', [(DIRECT, 10000), (FULL, 1000000)])
@pytest.mark.parametrize('is_buy', [True, False])
def test_captured_snapshot_signed_v1_roundtrip_offline(path, amount, is_buy, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('network access in hot path')
    monkeypatch.setattr(socket, 'socket', no_network)
    signer = Keypair.from_seed(bytes([7])*32)
    trade, ctx = prepare_fixture(path, is_buy, amount if is_buy else 1000000000, signer.pubkey())
    for before, after in zip(trade.steps, trade.steps[1:]):
        assert after.amount_in == before.minimum_net_amount_out
        assert after.hint.input_mint == before.hint.output_mint
    options = PumpSwapBuildOptions(Hash.default(), temporary_wsol_seed='test-offline', rent_lamports=2039280)
    a = trade.build_transaction(signer, ctx, options)
    b = trade.build_transaction(signer, ctx, options)
    assert a.wire == b.wire  # Stable accounts, recipient selection and signatures.
    message, keys, decoded = decode_v1(a.wire)
    assert message == a.message and keys[0] == signer.pubkey()
    assert a.signature.verify(signer.pubkey(), message)
    actual = [(p, data[:8]) for p, _, data in decoded if p in (ps.PUMPSWAP_PROGRAM,)]
    expected = ps.BUY_EXACT_QUOTE_IN_DISCRIMINATOR if is_buy else ps.SELL_DISCRIMINATOR
    assert actual == [(ps.PUMPSWAP_PROGRAM, expected)]
    if path == FULL:
        assert len(trade.steps) == 3
        assert (trade.input_mint if is_buy else trade.output_mint) == SOL_MINT
        assert a.required_native_lamports == 2039280 + (amount if is_buy else 0)
        temporary = next(accounts[1] for p, accounts, data in decoded
                         if p == ps.SYSTEM_PROGRAM and data[:4] == struct.pack('<I',3))
        assert decoded[-1][0] == ps.TOKEN_PROGRAM and decoded[-1][2] == bytes([9])
        assert decoded[-1][1][0] == temporary
        swaps = [d for d in decoded if d[0] in (ps.PUMPSWAP_PROGRAM,)]
        # No original WSOL ATA is closed by native settlement.
        assert all(a != ps.get_associated_token_address(signer.pubkey(), ps.WSOL_TOKEN_ACCOUNT)
                   for a in decoded[-1][1][:1])


@pytest.mark.parametrize('is_buy', [True, False])
def test_v0_real_signing_with_alt_and_full_nonce_tip(is_buy):
    signer = Keypair()
    trade, ctx = prepare_fixture(FULL, is_buy, 1000000 if is_buy else 1000000000, signer.pubkey())
    with pytest.raises(ValueError, match='1232'):
        trade.build_transaction(signer, ctx, PumpSwapBuildOptions(Hash.default(), 'v0',
            temporary_wsol_seed='v0-test', rent_lamports=2039280))
    base = trade.build_transaction(signer, ctx, PumpSwapBuildOptions(Hash.default(),
            temporary_wsol_seed='v0-test', rent_lamports=2039280))
    # Synthetic ALT validates compilation only; it is not an on-chain ALT.
    addresses = sorted({a.pubkey for ix in base.instructions for a in ix.accounts if not a.is_signer}, key=bytes)
    alt = AddressLookupTableAccount(Pubkey.new_unique(), addresses)
    nonce, recipient, nonce_hash = Pubkey.new_unique(), Pubkey.new_unique(), Hash.new_unique()
    built = trade.build_transaction(signer, ctx, PumpSwapBuildOptions(Hash.default(), 'v0', (alt,),
        nonce, nonce_hash, recipient, 100000, temporary_wsol_seed='v0-test', rent_lamports=2039280))
    tx = VersionedTransaction.from_bytes(built.wire)
    tx.verify_and_hash_message()
    assert tx.message.recent_blockhash == nonce_hash
    assert tx.message.address_table_lookups[0].account_key == alt.key
    assert bytes(tx.message.instructions[0].data) == struct.pack('<I',4)
    assert built.signature.verify(signer.pubkey(), built.message)
    assert len(built.wire) <= 1232 and built.required_native_lamports == base.required_native_lamports+100000
    v1 = trade.build_transaction(signer, ctx, PumpSwapBuildOptions(Hash.default(), nonce_account=nonce,
        nonce_hash=nonce_hash, tip_account=recipient, tip_lamports=100000,
        temporary_wsol_seed='nonce-v1', rent_lamports=2039280))
    _, _, decoded = decode_v1(v1.wire)
    assert v1.message[8:40] == bytes(nonce_hash)
    assert decoded[0][2] == struct.pack('<I',4)
    assert decoded[-1] == (ps.SYSTEM_PROGRAM, (signer.pubkey(),recipient), struct.pack('<IQ',2,100000))


def test_freshness_and_offline_build_guards():
    signer = Keypair()
    trade, ctx = prepare_fixture(DIRECT, True, 10000, signer.pubkey())
    trade.validate_freshness(replace(ctx,slot=ctx.slot+24))
    for bad in (replace(ctx,epoch=ctx.epoch+1),replace(ctx,slot=ctx.slot-1),
                replace(ctx,slot=ctx.slot+25),replace(ctx,slot=ctx.slot+1,maximum_slot_age=0)):
        with pytest.raises(ValueError):
            trade.validate_freshness(bad)
    for opts in (PumpSwapBuildOptions(Hash.default(),version='legacy'),
                 PumpSwapBuildOptions(Hash.default(),nonce_account=Pubkey.new_unique()),
                 PumpSwapBuildOptions(Hash.default(),tip_lamports=1),
                 PumpSwapBuildOptions(Hash.default(),tip_lamports=-1),
                 PumpSwapBuildOptions(Hash.default(),tip_lamports=0.0001),
                 PumpSwapBuildOptions(Hash.default(),address_lookup_tables=(object(),))):
        with pytest.raises(ValueError):
            trade.build_transaction(signer,ctx,opts)
    with pytest.raises(ValueError,match='payer'):
        trade.build_transaction(Keypair(),ctx,PumpSwapBuildOptions(Hash.default()))
    from solders.instruction import Instruction,AccountMeta
    def add_signer(instructions):
        return instructions+(Instruction(ps.SYSTEM_PROGRAM,b'', [AccountMeta(Pubkey.new_unique(),True,False)]),)
    with pytest.raises(ValueError,match='extra'):
        trade.build_transaction(signer,ctx,PumpSwapBuildOptions(Hash.default(),transaction_middleware=add_signer))


def search_fixture():
    d, snapshot, ctx = load_snapshot(DIRECT)
    base, _ = prepare_fixture(DIRECT,True,10000,Keypair().pubkey())
    token, quote = base.output_mint, base.input_mint
    asset = Pubkey.new_unique()
    hints = (PoolTradeHint(Pubkey.from_bytes(bytes([1])*32), asset, quote),
             PoolTradeHint(Pubkey.from_bytes(bytes([2])*32), quote, asset))
    class ControlledSnapshot:
        assert_usable = snapshot.assert_usable
        def get(self,key,context,expected_owner=None):
            if key in (h.pool for h in candidates):
                return SimpleNamespace(owner=Pubkey.new_unique())
            return snapshot.get(key,context,expected_owner)
        pumpswap = snapshot.pumpswap
        def prepare_route(self,hints,context,*args):
            # Distinct known quote outputs test ranking rather than generic BFS.
            amount = 100 if hints[0].pool == candidates[0].pool else 200
            return SimpleNamespace(legs=tuple(SimpleNamespace(hint=h) for h in hints), minimum_net_amount_out=amount)
    candidates = hints
    return ControlledSnapshot(),ctx,base.request,PumpSwapRouteSearch(Pubkey.from_string(d['pool']),token,asset,hints)


def test_best_output_not_first_path_and_byte_order_independent():
    snapshot,ctx,request,search = search_fixture()
    a = prepare_best_pumpswap_trade(snapshot,search,request,ctx,True)
    b = prepare_best_pumpswap_trade(snapshot,replace(search,conversion_pools=search.conversion_pools[::-1]),request,ctx,True)
    assert a.trade.minimum_output_credit == 200
    assert a.routes_evaluated == b.routes_evaluated == 2
    assert a.trade.steps[0].hint.pool == b.trade.steps[0].hint.pool == search.conversion_pools[1].pool
    duplicate = replace(search,conversion_pools=search.conversion_pools+(replace(search.conversion_pools[0],input_mint=search.conversion_pools[0].output_mint,output_mint=search.asset_mint),))
    assert prepare_best_pumpswap_trade(snapshot,duplicate,request,ctx,True).routes_evaluated==2


def test_search_exhaustion_invalid_conflicting_and_stale_candidates():
    snapshot,ctx,request,search = search_fixture()
    # A root and two complete paths require 3 nodes; no partial result on budget 2.
    with pytest.raises(ValueError,match='budget exhausted'):
        prepare_best_pumpswap_trade(snapshot,replace(search,maximum_search_nodes=2),request,ctx,True)
    for kwargs in ({'maximum_conversion_hops':4},{'maximum_search_nodes':0},{'conversion_pools':search.conversion_pools*17}):
        with pytest.raises(ValueError,match='limits'):
            prepare_best_pumpswap_trade(snapshot,replace(search,**kwargs),request,ctx,True)
    bad = replace(search.conversion_pools[0],output_mint=Pubkey.new_unique())
    with pytest.raises(ValueError,match='Conflicting'):
        prepare_best_pumpswap_trade(snapshot,replace(search,conversion_pools=search.conversion_pools+(bad,)),request,ctx,True)
    original = snapshot.prepare_route
    def reject_one(hints,*args):
        if hints[0].pool==search.conversion_pools[0].pool:
            raise ValueError('stale cached account')
        return original(hints,*args)
    snapshot.prepare_route = reject_one
    selection = prepare_best_pumpswap_trade(snapshot,search,request,ctx,True)
    assert selection.trade.minimum_output_credit==200 and len(selection.rejected_routes)==1
    assert 'stale' in selection.rejected_routes[0].reason


def test_custom_quote_direct_directions_creator_and_program_validation():
    from test_pumpswap_fee_parity import params
    quote, token, payer = Pubkey.new_unique(),Pubkey.new_unique(),Pubkey.new_unique()
    pool = params(base_mint=token,quote_mint=quote,quote_token_program=ps.TOKEN_PROGRAM_2022)
    buy = ps.build_buy_instructions(ps.BuildBuyParams(payer,10000,100,pool,False,False,False))[-1]
    assert buy.data[:8]==ps.BUY_EXACT_QUOTE_IN_DISCRIMINATOR
    sell = ps.build_sell_instructions(ps.BuildSellParams(payer,10000,100,pool,False))[-1]
    assert sell.data[:8]==ps.SELL_DISCRIMINATOR
    reverse = ps.build_sell_instructions(ps.BuildSellParams(payer,10000,100,pool,False,input_mint=quote,output_mint=token))[-1]
    assert reverse.data[:8]==ps.BUY_EXACT_QUOTE_IN_DISCRIMINATOR
    for overrides in ({'coin_creator_vault_ata':Pubkey.new_unique()},
                      {'coin_creator_vault_authority':Pubkey.new_unique()},
                      {'coin_creator':None},{'base_token_program':Pubkey.new_unique()}):
        with pytest.raises(ValueError):
            ps.build_buy_instructions(ps.BuildBuyParams(payer,10000,100,replace(pool,**overrides)))
    with pytest.raises(ValueError,match='conversion'):
        ps.build_buy_instructions(ps.BuildBuyParams(payer,10000,100,pool,input_mint=ps.WSOL_TOKEN_ACCOUNT,output_mint=token))
    with pytest.raises(ValueError,match='program'):
        ps.build_buy_instructions(ps.BuildBuyParams(payer,10000,100,pool,input_token_program=ps.TOKEN_PROGRAM))
    assert ps.handle_wsol(payer,10000)[1].data==struct.pack('<IQ',2,10000)


def test_ties_use_pubkey_bytes_and_fewer_hops():
    snapshot,ctx,request,search = search_fixture()
    def equal_output(hints,*args):
        return SimpleNamespace(legs=tuple(SimpleNamespace(hint=h) for h in hints),minimum_net_amount_out=300)
    snapshot.prepare_route = equal_output
    choice = prepare_best_pumpswap_trade(snapshot,replace(search,conversion_pools=search.conversion_pools[::-1]),request,ctx,True)
    assert choice.trade.steps[0].hint.pool==search.conversion_pools[0].pool
    # An extra intermediate candidate gives a second, longer path with equal output.
    intermediate = Pubkey.new_unique()
    one,two = search.conversion_pools
    extra1 = PoolTradeHint(Pubkey.new_unique(),search.asset_mint,intermediate)
    extra2 = PoolTradeHint(Pubkey.new_unique(),intermediate,one.output_mint)
    original_get = snapshot.get
    snapshot.get=lambda key,*args: SimpleNamespace(owner=Pubkey.new_unique()) if key in (extra1.pool,extra2.pool) else original_get(key,*args)
    selected=prepare_best_pumpswap_trade(snapshot,replace(search,conversion_pools=(extra1,extra2,one)),request,ctx,True)
    assert selected.routes_evaluated==2 and len(selected.trade.steps)==2


def test_dead_ends_consume_search_budget_and_token_intermediate_excluded():
    snapshot,ctx,request,search=search_fixture()
    live=search.conversion_pools[0]
    dead=PoolTradeHint(Pubkey.new_unique(),search.asset_mint,Pubkey.new_unique())
    with pytest.raises(ValueError,match='budget exhausted'):
        prepare_best_pumpswap_trade(snapshot,replace(search,conversion_pools=(live,dead),maximum_search_nodes=2),request,ctx,True)
    # A path through the traded token is excluded before recursion.
    through=PoolTradeHint(Pubkey.new_unique(),search.asset_mint,search.token_mint)
    blocked=replace(search,conversion_pools=(through,))
    with pytest.raises(ValueError,match='No conversion path'):
        prepare_best_pumpswap_trade(snapshot,blocked,request,ctx,True)


def test_new_pumpswap_floor_and_cashback_layout():
    from test_pumpswap_fee_parity import params
    assert ps.minimum_output_with_slippage(101,100)==99
    assert ps.minimum_output_with_slippage(1,100)==0
    creator,quote,payer=Pubkey.new_unique(),Pubkey.new_unique(),Pubkey.new_unique()
    pool=params(quote_mint=quote,coin_creator=creator,is_cashback_coin=True,quote_token_program=ps.TOKEN_PROGRAM_2022)
    quote_ata=ps.get_user_volume_accumulator_quote_ata(payer,quote,ps.TOKEN_PROGRAM_2022)
    for is_quote_input in (True,False):
        source,target=(pool.quote_mint,pool.base_mint) if is_quote_input else (pool.base_mint,pool.quote_mint)
        ix=ps.build_buy_instructions(ps.BuildBuyParams(payer,1000000,100,pool,False,False,False,input_mint=source,output_mint=target))[-1]
        start=23 if is_quote_input else 21
        assert ix.accounts[start].pubkey==quote_ata
        if not is_quote_input:
            assert ix.accounts[start+1].pubkey==ps.get_user_volume_accumulator_pda(payer)
        else:
            assert ix.data[-1]==1


def test_account_setup_policy_and_both_middlewares():
    signer=Keypair()
    trade,ctx=prepare_fixture(DIRECT,True,10000,signer.pubkey())
    calls=[]
    def protocol(instructions):
        calls.append('protocol')
        return instructions
    def full(instructions):
        calls.append('transaction')
        return instructions
    built=trade.build_transaction(signer,ctx,PumpSwapBuildOptions(Hash.default(),
        protocol_middleware=protocol,transaction_middleware=full,create_associated_accounts=False))
    assert calls==['protocol','transaction']
    assert len(built.instructions)==1 and built.instructions[0].program_id==ps.PUMPSWAP_PROGRAM
    assert built.signature.verify(signer.pubkey(),built.message)
