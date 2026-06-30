from solders.pubkey import Pubkey

from src.instruction.pumpswap_builder import (
    BUY_DISCRIMINATOR,
    BUY_EXACT_QUOTE_IN_DISCRIMINATOR,
    FEE_CONFIG,
    TOKEN_PROGRAM,
    WSOL_TOKEN_ACCOUNT,
    BuildBuyParams,
    BuildSellParams,
    PumpSwapFeeBasisPoints,
    PumpSwapPool,
    PumpSwapParams,
    build_buy_instructions,
    build_sell_instructions,
    compute_pumpswap_fee_basis_points,
    decode_fee_config,
    decode_mint_supply,
    get_associated_token_address,
    get_coin_creator_vault_ata,
    get_coin_creator_vault_authority,
    get_pump_pool_authority_pda,
    get_pool_v2_pda,
    params_from_pool_address,
)


def params(**overrides) -> PumpSwapParams:
    data = dict(
        pool=Pubkey.new_unique(),
        base_mint=Pubkey.new_unique(),
        quote_mint=WSOL_TOKEN_ACCOUNT,
        pool_base_token_account=Pubkey.new_unique(),
        pool_quote_token_account=Pubkey.new_unique(),
        pool_base_token_reserves=1_000_000_000_000,
        pool_quote_token_reserves=4_500_000_000,
        coin_creator_vault_ata=Pubkey.new_unique(),
        coin_creator_vault_authority=Pubkey.new_unique(),
        base_token_program=TOKEN_PROGRAM,
        quote_token_program=TOKEN_PROGRAM,
        is_mayhem_mode=False,
        is_cashback_coin=False,
        coin_creator=Pubkey.new_unique(),
        fee_basis_points=PumpSwapFeeBasisPoints(20, 5, 75),
    )
    data.update(overrides)
    return PumpSwapParams(**data)


def build_ix(protocol_params: PumpSwapParams):
    return build_buy_instructions(
        BuildBuyParams(
            payer=Pubkey.new_unique(),
            input_amount=1_000_000,
            slippage_basis_points=300,
            protocol_params=protocol_params,
            create_input_mint_ata=False,
            create_output_mint_ata=False,
            use_exact_quote_amount=True,
        )
    )[-1]


def test_pumpswap_buy_uses_fee_basis_points_from_params():
    current = build_ix(params(fee_basis_points=PumpSwapFeeBasisPoints(20, 5, 75)))
    legacy = build_ix(params(fee_basis_points=PumpSwapFeeBasisPoints(25, 5, 5)))

    assert bytes(current.data)[:8] == BUY_EXACT_QUOTE_IN_DISCRIMINATOR
    assert len(bytes(current.data)) == 25
    assert bytes(current.data)[16:24] != bytes(legacy.data)[16:24]


def test_pumpswap_fixed_output_buy_uses_buy_discriminator():
    ix = build_buy_instructions(
        BuildBuyParams(
            payer=Pubkey.new_unique(),
            input_amount=1_000_000,
            fixed_output_amount=123,
            slippage_basis_points=300,
            protocol_params=params(),
            create_input_mint_ata=False,
            create_output_mint_ata=False,
            use_exact_quote_amount=True,
        )
    )[-1]

    data = bytes(ix.data)
    assert data[:8] == BUY_DISCRIMINATOR
    assert len(data) == 25
    assert int.from_bytes(data[8:16], "little") == 123
    assert data[24] == 0


def test_pumpswap_reverse_sell_uses_buy_two_arg_data():
    payer = Pubkey.new_unique()
    quote_mint = Pubkey.new_unique()
    ixs = build_sell_instructions(
        BuildSellParams(
            payer=payer,
            input_amount=1_000_000,
            slippage_basis_points=300,
            protocol_params=params(
                base_mint=WSOL_TOKEN_ACCOUNT,
                quote_mint=quote_mint,
            ),
            create_output_mint_ata=False,
            close_input_mint_ata=True,
        )
    )

    ix = ixs[-2]
    data = bytes(ix.data)
    assert data[:8] == BUY_DISCRIMINATOR
    assert len(data) == 24

    close_ix = ixs[-1]
    assert close_ix.accounts[0].pubkey == get_associated_token_address(payer, quote_mint, TOKEN_PROGRAM)
    assert close_ix.program_id == TOKEN_PROGRAM


