"""Repeatable cached quote/build/sign CPU workload; no RPC or bank execution."""
import cProfile
import json
from pathlib import Path
from examples.pumpswap_bank_replay import benchmark


def run(profile=False):
    config=json.loads((Path(__file__).with_suffix('.json')).read_text())
    iterations=config['iterations']
    if profile:
        profiler=cProfile.Profile()
        profiler.enable()
    result=benchmark(iterations)
    if profile:
        profiler.disable()
        profiler.dump_stats('/tmp/python-trade-hotpath.prof')
    return result


if __name__ == '__main__':
    import sys
    print(json.dumps(run('--profile' in sys.argv),indent=2))
