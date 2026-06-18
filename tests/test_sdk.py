"""
Tests for Sol Trade SDK - Python
"""

import asyncio
from types import SimpleNamespace
import pytest
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import Transaction
from sol_trade_sdk.common.types import (
    GasFeeStrategy,
    GasFeeStrategyType,
    TradeType,
    SwqosType,
    BondingCurveAccount,
    NonceCache,
    DurableNonceInfo,
)
from sol_trade_sdk.common.gas_fee_strategy import create_gas_fee_strategy
from sol_trade_sdk import calc
from sol_trade_sdk import (
    AccountPolicy,
    BuyAmount,
    DexType,
    SellAmount,
    SimpleBuyParams,
    SimpleSellParams,
    TradeTokenType,
    TradeBuyParams,
    TradeConfig as RootTradeConfig,
    TradingClient,
    SwqosConfig as RootSwqosConfig,
    SwqosRegion as RootSwqosRegion,
    SwqosType as RootSwqosType,
    create_trade_config,
    DurableNonceInfo as RootDurableNonceInfo,
    recommended_sender_thread_core_indices,
    simple_buy_params_to_trade_buy_params,
    simple_sell_params_to_trade_sell_params,
)
from sol_trade_sdk.swqos.clients import (
    ASTRALANE_ENDPOINTS,
    ASTRALANE_QUIC_HOSTS,
    BLOXROUTE_ENDPOINTS,
    BLOCK_RAZOR_ENDPOINTS,
    ClientFactory as SenderClientFactory,
    MIN_TIP_DEFAULT,
    MIN_TIP_SOLAMI,
    NODE1_ENDPOINTS,
    SOYAS_ENDPOINTS,
    SolamiClient,
    SPEEDLANDING_ENDPOINTS,
    STELLIUM_ENDPOINTS,
    SwqosConfig as SenderSwqosConfig,
    SwqosRegion as SenderSwqosRegion,
    SwqosType as SenderSwqosType,
    _signature_from_serialized_transaction,
)
from sol_trade_sdk.trading.executor import (
    TradeConfig as ExecutorTradeConfig,
    TradeExecutor,
)
from sol_trade_sdk.trading.high_perf_executor import (
    TradeConfig as HighPerfTradeConfig,
)
from sol_trade_sdk.trading.confirmation_parity import (
    extract_hints_from_logs,
    format_parsed_transaction_error,
    instruction_error_code_from_meta_err,
)
from sol_trade_sdk.trading.core.async_executor import (
    AsyncTradeExecutor,
    ExecutionConfig,
    SubmitMode,
)
from sol_trade_sdk.swqos.providers import (
    SwqosConfig as ProviderSwqosConfig,
    SwqosManager,
    SwqosType as ProviderSwqosType,
    TransactionResult,
)


class _FakeSwqosClient:
    def __init__(self, signature: str, delay: float, fail: bool = False):
        self.signature = signature
        self.delay = delay
        self.fail = fail

    async def send_transaction(self, trade_type, transaction, wait_confirmation):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("submit failed")
        return self.signature


class _FakeProviderClient:
    def __init__(self, swqos_type: ProviderSwqosType, signature: str, delay: float = 0.0):
        self.config = ProviderSwqosConfig(swqos_type=swqos_type)
        self.signature = signature
        self.delay = delay
        self.calls = 0

    async def submit_transaction(self, transaction: bytes, tip: int = 0):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return TransactionResult(
            success=True,
            signature=self.signature,
            provider=self.config.swqos_type.value,
        )


class _FakeSimValue:
    err = None
    units_consumed = 123
    logs = ["ok"]


class _FakeSimResponse:
    value = _FakeSimValue()


class _FakeSendResponse:
    value = Signature.default()


class _FakeRootRpcClient:
    def __init__(self):
        self.simulated = None
        self.sent = None
        self.blockhash = str(Hash.from_bytes(bytes([6]) * 32))

    async def simulate_transaction(self, txn, sig_verify=False, commitment=None):
        self.simulated = (txn, sig_verify, str(commitment))
        return _FakeSimResponse()

    async def send_raw_transaction(self, raw):
        self.sent = raw
        return _FakeSendResponse()

    async def get_latest_blockhash(self):
        return SimpleNamespace(value=Hash.from_string(self.blockhash))


class _RecordingMiddlewareManager:
    def __init__(self):
        self.calls = []

    def apply_middlewares_process_protocol_instructions(self, instructions, protocol_name, is_buy):
        self.calls.append(("protocol", protocol_name, is_buy, len(instructions)))
        return instructions + [Instruction(Pubkey.default(), b"protocol", [])]

    def apply_middlewares_process_full_instructions(self, instructions, protocol_name, is_buy):
        self.calls.append(("full", protocol_name, is_buy, len(instructions)))
        return instructions + [Instruction(Pubkey.default(), b"full", [])]


class _FakeInstructionBuilder:
    async def build_buy_instructions(self, **kwargs):
        return [Instruction(Pubkey.default(), b"buy", [])]

    async def build_sell_instructions(self, **kwargs):
        return [Instruction(Pubkey.default(), b"sell", [])]


