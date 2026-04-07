"""
SWQOS Clients for Sol Trade SDK
Implements various SWQOS (Solana Write Queue Operating System) providers.
"""

import asyncio
import base64
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

import aiohttp

from ..common.types import SwqosType, SwqosRegion, TradeType


# ===== Constants =====

# Minimum tips in SOL for each provider
MIN_TIP_JITO = 0.001
MIN_TIP_BLOXROUTE = 0.0003
MIN_TIP_ZERO_SLOT = 0.0001
MIN_TIP_TEMPORAL = 0.0001
MIN_TIP_FLASH_BLOCK = 0.0001
MIN_TIP_BLOCK_RAZOR = 0.0001
MIN_TIP_NODE1 = 0.0001
MIN_TIP_ASTRALANE = 0.0001
MIN_TIP_HELIUS = 0.000005  # SWQOS-only mode
MIN_TIP_DEFAULT = 0.0

# Endpoints for each provider by region
JITO_ENDPOINTS = {
    SwqosRegion.NEW_YORK: "amsterdam.mainnet.block-engine.jito.wtf",
    SwqosRegion.FRANKFURT: "frankfurt.mainnet.block-engine.jito.wtf",
    SwqosRegion.AMSTERDAM: "amsterdam.mainnet.block-engine.jito.wtf",
    SwqosRegion.TOKYO: "tokyo.mainnet.block-engine.jito.wtf",
}


# ===== Error Handling =====

@dataclass
class TradeError(Exception):
    """Trade error with detailed information"""
    code: int
    message: str
    instruction_index: Optional[int] = None

    def __str__(self):
        return f"TradeError(code={self.code}, message={self.message})"


# ===== Interfaces =====

class SwqosClient(ABC):
    """Abstract base class for SWQOS clients"""

    @abstractmethod
    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        """
        Send a transaction via the SWQOS provider.
        
        Args:
            trade_type: Type of trade (buy/sell)
            transaction: Raw transaction bytes
            wait_confirmation: Whether to wait for confirmation
        
        Returns:
            Transaction signature as base58 string
        """
        pass

    @abstractmethod
    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        """Send multiple transactions via the SWQOS provider"""
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


# ===== HTTP Client Base =====

class HTTPClientMixin:
    """Mixin for HTTP client functionality"""

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=3)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=4,
                keepalive_timeout=300,
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
    """Jito SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._tip_account = "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmBUvrNei"

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
        url = f"https://{self.endpoint}/api/v1/bundles"

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Jito-Auth-Token"] = self.auth_token

        async with session.post(url, json=payload, headers=headers) as resp:
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
        return SwqosType.JITO

    def min_tip_sol(self) -> float:
        return MIN_TIP_JITO


# ===== Bloxroute Client =====

class BloxrouteClient(SwqosClient, HTTPClientMixin):
    """Bloxroute SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
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

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v2/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

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
    """ZeroSlot SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
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

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

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


# ===== Temporal Client =====

class TemporalClient(SwqosClient, HTTPClientMixin):
    """Temporal SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._tip_account = "temporalGxiRP8dLKPhUT6vJ6Qnq1RmqNGW8mVu8mPTwogbNX7j"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

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
        return SwqosType.TEMPORAL

    def min_tip_sol(self) -> float:
        return MIN_TIP_TEMPORAL


# ===== FlashBlock Client =====

class FlashBlockClient(SwqosClient, HTTPClientMixin):
    """FlashBlock SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._tip_account = "flashblockHjE4frLuq8iFzboHy5AW8VZMo7mDhjt4VhV"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.auth_token or "",
        }

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
        return SwqosType.FLASH_BLOCK

    def min_tip_sol(self) -> float:
        return MIN_TIP_FLASH_BLOCK


# ===== Helius Client =====

class HeliusClient(SwqosClient, HTTPClientMixin):
    """Helius SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: Optional[str] = None,
        swqos_only: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
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

        session = await self.get_session()

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

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
        if self.swqos_only:
            return MIN_TIP_HELIUS
        return 0.0002


# ===== Default RPC Client =====

class DefaultClient(SwqosClient, HTTPClientMixin):
    """Default RPC client implementation"""

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

        headers = {"Content-Type": "application/json"}

        async with session.post(self.rpc_url, json=payload, headers=headers) as resp:
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


# ===== Additional SWQOS Clients =====

