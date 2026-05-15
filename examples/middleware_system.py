import asyncio

from solders.compute_budget import set_compute_unit_limit
from sol_trade_sdk.middleware import InstructionMiddleware, LoggingMiddleware, MiddlewareManager


class ValidationMiddleware(InstructionMiddleware):
    def __init__(self, max_instructions: int, max_data_size: int):
        self.max_instructions = max_instructions
        self.max_data_size = max_data_size

    def name(self) -> str:
        return "ValidationMiddleware"

    def process_protocol_instructions(self, protocol_instructions, protocol_name, is_buy):
        if len(protocol_instructions) > self.max_instructions:
            raise ValueError("too many instructions")
        return protocol_instructions

    def process_full_instructions(self, full_instructions, protocol_name, is_buy):
        if len(full_instructions) > self.max_instructions:
            raise ValueError("too many instructions")
        return full_instructions


async def main() -> None:
    manager = MiddlewareManager().add_middleware(ValidationMiddleware(32, 1024)).add_middleware(LoggingMiddleware())
    instructions = [set_compute_unit_limit(180_000)]
    processed = manager.apply_middlewares_process_protocol_instructions(instructions, "PumpFun", True)
    print("Middleware processed instructions:", len(processed))


if __name__ == "__main__":
    asyncio.run(main())