class TestGasFeeStrategy:
    """Tests for GasFeeStrategy class"""

    def test_create_strategy(self):
        """Test creating a gas fee strategy"""
        strategy = GasFeeStrategy()
        assert strategy is not None

    def test_set_and_get(self):
        """Test setting and getting gas fee strategies"""
        strategy = GasFeeStrategy()
        strategy.set(
            SwqosType.JITO,
            TradeType.BUY,
            GasFeeStrategyType.NORMAL,
            200000,
            100000,
            0.001,
        )

        value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        assert value is not None
        assert value.cu_limit == 200000
        assert value.cu_price == 100000
        assert value.tip == 0.001

    def test_global_fee_strategy(self):
        """Test setting global fee strategy"""
        strategy = create_gas_fee_strategy()
        
        # Check that all SWQOS types have strategies set
        for swqos_type in [SwqosType.JITO, SwqosType.BLOXROUTE, SwqosType.ZERO_SLOT]:
            value = strategy.get(swqos_type, TradeType.BUY, GasFeeStrategyType.NORMAL)
            assert value is not None

    def test_update_buy_tip(self):
        """Test updating buy tip for all strategies"""
        strategy = GasFeeStrategy()
        strategy.set(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL, 200000, 100000, 0.001)
        strategy.set(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL, 200000, 100000, 0.002)

        strategy.update_buy_tip(0.005)

        buy_value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        sell_value = strategy.get(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL)

        assert buy_value.tip == 0.005
        assert sell_value.tip == 0.002

    def test_delete(self):
        """Test deleting strategies"""
        strategy = GasFeeStrategy()
        strategy.set(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL, 200000, 100000, 0.001)

        strategy.delete(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)

        value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        assert value is None

    def test_conflict_resolution(self):
        """Test that Normal strategy removes high/low variants"""
        strategy = GasFeeStrategy()
        
        # Set high/low strategies first
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE,
            200000, 100000, 0.0005
        )
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE,
            200000, 100000, 0.002
        )

        # Set Normal strategy (should remove high/low)
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL,
            200000, 100000, 0.001
        )

        # Check that high/low are gone
        low = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE)
        high = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE)
        normal = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)

        assert low is None
        assert high is None
        assert normal is not None


class TestTradeConfig:
    """Tests for trade configuration normalization"""

    def test_adds_default_rpc_when_swqos_configured(self):
        cfg = create_trade_config(
            "https://x",
            [
                RootSwqosConfig(
                    type=RootSwqosType.JITO,
                    region=RootSwqosRegion.FRANKFURT,
                    api_key="uuid",
                )
            ],
        )

        assert [c.type for c in cfg.swqos_configs] == [
            RootSwqosType.JITO,
            RootSwqosType.DEFAULT,
        ]

    def test_adds_default_rpc_when_no_swqos_configured(self):
        cfg = RootTradeConfig(rpc_url="https://x")
        assert [c.type for c in cfg.swqos_configs] == [RootSwqosType.DEFAULT]

    def test_rust_parity_defaults(self):
        cfg = create_trade_config("https://x")

        assert cfg.log_enabled is True
        assert cfg.check_min_tip is False
        assert cfg.mev_protection is False
        assert cfg.use_seed_optimize is True
        assert cfg.create_wsol_ata_on_startup is True
        assert cfg.swqos_cores_from_end is False

    def test_filters_nextblock_blacklist(self):
        cfg = create_trade_config(
            "https://x",
            [
                RootSwqosConfig(
                    type=RootSwqosType.NEXT_BLOCK,
                    region=RootSwqosRegion.FRANKFURT,
                    api_key="token",
                )
            ],
        )

        assert [c.type for c in cfg.swqos_configs] == [RootSwqosType.DEFAULT]

    def test_recommended_sender_thread_core_indices_uses_two_thirds_cap(self):
        assert recommended_sender_thread_core_indices(10, 6) == [2, 3, 4, 5]

    def test_module_executor_configs_normalize_default_and_blacklist(self):
        low = ExecutorTradeConfig(
            rpc_url="https://x",
            swqos_configs=[
                SenderSwqosConfig(type=SenderSwqosType.NEXT_BLOCK),
            ],
        )
        high = HighPerfTradeConfig(
            rpc_url="https://x",
            swqos_configs=[
                SenderSwqosConfig(type=SenderSwqosType.NEXT_BLOCK),
            ],
        )

        assert [c.type for c in low.swqos_configs] == [SenderSwqosType.DEFAULT]
        assert [c.type for c in high.swqos_configs] == [SenderSwqosType.DEFAULT]


