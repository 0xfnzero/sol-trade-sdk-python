"""Signed legacy bytes AMMv4 API, actual deployed program, offline local bank."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_signed_public_amm_bytes_bank(tmp_path):
    pytest.importorskip('solders.litesvm')
    workspace = Path(__file__).resolve().parents[2]
    script = workspace / 'tools/code-review-20261009-bank-performance-completion/amm/signed_legacy_amm.py'
    if not script.exists():
        pytest.skip('Workspace captured-program bank harness is required')
    completed = subprocess.run([sys.executable, str(script), '--output-dir', str(tmp_path)], cwd=workspace, text=True, capture_output=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads((tmp_path / 'bank-evidence.json').read_text())
    assert evidence['broadcasts'] == evidence['hotpath_rpc_calls'] == 0
    assert evidence['sigverify'] and evidence['blockhash_check']
    assert evidence['program']['program'] == '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8'
    rows = {r['name']: r for r in evidence['cases']}
    assert set(rows) == {'buy', 'sell', 'slippage', 'tampered-signature', 'stale-blockhash'}
    for side in ['buy', 'sell']:
        row = rows[side]
        assert row['simulation_no_commit']
        assert row['amount_out'] > 0
        assert row['parsed_event']['amount_in'] == row['amount_in']
        assert row['parsed_event']['amount_out'] == row['amount_out']
        source = 0 if side == 'buy' else 1
        destination = 1 - source
        assert row['before'][source] - row['after'][source] == row['amount_in']
        assert row['after'][destination] - row['before'][destination] == row['amount_out']
    assert rows['slippage']['simulation']['err'] == {'InstructionError': [1, {'Custom': 30}]}
    assert rows['tampered-signature']['simulation']['err'] == 'SignatureFailure'
    assert rows['stale-blockhash']['simulation']['err'] == 'BlockhashNotFound'
    for name in ['slippage', 'tampered-signature', 'stale-blockhash']:
        assert rows[name]['before'] == rows[name]['after']
