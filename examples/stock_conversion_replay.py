"""Historical parser output; no RPC, signing or broadcasting."""

import argparse
import json
from pathlib import Path
from sol_trade_sdk.stock_catalog import screened_stock_catalog, stock_conversion_legs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures/stock_conversion_routes.json",
    )
    args = parser.parse_args()
    catalog = screened_stock_catalog()
    for case in json.loads(args.fixture.read_text())["cases"]:
        print(
            json.dumps(
                dict(
                    signature=case["signature"],
                    name=case["name"],
                    replay=True,
                    conversion_legs=stock_conversion_legs(catalog, case["route"]),
                )
            )
        )


if __name__ == "__main__":
    main()
