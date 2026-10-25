"""Official PumpSwap multi_hop_swap for Pump.fun curves and migrated pools.

python -m examples.pump_multi_hop --help
RPC is example bootstrap only; SDK derivation/build is entirely local.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import requests
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.system_program import transfer, TransferParams
from sol_trade_sdk.common.bonding_curve import decode_bonding_curve_account
from sol_trade_sdk.instruction.pumpswap_builder import decode_pool_account
from sol_trade_sdk.instruction.pump_compact_accounts import (
    PumpMultiHop,
)
from sol_trade_sdk.instruction.pump_route import PumpRouteOptions, PumpRouteExecution, select_pump_route
from sol_trade_sdk.instruction.common import (
    get_associated_token_address as ata,
    create_associated_token_account_idempotent_instruction as create_ata,
)
from sol_trade_sdk.serialization.v1 import compile_v1_message, V1Config
from ._simulation import validate_simulation_response

PUMP = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
AMM = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
WSOL = Pubkey.from_string("So11111111111111111111111111111111111111112")
TOKEN = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")


def pda(program, *seeds):
    return Pubkey.find_program_address(list(seeds), program)[0]


def curve_address(mint):
    return pda(PUMP, b"bonding-curve", bytes(mint))


def pool_address(base, quote):
    return pda(
        AMM,
        b"pool",
        bytes(2),
        bytes(pda(PUMP, b"pool-authority", bytes(base))),
        bytes(base),
        bytes(quote),
    )


def positive_u64(text):
    if not text.isascii() or not text.isdecimal() or not 0 < int(text) < 2**64:
        raise argparse.ArgumentTypeError("Expected positive raw u64")
    return int(text)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Path is always in buy order; sell reverses it. Venue selects the target only. Provide a fresh min-out quote. Build by default; --simulate uses an unsigned transaction and requires a funded user. No signing/broadcast. Pool sells leave WSOL; curve sells pay native SOL.",
    )
    parser.add_argument("--venue", choices=["pumpfun", "pumpswap"], required=True)
    parser.add_argument(
        "--path", required=True, help="SOL,INTERMEDIATE_MINT,TARGET_MINT (2 or 3 hops)"
    )
    parser.add_argument("--side", choices=["buy", "sell"], required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--amount", type=positive_u64, required=True)
    parser.add_argument("--min-out", type=positive_u64, required=True)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--report", type=Path, help="New file; refuses overwrite")
    args = parser.parse_args()
    path = [
        WSOL if s in ("SOL", "WSOL") else Pubkey.from_string(s)
        for s in args.path.split(",")
    ]
    if not 3 <= len(path) <= 4 or len(set(path)) != len(path):
        raise ValueError("Provide 2 or 3 hops without repeated mints")
    user = Pubkey.from_string(args.user)
    endpoint = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

    def rpc(method, params):
        response = requests.post(
            endpoint,
            json=dict(jsonrpc="2.0", id=1, method=method, params=params),
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("error") or "result" not in body:
            raise ValueError(f"{method} failed")
        return body["result"]

    global_config = pda(AMM, b"global_config")
    keys = (
        path
        + [
            k
            for quote, base in zip(path, path[1:])
            for k in (curve_address(base), pool_address(base, quote))
        ]
        + [global_config]
    )
    batch = rpc(
        "getMultipleAccounts",
        [[str(k) for k in keys], dict(encoding="base64", commitment="confirmed")],
    )
    if len(batch["value"]) != len(keys):
        raise ValueError("Incomplete RPC batch")
    accounts = {
        k: (
            None
            if a is None
            else (Pubkey.from_string(a["owner"]), base64.b64decode(a["data"][0]))
        )
        for k, a in zip(keys, batch["value"])
    }

    def get(key):
        a = accounts.get(key)
        if a is None:
            raise ValueError(f"Missing account {key}")
        return a

    programs = []
    for mint in path:
        owner, data = get(mint)
        if (
            owner not in (TOKEN, TOKEN2022)
            or len(data) < 82
            or data[45] != 1
            or int.from_bytes(data[:4], "little") > 1
            or int.from_bytes(data[46:50], "little") > 1
        ):
            raise ValueError(f"Invalid mint {mint}")
        programs.append(owner)
    owner, g = get(global_config)
    if (
        owner != AMM
        or len(g) < 899
        or g[:8] != bytes([149, 8, 156, 202, 160, 252, 176, 217])
    ):
        raise ValueError("Invalid GlobalConfig")
    recipient = next(
        (
            Pubkey.from_bytes(g[643 + i * 32 : 675 + i * 32])
            for i in range(8)
            if any(g[643 + i * 32 : 675 + i * 32])
        ),
        None,
    )
    if recipient is None:
        raise ValueError("No current buyback recipient")
    hops = []
    for i, (quote, base) in enumerate(zip(path, path[1:])):
        address = curve_address(base)
        account = accounts.get(address)
        curve = decode_bonding_curve_account(account[1]) if account else None
        if account and (account[0] != PUMP or curve is None):
            raise ValueError("Invalid curve account")
        common = dict(
            base_mint=base,
            quote_mint=quote,
            base_token_program=programs[i + 1],
            quote_token_program=programs[i],
        )
        if curve and not curve.complete:
            if Pubkey.from_bytes(curve.effective_quote_mint()) != quote:
                raise ValueError("Curve quote mismatch")
            hop = PumpMultiHop(
                **common,
                venue="curve",
                address=address,
                base_vault=ata(address, base, programs[i + 1]),
                quote_vault=ata(address, quote, programs[i]),
                mayhem=curve.is_mayhem_mode,
                cashback=curve.is_cashback_coin,
            )
        else:
            address = pool_address(base, quote)
            owner, data = get(address)
            pool = decode_pool_account(data)
            if (
                owner != AMM
                or pool is None
                or pool.base_mint != base
                or pool.quote_mint != quote
            ):
                raise ValueError("Invalid canonical pool")
            hop = PumpMultiHop(
                **common,
                venue="pool",
                address=address,
                base_vault=pool.pool_base_token_account,
                quote_vault=pool.pool_quote_token_account,
                mayhem=pool.is_mayhem_mode,
                cashback=pool.is_cashback_coin,
                complete=True,
                index=pool.index,
                creator=pool.creator,
            )
        hops.append(hop)
    currency, target = hops[0], hops[-1]
    if target.venue != ("curve" if args.venue == "pumpfun" else "pool"):
        raise ValueError("Target venue changed; refresh path/venue")
    sell = args.side == "sell"
    input_mint, output_mint = (
        (target.base_mint, currency.quote_mint)
        if sell
        else (currency.quote_mint, target.base_mint)
    )
    input_program, output_program = (
        (target.base_token_program, currency.quote_token_program)
        if sell
        else (currency.quote_token_program, target.base_token_program)
    )
    input_ata = ata(user, input_mint, input_program)
    instructions = [
        create_ata(user, user, input_mint, input_program),
        create_ata(user, user, output_mint, output_program),
        create_ata(user, recipient, currency.quote_mint, currency.quote_token_program),
    ]
    if not sell and input_mint == WSOL and currency.venue == "pool":
        instructions.extend(
            [
                transfer(
                    TransferParams(
                        from_pubkey=user,
                        to_pubkey=input_ata,
                        lamports=args.amount,
                    )
                ),
                Instruction(
                    TOKEN,
                    bytes([17]),
                    [AccountMeta(input_ata, False, True)],
                ),
            ]
        )
    instructions.append(
        select_pump_route(PumpRouteOptions(PumpRouteExecution.OFFICIAL, args.min_out, recipient),
            user, input_mint, output_mint, args.amount, list(reversed(hops)) if sell else hops)
    )
    block = rpc("getLatestBlockhash", [dict(commitment="confirmed")])["value"][
        "blockhash"
    ]
    compiled = compile_v1_message(
        user,
        instructions,
        block,
        V1Config(
            compute_unit_limit=400000, loaded_accounts_data_size_limit=64 * 1024 * 1024
        ),
    )
    wire = compiled.message + bytes(64 * compiled.required_signatures)
    if len(wire) > 4096:
        raise ValueError("V1 transaction too large")
    report = dict(
        signed=False,
        broadcast=False,
        snapshot_slot=batch["context"]["slot"],
        side=args.side,
        amount_in=str(args.amount),
        min_amount_out=str(args.min_out),
        message_version=1,
        route_in_buy_order=[
            dict(
                venue=h.venue,
                address=str(h.address),
                base_mint=str(h.base_mint),
                quote_mint=str(h.quote_mint),
            )
            for h in hops
        ],
        wire=base64.b64encode(wire).decode(),
        wire_bytes=len(wire),
    )
    failed = False
    if args.simulate:
        result = rpc(
            "simulateTransaction",
            [
                base64.b64encode(wire).decode(),
                dict(
                    encoding="base64",
                    sigVerify=False,
                    replaceRecentBlockhash=True,
                    innerInstructions=True,
                    commitment="confirmed",
                    minContextSlot=batch["context"]["slot"],
                ),
            ],
        )
        report["response"] = {"result": result}
        failed = validate_simulation_response(report["response"]) is not None
    if args.report:
        with args.report.open("x") as output:
            json.dump(report, output, indent=2)
    print(json.dumps(report))
    if failed:
        raise SystemExit("Simulation failed; inspect report logs")


if __name__ == "__main__":
    main()
