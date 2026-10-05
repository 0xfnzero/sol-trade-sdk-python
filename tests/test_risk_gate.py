"""TradeRiskGate buy-path parity with Rust 5.0.2."""

import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from src import (
    DexType,
    TradeBuyParams,
    TradeConfig,
    TradeTokenType,
    TradingClient,
)


class RejectingGate:
    def __init__(self):
        self.calls = 0

    def check_buy(self, params):
        self.calls += 1
        raise RuntimeError("blocked by risk gate")


@pytest.mark.asyncio
async def test_buy_invokes_risk_gate():
    payer = Keypair()
    client = TradingClient(payer, TradeConfig(rpc_url="http://localhost:8899"))
    gate = RejectingGate()
    client.with_risk_gate(gate)
    with pytest.raises(RuntimeError, match="blocked by risk gate"):
        await client.buy(
            TradeBuyParams(
                dex_type=DexType.PUMPFUN,
                input_token_type=TradeTokenType.SOL,
                mint=Pubkey.default(),
                input_token_amount=1_000_000,
                extension_params=object(),
                slippage_basis_points=100,
            )
        )
    assert gate.calls == 1
    await client.close()
