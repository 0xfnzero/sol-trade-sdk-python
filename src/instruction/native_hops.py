"""Native direct CLMM, Whirlpool and DLMM conversion instructions, without RPC."""

from dataclasses import dataclass
from typing import Tuple, Optional
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

MEMO = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
CLMM = Pubkey.from_string("CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK")
WHIRLPOOL = Pubkey.from_string("whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc")
DLMM = Pubkey.from_string("LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo")
DLMM_EVENT = Pubkey.from_string("D1ZN9Wj1fRSUQfCjhvnu1hqDMT7hzjzBBpi12nVniYD6")


@dataclass(frozen=True)
class SwapV2Args:
    amount: int
    other_amount_threshold: int
    sqrt_price_limit: int = 0
    amount_specified_is_input: bool = True


def data_v2(args):
    for v in (args.amount, args.other_amount_threshold):
        if type(v) is not int or not 0 <= v < 1 << 64:
            raise ValueError("Swap amount outside u64")
    if type(args.sqrt_price_limit) is not int or not 0 <= args.sqrt_price_limit < 1 << 128:
        raise ValueError("Sqrt price outside u128")
    if type(args.amount_specified_is_input) is not bool:
        raise ValueError("Swap mode must be boolean")
    return (
        bytes([43, 4, 237, 11, 26, 201, 30, 98])
        + struct.pack("<QQ", args.amount, args.other_amount_threshold)
        + args.sqrt_price_limit.to_bytes(16, "little")
        + bytes([args.amount_specified_is_input])
    )


def instruction(program, data, keys, signer, writable):
    return Instruction(
        program, data, [AccountMeta(k, i == signer, writable(i)) for i, k in enumerate(keys)]
    )


@dataclass(frozen=True)
class RaydiumClmmSwapV2Accounts:
    payer: Pubkey
    amm_config: Pubkey
    pool_state: Pubkey
    input_token_account: Pubkey
    output_token_account: Pubkey
    input_vault: Pubkey
    output_vault: Pubkey
    observation_state: Pubkey
    token_program: Pubkey
    token_program_2022: Pubkey
    input_vault_mint: Pubkey
    output_vault_mint: Pubkey
    tick_arrays: Tuple[Pubkey, ...]
    tick_array_bitmap_extension: Optional[Pubkey] = None


def build_raydium_clmm_swap_v2(a, args):
    pda = Pubkey.find_program_address(
        [b"pool_tick_array_bitmap_extension", bytes(a.pool_state)], CLMM
    )[0]
    if a.tick_array_bitmap_extension is not None and a.tick_array_bitmap_extension != pda:
        raise ValueError("CLMM bitmap identity mismatch")
    ticks = [k for k in a.tick_arrays if k != pda]
    bitmap = a.tick_array_bitmap_extension == pda or pda in a.tick_arrays
    if not ticks:
        raise ValueError("CLMM requires at least one tick array")
    keys = (
        [
            a.payer,
            a.amm_config,
            a.pool_state,
            a.input_token_account,
            a.output_token_account,
            a.input_vault,
            a.output_vault,
            a.observation_state,
            a.token_program,
            a.token_program_2022,
            MEMO,
            a.input_vault_mint,
            a.output_vault_mint,
        ]
        + ([pda] if bitmap else [])
        + ticks
    )
    return instruction(CLMM, data_v2(args), keys, 0, lambda i: 2 <= i <= 7 or i >= 13)


@dataclass(frozen=True)
class WhirlpoolSwapV2Accounts:
    token_program_a: Pubkey
    token_program_b: Pubkey
    token_authority: Pubkey
    whirlpool: Pubkey
    mint_a: Pubkey
    mint_b: Pubkey
    owner_a: Pubkey
    vault_a: Pubkey
    owner_b: Pubkey
    vault_b: Pubkey
    tick_arrays: Tuple[Pubkey, ...]


