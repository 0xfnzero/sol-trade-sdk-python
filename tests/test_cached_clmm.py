import base64, json, copy
from pathlib import Path
import pytest
from sol_trade_sdk.trading.subscription_cache import AccountCacheSnapshot
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
)

V = json.loads(
    (
        Path(__file__).parents[1] / "examples/fixtures/clmm_mainnet_20261002.json"
    ).read_text()
)


def prepare(v, reverse=False, age=0, amount=10000, budget=8):
    cache = SubscriptionAccountCache()
    for a in v["accounts"]:
        cache.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]),
                base64.b64decode(a["data"]),
                int(a["slot"]),
                int(a["write_version"]),
            ),
        )
    im, om = (
        (v["output_mint"], v["input_mint"])
        if reverse
        else (v["input_mint"], v["output_mint"])
    )
    h = PoolTradeHint(*(Pubkey.from_string(k) for k in (v["pool"], im, om)))
    ctx = CacheReadContext(int(v["read_slot"]) + age, int(v["epoch"]), 0)
    return cache.snapshot().prepare_clmm(
        h,
        ctx,
        int(v["unix_timestamp"]),
        Pubkey.from_string(v["payer"]),
        amount,
        100,
        budget,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_mainnet_replay(reverse):
    a, q, ix = prepare(V, reverse)
    assert (
        str(q.estimated_net_amount_out)
        == V["expected"]["usdc_to_stock" if reverse else "stock_to_usdc"]
    )
    assert q.minimum_amount_out == q.estimated_net_amount_out * 99 // 100
    assert ix.accounts[0].pubkey == Pubkey.from_string(V["payer"])
    assert a.input_vault_mint == Pubkey.from_string(
        V["output_mint"] if reverse else V["input_mint"]
    )
    assert len(a.tick_arrays) == 1


def test_empty_extended_bitmap_read_once(monkeypatch):
    v = json.loads((Path(__file__).parent / "fixtures/clmm_empty_bitmap_review_20261005.json").read_text())
    original = AccountCacheSnapshot.get
    reads = []
    def counted(snapshot, key, context, expected_owner=None):
        if str(key) == v["bitmap"]:
            reads.append(key)
        return original(snapshot, key, context, expected_owner)
    monkeypatch.setattr(AccountCacheSnapshot, "get", counted)
    with pytest.raises(ValueError, match="Insufficient CLMM liquidity"):
        prepare(v)
    assert len(reads) == 1


@pytest.mark.parametrize("kind,match", [("missing", "Missing cached"), ("stale", "stale"), ("owner", "owner"), ("identity", "bitmap extension")])
def test_extended_bitmap_validation_preserved(kind, match):
    v = json.loads((Path(__file__).parent / "fixtures/clmm_empty_bitmap_review_20261005.json").read_text())
    bitmap = next(a for a in v["accounts"] if a["pubkey"] == v["bitmap"])
    if kind == "missing":
        v["accounts"].remove(bitmap)
    elif kind == "stale":
        bitmap["slot"] = str(int(v["read_slot"]) - 1)
    elif kind == "owner":
        bitmap["owner"] = str(Pubkey.default())
    else:
        d = bytearray(base64.b64decode(bitmap["data"]))
        d[8] ^= 1
        bitmap["data"] = base64.b64encode(d).decode()
    with pytest.raises(ValueError, match=match):
        prepare(v)


@pytest.mark.parametrize(
    "kind",
    [
        "stale",
        "owner",
        "missing_array",
        "pool_identity",
        "tick_index",
        "closed",
        "budget",
    ],
)
def test_invalid_snapshot(kind):
    v = copy.deepcopy(V)
    age = 0
    budget = 8
    pool = next(a for a in v["accounts"] if a["pubkey"] == v["pool"])
    arrays = [a for a in v["accounts"] if len(base64.b64decode(a["data"])) == 10240]
    if kind == "stale":
        age = 1
    elif kind == "owner":
        pool["owner"] = "11111111111111111111111111111111"
    elif kind == "missing_array":
        v["accounts"] = [a for a in v["accounts"] if a not in arrays]
    elif kind == "closed":
        pool["data"] = ""
    elif kind == "budget":
        budget = 0
    else:
        for a in arrays:
            d = bytearray(base64.b64decode(a["data"]))
            if kind == "pool_identity":
                d[8:40] = bytes(32)
            else:
                for i in range(60):
                    o = 44 + i * 168
                    if any(d[o + 20 : o + 36]) or any(d[o + 124 : o + 140]):
                        d[o : o + 4] = (443636).to_bytes(4, "little", signed=True)
            a["data"] = base64.b64encode(d).decode()
    with pytest.raises(ValueError):
        prepare(v, age=age, budget=budget)
