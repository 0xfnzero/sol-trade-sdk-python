"""Single AMM legacy entry migrated to V2. Snapshot schema: ../docs/USAGE.md#amm-v4-cache.
Usage: PYTHONPATH=. python examples/legacy_amm_v2.py snapshot.json [--simulate] [--exact-output=N].
Buy wraps SOL into the payer WSOL ATA; sell receives WSOL. Existing ATAs are never closed.
Use cached_trade.py for temporary SOL accounts or multi-hop routes. No sends or hot-path RPC.
"""

import argparse, base64, json, os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    SubscriptionAccountCache,
    PoolTradeHint,
    CacheReadContext,
    RaydiumAmmV4Params,
)
from sol_trade_sdk.instruction.raydium_amm_v4_builder import (
    build_buy_instructions,
    build_sell_instructions,
)
from sol_trade_sdk.serialization.v1 import compile_v1_message, V1Config


def build(v, exact_output=None):
    if len(v["legs"]) != 1:
        raise ValueError("Single AMM pool required; use cached_trade for routes")
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
    h = v["legs"][0]
    hint = PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ("pool", "input_mint", "output_mint")))
    ctx = CacheReadContext(int(v["read_slot"]), int(v["epoch"]), int(v.get("maximum_slot_age", 32)))
    p = cache.snapshot().amm_v4(hint, ctx, int(v["unix_timestamp"]))
    params = RaydiumAmmV4Params(
        amm=p.pool,
        coin_mint=p.coin_mint,
        pc_mint=p.pc_mint,
        token_coin=p.coin_vault,
        token_pc=p.pc_vault,
        coin_reserve=p.coin_reserve,
        pc_reserve=p.pc_reserve,
        swap_fee_numerator=p.swap_fee_numerator,
        swap_fee_denominator=p.swap_fee_denominator,
    )
    common = dict(
        payer=Pubkey.from_string(v["payer"]),
        input_amount=int(v["amount"]),
        slippage_bps=v.get("slippage_bps", 100),
        params=params,
        fixed_output_amount=exact_output,
    )
    if v["trade_type"] == "Buy":
        ixs = build_buy_instructions(
            **common,
            input_mint=hint.input_mint,
            output_mint=hint.output_mint,
            create_input_ata=v.get("native_input", False),
        )
    elif v["trade_type"] == "Sell":
        ixs = build_sell_instructions(
            **common, input_mint=hint.input_mint, output_mint=hint.output_mint
        )
    else:
        raise ValueError("Explicit Buy/Sell required")
    c = compile_v1_message(
        common["payer"],
        ixs,
        v["recent_blockhash"],
        V1Config(compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024),
    )
    return c.message + bytes(64 * c.required_signatures)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--exact-output", type=int)
    args = ap.parse_args()
    raw = build(json.loads(args.snapshot.read_text()), args.exact_output)
    encoded = base64.b64encode(raw).decode()
    print(json.dumps(dict(wire_bytes=len(raw), transaction=encoded)))
    if args.simulate:
        response = requests.post(
            os.environ.get("RPC_URL", "https://api.mainnet-beta.solana.com"),
            json=dict(
                jsonrpc="2.0",
                id=1,
                method="simulateTransaction",
                params=[
                    encoded,
                    dict(encoding="base64", sigVerify=False, replaceRecentBlockhash=True),
                ],
            ),
            timeout=60,
        )
        response.raise_for_status()
        value = response.json()
        print(json.dumps(value))
        if "error" in value or value["result"]["value"]["err"] is not None:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
