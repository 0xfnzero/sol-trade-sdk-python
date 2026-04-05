"""
Middleware trait definitions.
Based on sol-trade-sdk Rust implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class InstructionMiddleware(ABC):
    """Instruction middleware trait for processing instructions."""

    @abstractmethod
    def name(self) -> str:
        """Middleware name"""
        pass

    @abstractmethod
    def process_protocol_instructions(
        self,
        protocol_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """
        Process protocol instructions.

        Args:
            protocol_instructions: Current instruction list
            protocol_name: Protocol name
            is_buy: Whether the transaction is a buy transaction

        Returns:
            Modified instruction list
        """
        pass

    @abstractmethod
    def process_full_instructions(
        self,
        full_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """
        Process full instructions.

        Args:
            full_instructions: Current instruction list
            protocol_name: Protocol name
            is_buy: Whether the transaction is a buy transaction

        Returns:
            Modified instruction list
        """
        pass

    def clone(self) -> "InstructionMiddleware":
        """Clone middleware"""
        return self


class MiddlewareManager:
    """Middleware manager for applying multiple middlewares."""

    def __init__(self):
        self.middlewares: List[InstructionMiddleware] = []

    def add_middleware(self, middleware: InstructionMiddleware) -> "MiddlewareManager":
        """Add middleware to the chain"""
        self.middlewares.append(middleware)
        return self

    def apply_middlewares_process_protocol_instructions(
        self,
        protocol_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """Apply all middlewares to process protocol instructions"""
        result = protocol_instructions
        for middleware in self.middlewares:
            result = middleware.process_protocol_instructions(result, protocol_name, is_buy)
            if not result:
                break
        return result

    def apply_middlewares_process_full_instructions(
        self,
        full_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """Apply all middlewares to process full instructions"""
        result = full_instructions
        for middleware in self.middlewares:
            result = middleware.process_full_instructions(result, protocol_name, is_buy)
            if not result:
                break
        return result

    @classmethod
    def with_common_middlewares(cls) -> "MiddlewareManager":
        """Create manager with common middlewares"""
        from .builtin import LoggingMiddleware
        return cls().add_middleware(LoggingMiddleware())
