"""Build a direct stock/meme V1 swap from saved subscription snapshots.

python examples/stonkfun_native_curve.py snapshots.json [--simulate]
JSON requires: payer, recent_blockhash, epoch, buy, amount, slippage_bps,
and pool/global/platform/base_mint/quote_mint objects {pubkey,owner,data(base64)}.
Simulation uses RPC_URL; construction and quoting perform no network calls.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    LaunchLabAccountBytes,
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
    compile_v1_message,
    V1Config,
)
from sol_trade_sdk.instruction.common import create_associated_token_account_idempotent_instruction


def build(snapshot):
    def account(name):
        value = snapshot[name]
        return LaunchLabAccountBytes(
            Pubkey.from_string(value["pubkey"]),
            Pubkey.from_string(value["owner"]),
            base64.b64decode(value["data"], validate=True),
        )

    cache = SubscriptionAccountCache()
    names = ("pool", "global", "platform", "base_mint", "quote_mint")
    for name in names:
        a, value = account(name), snapshot[name]
        cache.update(
            a.pubkey,
            CachedAccount(a.owner, a.data, int(value["slot"]), int(value["write_version"])),
        )
    # Replay defaults to the saved account slot. Live callers supply their Clock
    # slot and an explicit age budget, refreshed through the subscription.
    read_slot = int(snapshot.get("read_slot", max(int(snapshot[n]["slot"]) for n in names)))
    context = CacheReadContext(
        read_slot, int(snapshot["epoch"]), int(snapshot.get("maximum_slot_age", 32))
    )
    base, quote = account("base_mint"), account("quote_mint")
    payer = Pubkey.from_string(snapshot["payer"])
    buy = snapshot["buy"]
    if not isinstance(buy, bool):
        raise ValueError("buy must be boolean")
    hint = PoolTradeHint(
        account("pool").pubkey,
        quote.pubkey if buy else base.pubkey,
        base.pubkey if buy else quote.pubkey,
    )
    _, result, swap = cache.snapshot().prepare_stonkfun_curve(
        hint, context, payer, int(snapshot["amount"]), int(snapshot["slippage_bps"])
    )
    setup = [
        create_associated_token_account_idempotent_instruction(payer, payer, m.pubkey, m.owner)
        for m in (base, quote)
    ]
    compiled = compile_v1_message(
        payer,
        setup + [swap],
        snapshot["recent_blockhash"],
        V1Config(compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024),
    )
    # Zero signatures are only for sigVerify:false simulations. Nothing is submitted.
    raw = compiled.message + bytes(64 * compiled.required_signatures)
    return result, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", type=Path)
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    quote, raw = build(json.loads(args.snapshots.read_text()))
    print(
        json.dumps(
            {
                "amount_in": str(quote.amount_in),
                "minimum_amount_out": str(quote.minimum_amount_out),
                "version": 1,
                "wire_bytes": len(raw),
                "transaction": base64.b64encode(raw).decode(),
            }
        )
    )
    if args.simulate:
        response = requests.post(
            os.environ.get("RPC_URL", "https://api.mainnet-beta.solana.com"),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "simulateTransaction",
                "params": [
                    base64.b64encode(raw).decode(),
                    {
                        "encoding": "base64",
                        "sigVerify": False,
                        "replaceRecentBlockhash": True,
                        "commitment": "confirmed",
                    },
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        print(json.dumps(result, indent=2))
        if "error" in result or result["result"]["value"]["err"] is not None:
            raise SystemExit("Simulation failed; inspect the returned logs")


if __name__ == "__main__":
    main()
