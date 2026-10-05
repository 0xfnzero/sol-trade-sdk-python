import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.trading.route_candidates import candidate_routes, iterate_candidate_routes
from sol_trade_sdk import PoolTradeHint
key=lambda n: Pubkey.from_bytes(bytes([n])*32)
edge=lambda n,a,b: PoolTradeHint(key(n),key(a),key(b))
def test_shortest_reversible_deterministic_paths():
    pools=[edge(10,1,2),edge(11,2,3),edge(12,1,3)]
    paths=candidate_routes(pools,key(3),key(1))
    assert [len(p) for p in paths]==[1,2]
    assert paths[0][0].input_mint==key(3)
    assert candidate_routes(list(reversed(pools)),key(3),key(1))==paths
    for values in [(pools,key(1),key(4)),(pools,key(1),Pubkey.default()),(pools+[edge(10,1,4)],key(1),key(3))]:
        with pytest.raises(ValueError): candidate_routes(*values)
    with pytest.raises(ValueError): candidate_routes(pools,key(1),key(3),6)

def test_lazy_shortest_path_stops_before_longer_route_budget():
    pools=[]
    n=10
    for a in range(1,10):
        for b in range(a+1,10):
            pools.append(edge(n,a,b));n+=1
    assert len(next(iterate_candidate_routes(pools,key(1),key(2))))==1
    with pytest.raises(ValueError,match="budget"):candidate_routes(pools,key(1),key(2))

def test_hop_limit_does_not_expand_unreachable_terminal_frontier():
    pools=[]
    n=100
    for a in range(1,12):
        for b in range(a+1,12):
            pools.append(edge(n,a,b)); n+=1
    with pytest.raises(ValueError,match="No connected"):
        candidate_routes(pools,key(1),key(200),4)
    with pytest.raises(ValueError,match="budget"):
        candidate_routes(pools,key(1),key(200),5)

def test_all_small_graphs_preserve_breadth_first_lexical_order():
    possible=[edge(100+i,a,b) for i,(a,b) in enumerate([(1,2),(1,3),(1,4),(2,3),(2,4),(3,4)])]
    for mask in range(64):
        pools=[h for i,h in enumerate(possible) if mask & (1<<i)]
        edges=sorted([e for h in pools for e in (h,PoolTradeHint(h.pool,h.output_mint,h.input_mint))],key=lambda h:(str(h.pool),str(h.output_mint)))
        frontier=[((),key(1),{key(1)})]; expected=[]
        for _ in range(3):
            next_paths=[]
            for path,mint,seen in frontier:
                for h in edges:
                    if h.input_mint!=mint or h.output_mint in seen: continue
                    if h.output_mint==key(4): expected.append(path+(h,))
                    else: next_paths.append((path+(h,),h.output_mint,seen|{h.output_mint}))
            frontier=next_paths
        if expected: assert candidate_routes(list(reversed(pools)),key(1),key(4),3)==tuple(expected)
        else:
            with pytest.raises(ValueError,match="No connected"): candidate_routes(pools,key(1),key(4),3)
