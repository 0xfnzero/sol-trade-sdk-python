"""Validated PumpSwap cache state. No RPC and no legacy fee fallback."""
from dataclasses import dataclass
from solders.pubkey import Pubkey
from ..instruction import pumpswap_builder as ix
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..calc import effective_quote_reserves, PumpSwapFeeBasisPoints

@dataclass(frozen=True)
class CachedPumpSwapState:
    pool_address: Pubkey
    pool: object
    base_reserve: int
    quote_reserve: int
    base_mint_supply: int
    base_token_program: Pubkey
    quote_token_program: Pubkey
    base_transfer_fee: object
    quote_transfer_fee: object
    fee_basis_points: PumpSwapFeeBasisPoints
    disable_flags: int
    protocol_fee_recipients: tuple
    reserved_fee_recipients: tuple
    buyback_fee_recipients: tuple
    mayhem_enabled: bool
    cashback_enabled: bool

def cached_pumpswap(snapshot,hint,context):
    d=snapshot.get(hint.pool,context,ix.PUMPSWAP_PROGRAM).data
    if len(d)<8 or d[:8]!=bytes([241,154,109,4,17,177,109,188]):
        raise ValueError('Invalid PumpSwap pool discriminator')
    pool=ix.decode_pool(d[8:])
    if pool is None or d[243]>1 or d[244]>1:
        raise ValueError('Invalid PumpSwap pool layout')
    hint.matches(pool.base_mint,pool.quote_mint)
    address,bump=Pubkey.find_program_address([b'pool',pool.index.to_bytes(2,'little'),bytes(pool.creator),bytes(pool.base_mint),bytes(pool.quote_mint)],ix.PUMPSWAP_PROGRAM)
    if address!=hint.pool or bump!=pool.pool_bump:
        raise ValueError('PumpSwap pool PDA mismatch')
    if pool.pool_base_token_account==pool.pool_quote_token_account:
        raise ValueError('PumpSwap vaults collide')
    global_data=snapshot.get(ix.PUMPSWAP_GLOBAL_ACCOUNT,context,ix.PUMPSWAP_PROGRAM).data
    if len(global_data)<899 or global_data[:8]!=bytes([149,8,156,202,160,252,176,217]) or global_data[417]>1 or global_data[642]>1:
        raise ValueError('Invalid PumpSwap global config')
    fee_data=snapshot.get(ix.FEE_CONFIG,context,ix.FEE_PROGRAM).data
    fee_address,fee_bump=Pubkey.find_program_address([b'fee_config',bytes(ix.PUMPSWAP_PROGRAM)],ix.FEE_PROGRAM)
    if fee_address!=ix.FEE_CONFIG or len(fee_data)<9 or fee_data[8]!=fee_bump:
        raise ValueError('PumpSwap fee config PDA bump mismatch')
    config=ix.decode_fee_config(fee_data)
    if config is None: raise ValueError('Invalid PumpSwap fee config')
    for tiers in (config.fee_tiers,config.stable_fee_tiers):
        if any(a.market_cap_lamports_threshold>=b.market_cap_lamports_threshold for a,b in zip(tiers,tiers[1:])):
            raise ValueError('PumpSwap fee tiers are not strictly ordered')
    mint_keys=(pool.base_mint,pool.quote_mint)
    mints=[snapshot.get(k,context) for k in mint_keys]
    transfer_fees=[token_transfer_fee_for_epoch(m.data,m.owner,context.epoch) for m in mints]
    reserves=[]
    for i,key in enumerate((pool.pool_base_token_account,pool.pool_quote_token_account)):
        v=snapshot.get(key,context,mints[i].owner).data
        if len(v)<165 or v[:32]!=bytes(mint_keys[i]) or v[32:64]!=bytes(hint.pool) or v[108]!=1:
            raise ValueError('Invalid PumpSwap vault identity or state')
        reserves.append(int.from_bytes(v[64:72],'little'))
    if not all(reserves): raise ValueError('PumpSwap reserves are empty')
    effective_quote_reserve=effective_quote_reserves(reserves[1],pool.virtual_quote_reserves)
    supply=int.from_bytes(mints[0].data[36:44],'little')
    fee=ix.compute_pumpswap_fee_basis_points(config,pool.creator,pool.base_mint,supply,reserves[0],effective_quote_reserve,pool.quote_mint)
    if len(global_data)>940 and global_data[940]==1 and pool.creator_fee_bps>0:fee.coin_creator_fee_basis_points=pool.creator_fee_bps
    keys=lambda start,n:tuple(Pubkey.from_bytes(global_data[start+i*32:start+(i+1)*32]) for i in range(n))
    snapshot.assert_usable()
    return CachedPumpSwapState(hint.pool,pool,*reserves,supply,*(m.owner for m in mints),*transfer_fees,
        PumpSwapFeeBasisPoints(fee.lp_fee_basis_points,fee.protocol_fee_basis_points,fee.coin_creator_fee_basis_points),global_data[56],keys(57,8),keys(385,1)+keys(418,7),keys(643,8),global_data[417]==1,global_data[642]==1)