def test_pumpswap_omits_pool_v2_when_known_coin_creator_is_default():
    base_mint = Pubkey.new_unique()
    ix = build_ix(params(base_mint=base_mint, coin_creator=Pubkey.default()))

    pool_v2 = get_pool_v2_pda(base_mint)
    assert pool_v2 not in [meta.pubkey for meta in ix.accounts]


def fee_config_bytes() -> bytes:
    data = bytearray()
    data.extend(bytes(8))  # discriminator
    data.extend(b"\x01")  # bump
    data.extend(bytes(Pubkey.new_unique()))  # admin
    data.extend((30).to_bytes(8, "little"))
    data.extend((7).to_bytes(8, "little"))
    data.extend((9).to_bytes(8, "little"))
    data.extend((2).to_bytes(4, "little"))
    data.extend((0).to_bytes(16, "little"))
    data.extend((25).to_bytes(8, "little"))
    data.extend((5).to_bytes(8, "little"))
    data.extend((5).to_bytes(8, "little"))
    data.extend((1_000).to_bytes(16, "little"))
    data.extend((20).to_bytes(8, "little"))
    data.extend((5).to_bytes(8, "little"))
    data.extend((75).to_bytes(8, "little"))
    data.extend((0).to_bytes(4, "little"))  # stable tiers
    return bytes(data)


def mint_bytes(supply: int) -> bytes:
    data = bytearray(82)
    data[36:44] = supply.to_bytes(8, "little")
    return bytes(data)


def pool_bytes(pool: PumpSwapPool) -> bytes:
    data = bytearray(8)
    data.extend(bytes([pool.pool_bump]))
    data.extend(pool.index.to_bytes(2, "little"))
    data.extend(bytes(pool.creator))
    data.extend(bytes(pool.base_mint))
    data.extend(bytes(pool.quote_mint))
    data.extend(bytes(pool.lp_mint))
    data.extend(bytes(pool.pool_base_token_account))
    data.extend(bytes(pool.pool_quote_token_account))
    data.extend(pool.lp_supply.to_bytes(8, "little"))
    data.extend(bytes(pool.coin_creator))
    data.extend(bytes([1 if pool.is_mayhem_mode else 0]))
    data.extend(bytes([1 if pool.is_cashback_coin else 0]))
    data.extend(bytes(7))
    return bytes(data)


class FakePumpSwapFetcher:
    def __init__(self, accounts, balances):
        self.accounts = accounts
        self.balances = balances

    async def get_account_info(self, pubkey: Pubkey):
        return self.accounts.get(pubkey)

    async def get_token_account_balance(self, pubkey: Pubkey):
        return self.balances.get(pubkey)


class RpcValue:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeSolanaRpcFetcher(FakePumpSwapFetcher):
    async def get_account_info(self, pubkey: Pubkey):
        data = self.accounts.get(pubkey)
        return RpcValue(value=RpcValue(data=data)) if data is not None else RpcValue(value=None)

    async def get_token_account_balance(self, pubkey: Pubkey):
        balance = self.balances.get(pubkey)
        return (
            RpcValue(value=RpcValue(amount=str(balance)))
            if balance is not None
            else RpcValue(value=None)
        )


def test_decode_fee_config_and_compute_fee_tier():
    base_mint = Pubkey.new_unique()
    config = decode_fee_config(fee_config_bytes())

    assert config is not None
    fees = compute_pumpswap_fee_basis_points(
        config,
        get_pump_pool_authority_pda(base_mint),
        base_mint,
        10_000,
        1_000,
        1_000,
    )

    assert fees == PumpSwapFeeBasisPoints(20, 5, 75)


def test_decode_mint_supply():
    assert decode_mint_supply(mint_bytes(123_456)) == 123_456
    assert decode_mint_supply(bytes(10)) is None


