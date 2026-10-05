"""Caller-supplied candidate pools, deterministic minimum-hop order; no RPC."""
from solders.pubkey import Pubkey
from .subscription_cache import PoolTradeHint

def iterate_candidate_routes(candidates, input_mint, output_mint, maximum_hops=5):
    if type(maximum_hops) is not int or not 1 <= maximum_hops <= 5 or not isinstance(input_mint, Pubkey) or not isinstance(output_mint, Pubkey) or input_mint == output_mint or input_mint == Pubkey.default() or output_mint == Pubkey.default():
        raise ValueError("Invalid candidate route endpoints or hop limit")
    by_pool = {}
    for h in candidates:
        PoolTradeHint(h.pool, h.input_mint, h.output_mint)
        old = by_pool.get(h.pool)
        if old and {old.input_mint, old.output_mint} != {h.input_mint, h.output_mint}:
            raise ValueError("Conflicting candidate pool mints")
        by_pool[h.pool] = h
        if len(by_pool) > 64: raise ValueError("Candidate search budget: maximum 64 pools")
    edges = sorted((edge for h in by_pool.values() for edge in (h, PoolTradeHint(h.pool, h.output_mint, h.input_mint))), key=lambda h: (str(h.pool), str(h.output_mint)))
    adjacent = {}
    for h in edges:
        adjacent.setdefault(h.input_mint, []).append(h)
    paths = 0
    frontier = [((), input_mint, {input_mint})]
    for depth in range(maximum_hops):
        next_paths = []
        for hints, mint, seen in frontier:
            for h in adjacent.get(mint, ()):
                if h.output_mint in seen or any(x.pool == h.pool for x in hints):
                    continue
                route = hints + (h,)
                if h.output_mint == output_mint:
                    paths += 1
                    if paths > 64: raise ValueError("Candidate search budget: maximum 64 paths")
                    yield route
                elif depth + 1 < maximum_hops:
                    if len(next_paths) >= 4096: raise ValueError("Candidate search budget exceeded")
                    next_paths.append((route, h.output_mint, seen | {h.output_mint}))
        frontier = next_paths
        if not frontier: break
    if not paths: raise ValueError("No connected candidate route")
    return

def candidate_routes(candidates,input_mint,output_mint,maximum_hops=5):
    return tuple(iterate_candidate_routes(candidates,input_mint,output_mint,maximum_hops))
