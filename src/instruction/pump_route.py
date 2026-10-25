"""Official vs sequential execution; independent of the single-trade version. No RPC."""
from dataclasses import dataclass
from enum import Enum
from solders.pubkey import Pubkey
from .pump_compact_accounts import derive_pump_multi_hop_accounts
from .pump_upgrade import build_pump_amm_multi_hop_swap_instruction
from .common import TOKEN_PROGRAM, TOKEN_PROGRAM_2022


class PumpRouteExecution(str, Enum):
    AUTO = "auto"
    OFFICIAL = "official"
    SEQUENTIAL = "sequential"


@dataclass(frozen=True)
class PumpRouteOptions:
    execution: PumpRouteExecution = PumpRouteExecution.AUTO
    # Fresh final recipient credit; sequential hop quotes are not official quotes.
    minimum_output_amount: int | None = None
    buyback_recipient: Pubkey | None = None


def select_pump_route(options, user, input_mint, output_mint, amount, hops=None):
    """None selects sequential execution. Never retry a failed submission here."""
    execution = PumpRouteExecution(options.execution)
    positive = lambda n: type(n) is int and 0 < n < 1 << 64
    if not positive(amount):
        raise ValueError("Pump route input must be a positive u64")
    if execution == PumpRouteExecution.SEQUENTIAL:
        return None
    if options.minimum_output_amount is not None and not positive(options.minimum_output_amount):
        raise ValueError("Official Pump route minimum must be a positive u64")
    if options.buyback_recipient == Pubkey.default():
        raise ValueError("Missing Pump buyback recipient")
    if execution == PumpRouteExecution.AUTO and (not hops or not 2 <= len(hops) <= 3
            or options.minimum_output_amount is None or options.buyback_recipient is None):
        return None
    try:
        if not hops or not 2 <= len(hops) <= 3:
            raise ValueError("Official Pump routes require two or three supported hops")
        if options.minimum_output_amount is None or options.buyback_recipient is None:
            raise ValueError("Provide an official final minimum and current buyback recipient")
        if user == Pubkey.default() or input_mint == output_mint:
            raise ValueError("Invalid Pump route endpoints")
        seen, current, previous = {input_mint}, input_mint, None
        for h in hops:
            if any(p not in (TOKEN_PROGRAM, TOKEN_PROGRAM_2022) for p in (h.base_token_program, h.quote_token_program)):
                raise ValueError("Unknown Pump route token program")
            buy = current == h.quote_mint
            if not buy and current != h.base_mint:
                raise ValueError("Disconnected Pump route")
            next_mint = h.base_mint if buy else h.quote_mint
            program = h.quote_token_program if buy else h.base_token_program
            if previous is not None and previous != program:
                raise ValueError("Inconsistent intermediate token program")
            if next_mint in seen:
                raise ValueError("Pump route contains an asset cycle")
            seen.add(next_mint)
            if Pubkey.default() in (h.address, h.base_vault, h.quote_vault) or h.base_vault == h.quote_vault:
                raise ValueError("Incomplete Pump route venue")
            current, previous = next_mint, h.base_token_program if buy else h.quote_token_program
        accounts, remaining = derive_pump_multi_hop_accounts(user, input_mint, output_mint, options.buyback_recipient, hops)
        return build_pump_amm_multi_hop_swap_instruction(accounts, amount, options.minimum_output_amount, remaining)
    except ValueError:
        if execution == PumpRouteExecution.AUTO:
            return None
        raise
