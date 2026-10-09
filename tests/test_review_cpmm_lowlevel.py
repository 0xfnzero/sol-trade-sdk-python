"""Public bytes API must emit the official CPMM ABI and a real signed wire."""
import hashlib
import importlib
from solders.hash import Hash
from solders.instruction import Instruction, AccountMeta
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction


def test_public_bytes_cpmm_builder_signed_wire_and_official_pdas():
    public = importlib.import_module('sol_trade_sdk.instruction.raydium_cpmm')
    program = Pubkey.from_string('CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C')
    payer = Keypair.from_seed(bytes(range(32)))
    config, pool, source, destination, in_vault, out_vault, in_program, out_program, in_mint, out_mint, observation = [Pubkey.from_bytes(bytes([n])*32) for n in range(1,12)]
    for name, seeds, args in [
        ('get_pool_pda', [b'pool', bytes(config), bytes(in_mint), bytes(out_mint)], [config,in_mint,out_mint]),
        ('get_observation_state_pda', [b'observation',bytes(pool)], [pool]),
        ('get_vault_account', [b'pool_vault',bytes(pool),bytes(in_mint)], [pool,in_mint]),
    ]:
        assert getattr(public,name)(*[bytes(k) for k in args]) == bytes(Pubkey.find_program_address(seeds,program)[0])
    for explicit in [None,bytes(observation)]:
        raw=public.RaydiumCpmmInstructionBuilder.build_swap_instructions(
            *[bytes(k) for k in [payer.pubkey(),config,pool,source,destination,in_vault,out_vault,in_program,out_program,in_mint,out_mint]],100_001,90_000,explicit)[0]
        assert raw.program_id==bytes(program)
        assert raw.data==hashlib.sha256(b'global:swap_base_input').digest()[:8]+(100_001).to_bytes(8,'little')+(90_000).to_bytes(8,'little')
        expected_observation=observation if explicit else Pubkey.find_program_address([b'observation',bytes(pool)],program)[0]
        authority=Pubkey.find_program_address([b'vault_and_lp_mint_auth_seed'],program)[0]
        expected=[payer.pubkey(),authority,config,pool,source,destination,in_vault,out_vault,in_program,out_program,in_mint,out_mint,expected_observation]
        assert [m.pubkey for m in raw.accounts]==[bytes(k) for k in expected]
        assert [(m.is_signer,m.is_writable) for m in raw.accounts]==[(True,True),(False,False),(False,False)]+[(False,True)]*5+[(False,False)]*4+[(False,True)]
        ix=Instruction(program,raw.data,[AccountMeta(Pubkey.from_bytes(m.pubkey),m.is_signer,m.is_writable) for m in raw.accounts])
        parsed=Transaction.from_bytes(bytes(Transaction.new_signed_with_payer([ix],payer.pubkey(),[payer],Hash.default())))
        assert parsed.verify_with_results()==[True]
        assert parsed.message.instructions[0].data==raw.data
        damaged=bytearray(bytes(parsed)); damaged[-1]^=1
        assert Transaction.from_bytes(bytes(damaged)).verify_with_results()==[False]
