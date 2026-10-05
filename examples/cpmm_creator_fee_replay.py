"""Offline replay: uv run python examples/cpmm_creator_fee_replay.py. Never sends transactions."""

import base64, json
from pathlib import Path
from types import SimpleNamespace
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction import cpmm_creator_fee as f

for c in json.loads(
    (Path(__file__).parent / "fixtures/cpmm_creator_fee_rust_5_0_7.json").read_text()
):
    raw = lambda a: base64.b64decode(a["data_base64"])
    pool = f.decode_cpmm_collection_pool(raw(c["accounts"][0]))
    config = f.decode_cpmm_amm_config(raw(c["accounts"][1]))
    a = c["accounts"][2]
    rate = f.resolve_creator_fee_share_rate(
        config,
        pool.pool_creator,
        pool.amm_config,
        (
            None
            if a is None
            else SimpleNamespace(
                owner=Pubkey.from_string(a["owner"]), data=raw(a), lamports=a["lamports"]
            )
        ),
    )
    address = Pubkey.from_string(c["pool"])
    ix = (
        f.collect_creator_fee_permissionless(Pubkey.from_string(c["payer"]), address, pool)
        if c["permissionless"]
        else f.collect_creator_fee(address, pool)
    )
    assert [str(m.pubkey) for m in ix.accounts] == c["instruction"]["accounts"]
    assert bytes(ix.data) == base64.b64decode(c["instruction"]["data_base64"])
    print(
        c["name"],
        {
            "permissionless": c["permissionless"],
            "accounts": len(ix.accounts),
            "rate": rate,
            "payout": f.estimate_creator_fee_payout(pool, rate),
        },
    )
