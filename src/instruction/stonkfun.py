"""Native stock-quoted LaunchLab instruction and exact integer quote math."""

from dataclasses import dataclass
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from .common import get_associated_token_address

PROGRAM = Pubkey.from_string("LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj")
AUTHORITY = Pubkey.from_string("WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh")
EVENT_AUTHORITY = Pubkey.from_string("2DPAtwB8L12vrMRExbLuyGnC7n2J5LNoZQSejeQGpwkr")
CONFIGS = {
    "4E876qZTE9FJMrBzgVtBrSrzz2TLivB5Y5QXPjB4gZL7",
    "6BwHHDg3u1854jC8PDLXvR4spTcLNaoBxLJNGC4nTESt",
}
U64 = (1 << 64) - 1
U128 = (1 << 128) - 1


def unsigned(v, maximum=U64):
    if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= maximum:
        raise ValueError("Amount outside unsigned integer range")
    return v


def ceil(n, d):
    return (n + d - 1) // d


@dataclass(frozen=True)
class TokenTransferFee:
    basis_points: int = 0
    maximum_fee: int = 0

    def calculate(self, amount, inverse=False):
        unsigned(amount)
        unsigned(self.maximum_fee)
        if not isinstance(inverse, bool):
            raise ValueError("Boolean transfer fee direction required")
        if (
            not isinstance(self.basis_points, int)
            or isinstance(self.basis_points, bool)
            or not 0 <= self.basis_points <= 10000
        ):
            raise ValueError("Invalid token fee basis points")
        if not self.basis_points or not amount:
            return 0
        rate = self.basis_points
        value = (
            (self.maximum_fee if rate == 10000 else ceil(amount * rate, 10000 - rate))
            if inverse
            else ceil(amount * rate, 10000)
        )
        return min(value, self.maximum_fee)


@dataclass(frozen=True)
class LaunchLabQuoteState:
    virtual_base: int
    virtual_quote: int
    real_base: int
    real_quote: int
    total_base_sell: int
    curve_type: int
    trade_fee_rate: int
    platform_fee_rate: int
    creator_fee_rate: int
    base_transfer_fee: TokenTransferFee = TokenTransferFee()
    quote_transfer_fee: TokenTransferFee = TokenTransferFee()


@dataclass(frozen=True)
class LaunchLabQuote:
    amount_in: int
    minimum_amount_out: int


