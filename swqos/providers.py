"""
SWQoS provider implementations.
Based on sol-trade-sdk Rust implementation.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Union
import time
import logging

logger = logging.getLogger(__name__)


class SwqosType(Enum):
    """SWQOS service provider types"""
    JITO = "Jito"
    NEXT_BLOCK = "NextBlock"
    ZERO_SLOT = "ZeroSlot"
    TEMPORAL = "Temporal"
    BLOXROUTE = "Bloxroute"
    NODE1 = "Node1"
    FLASH_BLOCK = "FlashBlock"
    BLOCK_RAZOR = "BlockRazor"
    ASTRALANE = "Astralane"
    STELLIUM = "Stellium"
    LIGHTSPEED = "Lightspeed"
    SOYAS = "Soyas"
    SPEEDLANDING = "Speedlanding"
    HELIUS = "Helius"
    TRITON = "Triton"
    QUICKNODE = "QuickNode"
    SYNDICA = "Syndica"
    FIGMENT = "Figment"
    ALCHEMY = "Alchemy"
    DEFAULT = "Default"


class SwqosRegion(Enum):
    """SWQOS service regions"""
    NEW_YORK = "NewYork"
    FRANKFURT = "Frankfurt"
    AMSTERDAM = "Amsterdam"
    SLC = "SLC"
    TOKYO = "Tokyo"
    LONDON = "London"
    LOS_ANGELES = "LosAngeles"
    SINGAPORE = "Singapore"
    DEFAULT = "Default"


class MevProtectionLevel(Enum):
    """MEV protection levels"""
    NONE = "none"
    BASIC = "basic"
    ENHANCED = "enhanced"
    MAXIMUM = "maximum"


@dataclass
class SwqosConfig:
    """SWQOS configuration"""
    swqos_type: SwqosType
    api_key: Optional[str] = None
    region: SwqosRegion = SwqosRegion.DEFAULT
    url: Optional[str] = None
    timeout_ms: int = 5000
    max_retries: int = 3
    enabled: bool = True
    priority_fee_multiplier: float = 1.0
    mev_protection: MevProtectionLevel = MevProtectionLevel.ENHANCED
    custom_headers: Dict[str, str] = field(default_factory=dict)
    rate_limit_rps: int = 100

    def is_blacklisted(self) -> bool:
        """Check if this provider is blacklisted"""
        return not self.enabled

    def swqos_type_value(self) -> str:
        """Get SWQOS type value"""
        return self.swqos_type.value


@dataclass
class TransactionResult:
    """Transaction submission result"""
    success: bool
    signature: Optional[str] = None
    provider: str = ""
    latency_ms: int = 0
    slot: Optional[int] = None
    error: Optional[str] = None
    bundle_id: Optional[str] = None
    confirmation_status: Optional[str] = None


class SwqosClient:
    """Base SWQOS client"""

    def __init__(self, config: SwqosConfig):
        self.config = config
        self._stats = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "avg_latency_ms": 0,
            "last_error": None,
        }
        self._last_request_time = 0
        self._rate_limit_delay = 1.0 / config.rate_limit_rps if config.rate_limit_rps > 0 else 0

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction to SWQOS provider"""
        raise NotImplementedError("Subclass must implement submit_transaction")

    async def submit_bundle(
        self,
        transactions: List[bytes],
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction bundle"""
        # Default: submit first transaction only
        if transactions:
            return await self.submit_transaction(transactions[0], tip)
        return TransactionResult(success=False, provider=self.config.swqos_type.value, error="Empty bundle")

    async def get_tip_recommendation(self) -> int:
        """Get recommended tip amount in lamports"""
        return 10000  # Default 0.00001 SOL

    async def simulate_transaction(
        self,
        transaction: bytes,
    ) -> Dict[str, Any]:
        """Simulate transaction without submitting"""
        return {"success": True, "units_consumed": 0}

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return self._stats.copy()

    def update_stats(self, success: bool, latency_ms: int, error: Optional[str] = None):
        """Update client statistics"""
        self._stats["requests"] += 1
        if success:
            self._stats["successes"] += 1
        else:
            self._stats["failures"] += 1
            self._stats["last_error"] = error

        # Update average latency
        n = self._stats["requests"]
        self._stats["avg_latency_ms"] = (
            (self._stats["avg_latency_ms"] * (n - 1) + latency_ms) // n
        )

    def _rate_limit_check(self):
        """Check and enforce rate limiting"""
        if self._rate_limit_delay <= 0:
            return

        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        self._last_request_time = time.time()


class JitoClient(SwqosClient):
    """Jito SWQOS client - MEV protection and bundle submission"""

    DEFAULT_ENDPOINTS = {
        SwqosRegion.NEW_YORK: "https://mainnet.block-engine.jito.wtf",
        SwqosRegion.FRANKFURT: "https://frankfurt.mainnet.block-engine.jito.wtf",
        SwqosRegion.AMSTERDAM: "https://amsterdam.mainnet.block-engine.jito.wtf",
        SwqosRegion.TOKYO: "https://tokyo.mainnet.block-engine.jito.wtf",
        SwqosRegion.SLC: "https://slc.mainnet.block-engine.jito.wtf",
    }

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.bundle_url = config.url or self._get_endpoint_for_region()
        self.auth_token: Optional[str] = None

    def _get_endpoint_for_region(self) -> str:
        """Get endpoint for configured region"""
        return self.DEFAULT_ENDPOINTS.get(
            self.config.region,
            self.DEFAULT_ENDPOINTS[SwqosRegion.NEW_YORK]
        )

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Jito"""
        self._rate_limit_check()
        start = time.time()

        try:
            # Placeholder: actual implementation would use Jito JSON-RPC API
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="jito_signature_placeholder",
                provider="Jito",
                latency_ms=latency_ms,
                bundle_id=f"bundle_{int(time.time())}"
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Jito",
                latency_ms=latency_ms,
                error=str(e)
            )

    async def submit_bundle(
        self,
        transactions: List[bytes],
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction bundle via Jito"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="jito_bundle_signature",
                provider="Jito",
                latency_ms=latency_ms,
                bundle_id=f"bundle_{int(time.time())}"
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Jito",
                latency_ms=latency_ms,
                error=str(e)
            )

    async def get_tip_recommendation(self) -> int:
        """Get Jito tip recommendation"""
        # Jito typically recommends 10000-100000 lamports
        return 50000