async def test_params_from_pool_address_auto_discovers_fee_config():
    base_mint = Pubkey.new_unique()
    pool_address = Pubkey.new_unique()
    coin_creator = Pubkey.new_unique()
    pool = PumpSwapPool(
        pool_bump=1,
        index=0,
        creator=get_pump_pool_authority_pda(base_mint),
        base_mint=base_mint,
        quote_mint=WSOL_TOKEN_ACCOUNT,
        lp_mint=Pubkey.new_unique(),
        pool_base_token_account=get_associated_token_address(pool_address, base_mint, TOKEN_PROGRAM),
        pool_quote_token_account=get_associated_token_address(
            pool_address, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
        ),
        lp_supply=100,
        coin_creator=coin_creator,
        is_mayhem_mode=False,
        is_cashback_coin=True,
    )
    fetcher = FakePumpSwapFetcher(
        {
            pool_address: pool_bytes(pool),
            base_mint: mint_bytes(10_000),
            FEE_CONFIG: fee_config_bytes(),
        },
        {
            pool.pool_base_token_account: 1_000,
            pool.pool_quote_token_account: 1_000,
        },
    )

    built = await params_from_pool_address(fetcher, pool_address)

    assert built.fee_basis_points == PumpSwapFeeBasisPoints(20, 5, 75)
    assert built.base_mint_supply == 10_000
    assert built.pool_creator == pool.creator
    assert built.coin_creator == coin_creator
    assert built.coin_creator_vault_authority == get_coin_creator_vault_authority(coin_creator)
    assert built.coin_creator_vault_ata == get_coin_creator_vault_ata(coin_creator, WSOL_TOKEN_ACCOUNT)


async def test_params_from_pool_address_preserves_manual_fee_basis_points():
    base_mint = Pubkey.new_unique()
    pool_address = Pubkey.new_unique()
    pool = PumpSwapPool(
        pool_bump=1,
        index=0,
        creator=get_pump_pool_authority_pda(base_mint),
        base_mint=base_mint,
        quote_mint=WSOL_TOKEN_ACCOUNT,
        lp_mint=Pubkey.new_unique(),
        pool_base_token_account=get_associated_token_address(pool_address, base_mint, TOKEN_PROGRAM),
        pool_quote_token_account=get_associated_token_address(
            pool_address, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
        ),
        lp_supply=100,
        coin_creator=Pubkey.new_unique(),
        is_mayhem_mode=False,
        is_cashback_coin=False,
    )
    manual = PumpSwapFeeBasisPoints(99, 88, 77)
    fetcher = FakePumpSwapFetcher(
        {
            pool_address: pool_bytes(pool),
            base_mint: mint_bytes(10_000),
            FEE_CONFIG: fee_config_bytes(),
        },
        {
            pool.pool_base_token_account: 1_000,
            pool.pool_quote_token_account: 1_000,
        },
    )

    built = await params_from_pool_address(fetcher, pool_address, fee_basis_points=manual)

    assert built.fee_basis_points == manual


async def test_params_from_pool_address_accepts_solana_rpc_style_responses():
    base_mint = Pubkey.new_unique()
    pool_address = Pubkey.new_unique()
    pool = PumpSwapPool(
        pool_bump=1,
        index=0,
        creator=get_pump_pool_authority_pda(base_mint),
        base_mint=base_mint,
        quote_mint=WSOL_TOKEN_ACCOUNT,
        lp_mint=Pubkey.new_unique(),
        pool_base_token_account=get_associated_token_address(pool_address, base_mint, TOKEN_PROGRAM),
        pool_quote_token_account=get_associated_token_address(
            pool_address, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
        ),
        lp_supply=100,
        coin_creator=Pubkey.new_unique(),
        is_mayhem_mode=False,
        is_cashback_coin=False,
    )
    fetcher = FakeSolanaRpcFetcher(
        {
            pool_address: pool_bytes(pool),
            base_mint: mint_bytes(10_000),
            FEE_CONFIG: fee_config_bytes(),
        },
        {
            pool.pool_base_token_account: 1_000,
            pool.pool_quote_token_account: 1_000,
        },
    )

    built = await params_from_pool_address(fetcher, pool_address)

    assert built.fee_basis_points == PumpSwapFeeBasisPoints(20, 5, 75)
