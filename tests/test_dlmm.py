import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.dlmm import (
    DlmmPool,
    DlmmStaticFee,
    DlmmVariableFee,
    DlmmBin,
    dlmm_swap_exact_in,
    InsufficientDlmmArrays,
)

CASES = json.loads((Path(__file__).parent / "fixtures/dlmm_rust_5_0_6.json").read_text())


def args(c):
    v = {**c["variable"], "last_timestamp": int(c["variable"]["last_timestamp"])}
    return [
        DlmmPool(
            c["active_id"],
            c["bin_step"],
            c["fee_mode"],
            DlmmStaticFee(**c["static"]),
            DlmmVariableFee(**v),
        ),
        [DlmmBin(**{k: int(v) for k, v in b.items()}) for b in c["bins"]],
        c["loaded_arrays"],
        int(c["amount"]),
        int(c["timestamp"]),
        c["down"],
        c["orders"],
        True,
        c["exhaustive"],
    ]


@pytest.mark.parametrize("c", CASES, ids=[str(i) for i in range(len(CASES))])
def test_dlmm_rust(c):
    try:
        q = dlmm_swap_exact_in(*args(c))
        error = False
    except InsufficientDlmmArrays as e:
        q = e.partial
        error = True
    assert (
        dict(
            amount_out=str(q.amount_out),
            remaining_in=str(q.remaining_in),
            bins_crossed=q.bins_crossed,
            complete=q.complete,
            missing_bin_id=q.missing_bin_id,
            error=error,
        )
        == c["expected"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate_array",
        "unloaded",
        "negative_amount",
        "future_time",
        "zero_price",
        "duplicate_bin",
        "invalid_flag",
    ],
)
def test_invalid(kind):
    c = next(c for c in CASES if c["bins"])
    a = args(c)
    if kind == "duplicate_array":
        a[2] = a[2] + a[2][:1]
    if kind == "unloaded":
        a[2] = []
    if kind == "negative_amount":
        a[3] = -1
    if kind == "future_time":
        a[4] = 0
    if kind == "zero_price":
        a[1] = [DlmmBin(a[1][0].bin_id, 1, 0, 0)]
    if kind == "duplicate_bin":
        a[1] = a[1] + a[1][:1]
    if kind == "invalid_flag":
        a[5] = 1
    with pytest.raises(ValueError):
        dlmm_swap_exact_in(*a)
