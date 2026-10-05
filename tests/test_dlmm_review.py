import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.dlmm import DlmmPool, DlmmStaticFee, DlmmVariableFee, DlmmBin, dlmm_swap_exact_in, InsufficientDlmmArrays

VECTORS = json.loads((Path(__file__).parent / "fixtures/dlmm_review_reference_20261005.json").read_text())


@pytest.mark.parametrize("c", VECTORS, ids=lambda c: c["name"])
def test_sparse_walk_preserves_previous_native_result(c):
    pool = DlmmPool(c["active_id"], c["bin_step"], c["fee_mode"], DlmmStaticFee(**c["static"]), DlmmVariableFee(**{**c["variable"], "last_timestamp": int(c["variable"]["last_timestamp"])}))
    original = [DlmmBin(**{k: int(value) for k, value in b.items()}) for b in c["bins"]]
    for bins in (original, sorted(original, key=lambda b: b.bin_id), list(reversed(original))):
        before = repr((pool, bins, c["loaded_arrays"]))
        try:
            q = dlmm_swap_exact_in(pool, bins, c["loaded_arrays"], int(c["amount"]), int(c["timestamp"]), c["down"], c["orders"], c["strict"], c["exhaustive"])
            error = False
        except InsufficientDlmmArrays as e:
            q, error = e.partial, True
        assert dict(amount_out=str(q.amount_out), remaining_in=str(q.remaining_in), bins_crossed=q.bins_crossed, complete=q.complete, missing_bin_id=q.missing_bin_id, error=error) == c["expected"]
        assert repr((pool, bins, c["loaded_arrays"])) == before
