"""Validated current config only, not a PumpFun quote/factory. No RPC."""
from dataclasses import dataclass
from typing import Optional
from solders.pubkey import Pubkey
from ..instruction.pumpfun_builder import (
    PUMPFUN_PROGRAM_ID, GLOBAL_ACCOUNT, FEE_PROGRAM,
    get_fee_sharing_config_pda, get_creator_vault_pda,
)


def decode_pumpfun_global_fee_recipient(data: bytes) -> Pubkey:
    if len(data) < 73 or data[:8] != bytes([167,232,232,177,200,108,114,127]):
        raise ValueError("Invalid PumpFun Global discriminator or size")
    return Pubkey.from_bytes(data[41:73])


def decode_pumpfun_sharing_creator_vault(data: bytes, mint: Pubkey) -> Optional[Pubkey]:
    if len(data) < 43 or data[:8] != bytes([216,74,9,0,56,140,93,75]):
        raise ValueError("Invalid PumpFun SharingConfig discriminator or size")
    if data[11:43] != bytes(mint):
        raise ValueError("PumpFun SharingConfig mint mismatch")
    return get_creator_vault_pda(get_fee_sharing_config_pda(mint)) if data[10] == 1 else None


@dataclass(frozen=True)
class CachedPumpFunConfiguration:
    fee_recipient: Pubkey
    sharing_config: Pubkey
    fee_sharing_creator_vault_if_active: Optional[Pubkey]


def cached_pumpfun_configuration(snapshot, mint: Pubkey, context) -> CachedPumpFunConfiguration:
    # Absence is unresolved; callers must prepare/revalidate before trading.
    if mint == Pubkey.default():
        raise ValueError("Missing PumpFun mint")
    global_account = snapshot.get(GLOBAL_ACCOUNT, context, PUMPFUN_PROGRAM_ID)
    recipient = decode_pumpfun_global_fee_recipient(global_account.data)
    if recipient == Pubkey.default():
        raise ValueError("Missing PumpFun Global fee recipient")
    config = get_fee_sharing_config_pda(mint)
    sharing = snapshot.get(config, context, FEE_PROGRAM)
    vault = decode_pumpfun_sharing_creator_vault(sharing.data, mint)
    snapshot.assert_usable()
    return CachedPumpFunConfiguration(recipient, config, vault)
