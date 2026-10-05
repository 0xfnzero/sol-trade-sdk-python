"""CPMM creator fee parity with Rust 5.0.7. Account decoders take full Anchor bytes."""

from dataclasses import dataclass
import struct
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from .raydium_cpmm_builder import RAYDIUM_CPMM_PROGRAM_ID as PROGRAM, AUTHORITY
from .common import get_associated_token_address, SYSTEM_PROGRAM, TOKEN_PROGRAM, TOKEN_PROGRAM_2022

ATA = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
CONFIG_DISC = bytes([218, 244, 33, 104, 203, 203, 43, 111])
SHARE_DISC = bytes([30, 235, 98, 252, 26, 197, 66, 86])
POOL_DISC = bytes([247, 237, 227, 245, 215, 195, 222, 70])


def _bytes(data, size, disc):
    if len(data) < size or data[:8] != disc:
        raise ValueError("Invalid CPMM account layout/discriminator")
    return bytes(data)


def _u64(n):
    if type(n) is not int or not 0 <= n < 2**64:
        raise ValueError("Value outside u64")


def _rate(n):
    _u64(n)
    if n > 1_000_000:
        raise ValueError("Creator fee share rate exceeds 1,000,000")


@dataclass(frozen=True)
class CpmmAmmConfig:
    bump: int
    disable_create_pool: bool
    index: int
    trade_fee_rate: int
    protocol_fee_rate: int
    fund_fee_rate: int
    create_pool_fee: int
    protocol_owner: Pubkey
    fund_owner: Pubkey
    creator_fee_rate: int
    creator_fee_share_rate: int
    padding: tuple


def decode_cpmm_amm_config(data):
    b = _bytes(data, 236, CONFIG_DISC)
    if b[9] > 1:
        raise ValueError("Invalid config bool")
    u = lambda o: struct.unpack_from("<Q", b, o)[0]
    return CpmmAmmConfig(
        b[8],
        bool(b[9]),
        struct.unpack_from("<H", b, 10)[0],
        u(12),
        u(20),
        u(28),
        u(36),
        Pubkey.from_bytes(b[44:76]),
        Pubkey.from_bytes(b[76:108]),
        u(108),
        u(116),
        tuple(u(124 + i * 8) for i in range(14)),
    )


@dataclass(frozen=True)
class CpmmCreatorFeeShare:
    bump: int
    creator: Pubkey
    amm_config: Pubkey
    share_rate: int
    padding: tuple


def decode_cpmm_creator_fee_share(data):
    b = _bytes(data, 145, SHARE_DISC)
    return CpmmCreatorFeeShare(
        b[8],
        Pubkey.from_bytes(b[9:41]),
        Pubkey.from_bytes(b[41:73]),
        struct.unpack_from("<Q", b, 73)[0],
        tuple(struct.unpack_from("<Q", b, 81 + i * 8)[0] for i in range(8)),
    )


@dataclass(frozen=True)
class CpmmCollectionPool:
    amm_config: Pubkey
    pool_creator: Pubkey
    token0_vault: Pubkey
    token1_vault: Pubkey
    token0_mint: Pubkey
    token1_mint: Pubkey
    token0_program: Pubkey
    token1_program: Pubkey
    creator_fees_token0: int
    creator_fees_token1: int
    protocol_fees_token0: int
    protocol_fees_token1: int


def decode_cpmm_collection_pool(data):
    b = _bytes(data, 637, POOL_DISC)
    if b[390] > 1:
        raise ValueError("Invalid pool bool")
    pk = lambda i: Pubkey.from_bytes(b[8 + i * 32 : 40 + i * 32])
    return CpmmCollectionPool(
        *(pk(i) for i in [0, 1, 2, 3, 5, 6, 7, 8]),
        *struct.unpack_from("<QQ", b, 397),
        *struct.unpack_from("<QQ", b, 341),
    )


def get_creator_fee_share_pda(creator, config):
    return Pubkey.find_program_address(
        [b"creator_fee_share", bytes(creator), bytes(config)], PROGRAM
    )[0]


def resolve_creator_fee_share_rate(config, creator, address, share):
    # share is None or an object with owner/data/lamports. Cache closure uses None.
    n = config.creator_fee_share_rate
    if share is not None and share.lamports != 0 and share.owner == PROGRAM and share.data:
        s = decode_cpmm_creator_fee_share(share.data)
        if s.creator != creator or s.amm_config != address:
            raise ValueError("CreatorFeeShare creator/config mismatch")
        n = s.share_rate
    _rate(n)
    return n


async def fetch_creator_fee_share_rate(rpc, creator, config):
    result = await rpc.get_multiple_accounts(
        [config, get_creator_fee_share_pda(creator, config)], commitment="confirmed"
    )
    if len(result.value) != 2:
        raise ValueError("Incomplete fee-share snapshot")
    a = result.value[0]
    if a is None or a.owner != PROGRAM or a.lamports == 0:
        raise ValueError("Missing/invalid CPMM config")
    return resolve_creator_fee_share_rate(
        decode_cpmm_amm_config(a.data), creator, config, result.value[1]
    )