def quote_launchlab_exact_in(p, amount, buy, slippage_bps=0, share_fee_rate=0):
    unsigned(amount)
    if not amount:
        raise ValueError("Amount cannot be zero")
    if not isinstance(buy, bool):
        raise ValueError("Boolean trade direction required")
    if not isinstance(p.curve_type, int) or isinstance(p.curve_type, bool) or p.curve_type != 0:
        raise ValueError("Unsupported LaunchLab curve type")
    for n in (p.virtual_base, p.virtual_quote, p.real_base, p.real_quote, p.total_base_sell):
        unsigned(n, U128)
    if p.real_base > p.virtual_base:
        raise ValueError("LaunchLab reserve underflow")
    base, quote = p.virtual_base - p.real_base, unsigned(p.virtual_quote + p.real_quote, U128)
    rate = sum(
        unsigned(n)
        for n in (p.trade_fee_rate, p.platform_fee_rate, p.creator_fee_rate, share_fee_rate)
    )
    if rate > 1000000:
        raise ValueError("LaunchLab fee exceeds denominator")
    if (
        not isinstance(slippage_bps, int)
        or isinstance(slippage_bps, bool)
        or not 0 <= slippage_bps <= 9999
    ):
        raise ValueError("Slippage must be 0..9999")
    actual = amount
    if buy:
        vault = amount - p.quote_transfer_fee.calculate(amount)
        net = vault - ceil(vault * rate, 1000000)
        denominator = unsigned(quote + net, U128)
        if not denominator:
            raise ValueError("Empty curve reserves")
        out = unsigned(net * base, U128) // denominator
        if p.total_base_sell:
            if p.real_base > p.total_base_sell:
                raise ValueError("LaunchLab sold amount exceeds cap")
            remaining = p.total_base_sell - p.real_base
            if out > remaining:
                after = base - remaining
                if after <= 0 or rate == 1000000:
                    raise ValueError("LaunchLab graduation exhausts reserves")
                required = ceil(unsigned(quote * remaining, U128), after)
                required_vault = unsigned(ceil(unsigned(required * 1000000, U128), 1000000 - rate))
                actual = min(
                    unsigned(required_vault + p.quote_transfer_fee.calculate(required_vault, True)),
                    amount,
                )
                out = remaining
        unsigned(out)
        received = out - p.base_transfer_fee.calculate(out)
    else:
        net = amount - p.base_transfer_fee.calculate(amount)
        denominator = unsigned(base + net, U128)
        if not denominator:
            raise ValueError("Empty curve reserves")
        gross = unsigned(net * quote, U128) // denominator
        vault = unsigned(gross - ceil(gross * rate, 1000000))
        received = vault - p.quote_transfer_fee.calculate(vault)
    return LaunchLabQuote(actual, unsigned(received - received * slippage_bps // 10000))


@dataclass(frozen=True)
class StonkFunCurveAccounts:
    pool: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    base_vault: Pubkey
    quote_vault: Pubkey
    global_config: Pubkey
    platform_config: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    platform_associated_account: Pubkey
    creator_associated_account: Pubkey


def build_stonkfun_curve_exact_in(p, payer, amount_in, minimum_amount_out, buy, share_fee_rate=0):
    if str(p.platform_config) not in CONFIGS:
        raise ValueError("Unverified StonkFun platform config")
    return build_launchlab_curve_exact_in(p,payer,amount_in,minimum_amount_out,buy,share_fee_rate)


def build_launchlab_curve_exact_in(p, payer, amount_in, minimum_amount_out, buy, share_fee_rate=0):
    """One swap. ATA creation, funding and SOL wrapping are caller operations."""
    unsigned(amount_in)
    unsigned(minimum_amount_out)
    unsigned(share_fee_rate)
    if not amount_in:
        raise ValueError("Amount cannot be zero")
    if not isinstance(buy, bool):
        raise ValueError("Boolean trade direction required")
    if p.base_mint == p.quote_mint:
        raise ValueError("Identical base and quote")
    if any(k == Pubkey.default() for k in p.__dict__.values()):
        raise ValueError("Missing StonkFun account")
    user_base = get_associated_token_address(payer, p.base_mint, p.base_token_program)
    user_quote = get_associated_token_address(payer, p.quote_mint, p.quote_token_program)
    keys = [
        payer,
        AUTHORITY,
        p.global_config,
        p.platform_config,
        p.pool,
        user_base,
        user_quote,
        p.base_vault,
        p.quote_vault,
        p.base_mint,
        p.quote_mint,
        p.base_token_program,
        p.quote_token_program,
        EVENT_AUTHORITY,
        PROGRAM,
        Pubkey.default(),
        p.platform_associated_account,
        p.creator_associated_account,
    ]
    data = bytes(
        [250, 234, 13, 123, 213, 156, 19, 236] if buy else [149, 39, 222, 155, 211, 124, 152, 26]
    ) + struct.pack("<QQQ", amount_in, minimum_amount_out, share_fee_rate)
    return Instruction(
        PROGRAM,
        data,
        [AccountMeta(k, i == 0, i in (0, 4, 5, 6, 7, 8, 16, 17)) for i, k in enumerate(keys)],
    )


@dataclass(frozen=True)
class LaunchLabAccountBytes:
    pubkey: Pubkey
    owner: Pubkey
    data: bytes


def decode_stonkfun_curve(
    pool,
    global_config,
    platform,
    base_token_program,
    quote_token_program,
    base_transfer_fee,
    quote_transfer_fee,
):
    if str(platform.pubkey) not in CONFIGS:
        raise ValueError("LaunchLab config identity mismatch")
    return decode_launchlab_curve(pool,global_config,platform,base_token_program,quote_token_program,base_transfer_fee,quote_transfer_fee)


def decode_launchlab_curve(pool,global_config,platform,base_token_program,quote_token_program,base_transfer_fee,quote_transfer_fee):
    for a in (pool, global_config, platform):
        if a.owner != PROGRAM:
            raise ValueError("Unexpected LaunchLab account owner")
    d, g, p = bytes(pool.data), bytes(global_config.data), bytes(platform.data)
    if (
        len(d) < 429
        or d[:8] != bytes.fromhex("f7ede3f5d7c3de46")
        or len(g) < 35
        or g[:8] != bytes.fromhex("95089ccaa0fcb0d9")
        or len(p) < 728
        or p[:8] != bytes.fromhex("a04e8000f853e6a0")
    ):
        raise ValueError("Invalid LaunchLab state bytes")
    key = lambda o: Pubkey.from_bytes(d[o : o + 32])
    number = lambda data, o: int.from_bytes(data[o : o + 8], "little")
    if (
        key(141) != global_config.pubkey
        or key(173) != platform.pubkey
    ):
        raise ValueError("LaunchLab config identity mismatch")
    if d[17] != 0:
        raise ValueError("LaunchLab curve is not trading")
    quote, creator = key(237), key(333)
    associated = lambda k: Pubkey.find_program_address([bytes(k), bytes(quote)], PROGRAM)[0]
    accounts = StonkFunCurveAccounts(
        pool.pubkey,
        key(205),
        quote,
        key(269),
        key(301),
        global_config.pubkey,
        platform.pubkey,
        base_token_program,
        quote_token_program,
        associated(platform.pubkey),
        associated(creator),
    )
    state = LaunchLabQuoteState(
        number(d, 37),
        number(d, 45),
        number(d, 53),
        number(d, 61),
        number(d, 29),
        g[16],
        number(g, 27),
        number(p, 104),
        number(p, 720),
        base_transfer_fee,
        quote_transfer_fee,
    )
    return accounts, state
