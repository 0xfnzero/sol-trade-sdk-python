"""Current-state CPMM quote and direct exact-in instruction, without RPC."""

from dataclasses import dataclass
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from .stonkfun import TokenTransferFee, unsigned, ceil
from .common import get_associated_token_address

PROGRAM = Pubkey.from_string("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C")
AUTHORITY = Pubkey.from_string("GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL")


@dataclass(frozen=True)
class CachedCpmmState:
    pool: Pubkey
    config: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    base_vault: Pubkey
    quote_vault: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    observation: Pubkey
    base_reserve: int
    quote_reserve: int
    trade_fee_rate: int
    protocol_fee_rate: int
    fund_fee_rate: int
    creator_fee_rate: int
    creator_fee_on: int
    enable_creator_fee: bool
    base_transfer_fee: TokenTransferFee
    quote_transfer_fee: TokenTransferFee
    open_time: int


@dataclass(frozen=True)
class CpmmQuote:
    amount_in: int
    amount_out: int
    minimum_amount_out: int
    trade_fee: int
    creator_fee: int


def quote_cached_cpmm_exact_in(p, amount, base_in, slippage_bps=0):
    unsigned(amount)
    if not amount or not isinstance(base_in, bool):
        raise ValueError("Positive amount and boolean direction required")
    if (
        not isinstance(slippage_bps, int)
        or isinstance(slippage_bps, bool)
        or not 0 <= slippage_bps <= 9999
    ):
        raise ValueError("Slippage must be 0..9999")
    if (
        not isinstance(p.enable_creator_fee, bool)
        or not isinstance(p.creator_fee_on, int)
        or isinstance(p.creator_fee_on, bool)
    ):
        raise ValueError("Invalid CPMM fee configuration")
    raw_creator_rate = unsigned(p.creator_fee_rate)
    creator_rate = raw_creator_rate if p.enable_creator_fee else 0
    trade_rate = unsigned(p.trade_fee_rate)
    if (
        trade_rate + creator_rate >= 1000000
        or unsigned(p.protocol_fee_rate) + unsigned(p.fund_fee_rate) > 1000000
        or p.creator_fee_on not in (0, 1, 2)
    ):
        raise ValueError("Invalid CPMM fee configuration")
    i, o, input_fee, output_fee = (
        (p.base_reserve, p.quote_reserve, p.base_transfer_fee, p.quote_transfer_fee)
        if base_in
        else (p.quote_reserve, p.base_reserve, p.quote_transfer_fee, p.base_transfer_fee)
    )
    if not unsigned(i) or not unsigned(o):
        raise ValueError("Empty CPMM reserves")
    net = amount - input_fee.calculate(amount)
    on_input = (
        p.creator_fee_on == 0
        or (p.creator_fee_on == 1 and base_in)
        or (p.creator_fee_on == 2 and not base_in)
    )
    total_rate = trade_rate + (creator_rate if on_input else 0)
    fee = ceil(net * total_rate, 1000000)
    creator = fee * creator_rate // total_rate if on_input and total_rate else 0
    trade = fee - creator
    swapped = o * (net - fee) // (i + net - fee)
    if not on_input:
        creator = ceil(swapped * creator_rate, 1000000)
    gross = swapped - (creator if not on_input else 0)
    received = gross - output_fee.calculate(gross)
    return CpmmQuote(
        amount, unsigned(received), received * (10000 - slippage_bps) // 10000, trade, creator
    )


def build_cached_cpmm_exact_in(p, payer, amount, minimum_amount_out, base_in):
    unsigned(amount)
    unsigned(minimum_amount_out)
    if not amount or not isinstance(base_in, bool):
        raise ValueError("Positive amount and boolean direction required")
    im, om, iv, ov, ip, op = (
        (
            p.base_mint,
            p.quote_mint,
            p.base_vault,
            p.quote_vault,
            p.base_token_program,
            p.quote_token_program,
        )
        if base_in
        else (
            p.quote_mint,
            p.base_mint,
            p.quote_vault,
            p.base_vault,
            p.quote_token_program,
            p.base_token_program,
        )
    )
    keys = [
        payer,
        AUTHORITY,
        p.config,
        p.pool,
        get_associated_token_address(payer, im, ip),
        get_associated_token_address(payer, om, op),
        iv,
        ov,
        ip,
        op,
        im,
        om,
        p.observation,
    ]
    data = bytes([143, 190, 90, 218, 196, 30, 51, 222]) + struct.pack(
        "<QQ", amount, minimum_amount_out
    )
    return Instruction(
        PROGRAM,
        data,
        [AccountMeta(k, i == 0, i in (0, 3, 4, 5, 6, 7, 12)) for i, k in enumerate(keys)],
    )
