import pytest
from solders.pubkey import Pubkey
from src import PumpFunParams
from src.instruction.pumpfun_builder import (reconcile_mayhem_mode_for_trade,
    fee_recipient_ok_for_bonding_curve_mode, _pump_fun_fee_recipient,
    FEE_RECIPIENT, MAYHEM_FEE_RECIPIENTS, STANDARD_BONDING_FEE_RECIPIENTS,
    PumpFunParams as BuilderParams)
@pytest.mark.parametrize('key,expected', [
    (Pubkey.default(),[False,False,True]),
    (FEE_RECIPIENT,[False,False,False]),
    (MAYHEM_FEE_RECIPIENTS[0],[True,True,True]),
    (STANDARD_BONDING_FEE_RECIPIENTS[1],[False,False,True]),
    (Pubkey.from_bytes(bytes([42])*32),[False,False,True]),
])
def test_fee_mode_reconciliation(key,expected):
    for flag,wanted in zip([None,False,True],expected):
        assert reconcile_mayhem_mode_for_trade(flag,key) is wanted
        assert PumpFunParams.from_parser_trade_event(dict(fee_recipient=key,mayhem_mode=flag)).bonding_curve.is_mayhem_mode is wanted

def test_fee_recipient_fallback_and_rotation():
    assert _pump_fun_fee_recipient(BuilderParams(fee_recipient=MAYHEM_FEE_RECIPIENTS[0]))==FEE_RECIPIENT
    assert _pump_fun_fee_recipient(BuilderParams(fee_recipient=STANDARD_BONDING_FEE_RECIPIENTS[1],is_mayhem_mode=True)) in MAYHEM_FEE_RECIPIENTS
    unknown=Pubkey.from_bytes(bytes([42])*32)
    for flag in [False,True]:
        assert _pump_fun_fee_recipient(BuilderParams(fee_recipient=unknown,is_mayhem_mode=flag))==unknown
    assert not fee_recipient_ok_for_bonding_curve_mode(Pubkey.default(),False)

@pytest.mark.parametrize('flag', [0,1,'false'])
def test_bad_flag(flag):
    with pytest.raises(ValueError,match='boolean'):
        reconcile_mayhem_mode_for_trade(flag,FEE_RECIPIENT)
