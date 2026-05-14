"""
Bonding curve account for Pump.fun.
Based on sol-trade-sdk Rust implementation.
"""

from dataclasses import dataclass
from typing import Optional
try:
    from ..calc.pumpfun import (
        get_buy_token_amount_from_sol_amount,
        get_sell_sol_amount_from_token_amount,
        INITIAL_VIRTUAL_TOKEN_RESERVES,
        INITIAL_VIRTUAL_SOL_RESERVES,
        INITIAL_REAL_TOKEN_RESERVES,
        TOKEN_TOTAL_SUPPLY,
    )
except ImportError:
    from pumpfun import (
        get_buy_token_amount_from_sol_amount,
        get_sell_sol_amount_from_token_amount,
        INITIAL_VIRTUAL_TOKEN_RESERVES,
        INITIAL_VIRTUAL_SOL_RESERVES,
        INITIAL_REAL_TOKEN_RESERVES,
        TOKEN_TOTAL_SUPPLY,
    )


@dataclass
class BondingCurveAccount:
    """Represents the bonding curve account for token pricing"""
    
    discriminator: int = 0
    account: bytes = b'\x00' * 32
    virtual_token_reserves: int = INITIAL_VIRTUAL_TOKEN_RESERVES
    virtual_sol_reserves: int = INITIAL_VIRTUAL_SOL_RESERVES
    real_token_reserves: int = INITIAL_REAL_TOKEN_RESERVES
    real_sol_reserves: int = 0
    token_total_supply: int = TOKEN_TOTAL_SUPPLY
    complete: bool = False
    creator: bytes = b'\x00' * 32
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    
    @classmethod
    def from_dev_trade(
        cls,
        bonding_curve: bytes,
        mint: bytes,
        dev_token_amount: int,
        dev_sol_amount: int,
        creator: bytes,
        is_mayhem_mode: bool = False,
        is_cashback_coin: bool = False,
    ) -> "BondingCurveAccount":
        """Create from dev trade data"""
        account = bonding_curve if bonding_curve != bytes(32) else bytes(32)  # Would use get_bonding_curve_pda
        
        return cls(
            discriminator=0,
            account=account,
            virtual_token_reserves=INITIAL_VIRTUAL_TOKEN_RESERVES - dev_token_amount,
            virtual_sol_reserves=INITIAL_VIRTUAL_SOL_RESERVES + dev_sol_amount,
            real_token_reserves=INITIAL_REAL_TOKEN_RESERVES - dev_token_amount,
            real_sol_reserves=dev_sol_amount,
            token_total_supply=TOKEN_TOTAL_SUPPLY,
            complete=False,
            creator=creator,
            is_mayhem_mode=is_mayhem_mode,
            is_cashback_coin=is_cashback_coin,
        )
    
    @classmethod
    def from_trade(
        cls,
        bonding_curve: bytes,
        mint: bytes,
        creator: bytes,
        virtual_token_reserves: int,
        virtual_sol_reserves: int,
        real_token_reserves: int,
        real_sol_reserves: int,
        is_mayhem_mode: bool = False,
        is_cashback_coin: bool = False,
    ) -> "BondingCurveAccount":
        """Create from trade data"""
        account = bonding_curve if bonding_curve != bytes(32) else bytes(32)
        
        return cls(
            discriminator=0,
            account=account,
            virtual_token_reserves=virtual_token_reserves,
            virtual_sol_reserves=virtual_sol_reserves,
            real_token_reserves=real_token_reserves,
            real_sol_reserves=real_sol_reserves,
            token_total_supply=TOKEN_TOTAL_SUPPLY,
            complete=False,
            creator=creator,
            is_mayhem_mode=is_mayhem_mode,
            is_cashback_coin=is_cashback_coin,
        )
    
    def get_buy_price(self, amount: int) -> int:
        """Calculate tokens received for given SOL amount"""
        if self.complete:
            raise ValueError("Curve is complete")
        
        return get_buy_token_amount_from_sol_amount(
            self.virtual_token_reserves,
            self.virtual_sol_reserves,
            self.real_token_reserves,
            self.creator,
            amount,
        )
    
    def get_sell_price(self, amount: int) -> int:
        """Calculate SOL received for given token amount"""
        if self.complete:
            raise ValueError("Curve is complete")
        
        return get_sell_sol_amount_from_token_amount(
            self.virtual_token_reserves,
            self.virtual_sol_reserves,
            self.creator,
            amount,
        )
    
    def get_market_cap_sol(self) -> float:
        """Calculate current market cap in SOL"""
        if self.virtual_token_reserves == 0:
            return 0.0
        
        price_per_token = self.virtual_sol_reserves / self.virtual_token_reserves
        return price_per_token * self.token_total_supply / 1e9
    
    def get_buy_out_price(self, amount: int) -> int:
        """Calculate price to buy out all remaining tokens"""
        if self.complete:
            raise ValueError("Curve is complete")
        
        # Rough estimate: current price * amount
        if self.virtual_token_reserves == 0:
            return 0
        
        price_ratio = self.virtual_sol_reserves / self.virtual_token_reserves
        return int(price_ratio * amount)

    def get_token_price(self) -> float:
        """Calculate the current token price in SOL.
        100% from Rust: src/common/bonding_curve.rs get_token_price
        """
        v_sol = self.virtual_sol_reserves / 100_000_000.0
        v_tokens = self.virtual_token_reserves / 100_000.0
        if v_tokens == 0:
            return 0.0
        return v_sol / v_tokens

    def get_final_market_cap_sol(self, fee_basis_points: int = 95) -> int:
        """Calculate the final market cap in SOL after all tokens are sold.
        100% from Rust: src/common/bonding_curve.rs get_final_market_cap_sol
        """
        total_sell_value = self._get_buy_out_price_internal(self.real_token_reserves, fee_basis_points)
        total_virtual_value = self.virtual_sol_reserves + total_sell_value
        total_virtual_tokens = self.virtual_token_reserves - self.real_token_reserves

        if total_virtual_tokens == 0:
            return 0

        return (self.token_total_supply * total_virtual_value) // total_virtual_tokens

    def _get_buy_out_price_internal(self, amount: int, fee_basis_points: int) -> int:
        """Internal helper for buy out price calculation"""
        sol_tokens = max(amount, self.real_sol_reserves)

        if self.virtual_token_reserves <= sol_tokens:
            return 0

        total_sell_value = (sol_tokens * self.virtual_sol_reserves) // (self.virtual_token_reserves - sol_tokens) + 1
        fee = (total_sell_value * fee_basis_points) // 10000

        return total_sell_value + fee

    def get_creator_vault_pda(self) -> bytes:
        """Get the creator vault PDA for this bonding curve"""
        from ..instruction.pumpfun_builder import get_creator_vault_pda
        return get_creator_vault_pda(self.creator)


