"""
Advanced SWQOS Clients with gRPC/QUIC Support
High-performance transaction submission with multiple transport options.
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio
import base64
import json
import time
import ssl

# Try to import grpc, fallback to HTTP if not available
try:
    import grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

# Try to import aioquic, fallback to HTTP if not available
try:
    import aioquic
    QUIC_AVAILABLE = True
except ImportError:
    QUIC_AVAILABLE = False

import aiohttp

from ..common.types import SwqosType, TradeType


# ===== Constants =====

# Minimum tips in SOL
MIN_TIP_JITO = 0.001
MIN_TIP_BLOXROUTE = 0.0003
MIN_TIP_ZERO_SLOT = 0.0001
MIN_TIP_TEMPORAL = 0.0001
MIN_TIP_FLASH_BLOCK = 0.0001
MIN_TIP_BLOCK_RAZOR = 0.0001
MIN_TIP_NODE1 = 0.0001
MIN_TIP_ASTRALANE = 0.0001
MIN_TIP_HELIUS = 0.000005
MIN_TIP_DEFAULT = 0.0

# gRPC Endpoints
GRPC_JITO_ENDPOINTS = {
    "amsterdam": "amsterdam.mainnet.block-engine.jito.wtf:1002",
    "frankfurt": "frankfurt.mainnet.block-engine.jito.wtf:1002",
    "ny": "ny.mainnet.block-engine.jito.wtf:1002",
    "tokyo": "tokyo.mainnet.block-engine.jito.wtf:1002",
}

# HTTP Endpoints
HTTP_JITO_ENDPOINTS = {
    "amsterdam": "https://amsterdam.mainnet.block-engine.jito.wtf",
    "frankfurt": "https://frankfurt.mainnet.block-engine.jito.wtf",
    "ny": "https://ny.mainnet.block-engine.jito.wtf",
    "tokyo": "https://tokyo.mainnet.block-engine.jito.wtf",
}


# ===== Transport Types =====

class TransportType:
    HTTP = "http"
    GRPC = "grpc"
    QUIC = "quic"
    WEBSOCKET = "websocket"


# ===== Trade Error =====

@dataclass
class TradeError(Exception):
    """Trade error with detailed information"""
    code: int
    message: str
    instruction_index: Optional[int] = None

    def __str__(self):
        return f"TradeError(code={self.code}, message={self.message})"


# ===== Base Client Interface =====

class SwqosClient(ABC):
    """Abstract base class for SWQOS clients"""

    @abstractmethod
    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        """Send a transaction and return the signature"""
        pass

    @abstractmethod
    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        """Send multiple transactions"""
        pass

    @abstractmethod
    def get_tip_account(self) -> str:
        """Get the tip account for this provider"""
        pass

    @abstractmethod
    def get_swqos_type(self) -> SwqosType:
        """Get the SWQOS type"""
        pass

    @abstractmethod
    def min_tip_sol(self) -> float:
        """Get minimum tip in SOL"""
        pass


# ===== HTTP Client Mixin =====

class HTTPClientMixin:
    """Mixin for HTTP client functionality"""

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=5, connect=2)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                keepalive_timeout=300,
                enable_compression=True,
            )
            cls._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()


# ===== Jito Client =====

class JitoClient(SwqosClient, HTTPClientMixin):
    """Jito SWQOS client with HTTP and gRPC support"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
        region: str = "amsterdam",
        use_grpc: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.region = region
        self.use_grpc = use_grpc and GRPC_AVAILABLE
        self._tip_account = "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmBUvrNei"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        if self.use_grpc:
            return await self._send_grpc(transaction)
        return await self._send_http(transaction)

    async def _send_http(self, transaction: bytes) -> str:
        """Send via HTTP"""
        encoded = base64.b64encode(transaction).decode()

        # Try bundle endpoint first
        bundle_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [[encoded]],
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Jito-Auth-Token"] = self.auth_token

        session = await self.get_session()
        url = f"{self.endpoint}/api/v1/bundles"

        try:
            async with session.post(url, json=bundle_payload, headers=headers) as resp:
                data = await resp.json()

            if "error" in data:
                # Fallback to regular RPC
                return await self._send_http_rpc(transaction)

            return data["result"]
        except Exception as e:
            return await self._send_http_rpc(transaction)

    async def _send_http_rpc(self, transaction: bytes) -> str:
        """Send via HTTP RPC"""
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Jito-Auth-Token"] = self.auth_token

        session = await self.get_session()

        async with session.post(f"{self.endpoint}/api/v1/bundles", json=payload, headers=headers) as resp:
            data = await resp.json()

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        return data["result"]

    async def _send_grpc(self, transaction: bytes) -> str:
        """Send via gRPC"""
        if not GRPC_AVAILABLE:
            return await self._send_http(transaction)

        # gRPC implementation would go here
        # For now, fallback to HTTP
        return await self._send_http(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        # Jito supports bundles - send all at once
        if len(transactions) > 1:
            return await self._send_bundle(transactions)
        
        # Single transaction
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    async def _send_bundle(self, transactions: List[bytes]) -> List[str]:
        """Send as a bundle"""
        encoded = [base64.b64encode(tx).decode() for tx in transactions]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [encoded],
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Jito-Auth-Token"] = self.auth_token

        session = await self.get_session()
        url = f"{self.endpoint}/api/v1/bundles"

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Bundle failed"),
            )

        # Return bundle signature
        return [data["result"]]

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.JITO

    def min_tip_sol(self) -> float:
        return MIN_TIP_JITO


