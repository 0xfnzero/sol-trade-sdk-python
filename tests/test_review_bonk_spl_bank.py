"""Classic SPL positive execution of the public Bonk bytes API, offline only."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_public_bonk_bytes_classic_spl_bank(tmp_path):
    workspace=Path(__file__).resolve().parents[2]
    harness=workspace/'tools/code-review-20261009-bank-performance-completion/bonk/bonk_spl_bank.py'
    cache=workspace/'tools/validation/simulation-local-bank-20261008/accounts'
    if not harness.exists() or not cache.exists():
        pytest.skip('Captured executable/account fixture and offline Bonk bank harness are required')
    pytest.importorskip('solders.litesvm')
    completed=subprocess.run([sys.executable,str(harness),'--output-dir',str(tmp_path)],cwd=workspace,text=True,capture_output=True,timeout=60)
    assert completed.returncode==0,completed.stdout+completed.stderr
    evidence=json.loads((tmp_path/'bonk-bank-evidence.json').read_text())
    assert evidence['rpc_calls']==evidence['broadcasts']==0
    assert evidence['classic_spl_mint_owner']=='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
    rows={row['name']:row for row in evidence['rows']}
    assert len(rows)==8
    for name in ['signed_create_platform','signed_initialize_spl_pool','signed_fund_token_accounts','sdk_buy','sdk_sell']:
        assert rows[name]['success'] and rows[name]['execution_committed']
        assert rows[name]['independent_wire_parsed'] and rows[name]['simulation_no_commit']
    for name in ['sdk_buy_impossible_minimum','sdk_sell_impossible_minimum']:
        assert rows[name]['error']=={'InstructionError':[1,{'Custom':6004}]}
        assert not rows[name]['execution_committed'] and rows[name]['simulation_no_commit']
    assert rows['sdk_tampered_signature']['error']=='SignatureFailure'
    assert rows['sdk_tampered_signature']['local_execution_rejected']
    for side in ['buy','sell']:
        row=rows['sdk_'+side]
        deltas=[balance['delta'] for balance in row['token_balances'].values()]
        assert row['trade_event']['amount_out']>0
        assert -row['trade_event']['amount_in'] in deltas
        assert row['trade_event']['amount_out'] in deltas