def build_whirlpool_swap_v2(a, args, a_to_b):
    if type(a_to_b) is not bool:
        raise ValueError("Swap direction must be boolean")
    if not 3 <= len(a.tick_arrays) <= 6:
        raise ValueError("Whirlpool requires 3..6 tick arrays")
    oracle = Pubkey.find_program_address([b"oracle", bytes(a.whirlpool)], WHIRLPOOL)[0]
    keys = (
        [
            a.token_program_a,
            a.token_program_b,
            MEMO,
            a.token_authority,
            a.whirlpool,
            a.mint_a,
            a.mint_b,
            a.owner_a,
            a.vault_a,
            a.owner_b,
            a.vault_b,
        ]
        + list(a.tick_arrays[:3])
        + [oracle]
        + list(a.tick_arrays[3:])
    )
    limit = args.sqrt_price_limit or (4295048016 if a_to_b else 79226673515401279992447579055)
    data = data_v2(
        SwapV2Args(args.amount, args.other_amount_threshold, limit, args.amount_specified_is_input)
    ) + bytes([a_to_b])
    data += (
        bytes([1]) + struct.pack("<I", 1) + bytes([6, len(a.tick_arrays) - 3])
        if len(a.tick_arrays) > 3
        else bytes([0])
    )
    return instruction(WHIRLPOOL, data, keys, 3, lambda i: i == 4 or i >= 7)


@dataclass(frozen=True)
class MeteoraDlmmSwap2Accounts:
    lb_pair: Pubkey
    reserve_x: Pubkey
    reserve_y: Pubkey
    user_token_in: Pubkey
    user_token_out: Pubkey
    token_x_mint: Pubkey
    token_y_mint: Pubkey
    oracle: Pubkey
    user: Pubkey
    token_x_program: Pubkey
    token_y_program: Pubkey
    bin_arrays: Tuple[Pubkey, ...]
    bitmap_extension: Optional[Pubkey] = None


def build_meteora_dlmm_swap2(a, amount_in, min_out):
    if not a.bin_arrays:
        raise ValueError("DLMM requires at least one bin array")
    for v in (amount_in, min_out):
        if type(v) is not int or not 0 <= v < 1 << 64:
            raise ValueError("Swap amount outside u64")
    keys = [
        a.lb_pair,
        a.bitmap_extension or DLMM,
        a.reserve_x,
        a.reserve_y,
        a.user_token_in,
        a.user_token_out,
        a.token_x_mint,
        a.token_y_mint,
        a.oracle,
        DLMM,
        a.user,
        a.token_x_program,
        a.token_y_program,
        MEMO,
        DLMM_EVENT,
        DLMM,
    ] + list(a.bin_arrays)
    data = bytes([65, 75, 63, 76, 235, 91, 91, 136]) + struct.pack("<QQI", amount_in, min_out, 0)
    return instruction(
        DLMM,
        data,
        keys,
        10,
        lambda i: i == 0
        or (i == 1 and a.bitmap_extension is not None)
        or 2 <= i <= 5
        or i == 8
        or i >= 16,
    )


def build_whirlpool_swap_v2_with_hooks(a, args, a_to_b, hook_a=(), hook_b=()):
    """Low-level swap with resolved Hook metas; cached routes still fail closed.

    Resolve each side for its actual source/destination before calling. For
    exact-out/output transfers, amount-dependent metadata needs a full resolver.
    """
    base = build_whirlpool_swap_v2(a, args, a_to_b)
    slices = []
    extras = []
    for kind, metas in ((0, hook_a), (1, hook_b), (6, base.accounts[15:])):
        if len(metas) > 255:
            raise ValueError('Whirlpool remaining slice exceeds u8')
        if metas:
            slices.append(bytes([kind, len(metas)]))
            extras.extend(metas)
    info = bytes([1]) + struct.pack('<I', len(slices)) + b''.join(slices) if slices else bytes([0])
    return Instruction(WHIRLPOOL, bytes(base.data[:42]) + info, list(base.accounts[:15]) + extras)
