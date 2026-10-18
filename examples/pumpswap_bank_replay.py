"""Native offline execution of newly signed PumpSwap trades on deployed SBF.

Run: python -m examples.pumpswap_bank_replay
Local synthetic wallet/token funding and rent; historical mixed captures, not a
mainnet fork or an RPC simulation. Never connects to RPC or broadcasts.
"""
import base64
import gzip
import hashlib
import json
import time
from pathlib import Path

from solders.account import Account
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.clock import Clock
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import MessageV0, MessageAddressTableLookup
from solders.litesvm import LiteSVM
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from sol_trade_sdk import PumpSwapBuildOptions, prepare_pumpswap_trade
from examples.pumpswap_cached_prepare import prepare_fixture, load_snapshot

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / 'examples/pumpswap_bank'
FIXTURE = ROOT / 'tests/fixtures/pumpswap_ttwo_accounts.json'
WALLET = Keypair.from_seed(bytes([117]) * 32)  # Public test seed; never fund on chain.


def initialize(is_buy, use_alt, full_route=False):
    fixture = ROOT / 'tests/fixtures/pumpswap_ttwo_route_accounts.json' if full_route else FIXTURE
    captured = json.loads(fixture.read_text())
    bank = LiteSVM().with_sigverify(True).with_blockhash_check(True).with_log_bytes_limit(None)
    bank.set_clock(Clock(captured['slot'], 0, captured['epoch'], captured['epoch'], captured['unix_timestamp']))
    config = json.loads((RESOURCES / 'config.json').read_text())
    raw = (RESOURCES / config['programs']).read_bytes()
    manifest = json.loads((RESOURCES / config['programs_manifest']).read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest['sha256']
    programs = json.loads(gzip.decompress(raw))['programs']
    for address, encoded in programs.items():
        code = base64.b64decode(encoded, validate=True)
        assert hashlib.sha256(code).hexdigest() == manifest['programs'][address]
        bank.add_program(Pubkey.from_string(address), code)
    frozen = (RESOURCES / config['snapshot']).read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == config['sha256']
    bundle = json.loads(gzip.decompress(frozen))
    for address, a in bundle['route_accounts' if full_route else 'accounts'].items():
        bank.set_account(Pubkey.from_string(address), Account(int(a['lamports']),
            base64.b64decode(a['data_base64'], validate=True), Pubkey.from_string(a['owner']),
            a['executable'], int(a['rent_epoch'])))
    supplement = json.loads((RESOURCES / 'supplemental_accounts.json').read_text())
    for address, a in supplement['accounts'].items():
        bank.set_account(Pubkey.from_string(address), Account(a['lamports'],
            base64.b64decode(a['data'][0], validate=True), Pubkey.from_string(a['owner']),
            a['executable'], a['rentEpoch']))
    trade, context = prepare_fixture(fixture, is_buy,
        (1000000 if full_route else 10000) if is_buy else 1000000000, WALLET.pubkey())
    # Initialize intermediary ATAs with zero balances, preserving each token's
    # real extension layout. Only the actual trade input is synthetically funded.
    token_templates = {}
    for a in bundle['route_accounts' if full_route else 'accounts'].values():
        data = base64.b64decode(a['data_base64'])
        if len(data) >= 165 and data[108] == 1:
            token_templates[(data[:32], a['owner'])] = data
    for setup in trade.route.setup_instructions:
        a = setup.accounts
        template = token_templates[(bytes(a[3].pubkey), str(a[5].pubkey))]
        data = bytearray(template)
        data[32:64] = bytes(WALLET.pubkey())
        data[64:72] = bytes(8)
        data[72:108] = bytes(36)
        data[108] = 1
        data[109:165] = bytes(56)
        bank.set_account(a[1].pubkey, Account(bank.minimum_balance_for_rent_exemption(len(data)),
            bytes(data), a[5].pubkey))
    from sol_trade_sdk.instruction import pumpswap_builder as ps
    ix = next(i for i in trade.route.swap_instructions if i.program_id == ps.PUMPSWAP_PROGRAM)
    # Extension-preserving synthetic Token2022 accounts: base/quote use their
    # respective real vault layouts. Fee accounts start empty; wallet is funded.
    roles = [(5, WALLET.pubkey(), 3, 7, 11, 10**12 if not is_buy else 0),
             (6, WALLET.pubkey(), 4, 8, 12, 10**12 if is_buy and not full_route else 0),
             (10, ix.accounts[9].pubkey, 4, 8, 12, 0),
             (17, ix.accounts[18].pubkey, 4, 8, 12, 0),
             (len(ix.accounts)-1, ix.accounts[-2].pubkey, 4, 8, 12, 0)]
    for target, owner, mint, vault, token_program, amount in roles:
        data = bytearray(bank.get_account(ix.accounts[vault].pubkey).data)
        data[:32] = bytes(ix.accounts[mint].pubkey)
        data[32:64] = bytes(owner)
        data[64:72] = amount.to_bytes(8, 'little')
        data[72:108] = bytes(36)
        data[108] = 1
        data[109:165] = bytes(56)
        bank.set_account(ix.accounts[target].pubkey, Account(
            bank.minimum_balance_for_rent_exemption(len(data)), bytes(data), ix.accounts[token_program].pubkey))
    bank.airdrop(WALLET.pubkey(), 10**10)
    tracked = {a.pubkey for i in trade.route.swap_instructions for a in i.accounts} | {WALLET.pubkey()}
    tables = []
    if use_alt:
        addresses = list(dict.fromkeys(a.pubkey for i in trade.route.swap_instructions for a in i.accounts if not a.is_signer))
        key = Pubkey.from_bytes(bytes([118]) * 32)
        data = bytes([1, 0, 0, 0]) + bytes([255]) * 8 + bytes(44) + b''.join(bytes(a) for a in addresses)
        bank.set_account(key, Account(bank.minimum_balance_for_rent_exemption(len(data)), data,
            Pubkey.from_string('AddressLookupTab1e1111111111111111111111111')))
        tables = [AddressLookupTableAccount(key, addresses)]
        tracked.add(key)
    return bank, trade, context, tables, tracked


def execute(is_buy, use_alt, reject, full_route=False):
    bank, trade, context, tables, tracked = initialize(is_buy, use_alt, full_route)
    def impossible_minimum(instructions):
        return tuple(Instruction(i.program_id, i.data[:16] + bytes([255])*8 + i.data[24:], i.accounts)
                     if n == len(instructions)-1 else i for n, i in enumerate(instructions))
    options = PumpSwapBuildOptions(bank.latest_blockhash(), 'v0', tuple(tables),
        create_associated_accounts=False, temporary_wsol_seed='bank-native-route', rent_lamports=2039280,
        protocol_middleware=impossible_minimum if reject else None)
    built = trade.build_transaction(WALLET, context, options)
    assert built.wire == trade.build_transaction(WALLET, context, options).wire
    tx = VersionedTransaction.from_bytes(built.wire)
    tx.verify_and_hash_message()
    assert bool(tx.message.address_table_lookups) == use_alt
    tracked.update(tx.message.account_keys)
    state = lambda: {k: bank.get_account(k) for k in tracked}
    before = state()
    sim = bank.simulate_transaction(tx)
    assert state() == before, 'simulation mutated bank'
    simulated = json.loads(sim.to_json())
    committed = bank.send_transaction(tx)
    after = state()
    if reject:
        error = simulated['err']['InstructionError']
        expected = 6040 if is_buy else (30 if full_route else 6004)
        assert error[1] == {'Custom': expected}, simulated.get('err')
        if full_route:
            assert error[0] == 6
            assert sum(line.endswith(' success') for line in sim.meta().logs()) >= 2
        assert hasattr(committed, 'err')
        assert all(after[k] == a for k, a in before.items() if k != WALLET.pubkey())
        assert before[WALLET.pubkey()].lamports - after[WALLET.pubkey()].lamports == 5000
        deltas = None
    else:
        assert 'err' not in simulated, simulated.get('err')
        assert not hasattr(committed, 'err')
        assert all((after[k] if after[k] is not None and after[k].lamports else None) == (a if a.lamports else None) for k, a in sim.post_accounts() if k in tracked)
        from sol_trade_sdk.instruction import pumpswap_builder as ps
        ix = next(i for i in trade.route.swap_instructions if i.program_id == ps.PUMPSWAP_PROGRAM)
        token_amount = lambda a: int.from_bytes(a.data[64:72], 'little')
        deltas = [token_amount(after[ix.accounts[n].pubkey])-token_amount(before[ix.accounts[n].pubkey]) for n in (5, 6)]
        if full_route:
            assert deltas == ([48416740, 5] if is_buy else [-1000000000, 101]), 'three-hop pinned execution oracle changed'
            assert after[WALLET.pubkey()].lamports-before[WALLET.pubkey()].lamports == (-2849400 if is_buy else 19454119)
            if is_buy:
                assert deltas[0] >= trade.minimum_output_credit
                assert before[WALLET.pubkey()].lamports-after[WALLET.pubkey()].lamports >= trade.request.amount_in+5000
            else:
                assert -deltas[0] == trade.request.amount_in
                assert after[WALLET.pubkey()].lamports-before[WALLET.pubkey()].lamports+5000 >= trade.minimum_output_credit
            for program in (ps.PUMPSWAP_PROGRAM, Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8'),
                            Pubkey.from_string('LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo')):
                assert 'Program '+str(program)+' success' in sim.meta().logs()
        else:
            input_delta, output_delta = (-deltas[1], deltas[0]) if is_buy else (-deltas[0], deltas[1])
            assert input_delta == trade.request.amount_in
            assert deltas == ([1014985984, -10000] if is_buy else [-1000000000, 9791]), 'pinned execution oracle changed'
            assert output_delta >= trade.minimum_output_credit
        assert any('TransferChecked' in line for line in sim.meta().logs())
    # A corrupted genuine Ed25519 signature fails before any program/account write.
    bad = bytearray(built.wire)
    bad[1] ^= 1
    failed = bank.simulate_transaction(VersionedTransaction.from_bytes(bytes(bad)))
    assert json.loads(failed.to_json())['err'] == 'SignatureFailure'
    assert not failed.meta().logs() and state() == after
    if use_alt:
        msg = tx.message
        lookup = msg.address_table_lookups[0]
        invalid = MessageAddressTableLookup(lookup.account_key,
            bytes([255]) + bytes(lookup.writable_indexes)[1:], lookup.readonly_indexes)
        signed = VersionedTransaction(MessageV0(msg.header, msg.account_keys,
            msg.recent_blockhash, msg.instructions, [invalid]), [WALLET])
        failed = bank.simulate_transaction(signed)
        assert json.loads(failed.to_json())['err'] == 'InvalidAddressLookupTableIndex'
        assert not failed.meta().logs() and state() == after
    return {'buy': is_buy, 'alt': use_alt, 'reject': reject, 'full_route': full_route, 'deltas': deltas,
            'wire': built.wire.hex(), 'logs': sim.meta().logs(),
            'wallet_lamports_delta': after[WALLET.pubkey()].lamports-before[WALLET.pubkey()].lamports,
            'state': {str(k): None if a is None else a.to_json() for k, a in sorted(after.items(), key=lambda p: str(p[0]))}}


def run_bank(repetitions=2):
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ValueError('repetitions must be between 1 and 10')
    results = []
    for buy in (True, False):
        for alt in (False, True):
            for reject in (False, True):
                a = execute(buy, alt, reject)
                for _ in range(repetitions - 1):
                    assert a == execute(buy, alt, reject), 'fresh-bank replay is not deterministic'
                results.append({k: a[k] for k in ('buy', 'alt', 'reject', 'deltas')})
    for buy in (True, False):
        for reject in (False, True):
            a = execute(buy, True, reject, True)
            for _ in range(repetitions - 1):
                assert a == execute(buy, True, reject, True), 'three-hop replay is not deterministic'
            results.append({k: a[k] for k in ('buy', 'alt', 'reject', 'full_route', 'deltas')})
    return results


def benchmark(iterations):
    """Local CPU timings only; exclude fixture I/O and bank/SBF execution."""
    if type(iterations) is not int or not 0 <= iterations <= 100000:
        raise ValueError('benchmark_iterations must be between 0 and 100000')
    if not iterations:
        return None
    _, snapshot, context = load_snapshot(FIXTURE)
    base, _ = prepare_fixture(FIXTURE, True, 10000, WALLET.pubkey())
    hints = tuple(step.hint for step in base.steps)
    from solders.hash import Hash
    options = PumpSwapBuildOptions(Hash.default(), 'v0', create_associated_accounts=False)
    quote, signing = [], []
    for index in range(iterations + 20):
        start = time.perf_counter_ns()
        trade = prepare_pumpswap_trade(snapshot, hints, base.input_mint,
            base.output_mint, base.request, context, True)
        prepared = time.perf_counter_ns()
        trade.build_transaction(WALLET, context, options)
        end = time.perf_counter_ns()
        if index >= 20:
            quote.append((prepared-start)/1000)
            signing.append((end-prepared)/1000)
    def percentiles(values):
        values.sort()
        return {name: values[min(len(values)-1, int((len(values)-1)*p))]
                for name, p in [('p50', .50), ('p95', .95), ('p99', .99), ('max', 1)]}
    return {'iterations': iterations, 'units': 'microseconds', 'rpc_calls': 0,
            'scope': 'local CPU snapshot preparation and V0 build+Ed25519 sign; not production latency',
            'prepare': percentiles(quote), 'build_sign_v0': percentiles(signing)}


if __name__ == '__main__':
    config = json.loads((RESOURCES / 'config.json').read_text())
    print(json.dumps({'scenarios': run_bank(config.get('repetitions', 2)), 'rpc_calls': 0, 'broadcasts': 0,
        'benchmark': benchmark(config.get('benchmark_iterations', 0))}, indent=2))
