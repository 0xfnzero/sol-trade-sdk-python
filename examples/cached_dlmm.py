"""Offline Dlmm from gRPC snapshots. Usage: cached_dlmm.py snapshots.json [--simulate].

Requires pool,input_mint,output_mint,payer,amount,epoch,unix_timestamp,read_slot,
recent_blockhash, accounts[{pubkey,owner,data(base64),slot,write_version}].
No send path. RPC is used only for explicit simulation.
"""

import argparse, base64, json, os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
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
    hint = PoolTradeHint(*(Pubkey.from_string(v[k]) for k in ("pool", "input_mint", "output_mint")))
    payer = Pubkey.from_string(v["payer"])
    _, quote, swap = snapshot.prepare_dlmm(
        hint,
        ctx,
        int(v["unix_timestamp"]),
        payer,
        int(v["amount"]),
        v.get("slippage_bps", 100),
        v.get("maximum_arrays", 8),
    )
    setup = [
        create_associated_token_account_idempotent_instruction(
            payer, payer, m, snapshot.get(m, ctx).owner
        )
        for m in (hint.input_mint, hint.output_mint)
    ]
    compiled = compile_v1_message(
        payer,
        setup + [swap],
        v["recent_blockhash"],
        V1Config(compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024),
    )
    return quote, compiled.message + bytes(64 * compiled.required_signatures)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshots", type=Path)
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args()
    quote, raw = build(json.loads(args.snapshots.read_text()))
    print(
        json.dumps(
            dict(
                amount_in=str(quote.amount_in),
                amount_out=str(quote.estimated_net_amount_out),
                minimum_amount_out=str(quote.minimum_amount_out),
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