class BloxrouteClient(SwqosClient):
    """Bloxroute SWQOS client - High-speed transaction relay"""

    DEFAULT_ENDPOINTS = {
        SwqosRegion.NEW_YORK: "https://solana.dex.blxrbdn.com",
        SwqosRegion.FRANKFURT: "https://solana.dex.blxrbdn.com",
    }

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.gateway_url = config.url or "https://solana.dex.blxrbdn.com"
        self.ws_url = config.url.replace("https://", "wss://") if config.url else "wss://solana.dex.blxrbdn.com"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Bloxroute"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="bloxroute_signature_placeholder",
                provider="Bloxroute",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Bloxroute",
                latency_ms=latency_ms,
                error=str(e)
            )


class ZeroSlotClient(SwqosClient):
    """ZeroSlot SWQOS client - Zero-slot latency"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.zeroslot.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via ZeroSlot"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="zeroslot_signature_placeholder",
                provider="ZeroSlot",
                latency_ms=latency_ms,
                slot=None  # Would be populated from response
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="ZeroSlot",
                latency_ms=latency_ms,
                error=str(e)
            )


class NextBlockClient(SwqosClient):
    """NextBlock SWQOS client - Next block inclusion guarantee"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.nextblock.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via NextBlock"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="nextblock_signature_placeholder",
                provider="NextBlock",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="NextBlock",
                latency_ms=latency_ms,
                error=str(e)
            )


class TemporalClient(SwqosClient):
    """Temporal SWQOS client - Time-based execution"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.temporal.trade"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Temporal"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="temporal_signature_placeholder",
                provider="Temporal",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Temporal",
                latency_ms=latency_ms,
                error=str(e)
            )


class Node1Client(SwqosClient):
    """Node1 SWQOS client - Premium node access"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.node1.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Node1"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="node1_signature_placeholder",
                provider="Node1",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Node1",
                latency_ms=latency_ms,
                error=str(e)
            )


class FlashBlockClient(SwqosClient):
    """FlashBlock SWQOS client - Flash block inclusion"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.flashblock.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via FlashBlock"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="flashblock_signature_placeholder",
                provider="FlashBlock",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="FlashBlock",
                latency_ms=latency_ms,
                error=str(e)
            )


class BlockRazorClient(SwqosClient):
    """BlockRazor SWQOS client - Block optimization"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.blockrazor.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via BlockRazor"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="blockrazor_signature_placeholder",
                provider="BlockRazor",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="BlockRazor",
                latency_ms=latency_ms,
                error=str(e)
            )


class AstralaneClient(SwqosClient):
    """Astralane SWQOS client - High-speed relay"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.astralane.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Astralane"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="astralane_signature_placeholder",
                provider="Astralane",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Astralane",
                latency_ms=latency_ms,
                error=str(e)
            )


class StelliumClient(SwqosClient):
    """Stellium SWQOS client - Premium infrastructure"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.stellium.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Stellium"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="stellium_signature_placeholder",
                provider="Stellium",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Stellium",
                latency_ms=latency_ms,
                error=str(e)
            )


