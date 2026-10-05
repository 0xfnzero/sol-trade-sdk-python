"""Native cached DLMM exact-in preparation. No network calls or guessed liquidity."""

from dataclasses import dataclass
from solders.pubkey import Pubkey
from ..calc.dlmm import (
    DlmmPool,
    DlmmStaticFee,
    DlmmVariableFee,
    DlmmBin,
    dlmm_swap_exact_in,
    InsufficientDlmmArrays,
)
from ..instruction.stonkfun import unsigned
from ..instruction.token_mint_state import token_transfer_fee_for_epoch
from ..instruction.common import get_associated_token_address
from ..instruction.native_hops import DLMM, MeteoraDlmmSwap2Accounts, build_meteora_dlmm_swap2


@dataclass(frozen=True)
class CachedDlmmQuote:
    amount_in: int
    estimated_net_amount_out: int
    minimum_net_amount_out: int
    minimum_amount_out: int
    state_slot: int
    epoch: int
    bins_crossed: int


def decode_dlmm_bins(data, pool, index):
    if type(index) is not int or not -6338 <= index <= 6337:
        raise ValueError("Invalid DLMM array index")
    d = bytes(data)
    if (
        len(d) < 10136
        or d[:8] != bytes([92, 142, 92, 220, 5, 148, 70, 181])
        or int.from_bytes(d[8:16], "little", signed=True) != index
        or d[24:56] != bytes(pool)
    ):
        raise ValueError("Invalid DLMM bin array identity")
    result = []
    for i in range(70):
        o = 56 + i * 144
        n = lambda p, w: int.from_bytes(d[o + p : o + p + w], "little")
        ax, ay, price, oo, po = n(0, 8), n(8, 8), n(16, 16), n(112, 8), n(128, 8)
        if not price:
            if ax or ay or oo or po:
                raise ValueError("Zero DLMM bin price with liquidity")
            continue
        bid = index * 70 + i
        if not -443636 <= bid <= 443636:
            raise ValueError("DLMM bin outside range")
        result.append(DlmmBin(bid, ax, ay, price, oo, po, d[o + 140]))
    return result


def prepare_cached_dlmm(
    snapshot, hint, context, unix_timestamp, payer, amount, slippage_bps=0, maximum_arrays=8
):
    unsigned(amount)
    unsigned(unix_timestamp, (1 << 63) - 1)
    if (
        not amount
        or type(slippage_bps) is not int
        or not 0 <= slippage_bps < 10000
        or type(maximum_arrays) is not int
        or not 1 <= maximum_arrays <= 32
    ):
        raise ValueError("Invalid cached DLMM request")
    d = snapshot.get(hint.pool, context, DLMM).data
    if len(d) < 904 or d[:8] != bytes([33, 11, 49, 98, 181, 101, 177, 13]) or d[82] != 0:
        raise ValueError("Disabled or invalid DLMM pool")
    key = lambda o: Pubkey.from_bytes(d[o : o + 32])
    n = lambda o, w, s=False: int.from_bytes(d[o : o + w], "little", signed=s)
    hint.matches(key(88), key(120))
    if d[86] > 1 or (context.slot if d[86] == 0 else unix_timestamp) < n(816, 8):
        raise ValueError("DLMM not activated")
    if d[35] > 2:
        raise ValueError("Unknown DLMM function type")
    orders = d[35] == 2 or (
        d[35] == 0 and key(264) == Pubkey.default() and key(408) == Pubkey.default()
    )
    state = DlmmPool(
        n(76, 4, True),
        n(80, 2),
        d[36],
        DlmmStaticFee(n(8, 2), d[34], n(16, 4), n(20, 4), n(10, 2), n(12, 2), n(14, 2)),
        DlmmVariableFee(n(40, 4), n(44, 4), n(48, 4, True), n(56, 8, True)),
    )
    mints = [snapshot.get(key(o), context) for o in (88, 120)]
    fees = [token_transfer_fee_for_epoch(a.data, a.owner, context.epoch) for a in mints]
    down = hint.input_mint == key(88)
    fi, fo = (fees[0], fees[1]) if down else (fees[1], fees[0])
    net_input = amount - fi.calculate(amount)
    if not net_input:
        raise ValueError("Zero DLMM input after transfer fee")
    arrays = []
    loaded = []
    bins = []
    bitmap = None
    extension = None
    for offset in range(12676):
        index = state.active_id // 70 + (-offset if down else offset)
        if index * 70 > 443636 or (index + 1) * 70 <= -443636:
            break
        if -512 <= index < 512:
            initialized = bool(d[584 + (index + 512) // 8] & (1 << ((index + 512) % 8)))
        else:
            if extension is None:
                bitmap = Pubkey.find_program_address([b"bitmap", bytes(hint.pool)], DLMM)[0]
                extension = snapshot.get(bitmap, context, DLMM).data
                if (
                    len(extension) < 1576
                    or extension[:8] != bytes([80, 111, 124, 113, 55, 237, 18, 5])
                    or extension[8:40] != bytes(hint.pool)
                ):
                    raise ValueError("DLMM bitmap identity mismatch")
            pos = index - 512 if index >= 512 else -index - 513
            if not 0 <= pos < 6144:
                raise ValueError("DLMM bitmap index outside range")
            initialized = bool(
                extension[(40 if index >= 512 else 808) + pos // 8] & (1 << (pos % 8))
            )
        loaded.append(index)
        if initialized:
            address = Pubkey.find_program_address(
                [b"bin_array", bytes(hint.pool), index.to_bytes(8, "little", signed=True)], DLMM
            )[0]
            bins.extend(
                decode_dlmm_bins(snapshot.get(address, context, DLMM).data, hint.pool, index)
            )
            arrays.append(address)
        if not initialized:
            continue
        try:
            r = dlmm_swap_exact_in(state, bins, loaded, net_input, unix_timestamp, down, orders)
        except InsufficientDlmmArrays:
            r = None
        if r is not None and r.complete and not r.remaining_in and arrays:
            net = r.amount_out - fo.calculate(r.amount_out)
            minimum = net * (10000 - slippage_bps) // 10000
            if not minimum:
                raise ValueError("Zero protected DLMM output")
            quote = CachedDlmmQuote(
                amount, net, minimum, minimum, context.slot, context.epoch, r.bins_crossed
            )
            a = MeteoraDlmmSwap2Accounts(
                hint.pool,
                key(152),
                key(184),
                get_associated_token_address(payer, hint.input_mint, mints[0 if down else 1].owner),
                get_associated_token_address(
                    payer, hint.output_mint, mints[1 if down else 0].owner
                ),
                key(88),
                key(120),
                key(552),
                payer,
                mints[0].owner,
                mints[1].owner,
                tuple(arrays),
                bitmap,
            )
            return a, quote, build_meteora_dlmm_swap2(a, amount, minimum)
        if len(arrays) >= maximum_arrays:
            raise ValueError("DLMM quote exceeds array budget")
    raise ValueError("Insufficient DLMM liquidity in supplied snapshot")
