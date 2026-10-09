import asyncio
from unittest.mock import patch
import pytest
from src.common.types import SwqosType, TradeType
from src.trading.high_perf_executor import TradeExecutor, TradeConfig, ExecuteOptions
from src.swqos.clients import DefaultClient

class Client:
    def __init__(self, action, kind=SwqosType.DEFAULT): self.action, self.kind = action, kind
    async def send_transaction(self, kind, tx, wait):
        assert wait is False
        return await self.action()
    def get_swqos_type(self): return self.kind

def executor(clients):
    result = TradeExecutor(TradeConfig(rpc_url='http://offline.invalid'))
    result._clients = clients
    return result

@pytest.mark.parametrize('parallel', [True, False])
def test_execution_deadline_includes_rate_wait_and_hanging_lane(parallel):
    async def run():
        async def hang(): await asyncio.Event().wait()
        ex = executor({SwqosType.DEFAULT: Client(hang)})
        for rate_wait in [False, True]:
            if rate_wait:
                ex._rate_limiter.wait_async = hang
            result = await asyncio.wait_for(ex.execute(TradeType.BUY, b'', ExecuteOptions(timeout_ms=10, parallel_submit=parallel)), .3)
            assert not result.success and 'deadline' in result.error.lower()
            await asyncio.sleep(0)
            assert not ex._pending_submissions
    asyncio.run(run())


def test_sequential_clients_snapshot_survives_public_mutation():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def fail():
            entered.set(); await release.wait(); raise RuntimeError('rejected')
        async def ack(): return 'ack'
        ex=executor({SwqosType.DEFAULT: Client(fail), SwqosType.JITO: Client(ack, SwqosType.JITO)})
        task=asyncio.create_task(ex.execute(TradeType.BUY,b'',ExecuteOptions(parallel_submit=False, wait_confirmation=False)))
        await entered.wait(); ex.remove_client(SwqosType.JITO); release.set()
        result=await task
        assert result.success and result.signature=='ack' and result.swqos_type==SwqosType.JITO
    asyncio.run(run())

@pytest.mark.parametrize('parallel', [True, False])
def test_acknowledgement_survives_confirmation_deadline(parallel):
    async def run():
        async def ack(): return 'ack'
        async def hang(*args, **kwargs): await asyncio.Event().wait()
        ex=executor({SwqosType.JITO: Client(ack, SwqosType.JITO)})
        with patch('src.trading.high_perf_executor.poll_for_confirmation_error', hang):
            result=await ex.execute(TradeType.BUY,b'',ExecuteOptions(timeout_ms=10,parallel_submit=parallel))
        assert not result.success and result.signature=='ack'
        assert result.swqos_type==SwqosType.JITO and result.confirmed_at is None
        assert 'deadline' in result.error.lower()
    asyncio.run(run())

@pytest.mark.parametrize('confirmed', [True, False])
def test_confirmation_is_observed_and_failure_not_retried(confirmed):
    async def run():
        count=0
        async def ack():
            nonlocal count
            count+=1;return 'ack'
        ex=executor({SwqosType.DEFAULT: Client(ack)})
        with patch('src.trading.high_perf_executor.poll_for_confirmation_error', return_value=(confirmed, None if confirmed else 'on-chain error')) as observe:
            result=await ex.execute(TradeType.BUY,b'',ExecuteOptions(parallel_submit=False))
        assert result.success==confirmed and count==1 and observe.await_count==1
        assert (result.confirmed_at is not None)==confirmed
        result=await ex.execute(TradeType.BUY,b'',ExecuteOptions(wait_confirmation=False))
        assert result.success and result.confirmed_at is None and result.confirmation_time_ms is None
    asyncio.run(run())


def test_default_client_wait_true_observes_actual_status():
    class Response:
        status=200
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def json(self): return {'result':'ack'}
    class Session:
        def post(self,*a,**kw): return Response()
    async def run():
        client=DefaultClient('offline://unused')
        with patch.object(client,'get_session',return_value=Session()), patch('src.trading.executor.poll_for_confirmation_error',return_value=(True,None)) as observe:
            assert await client.send_transaction(TradeType.BUY,b'',True)=='ack'
            observe.assert_awaited_once_with('offline://unused','ack')
            observe.reset_mock()
            await client.send_transaction(TradeType.BUY,b'',False)
            observe.assert_not_awaited()
    asyncio.run(run())

@pytest.mark.parametrize('failed', [True,False])
def test_default_client_uses_status_rpc_only_when_requested(failed):
    methods=[]
    class Response:
        status=200
        def __init__(self,data): self.data=data
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def json(self): return self.data
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        def post(self,url,*,json,**kw):
            method=json['method'];methods.append(method)
            if method=='sendTransaction': return Response({'result':'ack'})
            if method=='getTransaction': return Response({'result':None})
            return Response({'result':{'value':[{'err':'BlockhashNotFound' if failed else None,'confirmationStatus':'confirmed'}]}})
    async def run():
        client=DefaultClient('offline://unused')
        with patch.object(client,'get_session',return_value=Session()),patch('aiohttp.ClientSession',Session):
            assert await client.send_transaction(TradeType.BUY,b'',False)=='ack'
            assert methods==['sendTransaction']
            if failed:
                with pytest.raises(Exception) as raised: await client.send_transaction(TradeType.BUY,b'',True)
                assert raised.value.signature=='ack'
            else:
                assert await client.send_transaction(TradeType.BUY,b'',True)=='ack'
            assert methods[1:3]==['sendTransaction','getSignatureStatuses']
    asyncio.run(run())
