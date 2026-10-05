"""Offline independent stock/meme multi-hop route from gRPC snapshots. Usage: cached_route.py snapshots.json [--simulate].

Requires legs[{pool,input_mint,output_mint}],payer,amount,epoch,unix_timestamp,read_slot,
recent_blockhash, accounts[{pubkey,owner,data(base64),slot,write_version}].
No send path. RPC is used only for explicit simulation.
"""

import argparse, base64, json, os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
from sol_trade_sdk import settle_cached_route_with_native_sol
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
    compile_v1_message,
    V1Config,
)
from sol_trade_sdk.instruction.common import (
    create_associated_token_account_idempotent_instruction,
)


def build(v):
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
        for h in v["legs"]
    ]
    payer = Pubkey.from_string(v["payer"])
    route = snapshot.prepare_route(
        hints,
        ctx,
        int(v["unix_timestamp"]),
        payer,
        int(v["amount"]),
        v.get("slippage_bps", 100),
        v.get("maximum_arrays", 8),
    )
    instructions = list(route.setup_instructions + route.swap_instructions)
    for k in ("native_input", "native_output"):
        if k in v and not isinstance(v[k], bool):
            raise ValueError(k + " must be boolean")
    if v.get("native_input", False) or v.get("native_output", False):
        settled = settle_cached_route_with_native_sol(
            route,
            payer,
            v["temporary_wsol_seed"],
            int(v["rent_lamports"]),
            v.get("native_input", False),
            v.get("native_output", False),
        )
        instructions = list(settled.instructions)

    compiled = compile_v1_message(
        payer,
        instructions,
        v["recent_blockhash"],
        V1Config(compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024),
    )
    return route, compiled.message + bytes(64 * compiled.required_signatures)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshots", type=Path)
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args()
    route, raw = build(json.loads(args.snapshots.read_text()))
    print(
        json.dumps(
            dict(
                minimum_amount_out=str(route.minimum_net_amount_out),
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
            )
        )
    )
    if args.simulate:
        response = requests.post(
            os.environ.get("RPC_URL", "https://api.mainnet-beta.solana.com"),
            json=dict(
                jsonrpc="2.0",
                id=1,
                method="simulateTransaction",
                params=[
                    base64.b64encode(raw).decode(),
                    dict(encoding="base64", sigVerify=False, replaceRecentBlockhash=True),
                ],
            ),
            timeout=60,
        )
        response.raise_for_status()
        v = response.json()
        print(json.dumps(v))
        if "error" in v or v["result"]["value"]["err"] is not None:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
