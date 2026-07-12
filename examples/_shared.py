import json
import os
import time
from typing import Optional

import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from sol_trade_sdk import (
    TOKEN_PROGRAM,
    WSOL_TOKEN_ACCOUNT,
    AstralaneTransport,
    BondingCurveAccount,
    BonkParams,
    DexType,
    GasFeeStrategy,
    MeteoraDammV2Params,
    PumpFunParams,
    PumpSwapParams,
    RaydiumAmmV4Params,
    RaydiumCpmmParams,
    SwqosConfig,
    SwqosRegion,
    SwqosTransport,
    SwqosType,
    TradeBuyParams,
    TradeConfig,
    TradeResult,
    TradeSellParams,
    TradeTokenType,
    TradingClient,
)

RUN_LIVE = os.getenv("RUN_LIVE_EXAMPLES") == "1"
EXAMPLE_BLOCKHASH = str(Pubkey.from_bytes(bytes([99]) * 32))


def rpc_url() -> str:
    return os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")


def example_pubkey(seed: int) -> Pubkey:
    return Pubkey.from_bytes(bytes([seed]) * 32)


def default_swqos_configs() -> list[SwqosConfig]:
    configs = [SwqosConfig(type=SwqosType.DEFAULT, region=SwqosRegion.DEFAULT, api_key="")]

    if os.getenv("JITO_UUID"):
        configs.append(
            SwqosConfig(
                type=SwqosType.JITO, region=SwqosRegion.FRANKFURT, api_key=os.environ["JITO_UUID"]
            )
        )
    if os.getenv("BLOXROUTE_AUTH_TOKEN"):
        configs.append(
            SwqosConfig(
                type=SwqosType.BLOXROUTE,
                region=SwqosRegion.FRANKFURT,
                api_key=os.environ["BLOXROUTE_AUTH_TOKEN"],
            )
        )
    if os.getenv("ASTRALANE_API_KEY"):
        configs.append(
            SwqosConfig(
                type=SwqosType.ASTRALANE,
                region=SwqosRegion.FRANKFURT,
                api_key=os.environ["ASTRALANE_API_KEY"],
                transport=SwqosTransport.QUIC,
                astralane_transport=AstralaneTransport.QUIC,
                mev_protection=True,
            )
        )
    if os.getenv("HELIUS_API_KEY"):
        configs.append(
            SwqosConfig(
                type=SwqosType.HELIUS,
                region=SwqosRegion.DEFAULT,
                api_key=os.environ["HELIUS_API_KEY"],
                swqos_only=True,
            )
        )

    return configs


def low_latency_gas_strategy() -> GasFeeStrategy:
    strategy = GasFeeStrategy()
    strategy.set_global_fee_strategy(180_000, 160_000, 800_000, 600_000, 0.002, 0.0015)
    return strategy


def trade_config(**overrides) -> TradeConfig:
    builder = (
        TradeConfig.builder(rpc_url())
        .swqos_configs(overrides.pop("swqos_configs", default_swqos_configs()))
        .use_seed_optimize(overrides.pop("use_seed_optimize", True))
        .swqos_cores_from_end(overrides.pop("swqos_cores_from_end", False))
        .max_swqos_submit_concurrency(overrides.pop("max_swqos_submit_concurrency", 8))
        .log_enabled(overrides.pop("log_enabled", True))
    )
    return builder.build()


def create_example_client(**config_overrides) -> TradingClient:
    if RUN_LIVE:
        raise RuntimeError(
            "Protocol examples contain placeholder accounts and are dry-run only. "
            "Use low_latency_bot.py with real parser/streamer adapters before submitting."
        )
    return TradingClient(Keypair(), trade_config(**config_overrides))


def load_payer_from_env(name: str = "PRIVATE_KEY") -> Keypair:
    encoded = os.getenv(name, "").strip()
    if not encoded:
        raise RuntimeError(f"{name} is required for live trading")

    secret = bytearray()
    try:
        if encoded.startswith("["):
            values = json.loads(encoded)
            if (
                not isinstance(values, list)
                or len(values) != 64
                or any(
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 0
                    or value > 255
                    for value in values
                )
            ):
                raise ValueError("JSON private key must contain exactly 64 bytes")
            secret.extend(values)
        else:
            secret.extend(base58.b58decode(encoded))
        if len(secret) != 64:
            raise ValueError(f"decoded private key has {len(secret)} bytes, expected 64")
        return Keypair.from_bytes(bytes(secret))
    except Exception as exc:
        raise RuntimeError(f"Invalid {name}: {exc}") from exc
    finally:
        for index in range(len(secret)):
            secret[index] = 0


