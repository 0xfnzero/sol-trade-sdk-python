"""Offline Hook account resolution for literal keys and SPL PDA seeds.

Unknown configurations fail closed; callers must refresh the mint and TLV list
for every transfer. This helper does not enable cached DEX routes automatically.
"""
from solders.pubkey import Pubkey
from solders.instruction import AccountMeta

TOKEN22 = Pubkey.from_string('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb')
EXECUTE = bytes([105, 37, 101, 197, 75, 251, 102, 26])


def resolve_hook_accounts(hook, mint, mint_owner, mint_data, meta, meta_owner, meta_data, execute_accounts, execute_data=b"", account_data=None):
    """Return extra metas, Hook program, and validation PDA, in SPL order.

    execute_accounts are source, mint, destination, authority, validation PDA.
    Instruction/account seed data must be supplied from this transfer; signer metadata remains unsupported.
    """
    if mint_owner != TOKEN22 or len(mint_data) < 166 or mint_data[165] != 1 or mint_data[45] != 1:
        raise ValueError('Invalid Token-2022 mint')
    if execute_data and (len(execute_data) != 16 or execute_data[:8] != EXECUTE):
        raise ValueError("Invalid Execute instruction data")
    account_data = account_data or {}
    active = None
    offset = 166
    while offset + 4 <= len(mint_data):
        kind = int.from_bytes(mint_data[offset:offset+2], 'little')
        # SPL treats Uninitialized as the end of used TLV data.
        if kind == 0:
            break
        length = int.from_bytes(mint_data[offset+2:offset+4], 'little')
        end = offset + 4 + length
        if end > len(mint_data):
            raise ValueError('Truncated mint extension')
        if kind == 14:
            if active is not None or length != 64:
                raise ValueError('Invalid Hook extension')
            active = Pubkey.from_bytes(mint_data[offset+36:end])
        offset = end
    if active != hook or hook == Pubkey.default():
        raise ValueError('Active Hook program mismatch')
    expected = Pubkey.find_program_address([b'extra-account-metas', bytes(mint)], hook)[0]
    if meta != expected or meta_owner != hook:
        raise ValueError('Invalid Hook validation account')
    if len(execute_accounts) != 5 or execute_accounts[1] != mint or execute_accounts[4] != meta:
        raise ValueError('Invalid Execute account order')
    if len(meta_data) < 16 or meta_data[:8] != EXECUTE:
        raise ValueError('Invalid Execute TLV')
    count = int.from_bytes(meta_data[12:16], 'little')
    if int.from_bytes(meta_data[8:12], 'little') != 4 + 35*count or len(meta_data) != 16+35*count:
        raise ValueError('Invalid Execute TLV length')
    resolved = []
    keys = list(execute_accounts)
    for i in range(count):
        item = meta_data[16+35*i:51+35*i]
        if item[33] != 0 or item[34] > 1:
            raise ValueError('Unsupported signer or invalid flags')
        config = item[1:33]
        if item[0] == 0:
            key = Pubkey.from_bytes(config)
        elif item[0] == 2:
            if config[0] == 1:
                start = config[1]
                if any(config[2:]) or start+32 > len(execute_data):
                    raise ValueError('Invalid instruction PubkeyData')
                key = Pubkey.from_bytes(execute_data[start:start+32])
            elif config[0] == 2:
                index, start = config[1:3]
                if any(config[3:]) or index >= len(keys):
                    raise ValueError('Invalid account PubkeyData')
                data = account_data.get(keys[index])
                if data is None or start+32 > len(data):
                    raise ValueError('Missing or invalid PubkeyData snapshot')
                key = Pubkey.from_bytes(data[start:start+32])
            else:
                raise ValueError('Invalid PubkeyData configuration')
        elif item[0] == 1 or item[0] >= 128:
            program = hook
            if item[0] >= 128:
                index = item[0] - 128
                if index >= len(keys):
                    raise ValueError('Invalid external Hook PDA program index')
                program = keys[index]
            seeds = []
            offset = 0
            while offset < 32 and config[offset]:
                kind = config[offset]
                if kind == 1:
                    if offset+1 >= 32 or config[offset+1] > 32 or offset+2+config[offset+1] > 32:
                        raise ValueError('Invalid literal Hook PDA seed')
                    length = config[offset+1]
                    seeds.append(config[offset+2:offset+2+length]); offset += 2+length
                elif kind == 2:
                    if offset+2 >= 32:
                        raise ValueError('Truncated instruction Hook PDA seed')
                    start,length = config[offset+1:offset+3]
                    if length > 32 or not execute_data or start+length > len(execute_data):
                        raise ValueError('Missing or invalid Execute seed data')
                    seeds.append(execute_data[start:start+length]); offset += 3
                elif kind == 3:
                    if offset+1 >= 32 or config[offset+1] >= len(keys):
                        raise ValueError('Invalid account-key Hook PDA seed')
                    seeds.append(bytes(keys[config[offset+1]])); offset += 2
                elif kind == 4:
                    if offset+3 >= 32 or config[offset+1] >= len(keys):
                        raise ValueError('Invalid account-data Hook PDA seed')
                    index,start,length = config[offset+1:offset+4]
                    data = account_data.get(keys[index])
                    if data is None or length > 32 or start+length > len(data):
                        raise ValueError('Missing or invalid account seed data')
                    seeds.append(data[start:start+length]); offset += 4
                else:
                    raise ValueError('Unsupported Hook PDA seed')
            if any(config[offset:]) or len(seeds) > 15:
                raise ValueError('Invalid Hook PDA seed padding/count')
            key = Pubkey.find_program_address(seeds, program)[0]
        else:
            raise ValueError('Unsupported Hook account configuration')
        # Execute base accounts are readonly/non-signers in the callback; do not escalate duplicates.
        writable = bool(item[34]) and key not in execute_accounts
        if key in keys[5:]:
            writable = writable and any(m.pubkey == key and m.is_writable for m in resolved)
        resolved.append(AccountMeta(key, False, writable))
        keys.append(key)
    return resolved + [AccountMeta(hook, False, False), AccountMeta(meta, False, False)]