@dataclass(frozen=True)
class PumpSwapQuote:
    amount_in: int
    amount_out: int
    minimum_amount_out: int


def prepare_cached_pumpswap(snapshot,hint,context,payer,amount,slippage_bps=0):
    from solders.instruction import Instruction, AccountMeta
    from ..calc import buy_quote_input_internal_with_fees,sell_base_input_internal_with_fees,calculate_with_slippage_sell,_u64
    _u64(amount,'amount')
    if not amount or type(slippage_bps) is not int or not 0<=slippage_bps<10000 or payer==Pubkey.default():
        raise ValueError('Invalid PumpSwap preparation request')
    state=cached_pumpswap(snapshot,hint,context);p=state.pool
    quote_in=hint.input_mint==p.quote_mint
    if state.disable_flags & (8 if quote_in else 16): raise ValueError('PumpSwap direction is disabled')
    if p.is_cashback_coin: raise ValueError('PumpSwap cashback quote requires a verified current fee context')
    for f in (state.base_transfer_fee,state.quote_transfer_fee):
        if f.basis_points and f.maximum_fee: raise ValueError('PumpSwap transfer-fee quote semantics are not yet verified')
    raw_fee=state.fee_basis_points
    fees=PumpSwapFeeBasisPoints(raw_fee.lp_fee_basis_points,raw_fee.protocol_fee_basis_points,raw_fee.coin_creator_fee_basis_points if p.coin_creator!=Pubkey.default() else 0)
    args=(amount,0,state.base_reserve,state.quote_reserve,p.virtual_quote_reserves,fees)
    out=buy_quote_input_internal_with_fees(*args).base if quote_in else sell_base_input_internal_with_fees(*args).ui_quote
    minimum=calculate_with_slippage_sell(out,slippage_bps)
    if not minimum: raise ValueError('PumpSwap quote has zero protected output')
    def choose(keys,label):
        for k in keys:
            if k!=Pubkey.default(): return k
        raise ValueError('Missing current PumpSwap '+label+' recipient')
    recipient=choose(state.reserved_fee_recipients if p.is_mayhem_mode else state.protocol_fee_recipients,'protocol')
    buyback=choose(state.buyback_fee_recipients,'buyback')
    w=lambda k:AccountMeta(k,False,True);r=lambda k:AccountMeta(k,False,False)
    ata=ix.get_associated_token_address
    accounts=[w(hint.pool),AccountMeta(payer,True,True),r(ix.PUMPSWAP_GLOBAL_ACCOUNT),r(p.base_mint),r(p.quote_mint),w(ata(payer,p.base_mint,state.base_token_program)),w(ata(payer,p.quote_mint,state.quote_token_program)),w(p.pool_base_token_account),w(p.pool_quote_token_account),r(recipient),w(ata(recipient,p.quote_mint,state.quote_token_program)),r(state.base_token_program),r(state.quote_token_program),r(ix.SYSTEM_PROGRAM),r(ix.ASSOCIATED_TOKEN_PROGRAM),r(ix.PUMPSWAP_EVENT_AUTHORITY),r(ix.PUMPSWAP_PROGRAM),w(ix.get_coin_creator_vault_ata(p.coin_creator,p.quote_mint,state.quote_token_program)),r(ix.get_coin_creator_vault_authority(p.coin_creator))]
    if quote_in: accounts.extend([w(ix.GLOBAL_VOLUME_ACCUMULATOR),w(ix.get_user_volume_accumulator_pda(payer))])
    accounts.extend([r(ix.FEE_CONFIG),r(ix.FEE_PROGRAM)])
    if p.coin_creator!=Pubkey.default(): accounts.append(r(ix.get_pool_v2_pda(p.base_mint)))
    accounts.extend([r(buyback),w(ata(buyback,p.quote_mint,state.quote_token_program))])
    disc=ix.BUY_EXACT_QUOTE_IN_DISCRIMINATOR if quote_in else ix.SELL_DISCRIMINATOR
    data=bytes(disc)+amount.to_bytes(8,'little')+minimum.to_bytes(8,'little')+(bytes(1) if quote_in else b'')
    instruction=Instruction(ix.PUMPSWAP_PROGRAM,data,accounts)
    snapshot.assert_usable()
    return state,PumpSwapQuote(amount,out,minimum),instruction
