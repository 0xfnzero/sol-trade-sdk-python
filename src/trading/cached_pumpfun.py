"""Current fee-program schedule and exact-in quote; frozen state, no RPC."""
from dataclasses import dataclass
from solders.pubkey import Pubkey
from ..common.bonding_curve import decode_bonding_curve_account
from ..instruction.pumpfun_builder import PUMPFUN_PROGRAM_ID, FEE_PROGRAM, FEE_CONFIG, GLOBAL_ACCOUNT, get_bonding_curve_pda
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..instruction.stonkfun import unsigned

WSOL=Pubkey.from_string('So11111111111111111111111111111111111111112')
USDC=Pubkey.from_string('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')
NATIVE2022=Pubkey.from_string('9pan9bMn5HatX4EJdBwg9VgCa7Uz5HL8N1m5D3NdXejP')

@dataclass(frozen=True)
class PumpFunCurrentFees:
    protocol_fee_bps: int
    creator_fee_bps: int

def decode_pumpfun_current_fees(data: bytes, quote: Pubkey, market_cap: int, creator_override=0):
    if len(data)<69 or data[:8]!=bytes([143,52,146,187,219,123,76,155]) or type(market_cap) is not int or not 0<=market_cap<1<<128:
        raise ValueError('Invalid PumpFun FeeConfig or market cap')
    unsigned(creator_override)
    offset=41
    def read_fees():
        nonlocal offset
        if offset+24>len(data):raise ValueError('Truncated PumpFun fees')
        fees=tuple(int.from_bytes(data[offset+i:offset+i+8],'little') for i in (0,8,16));offset+=24
        if any(f>10000 for f in fees):raise ValueError('Invalid PumpFun fee rate')
        return fees
    flat=read_fees()
    def read_tiers():
        nonlocal offset
        if offset+4>len(data):raise ValueError('Truncated PumpFun tier count')
        n=int.from_bytes(data[offset:offset+4],'little');offset+=4
        if n>(len(data)-offset)//40:raise ValueError('Truncated PumpFun fee tiers')
        tiers=[]
        for _ in range(n):
            threshold=int.from_bytes(data[offset:offset+16],'little');offset+=16
            if tiers and threshold<=tiers[-1][0]:raise ValueError('PumpFun fee tiers are not strictly ordered')
            tiers.append((threshold,read_fees()))
        return tiers
    tiers=read_tiers();stable=[] if offset==len(data) else read_tiers();exotic=(0,0,0) if offset==len(data) else read_fees()
    native=quote in (Pubkey.default(),WSOL,NATIVE2022)
    if native or quote==USDC:
        schedule=stable if not native and stable else tiers
        if not schedule:raise ValueError('PumpFun fee tiers cannot be empty')
        selected=schedule[0][1]
        for threshold,fees in schedule:
            if market_cap>=threshold:selected=fees
            else:break
    else:selected=exotic if any(exotic) else flat
    protocol=selected[1];creator=creator_override or selected[2]
    if protocol+creator>10000:raise ValueError('PumpFun combined fees exceed 100%')
    return PumpFunCurrentFees(protocol,creator)

@dataclass(frozen=True)
class CachedPumpFunState:
    curve: object
    mint: Pubkey
    quote: Pubkey
    buy_fees: PumpFunCurrentFees
    sell_fees: PumpFunCurrentFees
    token_program: Pubkey
    quote_token_program: Pubkey

