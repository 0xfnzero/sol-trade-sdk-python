"""python examples/damm_v2_snapshot.py snapshot.json [--simulate].
Historical wire reconstruction: WSOL input uses the legacy SOL-funding helper.
For existing WSOL or temporary native SOL use cached_damm_v2.py.
Validated frozen DAMM v2 state -> explicit swap2 threshold -> unsigned V1.
No automatic quote or send. RPC only for explicit simulation.
"""
import argparse,json,base64,os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
from sol_trade_sdk import SubscriptionAccountCache,CachedAccount,CacheReadContext,PoolTradeHint
from sol_trade_sdk.instruction.meteora_damm_v2_builder import MeteoraDammV2Params,build_buy_instructions
from sol_trade_sdk.serialization.v1 import compile_v1_message,V1Config

def build(v):
    cache=SubscriptionAccountCache()
    for a in v['accounts']:cache.update(Pubkey.from_string(a['pubkey']),CachedAccount(Pubkey.from_string(a['owner']),base64.b64decode(a['data'],validate=True),int(a['slot']),int(a['write_version'])))
    if len(v['legs'])!=1:raise ValueError('One independent DAMM v2 swap required')
    h=PoolTradeHint(*(Pubkey.from_string(v['legs'][0][k]) for k in ('pool','input_mint','output_mint')))
    s=cache.snapshot().damm_v2(h,CacheReadContext(int(v['read_slot']),int(v['epoch']),int(v['maximum_slot_age'])),int(v['unix_timestamp']))
    p=s.pool
    if any(f.basis_points and f.maximum_fee for f in s.transfer_fees):raise ValueError('Explicit snapshot example does not verify nonzero transfer-fee thresholds')
    minimum=int(v['fixed_output_amount'])
    if not 0<minimum<2**64:raise ValueError('Explicit positive u64 minimum required')
    params=MeteoraDammV2Params(pool=h.pool,token_a_vault=p.token_a_vault,token_b_vault=p.token_b_vault,token_a_mint=p.token_a_mint,token_b_mint=p.token_b_mint,token_a_program=s.token_a_program,token_b_program=s.token_b_program,swap_mode=0,include_rate_limiter_sysvar=p.pool_fees.base_fee.fee_scheduler_mode==2)
    payer=Pubkey.from_string(v['payer'])
    ixs=build_buy_instructions(payer=payer,input_mint=h.input_mint,output_mint=h.output_mint,input_amount=int(v['amount']),params=params,fixed_output_amount=minimum,create_input_ata=True,create_output_ata=True)
    message=compile_v1_message(payer,ixs,v['recent_blockhash'],V1Config(compute_unit_limit=300000,loaded_accounts_data_size_limit=64*1024*1024))
    return message.message+bytes(64*message.required_signatures)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('snapshot',type=Path);ap.add_argument('--simulate',action='store_true');args=ap.parse_args()
    wire=build(json.loads(args.snapshot.read_text()));print(json.dumps(dict(transaction=base64.b64encode(wire).decode(),wire_bytes=len(wire))))
    if args.simulate:
        r=requests.post(os.environ.get('RPC_URL','https://api.mainnet-beta.solana.com'),json=dict(jsonrpc='2.0',id=1,method='simulateTransaction',params=[base64.b64encode(wire).decode(),dict(encoding='base64',sigVerify=False,replaceRecentBlockhash=True,innerInstructions=True,commitment='confirmed')]),timeout=60);r.raise_for_status();response=r.json();print(json.dumps(response))
        if 'error' in response or response['result']['value']['err'] is not None:raise SystemExit(1)
if __name__=='__main__':main()
