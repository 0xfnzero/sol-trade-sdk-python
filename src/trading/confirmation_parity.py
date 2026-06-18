"""Rust-parity transaction error and log parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


SOLANA_INSTRUCTION_ERROR_CODES: dict[str, int] = {
    "GenericError": 1,
    "InvalidArgument": 2,
    "InvalidInstructionData": 3,
    "InvalidAccountData": 4,
    "AccountDataTooSmall": 5,
    "InsufficientFunds": 6,
    "IncorrectProgramId": 7,
    "MissingRequiredSignature": 8,
    "AccountAlreadyInitialized": 9,
    "UninitializedAccount": 10,
}


@dataclass(frozen=True)
class ParsedTransactionError:
    code: int
    instruction_index: Optional[int] = None


def extract_hints_from_logs(logs: Optional[Iterable[str]]) -> str:
    """Extract the same user-facing log hints as Rust `swqos::common`."""
    if not logs:
        return ""

    parts: list[str] = []
    for log in logs:
        idx = log.find("Error Message: ")
        if idx != -1:
            parts.append(log[idx + 15 :].rstrip(".").strip())
            continue

        idx = log.find("Program log: Error: ")
        if idx != -1:
            parts.append(log[idx + 20 :].rstrip(".").strip())

    return "; ".join(part for part in parts if part)


def instruction_error_code_from_meta_err(err: Any) -> ParsedTransactionError:
    """Map Solana `meta.err` JSON to Rust-compatible numeric error codes."""
    if err is None:
        return ParsedTransactionError(code=0)

    if isinstance(err, dict):
        instruction_error = err.get("InstructionError")
        if (
            isinstance(instruction_error, (list, tuple))
            and len(instruction_error) >= 2
        ):
            instruction_index = instruction_error[0]
            detail = instruction_error[1]
            if isinstance(detail, dict) and "Custom" in detail:
                return ParsedTransactionError(
                    code=int(detail["Custom"]),
                    instruction_index=int(instruction_index),
                )
            if isinstance(detail, str) and detail in SOLANA_INSTRUCTION_ERROR_CODES:
                return ParsedTransactionError(
                    code=SOLANA_INSTRUCTION_ERROR_CODES[detail],
                    instruction_index=int(instruction_index),
                )
            return ParsedTransactionError(
                code=999,
                instruction_index=int(instruction_index),
            )

    return ParsedTransactionError(code=108)


def format_parsed_transaction_error(err: Any, logs: Optional[Iterable[str]] = None) -> str:
    """Format `meta.err` and log hints using the same visible shape as Rust."""
    parsed = instruction_error_code_from_meta_err(err)
    hints = extract_hints_from_logs(logs)
    message = f"{err}"
    if hints:
        message = f"{message} {hints}"
    if parsed.instruction_index is not None:
        return f"TradeError(code={parsed.code}, instruction={parsed.instruction_index}): {message}"
    return f"TradeError(code={parsed.code}): {message}"