class TestSimpleTradingParams:
    """Tests for Rust-parity simple trade parameter conversion"""

    def test_simple_param_constructors_and_defaults(self):
        buy = SimpleBuyParams.new(
            DexType.PUMPFUN,
            TradeTokenType.WSOL,
            Pubkey.default(),
            BuyAmount.with_max_input(5_000),
            object(),
            "recent",
        )

        assert buy.account_policy == AccountPolicy.AUTO
        assert buy.wait_tx_confirmed is False
        assert buy.wait_for_all_submits is False
        assert buy.simulate is False
        assert buy.recent_blockhash == "recent"

        sell = SimpleSellParams.new(
            DexType.PUMPFUN,
            TradeTokenType.USDC,
            Pubkey.default(),
            SellAmount.exact_input(7_000),
            object(),
            "recent",
        )
        assert sell.account_policy == AccountPolicy.AUTO
        assert sell.with_tip is True
        assert sell.wait_tx_confirmed is False
        assert sell.wait_for_all_submits is False
        assert sell.simulate is False

    def test_simple_durable_nonce_constructors_clear_recent_blockhash(self):
        nonce = RootDurableNonceInfo(
            nonce_account=Pubkey.from_bytes(bytes([1]) * 32),
            authority=Pubkey.from_bytes(bytes([2]) * 32),
            nonce_hash=str(Hash.from_bytes(bytes([3]) * 32)),
            recent_blockhash=str(Hash.from_bytes(bytes([4]) * 32)),
        )

        buy = SimpleBuyParams.with_durable_nonce(
            DexType.PUMPFUN,
            TradeTokenType.SOL,
            Pubkey.default(),
            BuyAmount.exact_input(1_000),
            object(),
            nonce,
        )
        assert buy.recent_blockhash is None
        assert buy.durable_nonce is nonce

        sell = SimpleSellParams.with_durable_nonce(
            DexType.PUMPFUN,
            TradeTokenType.SOL,
            Pubkey.default(),
            SellAmount.exact_output(500, 1_000),
            object(),
            nonce,
        )
        assert sell.recent_blockhash is None
        assert sell.durable_nonce is nonce

    def test_simple_setters_return_updated_copies(self):
        nonce = RootDurableNonceInfo(
            nonce_account=Pubkey.from_bytes(bytes([1]) * 32),
            authority=Pubkey.from_bytes(bytes([2]) * 32),
            nonce_hash=str(Hash.from_bytes(bytes([3]) * 32)),
            recent_blockhash=str(Hash.from_bytes(bytes([4]) * 32)),
        )
        base = SimpleBuyParams.new(
            DexType.PUMPFUN,
            TradeTokenType.WSOL,
            Pubkey.default(),
            BuyAmount.exact_input(1_000),
            object(),
            "recent",
        )

        buy = (
            base.set_slippage_basis_points(123)
            .set_account_policy(AccountPolicy.CREATE_MISSING)
            .set_durable_nonce(nonce)
            .set_wait_tx_confirmed(True)
            .set_wait_for_all_submits(True)
            .set_simulate(True)
            .set_grpc_recv_us(456)
        )
        assert base.recent_blockhash == "recent"
        assert buy.recent_blockhash is None
        assert buy.slippage_basis_points == 123
        assert buy.account_policy == AccountPolicy.CREATE_MISSING
        assert buy.wait_tx_confirmed is True
        assert buy.wait_for_all_submits is True
        assert buy.simulate is True
        assert buy.grpc_recv_us == 456

        sell = (
            SimpleSellParams.new(
                DexType.PUMPFUN,
                TradeTokenType.SOL,
                Pubkey.default(),
                SellAmount.exact_input(1_000),
                object(),
                "recent",
            )
            .set_slippage_basis_points(321)
            .set_account_policy(AccountPolicy.ASSUME_PREPARED)
            .set_wait_tx_confirmed(True)
            .set_wait_for_all_submits(True)
            .set_simulate(True)
            .set_with_tip(False)
            .set_grpc_recv_us(654)
        )
        assert sell.slippage_basis_points == 321
        assert sell.account_policy == AccountPolicy.ASSUME_PREPARED
        assert sell.wait_tx_confirmed is True
        assert sell.wait_for_all_submits is True
        assert sell.simulate is True
        assert sell.with_tip is False
        assert sell.grpc_recv_us == 654

    def test_simple_buy_with_max_input_hot_path_and_nonce(self):
        nonce = RootDurableNonceInfo(
            nonce_account=Pubkey.from_bytes(bytes([1]) * 32),
            authority=Pubkey.from_bytes(bytes([2]) * 32),
            nonce_hash=str(Hash.from_bytes(bytes([3]) * 32)),
            recent_blockhash=str(Hash.from_bytes(bytes([4]) * 32)),
        )

        low = simple_buy_params_to_trade_buy_params(
            SimpleBuyParams(
                dex_type=DexType.PUMPFUN,
                pay_with=TradeTokenType.USDC,
                mint=Pubkey.default(),
                amount=BuyAmount.with_max_input(10_000),
                extension_params=object(),
                recent_blockhash="recent",
                slippage_basis_points=250,
                account_policy=AccountPolicy.HOT_PATH_MINIMAL,
                wait_for_all_submits=True,
                durable_nonce=nonce,
                simulate=True,
            )
        )

        assert low.input_token_type == TradeTokenType.USDC
        assert low.input_token_amount == 10_000
        assert low.use_exact_sol_amount is False
        assert low.create_input_token_ata is False
        assert low.create_mint_ata is False
        assert low.close_input_token_ata is False
        assert low.recent_blockhash is None
        assert low.durable_nonce is nonce
        assert low.wait_for_all_submits is True
        assert low.simulate is True
        assert low.slippage_basis_points == 250

    def test_simple_buy_exact_output_auto_policy(self):
        low = simple_buy_params_to_trade_buy_params(
            SimpleBuyParams(
                dex_type=DexType.PUMPFUN,
                pay_with=TradeTokenType.SOL,
                mint=Pubkey.default(),
                amount=BuyAmount.exact_output(42, 10_000),
                extension_params=object(),
                account_policy=AccountPolicy.AUTO,
            )
        )

        assert low.input_token_amount == 10_000
        assert low.fixed_output_token_amount == 42
        assert low.use_exact_sol_amount is True
        assert low.create_input_token_ata is False
        assert low.create_mint_ata is True
        assert low.close_input_token_ata is False

    def test_simple_sell_defaults_and_output_policy(self):
        low = simple_sell_params_to_trade_sell_params(
            SimpleSellParams(
                dex_type=DexType.PUMPFUN,
                receive_as=TradeTokenType.USDC,
                mint=Pubkey.default(),
                amount=SellAmount.exact_output(7_000, 50_000),
                extension_params=object(),
            )
        )

        assert low.input_token_amount == 50_000
        assert low.fixed_output_token_amount == 7_000
        assert low.with_tip is True
        assert low.create_output_token_ata is True
        assert low.close_output_token_ata is False
        assert low.close_mint_token_ata is False

        sol_low = simple_sell_params_to_trade_sell_params(
            SimpleSellParams(
                dex_type=DexType.PUMPFUN,
                receive_as=TradeTokenType.SOL,
                mint=Pubkey.default(),
                amount=SellAmount.exact_input(50_000),
                extension_params=object(),
                with_tip=False,
            )
        )

        assert sol_low.with_tip is False
        assert sol_low.create_output_token_ata is False