def cached_pumpfun(snapshot,hint,context):
    raw=snapshot.get(hint.pool,context,PUMPFUN_PROGRAM_ID).data
    curve=decode_bonding_curve_account(raw)
    if curve is None:raise ValueError('Invalid PumpFun curve')
    quote=Pubkey.from_bytes(curve.quote_mint);quote=WSOL if quote==Pubkey.default() else quote
    mint=hint.output_mint if hint.input_mint==quote else hint.input_mint
    hint.matches(mint,quote)
    if get_bonding_curve_pda(mint)!=hint.pool or curve.complete or not curve.virtual_token_reserves or not curve.virtual_sol_reserves:
        raise ValueError('Invalid, completed or mismatched PumpFun curve')
    global_data=snapshot.get(GLOBAL_ACCOUNT,context,PUMPFUN_PROGRAM_ID).data
    if len(global_data)<1045 or global_data[:8]!=bytes([167,232,232,177,200,108,114,127]) or global_data[8]>1:
        raise ValueError('Invalid PumpFun Global')
    if 1045<len(global_data)<1054 or 115<len(raw)<123:raise ValueError('Truncated PumpFun configurable fee fields')
    if len(global_data)>=1054 and global_data[1045]>1:raise ValueError('Invalid PumpFun creator fee gate')
    override=int.from_bytes(raw[115:123],'little') if len(global_data)>=1054 and global_data[1045]==1 and len(raw)>=123 else 0
    if override and override>int.from_bytes(global_data[1046:1054],'little'):raise ValueError('PumpFun creator fee exceeds Global maximum')
    data=snapshot.get(FEE_CONFIG,context,FEE_PROGRAM).data
    address,bump=Pubkey.find_program_address([b'fee_config',bytes(PUMPFUN_PROGRAM_ID)],FEE_PROGRAM)
    if address!=FEE_CONFIG or len(data)<9 or data[8]!=bump:raise ValueError('PumpFun FeeConfig PDA bump mismatch')
    mints=[snapshot.get(k,context) for k in (mint,quote)]
    fees=[token_transfer_fee_for_epoch(m.data,m.owner,context.epoch) for m in mints]
    if any(f.basis_points and f.maximum_fee for f in fees):raise ValueError('PumpFun nonzero transfer-fee quotes are not yet verified')
    supply=int.from_bytes(mints[0].data[36:44],'little')
    if not supply:raise ValueError('PumpFun mint supply is zero')
    cap=lambda s:s*curve.virtual_sol_reserves//curve.virtual_token_reserves
    buy=decode_pumpfun_current_fees(data,quote,cap(supply),override)
    sell=decode_pumpfun_current_fees(data,quote,cap(supply if curve.is_mayhem_mode else 1_000_000_000_000_000),override)
    snapshot.assert_usable()
    return CachedPumpFunState(curve,mint,quote,buy,sell,mints[0].owner,mints[1].owner)

@dataclass(frozen=True)
class CachedPumpFunQuote:
    amount_in: int
    estimated_net_amount_out: int
    minimum_net_amount_out: int
    fees: PumpFunCurrentFees

