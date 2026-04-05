"""
High-Performance RPC Client for Sol Trade SDK
Provides async and sync methods for Solana RPC communication.
"""

from typing import Any, Optional, Dict, List, Union
from dataclasses import dataclass, field
import json
import asyncio
import aiohttp
import requests
from contextlib import asynccontextmanager
import time

from ..cache.cache import TTLCache, cached


@dataclass
class RPCConfig:
    """RPC client configuration"""
    endpoint: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.1
    headers: Dict[str, str] = field(default_factory=dict)
    max_connections: int = 100
    max_keepalive: int = 20


@dataclass
class AccountInfo:
    """Account information"""
    lamports: int
    data: bytes
    owner: str
    executable: bool
    rent_epoch: int


@dataclass
class BlockhashResult:
    """Latest blockhash result"""
    blockhash: str
    last_valid_block_height: int


@dataclass
class SignatureStatus:
    """Transaction signature status"""
    slot: int
    confirmations: Optional[int]
    err: Optional[Dict]
    confirmation_status: str


class RPCError(Exception):
    """RPC error"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"RPC Error {code}: {message}")


class RPCClient:
    """
    High-performance synchronous RPC client.
    
    Features:
    - Connection pooling
    - Request caching
    - Automatic retries
    - Statistics tracking
    """

    def __init__(self, config: RPCConfig):
        self._config = config
        self._session = requests.Session()
        self._request_id = 0
        self._requests_count = 0
        self._error_count = 0
        self._total_latency = 0.0

        # Configure session
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=config.max_connections,
            pool_maxsize=config.max_keepalive,
            max_retries=max_retries,
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._session.headers.update({
            "Content-Type": "application/json",
            **config.headers,
        })

        # Caches
        self._blockhash_cache = TTLCache[str, str](ttl=2.0)
        self._account_cache = TTLCache[str, AccountInfo](ttl=10.0)

    def _make_request(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """Make a JSON-RPC request"""
        self._request_id += 1
        self._requests_count += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or [],
        }

        start = time.time()
        try:
            response = self._session.post(
                self._config.endpoint,
                json=payload,
                timeout=self._config.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                self._error_count += 1
                raise RPCError(
                    data["error"].get("code", -1),
                    data["error"].get("message", "Unknown error"),
                )

            return data.get("result")

        except requests.RequestException as e:
            self._error_count += 1
            raise RPCError(-1, str(e))
        finally:
            self._total_latency += time.time() - start

    # ===== Core Methods =====

    def get_balance(self, pubkey: str, commitment: str = "confirmed") -> int:
        """Get account balance"""
        result = self._make_request(
            "getBalance",
            [pubkey, {"commitment": commitment}],
        )
        return result.get("value", 0)

    def get_account_info(
        self,
        pubkey: str,
        encoding: str = "base64",
        commitment: str = "confirmed",
    ) -> Optional[AccountInfo]:
        """Get account information"""
        # Check cache
        cached = self._account_cache.get(pubkey)
        if cached:
            return cached

        result = self._make_request(
            "getAccountInfo",
            [pubkey, {"encoding": encoding, "commitment": commitment}],
        )

        if result.get("value") is None:
            return None

        value = result["value"]
        data = value.get("data", ["", "base64"])
        if isinstance(data, list) and len(data) > 0:
            import base64
            raw_data = base64.b64decode(data[0]) if data[0] else b""
        else:
            raw_data = b""

        info = AccountInfo(
            lamports=value.get("lamports", 0),
            data=raw_data,
            owner=value.get("owner", ""),
            executable=value.get("executable", False),
            rent_epoch=value.get("rentEpoch", 0),
        )

        self._account_cache.set(pubkey, info)
        return info

    def get_multiple_accounts(
        self,
        pubkeys: List[str],
        encoding: str = "base64",
        commitment: str = "confirmed",
    ) -> List[Optional[AccountInfo]]:
        """Get multiple accounts info"""
        result = self._make_request(
            "getMultipleAccounts",
            [pubkeys, {"encoding": encoding, "commitment": commitment}],
        )

        accounts = []
        for value in result.get("value", []):
            if value is None:
                accounts.append(None)
                continue

            data = value.get("data", ["", "base64"])
            if isinstance(data, list) and len(data) > 0:
                import base64
                raw_data = base64.b64decode(data[0]) if data[0] else b""
            else:
                raw_data = b""

            accounts.append(AccountInfo(
                lamports=value.get("lamports", 0),
                data=raw_data,
                owner=value.get("owner", ""),
                executable=value.get("executable", False),
                rent_epoch=value.get("rentEpoch", 0),
            ))

        return accounts

    def get_latest_blockhash(self, commitment: str = "confirmed") -> BlockhashResult:
        """Get the latest blockhash"""
        # Check cache
        cached = self._blockhash_cache.get("latest")
        if cached:
            return BlockhashResult(
                blockhash=cached,
                last_valid_block_height=0,  # Approximate
            )

        result = self._make_request(
            "getLatestBlockhash",
            [{"commitment": commitment}],
        )

        blockhash = BlockhashResult(
            blockhash=result["blockhash"],
            last_valid_block_height=result["lastValidBlockHeight"],
        )

        self._blockhash_cache.set("latest", blockhash.blockhash)
        return blockhash

    def get_signature_statuses(
        self,
        signatures: List[str],
        search_transaction_history: bool = False,
    ) -> List[Optional[SignatureStatus]]:
        """Get signature statuses"""
        result = self._make_request(
            "getSignatureStatuses",
            [signatures, {"searchTransactionHistory": search_transaction_history}],
        )

        statuses = []
        for value in result.get("value", []):
            if value is None:
                statuses.append(None)
                continue

            statuses.append(SignatureStatus(
                slot=value.get("slot", 0),
                confirmations=value.get("confirmations"),
                err=value.get("err"),
                confirmation_status=value.get("confirmationStatus", "processed"),
            ))

        return statuses

    def send_transaction(
        self,
        transaction: bytes,
        skip_preflight: bool = False,
        preflight_commitment: str = "confirmed",
    ) -> str:
        """Send a transaction"""
        import base64
        encoded = base64.b64encode(transaction).decode()

        result = self._make_request(
            "sendTransaction",
            [encoded, {
                "encoding": "base64",
                "skipPreflight": skip_preflight,
                "preflightCommitment": preflight_commitment,
            }],
        )

        return result

    def simulate_transaction(
        self,
        transaction: bytes,
        sig_verify: bool = False,
    ) -> Dict[str, Any]:
        """Simulate a transaction"""
        import base64
        encoded = base64.b64encode(transaction).decode()

        result = self._make_request(
            "simulateTransaction",
            [encoded, {
                "encoding": "base64",
                "sigVerify": sig_verify,
            }],
        )

        return result.get("value", {})

    # ===== Utility Methods =====

    def close(self) -> None:
        """Close the client"""
        self._session.close()

    @property
    def stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        avg_latency = (
            self._total_latency / self._requests_count
            if self._requests_count > 0 else 0
        )
        return {
            "requests": self._requests_count,
            "errors": self._error_count,
            "avg_latency_ms": avg_latency * 1000,
        }


class AsyncRPCClient:
    """
    High-performance async RPC client.
    
    Features:
    - Async I/O
    - Connection pooling
    - Concurrent requests
    """

    def __init__(self, config: RPCConfig):
        self._config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_id = 0
        self._requests_count = 0
        self._error_count = 0
        self._total_latency = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            connector = aiohttp.TCPConnector(
                limit=self._config.max_connections,
                limit_per_host=self._config.max_keepalive,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "Content-Type": "application/json",
                    **self._config.headers,
                },
            )
        return self._session

    async def _make_request(self, method: str, params: List[Any] = None) -> Any:
        """Make an async JSON-RPC request"""
        self._request_id += 1
        self._requests_count += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or [],
        }

        start = time.time()
        try:
            session = await self._get_session()
            async with session.post(
                self._config.endpoint,
                json=payload,
            ) as response:
                data = await response.json()

                if "error" in data:
                    self._error_count += 1
                    raise RPCError(
                        data["error"].get("code", -1),
                        data["error"].get("message", "Unknown error"),
                    )

                return data.get("result")

        except aiohttp.ClientError as e:
            self._error_count += 1
            raise RPCError(-1, str(e))
        finally:
            self._total_latency += time.time() - start

    async def get_balance(self, pubkey: str, commitment: str = "confirmed") -> int:
        """Get account balance"""
        result = await self._make_request(
            "getBalance",
            [pubkey, {"commitment": commitment}],
        )
        return result.get("value", 0)

    async def get_latest_blockhash(self, commitment: str = "confirmed") -> BlockhashResult:
        """Get the latest blockhash"""
        result = await self._make_request(
            "getLatestBlockhash",
            [{"commitment": commitment}],
        )
        return BlockhashResult(
            blockhash=result["blockhash"],
            last_valid_block_height=result["lastValidBlockHeight"],
        )

    async def send_transaction(self, transaction: bytes, **kwargs) -> str:
        """Send a transaction"""
        import base64
        encoded = base64.b64encode(transaction).decode()
        return await self._make_request(
            "sendTransaction",
            [encoded, {"encoding": "base64", **kwargs}],
        )

    async def close(self) -> None:
        """Close the client"""
        if self._session and not self._session.closed:
            await self._session.close()

    @asynccontextmanager
    async def session(self):
        """Context manager for the client"""
        try:
            yield self
        finally:
            await self.close()

    @property
    def stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        avg_latency = (
            self._total_latency / self._requests_count
            if self._requests_count > 0 else 0
        )
        return {
            "requests": self._requests_count,
            "errors": self._error_count,
            "avg_latency_ms": avg_latency * 1000,
        }
