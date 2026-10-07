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
    virtual_token_reserves: int = 0
    virtual_sol_reserves: int = 0
    real_token_reserves: int = 0
    real_sol_reserves: int = 0
    token_total_supply: int = 0
    complete: bool = False
    creator: bytes = b'\x00' * 32
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    quote_mint: bytes = bytes(32)
    creator_fee_bps: int = 0
    can_edit_creator_fee: bool = False
    is_holder_reward: bool = False
    creator_fee: int = 0
    protocol_fees: int = 0
    depth: int = 0
    initial_virtual_quote_reserves: int = 0
    post_complete_base_out: int = 0
    post_complete_quote_in: int = 0

    
    def __post_init__(self):
        self._validate_reserves()

    def _validate_reserves(self):
        for value in (self.virtual_token_reserves, self.virtual_sol_reserves,
                      self.real_token_reserves, self.real_sol_reserves, self.token_total_supply):
            self._u64(value)

    @staticmethod
    def normalize_quote_mint(mint):
        from solders.pubkey import Pubkey
        raw = bytes(mint)
        if len(raw) != 32:
            raise ValueError("Quote mint must be a 32-byte public key")
        if raw in (bytes(32), bytes(Pubkey.from_string("So11111111111111111111111111111111111111111"))):
            raw = bytes(Pubkey.from_string("So11111111111111111111111111111111111111112"))
        return Pubkey.from_bytes(raw) if isinstance(mint, Pubkey) else raw

    def effective_quote_mint(self):
        return self.normalize_quote_mint(self.quote_mint)

    @staticmethod
    def initial_virtual_quote_reserves_for_quote_mint(mint):
        from solders.pubkey import Pubkey
        return 4_292_000_000 if bytes(mint) == bytes(Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")) else 30_000_000_000

    def virtual_quote_reserves(self):
        self._validate_reserves()
        return self.virtual_sol_reserves

    def real_quote_reserves(self):
        self._validate_reserves()
        return self.real_sol_reserves

    def with_quote_mint(self, mint):
        self._validate_reserves()
        normalized = self.normalize_quote_mint(mint)
        previous = self.initial_virtual_quote_reserves_for_quote_mint(self.effective_quote_mint())
        if self.virtual_sol_reserves == min((1 << 64)-1, previous + self.real_sol_reserves):
            self.virtual_sol_reserves = min((1 << 64)-1, self.initial_virtual_quote_reserves_for_quote_mint(normalized) + self.real_sol_reserves)
        self.quote_mint = normalized
        return self

    def get_creator_vault_pda(self):
        from solders.pubkey import Pubkey
        from ..instruction.pumpfun_builder import get_creator_vault_pda
        return get_creator_vault_pda(Pubkey.from_bytes(bytes(self.creator)))

    @classmethod
    def from_dev_trade_with_quote_mint(cls, bonding_curve, mint, dev_token_amount,
                                     dev_quote_amount, creator, is_mayhem_mode,
                                     is_cashback_coin, quote_mint):
        token, quote = cls._u64(dev_token_amount), cls._u64(dev_quote_amount)
        if token > INITIAL_REAL_TOKEN_RESERVES:
            raise ValueError("Dev trade exceeds initial real token reserves")
        normalized = cls.normalize_quote_mint(quote_mint)
        curve = cls.from_trade_with_quote_mint(
            bonding_curve, mint, creator, INITIAL_VIRTUAL_TOKEN_RESERVES-token,
            cls.initial_virtual_quote_reserves_for_quote_mint(normalized)+quote,
            INITIAL_REAL_TOKEN_RESERVES-token, quote, is_mayhem_mode,
            is_cashback_coin, normalized)
        return curve

    @classmethod
    def from_trade_with_quote_mint(cls, bonding_curve, mint, creator,
                                  virtual_token_reserves, virtual_quote_reserves,
                                  real_token_reserves, real_quote_reserves,
                                  is_mayhem_mode, is_cashback_coin, quote_mint):
        account = bonding_curve
        if bytes(bonding_curve) == bytes(32):
            from solders.pubkey import Pubkey
            from ..instruction.pumpfun_builder import get_bonding_curve_pda
            account = bytes(get_bonding_curve_pda(Pubkey.from_bytes(bytes(mint))))
        return cls(account=account, creator=creator,
                   virtual_token_reserves=virtual_token_reserves,
                   virtual_sol_reserves=virtual_quote_reserves,
                   real_token_reserves=real_token_reserves,
                   real_sol_reserves=real_quote_reserves,
                   token_total_supply=TOKEN_TOTAL_SUPPLY,
                   is_mayhem_mode=is_mayhem_mode, is_cashback_coin=is_cashback_coin,
                   quote_mint=cls.normalize_quote_mint(quote_mint))

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
        return cls.from_dev_trade_with_quote_mint(
            bonding_curve, mint, dev_token_amount, dev_sol_amount, creator,
            is_mayhem_mode, is_cashback_coin, bytes(32))

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
        return cls.from_trade_with_quote_mint(
            bonding_curve, mint, creator, virtual_token_reserves,
            virtual_sol_reserves, real_token_reserves, real_sol_reserves,
            is_mayhem_mode, is_cashback_coin, bytes(32))

    @staticmethod
    def _u64(value: int) -> int:
        if type(value) is not int or not 0 <= value < 1 << 64:
            raise ValueError("Expected u64 integer")
        return value

    def get_buy_price(self, amount: int) -> int:
        """Raw curve price (no fee), matching Rust BondingCurveAccount."""
        self._validate_reserves()
        self._u64(amount)
        if self.complete:
            raise ValueError("Curve is complete")
        if amount == 0:
            return 0
        reserve = self.virtual_sol_reserves * self.virtual_token_reserves // (self.virtual_sol_reserves + amount) + 1
        if reserve > self.virtual_token_reserves:
            raise ValueError("Invalid curve reserves")
        return min((self.virtual_token_reserves - reserve) & ((1 << 64) - 1), self.real_token_reserves)

    def get_sell_price(self, amount: int, fee_basis_points: int = 95) -> int:
        self._validate_reserves()
        self._u64(amount)
        self._u64(fee_basis_points)
        if self.complete:
            raise ValueError("Curve is complete")
        if amount == 0:
            return 0
        gross = amount * self.virtual_sol_reserves // (self.virtual_token_reserves + amount)
        fee = gross * fee_basis_points // 10000
        if fee > gross:
            raise ValueError("Fee exceeds output")
        return (gross - fee) & ((1 << 64) - 1)

    def get_market_cap_sol(self) -> int:
        """Market cap in quote atoms, matching Rust's u64 return value."""
        self._validate_reserves()
        if self.virtual_token_reserves == 0:
            return 0
        return (self.token_total_supply * self.virtual_sol_reserves // self.virtual_token_reserves) & ((1 << 64) - 1)

    def get_buy_out_price(self, amount: int, fee_basis_points: int = 95) -> int:
        self._validate_reserves()
        self._u64(amount)
        self._u64(fee_basis_points)
        tokens = max(amount, self.real_sol_reserves)
        if tokens >= self.virtual_token_reserves:
            raise ValueError("Invalid buyout reserves")
        value = tokens * self.virtual_sol_reserves // (self.virtual_token_reserves - tokens) + 1
        return (value + value * fee_basis_points // 10000) & ((1 << 64) - 1)

    def get_token_price(self) -> float:
        v_sol = self.virtual_sol_reserves / 100_000_000.0
        v_tokens = self.virtual_token_reserves / 100_000.0
        if v_tokens == 0:
            return float('nan') if v_sol == 0 else float('inf')
        return v_sol / v_tokens

    def get_final_market_cap_sol(self, fee_basis_points: int = 95) -> int:
        value = self.get_buy_out_price(self.real_token_reserves, fee_basis_points)
        tokens = self.virtual_token_reserves - self.real_token_reserves
        if tokens < 0:
            raise ValueError("Invalid curve reserves")
        if tokens == 0:
            return 0
        return (self.token_total_supply * (self.virtual_sol_reserves + value) // tokens) & ((1 << 64) - 1)

    def _get_buy_out_price_internal(self, amount: int, fee_basis_points: int) -> int:
        return self.get_buy_out_price(amount, fee_basis_points)

    def get_creator_vault_pda(self) -> bytes:
        """Get the creator vault PDA for this bonding curve"""
        from ..instruction.pumpfun_builder import get_creator_vault_pda
        return get_creator_vault_pda(self.creator)


# ===== Decoding Functions - from Rust: src/instruction/utils/pumpfun.rs =====

BONDING_CURVE_ACCOUNT_SIZE = 115  # discriminator + full pinned Rust V2 body


def decode_bonding_curve_account(data: bytes) -> Optional[BondingCurveAccount]:
    """Decode a prefixed account or exact 75/107-byte legacy/V2 Borsh body.

    A missing legacy quote key remains zero (native); partial keys are rejected.
    Extended prefixed V2 accounts are accepted without dropping quote metadata.
    """
    import struct
    discriminator = bytes([23, 183, 248, 55, 96, 216, 172, 96])
    if len(data) in (75, 107) and data[:8] != discriminator:
        body = data
    else:
        if len(data) < 83 or 83 < len(data) < 115 or data[:8] != discriminator:
            return None
        body = data[8:]
    if any(body[i] > 1 for i in (40, 73, 74)):
        return None
    reserves = struct.unpack_from('<5Q', body)
    return BondingCurveAccount(
        creator_fee_bps=int.from_bytes(body[107:115], 'little') if len(body)>=115 else 0,
        can_edit_creator_fee=bool(body[115]) if len(body)>115 else False,
        is_holder_reward=bool(body[116]) if len(body)>116 else False,
        creator_fee=int.from_bytes(body[117:125], 'little') if len(body)>=125 else 0,
        protocol_fees=int.from_bytes(body[125:133], 'little') if len(body)>=133 else 0,
        depth=body[133] if len(body)>133 else 0,
        initial_virtual_quote_reserves=int.from_bytes(body[134:142], 'little') if len(body)>=142 else 0,
        post_complete_base_out=int.from_bytes(body[142:150], 'little') if len(body)>=150 else 0,
        post_complete_quote_in=int.from_bytes(body[150:158], 'little') if len(body)>=158 else 0,

        virtual_token_reserves=reserves[0], virtual_sol_reserves=reserves[1],
        real_token_reserves=reserves[2], real_sol_reserves=reserves[3],
        token_total_supply=reserves[4], complete=bool(body[40]),
        creator=body[41:73], is_mayhem_mode=bool(body[73]),
        is_cashback_coin=bool(body[74]),
        quote_mint=body[75:107] if len(body) >= 107 else bytes(32),
    )