def quote_cached_pumpfun_exact_in(state,amount,buy,slippage_bps=0):
    unsigned(amount)
    if not amount or type(buy) is not bool or type(slippage_bps) is not int or not 0<=slippage_bps<=9999:raise ValueError('Invalid PumpFun exact-in request')
    c=state.curve;f=state.buy_fees if buy else state.sell_fees;creator=0 if c.creator==bytes(32) else f.creator_fee_bps
    for value in (c.virtual_token_reserves,c.virtual_sol_reserves,c.real_token_reserves,f.protocol_fee_bps,f.creator_fee_bps):unsigned(value)
    if c.complete or not c.virtual_token_reserves or not c.virtual_sol_reserves or f.protocol_fee_bps+f.creator_fee_bps>10000:raise ValueError('Invalid PumpFun quote state')
    if buy:
        net=(amount-1)*10000//(10000+f.protocol_fee_bps+creator)
        estimated=min(net*c.virtual_token_reserves//(c.virtual_sol_reserves+net),c.real_token_reserves)
    else:
        gross=amount*c.virtual_sol_reserves//(c.virtual_token_reserves+amount)
        estimated=gross-(gross*f.protocol_fee_bps+9999)//10000-(gross*creator+9999)//10000
    minimum=estimated*(10000-slippage_bps)//10000
    if estimated<=0 or minimum<=0:raise ValueError('PumpFun quote has zero protected output')
    unsigned(estimated)
    return CachedPumpFunQuote(amount,estimated,minimum,f)

def prepare_cached_pumpfun(snapshot,hint,context,payer,amount,slippage_bps=0):
    return _prepare_cached_pumpfun_route_leg(snapshot,hint,context,payer,amount,slippage_bps,True)

def _prepare_cached_pumpfun_route_leg(snapshot,hint,context,payer,amount,slippage_bps,allow_native):
    import struct
    from solders.instruction import Instruction,AccountMeta
    from ..instruction import pumpfun_builder as ix
    from ..instruction.common import get_associated_token_address
    from .cached_pumpfun_config import decode_pumpfun_sharing_creator_vault
    token=Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')
    token2022=Pubkey.from_string('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb')
    if payer==Pubkey.default():raise ValueError('Missing PumpFun payer')
    s=cached_pumpfun(snapshot,hint,context)
    if s.quote==WSOL and not allow_native:raise ValueError('PumpFun native quote requires cached trade settlement')
    buy=hint.input_mint==s.quote;q=quote_cached_pumpfun_exact_in(s,amount,buy,slippage_bps)
    if s.quote_token_program!=token:raise ValueError('PumpFun V2 quote token program is unsupported')
    if str(s.mint).endswith('pump') and s.token_program!=token2022:raise ValueError('PumpFun mint suffix and token program mismatch')
    raw=snapshot.get(hint.pool,context,PUMPFUN_PROGRAM_ID).data
    if len(raw)>=125 and raw[124]!=0:
        holder=Pubkey.find_program_address([b'holder-rewards',bytes(s.mint)],PUMPFUN_PROGRAM_ID)[0]
        if raw[124]!=1 or bytes(holder)!=s.curve.creator:raise ValueError('Invalid PumpFun holder-reward creator')
    config=ix.get_fee_sharing_config_pda(s.mint);sharing=snapshot.get_optional(config,context,FEE_PROGRAM)
    active=decode_pumpfun_sharing_creator_vault(sharing.data,s.mint) if sharing else None
    creator=Pubkey.from_bytes(s.curve.creator);vault=active or ix.get_creator_vault_pda(creator)
    g=snapshot.get(GLOBAL_ACCOUNT,context,PUMPFUN_PROGRAM_ID).data
    def first(start,n):
        for i in range(n):
            key=Pubkey.from_bytes(g[start+i*32:start+(i+1)*32])
            if key!=Pubkey.default():return key
        raise ValueError('Missing PumpFun current fee recipient')
    recipient=first(483 if s.curve.is_mayhem_mode else 41,1);buyback=first(741,8)
    p=ix.PumpFunParams(bonding_curve_account=hint.pool,virtual_token_reserves=s.curve.virtual_token_reserves,virtual_sol_reserves=s.curve.virtual_sol_reserves,real_token_reserves=s.curve.real_token_reserves,creator=creator,is_mayhem_mode=s.curve.is_mayhem_mode,is_cashback_coin=s.curve.is_cashback_coin,creator_vault=vault,fee_sharing_creator_vault_if_active=active,token_program=s.token_program,fee_recipient=recipient,quote_mint=s.quote,curve_quote_mint=s.quote)
    swaps=ix.build_buy_v2_instructions(payer,s.mint,s.quote,amount,p,create_output_ata=False,create_input_ata=False,use_exact_sol_amount=True) if buy else ix.build_sell_v2_instructions(payer,s.mint,s.quote,amount,p,create_output_ata=False,fixed_output_amount=q.minimum_net_amount_out)
    if len(swaps)!=1 or len(swaps[0].accounts)!=(27 if buy else 26):raise ValueError('Unexpected PumpFun V2 layout')
    swap=swaps[0];keys=list(swap.accounts)
    for index,key in [(6,recipient),(7,get_associated_token_address(recipient,s.quote,token)),(8,buyback),(9,get_associated_token_address(buyback,s.quote,token))]:
        meta=keys[index];keys[index]=AccountMeta(key,meta.is_signer,True if index==8 else meta.is_writable)
    data=bytearray(swap.data);struct.pack_into('<2Q',data,8,amount,q.minimum_net_amount_out)
    snapshot.assert_usable()
    return s,q,Instruction(PUMPFUN_PROGRAM_ID,bytes(data),keys)