class TestRootTradingClientExecution:
    @pytest.mark.asyncio
    async def test_simulate_uses_nonce_hash_and_does_not_submit(self):
        payer = Keypair()
        nonce_hash = str(Hash.from_bytes(bytes([9]) * 32))
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake

        result = await client._execute_transaction(
            [
                Instruction(
                    Pubkey.default(),
                    b"abc",
                    [AccountMeta(Pubkey.default(), False, False)],
                )
            ],
            None,
            False,
            trade_type=TradeType.BUY,
            durable_nonce=RootDurableNonceInfo(
                nonce_account=Pubkey.from_bytes(bytes([3]) * 32),
                authority=payer.pubkey(),
                nonce_hash=nonce_hash,
                recent_blockhash=nonce_hash,
            ),
            gas_fee_strategy=SimpleNamespace(
                buy_priority_fee=7,
                buy_compute_units=200_000,
                buy_tip_lamports=99,
            ),
            simulate=True,
        )

        assert result.success is True
        assert result.simulation == {"units_consumed": 123, "logs": ["ok"]}
        assert fake.sent is None
        tx = fake.simulated[0]
        assert str(tx.message.recent_blockhash) == nonce_hash
        assert list(tx.message.instructions[0].data) == [4, 0, 0, 0]
        assert list(tx.message.instructions[1].data)[0] == 3
        assert list(tx.message.instructions[2].data)[0] == 2

    @pytest.mark.asyncio
    async def test_wsol_helper_fetches_blockhash_for_non_hot_path_helper(self):
        payer = Keypair()
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake

        sig = await client.wrap_sol_to_wsol(1)

        assert sig == str(Signature.default())
        assert fake.sent is not None

    @pytest.mark.asyncio
    async def test_direct_send_serializes_nonce_advance_before_compute_budget(self):
        payer = Keypair()
        nonce_hash = str(Hash.from_bytes(bytes([8]) * 32))
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake

        result = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            None,
            False,
            trade_type=TradeType.SELL,
            durable_nonce=SimpleNamespace(
                nonce_account=Pubkey.from_bytes(bytes([4]) * 32),
                authority=payer.pubkey(),
                nonce_hash=nonce_hash,
                recent_blockhash=nonce_hash,
            ),
            gas_fee_strategy=SimpleNamespace(
                sell_priority_fee=11,
                sell_compute_units=180_000,
                sell_tip_lamports=99,
            ),
            with_tip=True,
        )

        assert result.success is True
        tx = Transaction.from_bytes(fake.sent)
        assert str(tx.message.recent_blockhash) == nonce_hash
        assert list(tx.message.instructions[0].data) == [4, 0, 0, 0]
        assert list(tx.message.instructions[1].data)[0] == 3
        assert list(tx.message.instructions[2].data)[0] == 2

    @pytest.mark.asyncio
    async def test_legacy_execution_prefers_durable_nonce_over_recent_blockhash(self):
        payer = Keypair()
        recent = str(Hash.from_bytes(bytes([12]) * 32))
        nonce_hash = str(Hash.from_bytes(bytes([13]) * 32))
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake

        result = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            recent,
            False,
            trade_type=TradeType.SELL,
            durable_nonce=SimpleNamespace(
                nonce_account=Pubkey.from_bytes(bytes([4]) * 32),
                authority=payer.pubkey(),
                nonce_hash=nonce_hash,
                recent_blockhash=nonce_hash,
            ),
        )

        assert result.success is True
        tx = Transaction.from_bytes(fake.sent)
        assert str(tx.message.recent_blockhash) == nonce_hash

    @pytest.mark.asyncio
    async def test_rejects_oversized_signed_transaction_before_submit(self):
        payer = Keypair()
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake
        recent = str(Hash.from_bytes(bytes([12]) * 32))

        result = await client._execute_transaction(
            [
                Instruction(
                    Pubkey.default(),
                    bytes([1]) * 700,
                    [
                        AccountMeta(Pubkey.from_bytes(bytes([i + 1]) * 32), False, False)
                        for i in range(40)
                    ],
                )
            ],
            recent,
            False,
            trade_type=TradeType.BUY,
        )

        assert result.success is False
        assert "transaction too large" in (result.error or "")
        assert fake.sent is None
        assert fake.simulated is None

    @pytest.mark.asyncio
    async def test_rust_style_middleware_manager_runs_protocol_and_full_passes(self):
        payer = Keypair()
        blockhash = str(Hash.from_bytes(bytes([10]) * 32))
        manager = _RecordingMiddlewareManager()
        client = TradingClient(
            payer,
            RootTradeConfig.builder("https://x").middleware_manager(manager).build(),
        )
        fake = _FakeRootRpcClient()
        client.client = fake
        client._create_instruction_builder = lambda dex_type: _FakeInstructionBuilder()

        result = await client.buy(
            TradeBuyParams(
                dex_type=DexType.PUMPFUN,
                input_token_type=TradeTokenType.SOL,
                mint=Pubkey.default(),
                input_token_amount=1,
                extension_params=object(),
                recent_blockhash=blockhash,
                gas_fee_strategy=SimpleNamespace(
                    buy_priority_fee=7,
                    buy_compute_units=200_000,
                    buy_tip_lamports=0,
                ),
            )
        )

        assert result.success is True
        assert manager.calls == [
            ("protocol", "PumpFun", True, 1),
            ("full", "PumpFun", True, 4),
        ]
        tx = Transaction.from_bytes(fake.sent)
        assert bytes(tx.message.instructions[-1].data) == b"full"

    @pytest.mark.asyncio
    async def test_tip_recipient_inserts_tip_between_nonce_and_compute_budget(self):
        payer = Keypair()
        nonce_hash = str(Hash.from_bytes(bytes([7]) * 32))
        client = TradingClient(payer, RootTradeConfig(rpc_url="https://x"))
        fake = _FakeRootRpcClient()
        client.client = fake

        result = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            None,
            False,
            trade_type=TradeType.SELL,
            durable_nonce=SimpleNamespace(
                nonce_account=Pubkey.from_bytes(bytes([6]) * 32),
                authority=payer.pubkey(),
                nonce_hash=nonce_hash,
                recent_blockhash=nonce_hash,
            ),
            gas_fee_strategy=SimpleNamespace(
                sell_priority_fee=11,
                sell_compute_units=180_000,
                sell_tip_lamports=99,
            ),
            with_tip=True,
            tip_recipient=Pubkey.from_bytes(bytes([5]) * 32),
        )

        assert result.success is True
        tx = Transaction.from_bytes(fake.sent)
        assert list(tx.message.instructions[0].data) == [4, 0, 0, 0]
        assert list(tx.message.instructions[1].data)[:4] == [2, 0, 0, 0]
        assert list(tx.message.instructions[2].data)[0] == 3
        assert list(tx.message.instructions[3].data)[0] == 2

    @pytest.mark.asyncio
    async def test_swqos_execution_waits_for_first_or_all_submits(self, monkeypatch):
        payer = Keypair()
        blockhash = str(Hash.from_bytes(bytes([5]) * 32))
        client = TradingClient(
            payer,
            RootTradeConfig(
                rpc_url="https://rpc.example",
                swqos_configs=[
                    RootSwqosConfig(type=RootSwqosType.JITO, region=RootSwqosRegion.FRANKFURT),
                ],
            ),
        )
        fake = _FakeRootRpcClient()
        client.client = fake

        class FakeSenderFactory:
            calls = 0

            @staticmethod
            def create_client(config, rpc_url):
                FakeSenderFactory.calls += 1
                if FakeSenderFactory.calls == 1:
                    return _FakeSwqosClient("sig-fast", 0.0)
                return _FakeSwqosClient("sig-slow", 0.01)

        import sol_trade_sdk.swqos.clients as swqos_clients

        monkeypatch.setattr(swqos_clients, "ClientFactory", FakeSenderFactory)

        missing_nonce = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            blockhash,
            False,
            trade_type=TradeType.BUY,
        )
        assert missing_nonce.success is False
        assert "durable_nonce" in missing_nonce.error

        nonce = RootDurableNonceInfo(
            nonce_account=Pubkey.from_bytes(bytes([6]) * 32),
            authority=payer.pubkey(),
            nonce_hash=blockhash,
            recent_blockhash=blockhash,
        )

        FakeSenderFactory.calls = 0
        first = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            None,
            False,
            trade_type=TradeType.BUY,
            durable_nonce=nonce,
        )
        assert first.signatures == ["sig-fast"]

        FakeSenderFactory.calls = 0
        all_submits = await client._execute_transaction(
            [Instruction(Pubkey.default(), b"abc", [])],
            None,
            False,
            trade_type=TradeType.BUY,
            durable_nonce=nonce,
            wait_for_all_submits=True,
        )
        assert all_submits.signatures == ["sig-fast", "sig-slow"]


