"""Current epoch transfer fees and public-transfer eligibility from cached bytes."""

from .stonkfun import TokenTransferFee, unsigned

TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
LENGTHS = {
    1: 108,
    3: 32,
    4: 65,
    6: 1,
    10: 52,
    12: 32,
    14: 64,
    16: 129,
    18: 64,
    20: 64,
    21: 80,
    22: 64,
    23: 72,
    25: 56,
    26: 33,
}


def token_transfer_fee_for_epoch(data, owner, epoch):
    unsigned(epoch)
    d = bytes(data)
    program = str(owner)
    number = lambda o, n: int.from_bytes(d[o : o + n], "little")
    if program not in (TOKEN, TOKEN2022):
        raise ValueError("Unsupported mint token program")
    if len(d) < 82 or d[45] != 1 or number(0, 4) > 1 or number(46, 4) > 1:
        raise ValueError("Invalid or uninitialized cached mint")
    if program == TOKEN:
        if len(d) != 82:
            raise ValueError("Invalid classic mint size")
        return TokenTransferFee()
    if len(d) == 82:
        return TokenTransferFee()
    if len(d) < 166 or len(d) == 355 or d[165] != 1 or any(d[82:165]):
        raise ValueError("Invalid Token2022 mint layout")
    extensions = {}
    offset = 166
    while offset < len(d):
        # Valid supported extension tags have a nonzero low byte. Only
        # possible padding needs a tail scan/copy, not every extension.
        if d[offset] == 0 and not any(d[offset:]):
            break
        if offset + 4 > len(d):
            raise ValueError("Truncated mint extension")
        kind, length = number(offset, 2), number(offset + 2, 2)
        offset += 4
        if not kind or kind in extensions or offset + length > len(d):
            raise ValueError("Invalid/duplicate mint extension")
        if kind != 19 and kind not in LENGTHS:
            raise ValueError("Unsupported mint extension")
        if kind != 19 and LENGTHS[kind] != length:
            raise ValueError("Invalid mint extension size")
        extensions[kind] = d[offset : offset + length]
        offset += length
    if 6 in extensions and extensions[6][0] != 1:
        raise ValueError("Mint defaults to frozen/uninitialized accounts")
    if 26 in extensions and extensions[26][32] != 0:
        raise ValueError("Mint transfers are paused")
    if 14 in extensions and any(extensions[14][32:]):
        raise ValueError("Active transfer hook requires extra accounts")
    if 1 not in extensions:
        return TokenTransferFee()
    fees = extensions[1]
    start = 90 if epoch >= int.from_bytes(fees[90:98], "little") else 72
    basis_points = int.from_bytes(fees[start + 16 : start + 18], "little")
    if basis_points > 10000:
        raise ValueError("Invalid mint fee basis points")
    return TokenTransferFee(basis_points, int.from_bytes(fees[start + 8 : start + 16], "little"))