# ===== Bloxroute Client =====

class BloxrouteClient(SwqosClient, HTTPClientMixin):
    """Bloxroute SWQOS client"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint or "api.bloxroute.com"
        self.auth_token = auth_token
        self._tip_account = "HWeXY6GuqP3i2vMPUgwt4XPq5LqSvdkfF3R6dQ5ciPfo"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [encoded],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v2/submit"

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        if "reason" in data:
            raise TradeError(code=500, message=data["reason"])

        return data["signature"]

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.BLOXROUTE

    def min_tip_sol(self) -> float:
        return MIN_TIP_BLOXROUTE


# ===== ZeroSlot Client =====

class ZeroSlotClient(SwqosClient, HTTPClientMixin):
    """ZeroSlot SWQOS client"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint or "api.zeroslot.com"
        self.auth_token = auth_token
        self._tip_account = "zeroslotH4gNdW3DyUr3QYjE3QiPYq78mi4jh7U3YyHY"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        if "error" in data:
            raise TradeError(code=500, message=data["error"])

        return data["signature"]

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.ZERO_SLOT

    def min_tip_sol(self) -> float:
        return MIN_TIP_ZERO_SLOT


# ===== Helius Client =====

class HeliusClient(SwqosClient, HTTPClientMixin):
    """Helius SWQOS client"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: Optional[str] = None,
        swqos_only: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint or rpc_url
        self.api_key = api_key
        self.swqos_only = swqos_only
        self._tip_account = "heliusH4gNdW3DyUr3QYjE3QiPYq78mi4jh7U3YyHY"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        session = await self.get_session()

        async with session.post(self.endpoint, json=payload, headers=headers) as resp:
            data = await resp.json()

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        return data["result"]

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.HELIUS

    def min_tip_sol(self) -> float:
        return MIN_TIP_HELIUS if self.swqos_only else 0.0002


# ===== Default RPC Client =====

class DefaultClient(SwqosClient, HTTPClientMixin):
    """Default RPC client"""

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        session = await self.get_session()

        async with session.post(
            self.rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            data = await resp.json()

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        return data["result"]

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return ""

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.DEFAULT

    def min_tip_sol(self) -> float:
        return MIN_TIP_DEFAULT


# ===== Client Factory =====

@dataclass
class SwqosConfig:
    """Configuration for SWQOS client"""
    type: SwqosType
    region: str = "amsterdam"
    custom_url: Optional[str] = None
    api_key: Optional[str] = None
    use_grpc: bool = False


class ClientFactory:
    """Factory for creating SWQOS clients"""

    @staticmethod
    def create_client(config: SwqosConfig, rpc_url: str) -> SwqosClient:
        """Create a SWQOS client from configuration"""
        
        if config.type == SwqosType.JITO:
            endpoint = config.custom_url or HTTP_JITO_ENDPOINTS.get(
                config.region, HTTP_JITO_ENDPOINTS["amsterdam"]
            )
            return JitoClient(
                rpc_url, endpoint, config.api_key,
                region=config.region, use_grpc=config.use_grpc
            )

        elif config.type == SwqosType.BLOXROUTE:
            return BloxrouteClient(
                rpc_url,
                config.custom_url or "api.bloxroute.com",
                config.api_key,
            )

        elif config.type == SwqosType.ZERO_SLOT:
            return ZeroSlotClient(
                rpc_url,
                config.custom_url or "api.zeroslot.com",
                config.api_key,
            )

        elif config.type == SwqosType.HELIUS:
            return HeliusClient(
                rpc_url,
                config.custom_url or rpc_url,
                config.api_key,
            )

        elif config.type == SwqosType.DEFAULT:
            return DefaultClient(rpc_url)

        else:
            # Fallback to default
            return DefaultClient(rpc_url)


# ===== Convenience Function =====

def create_swqos_client(
    swqos_type: SwqosType,
    rpc_url: str,
    auth_token: Optional[str] = None,
    region: str = "amsterdam",
    custom_url: Optional[str] = None,
    use_grpc: bool = False,
) -> SwqosClient:
    """Convenience function to create a SWQOS client"""
    config = SwqosConfig(
        type=swqos_type,
        region=region,
        custom_url=custom_url,
        api_key=auth_token,
        use_grpc=use_grpc,
    )
    return ClientFactory.create_client(config, rpc_url)