class TestSwqosSolami:
    """Tests for Solami SWQOS parity added in Rust v4.0.21"""

    def test_sender_factory_creates_solami_client(self):
        client = SenderClientFactory.create_client(
            SenderSwqosConfig(
                type=RootSwqosType.SOLAMI,
                region=RootSwqosRegion.TOKYO,
            ),
            "https://rpc.example",
        )

        assert isinstance(client, SolamiClient)
        assert client.get_swqos_type().value == RootSwqosType.SOLAMI.value
        assert client.endpoint == "beam.solami.dev:11000"
        assert client._SERVER_NAME == "solami-beam"
        assert client.min_tip_sol() == MIN_TIP_SOLAMI

    def test_provider_factory_exposes_solami(self):
        from sol_trade_sdk.swqos.providers import (
            SolamiClient as ProviderSolamiClient,
            SwqosClientFactory,
        )

        cfg = ProviderSwqosConfig(swqos_type=ProviderSwqosType.SOLAMI)
        client = SwqosClientFactory.create_client(cfg)

        assert isinstance(client, ProviderSolamiClient)
        assert ProviderSwqosType.TRITON not in SwqosClientFactory.get_supported_types()
        assert ProviderSwqosType.QUICKNODE not in SwqosClientFactory.get_supported_types()
        assert ProviderSwqosType.SYNDICA not in SwqosClientFactory.get_supported_types()
        assert ProviderSwqosType.FIGMENT not in SwqosClientFactory.get_supported_types()
        assert ProviderSwqosType.ALCHEMY not in SwqosClientFactory.get_supported_types()

        with pytest.raises(ValueError, match="Unsupported SWQOS type"):
            SwqosClientFactory.create_client(ProviderSwqosConfig(swqos_type=ProviderSwqosType.TRITON))

    @pytest.mark.asyncio
    async def test_sender_solami_requires_api_token(self):
        client = SenderClientFactory.create_client(
            SenderSwqosConfig(
                type=RootSwqosType.SOLAMI,
                region=RootSwqosRegion.TOKYO,
            ),
            "https://rpc.example",
        )

        with pytest.raises(Exception, match="Solami api_token is required"):
            await client.send_transaction(TradeType.BUY, bytes([1] + [0] * 64))

    @pytest.mark.asyncio
    async def test_provider_solami_does_not_claim_http_live_submit(self):
        from sol_trade_sdk.swqos.providers import SwqosClientFactory

        cfg = ProviderSwqosConfig(swqos_type=ProviderSwqosType.SOLAMI)
        client = SwqosClientFactory.create_client(cfg)
        result = await client.submit_transaction(bytes([1] + [0] * 64))

        assert result.success is False
        assert "QUIC path" in result.error

    def test_nextblock_is_blacklisted_by_rust_parity_factories(self):
        with pytest.raises(ValueError, match="blacklisted"):
            SenderClientFactory.create_client(
                SenderSwqosConfig(type=SenderSwqosType.NEXT_BLOCK),
                "https://rpc.example",
            )

        from sol_trade_sdk.swqos.providers import SwqosClientFactory

        with pytest.raises(ValueError, match="blacklisted"):
            SwqosClientFactory.create_client(
                ProviderSwqosConfig(swqos_type=ProviderSwqosType.NEXT_BLOCK)
            )


