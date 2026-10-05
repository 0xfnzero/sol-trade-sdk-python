from dataclasses import replace
import pytest
from solders.pubkey import Pubkey
from src.trading.cached_pumpfun_config import cached_pumpfun_configuration, decode_pumpfun_global_fee_recipient, decode_pumpfun_sharing_creator_vault
from src.trading.subscription_cache import AccountCacheSnapshot, CachedAccount, CacheReadContext
from src.instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID, GLOBAL_ACCOUNT, FEE_PROGRAM, get_fee_sharing_config_pda, get_creator_vault_pda

MINT=Pubkey.from_string('So11111111111111111111111111111111111111112')
RECIPIENT=Pubkey.from_string('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')
CONTEXT=CacheReadContext(100,1,5)

def fixture():
    g=bytearray(73);g[:8]=bytes([167,232,232,177,200,108,114,127]);g[41:73]=bytes(RECIPIENT)
    s=bytearray(43);s[:8]=bytes([216,74,9,0,56,140,93,75]);s[10]=1;s[11:43]=bytes(MINT)
    return {GLOBAL_ACCOUNT:CachedAccount(PUMPFUN_PROGRAM_ID,bytes(g),100,0),get_fee_sharing_config_pda(MINT):CachedAccount(FEE_PROGRAM,bytes(s),100,0)}

def test_current_recipient_and_active_vault(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *args:pytest.fail('network in cached config'))
    state=cached_pumpfun_configuration(AccountCacheSnapshot(fixture()),MINT,CONTEXT)
    assert state.fee_recipient==RECIPIENT
    assert state.fee_sharing_creator_vault_if_active==get_creator_vault_pda(state.sharing_config)

def test_inactive_is_not_missing():
    a=fixture();key=get_fee_sharing_config_pda(MINT);d=bytearray(a[key].data);d[10]=0;a[key]=replace(a[key],data=bytes(d))
    assert cached_pumpfun_configuration(AccountCacheSnapshot(a),MINT,CONTEXT).fee_sharing_creator_vault_if_active is None
    del a[key]
    with pytest.raises(ValueError,match='Missing cached'):cached_pumpfun_configuration(AccountCacheSnapshot(a),MINT,CONTEXT)

@pytest.mark.parametrize('failure',['owner','stale','mint','global-disc','sharing-disc','zero-recipient'])
def test_bad_state_rejected(failure):
    a=fixture();g=GLOBAL_ACCOUNT;s=get_fee_sharing_config_pda(MINT)
    if failure=='owner':a[g]=replace(a[g],owner=Pubkey.default())
    elif failure=='stale':a[g]=replace(a[g],slot=94)
    else:
        k=s if failure in ('mint','sharing-disc') else g;d=bytearray(a[k].data)
        if failure=='zero-recipient':d[41:73]=bytes(32)
        else:d[11 if failure=='mint' else 0]^=1
        a[k]=replace(a[k],data=bytes(d))
    with pytest.raises(ValueError):cached_pumpfun_configuration(AccountCacheSnapshot(a),MINT,CONTEXT)

def test_truncation_and_interruption():
    with pytest.raises(ValueError):decode_pumpfun_global_fee_recipient(bytes(72))
    with pytest.raises(ValueError):decode_pumpfun_sharing_creator_vault(bytes(42),MINT)
    def interrupted():raise ValueError('interrupted')
    with pytest.raises(ValueError,match='interrupted'):cached_pumpfun_configuration(AccountCacheSnapshot(fixture(),interrupted),MINT,CONTEXT)
