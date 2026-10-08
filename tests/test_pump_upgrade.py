import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from solders.instruction import AccountMeta
from src.instruction.pump_upgrade import build_pump_upgrade_instruction
from src.calc.pump_v3 import (
    PumpV3QuoteState,
    quote_pump_buy_v3_exact_in,
    quote_pump_buy_v3_exact_out,
)

ROOT = Path(__file__).parent / "fixtures/pump_upgrade"


def test_official_instruction_interfaces():
    for name, s in json.loads((ROOT / "instructions.json").read_text())[
        "instructions"
    ].items():
        accounts = {
            a["name"]: Pubkey.from_bytes(bytes([i + 1]) * 32)
            for i, a in enumerate(s["accounts"])
        }
        hops = (
            [
                AccountMeta(Pubkey.from_bytes(bytes([i + 70]) * 32), False, i >= 2)
                for i in range(5)
            ]
            if name == "pump_amm_multi_hop_swap"
            else []
        )
        ix = build_pump_upgrade_instruction(
            name,
            accounts,
            (7, 9) if s["args"] else (),
            True if s["partial_fill"] else None,
            hops,
        )
        assert str(ix.program_id) == s["program"]
        assert ix.data[:8] == bytes(s["discriminator"])
        assert [
            (a.pubkey, a.is_writable, a.is_signer)
            for a in ix.accounts[: len(s["accounts"])]
        ] == [
            (accounts[a["name"]], a.get("writable", False), a.get("signer", False))
            for a in s["accounts"]
        ]
        if s["args"]:
            assert ix.data[8:24] == (7).to_bytes(8, "little") + (9).to_bytes(
                8, "little"
            )
        if s["partial_fill"]:
            assert ix.data[24] == 1
        with pytest.raises(ValueError):
            build_pump_upgrade_instruction(
                name, {}, (7, 9) if s["args"] else (), remaining=hops
            )


def test_official_v3_quotes():
    for c in json.loads((ROOT / "quotes.json").read_text())["cases"]:
        s = PumpV3QuoteState(**{k: int(v) for k, v in c["state"].items()})
        q = (
            quote_pump_buy_v3_exact_out
            if c["mode"] == "out"
            else quote_pump_buy_v3_exact_in
        )(s, int(c["amount"]))
        assert (q.quote_in if c["mode"] == "out" else q.base_out) == int(c["expected"])
        if c["mode"] == "in":
            assert q.quote_in <= int(c["amount"])


def test_reject_invalid_state_and_arguments():
    with pytest.raises(ValueError):
        build_pump_upgrade_instruction("pump_buy_v3", {}, (True, 2))
    with pytest.raises(ValueError):
        build_pump_upgrade_instruction("pump_amm_multi_hop_swap", {}, (1, 0))
    s = PumpV3QuoteState(1000, 100, 100, 1, 200, complete=True)
    with pytest.raises(ValueError):
        quote_pump_buy_v3_exact_out(s, 1)
    s = PumpV3QuoteState(1000, 100, 100, 1, 200, mayhem=True)
    with pytest.raises(ValueError):
        quote_pump_buy_v3_exact_out(s, 101)


from src.instruction.pump_create_v2 import build_pump_create_v2_instruction
from src.instruction.pump_compact_accounts import (
    derive_pump_v3_accounts,
    derive_pump_multi_hop_accounts,
    PumpMultiHop,
    WSOL,
    derive_pump_coin_quote_create_accounts,
)


def test_official_anchor_create_encoding():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/pump_upgrade/create.json").read_text()
    )
    accounts = {
        a["name"]: Pubkey(bytes([i + 1]) * 32)
        for i, a in enumerate(fixture["accounts"])
    }
    ix = build_pump_create_v2_instruction(
        accounts,
        "测试",
        "Q",
        "https://example.com/q",
        Pubkey(bytes([9]) * 32),
        creator_fee_bps=25,
        holder_reward=True,
    )
    assert bytes(ix.data).hex() == fixture["data"]
    for m, a in zip(ix.accounts, fixture["accounts"]):
        assert (m.is_signer, m.is_writable) == (a["signer"], a["writable"])


def test_nested_curve_route_validation():
    user, a, b = [Pubkey(bytes([i]) * 32) for i in (1, 2, 3)]
    token = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

    def hop(base, quote):
        p = derive_pump_v3_accounts(user, base, quote, token, token, user)
        return PumpMultiHop(
            "curve",
            base,
            quote,
            p["bonding_curve"],
            p["associated_base_bonding_curve"],
            p["associated_quote_bonding_curve"],
            token,
            token,
        )

    hops = [hop(a, WSOL), hop(b, a)]
    assert len(derive_pump_coin_quote_create_accounts(b, hops[0], 0, 1)) == 5
    with pytest.raises(ValueError):
        derive_pump_coin_quote_create_accounts(b, hops[0], 1, 1)
    accounts, remaining = derive_pump_multi_hop_accounts(user, WSOL, b, user, hops)
    assert (
        len(accounts) == 16
        and len(remaining) == 10
        and accounts["buyback_fee_recipient"] != user
    )
    with pytest.raises(ValueError):
        derive_pump_multi_hop_accounts(user, WSOL, b, user, list(reversed(hops)))
    hops[1].cashback = True
    with pytest.raises(ValueError):
        derive_pump_multi_hop_accounts(user, WSOL, b, user, hops)


from src.instruction.pump_create_v2 import decode_pump_quote_control
from src.calc.pump_v3 import pump_coin_initial_quote_reserves


def test_official_quote_control_and_child_reserves():
    f = json.loads((ROOT / "quote_control.json").read_text())
    raw = bytes.fromhex(f["data"])
    c = decode_pump_quote_control(raw)
    assert (
        str(c["admin"]) == f["admin"] and str(c["reserves_admin"]) == f["reservesAdmin"]
    )
    assert (
        str(c["mints"][0]["mint"]) == f["mint"]
        and c["mints"][0]["initial_virtual_quote_reserves"] == 321
    )
    with pytest.raises(ValueError):
        decode_pump_quote_control(raw[:-1])
    assert (
        pump_coin_initial_quote_reserves(123, 1000, 10, 1000, 100, 2000, 0, 1) == 12300
    )
    with pytest.raises(ValueError):
        pump_coin_initial_quote_reserves(123, 1000, 10, 1000, 100, 100, 0, 1)


def test_builders_match_successful_mainnet_simulations():
    from pathlib import Path
    import json
    from solders.pubkey import Pubkey
    from src.instruction.pump_upgrade import build_pump_upgrade_instruction

    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures/pump_upgrade/simulated_instructions.json"
        ).read_text()
    )
    for c in fixture["cases"]:
        ix = build_pump_upgrade_instruction(
            c["name"],
            {k: Pubkey.from_string(v) for k, v in c["accounts"].items()},
            [int(n) for n in c["args"]],
        )
        assert str(ix.program_id) == c["program"]
        assert bytes(ix.data).hex() == c["data"]
        assert [
            {"pubkey": str(a.pubkey), "signer": a.is_signer, "writable": a.is_writable}
            for a in ix.accounts
        ] == c["metas"]