class TestSwqosEndpointParity:
    def test_key_region_fallbacks_match_rust_v4_0_21(self):
        assert MIN_TIP_DEFAULT == 0.00001
        assert BLOXROUTE_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "https://tokyo.solana.dex.blxrbdn.com"
        assert NODE1_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "http://tk.node1.me"
        assert "tokyo.solana.blockrazor" in BLOCK_RAZOR_ENDPOINTS[SenderSwqosRegion.SINGAPORE]
        assert ASTRALANE_ENDPOINTS[SenderSwqosRegion.SLC] == "http://la.gateway.astralane.io/irisb"
        assert ASTRALANE_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "http://sg.gateway.astralane.io/irisb"
        assert ASTRALANE_QUIC_HOSTS[SenderSwqosRegion.SINGAPORE] == "sg.gateway.astralane.io"
        assert STELLIUM_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "http://tyo1.flashrpc.com"
        assert SOYAS_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "tyo.landing.soyas.xyz:9000"
        assert SPEEDLANDING_ENDPOINTS[SenderSwqosRegion.SINGAPORE] == "sgp.speedlanding.trade:17778"

        client = SenderClientFactory.create_client(
            SenderSwqosConfig(type=RootSwqosType.BLOXROUTE, region=RootSwqosRegion.SINGAPORE),
            "https://rpc.example",
        )
        assert client.endpoint == "https://tokyo.solana.dex.blxrbdn.com"

    def test_serialized_transaction_signature_helper(self):
        tx = bytes([1] + [7] * 64)
        assert (
            _signature_from_serialized_transaction(tx)
            == "99eUso3aSbE9tqGSTXzo3TLfKb9RkMTURrHKQ1K7Zh3BbeqPevr5E1iCbpTjqHuTFLtfxTTD5ekfVuZFzQyEQf8"
        )


