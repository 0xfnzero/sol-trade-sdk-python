"""Historical identity catalog shared with Rust; not a live fee or liquidity quote."""

import json
from pathlib import Path

STOCK_DEX_PROGRAMS = {
    "raydium_clmm": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "raydium_cpmm": "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "orca_whirlpool": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "meteora_dlmm": "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
}
_PROTOCOL_DEX = dict(
    zip(
        ("RaydiumClmm", "RaydiumCpmm", "OrcaWhirlpool", "MeteoraDlmm"),
        STOCK_DEX_PROGRAMS,
    )
)


def screened_stock_catalog():
    """Return an owned, extensible catalog; defaults are explicitly opt-in."""
    return json.loads(Path(__file__).with_name("stock_token_catalog.json").read_text())


def preferred_stock_pool(catalog, mint):
    return next((pool for pool in catalog["pools"] if pool["mint"] == str(mint)), None)


def stock_conversion_legs(catalog, route):
    """Keep verified independent legs; do not infer a route or restrict by launch platform."""
    get = lambda obj, key: obj.get(key) if isinstance(obj, dict) else getattr(obj, key)
    if not get(route, "succeeded"):
        return []
    pools = {pool["pool"]: pool for pool in catalog["pools"]}
    result = []
    for leg in get(route, "legs"):
        pool = pools.get(str(get(leg, "pool")))
        protocol = get(leg, "protocol")
        dex = _PROTOCOL_DEX.get(getattr(protocol, "value", protocol))
        if (
            pool
            and dex == pool["dex_type"]
            and str(get(leg, "program")) == STOCK_DEX_PROGRAMS[dex]
            and {str(get(leg, "input_mint")), str(get(leg, "output_mint"))}
            == {pool["mint"], pool["quote_mint"]}
        ):
            result.append(leg)
    return result
