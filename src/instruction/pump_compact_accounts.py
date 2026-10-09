"""Derive compact account roles. Token accounts must already exist; no RPC."""

from dataclasses import replace
from solders.pubkey import Pubkey

PUMP = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
AMM = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
FEES = Pubkey.from_string("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")
ATA = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
WSOL = Pubkey.from_string("So11111111111111111111111111111111111111112")


def _normalize_quote(mint):
    if mint in (
        Pubkey.default(),
        Pubkey.from_string("So11111111111111111111111111111111111111111"),
    ):
        return WSOL
    return mint


def _normalize_hop(hop):
    quote = _normalize_quote(hop.quote_mint)
    token = (
        Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        if quote == WSOL
        else hop.quote_token_program
    )
    return replace(hop, quote_mint=quote, quote_token_program=token)


def _pda(program, seed, key=None):
    return Pubkey.find_program_address(
        [seed.encode()] + ([] if key is None else [bytes(key)]), program
    )[0]


def _ata(owner, mint, token):
    return Pubkey.find_program_address([bytes(owner), bytes(token), bytes(mint)], ATA)[
        0
    ]


def derive_pump_v3_accounts(
    user,
    base_mint,
    quote_mint,
    base_token_program,
    quote_token_program,
    buyback_recipient,
    *,
    cashback=False,
    complete=False
):
    quote_mint = _normalize_quote(quote_mint)
    if quote_mint == WSOL:
        quote_token_program = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    if cashback:
        raise ValueError("Cashback coins require Pump v2")
    if complete:
        raise ValueError("BondingCurveComplete")
    curve = _pda(PUMP, "bonding-curve", base_mint)
    accounts = dict(
        global_account=_pda(PUMP, "global"),
        base_mint=base_mint,
        quote_mint=quote_mint,
        base_token_program=base_token_program,
        quote_token_program=quote_token_program,
        bonding_curve=curve,
        associated_base_bonding_curve=_ata(curve, base_mint, base_token_program),
        associated_quote_bonding_curve=_ata(curve, quote_mint, quote_token_program),
        user=user,
        associated_base_user=_ata(user, base_mint, base_token_program),
        associated_quote_user=_ata(user, quote_mint, quote_token_program),
        user_volume_accumulator=_pda(PUMP, "user_volume_accumulator", user),
        fee_config=_pda(FEES, "fee_config", PUMP),
        buyback_fee_recipient=(
            buyback_recipient
            if quote_mint == WSOL
            else _ata(buyback_recipient, quote_mint, quote_token_program)
        ),
        system_program=Pubkey.default(),
        event_authority=_pda(PUMP, "__event_authority"),
        program=PUMP,
    )
    accounts["global"] = accounts.pop("global_account")
    return accounts


def derive_pump_swap_v2_accounts(
    user,
    base_mint,
    quote_mint,
    base_token_program,
    quote_token_program,
    buyback_recipient,
    pool,
    base_vault,
    quote_vault,
    *,
    cashback=False
):
    quote_mint = _normalize_quote(quote_mint)
    if quote_mint == WSOL:
        quote_token_program = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    if cashback:
        raise ValueError("Cashback pools require PumpSwap v1")
    return dict(
        pool=pool,
        user=user,
        global_config=_pda(AMM, "global_config"),
        base_mint=base_mint,
        quote_mint=quote_mint,
        user_base_token_account=_ata(user, base_mint, base_token_program),
        user_quote_token_account=_ata(user, quote_mint, quote_token_program),
        pool_base_token_account=base_vault,
        pool_quote_token_account=quote_vault,
        base_token_program=base_token_program,
        quote_token_program=quote_token_program,
        system_program=Pubkey.default(),
        user_volume_accumulator=_pda(AMM, "user_volume_accumulator", user),
        fee_config=_pda(FEES, "fee_config", AMM),
        buyback_fee_recipient=_ata(buyback_recipient, quote_mint, quote_token_program),
        event_authority=_pda(AMM, "__event_authority"),
        program=AMM,
    )


from dataclasses import dataclass
from solders.instruction import AccountMeta


@dataclass
class PumpMultiHop:
    venue: str
    base_mint: Pubkey
    quote_mint: Pubkey
    address: Pubkey
    base_vault: Pubkey
    quote_vault: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    mayhem: bool = False
    cashback: bool = False
    complete: bool = False
    index: int = 0
    creator: Pubkey = None


