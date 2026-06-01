"""
Comprehensive tests for Hot Path modules
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from sol_trade_sdk.hotpath import (
    HotPathConfig,
    HotPathState,
    HotPathExecutor,
    HotPathMetrics,
    TradingContext,
    PrefetchedData,
    AccountState,
    PoolState,
    ExecuteOptions,
    ExecuteResult,
    StaleBlockhashError,
    MissingAccountError,
    HotPathError,
    create_hot_path_executor,
)


class TestHotPathConfig:
    """Tests for HotPathConfig"""

    def test_default_config(self):
        """Test default configuration values"""
        config = HotPathConfig()
        assert config.blockhash_refresh_interval == 2.0
        assert config.cache_ttl == 5.0
        assert config.enable_prefetch is True
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration values"""
        config = HotPathConfig(
            blockhash_refresh_interval=1.0,
            cache_ttl=3.0,
            enable_prefetch=False,
        )
        assert config.blockhash_refresh_interval == 1.0
        assert config.cache_ttl == 3.0
        assert config.enable_prefetch is False


class TestPrefetchedData:
    """Tests for PrefetchedData"""

    def test_is_fresh(self):
        """Test freshness check"""
        data = PrefetchedData(
            blockhash="test_blockhash",
            last_valid_height=100,
            slot=50,
            fetched_at=time.time(),
        )
        assert data.is_fresh(5.0) is True

    def test_is_stale(self):
        """Test staleness check"""
        data = PrefetchedData(
            blockhash="test_blockhash",
            last_valid_height=100,
            slot=50,
            fetched_at=time.time() - 10.0,  # 10 seconds ago
        )
        assert data.is_fresh(5.0) is False

    def test_age(self):
        """Test age calculation"""
        data = PrefetchedData(
            fetched_at=time.time() - 2.0,
        )
        assert 1.9 < data.age() < 2.1


class TestAccountState:
    """Tests for AccountState"""

    def test_account_state_creation(self):
        """Test account state creation"""
        state = AccountState(
            pubkey="test_pubkey",
            data=b"test_data",
            lamports=1000000,
            owner="owner_pubkey",
            executable=False,
            rent_epoch=0,
            slot=100,
        )
        assert state.pubkey == "test_pubkey"
        assert state.data == b"test_data"
        assert state.lamports == 1000000

    def test_is_fresh(self):
        """Test account state freshness"""
        state = AccountState(
            pubkey="test",
            data=b"",
            lamports=0,
            owner="",
            executable=False,
            rent_epoch=0,
            slot=0,
            fetched_at=time.time(),
        )
        assert state.is_fresh(5.0) is True


class TestPoolState:
    """Tests for PoolState"""

    def test_pool_state_creation(self):
        """Test pool state creation"""
        state = PoolState(
            pool_address="pool_addr",
            pool_type="pumpfun",
            mint_a="mint_a",
            mint_b="mint_b",
            vault_a="vault_a",
            vault_b="vault_b",
            reserve_a=1000,
            reserve_b=2000,
            fee_rate=0.003,
        )
        assert state.pool_address == "pool_addr"
        assert state.pool_type == "pumpfun"
        assert state.reserve_a == 1000