class Node1Client(SwqosClient, HTTPClientMixin):
    """Node1 SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._tip_account = "node1H4gNdW3DyUr3QYjE3QiPYq78mi4jh7U3YyHY"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

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
        return SwqosType.NODE1

    def min_tip_sol(self) -> float:
        return MIN_TIP_NODE1


class BlockRazorClient(SwqosClient, HTTPClientMixin):
    """BlockRazor SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
        mev_protection: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.mev_protection = mev_protection
        self._tip_account = "blockrazorH4gNdW3DyUr3QYjE3QiPYq78mi4jh7U3YyHY"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        session = await self.get_session()
        # Use sandwichMitigation mode for MEV protection
        mode = "sandwichMitigation" if self.mev_protection else "fast"
        url = f"https://{self.endpoint}/api/v1/submit?mode={mode}"

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.auth_token or "",
        }

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
        return SwqosType.BLOCK_RAZOR

    def min_tip_sol(self) -> float:
        return MIN_TIP_BLOCK_RAZOR


class AstralaneClient(SwqosClient, HTTPClientMixin):
    """Astralane SWQOS client implementation"""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._tip_account = "astralaneH4gNdW3DyUr3QYjE3QiPYq78mi4jh7U3YyHY"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transaction": encoded}

        session = await self.get_session()
        url = f"https://{self.endpoint}/api/v1/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

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
        return SwqosType.ASTRALANE

    def min_tip_sol(self) -> float:
        return MIN_TIP_ASTRALANE


# ===== Client Factory =====

@dataclass
class SwqosConfig:
    """Configuration for SWQOS client"""
    type: SwqosType
    region: SwqosRegion = SwqosRegion.DEFAULT
    custom_url: Optional[str] = None
    api_key: Optional[str] = None
    mev_protection: bool = False


class ClientFactory:
    """Factory for creating SWQOS clients"""

    @staticmethod
    def create_client(config: SwqosConfig, rpc_url: str) -> SwqosClient:
        """Create a SWQOS client from configuration"""
        if config.type == SwqosType.JITO:
            endpoint = config.custom_url or JITO_ENDPOINTS.get(
                config.region, "amsterdam.mainnet.block-engine.jito.wtf"
            )
            return JitoClient(rpc_url, endpoint, config.api_key)

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

        elif config.type == SwqosType.TEMPORAL:
            return TemporalClient(
                rpc_url,
                config.custom_url or "api.temporal.com",
                config.api_key,
            )

        elif config.type == SwqosType.FLASH_BLOCK:
            return FlashBlockClient(
                rpc_url,
                config.custom_url or "api.flashblock.com",
                config.api_key,
            )

        elif config.type == SwqosType.HELIUS:
            return HeliusClient(
                rpc_url,
                config.custom_url or rpc_url,
                config.api_key,
                swqos_only=False,
            )

        elif config.type == SwqosType.NODE1:
            return Node1Client(
                rpc_url,
                config.custom_url or "api.node1.com",
                config.api_key,
            )

        elif config.type == SwqosType.BLOCK_RAZOR:
            return BlockRazorClient(
                rpc_url,
                config.custom_url or "api.blockrazor.com",
                config.api_key,
                mev_protection=config.mev_protection,
            )

        elif config.type == SwqosType.ASTRALANE:
            # MEV protection for Astralane: use port 9000 endpoint
            if config.mev_protection and config.custom_url is None:
                endpoint = "api-mev.astralane.com"  # port 9000 MEV endpoint
            else:
                endpoint = config.custom_url or "api.astralane.com"
            return AstralaneClient(
                rpc_url,
                endpoint,
                config.api_key,
            )

        elif config.type == SwqosType.DEFAULT:
            return DefaultClient(rpc_url)

        else:
            raise ValueError(f"Unsupported SWQOS type: {config.type}")


# ===== Convenience function for creating clients =====

def create_swqos_client(
    swqos_type: SwqosType,
    rpc_url: str,
    auth_token: Optional[str] = None,
    region: SwqosRegion = SwqosRegion.DEFAULT,
    custom_url: Optional[str] = None,
    mev_protection: bool = False,
) -> SwqosClient:
    """Convenience function to create a SWQOS client"""
    config = SwqosConfig(
        type=swqos_type,
        region=region,
        custom_url=custom_url,
        api_key=auth_token,
        mev_protection=mev_protection,
    )
    return ClientFactory.create_client(config, rpc_url)
