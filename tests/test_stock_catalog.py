import json
from copy import deepcopy
from pathlib import Path
import pytest
from sol_trade_sdk.stock_catalog import screened_stock_catalog, stock_conversion_legs

CASES = json.loads(
    (
        Path(__file__).parents[1] / "examples/fixtures/stock_conversion_routes.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_exact_conversion_identity(case):
    catalog = screened_stock_catalog()
    assert [l["pool"] for l in stock_conversion_legs(catalog, case["route"])] == case[
        "expected_pools"
    ]
    assert not stock_conversion_legs(catalog, dict(case["route"], succeeded=False))
    for field in ("program", "pool", "protocol", "input_mint", "output_mint"):
        route = deepcopy(case["route"])
        for leg in route["legs"]:
            leg[field] = "invalid"
        assert not stock_conversion_legs(catalog, route)


def test_catalog_is_owned():
    a, b = screened_stock_catalog(), screened_stock_catalog()
    assert a == b
    a["pools"].clear()
    assert b["pools"]
