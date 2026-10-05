"""WSOL-sentinel PumpFun V2 still settles in wallet SOL; convert endpoints explicitly."""
from hashlib import sha256
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction,AccountMeta
from ..instruction.common import TOKEN_PROGRAM,WSOL_TOKEN_ACCOUNT,ASSOCIATED_TOKEN_PROGRAM,SYSTEM_PROGRAM,get_associated_token_address
from ..instruction.stonkfun import unsigned
from ..instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID
from dataclasses import replace

def _validate_settlement_instructions(route,payer):
    if len(route.swap_instructions)!=len(route.legs):
        raise ValueError('Invalid PumpFun settlement instructions')
    for leg,ix in zip(route.legs,route.swap_instructions):
        if ix!=getattr(leg,'instruction',None):
            raise ValueError('PumpFun settlement instruction differs from quoted leg')
        if not any(a.pubkey==payer and a.is_signer for a in ix.accounts):
            raise ValueError('PumpFun settlement belongs to a different wallet')
        unsigned(leg.amount_in);unsigned(leg.minimum_net_amount_out)
        if not leg.amount_in or not leg.minimum_net_amount_out:
            raise ValueError('Invalid PumpFun settlement amount or protection')
    if route.minimum_net_amount_out!=route.legs[-1].minimum_net_amount_out:
        raise ValueError('PumpFun settlement protection differs from quoted leg')

def _validate_native_anchor(leg,payer,buy):
    ix=leg.instruction;keys=ix.accounts
    discriminator=bytes.fromhex('c2ab1c46684d5b2f' if buy else '5df6823ce7e940b2')
    if (len(ix.data)!=24 or ix.data[:8]!=discriminator or len(keys)!=(27 if buy else 26)
        or struct.unpack_from('<QQ',ix.data,8)!=(leg.amount_in,leg.minimum_net_amount_out)
        or keys[13].pubkey!=payer or not keys[13].is_signer or not keys[13].is_writable
        or keys[10].pubkey!=leg.hint.pool or keys[2].pubkey!=WSOL_TOKEN_ACCOUNT
        or keys[1].pubkey!=(leg.hint.output_mint if buy else leg.hint.input_mint)):
        raise ValueError('PumpFun native settlement requires matching exact-in V2 quote and accounts')

def settle_pumpfun_native_quote(route,payer,native_input,native_output,seed,rent):
    if type(native_input) is not bool or type(native_output) is not bool:
        raise ValueError('Invalid PumpFun native endpoint flags')
    if len(route.legs)!=1:
        if not 2<=len(route.legs)<=5 or native_input or native_output:
            raise ValueError('Invalid PumpFun native-quote multi-hop endpoints')
        indices=[i for i,leg in enumerate(route.legs) if getattr(getattr(leg,'instruction',None),'program_id',None)==PUMPFUN_PROGRAM_ID]
        if len(indices)!=1 or indices[0] not in (0,len(route.legs)-1):
            raise ValueError('PumpFun multi-hop requires one curve at the buy or sell anchor')
        index=indices[0];anchor=route.legs[index]
        buy=index==len(route.legs)-1
        if (anchor.hint.input_mint if buy else anchor.hint.output_mint)!=WSOL_TOKEN_ACCOUNT:
            raise ValueError('PumpFun multi-hop anchor must use native quote')
        for previous,current in zip(route.legs,route.legs[1:]):
            if previous.hint.output_mint!=current.hint.input_mint or not 0<current.amount_in<=previous.minimum_net_amount_out:
                raise ValueError('PumpFun multi-hop exceeds protected intermediate credit')
        _validate_settlement_instructions(route,payer)
        one=replace(route,legs=(anchor,),setup_instructions=(),swap_instructions=(anchor.instruction,),minimum_net_amount_out=anchor.minimum_net_amount_out,estimated_intermediate_residuals=())
        converted,required,residual=settle_pumpfun_native_quote(one,payer,False,False,seed,rent)
        swaps=route.swap_instructions
        if buy:
            return route.setup_instructions+swaps[:-1]+converted,required,residual
        return route.setup_instructions+converted+swaps[1:],required,residual
    leg=route.legs[0];buy=leg.hint.input_mint==WSOL_TOKEN_ACCOUNT
    if (getattr(getattr(leg,'instruction',None),'program_id',None)!=PUMPFUN_PROGRAM_ID
        or (leg.hint.input_mint==WSOL_TOKEN_ACCOUNT)==(leg.hint.output_mint==WSOL_TOKEN_ACCOUNT)):
        raise ValueError('PumpFun settlement requires one native-quote curve')
    _validate_settlement_instructions(route,payer)
    _validate_native_anchor(leg,payer,buy)
    if (native_output if buy else native_input):raise ValueError('Invalid PumpFun native endpoint')
    ata=get_associated_token_address(payer,WSOL_TOKEN_ACCOUNT,TOKEN_PROGRAM)
    keep=tuple(ix for ix in route.setup_instructions if not (ix.program_id==ASSOCIATED_TOKEN_PROGRAM and len(ix.accounts)>1 and ix.accounts[1].pubkey==ata))
    swaps=route.swap_instructions
    if buy and native_input:return keep+swaps,leg.amount_in,0
    if not buy and native_output:return keep+swaps,0,0
    if not buy:
        minimum=route.minimum_net_amount_out
        if leg.estimated_net_amount_out is None or leg.estimated_net_amount_out<minimum:raise ValueError('Missing PumpFun output estimate')
        fund=Instruction(SYSTEM_PROGRAM,struct.pack('<IQ',2,minimum),[AccountMeta(payer,True,True),AccountMeta(ata,False,True)])
        sync=Instruction(TOKEN_PROGRAM,bytes([17]),[AccountMeta(ata,False,True)])
        return route.setup_instructions+swaps+(fund,sync),0,leg.estimated_net_amount_out-minimum
    unsigned(rent)
    if not isinstance(seed,str) or not 1<=len(seed.encode())<=32 or not rent:raise ValueError('WSOL PumpFun input requires unique seed and current account rent')
    encoded=seed.encode();temporary=Pubkey.from_bytes(sha256(bytes(payer)+encoded+bytes(TOKEN_PROGRAM)).digest())
    if temporary==ata:raise ValueError('Temporary WSOL account collides with input ATA')
    data=struct.pack('<I',3)+bytes(payer)+struct.pack('<Q',len(encoded))+encoded+struct.pack('<QQ',rent,165)+bytes(TOKEN_PROGRAM)
    create=Instruction(SYSTEM_PROGRAM,data,[AccountMeta(payer,True,True),AccountMeta(temporary,False,True)])
    init=Instruction(TOKEN_PROGRAM,bytes([18])+bytes(payer),[AccountMeta(temporary,False,True),AccountMeta(WSOL_TOKEN_ACCOUNT,False,False)])
    transfer=Instruction(TOKEN_PROGRAM,struct.pack('<BQ',3,leg.amount_in),[AccountMeta(ata,False,True),AccountMeta(temporary,False,True),AccountMeta(payer,True,False)])
    close=Instruction(TOKEN_PROGRAM,bytes([9]),[AccountMeta(temporary,False,True),AccountMeta(payer,False,True),AccountMeta(payer,True,False)])
    return (create,init,transfer,close)+keep+swaps,rent,0
