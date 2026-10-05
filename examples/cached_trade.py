"""Offline independent stock/meme multi-hop route from gRPC snapshots. Usage: cached_trade.py snapshots.json [--simulate].

Requires legs[{pool,input_mint,output_mint}],payer,amount,epoch,unix_timestamp,read_slot,
recent_blockhash, accounts[{pubkey,owner,data(base64),slot,write_version}].
No send path. RPC is used only for explicit simulation.
"""

import argparse, base64, json
from pathlib import Path
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
)


def prepare(v):
    cache = SubscriptionAccountCache()
    for a in v["accounts"]:
        cache.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]),
                base64.b64decode(a["data"], validate=True),
                int(a["slot"]),
                int(a["write_version"]),
            ),
        )
    snapshot = cache.snapshot()
    ctx = CacheReadContext(int(v["read_slot"]), int(v["epoch"]), int(v.get("maximum_slot_age", 32)))
    hints = [
        PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ("pool", "input_mint", "output_mint")))
        for h in v.get("legs", [])
    ]
    payer = Pubkey.from_string(v["payer"])
    from sol_trade_sdk import CachedTradeRequest
    from sol_trade_sdk.trading.factory import TradeExecutorFactory

    request = CachedTradeRequest(
        dex_type=v["dex_type"],
        trade_type=v["trade_type"],
        snapshot=snapshot,
        hints=tuple(hints),
        candidates=tuple(PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ("pool","input_mint","output_mint"))) for h in v.get("candidates",[])),
        input_mint=Pubkey.from_string(v["input_mint"]) if v.get("input_mint") else None,
        output_mint=Pubkey.from_string(v["output_mint"]) if v.get("output_mint") else None,
        context=ctx,
        unix_timestamp=int(v["unix_timestamp"]),
        payer=payer,
        amount=int(v["amount"]),
        fixed_output_amount=None if "fixed_output_amount" not in v else int(v["fixed_output_amount"]),
        recent_blockhash=v["recent_blockhash"],
        slippage_bps=v.get("slippage_bps", 100),
        maximum_arrays=v.get("maximum_arrays", 8),
        native_input=v.get("native_input", False),
        native_output=v.get("native_output", False),
        temporary_wsol_seed=v.get("temporary_wsol_seed", ""),
        rent_lamports=int(v.get("rent_lamports", 0)),
        tip_account=Pubkey.from_string(v["tip_account"]) if v.get("tip_account") else None,
        tip_lamports=int(v.get("tip_lamports", 0)),
    )
    return TradeExecutorFactory.create_cached_executor(request.dex_type).prepare(request)


def build(v):
    prepared = prepare(v)
    route, compiled = prepared.route, prepared.compiled
    return route, compiled.message + bytes(64 * compiled.required_signatures)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshots", type=Path)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--simulation-out", type=Path, help="Save original wire and RPC response for parser")
    args = ap.parse_args()
    if args.simulation_out and not args.simulate:
        ap.error("--simulation-out requires --simulate")
    value = json.loads(args.snapshots.read_text())
    prepared = prepare(value)
    route = prepared.route
    raw = prepared.compiled.message + bytes(64 * prepared.compiled.required_signatures)
    print(
        json.dumps(
            dict(
                minimum_amount_out=str(route.minimum_net_amount_out),
                estimated_native_residual_lamports=str(prepared.estimated_native_residual_lamports),
                legs=[
                    dict(
                        amount_in=str(l.amount_in),
                        amount_out=None if l.estimated_net_amount_out is None else str(l.estimated_net_amount_out),
                        minimum_amount_out=str(l.minimum_net_amount_out),
                    )
                    for l in route.legs
                ],
                intermediate_residuals=[
                    dict(mint=str(m), amount=str(a))
                    for m, a in route.estimated_intermediate_residuals
                ],
                wire_bytes=len(raw),
                transaction=base64.b64encode(raw).decode(),
            )
        )
    )
    if args.simulate:
        from _simulation import simulate
        simulate(raw, int(value['read_slot']), args.simulation_out)


if __name__ == "__main__":
    main()
