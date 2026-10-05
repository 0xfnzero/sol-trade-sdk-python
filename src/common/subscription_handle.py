"""
Subscription handle for WebSocket and event subscriptions.

Provides unified interface for managing async subscriptions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Set
import logging
import uuid
import json
import aiohttp
from solders.pubkey import Pubkey

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SubscriptionState(Enum):
    """Subscription state."""

    PENDING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    CLOSED = auto()
    ERROR = auto()


@dataclass
class SubscriptionConfig:
    """Configuration for subscription."""

    auto_reconnect: bool = True
    reconnect_delay_ms: int = 1000
    max_reconnect_attempts: int = 10
    heartbeat_interval_ms: int = 30000
    buffer_size: int = 1000


@dataclass
class SubscriptionStats:
    """Subscription statistics."""

    messages_received: int = 0
    messages_dropped: int = 0
    reconnections: int = 0
    errors: int = 0
    last_message_time: Optional[float] = None
    connected_since: Optional[float] = None


class SubscriptionHandle(Generic[T]):
    """
    Handle for managing an async subscription.

    Features:
    - Auto-reconnection
    - Message buffering
    - Backpressure handling
    - Statistics tracking
    """

    def __init__(
        self,
        subscription_id: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        self.subscription_id = subscription_id
        self.config = config or SubscriptionConfig()
        self._state = SubscriptionState.PENDING
        self._callback: Optional[Callable[[T], None]] = None
        self._error_callback: Optional[Callable[[Exception], None]] = None
        if type(self.config.buffer_size) is not int or self.config.buffer_size <= 0:
            raise ValueError("Subscription buffer_size must be positive")
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=self.config.buffer_size)
        self._stats = SubscriptionStats()
        self._task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._close_event = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SubscriptionState:
        """Get current subscription state."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self._state == SubscriptionState.ACTIVE

    def on_message(self, callback: Callable[[T], None]) -> "SubscriptionHandle[T]":
        """Set message callback."""
        self._callback = callback
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> "SubscriptionHandle[T]":
        """Set error callback."""
        self._error_callback = callback
        return self

    async def start(self) -> None:
        """Start the subscription."""
        async with self._lock:
            if self._state == SubscriptionState.CLOSED:
                raise RuntimeError("Subscription is closed")
            if self._task and not self._task.done():
                self._state = SubscriptionState.ACTIVE
                return

            self._state = SubscriptionState.ACTIVE
            self._stats.connected_since = asyncio.get_event_loop().time()
            self._task = asyncio.create_task(self._run())

        logger.debug(f"Subscription {self.subscription_id} started")

    async def stop(self) -> None:
        """Stop the subscription."""
        async with self._lock:
            if self._state == SubscriptionState.CLOSED:
                return

            self._state = SubscriptionState.CLOSED
            self._close_event.set()

            if self._task and self._task is not asyncio.current_task():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

        logger.debug(f"Subscription {self.subscription_id} stopped")

    async def pause(self) -> None:
        """Pause the subscription."""
        async with self._lock:
            if self._state == SubscriptionState.ACTIVE:
                self._state = SubscriptionState.PAUSED

    async def resume(self) -> None:
        """Resume the subscription."""
        async with self._lock:
            if self._state == SubscriptionState.PAUSED:
                self._state = SubscriptionState.ACTIVE

    async def send(self, message: T) -> bool:
        """
        Send message to subscription queue.

        Returns:
            True if message was queued, False if dropped
        """
        if self._state == SubscriptionState.CLOSED:
            return False
        try:
            self._queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            self._stats.messages_dropped += 1
            return False

    def get_stats(self) -> SubscriptionStats:
        """Get subscription statistics."""
        return SubscriptionStats(
            messages_received=self._stats.messages_received,
            messages_dropped=self._stats.messages_dropped,
            reconnections=self._stats.reconnections,
            errors=self._stats.errors,
            last_message_time=self._stats.last_message_time,
            connected_since=self._stats.connected_since,
        )

    async def _run(self) -> None:
        """Main subscription loop."""
        while self._state != SubscriptionState.CLOSED:
            try:
                if self._state == SubscriptionState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                # Wait for message
                message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )

                try:
                    while self._state == SubscriptionState.PAUSED:
                        await asyncio.sleep(0.01)
                    if self._state != SubscriptionState.CLOSED:
                        await self._process_message(message)
                finally:
                    self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._handle_error(e)

    async def _process_message(self, message: T) -> None:
        """Process received message."""
        self._stats.messages_received += 1
        self._stats.last_message_time = asyncio.get_event_loop().time()

        if self._callback:
            try:
                if asyncio.iscoroutinefunction(self._callback):
                    await self._callback(message)
                else:
                    self._callback(message)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def _handle_error(self, error: Exception) -> None:
        """Handle subscription error."""
        self._stats.errors += 1
        self._state = SubscriptionState.ERROR

        logger.error(f"Subscription {self.subscription_id} error: {error}")

        if self._error_callback:
            try:
                if asyncio.iscoroutinefunction(self._error_callback):
                    await self._error_callback(error)
                else:
                    self._error_callback(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")

        # Attempt reconnection
        if (
            self.config.auto_reconnect
            and self._reconnect_attempts < self.config.max_reconnect_attempts
        ):
            self._reconnect_attempts += 1
            self._stats.reconnections += 1

            await asyncio.sleep(self.config.reconnect_delay_ms / 1000)
            self._state = SubscriptionState.ACTIVE
            logger.info(f"Subscription {self.subscription_id} reconnected")
        else:
            self._state = SubscriptionState.CLOSED


class SubscriptionManager:
    """Manager for multiple subscriptions."""

    def __init__(self):
        self._subscriptions: Dict[str, SubscriptionHandle] = {}
        self._lock = asyncio.Lock()

    async def create_subscription(
        self,
        config: Optional[SubscriptionConfig] = None,
        subscription_id: Optional[str] = None,
    ) -> SubscriptionHandle:
        """
        Create a new subscription.

        Args:
            config: Subscription configuration
            subscription_id: Optional subscription ID (generated if not provided)

        Returns:
            New subscription handle
        """
        sub_id = subscription_id or str(uuid.uuid4())

        async with self._lock:
            if sub_id in self._subscriptions:
                raise ValueError("Duplicate subscription ID")
            handle = SubscriptionHandle(sub_id, config)
            self._subscriptions[sub_id] = handle

        return handle

    async def get_subscription(self, subscription_id: str) -> Optional[SubscriptionHandle]:
        """Get subscription by ID."""
        async with self._lock:
            return self._subscriptions.get(subscription_id)

    async def close_subscription(self, subscription_id: str) -> bool:
        """Close a subscription."""
        async with self._lock:
            handle = self._subscriptions.pop(subscription_id, None)

        if handle:
            await handle.stop()
            return True
        return False

    async def close_all(self) -> None:
        """Close all subscriptions."""
        async with self._lock:
            handles = list(self._subscriptions.values())
            self._subscriptions.clear()

        for handle in handles:
            await handle.stop()

    def get_all_stats(self) -> Dict[str, SubscriptionStats]:
        """Get stats for all subscriptions."""
        return {sub_id: handle.get_stats() for sub_id, handle in self._subscriptions.items()}

    def get_active_count(self) -> int:
        """Get number of active subscriptions."""
        return sum(1 for h in self._subscriptions.values() if h.is_active)


class WebSocketSubscription(SubscriptionHandle[Dict[str, Any]]):
    """WebSocket-specific subscription handle."""

    def __init__(
        self,
        subscription_id: str,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        super().__init__(subscription_id, config)
        self.ws_url = ws_url
        self._ws = None
        self._session = None
        self._reader = None
        self._server_id = None
        self._request_id = 0
        self._transport_lock = asyncio.Lock()

    def _request(self):
        name = next(
            (
                kind.__name__
                for kind in (
                    AccountSubscription,
                    ProgramSubscription,
                    SignatureSubscription,
                    LogSubscription,
                    SlotSubscription,
                    RootSubscription,
                    VoteSubscription,
                    BlockSubscription,
                )
                if isinstance(self, kind)
            ),
            "WebSocketSubscription",
        )
        options = {"commitment": "confirmed"}
        if name in ("AccountSubscription", "ProgramSubscription"):
            value = self.account if name == "AccountSubscription" else self.program_id
            return ("account" if name == "AccountSubscription" else "program") + "Subscribe", [
                str(Pubkey.from_bytes(value)),
                {**options, "encoding": "base64"},
            ]
        if name == "SignatureSubscription":
            return "signatureSubscribe", [self.signature, options]
        if name == "LogSubscription":
            return "logsSubscribe", [
                {"mentions": [str(Pubkey.from_bytes(self.mention))]} if self.mention else "all",
                options,
            ]
        methods = {
            "SlotSubscription": "slotSubscribe",
            "RootSubscription": "rootSubscribe",
            "VoteSubscription": "voteSubscribe",
            "BlockSubscription": "blockSubscribe",
        }
        if name not in methods:
            raise ValueError("Use a concrete WebSocket subscription type")
        return methods[name], (
            ["all", {**options, "encoding": "base64", "transactionDetails": "full"}]
            if name == "BlockSubscription"
            else []
        )

    async def _close_transport(self):
        ws, session = self._ws, self._session
        self._ws = self._session = None
        self._server_id = None
        if ws is not None:
            await ws.close()
        if session is not None:
            await session.close()

    async def _open_transport(self):
        method, params = self._request()
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(
                self.ws_url,
                heartbeat=(
                    self.config.heartbeat_interval_ms / 1000
                    if self.config.heartbeat_interval_ms > 0
                    else None
                ),
            )
            self._request_id += 1
            await self._ws.send_json(
                {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
            )
            reply = await self._ws.receive_json(timeout=30)
            if (
                reply.get("id") != self._request_id
                or reply.get("error") is not None
                or type(reply.get("result")) is not int
                or reply["result"] < 0
            ):
                raise ValueError("Invalid subscription acknowledgment")
            self._server_id = reply["result"]
            self._reconnect_attempts = 0
        except BaseException:
            await self._close_transport()
            raise

    async def connect(self) -> None:
        """Open and acknowledge a real Solana WebSocket subscription."""
        async with self._transport_lock:
            if self._state == SubscriptionState.CLOSED:
                raise RuntimeError("Subscription is closed")
            if self._ws is not None:
                return
            await self._open_transport()
            await self.start()
            self._reader = asyncio.create_task(self._receive())

    async def _receive(self):
        while self._state != SubscriptionState.CLOSED:
            try:
                async for message in self._ws:
                    if message.type != aiohttp.WSMsgType.TEXT:
                        if message.type == aiohttp.WSMsgType.ERROR:
                            raise RuntimeError("WebSocket receive failed")
                        continue
                    value = json.loads(message.data)
                    method, _ = self._request()
                    params = value.get("params", {})
                    if (
                        value.get("method") != method.replace("Subscribe", "Notification")
                        or params.get("subscription") != self._server_id
                    ):
                        continue
                    result = params.get("result")
                    await self.send(result)
                    if method == "signatureSubscribe" and not (
                        isinstance(result, dict) and result.get("value") == "receivedSignature"
                    ):
                        await self._queue.join()
                        self._server_id = None
                        await self.stop()
                        return
                if self._state == SubscriptionState.CLOSED:
                    return
                raise RuntimeError("WebSocket connection closed")
            except asyncio.CancelledError:
                return
            except Exception as error:
                await self._close_transport()
                # Retry actual network connection, not just the state flag.
                while self._state != SubscriptionState.CLOSED:
                    await self._handle_error(error)
                    if self._state == SubscriptionState.CLOSED:
                        await self.stop()
                        return
                    try:
                        await self._open_transport()
                        break
                    except asyncio.CancelledError:
                        return
                    except Exception as next_error:
                        error = next_error

    async def stop(self) -> None:
        async with self._transport_lock:
            # Also clean up when the reconnect limit has already marked CLOSED.
            if self._server_id is not None and self._ws is not None and not self._ws.closed:
                method, _ = self._request()
                try:
                    await self._ws.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": self._request_id + 1,
                            "method": method.replace("Subscribe", "Unsubscribe"),
                            "params": [self._server_id],
                        }
                    )
                except (aiohttp.ClientError, RuntimeError):
                    pass
            self._state = SubscriptionState.CLOSED
            self._close_event.set()
            for task in (self._reader, self._task):
                if task is not None and task is not asyncio.current_task():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._reader = self._task = None
            await self._close_transport()

    async def disconnect(self) -> None:
        await self.stop()


class AccountSubscription(WebSocketSubscription):
    """Subscription to account updates."""

    def __init__(
        self,
        account: bytes,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        sub_id = f"account:{account.hex()}"
        super().__init__(sub_id, ws_url, config)
        self.account = account


class ProgramSubscription(WebSocketSubscription):
    """Subscription to program account updates."""

    def __init__(
        self,
        program_id: bytes,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        sub_id = f"program:{program_id.hex()}"
        super().__init__(sub_id, ws_url, config)
        self.program_id = program_id


class SignatureSubscription(WebSocketSubscription):
    """Subscription to signature status updates."""

    def __init__(
        self,
        signature: str,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        sub_id = f"signature:{signature}"
        super().__init__(sub_id, ws_url, config)
        self.signature = signature


class SlotSubscription(WebSocketSubscription):
    """Subscription to slot updates."""

    def __init__(
        self,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        super().__init__("slot", ws_url, config)


class RootSubscription(WebSocketSubscription):
    """Subscription to root slot updates."""

    def __init__(
        self,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        super().__init__("root", ws_url, config)


class VoteSubscription(WebSocketSubscription):
    """Subscription to vote updates."""

    def __init__(
        self,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        super().__init__("vote", ws_url, config)


class BlockSubscription(WebSocketSubscription):
    """Subscription to block updates."""

    def __init__(
        self,
        ws_url: str,
        config: Optional[SubscriptionConfig] = None,
    ):
        super().__init__("block", ws_url, config)


class LogSubscription(WebSocketSubscription):
    """Subscription to transaction logs."""

    def __init__(
        self,
        mention: Optional[bytes] = None,
        ws_url: str = "",
        config: Optional[SubscriptionConfig] = None,
    ):
        sub_id = f"logs:{mention.hex()}" if mention else "logs:all"
        super().__init__(sub_id, ws_url, config)
        self.mention = mention