def derive_pump_multi_hop_accounts(
    user, input_mint, output_mint, buyback_recipient, hops, *, use_v0_with_alt=False
):
    """Uses decoded venue state; ATAs must exist. Four hops require v0 + ALT."""
    if not hops or (len(hops) >= 4 and not use_v0_with_alt):
        raise ValueError("Route requires hops and v0 with ALT for four or more hops")
    input_mint = _normalize_quote(input_mint)
    output_mint = _normalize_quote(output_mint)
    hops = [_normalize_hop(h) for h in hops]
    current = input_mint
    side = None
    remaining = []
    for i, h in enumerate(hops):
        if h.mayhem or h.base_mint == h.quote_mint:
            raise ValueError("Invalid multi-hop venue")
        buy = current == h.quote_mint
        if not buy and current != h.base_mint:
            raise ValueError("Discontinuous route")
        if side is not None and side != buy:
            raise ValueError("Mixed route direction")
        side = buy
        if h.cashback and i != (0 if buy else len(hops) - 1):
            raise ValueError("Cashback must be at currency endpoint")
        if h.venue == "curve":
            curve = _pda(PUMP, "bonding-curve", h.base_mint)
            if (
                h.complete
                or h.address != curve
                or h.base_vault != _ata(curve, h.base_mint, h.base_token_program)
                or h.quote_vault != _ata(curve, h.quote_mint, h.quote_token_program)
            ):
                raise ValueError("Invalid curve accounts")
        elif h.venue == "pool":
            authority = _pda(PUMP, "pool-authority", h.base_mint)
            pool = Pubkey.find_program_address(
                [
                    b"pool",
                    bytes([0, 0]),
                    bytes(authority),
                    bytes(h.base_mint),
                    bytes(h.quote_mint),
                ],
                AMM,
            )[0]
            if h.index != 0 or h.creator != authority or h.address != pool:
                raise ValueError("Noncanonical Pump pool")
        else:
            raise ValueError("Unknown venue")
        remaining.extend(
            AccountMeta(key, False, j >= 2)
            for j, key in enumerate(
                [h.base_mint, h.quote_mint, h.address, h.base_vault, h.quote_vault]
            )
        )
        current = h.base_mint if buy else h.quote_mint
    if current != output_mint:
        raise ValueError("Wrong output mint")
    first, last = hops[0], hops[-1]
    currency = first if side else last
    accounts = dict(
        user=user,
        user_in_token_account=_ata(
            user,
            input_mint,
            first.quote_token_program if side else first.base_token_program,
        ),
        user_out_token_account=_ata(
            user,
            output_mint,
            last.base_token_program if side else last.quote_token_program,
        ),
        global_config=_pda(AMM, "global_config"),
        fee_config=_pda(FEES, "fee_config", AMM),
        user_volume_accumulator=_pda(AMM, "user_volume_accumulator", user),
        buyback_fee_recipient=_ata(
            buyback_recipient, currency.quote_mint, currency.quote_token_program
        ),
        token_program=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
        token_2022_program=Pubkey.from_string(
            "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
        ),
        system_program=Pubkey.default(),
        event_authority=_pda(AMM, "__event_authority"),
        program=AMM,
        pump_program=PUMP,
        pump_global=_pda(PUMP, "global"),
        pump_fee_config=_pda(FEES, "fee_config", PUMP),
        pump_event_authority=_pda(PUMP, "__event_authority"),
    )
    return accounts, remaining


def derive_pump_coin_quote_create_accounts(
    new_mint, quote, depth, max_depth, listed_quote_mints=()
):
    """Additional create_v2 roles for an unlisted Pump coin quote, from decoded state."""
    quote = _normalize_hop(quote)
    if (
        type(depth) is not int
        or type(max_depth) is not int
        or not 0 <= depth < max_depth
    ):
        raise ValueError("CurveDepthExceeded")
    if depth == 0 and quote.quote_mint not in (
        WSOL,
        Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
        *listed_quote_mints,
    ):
        raise ValueError("QuoteBondingCurveNotEligible")
    derive_pump_multi_hop_accounts(
        new_mint, quote.quote_mint, quote.base_mint, new_mint, [quote]
    )
    curve = _pda(PUMP, "bonding-curve", new_mint)
    keys = [
        quote.base_mint,
        _ata(curve, quote.base_mint, quote.base_token_program),
        quote.base_token_program,
        _pda(PUMP, "quote-control"),
        _pda(PUMP, "bonding-curve", quote.base_mint),
    ]
    if quote.venue == "pool":
        keys.extend([quote.address, quote.base_vault, quote.quote_vault])
    return [AccountMeta(key, False, i == 1) for i, key in enumerate(keys)]
