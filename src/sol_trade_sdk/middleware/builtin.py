"""
Built-in middleware implementations.
Based on sol-trade-sdk Rust implementation.
"""

from typing import List, Dict, Any

try:
    from .traits import InstructionMiddleware
except ImportError:
    from traits import InstructionMiddleware


class LoggingMiddleware(InstructionMiddleware):
    """Logging middleware - Records instruction information"""

    def name(self) -> str:
        return "LoggingMiddleware"

    def process_protocol_instructions(
        self,
        protocol_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """Log protocol instructions"""
        print(f"-------------------[{self.name()}]-------------------")
        print("process_protocol_instructions")
        print(f"[{self.name()}] Instruction count: {len(protocol_instructions)}")
        print(f"[{self.name()}] Protocol name: {protocol_name}")
        print(f"[{self.name()}] Is buy: {is_buy}")
        for i, instruction in enumerate(protocol_instructions):
            print(f"Instruction {i + 1}:")
            print(f"{instruction}\n")
        return protocol_instructions

    def process_full_instructions(
        self,
        full_instructions: List[Dict[str, Any]],
        protocol_name: str,
        is_buy: bool,
    ) -> List[Dict[str, Any]]:
        """Log full instructions"""
        print(f"-------------------[{self.name()}]-------------------")
        print("process_full_instructions")
        print(f"[{self.name()}] Instruction count: {len(full_instructions)}")
        print(f"[{self.name()}] Protocol name: {protocol_name}")
        print(f"[{self.name()}] Is buy: {is_buy}")
        for i, instruction in enumerate(full_instructions):
            print(f"Instruction {i + 1}:")
            print(f"{instruction}\n")
        return full_instructions
