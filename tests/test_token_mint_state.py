import struct
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.token_mint_state import token_transfer_fee_for_epoch

TOKEN = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")


def mint(extensions):
    d = bytearray(166)
    d[45] = 1
    d[165] = 1
    return bytes(d) + b"".join(
        struct.pack("<HH", kind, len(data)) + data for kind, data in extensions
    )


def test_epoch_fee_schedule():
    fees = bytearray(108)
    struct.pack_into("<QQH", fees, 72, 0, 500, 100)
    struct.pack_into("<QQH", fees, 90, 4, 900, 300)
    assert token_transfer_fee_for_epoch(mint([(1, fees)]), TOKEN, 3).basis_points == 100
    assert token_transfer_fee_for_epoch(mint([(1, fees)]), TOKEN, 4).basis_points == 300


def test_stock_mint_public_transfer_state():
    pause, hook = bytearray(33), bytearray(64)

    def build(state=1):
        return mint([(6, bytes([state])), (26, pause), (14, hook), (4, bytes(65))])

    assert token_transfer_fee_for_epoch(build(), TOKEN, 1).basis_points == 0
    with pytest.raises(ValueError, match="frozen"):
        token_transfer_fee_for_epoch(build(2), TOKEN, 1)
    pause[32] = 1
    with pytest.raises(ValueError, match="paused"):
        token_transfer_fee_for_epoch(build(), TOKEN, 1)
    pause[32] = 0
    hook[32] = 1
    with pytest.raises(ValueError, match="hook"):
        token_transfer_fee_for_epoch(build(), TOKEN, 1)
    with pytest.raises(ValueError, match="size"):
        token_transfer_fee_for_epoch(mint([(6, b"")]), TOKEN, 1)


@pytest.mark.parametrize("padding", [1, 2, 3, 4, 64])
def test_zero_tail_padding(padding):
    d = mint([(6, bytes([1])), (19, b"")]) + bytes(padding)
    assert token_transfer_fee_for_epoch(d, TOKEN, 1).basis_points == 0


@pytest.mark.parametrize("tail", [b"\x00\x01", b"\x06\x00\x01", b"\x06\x00\x02\x00\x01"])
def test_malformed_extension_tail(tail):
    with pytest.raises(ValueError):
        token_transfer_fee_for_epoch(mint([]) + tail, TOKEN, 1)


@pytest.mark.parametrize("kind,payload", [(6, b"\x01"), (19, b"")])
def test_duplicate_extensions_including_empty_metadata(kind, payload):
    with pytest.raises(ValueError, match="duplicate"):
        token_transfer_fee_for_epoch(mint([(kind, payload), (kind, payload)]), TOKEN, 1)