def split_creator_fee(gross, share_rate):
    _u64(gross)
    _rate(share_rate)
    protocol = gross * share_rate // 1_000_000
    return gross - protocol, protocol


def estimate_creator_fee_payout(pool, share_rate):
    return (
        split_creator_fee(pool.creator_fees_token0, share_rate)[0],
        split_creator_fee(pool.creator_fees_token1, share_rate)[0],
    )


def _build(address, pool, payer=None):
    m = lambda key, w=False, s=False: AccountMeta(key, s, w)
    c = pool.pool_creator
    keys = (
        [m(payer, True, True), m(c), m(AUTHORITY), m(address, True)]
        if payer is not None
        else [m(c, True, True), m(AUTHORITY), m(address, True), m(pool.amm_config)]
    )
    keys += [
        m(pool.token0_vault, True),
        m(pool.token1_vault, True),
        m(pool.token0_mint),
        m(pool.token1_mint),
        m(get_associated_token_address(c, pool.token0_mint, pool.token0_program), True),
        m(get_associated_token_address(c, pool.token1_mint, pool.token1_program), True),
        m(pool.token0_program),
        m(pool.token1_program),
        m(ATA),
        m(SYSTEM_PROGRAM),
    ]
    if payer is not None:
        keys.append(m(pool.amm_config))
    keys.append(m(get_creator_fee_share_pda(c, pool.amm_config)))
    return Instruction(
        PROGRAM,
        bytes(
            [202, 202, 34, 83, 226, 122, 145, 229]
            if payer is not None
            else [20, 22, 86, 123, 198, 28, 219, 132]
        ),
        keys,
    )


def collect_creator_fee(address, pool):
    return _build(address, pool)


def collect_creator_fee_permissionless(payer, address, pool):
    return _build(address, pool, payer)


def prepare_cpmm_creator_fee_collection(snapshot, address, context, payer=None):
    from types import SimpleNamespace

    pool = decode_cpmm_collection_pool(snapshot.get(address, context, PROGRAM).data)
    if any(
        p not in (TOKEN_PROGRAM, TOKEN_PROGRAM_2022)
        for p in (pool.token0_program, pool.token1_program)
    ):
        raise ValueError("Unsupported CPMM token program")
    if (
        Pubkey.default() in (pool.token0_mint, pool.token1_mint)
        or pool.token0_mint == pool.token1_mint
    ):
        raise ValueError("Invalid mint pair")
    if pool.creator_fees_token0 == pool.creator_fees_token1 == 0:
        raise ValueError("No accrued CPMM creator fees")
    config = decode_cpmm_amm_config(snapshot.get(pool.amm_config, context, PROGRAM).data)
    share_pda = get_creator_fee_share_pda(pool.pool_creator, pool.amm_config)
    observation = snapshot.get_observation(share_pda, context)
    rate = resolve_creator_fee_share_rate(
        config,
        pool.pool_creator,
        pool.amm_config,
        (
            None
            if observation is None
            else SimpleNamespace(owner=observation.owner, data=observation.data, lamports=1)
        ),
    )
    payout0, protocol0 = split_creator_fee(pool.creator_fees_token0, rate)
    payout1, protocol1 = split_creator_fee(pool.creator_fees_token1, rate)
    _u64(pool.protocol_fees_token0 + protocol0)
    _u64(pool.protocol_fees_token1 + protocol1)
    versions = tuple(
        (
            key,
            snapshot.get_observation(key, context).slot,
            snapshot.get_observation(key, context).write_version,
        )
        for key in (address, pool.amm_config, share_pda)
    )
    snapshot.assert_usable()
    return SimpleNamespace(
        pool=address,
        creator=pool.pool_creator,
        amm_config=pool.amm_config,
        account_versions=versions,
        instruction=_build(address, pool, payer),
        snapshot_slot=context.slot,
        creator_fee_share=share_pda,
        share_rate=rate,
        creator_payout_token0=payout0,
        creator_payout_token1=payout1,
        protocol_share_token0=protocol0,
        protocol_share_token1=protocol1,
    )


def validate_cpmm_creator_fee_collection(snapshot, prepared, context, payer=None):
    for name in (
        "snapshot_slot",
        "share_rate",
        "creator_payout_token0",
        "creator_payout_token1",
        "protocol_share_token0",
        "protocol_share_token1",
    ):
        _u64(getattr(prepared, name))
    if context.slot < prepared.snapshot_slot:
        raise ValueError("Collection read context moved backwards")
    for key, slot, version in prepared.account_versions:
        if slot > prepared.snapshot_slot:
            raise ValueError("Prepared snapshot precedes observations")
        a = snapshot.get_observation(key, context)
        if (a.slot, a.write_version) != (slot, version):
            raise ValueError("Creator-fee preparation changed; reprepare")
    current = prepare_cpmm_creator_fee_collection(snapshot, prepared.pool, context, payer)
    current.snapshot_slot = prepared.snapshot_slot
    if vars(current) != vars(prepared):
        raise ValueError("CPMM creator-fee preparation changed; reprepare")