# ===== Decoding Functions - from Rust: src/instruction/utils/pumpfun.rs =====

BONDING_CURVE_ACCOUNT_SIZE = 8 + 8 + 8 + 8 + 8 + 8 + 1 + 32 + 1 + 1  # 77 bytes after discriminator


def decode_bonding_curve_account(data: bytes) -> Optional[BondingCurveAccount]:
    """
    Decode a BondingCurveAccount from on-chain account data.
    Data format (after 8-byte discriminator):
    - virtual_token_reserves: u64 (8 bytes)
    - virtual_sol_reserves: u64 (8 bytes)
    - real_token_reserves: u64 (8 bytes)
    - real_sol_reserves: u64 (8 bytes)
    - token_total_supply: u64 (8 bytes)
    - complete: bool (1 byte)
    - creator: Pubkey (32 bytes)
    - is_mayhem_mode: bool (1 byte)
    - is_cashback_coin: bool (1 byte)

    Args:
        data: Raw account data (with or without discriminator)

    Returns:
        BondingCurveAccount if successful, None if data is invalid
    """
    import struct

    # Handle data with or without discriminator
    if len(data) < BONDING_CURVE_ACCOUNT_SIZE:
        return None

    try:
        offset = 0

        # Check if data starts with discriminator (8 bytes)
        if len(data) >= 8 + BONDING_CURVE_ACCOUNT_SIZE:
            # Skip discriminator
            offset = 8

        # virtual_token_reserves: u64
        virtual_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # virtual_sol_reserves: u64
        virtual_sol_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # real_token_reserves: u64
        real_token_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # real_sol_reserves: u64
        real_sol_reserves = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # token_total_supply: u64
        token_total_supply = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # complete: bool
        complete = data[offset] == 1
        offset += 1

        # creator: Pubkey (32 bytes)
        creator = data[offset:offset + 32]
        offset += 32

        # is_mayhem_mode: bool
        is_mayhem_mode = data[offset] == 1
        offset += 1

        # is_cashback_coin: bool
        is_cashback_coin = data[offset] == 1

        return BondingCurveAccount(
            discriminator=0,
            account=b'\x00' * 32,  # Will be set by caller if needed
            virtual_token_reserves=virtual_token_reserves,
            virtual_sol_reserves=virtual_sol_reserves,
            real_token_reserves=real_token_reserves,
            real_sol_reserves=real_sol_reserves,
            token_total_supply=token_total_supply,
            complete=complete,
            creator=creator,
            is_mayhem_mode=is_mayhem_mode,
            is_cashback_coin=is_cashback_coin,
        )
    except Exception:
        return None
