"""Compact Pump trades and fee sweeps; official IDL commit 8cda1fa."""

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

_SPECS = {
    "pump_buy_v3": {
        "program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator": [7, 5, 29, 196, 245, 23, 101, 80],
        "accounts": [
            {"name": "global"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "bonding_curve", "writable": True},
            {"name": "associated_base_bonding_curve", "writable": True},
            {"name": "associated_quote_bonding_curve", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "associated_base_user", "writable": True},
            {"name": "associated_quote_user", "writable": True},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "system_program"},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": True,
    },
    "pump_buy_exact_quote_in_v3": {
        "program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator": [225, 247, 80, 30, 213, 179, 132, 136],
        "accounts": [
            {"name": "global"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "bonding_curve", "writable": True},
            {"name": "associated_base_bonding_curve", "writable": True},
            {"name": "associated_quote_bonding_curve", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "associated_base_user", "writable": True},
            {"name": "associated_quote_user", "writable": True},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "system_program"},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": True,
    },
    "pump_sell_v3": {
        "program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator": [28, 146, 222, 119, 38, 196, 105, 213],
        "accounts": [
            {"name": "global"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "bonding_curve", "writable": True},
            {"name": "associated_base_bonding_curve", "writable": True},
            {"name": "associated_quote_bonding_curve", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "associated_base_user", "writable": True},
            {"name": "associated_quote_user", "writable": True},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "system_program"},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": False,
    },
    "pump_sweep_creator_fee": {
        "program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator": [32, 246, 191, 52, 8, 201, 73, 186],
        "accounts": [
            {"name": "payer", "writable": True, "signer": True},
            {"name": "global"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "quote_token_program"},
            {"name": "associated_token_program"},
            {"name": "system_program"},
            {"name": "bonding_curve", "writable": True},
            {"name": "associated_quote_bonding_curve", "writable": True},
            {"name": "recipient", "writable": True},
            {"name": "associated_quote_recipient", "writable": True},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 0,
        "partial_fill": False,
    },
    "pump_sweep_protocol_fee": {
        "program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator": [8, 48, 190, 7, 182, 68, 183, 229],
        "accounts": [
            {"name": "payer", "writable": True, "signer": True},
            {"name": "global"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "quote_token_program"},
            {"name": "associated_token_program"},
            {"name": "system_program"},
            {"name": "bonding_curve", "writable": True},
            {"name": "associated_quote_bonding_curve", "writable": True},
            {"name": "recipient", "writable": True},
            {"name": "associated_quote_recipient", "writable": True},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 0,
        "partial_fill": False,
    },
    "pump_amm_buy_v2": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [184, 23, 238, 97, 103, 197, 211, 61],
        "accounts": [
            {"name": "pool", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "global_config"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "user_base_token_account", "writable": True},
            {"name": "user_quote_token_account", "writable": True},
            {"name": "pool_base_token_account", "writable": True},
            {"name": "pool_quote_token_account", "writable": True},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "system_program"},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": False,
    },
    "pump_amm_buy_exact_quote_in_v2": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [194, 171, 28, 70, 104, 77, 91, 47],
        "accounts": [
            {"name": "pool", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "global_config"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "user_base_token_account", "writable": True},
            {"name": "user_quote_token_account", "writable": True},
            {"name": "pool_base_token_account", "writable": True},
            {"name": "pool_quote_token_account", "writable": True},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "system_program"},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": False,
    },
    "pump_amm_sell_v2": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [93, 246, 130, 60, 231, 233, 64, 178],
        "accounts": [
            {"name": "pool", "writable": True},
            {"name": "user", "writable": True, "signer": True},
            {"name": "global_config"},
            {"name": "base_mint"},
            {"name": "quote_mint"},
            {"name": "user_base_token_account", "writable": True},
            {"name": "user_quote_token_account", "writable": True},
            {"name": "pool_base_token_account", "writable": True},
            {"name": "pool_quote_token_account", "writable": True},
            {"name": "base_token_program"},
            {"name": "quote_token_program"},
            {"name": "system_program"},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "fee_config"},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 2,
        "partial_fill": False,
    },
    "pump_amm_multi_hop_swap": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [43, 100, 73, 19, 233, 246, 111, 148],
        "accounts": [
            {"name": "user", "writable": True, "signer": True},
            {"name": "user_in_token_account", "writable": True},
            {"name": "user_out_token_account", "writable": True},
            {"name": "global_config"},
            {"name": "fee_config"},
            {"name": "user_volume_accumulator", "writable": True},
            {"name": "buyback_fee_recipient", "writable": True},
            {"name": "token_program"},
            {"name": "token_2022_program"},
            {"name": "system_program"},
            {"name": "event_authority"},
            {"name": "program"},
            {"name": "pump_program"},
            {"name": "pump_global"},
            {"name": "pump_fee_config"},
            {"name": "pump_event_authority"},
        ],
        "args": 2,
        "partial_fill": False,
    },
    "pump_amm_sweep_creator_fee": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [32, 246, 191, 52, 8, 201, 73, 186],
        "accounts": [
            {"name": "payer", "writable": True, "signer": True},
            {"name": "global_config"},
            {"name": "pool", "writable": True},
            {"name": "quote_mint"},
            {"name": "quote_token_program"},
            {"name": "pool_quote_token_account", "writable": True},
            {"name": "recipient"},
            {"name": "recipient_token_account", "writable": True},
            {"name": "system_program"},
            {"name": "associated_token_program"},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 0,
        "partial_fill": False,
    },
    "pump_amm_sweep_protocol_fee": {
        "program": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
        "discriminator": [8, 48, 190, 7, 182, 68, 183, 229],
        "accounts": [
            {"name": "payer", "writable": True, "signer": True},
            {"name": "global_config"},
            {"name": "pool", "writable": True},
            {"name": "quote_mint"},
            {"name": "quote_token_program"},
            {"name": "pool_quote_token_account", "writable": True},
            {"name": "recipient"},
            {"name": "recipient_token_account", "writable": True},
            {"name": "system_program"},
            {"name": "associated_token_program"},
            {"name": "event_authority"},
            {"name": "program"},
        ],
        "args": 0,
        "partial_fill": False,
    },
}


