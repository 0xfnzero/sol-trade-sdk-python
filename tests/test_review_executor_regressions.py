"""Offline regressions for confirmation, caller-loop submission and rate waits."""
import asyncio
from unittest.mock import patch
import aiohttp
import pytest
from src.common.types import TradeType, SwqosType
from src.pool.pool import RateLimiter
from src.swqos.clients import DefaultClient
from src.trading.confirmation_parity import is_successful_confirmation
from src.trading.executor import poll_for_confirmation, poll_for_confirmation_error
from src.trading.high_perf_executor import TradeExecutor, TradeConfig, ExecuteOptions


@pytest.mark.parametrize('level', ['processed', 'confirmed', 'finalized'])
@pytest.mark.parametrize('error', [None, {'InstructionError': [0, {'Custom': 0}]}, 'BlockhashNotFound'])
def test_confirmation_error_overrides_level(level, error):
    assert is_successful_confirmation({'confirmationStatus': level, 'err': error}) == (
        error is None and level in ('confirmed', 'finalized'))


class PollResponse:
    def __init__(self, payload): self.payload = payload
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def json(self): return self.payload


@pytest.mark.parametrize('level', ['confirmed', 'finalized'])
def test_both_polling_apis_reject_failed_confirmed_transaction(level):
    error = {'InstructionError': [0, {'Custom': 6001}]}
    class PollSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def post(self, url, *, json, **kwargs):
            if json['method'] == 'getSignatureStatuses':
                return PollResponse({'result': {'value': [{'err': error, 'confirmationStatus': level}]}})
            return PollResponse({'result': {'meta': {'err': error, 'logMessages': []}}})
    async def run():
        with patch('aiohttp.ClientSession', PollSession):
            assert await poll_for_confirmation('offline://unused', 'signature') is False
            ok, message = await poll_for_confirmation_error('offline://unused', 'signature')
            assert not ok and '6001' in message
    asyncio.run(run())


class HTTPResponse:
    status = 200
    async def __aenter__(self): return self
    async def __aexit__(self, *args): self.release()
    async def json(self): return {'result': 'offline-signature'}
    def release(self): pass
    async def wait_for_close(self): pass


@pytest.mark.parametrize('parallel', [False, True])
def test_real_default_client_reuses_session_on_caller_loop(parallel):
    async def run():
        client = DefaultClient('offline://unused')
        executor = None
        loops, sessions = [], []
        async def offline_request(session, *args, **kwargs):
            assert session._loop is asyncio.get_running_loop()
            assert not session._loop.is_closed()
            loops.append(session._loop)
            sessions.append(session)
            return HTTPResponse()
        try:
            with patch('src.trading.high_perf_executor.ClientFactory.create_client', return_value=client), \
                    patch.object(aiohttp.ClientSession, '_request', offline_request):
                executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
                opts = ExecuteOptions(wait_confirmation=False, parallel_submit=parallel)
                for _ in range(2):
                    result = await executor.execute(TradeType.BUY, b'unsigned offline fixture', opts)
                    assert result.success, result.error
                assert len(loops) == 2 and all(loop is asyncio.get_running_loop() for loop in loops)
                assert sessions[0] is sessions[1]
        finally:
            if executor is not None: executor.close()
            await DefaultClient.close_session()
    asyncio.run(run())


def test_exhausted_rate_bucket_yields_and_is_cancellable():
    async def run():
        client = DefaultClient('offline://unused')
        with patch('src.trading.high_perf_executor.ClientFactory.create_client', return_value=client):
            executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
        limiter = RateLimiter(rate=0.001, burst=1)
        assert limiter.allow()
        executor._rate_limiter = limiter
        heartbeat = asyncio.Event()
        task = asyncio.create_task(executor.execute(TradeType.BUY, b'fixture'))
        try:
            await asyncio.sleep(0)
            asyncio.get_running_loop().call_soon(heartbeat.set)
            await heartbeat.wait()
            assert not task.done()  # Still waits for a token while unrelated work runs.
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        finally:
            task.cancel()
            executor.close()
    asyncio.run(run())


def test_parallel_first_success_retains_other_lanes_until_completion():
    async def run():
        release = asyncio.Event()
        class FakeClient:
            def __init__(self, kind): self.kind = kind
            def get_swqos_type(self): return self.kind
            async def send_transaction(self, *args):
                if self.kind == SwqosType.JITO: await release.wait()
                return str(self.kind)
        with patch('src.trading.high_perf_executor.ClientFactory.create_client', return_value=FakeClient(SwqosType.DEFAULT)):
            executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
        executor._clients[SwqosType.JITO] = FakeClient(SwqosType.JITO)
        try:
            result = await executor.execute(TradeType.BUY, b'fixture', ExecuteOptions(wait_confirmation=False))
            assert result.success
            assert executor._pending_submissions
            release.set()
            await asyncio.gather(*executor._pending_submissions)
            await asyncio.sleep(0)
            assert not executor._pending_submissions
        finally:
            release.set()
            executor.close()
    asyncio.run(run())


def test_close_cancels_owned_remaining_lane():
    async def run():
        started, cancelled = asyncio.Event(), asyncio.Event()
        class FakeClient:
            def __init__(self, kind): self.kind = kind
            def get_swqos_type(self): return self.kind
            async def send_transaction(self, *args):
                if self.kind == SwqosType.JITO:
                    started.set()
                    try: await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        cancelled.set()
                        raise
                return 'offline-signature'
        with patch('src.trading.high_perf_executor.ClientFactory.create_client', return_value=FakeClient(SwqosType.DEFAULT)):
            executor = TradeExecutor(TradeConfig(rpc_url='offline://unused'))
        executor._clients[SwqosType.JITO] = FakeClient(SwqosType.JITO)
        result = await executor.execute(TradeType.BUY, b'fixture', ExecuteOptions(wait_confirmation=False))
        assert result.success and started.is_set()
        outstanding = tuple(executor._pending_submissions)
        executor.close()
        await asyncio.gather(*outstanding, return_exceptions=True)
        await asyncio.sleep(0)
        assert cancelled.is_set() and not executor._pending_submissions
    asyncio.run(run())
