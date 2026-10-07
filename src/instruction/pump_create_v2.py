"""Pump create_v2 with listed or Pump-coin quote remaining accounts."""

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

ROLES = [
    {"name": "mint", "writable": True, "signer": True},
    {"name": "mint_authority", "writable": False, "signer": False},
    {"name": "bonding_curve", "writable": True, "signer": False},
    {"name": "associated_bonding_curve", "writable": True, "signer": False},
    {"name": "global", "writable": False, "signer": False},
    {"name": "user", "writable": True, "signer": True},
    {"name": "system_program", "writable": False, "signer": False},
    {"name": "token_program", "writable": False, "signer": False},
    {"name": "associated_token_program", "writable": False, "signer": False},
    {"name": "mayhem_program_id", "writable": True, "signer": False},
    {"name": "global_params", "writable": False, "signer": False},
    {"name": "sol_vault", "writable": True, "signer": False},
    {"name": "mayhem_state", "writable": True, "signer": False},
    {"name": "mayhem_token_vault", "writable": True, "signer": False},
    {"name": "event_authority", "writable": False, "signer": False},
    {"name": "program", "writable": False, "signer": False},
]


def build_pump_create_v2_instruction(
    accounts,
    name,
    symbol,
    uri,
    creator,
    *,
    mayhem=False,
    creator_fee_bps=0,
    holder_reward=False,
    remaining=()
):
    if len(remaining) not in (0, 3, 4, 5, 8) or any(
        a.is_signer or a.is_writable != (i == 1) for i, a in enumerate(remaining)
    ):
        raise ValueError("Invalid quote creation accounts")
    if len(remaining) >= 5 and mayhem:
        raise ValueError("Mayhem pump coin quote not allowed")
    if type(creator_fee_bps) is not int or not 0 <= creator_fee_bps <= 10000:
        raise ValueError("Invalid creator fee")
    data = bytes([214, 144, 76, 236, 95, 139, 49, 180])
    for s in (name, symbol, uri):
        b = s.encode("utf8")
        data += len(b).to_bytes(4, "little") + b
    data += (
        bytes(creator)
        + bytes([mayhem, False])
        + creator_fee_bps.to_bytes(8, "little")
        + bytes([holder_reward])
    )
    keys = [AccountMeta(accounts[a["name"]], a["signer"], a["writable"]) for a in ROLES]
    return Instruction(
        Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"),
        data,
        keys + list(remaining),
    )


def decode_pump_quote_control(data):
    """Current QuoteControl: admin, reserves_admin, reserved[32], vec(mint,u64)."""
    if len(data) < 108 or data[:8] != bytes([56, 244, 35, 238, 193, 213, 162, 201]):
        raise ValueError("Invalid QuoteControl")
    count = int.from_bytes(data[104:108], "little")
    if count > (len(data) - 108) // 40:
        raise ValueError("Truncated QuoteControl")
    return dict(
        admin=Pubkey.from_bytes(data[8:40]),
        reserves_admin=Pubkey.from_bytes(data[40:72]),
        mints=[
            dict(
                mint=Pubkey.from_bytes(data[108 + i * 40 : 140 + i * 40]),
                initial_virtual_quote_reserves=int.from_bytes(
                    data[140 + i * 40 : 148 + i * 40], "little"
                ),
            )
            for i in range(count)
        ],
    )