def build_pump_upgrade_instruction(
    name, accounts, amounts=(), partial_fill=None, remaining=()
):
    """Bare instruction. Caller supplies existing token accounts and validated state."""
    if name not in _SPECS:
        raise ValueError("Unsupported Pump upgrade instruction")
    s = _SPECS[name]
    if len(amounts) != s["args"] or any(
        type(n) is not int or not 0 <= n <= (1 << 64) - 1 for n in amounts
    ):
        raise ValueError("Invalid u64 arguments")
    if amounts and amounts[0] == 0:
        raise ValueError("Input amount must be positive")
    if name == "pump_amm_multi_hop_swap":
        if amounts[1] == 0 or len(remaining) < 5 or len(remaining) % 5:
            raise ValueError("Invalid multi-hop route or minimum output")
    elif remaining:
        raise ValueError("Compact trades and sweeps take no remaining accounts")
    if partial_fill is not None and (
        not s["partial_fill"] or type(partial_fill) is not bool
    ):
        raise ValueError("Invalid partial fill")
    keys = []
    for a in s["accounts"]:
        k = accounts.get(a["name"])
        if not isinstance(k, Pubkey):
            raise ValueError("Missing account: " + a["name"])
        keys.append(AccountMeta(k, a.get("signer", False), a.get("writable", False)))
    if any(
        a.is_signer or a.is_writable != (i % 5 >= 2) for i, a in enumerate(remaining)
    ):
        raise ValueError("Invalid hop account flags")
    data = bytes(s["discriminator"]) + b"".join(
        n.to_bytes(8, "little") for n in amounts
    )
    if partial_fill is not None:
        data += bytes([partial_fill])
    return Instruction(Pubkey.from_string(s["program"]), data, keys + list(remaining))


def build_pump_buy_v3_instruction(accounts, amount, limit, partial_fill=None):
    return build_pump_upgrade_instruction(
        "pump_buy_v3", accounts, (amount, limit), partial_fill
    )


def build_pump_buy_exact_quote_in_v3_instruction(
    accounts, amount, limit, partial_fill=None
):
    return build_pump_upgrade_instruction(
        "pump_buy_exact_quote_in_v3", accounts, (amount, limit), partial_fill
    )


def build_pump_sell_v3_instruction(accounts, amount, limit):
    return build_pump_upgrade_instruction(
        "pump_sell_v3", accounts, (amount, limit), None
    )


def build_pump_sweep_creator_fee_instruction(accounts):
    return build_pump_upgrade_instruction("pump_sweep_creator_fee", accounts)


def build_pump_sweep_protocol_fee_instruction(accounts):
    return build_pump_upgrade_instruction("pump_sweep_protocol_fee", accounts)


def build_pump_amm_buy_v2_instruction(accounts, amount, limit):
    return build_pump_upgrade_instruction(
        "pump_amm_buy_v2", accounts, (amount, limit), None
    )


def build_pump_amm_buy_exact_quote_in_v2_instruction(accounts, amount, limit):
    return build_pump_upgrade_instruction(
        "pump_amm_buy_exact_quote_in_v2", accounts, (amount, limit), None
    )


def build_pump_amm_sell_v2_instruction(accounts, amount, limit):
    return build_pump_upgrade_instruction(
        "pump_amm_sell_v2", accounts, (amount, limit), None
    )


def build_pump_amm_multi_hop_swap_instruction(accounts, amount, limit, remaining):
    return build_pump_upgrade_instruction(
        "pump_amm_multi_hop_swap", accounts, (amount, limit), None, remaining
    )


def build_pump_amm_sweep_creator_fee_instruction(accounts):
    return build_pump_upgrade_instruction("pump_amm_sweep_creator_fee", accounts)


def build_pump_amm_sweep_protocol_fee_instruction(accounts):
    return build_pump_upgrade_instruction("pump_amm_sweep_protocol_fee", accounts)
