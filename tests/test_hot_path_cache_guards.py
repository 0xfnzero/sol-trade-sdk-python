"""Warm caches must preserve account freshness, continuity and caller isolation."""
from dataclasses import replace
import pytest
from test_cached_pumpswap import fixture, cases, context
from sol_trade_sdk.trading.subscription_cache import AccountCacheSnapshot


def test_v0_hot_signing_rejects_null_signer_and_accepts_valid_presigner():
    from pathlib import Path
    from solders.keypair import Keypair
    from solders.hash import Hash
    from solders.null_signer import NullSigner
    from solders.presigner import Presigner
    from solders import transaction
    from sol_trade_sdk import PumpSwapBuildOptions
    from examples.pumpswap_cached_prepare import prepare_fixture

    signer = Keypair.from_seed(bytes([117]) * 32)
    path = Path(__file__).parent / 'fixtures/pumpswap_ttwo_accounts.json'
    trade, ctx = prepare_fixture(path, True, 10000, signer.pubkey())
    options = PumpSwapBuildOptions(Hash.default(), version='v0')
    signed = trade.build_transaction(signer, ctx, options)
    with pytest.raises(transaction.TransactionError):
        trade.build_transaction(NullSigner(signer.pubkey()), ctx, options)
    presigned = trade.build_transaction(Presigner(signer.pubkey(), signed.signature), ctx, options)
    assert presigned.wire == signed.wire


def test_warm_fee_cache_does_not_leak_mutable_selected_fees():
    accounts, hint = fixture(cases[0])
    snapshot = AccountCacheSnapshot(accounts)
    first = snapshot.pumpswap(hint, context)
    expected = first.fee_basis_points.coin_creator_fee_basis_points
    from sol_trade_sdk.instruction import pumpswap_builder as ps
    modified = dict(accounts)
    for key, offset, value in ((hint.pool,261,55), (ps.PUMPSWAP_GLOBAL_ACCOUNT,940,1)):
        a = modified[key]
        data = bytearray(a.data)
        if len(data) < offset+8:
            data.extend(bytes(offset+8-len(data)))
        data[offset:offset+8] = value.to_bytes(8,'little')
        modified[key] = replace(a,data=bytes(data))
    assert AccountCacheSnapshot(modified).pumpswap(hint, context).fee_basis_points.coin_creator_fee_basis_points == 55
    assert snapshot.pumpswap(hint, context).fee_basis_points.coin_creator_fee_basis_points == expected
    # Account-level checks must still run after the byte-keyed decode cache warms.
    with pytest.raises(ValueError, match='stale'):
        snapshot.pumpswap(hint, replace(context, slot=context.slot+1))
    usable = [True]
    def guard():
        if not usable[0]:
            raise ValueError('continuity lost')
    snapshot = AccountCacheSnapshot(accounts, guard)
    snapshot.pumpswap(hint, context)
    usable[0] = False
    with pytest.raises(ValueError, match='continuity lost'):
        snapshot.pumpswap(hint, context)
