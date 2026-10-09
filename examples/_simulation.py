"""Explicit simulation only; owned original wire can be consumed by parser examples."""
import base64
import json
import os
from pathlib import Path
import requests


def validate_simulation_response(response):
    if not isinstance(response, dict) or response.get('error') is not None:
        raise ValueError('Simulation RPC error')
    result = response.get('result')
    value = result.get('value') if isinstance(result, dict) else None
    if not isinstance(value, dict) or 'err' not in value:
        raise ValueError('Simulation response missing execution result')
    return value['err']


def simulate(wire, slot, output=None, *, verify_signatures=False):
    """Enable signature verification only with the original signed blockhash."""
    r = requests.post(os.environ.get('RPC_URL', 'https://api.mainnet-beta.solana.com'),
        json=dict(jsonrpc='2.0', id=1, method='simulateTransaction', params=[
            base64.b64encode(wire).decode(), dict(encoding='base64', sigVerify=verify_signatures,
                replaceRecentBlockhash=not verify_signatures, innerInstructions=True, commitment='confirmed', minContextSlot=slot)]), timeout=30)
    r.raise_for_status()
    response = r.json()
    error = validate_simulation_response(response)
    if output:
        Path(output).write_text(json.dumps(dict(wire=base64.b64encode(wire).decode(),response=response), indent=2)+'\n')
    print(json.dumps(response))
    if error is not None:
        raise SystemExit(1)
    return response
