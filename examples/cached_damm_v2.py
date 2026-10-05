"""python examples/cached_damm_v2.py snapshot.json [--simulate].
Validated frozen DAMM v2 state -> explicit swap2 threshold -> unsigned V1.
Existing WSOL stays in its ATA; native_input/native_output use a temporary WSOL account.
No automatic quote or send. RPC only for explicit simulation.
"""
import argparse,json,base64
from pathlib import Path
from solders.pubkey import Pubkey
from sol_trade_sdk import SubscriptionAccountCache,CachedAccount,CacheReadContext,PoolTradeHint

def build(v):
    cache=SubscriptionAccountCache()
    for a in v['accounts']:cache.update(Pubkey.from_string(a['pubkey']),CachedAccount(Pubkey.from_string(a['owner']),base64.b64decode(a['data'],validate=True),int(a['slot']),int(a['write_version'])))
    if len(v['legs'])!=1:raise ValueError('One independent DAMM v2 swap required')
    h=PoolTradeHint(*(Pubkey.from_string(v['legs'][0][k]) for k in ('pool','input_mint','output_mint')))
    from sol_trade_sdk.trading.cached_trade import CachedTradeRequest,prepare_cached_trade
    prepared=prepare_cached_trade(CachedTradeRequest(
        dex_type="MeteoraDammV2",trade_type=v.get("trade_type","Buy"),snapshot=cache.snapshot(),hints=(h,),
        context=CacheReadContext(int(v['read_slot']),int(v['epoch']),int(v['maximum_slot_age'])),
        unix_timestamp=int(v['unix_timestamp']),payer=Pubkey.from_string(v['payer']),amount=int(v['amount']),
        recent_blockhash=v['recent_blockhash'],fixed_output_amount=int(v['fixed_output_amount']),
        native_input=v.get('native_input',False),native_output=v.get('native_output',False),
        temporary_wsol_seed=v.get('temporary_wsol_seed',''),rent_lamports=int(v.get('rent_lamports','0'))))
    message=prepared.compiled
    return message.message+bytes(64*message.required_signatures)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('snapshot',type=Path);ap.add_argument('--simulate',action='store_true');ap.add_argument('--simulation-out',type=Path);args=ap.parse_args()
    if args.simulation_out and not args.simulate:ap.error('--simulation-out requires --simulate')
    value=json.loads(args.snapshot.read_text());wire=build(value);print(json.dumps(dict(transaction=base64.b64encode(wire).decode(),wire_bytes=len(wire))))
    if args.simulate:
        from _simulation import simulate
        simulate(wire,int(value['read_slot']),args.simulation_out)
if __name__=='__main__':main()
