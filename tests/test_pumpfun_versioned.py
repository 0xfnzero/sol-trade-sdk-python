import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.pumpfun_builder import (
    PumpFunParams, PumpFunVersion, build_buy_instructions, build_sell_instructions,
    get_bonding_curve_pda, TOKEN_PROGRAM_2022,
)
from dataclasses import replace


def test_v1_preserves_native_settlement_and_rejects_token_endpoints():
    mint, payer = [Pubkey.from_bytes(bytes([n])*32) for n in (1, 3)]
    p = PumpFunParams(version=PumpFunVersion.LEGACY, bonding_curve_account=get_bonding_curve_pda(mint),
        virtual_token_reserves=1000000, virtual_sol_reserves=1000000, real_token_reserves=800000,
        token_program=TOKEN_PROGRAM_2022)
    sol = Pubkey.from_string('So11111111111111111111111111111111111111111')
    for endpoint in (None, Pubkey.default(), sol):
        buy = build_buy_instructions(payer, mint, 10000, p, create_output_ata=False,
            **({} if endpoint is None else {"input_mint": endpoint}))
        sell = build_sell_instructions(payer, mint, 10000, p, fixed_output_amount=7,
            **({} if endpoint is None else {"output_mint": endpoint}))
        assert len(buy) == len(sell) == 1
        assert buy[0].data[:8].hex() == '38fc74089edfcd5f'
        assert sell[0].data[:8].hex() == '33e685a4017f83ad'
        assert int.from_bytes(sell[0].data[16:24], 'little') == 7
    for endpoint in (Pubkey.from_string('So11111111111111111111111111111111111111112'),
                     Pubkey.from_string('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
                     Pubkey.from_bytes(bytes([4])*32)):
        with pytest.raises(ValueError, match="wallet SOL"):
            build_buy_instructions(payer, mint, 10000, p, input_mint=endpoint)
        with pytest.raises(ValueError, match="wallet SOL"):
            build_sell_instructions(payer, mint, 10000, p, output_mint=endpoint)
    assert p.version == PumpFunVersion.LEGACY


def test_v3_stock_quote_programs_and_protected_amounts():
    mint,quote,payer=[Pubkey.from_bytes(bytes([n])*32) for n in (1,2,3)]
    p=PumpFunParams(version=PumpFunVersion.V3,bonding_curve_account=get_bonding_curve_pda(mint),
        virtual_token_reserves=1000000,virtual_sol_reserves=1000000,real_token_reserves=800000,
        token_program=TOKEN_PROGRAM_2022,quote_mint=quote,quote_token_program=TOKEN_PROGRAM_2022,
        minimum_output_amount=7,base_transfer_fee_bps=0,quote_transfer_fee_bps=0)
    def buy(params=p):
        return build_buy_instructions(payer,mint,100,params,input_mint=quote,create_output_ata=False)
    for ix in (buy()[0],build_sell_instructions(payer,mint,100,p,output_mint=quote)[0]):
        assert len(ix.accounts)==17
        assert ix.accounts[2].pubkey==quote
        assert ix.accounts[4].pubkey==TOKEN_PROGRAM_2022
        assert int.from_bytes(ix.data[8:16],'little')==100
        assert int.from_bytes(ix.data[16:24],'little')==7
    for changed in (replace(p,version=PumpFunVersion.LEGACY),replace(p,quote_transfer_fee_bps=None),
                    replace(p,quote_transfer_fee_bps=1),replace(p,complete=True)):
        with pytest.raises(ValueError):buy(changed)
    sell = build_sell_instructions(payer,mint,100,p,output_mint=quote,fixed_output_amount=99)[0]
    assert int.from_bytes(sell.data[16:24], 'little') == 99
    with pytest.raises(ValueError, match="nonzero"):
        build_sell_instructions(payer,mint,100,p,output_mint=quote,fixed_output_amount=0)
    with pytest.raises(ValueError, match="explicit fixed output"):
        build_buy_instructions(payer,mint,100,p,input_mint=quote,use_exact_sol_amount=False)
    exact = build_buy_instructions(payer,mint,100,p,input_mint=quote,
        use_exact_sol_amount=False,fixed_output_amount=55,create_output_ata=False)[0]
    assert exact.data[:8].hex() == '07051dc4f5176550'
    assert int.from_bytes(exact.data[8:16], 'little') == 55
    assert int.from_bytes(exact.data[16:24], 'little') == 100


def test_v3_native_maximum_input_and_settlement():
    mint, payer = [Pubkey.from_bytes(bytes([n])*32) for n in (1,3)]
    sol = Pubkey.from_string('So11111111111111111111111111111111111111111')
    wsol = Pubkey.from_string('So11111111111111111111111111111111111111112')
    p = PumpFunParams(version=PumpFunVersion.V3,bonding_curve_account=get_bonding_curve_pda(mint),
        virtual_token_reserves=1000000,virtual_sol_reserves=1000000,real_token_reserves=800000,
        token_program=TOKEN_PROGRAM_2022)
    ix = build_buy_instructions(payer,mint,10000,p,input_mint=sol,
        use_exact_sol_amount=False,slippage_bps=1000,create_output_ata=False)[0]
    assert ix.data[:8].hex() == '07051dc4f5176550'
    assert int.from_bytes(ix.data[8:16], 'little') == 9806
    assert int.from_bytes(ix.data[16:24], 'little') == 11000
    exact_in = build_buy_instructions(payer,mint,10000,p,create_output_ata=False)[0]
    assert exact_in.data[:8].hex() == 'e1f7501ed5b38488'
    with pytest.raises(ValueError, match="wallet SOL"):
        build_buy_instructions(payer,mint,10000,p,input_mint=wsol)
    with pytest.raises(ValueError, match="wallet SOL"):
        build_sell_instructions(payer,mint,10000,p,output_mint=wsol)