def create_live_client(**config_overrides) -> TradingClient:
    if not RUN_LIVE:
        raise RuntimeError("Set RUN_LIVE_EXAMPLES=1 only after all live adapters are configured")
    return TradingClient(load_payer_from_env(), trade_config(**config_overrides))


def is_event_fresh(received_at_ms: int, max_age_ms: int, now_ms: Optional[int] = None) -> bool:
    current = int(time.time() * 1000) if now_ms is None else now_ms
    return max_age_ms > 0 and received_at_ms <= current and current - received_at_ms <= max_age_ms


def matches_target(actual: Pubkey, expected: Optional[Pubkey]) -> bool:
    return expected is None or actual == expected


def checked_position_delta(before: int, after: int) -> int:
    if after <= before:
        raise ValueError(
            f"Buy produced no positive token balance delta: before={before} after={after}"
        )
    return after - before


def validate_trade_intent(
    input_amount: int, slippage_basis_points: int, fixed_output: Optional[int] = None
) -> None:
    if not isinstance(input_amount, int) or isinstance(input_amount, bool) or input_amount <= 0:
        raise ValueError("input amount must be a positive integer")
    if (
        not isinstance(slippage_basis_points, int)
        or isinstance(slippage_basis_points, bool)
        or slippage_basis_points < 0
        or slippage_basis_points >= 10_000
    ):
        raise ValueError("slippage must be an integer from 0 through 9999 basis points")
    if fixed_output is not None and (
        not isinstance(fixed_output, int) or isinstance(fixed_output, bool) or fixed_output <= 0
    ):
        raise ValueError("fixed output amount must be a positive integer when provided")


def example_bonding_curve() -> BondingCurveAccount:
    return BondingCurveAccount(
        discriminator=0,
        account=example_pubkey(11),
        virtual_token_reserves=1_000_000_000,
        virtual_sol_reserves=30_000_000_000,
        real_token_reserves=800_000_000,
        real_sol_reserves=24_000_000_000,
        token_total_supply=1_000_000_000,
        complete=False,
        creator=example_pubkey(12),
        is_mayhem_mode=False,
        is_cashback_coin=True,
    )


def pump_fun_params() -> PumpFunParams:
    return PumpFunParams(
        bonding_curve=example_bonding_curve(),
        associated_bonding_curve=example_pubkey(13),
        creator_vault=example_pubkey(14),
        token_program=TOKEN_PROGRAM,
        fee_recipient=example_pubkey(15),
        quote_mint=WSOL_TOKEN_ACCOUNT,
    )


def pump_swap_params() -> PumpSwapParams:
    return PumpSwapParams(
        pool=example_pubkey(21),
        base_mint=example_pubkey(22),
        quote_mint=WSOL_TOKEN_ACCOUNT,
        pool_base_token_account=example_pubkey(23),
        pool_quote_token_account=example_pubkey(24),
        pool_base_token_reserves=2_000_000_000,
        pool_quote_token_reserves=50_000_000_000,
        coin_creator_vault_ata=example_pubkey(25),
        coin_creator_vault_authority=example_pubkey(26),
        base_token_program=TOKEN_PROGRAM,
        quote_token_program=TOKEN_PROGRAM,
        is_mayhem_mode=False,
        is_cashback_coin=True,
    )


def bonk_params() -> BonkParams:
    return BonkParams(
        virtual_base=2_000_000_000,
        virtual_quote=50_000_000_000,
        real_base=1_700_000_000,
        real_quote=40_000_000_000,
        pool_state=example_pubkey(31),
        base_vault=example_pubkey(32),
        quote_vault=example_pubkey(33),
        mint_token_program=TOKEN_PROGRAM,
        platform_config=example_pubkey(34),
        platform_associated_account=example_pubkey(35),
        creator_associated_account=example_pubkey(36),
        global_config=example_pubkey(37),
    )


def raydium_cpmm_params() -> RaydiumCpmmParams:
    return RaydiumCpmmParams(
        pool_state=example_pubkey(41),
        amm_config=example_pubkey(42),
        base_mint=example_pubkey(43),
        quote_mint=WSOL_TOKEN_ACCOUNT,
        base_reserve=2_000_000_000,
        quote_reserve=50_000_000_000,
        base_vault=example_pubkey(44),
        quote_vault=example_pubkey(45),
        base_token_program=TOKEN_PROGRAM,
        quote_token_program=TOKEN_PROGRAM,
        observation_state=example_pubkey(46),
    )