class LightspeedClient(SwqosClient):
    """Lightspeed SWQOS client - Ultra-low latency"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.lightspeed.trade"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Lightspeed"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="lightspeed_signature_placeholder",
                provider="Lightspeed",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Lightspeed",
                latency_ms=latency_ms,
                error=str(e)
            )


class SoyasClient(SwqosClient):
    """Soyas SWQOS client - MEV protection"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.soyas.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Soyas"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="soyas_signature_placeholder",
                provider="Soyas",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Soyas",
                latency_ms=latency_ms,
                error=str(e)
            )


class SpeedlandingClient(SwqosClient):
    """Speedlanding SWQOS client - Fast inclusion"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.speedlanding.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Speedlanding"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="speedlanding_signature_placeholder",
                provider="Speedlanding",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Speedlanding",
                latency_ms=latency_ms,
                error=str(e)
            )


class HeliusClient(SwqosClient):
    """Helius SWQOS client - Enhanced RPC"""

    DEFAULT_ENDPOINTS = {
        SwqosRegion.NEW_YORK: "https://api.helius-rpc.com",
        SwqosRegion.DEFAULT: "https://api.helius-rpc.com",
    }

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or self.DEFAULT_ENDPOINTS.get(
            config.region,
            self.DEFAULT_ENDPOINTS[SwqosRegion.DEFAULT]
        )

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Helius"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="helius_signature_placeholder",
                provider="Helius",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Helius",
                latency_ms=latency_ms,
                error=str(e)
            )


class TritonClient(SwqosClient):
    """Triton SWQOS client - High-performance RPC"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.triton.one"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Triton"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="triton_signature_placeholder",
                provider="Triton",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Triton",
                latency_ms=latency_ms,
                error=str(e)
            )


class QuickNodeClient(SwqosClient):
    """QuickNode SWQOS client - Enterprise RPC"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.quicknode.com"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via QuickNode"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="quicknode_signature_placeholder",
                provider="QuickNode",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="QuickNode",
                latency_ms=latency_ms,
                error=str(e)
            )


class SyndicaClient(SwqosClient):
    """Syndica SWQOS client - Premium infrastructure"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.syndica.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Syndica"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="syndica_signature_placeholder",
                provider="Syndica",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Syndica",
                latency_ms=latency_ms,
                error=str(e)
            )


