"""Validated DAMM v2 state; explicit swap2 output thresholds are required by Rust."""
from dataclasses import dataclass
from ..instruction.meteora_damm_v2_builder import decode_meteora_pool,METEORA_DAMM_V2_PROGRAM_ID,AUTHORITY
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..instruction.common import TOKEN_PROGRAM,TOKEN_PROGRAM_2022
@dataclass(frozen=True)
class CachedDammV2State:
    pool: object
    pool_address: object
    token_a_program: object
    token_b_program: object
    transfer_fees: tuple
    reserves: tuple

def cached_damm_v2(snapshot,hint,context,unix_timestamp):
    if type(unix_timestamp) is not int or not 0<=unix_timestamp<2**64:raise ValueError('Invalid DAMM v2 timestamp')
    data=snapshot.get(hint.pool,context,METEORA_DAMM_V2_PROGRAM_ID).data
    if len(data)<1112 or data[:8]!=bytes([241,154,109,4,17,177,109,188]):raise ValueError('Invalid DAMM v2 pool discriminator or size')
    p=decode_meteora_pool(data[8:]);hint.matches(p.token_a_mint,p.token_b_mint)
    if p.pool_status!=0 or not p.liquidity or p.activation_type>1 or not 0<p.sqrt_min_price<=p.sqrt_price<=p.sqrt_max_price:raise ValueError('DAMM v2 pool is inactive or invalid')
    if (context.slot if p.activation_type==0 else unix_timestamp)<p.activation_point:raise ValueError('DAMM v2 pool is not activated')
    if p.token_a_vault==p.token_b_vault:raise ValueError('DAMM v2 vaults collide')
    keys=(p.token_a_mint,p.token_b_mint);mints=[snapshot.get(k,context) for k in keys];fees=[];reserves=[]
    for i,flag in enumerate((p.token_a_flag,p.token_b_flag)):
        if flag>1 or mints[i].owner!=(TOKEN_PROGRAM if flag==0 else TOKEN_PROGRAM_2022):raise ValueError('DAMM v2 mint program flag mismatch')
        fees.append(token_transfer_fee_for_epoch(mints[i].data,mints[i].owner,context.epoch))
        v=snapshot.get((p.token_a_vault,p.token_b_vault)[i],context,mints[i].owner).data
        if len(v)<165 or v[:32]!=bytes(keys[i]) or v[32:64]!=bytes(AUTHORITY) or v[108]!=1:raise ValueError('Invalid DAMM v2 vault identity or state')
        reserves.append(int.from_bytes(v[64:72],'little'))
    snapshot.assert_usable()
    return CachedDammV2State(p,hint.pool,mints[0].owner,mints[1].owner,tuple(fees),tuple(reserves))


def prepare_explicit_damm_v2_route(snapshot, hints, context, timestamp, payer, amount, minimum, direction="Buy"):
    """Rust exact-in swap2 with a caller threshold; no estimated credit is invented."""
    from solders.pubkey import Pubkey
    from .cached_route import CachedRouteLeg, PreparedCachedRoute
    from ..instruction.meteora_damm_v2_builder import MeteoraDammV2Params, build_buy_instructions, build_sell_instructions
    from ..instruction.common import create_associated_token_account_idempotent_instruction
    from ..instruction.stonkfun import unsigned
    unsigned(amount)
    if minimum is None:
        raise ValueError("DAMM v2 requires explicit fixed_output_amount; it is not a quote")
    unsigned(minimum)
    if not amount or not minimum or payer == Pubkey.default() or len(hints) != 1 or direction not in ("Buy", "Sell"):
        raise ValueError("Explicit DAMM v2 requires one independent positive exact-in swap")
    hint = hints[0]
    state = cached_damm_v2(snapshot, hint, context, timestamp)
    if any(f.basis_points and f.maximum_fee for f in state.transfer_fees):
        raise ValueError("DAMM v2 net transfer-fee thresholds are not yet verified")
    p = state.pool
    params = MeteoraDammV2Params(pool=hint.pool, token_a_mint=p.token_a_mint,
        token_b_mint=p.token_b_mint, token_a_vault=p.token_a_vault, token_b_vault=p.token_b_vault,
        token_a_program=state.token_a_program, token_b_program=state.token_b_program,
        swap_mode=0, include_rate_limiter_sysvar=p.pool_fees.base_fee.fee_scheduler_mode == 2)
    args=dict(payer=payer,input_mint=hint.input_mint,output_mint=hint.output_mint,
        input_amount=amount,params=params,fixed_output_amount=minimum,create_output_ata=False)
    swaps = build_buy_instructions(**args,create_input_ata=False) if direction == "Buy" else build_sell_instructions(**args)
    if len(swaps) != 1:
        raise ValueError("Unexpected DAMM v2 exact-in instruction count")
    setup = tuple(create_associated_token_account_idempotent_instruction(
        payer,payer,m,state.token_a_program if m == p.token_a_mint else state.token_b_program) for m in (hint.input_mint,hint.output_mint))
    snapshot.assert_usable()
    return PreparedCachedRoute((CachedRouteLeg(hint,amount,None,minimum,swaps[0]),),setup,tuple(swaps),minimum,())