def raydium_amm_v4_params() -> RaydiumAmmV4Params:
    return RaydiumAmmV4Params(
        amm=example_pubkey(51),
        coin_mint=example_pubkey(52),
        pc_mint=WSOL_TOKEN_ACCOUNT,
        token_coin=example_pubkey(53),
        token_pc=example_pubkey(54),
        amm_open_orders=example_pubkey(55),
        amm_target_orders=example_pubkey(56),
        serum_program=example_pubkey(57),
        serum_market=example_pubkey(58),
        serum_bids=example_pubkey(59),
        serum_asks=example_pubkey(60),
        serum_event_queue=example_pubkey(61),
        serum_coin_vault_account=example_pubkey(62),
        serum_pc_vault_account=example_pubkey(63),
        serum_vault_signer=example_pubkey(64),
        coin_reserve=2_000_000_000,
        pc_reserve=50_000_000_000,
    )


def meteora_damm_v2_params() -> MeteoraDammV2Params:
    return MeteoraDammV2Params(
        pool=example_pubkey(71),
        token_a_vault=example_pubkey(72),
        token_b_vault=example_pubkey(73),
        token_a_mint=example_pubkey(74),
        token_b_mint=WSOL_TOKEN_ACCOUNT,
        token_a_program=TOKEN_PROGRAM,
        token_b_program=TOKEN_PROGRAM,
    )


def protocol_params(dex_type: DexType):
    if dex_type == DexType.PUMPFUN:
        return pump_fun_params()
    if dex_type == DexType.PUMPSWAP:
        return pump_swap_params()
    if dex_type == DexType.BONK:
        return bonk_params()
    if dex_type == DexType.RAYDIUM_CPMM:
        return raydium_cpmm_params()
    if dex_type == DexType.RAYDIUM_AMM_V4:
        return raydium_amm_v4_params()
    if dex_type == DexType.METEORA_DAMM_V2:
        return meteora_damm_v2_params()
    raise ValueError(f"unsupported dex type: {dex_type}")


def default_trade_mint(dex_type: DexType) -> Pubkey:
    if dex_type == DexType.PUMPSWAP:
        return pump_swap_params().base_mint
    if dex_type == DexType.RAYDIUM_CPMM:
        return raydium_cpmm_params().base_mint
    if dex_type == DexType.RAYDIUM_AMM_V4:
        return raydium_amm_v4_params().coin_mint
    if dex_type == DexType.METEORA_DAMM_V2:
        return meteora_damm_v2_params().token_a_mint
    return example_pubkey(91)


def example_buy_params(dex_type: DexType, mint: Optional[Pubkey] = None) -> TradeBuyParams:
    params = TradeBuyParams(
        dex_type=dex_type,
        input_token_type=TradeTokenType.USD1 if dex_type == DexType.BONK else TradeTokenType.WSOL,
        mint=mint or default_trade_mint(dex_type),
        input_token_amount=100_000,
        extension_params=protocol_params(dex_type),
        slippage_basis_points=300,
        recent_blockhash=EXAMPLE_BLOCKHASH,
        wait_tx_confirmed=True,
        create_input_token_ata=True,
        close_input_token_ata=True,
        create_mint_ata=True,
        gas_fee_strategy=low_latency_gas_strategy(),
        grpc_recv_us=0,
    )
    return params


def example_sell_params(dex_type: DexType, mint: Optional[Pubkey] = None) -> TradeSellParams:
    params = TradeSellParams(
        dex_type=dex_type,
        output_token_type=TradeTokenType.USD1 if dex_type == DexType.BONK else TradeTokenType.WSOL,
        mint=mint or default_trade_mint(dex_type),
        input_token_amount=50_000,
        extension_params=protocol_params(dex_type),
        slippage_basis_points=300,
        recent_blockhash=EXAMPLE_BLOCKHASH,
        with_tip=True,
        wait_tx_confirmed=True,
        create_output_token_ata=True,
        close_output_token_ata=True,
        close_mint_token_ata=False,
        gas_fee_strategy=low_latency_gas_strategy(),
        grpc_recv_us=0,
    )
    return params


def describe_dry_run(name: str) -> None:
    print(f"{name} prepared with current SDK types.")
    print(
        "Placeholder protocol accounts are never submitted. Use low_latency_bot.py for the guarded live workflow."
    )


def log_result(label: str, result: TradeResult) -> None:
    print(f"{label}: success={result.success} signatures={','.join(result.signatures)}")
    if result.error:
        print(f"{label} error: {result.error}")
