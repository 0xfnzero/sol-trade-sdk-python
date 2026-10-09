"""Independent ABI checks for public compatibility modules, with real signing."""
import hashlib
import importlib
import pytest
from solders.hash import Hash
from solders.instruction import Instruction, AccountMeta
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction

TOKEN = Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')
WSOL = Pubkey.from_string('So11111111111111111111111111111111111111112')

def signed(ix, payer):
    native=Instruction(Pubkey.from_bytes(ix.program_id),ix.data,[AccountMeta(Pubkey.from_bytes(m.pubkey),m.is_signer,m.is_writable) for m in ix.accounts])
    wire=bytes(Transaction.new_signed_with_payer([native],payer.pubkey(),[payer],Hash.default()))
    tx=Transaction.from_bytes(wire)
    assert tx.verify_with_results()==[True]
    compiled=tx.message.instructions[0]
    assert compiled.data==ix.data
    assert tx.message.account_keys[compiled.program_id_index]==Pubkey.from_bytes(ix.program_id)
    assert [tx.message.account_keys[index] for index in compiled.accounts]==[Pubkey.from_bytes(m.pubkey) for m in ix.accounts]
    return wire

@pytest.mark.parametrize('side',['buy','sell'])
def test_public_bonk_exact_in_abi_and_real_pdas(side):
    m=importlib.import_module('sol_trade_sdk.instruction.bonk')
    program=Pubkey.from_string('LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj')
    assert m.BONK_PROGRAM==bytes(program)
    keys=[bytes([i])*32 for i in range(1,12)]
    pool,base,quote,bv,qv,platform,pa,ca,config,userbase,userquote=keys
    assert m.get_pool_pda(base,quote)==bytes(Pubkey.find_program_address([b'pool',base,quote],program)[0])
    assert m.get_platform_associated_account(platform)==bytes(Pubkey.find_program_address([platform,bytes(WSOL)],program)[0])
    assert m.get_creator_associated_account(ca)==bytes(Pubkey.find_program_address([ca,bytes(WSOL)],program)[0])
    payer=Keypair.from_seed(bytes(range(32)))
    ix=getattr(m.BonkInstructionBuilder,'build_'+side+'_instructions')(bytes(payer.pubkey()),*keys,100001,90000)[0]
    expected_disc=hashlib.sha256(('global:'+side+'_exact_in').encode()).digest()[:8]
    assert ix.data==expected_disc+(100001).to_bytes(8,'little')+(90000).to_bytes(8,'little')+bytes(8)
    authority=Pubkey.from_string('WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh')
    event=Pubkey.find_program_address([b'__event_authority'],program)[0]
    expected=[bytes(payer.pubkey()),bytes(authority),config,platform,pool,userbase,userquote,bv,qv,base,quote,bytes(TOKEN),bytes(TOKEN),bytes(event),bytes(program),bytes(32),pa,ca]
    assert [a.pubkey for a in ix.accounts]==expected
    assert [(a.is_signer,a.is_writable) for a in ix.accounts]==[(True,True),(False,False),(False,False),(False,False)]+[(False,True)]*5+[(False,False)]*7+[(False,True)]*2
    signed(ix,payer)

@pytest.mark.parametrize('side',['buy','sell'])
def test_public_amm_v4_legacy_abi(side):
    m=importlib.import_module('sol_trade_sdk.instruction.raydium_amm_v4')
    program=Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8')
    assert m.RAYDIUM_AMM_V4_PROGRAM==bytes(program)
    payer=Keypair.from_seed(bytes(range(32)))
    keys=[bytes([i])*32 for i in range(1,17)]
    ix=getattr(m.RaydiumAmmV4InstructionBuilder,'build_'+side+'_instructions')(bytes(payer.pubkey()),*keys,100001,90000)[0]
    assert ix.data==bytes([9])+(100001).to_bytes(8,'little')+(90000).to_bytes(8,'little')
    assert [a.pubkey for a in ix.accounts]==[bytes(TOKEN),*keys,bytes(payer.pubkey())]
    assert [(a.is_signer,a.is_writable) for a in ix.accounts]==[(False,False),(False,True),(False,False)]+[(False,True)]*4+[(False,False)]+[(False,True)]*6+[(False,False)]+[(False,True)]*2+[(True,False)]
    signed(ix,payer)

@pytest.mark.parametrize('amount,minimum',[(1,0),((1<<64)-1,(1<<64)-1)])
def test_public_amm_cached_distinct_payer_authority_and_missing_signers(amount,minimum):
    """Legacy eighteen-account ABI survives cached two-party real signing."""
    from unittest.mock import Mock,call
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    from src.hotpath.executor import TransactionBuilder
    from sol_trade_sdk.instruction.raydium_amm_v4 import RaydiumAmmV4InstructionBuilder
    payer=Keypair.from_seed(bytes([71])*32)
    authority=Keypair.from_seed(bytes([72])*32)
    keys=[bytes([i])*32 for i in range(1,17)]
    raw=RaydiumAmmV4InstructionBuilder.build_swap_instructions(bytes(payer.pubkey()),*keys,bytes(authority.pubkey()),amount,minimum)[0]
    ix=Instruction(Pubkey.from_bytes(raw.program_id),raw.data,[AccountMeta(Pubkey.from_bytes(m.pubkey),m.is_signer,m.is_writable) for m in raw.accounts])
    executor=Mock(spec=['get_blockhash'])
    executor.get_blockhash.return_value=(str(Hash.default()),100,True)
    builder=TransactionBuilder(executor)
    wire,error=builder.build_transaction(str(payer.pubkey()),[ix],[payer,authority])
    assert error is None
    tx=Transaction.from_bytes(wire)
    assert tx.verify_with_results()==[True,True]
    assert tx.message.header.num_required_signatures==2
    compiled=tx.message.instructions[0]
    assert compiled.data==bytes([9])+amount.to_bytes(8,'little')+minimum.to_bytes(8,'little')
    assert [tx.message.account_keys[i] for i in compiled.accounts]==[TOKEN,*[Pubkey.from_bytes(k) for k in keys],authority.pubkey()]
    message=bytes(tx.message)
    for index,signature in enumerate(tx.signatures):
        verifier=Ed25519PublicKey.from_public_bytes(bytes(tx.message.account_keys[index]))
        verifier.verify(bytes(signature),message)
        with pytest.raises(InvalidSignature):verifier.verify(bytes(signature),message[:-1]+bytes([message[-1]^1]))
    for signers in ([payer],[authority]):
        missing,error=builder.build_transaction(str(payer.pubkey()),[ix],signers)
        assert missing is None and error
    assert executor.mock_calls==[call.get_blockhash()]*3
