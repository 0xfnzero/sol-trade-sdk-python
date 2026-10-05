"""
Trading factory and executor.
Based on sol-trade-sdk Rust implementation.

PumpFun / PumpSwap 指令统一由 `instruction.pumpfun_builder` / `instruction.pumpswap_builder`
构建（与链上程序及 Rust SDK 对齐）。
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from solders.pubkey import Pubkey

from .. import _parser_exact_integer

from .params import (
    DexType,
    TradeType,
    PumpFunParams,
    PumpSwapParams,
    BonkParams,
    RaydiumCpmmParams,
    RaydiumAmmV4Params,
    MeteoraDammV2Params,
)


def _to_pubkey(value: Any) -> Pubkey:
    """将 `Pubkey` / 32 字节 / base58 字符串 转为 `Pubkey`。"""
    if isinstance(value, Pubkey):
        return value
    if isinstance(value, (bytes, bytearray)):
        b = bytes(value)
        if len(b) != 32:
            raise ValueError("Pubkey bytes 长度必须为 32")
        return Pubkey.from_bytes(b)
    if isinstance(value, str):
        return Pubkey.from_string(value)
    raise TypeError(f"无法解析为 Pubkey: {type(value)!r}")


def _pumpswap_fee_basis_points(params: Dict[str, Any], fee_cls: Any) -> Any:
    fee = params.get("fee_basis_points")
    if fee is not None:
        get_value = fee.get if isinstance(fee, dict) else lambda key, default=0: getattr(fee, key, default)
        return fee_cls(
            int(get_value("lp_fee_basis_points", 0)),
            int(get_value("protocol_fee_basis_points", 0)),
            int(get_value("coin_creator_fee_basis_points", 0)),
        )
    if (
        "lp_fee_basis_points" in params
        or "protocol_fee_basis_points" in params
        or "coin_creator_fee_basis_points" in params
    ):
        return fee_cls(
            int(params.get("lp_fee_basis_points", 0)),
            int(params.get("protocol_fee_basis_points", 0)),
            int(params.get("coin_creator_fee_basis_points", 0)),
        )
    return None


def _pumpfun_bonding_to_builder_params(
    bonding_curve: Any,
    creator_vault: Any,
    associated_bonding_curve: Any,
    token_program: Any,
    close_token_account: bool,
    fee_recipient: Any = None,
    quote_mint: Any = None,
    observed_trade_creator: Any = None,
    fee_sharing_creator_vault_if_active: Any = None,
):
    """将 `BondingCurveAccount` 等运行时对象映射为 `pumpfun_builder.PumpFunParams`。"""
    from .. import _parser_exact_integer
    from ..instruction.pumpfun_builder import (
        PumpFunParams as PfbParams,
        TOKEN_PROGRAM as SPL_TOKEN,
    )

    acct = getattr(bonding_curve, "account", None)
    bonding_pk: Optional[Pubkey] = None
    if acct is not None:
        pk = _to_pubkey(acct)
        if pk != Pubkey.default():
            bonding_pk = pk

    assoc = _to_pubkey(associated_bonding_curve)
    assoc_opt = None if assoc == Pubkey.default() else assoc

    tp = _to_pubkey(token_program)
    if tp == Pubkey.default():
        tp = SPL_TOKEN

    creator_raw = getattr(bonding_curve, "creator", None)
    creator_pk = _to_pubkey(creator_raw) if creator_raw is not None else Pubkey.default()

    return PfbParams(
        bonding_curve_account=bonding_pk,
        virtual_token_reserves=_parser_exact_integer(getattr(bonding_curve, "virtual_token_reserves", 0), "virtual_token_reserves"),
        virtual_sol_reserves=_parser_exact_integer(getattr(bonding_curve, "virtual_sol_reserves", 0), "virtual_sol_reserves"),
        real_token_reserves=_parser_exact_integer(getattr(bonding_curve, "real_token_reserves", 0), "real_token_reserves"),
        real_sol_reserves=_parser_exact_integer(getattr(bonding_curve, "real_sol_reserves", 0), "real_sol_reserves"),
        token_total_supply=_parser_exact_integer(getattr(bonding_curve, "token_total_supply", 0), "token_total_supply"),
        complete=bool(getattr(bonding_curve, "complete", False)),
        creator=creator_pk,
        is_mayhem_mode=bool(getattr(bonding_curve, "is_mayhem_mode", False)),
        is_cashback_coin=bool(getattr(bonding_curve, "is_cashback_coin", False)),
        associated_bonding_curve=assoc_opt,
        creator_vault=_to_pubkey(creator_vault),
        token_program=tp,
        close_token_account_when_sell=close_token_account,
        fee_recipient=_to_pubkey(fee_recipient) if fee_recipient is not None else Pubkey.default(),
        quote_mint=_to_pubkey(quote_mint) if quote_mint is not None else Pubkey.default(),
        curve_quote_mint=_to_pubkey(getattr(bonding_curve, "quote_mint", bytes(32))),
        observed_trade_creator=(
            _to_pubkey(observed_trade_creator) if observed_trade_creator is not None else None
        ),
        fee_sharing_creator_vault_if_active=(
            _to_pubkey(fee_sharing_creator_vault_if_active)
            if fee_sharing_creator_vault_if_active is not None
            else None
        ),
    )


class TradeExecutor(ABC):
    """Abstract base class for trade executors"""

    @abstractmethod
    async def execute_buy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy trade"""
        pass

    @abstractmethod
    async def execute_sell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell trade"""
        pass


class PumpFunExecutor(TradeExecutor):
    """PumpFun trade executor（`pumpfun_builder`）"""

    async def build_buy_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on PumpFun"""
        from ..instruction.pumpfun_builder import build_buy_instructions as pfb_buy, _effective_quote_mint

        pfb_params = _pumpfun_bonding_to_builder_params(
            bonding_curve=params["bonding_curve"],
            creator_vault=params["creator_vault"],
            associated_bonding_curve=params["associated_bonding_curve"],
            token_program=params.get("token_program", bytes(32)),
            close_token_account=False,
            fee_recipient=params.get("fee_recipient"),
            quote_mint=params.get("quote_mint"),
            observed_trade_creator=params.get("observed_trade_creator"),
            fee_sharing_creator_vault_if_active=params.get("fee_sharing_creator_vault_if_active"),
        )
        instructions = pfb_buy(
            _to_pubkey(params["payer"]),
            _to_pubkey(params["output_mint"]),
            _parser_exact_integer(params["input_amount"], "input_amount"),
            pfb_params,
            slippage_bps=int(params.get("slippage_basis_points", 100)),
            create_output_ata=bool(params.get("create_output_mint_ata", True)),
            create_input_ata=bool(params.get("create_input_mint_ata", False)),
            close_input_ata=bool(params.get("close_input_mint_ata", False)),
            fixed_output_amount=params.get("fixed_output_amount"),
            use_exact_sol_amount=bool(params.get("use_exact_sol_amount", True)),
            input_mint=_to_pubkey(params.get("input_mint", _effective_quote_mint(pfb_params))),
        )

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "PumpFun",
            "type": "buy",
        }

    async def build_sell_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on PumpFun"""
        from ..instruction.pumpfun_builder import build_sell_instructions as pfb_sell, _effective_quote_mint

        close_tok = bool(params.get("close_token_account", False))
        pfb_params = _pumpfun_bonding_to_builder_params(
            bonding_curve=params["bonding_curve"],
            creator_vault=params["creator_vault"],
            associated_bonding_curve=params["associated_bonding_curve"],
            token_program=params.get("token_program", bytes(32)),
            close_token_account=close_tok,
            fee_recipient=params.get("fee_recipient"),
            quote_mint=params.get("quote_mint"),
            observed_trade_creator=params.get("observed_trade_creator"),
            fee_sharing_creator_vault_if_active=params.get("fee_sharing_creator_vault_if_active"),
        )
        instructions = pfb_sell(
            _to_pubkey(params["payer"]),
            _to_pubkey(params["input_mint"]),
            _parser_exact_integer(params["token_amount"], "token_amount"),
            pfb_params,
            slippage_bps=int(params.get("slippage_basis_points", 100)),
            create_output_ata=bool(params.get("create_output_mint_ata", False)),
            close_output_ata=bool(params.get("close_output_mint_ata", False)),
            close_input_ata=close_tok,
            fixed_output_amount=params.get("fixed_output_amount"),
            output_mint=_to_pubkey(params.get("output_mint", _effective_quote_mint(pfb_params))),
        )

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "PumpFun",
            "type": "sell",
        }


    async def execute_buy(self, params):
        return await UnifiedTradeExecutor(DexType.PUMP_FUN).execute_buy(params)

    async def execute_sell(self, params):
        return await UnifiedTradeExecutor(DexType.PUMP_FUN).execute_sell(params)


class PumpSwapExecutor(TradeExecutor):
    """PumpSwap trade executor（`pumpswap_builder`）"""

    async def build_buy_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on PumpSwap"""
        from ..instruction.pumpswap_builder import (
            build_buy_instructions as psb_buy,
            BuildBuyParams,
            PumpSwapFeeBasisPoints as PsbFeeBasisPoints,
            PumpSwapParams as PsbParams,
            TOKEN_PROGRAM as SPL_TOKEN,
        )

        btp = _to_pubkey(params.get("base_token_program", bytes(32)))
        qtp = _to_pubkey(params.get("quote_token_program", bytes(32)))
        if btp == Pubkey.default():
            btp = SPL_TOKEN
        if qtp == Pubkey.default():
            qtp = SPL_TOKEN

        protocol = PsbParams(
            pool=_to_pubkey(params["pool"]),
            base_mint=_to_pubkey(params["base_mint"]),
            quote_mint=_to_pubkey(params["quote_mint"]),
            pool_base_token_account=_to_pubkey(params["pool_base_token_account"]),
            pool_quote_token_account=_to_pubkey(params["pool_quote_token_account"]),
            pool_base_token_reserves=int(params["pool_base_token_reserves"]),
            pool_quote_token_reserves=int(params["pool_quote_token_reserves"]),
            virtual_quote_reserves=int(params.get("virtual_quote_reserves", 0)),
            coin_creator_vault_ata=_to_pubkey(params["coin_creator_vault_ata"]),
            coin_creator_vault_authority=_to_pubkey(params["coin_creator_vault_authority"]),
            base_token_program=btp,
            quote_token_program=qtp,
            is_mayhem_mode=bool(params.get("is_mayhem_mode", False)),
            is_cashback_coin=bool(params.get("is_cashback_coin", False)),
            coin_creator=_to_pubkey(params.get("coin_creator", bytes(32))),
            cashback_fee_basis_points=int(params.get("cashback_fee_basis_points", 0)),
            fee_basis_points=_pumpswap_fee_basis_points(params, PsbFeeBasisPoints),
            pool_creator=_to_pubkey(params.get("pool_creator", bytes(32))),
            base_mint_supply=params.get("base_mint_supply"),
        )
        builder_params = BuildBuyParams(
            payer=_to_pubkey(params["payer"]),
            input_amount=int(params["input_amount"]),
            slippage_basis_points=int(params.get("slippage_basis_points", 100)),
            protocol_params=protocol,
            create_input_mint_ata=bool(params.get("create_input_mint_ata", True)),
            close_input_mint_ata=bool(params.get("close_input_mint_ata", False)),
            create_output_mint_ata=bool(params.get("create_output_mint_ata", True)),
            use_exact_quote_amount=bool(params.get("use_exact_quote_amount", True)),
            fixed_output_amount=params.get("fixed_output_amount"),
        )
        instructions = psb_buy(builder_params)

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "PumpSwap",
            "type": "buy",
        }

    async def build_sell_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on PumpSwap"""
        from ..instruction.pumpswap_builder import (
            build_sell_instructions as psb_sell,
            BuildSellParams,
            PumpSwapFeeBasisPoints as PsbFeeBasisPoints,
            PumpSwapParams as PsbParams,
            TOKEN_PROGRAM as SPL_TOKEN,
        )

        btp = _to_pubkey(params.get("base_token_program", bytes(32)))
        qtp = _to_pubkey(params.get("quote_token_program", bytes(32)))
        if btp == Pubkey.default():
            btp = SPL_TOKEN
        if qtp == Pubkey.default():
            qtp = SPL_TOKEN

        protocol = PsbParams(
            pool=_to_pubkey(params["pool"]),
            base_mint=_to_pubkey(params["base_mint"]),
            quote_mint=_to_pubkey(params["quote_mint"]),
            pool_base_token_account=_to_pubkey(params["pool_base_token_account"]),
            pool_quote_token_account=_to_pubkey(params["pool_quote_token_account"]),
            pool_base_token_reserves=int(params["pool_base_token_reserves"]),
            pool_quote_token_reserves=int(params["pool_quote_token_reserves"]),
            virtual_quote_reserves=int(params.get("virtual_quote_reserves", 0)),
            coin_creator_vault_ata=_to_pubkey(params["coin_creator_vault_ata"]),
            coin_creator_vault_authority=_to_pubkey(params["coin_creator_vault_authority"]),
            base_token_program=btp,
            quote_token_program=qtp,
            is_mayhem_mode=bool(params.get("is_mayhem_mode", False)),
            is_cashback_coin=bool(params.get("is_cashback_coin", False)),
            coin_creator=_to_pubkey(params.get("coin_creator", bytes(32))),
            cashback_fee_basis_points=int(params.get("cashback_fee_basis_points", 0)),
            fee_basis_points=_pumpswap_fee_basis_points(params, PsbFeeBasisPoints),
            pool_creator=_to_pubkey(params.get("pool_creator", bytes(32))),
            base_mint_supply=params.get("base_mint_supply"),
        )
        builder_params = BuildSellParams(
            payer=_to_pubkey(params["payer"]),
            input_amount=int(params["token_amount"]),
            slippage_basis_points=int(params.get("slippage_basis_points", 100)),
            protocol_params=protocol,
            create_output_mint_ata=bool(params.get("create_output_mint_ata", False)),
            close_output_mint_ata=bool(params.get("close_output_mint_ata", False)),
            close_input_mint_ata=bool(params.get("close_input_mint_ata", False)),
            fixed_output_amount=params.get("fixed_output_amount"),
        )
        instructions = psb_sell(builder_params)

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "PumpSwap",
            "type": "sell",
        }


    async def execute_buy(self, params):
        return await UnifiedTradeExecutor(DexType.PUMP_SWAP).execute_buy(params)

    async def execute_sell(self, params):
        return await UnifiedTradeExecutor(DexType.PUMP_SWAP).execute_sell(params)


class RaydiumCpmmExecutor(TradeExecutor):
    """Raydium CPMM trade executor"""

    @staticmethod
    def _optional_pubkey(value: Any) -> Optional[Pubkey]:
        pk = _to_pubkey(value)
        return None if pk == Pubkey.default() else pk

    @staticmethod
    def _protocol_params(params: Dict[str, Any]):
        from ..instruction.raydium_cpmm_builder import (
            RaydiumCpmmParams as RcpmmParams,
            TOKEN_PROGRAM as SPL_TOKEN,
        )

        base_token_program = _to_pubkey(params.get("base_token_program", params.get("token_program", bytes(32))))
        quote_token_program = _to_pubkey(params.get("quote_token_program", params.get("token_program", bytes(32))))
        if base_token_program == Pubkey.default():
            base_token_program = SPL_TOKEN
        if quote_token_program == Pubkey.default():
            quote_token_program = SPL_TOKEN

        return RcpmmParams(
            pool_state=RaydiumCpmmExecutor._optional_pubkey(params.get("pool_state", bytes(32))),
            amm_config=_to_pubkey(params["amm_config"]),
            base_mint=_to_pubkey(params["base_mint"]),
            quote_mint=_to_pubkey(params["quote_mint"]),
            base_reserve=int(params.get("base_reserve", 0)),
            quote_reserve=int(params.get("quote_reserve", 0)),
            base_vault=RaydiumCpmmExecutor._optional_pubkey(
                params.get("base_vault", params.get("input_vault", bytes(32)))
            ),
            quote_vault=RaydiumCpmmExecutor._optional_pubkey(
                params.get("quote_vault", params.get("output_vault", bytes(32)))
            ),
            base_token_program=base_token_program,
            quote_token_program=quote_token_program,
            observation_state=RaydiumCpmmExecutor._optional_pubkey(
                params.get("observation_state", bytes(32))
            ),
        )

    async def build_buy_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on Raydium CPMM"""
        from ..instruction.raydium_cpmm_builder import build_buy_instructions

        instructions = build_buy_instructions(
            payer=_to_pubkey(params["payer"]),
            output_mint=_to_pubkey(params["output_mint"]),
            input_amount=int(params["amount_in"]),
            params=self._protocol_params(params),
            slippage_bps=int(params.get("slippage_basis_points", 100)),
            create_input_ata=bool(params.get("create_input_mint_ata", False)),
            create_output_ata=bool(params.get("create_output_mint_ata", False)),
            close_input_ata=bool(params.get("close_input_mint_ata", False)),
            fixed_output_amount=params.get("fixed_output_amount"),
        )

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "RaydiumCpmm",
            "type": "buy",
        }

    async def build_sell_instructions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on Raydium CPMM"""
        from ..instruction.raydium_cpmm_builder import build_sell_instructions

        instructions = build_sell_instructions(
            payer=_to_pubkey(params["payer"]),
            input_mint=_to_pubkey(params["input_mint"]),
            input_amount=int(params["amount_in"]),
            params=self._protocol_params(params),
            slippage_bps=int(params.get("slippage_basis_points", 100)),
            create_output_ata=bool(params.get("create_output_mint_ata", False)),
            close_output_ata=bool(params.get("close_output_mint_ata", False)),
            close_input_ata=bool(params.get("close_input_mint_ata", False)),
            fixed_output_amount=params.get("fixed_output_amount"),
        )

        return {
            "prepared": True,
            "submitted": False,
            "confirmed": False,
            "instructions": instructions,
            "dex": "RaydiumCpmm",
            "type": "sell",
        }


    async def execute_buy(self, params):
        return await UnifiedTradeExecutor(DexType.RAYDIUM_CPMM).execute_buy(params)

    async def execute_sell(self, params):
        return await UnifiedTradeExecutor(DexType.RAYDIUM_CPMM).execute_sell(params)


class UnifiedTradeExecutor(TradeExecutor):
    """Real shared cached execution; legacy instruction-only helpers stay explicit."""
    def __init__(self, dex_type): self.dex_type = dex_type

    async def _execute(self, direction, params):
        from .cached_trade import CachedTradeExecutor, value
        if not isinstance(params, dict) or not {"request", "signers", "submit"} <= params.keys():
            raise ValueError("Provide request, signers and raw-wire submit")
        request = params["request"]
        if value(request.dex_type) != value(self.dex_type): raise ValueError("Factory/request protocol mismatch")
        if value(request.trade_type) != direction: raise ValueError("Factory/request trade direction mismatch")
        receipt = await CachedTradeExecutor(self.dex_type).execute(request, params["signers"], params["submit"])
        return dict(receipt, success=receipt["submitted"])

    async def execute_buy(self, params): return await self._execute("Buy", params)
    async def execute_sell(self, params): return await self._execute("Sell", params)


class TradeExecutorFactory:
    """Factory for legacy instruction builders and native cached executors."""

    @classmethod
    def get_supported_cached_dex_types(cls):
        from .cached_trade import PROGRAMS

        return [DexType(v) for v in PROGRAMS]

    @classmethod
    def create_cached_executor(cls, dex_type):
        from .cached_trade import CachedTradeExecutor, PROGRAMS, value

        if value(dex_type) not in PROGRAMS:
            raise ValueError("Protocol has no native cached trade executor")
        return CachedTradeExecutor(dex_type)

    _executors = {}  # Explicit custom overrides only; built-ins share the real execution core.

    @classmethod
    def get_supported_dex_types(cls):
        return list(DexType)

    @classmethod
    def create_executor(cls, dex_type: DexType) -> TradeExecutor:
        dex_type = DexType(dex_type)
        custom = cls._executors.get(dex_type)
        if custom is not None:
            return custom()
        return UnifiedTradeExecutor(dex_type)

    @classmethod
    def register_executor(cls, dex_type: DexType, executor_class: type):
        """Register a new executor class"""
        cls._executors[dex_type] = executor_class


class TradingClient:
    """High-level trading client with an explicit cache-only entry point."""

    def prepare_cached_trade(self, request):
        from .cached_trade import prepare_cached_trade

        return prepare_cached_trade(request)

    async def execute_cached_trade(self, request, signers, submit):
        executor = TradeExecutorFactory.create_cached_executor(request.dex_type)
        return await executor.execute(request, signers, submit)

    def __init__(self):
        self.executors: Dict[DexType, TradeExecutor] = {}

    def get_executor(self, dex_type: DexType) -> TradeExecutor:
        """Get or create executor for DEX type"""
        if dex_type not in self.executors:
            self.executors[dex_type] = TradeExecutorFactory.create_executor(dex_type)
        return self.executors[dex_type]

    async def buy(self, dex_type: DexType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy trade"""
        executor = self.get_executor(dex_type)
        return await executor.execute_buy(params)

    async def sell(self, dex_type: DexType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell trade"""
        executor = self.get_executor(dex_type)
        return await executor.execute_sell(params)
