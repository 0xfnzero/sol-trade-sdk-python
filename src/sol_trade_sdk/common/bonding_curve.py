"""
Bonding curve account for Pump.fun.
Based on sol-trade-sdk Rust implementation.
"""

from dataclasses import dataclass
from typing import Optional
from ..calc.pumpfun import (
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
    virtual_token_reserves: int = 0
    virtual_sol_reserves: int = 0
    real_token_reserves: int = 0
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
