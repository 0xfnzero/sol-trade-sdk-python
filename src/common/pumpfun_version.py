"""Pump.fun instruction versions (independent of Solana message versions)."""
from enum import Enum


class PumpFunVersion(str, Enum):
    LEGACY = "v1"
    V2 = "v2"
    V3 = "v3"