class TestConfirmationParsing:
    """Rust-parity confirmation error parsing"""

    def test_extract_hints_from_logs_matches_rust_patterns(self):
        hints = extract_hints_from_logs(
            [
                "Program log: Error: slippage.",
                "x Error Message: user rejected.",
            ]
        )

        assert "slippage" in hints
        assert "user rejected" in hints

    def test_instruction_error_code_from_meta_err_matches_rust(self):
        assert instruction_error_code_from_meta_err(
            {"InstructionError": [2, {"Custom": 6001}]}
        ).code == 6001

        parsed = instruction_error_code_from_meta_err(
            {"InstructionError": [1, "InvalidInstructionData"]}
        )
        assert parsed.code == 3
        assert parsed.instruction_index == 1

        assert instruction_error_code_from_meta_err(
            {"InstructionError": [3, "ComputationalBudgetExceeded"]}
        ).code == 999
        assert instruction_error_code_from_meta_err("BlockhashNotFound").code == 108

    def test_format_parsed_transaction_error_includes_code_instruction_and_log_hint(self):
        message = format_parsed_transaction_error(
            {"InstructionError": [2, {"Custom": 6001}]},
            ["Program log: Error: slippage exceeded."],
        )

        assert "code=6001" in message
        assert "instruction=2" in message
        assert "slippage exceeded" in message


class TestParallelExecutor:
    """Tests for first-success parallel submit behavior"""

    @pytest.mark.asyncio
    async def test_parallel_submit_waits_past_first_failure(self):
        executor = TradeExecutor(ExecutorTradeConfig(rpc_url="https://x"))
        executor._clients = {
            SwqosType.JITO: _FakeSwqosClient("", 0.001, fail=True),
            SwqosType.BLOXROUTE: _FakeSwqosClient("sig-ok", 0.01),
        }

        results = await executor.execute_parallel(
            TradeType.BUY,
            [b"tx"],
            wait_confirmation=False,
        )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].signature == "sig-ok"

    @pytest.mark.asyncio
    async def test_parallel_submit_keeps_one_result_per_transaction(self):
        executor = TradeExecutor(ExecutorTradeConfig(rpc_url="https://x"))
        executor._clients = {
            SwqosType.JITO: _FakeSwqosClient("sig-ok", 0.001),
        }

        results = await executor.execute_parallel(
            TradeType.BUY,
            [b"tx1", b"tx2"],
            wait_confirmation=False,
        )

        assert len(results) == 2
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_core_parallel_executor_submits_all_providers(self):
        manager = SwqosManager()
        clients = [
            _FakeProviderClient(ProviderSwqosType.JITO, "sig-jito", 0.001),
            _FakeProviderClient(ProviderSwqosType.BLOXROUTE, "sig-blox", 0.01),
            _FakeProviderClient(ProviderSwqosType.HELIUS, "sig-helius", 0.01),
            _FakeProviderClient(ProviderSwqosType.DEFAULT, "sig-default", 0.01),
        ]
        for client in clients:
            manager.add_client(client)

        executor = AsyncTradeExecutor(manager)
        result = await executor.execute(
            b"tx",
            ExecutionConfig(
                submit_mode=SubmitMode.PARALLEL,
                parallel_submit_count=1,
                timeout_ms=1000,
            ),
        )
        await asyncio.sleep(0.03)

        assert result.success is True
        assert all(client.calls == 1 for client in clients)


class TestBondingCurveAccount:
    """Tests for BondingCurveAccount class"""

    def test_initial_state(self):
        """Test initial bonding curve state"""
        curve = BondingCurveAccount()
        
        assert curve.virtual_token_reserves == 1073000000000000
        assert curve.virtual_sol_reserves == 30000000000
        assert curve.real_token_reserves == 793000000000000
        assert curve.complete is False

    def test_get_buy_price(self):
        """Test calculating buy price"""
        curve = BondingCurveAccount()
        
        # Buy with 0.001 SOL (1_000_000 lamports)
        tokens = curve.get_buy_price(1_000_000)
        assert tokens > 0

    def test_get_sell_price(self):
        """Test calculating sell price"""
        curve = BondingCurveAccount()
        
        # Sell some tokens
        sol = curve.get_sell_price(1_000_000_000)  # 1 million tokens
        assert sol > 0

    def test_get_market_cap_sol(self):
        """Test calculating market cap"""
        curve = BondingCurveAccount()
        
        market_cap = curve.get_market_cap_sol()
        assert market_cap > 0

    def test_get_token_price(self):
        """Test calculating token price"""
        curve = BondingCurveAccount()
        
        price = curve.get_token_price()
        assert price > 0

    def test_complete_curve_returns_zero(self):
        """Test that complete curves return zero for buy/sell"""
        curve = BondingCurveAccount(complete=True)
        
        assert curve.get_buy_price(1_000_000) == 0
        assert curve.get_sell_price(1_000_000) == 0