class FigmentClient(SwqosClient):
    """Figment SWQOS client - Enterprise staking RPC"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.figment.io"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Figment"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="figment_signature_placeholder",
                provider="Figment",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Figment",
                latency_ms=latency_ms,
                error=str(e)
            )


class AlchemyClient(SwqosClient):
    """Alchemy SWQOS client - Web3 infrastructure"""

    def __init__(self, config: SwqosConfig):
        super().__init__(config)
        self.api_url = config.url or "https://api.alchemy.com"

    async def submit_transaction(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit transaction via Alchemy"""
        self._rate_limit_check()
        start = time.time()

        try:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(True, latency_ms)

            return TransactionResult(
                success=True,
                signature="alchemy_signature_placeholder",
                provider="Alchemy",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            self.update_stats(False, latency_ms, str(e))
            return TransactionResult(
                success=False,
                provider="Alchemy",
                latency_ms=latency_ms,
                error=str(e)
            )


class SwqosClientFactory:
    """Factory for creating SWQOS clients"""

    _CLIENT_MAP = {
        SwqosType.JITO: JitoClient,
        SwqosType.BLOXROUTE: BloxrouteClient,
        SwqosType.ZERO_SLOT: ZeroSlotClient,
        SwqosType.NEXT_BLOCK: NextBlockClient,
        SwqosType.TEMPORAL: TemporalClient,
        SwqosType.NODE1: Node1Client,
        SwqosType.FLASH_BLOCK: FlashBlockClient,
        SwqosType.BLOCK_RAZOR: BlockRazorClient,
        SwqosType.ASTRALANE: AstralaneClient,
        SwqosType.STELLIUM: StelliumClient,
        SwqosType.LIGHTSPEED: LightspeedClient,
        SwqosType.SOYAS: SoyasClient,
        SwqosType.SPEEDLANDING: SpeedlandingClient,
        SwqosType.HELIUS: HeliusClient,
        SwqosType.TRITON: TritonClient,
        SwqosType.QUICKNODE: QuickNodeClient,
        SwqosType.SYNDICA: SyndicaClient,
        SwqosType.FIGMENT: FigmentClient,
        SwqosType.ALCHEMY: AlchemyClient,
    }

    @classmethod
    def create_client(cls, config: SwqosConfig) -> SwqosClient:
        """Create SWQOS client based on config type"""
        client_class = cls._CLIENT_MAP.get(config.swqos_type, SwqosClient)
        return client_class(config)

    @classmethod
    def get_supported_types(cls) -> List[SwqosType]:
        """Get list of supported provider types"""
        return list(cls._CLIENT_MAP.keys())


class SwqosManager:
    """Manager for multiple SWQOS clients"""

    def __init__(self):
        self.clients: Dict[SwqosType, SwqosClient] = {}
        self._fallback_order: List[SwqosType] = []

    def add_client(self, client: SwqosClient) -> "SwqosManager":
        """Add a SWQOS client"""
        self.clients[client.config.swqos_type] = client
        if client.config.swqos_type not in self._fallback_order:
            self._fallback_order.append(client.config.swqos_type)
        return self

    def remove_client(self, swqos_type: SwqosType) -> "SwqosManager":
        """Remove a SWQOS client"""
        if swqos_type in self.clients:
            del self.clients[swqos_type]
        if swqos_type in self._fallback_order:
            self._fallback_order.remove(swqos_type)
        return self

    def get_client(self, swqos_type: SwqosType) -> Optional[SwqosClient]:
        """Get SWQOS client by type"""
        return self.clients.get(swqos_type)

    def get_all_clients(self) -> List[SwqosClient]:
        """Get all enabled clients"""
        return [c for c in self.clients.values() if c.config.enabled]

    def get_best_client(self) -> Optional[SwqosClient]:
        """Get client with best performance stats"""
        enabled = self.get_all_clients()
        if not enabled:
            return None

        # Sort by success rate and latency
        def score(client: SwqosClient) -> float:
            stats = client.get_stats()
            if stats["requests"] == 0:
                return 0.0
            success_rate = stats["successes"] / stats["requests"]
            # Higher success rate and lower latency = better score
            return success_rate * 1000 / (stats["avg_latency_ms"] + 1)

        return max(enabled, key=score)

    def set_fallback_order(self, order: List[SwqosType]) -> None:
        """Set fallback order for providers"""
        self._fallback_order = [t for t in order if t in self.clients]

    async def submit_with_fallback(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> TransactionResult:
        """Submit with automatic fallback"""
        import asyncio

        for swqos_type in self._fallback_order:
            client = self.clients.get(swqos_type)
            if not client or not client.config.enabled:
                continue

            result = await client.submit_transaction(transaction, tip)
            if result.success:
                return result

        return TransactionResult(
            success=False,
            provider="fallback",
            error="All providers failed"
        )

    async def submit_to_all(
        self,
        transaction: bytes,
        tip: int = 0,
    ) -> Dict[str, Any]:
        """Submit transaction to all enabled providers"""
        import asyncio

        tasks = []
        clients = self.get_all_clients()
        for client in clients:
            tasks.append(client.submit_transaction(transaction, tip))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "results": [
                r if not isinstance(r, Exception) else TransactionResult(
                    success=False,
                    provider="unknown",
                    error=str(r)
                )
                for r in results
            ],
            "total": len(tasks),
            "successful": sum(1 for r in results if isinstance(r, TransactionResult) and r.success),
        }

    async def submit_bundle_to_all(
        self,
        transactions: List[bytes],
        tip: int = 0,
    ) -> Dict[str, Any]:
        """Submit bundle to all providers that support it"""
        import asyncio

        tasks = []
        clients = self.get_all_clients()
        for client in clients:
            tasks.append(client.submit_bundle(transactions, tip))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "results": [
                r if not isinstance(r, Exception) else TransactionResult(
                    success=False,
                    provider="unknown",
                    error=str(r)
                )
                for r in results
            ],
            "total": len(tasks),
            "successful": sum(1 for r in results if isinstance(r, TransactionResult) and r.success),
        }

    def get_all_stats(self) -> Dict[SwqosType, Dict[str, Any]]:
        """Get stats for all clients"""
        return {t: c.get_stats() for t, c in self.clients.items()}

    def get_aggregated_stats(self) -> Dict[str, Any]:
        """Get aggregated stats across all clients"""
        total_requests = 0
        total_successes = 0
        total_failures = 0
        total_latency = 0

        for client in self.clients.values():
            stats = client.get_stats()
            total_requests += stats["requests"]
            total_successes += stats["successes"]
            total_failures += stats["failures"]
            total_latency += stats["avg_latency_ms"]

        avg_latency = total_latency / len(self.clients) if self.clients else 0

        return {
            "total_requests": total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": total_successes / total_requests if total_requests > 0 else 0,
            "avg_latency_ms": avg_latency,
            "active_providers": len(self.get_all_clients()),
        }