class TestHotPathState:
    """Tests for HotPathState"""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create mock RPC client"""
        client = AsyncMock()
        client.get_latest_blockhash = AsyncMock(return_value={
            'blockhash': 'test_blockhash',
            'last_valid_block_height': 100,
            'slot': 50,
        })
        client.get_multiple_accounts = AsyncMock(return_value=[
            {
                'data': b'test_data',
                'lamports': 1000000,
                'owner': 'owner_pubkey',
                'executable': False,
                'rent_epoch': 0,
            }
        ])
        return client

    @pytest.fixture
    def hot_path_state(self, mock_rpc_client):
        """Create HotPathState with mock client"""
        config = HotPathConfig(enable_prefetch=False)
        return HotPathState(mock_rpc_client, config)

    def test_get_blockhash_empty(self, hot_path_state):
        """Test get_blockhash with no data"""
        blockhash, last_valid, valid = hot_path_state.get_blockhash()
        assert valid is False

    @pytest.mark.asyncio
    async def test_prefetch_blockhash(self, hot_path_state, mock_rpc_client):
        """Test blockhash prefetching"""
        await hot_path_state._prefetch_blockhash()

        blockhash, last_valid, valid = hot_path_state.get_blockhash()
        assert valid is True
        assert blockhash == "test_blockhash"
        assert last_valid == 100

    @pytest.mark.asyncio
    async def test_prefetch_accounts(self, hot_path_state, mock_rpc_client):
        """Test account prefetching"""
        await hot_path_state.prefetch_accounts(["pubkey1", "pubkey2"])

        state = hot_path_state.get_account("pubkey1")
        assert state is not None
        assert state.data == b"test_data"

    def test_update_account(self, hot_path_state):
        """Test manual account update"""
        state = AccountState(
            pubkey="test_pubkey",
            data=b"manual_data",
            lamports=500000,
            owner="owner",
            executable=False,
            rent_epoch=0,
            slot=100,
        )
        hot_path_state.update_account("test_pubkey", state)

        retrieved = hot_path_state.get_account("test_pubkey")
        assert retrieved is not None
        assert retrieved.data == b"manual_data"

    def test_get_metrics(self, hot_path_state):
        """Test metrics retrieval"""
        metrics = hot_path_state.get_metrics()
        assert 'prefetch_count' in metrics
        assert 'prefetch_errors' in metrics
        assert 'accounts_cached' in metrics


class TestTradingContext:
    """Tests for TradingContext"""

    @pytest.fixture
    def hot_path_state_with_data(self):
        """Create HotPathState with prefetched data"""
        state = MagicMock(spec=HotPathState)
        state.get_blockhash.return_value = ("test_blockhash", 100, True)
        state.get_account.return_value = AccountState(
            pubkey="token_account",
            data=b"token_data",
            lamports=1000000,
            owner="owner",
            executable=False,
            rent_epoch=0,
            slot=100,
        )
        return state

    def test_context_creation(self, hot_path_state_with_data):
        """Test trading context creation"""
        context = TradingContext(hot_path_state_with_data, "payer_pubkey")
        assert context.blockhash == "test_blockhash"
        assert context.last_valid_height == 100
        assert context.payer == "payer_pubkey"

    def test_context_add_account(self, hot_path_state_with_data):
        """Test adding account to context"""
        context = TradingContext(hot_path_state_with_data, "payer")
        result = context.add_account("token_account", hot_path_state_with_data)
        assert result is True
        assert "token_account" in context.account_states

    def test_context_age(self, hot_path_state_with_data):
        """Test context age calculation"""
        context = TradingContext(hot_path_state_with_data, "payer")
        time.sleep(0.1)
        assert context.age() >= 0.1

    def test_context_is_valid(self, hot_path_state_with_data):
        """Test context validity check"""
        context = TradingContext(hot_path_state_with_data, "payer")
        assert context.is_valid(5.0) is True

    def test_context_expired(self, hot_path_state_with_data):
        """Test expired context"""
        context = TradingContext(hot_path_state_with_data, "payer")
        context.created_at = time.time() - 10.0
        assert context.is_valid(5.0) is False

    def test_context_stale_blockhash(self):
        """Test context creation with stale blockhash"""
        state = MagicMock(spec=HotPathState)
        state.get_blockhash.return_value = (None, 0, False)

        with pytest.raises(ValueError):
            TradingContext(state, "payer")


class TestHotPathMetrics:
    """Tests for HotPathMetrics"""

    def test_record_success(self):
        """Test recording successful trade"""
        metrics = HotPathMetrics()
        metrics.record(success=True, latency_ms=100)

        stats = metrics.get_stats()
        assert stats['total_trades'] == 1
        assert stats['success_trades'] == 1
        assert stats['failed_trades'] == 0

    def test_record_failure(self):
        """Test recording failed trade"""
        metrics = HotPathMetrics()
        metrics.record(success=False, latency_ms=50)

        stats = metrics.get_stats()
        assert stats['total_trades'] == 1
        assert stats['failed_trades'] == 1

    def test_average_latency(self):
        """Test average latency calculation"""
        metrics = HotPathMetrics()
        metrics.record(True, 100)
        metrics.record(True, 200)

        stats = metrics.get_stats()
        assert stats['avg_latency_ms'] == 150


class TestHotPathExecutor:
    """Tests for HotPathExecutor"""

    @pytest.fixture
    def mock_swqos_client(self):
        """Create mock SWQoS client"""
        client = AsyncMock()
        client.send_transaction = AsyncMock(return_value="test_signature")
        client.swqos_type = "jito"
        return client

    @pytest.fixture
    def mock_rpc_client(self):
        """Create mock RPC client"""
        client = AsyncMock()
        client.get_latest_blockhash = AsyncMock(return_value={
            'blockhash': 'test_blockhash',
            'last_valid_block_height': 100,
            'slot': 50,
        })
        return client

    @pytest.fixture
    def executor(self, mock_rpc_client):
        """Create HotPathExecutor"""
        config = HotPathConfig(enable_prefetch=False)
        return HotPathExecutor(mock_rpc_client, config)

    def test_add_swqos_client(self, executor, mock_swqos_client):
        """Test adding SWQoS client"""
        executor.add_swqos_client(mock_swqos_client)
        assert len(executor._swqos_clients) == 1

    def test_remove_swqos_client(self, executor, mock_swqos_client):
        """Test removing SWQoS client"""
        executor.add_swqos_client(mock_swqos_client)
        executor.remove_swqos_client("jito")
        assert len(executor._swqos_clients) == 0

    @pytest.mark.asyncio
    async def test_execute_no_clients(self, executor):
        """Test execution with no SWQoS clients"""
        result = await executor.execute("buy", b"tx_bytes")
        assert result.success is False
        assert "No SWQoS clients" in result.error

    @pytest.mark.asyncio
    async def test_execute_stale_blockhash(self, executor, mock_swqos_client):
        """Test execution with stale blockhash"""
        executor.add_swqos_client(mock_swqos_client)
        result = await executor.execute(
            "buy",
            b"tx_bytes",
            ExecuteOptions(skip_blockhash_validation=False)
        )
        assert result.success is False
        assert "Stale blockhash" in result.error

    @pytest.mark.asyncio
    async def test_execute_success(self, executor, mock_swqos_client, mock_rpc_client):
        """Test successful execution"""
        # Prefetch blockhash
        await executor.state._prefetch_blockhash()
        executor.add_swqos_client(mock_swqos_client)

        result = await executor.execute(
            "buy",
            b"tx_bytes",
            ExecuteOptions(skip_blockhash_validation=True)
        )
        assert result.success is True
        assert result.signature == "test_signature"

    @pytest.mark.asyncio
    async def test_execute_parallel(self, executor, mock_rpc_client):
        """Test parallel execution"""
        await executor.state._prefetch_blockhash()

        # Add multiple clients
        client1 = AsyncMock()
        client1.send_transaction = AsyncMock(return_value="sig1")
        client1.swqos_type = "jito"

        client2 = AsyncMock()
        client2.send_transaction = AsyncMock(return_value="sig2")
        client2.swqos_type = "bloxroute"

        executor.add_swqos_client(client1)
        executor.add_swqos_client(client2)

        result = await executor.execute(
            "buy",
            b"tx_bytes",
            ExecuteOptions(
                parallel_submit=True,
                skip_blockhash_validation=True
            )
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_parallel_waits_past_first_failure(self, executor, mock_rpc_client):
        """Fast failed routes must not hide a slower successful submit"""
        await executor.state._prefetch_blockhash()

        client1 = AsyncMock()
        client1.send_transaction = AsyncMock(side_effect=RuntimeError("fast failure"))
        client1.swqos_type = "jito"

        async def slow_success(*args):
            await asyncio.sleep(0.005)
            return "sig2"

        client2 = AsyncMock()
        client2.send_transaction = AsyncMock(side_effect=slow_success)
        client2.swqos_type = "default"

        executor.add_swqos_client(client1)
        executor.add_swqos_client(client2)

        result = await executor.execute(
            "buy",
            b"tx_bytes",
            ExecuteOptions(
                parallel_submit=True,
                skip_blockhash_validation=True,
                timeout=0.1,
            )
        )

        assert result.success is True
        assert result.signature == "sig2"
        assert client1.send_transaction.await_count == 1
        assert client2.send_transaction.await_count == 1

    def test_get_metrics(self, executor):
        """Test getting execution metrics"""
        metrics = executor.get_metrics()
        assert 'total_trades' in metrics


class TestCreateHotPathExecutor:
    """Tests for factory function"""

    def test_create_executor(self):
        """Test creating executor via factory"""
        executor = create_hot_path_executor(
            "https://api.mainnet-beta.solana.com"
        )
        assert executor is not None
        assert isinstance(executor, HotPathExecutor)


class TestExceptions:
    """Tests for custom exceptions"""

    def test_hot_path_error(self):
        """Test HotPathError"""
        with pytest.raises(HotPathError):
            raise HotPathError("Test error")

    def test_stale_blockhash_error(self):
        """Test StaleBlockhashError"""
        with pytest.raises(StaleBlockhashError):
            raise StaleBlockhashError("Blockhash is stale")

    def test_missing_account_error(self):
        """Test MissingAccountError"""
        with pytest.raises(MissingAccountError):
            raise MissingAccountError("Account not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