class TestNonceCache:
    """Tests for NonceCache class"""

    def test_set_and_get(self):
        """Test setting and getting nonce info"""
        cache = NonceCache()
        
        pubkey = b"test_pubkey_32_bytes_long_enough_xx"
        info = DurableNonceInfo(
            nonce_account=b"nonce_account_32_bytes_long_enough",
            authority=b"authority_32_bytes_long_enough_xx",
            nonce_hash=b"hash_32_bytes_long_enough_for_hash!",
            recent_blockhash=b"blockhash_32_bytes_long_enough!",
        )
        
        cache.set(pubkey, info)
        result = cache.get(pubkey)
        
        assert result is not None
        assert result.nonce_account == info.nonce_account

    def test_delete(self):
        """Test deleting nonce info"""
        cache = NonceCache()
        
        pubkey = b"test_pubkey_32_bytes_long_enough_xx"
        info = DurableNonceInfo(
            nonce_account=b"nonce_account_32_bytes_long_enough",
            authority=b"authority_32_bytes_long_enough_xx",
            nonce_hash=b"hash_32_bytes_long_enough_for_hash!",
            recent_blockhash=b"blockhash_32_bytes_long_enough!",
        )
        
        cache.set(pubkey, info)
        cache.delete(pubkey)
        
        result = cache.get(pubkey)
        assert result is None


class TestCalculations:
    """Tests for calculation utilities"""

    def test_compute_fee(self):
        """Test fee calculation"""
        fee = calc.compute_fee(1_000_000, 100, 10000)  # 1%
        assert fee == 10000

    def test_ceil_div(self):
        """Test ceiling division"""
        assert calc.ceil_div(10, 3) == 4
        assert calc.ceil_div(9, 3) == 3
        assert calc.ceil_div(11, 3) == 4

    def test_calculate_with_slippage_buy(self):
        """Test slippage calculation for buy"""
        result = calc.calculate_with_slippage_buy(1000, 100)  # 1% slippage
        assert result == 1010

    def test_calculate_with_slippage_sell(self):
        """Test slippage calculation for sell"""
        result = calc.calculate_with_slippage_sell(1000, 100)  # 1% slippage
        assert result == 990

    def test_get_buy_token_amount_from_sol_amount(self):
        """Test PumpFun buy calculation"""
        tokens = calc.get_buy_token_amount_from_sol_amount(
            sol_amount=1_000_000,
            virtual_sol_reserves=30_000_000_000,
            virtual_token_reserves=1_073_000_000_000_000,
            real_token_reserves=793_000_000_000_000,
        )
        assert tokens > 0

    def test_get_sell_sol_amount_from_token_amount(self):
        """Test PumpFun sell calculation"""
        sol = calc.get_sell_sol_amount_from_token_amount(
            token_amount=1_000_000_000,
            virtual_sol_reserves=30_000_000_000,
            virtual_token_reserves=1_073_000_000_000_000,
            real_sol_reserves=1_000_000_000,
        )
        assert sol > 0

    def test_buy_base_input_internal(self):
        """Test PumpSwap buy calculation"""
        result = calc.buy_base_input_internal(
            amount_in=1_000_000,
            reserve_in=30_000_000_000,
            reserve_out=1_073_000_000_000_000,
            slippage_bps=500,
        )
        assert result.amount_out > 0
        assert result.fee > 0

    def test_sell_base_input_internal(self):
        """Test PumpSwap sell calculation"""
        result = calc.sell_base_input_internal(
            amount_in=1_000_000_000,
            reserve_in=1_073_000_000_000_000,
            reserve_out=30_000_000_000,
            slippage_bps=500,
        )
        assert result.amount_out > 0
        assert result.fee > 0

    def test_raydium_amm_v4_calculations(self):
        """Test Raydium AMM V4 calculations"""
        amount_out = calc.raydium_amm_v4_get_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_raydium_cpmm_calculations(self):
        """Test Raydium CPMM calculations"""
        amount_out = calc.raydium_cpmm_get_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_bonk_calculations(self):
        """Test Bonk calculations"""
        amount_out = calc.get_bonk_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_lamports_conversions(self):
        """Test lamports to SOL conversions"""
        assert calc.lamports_to_sol(1_000_000_000) == 1.0
        assert calc.sol_to_lamports(1.0) == 1_000_000_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
