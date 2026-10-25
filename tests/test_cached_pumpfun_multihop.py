import json,hashlib,base64
from dataclasses import replace
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from solders.instruction import Instruction
from examples.cached_trade import prepare
from src.trading.pumpfun_settlement import settle_pumpfun_native_quote
ROOT=Path(__file__).parents[1]/'examples/fixtures'

@pytest.mark.parametrize('direction',['buy','sell'])
def test_instruction_versions_keep_protected_hops(direction,monkeypatch):
    import socket
    from sol_trade_sdk import TradeConfig, PumpFunVersion
    monkeypatch.setattr(socket.socket,'connect',lambda *a:pytest.fail('network in preparation'))
    assert TradeConfig.builder('http://localhost').build().pumpfun_version == PumpFunVersion.V3
    v=json.loads((ROOT/f'pumpfun_whirlpool_usdc_{direction}_20261005.json').read_text())
    discriminators=([bytes(x) for x in ([56,252,116,8,158,223,205,95],[194,171,28,70,104,77,91,47],[225,247,80,30,213,179,132,136])]
        if direction=='buy' else [bytes(x) for x in ([51,230,133,164,1,127,131,173],[93,246,130,60,231,233,64,178],[28,146,222,119,38,196,105,213])])
    protected = prepare(v)
    options = {"minimum_output_amount":"1", "buyback_recipient":v["payer"]}
    fallback = prepare(dict(v, pump_route=options))
    assert fallback.compiled.message == protected.compiled.message
    with pytest.raises(ValueError): prepare(dict(v, pump_route=dict(options,execution="official")))
    with pytest.raises(ValueError,match="final output"): prepare(dict(v, pump_route=dict(options,minimum_output_amount=str((1<<64)-1))))
    outputs=[]
    for version,disc in zip(('v1','v2','v3'),discriminators):
        p=prepare(dict(v,pumpfun_version=version))
        anchor=p.route.legs[-1 if direction=='buy' else 0]
        assert anchor.instruction.data[:8]==disc
        assert int.from_bytes(anchor.instruction.data[8:16],'little')==anchor.amount_in
        assert int.from_bytes(anchor.instruction.data[16:24],'little')==anchor.minimum_net_amount_out
        if version=='v3':assert len(anchor.instruction.accounts)==17
        outputs.append(p.route.minimum_net_amount_out)
    assert len(set(outputs))==1
    candidates = [dict(h,pumpfun_version="v2") for h in v["legs"]]
    for reverse in (False,True):
        ordered = [dict(h,input_mint=h["output_mint"],output_mint=h["input_mint"]) for h in candidates] if reverse else candidates
        p = prepare(dict(v,legs=[],candidates=ordered,input_mint=v["legs"][0]["input_mint"],
            output_mint=v["legs"][-1]["output_mint"],pumpfun_version="v3"))
        anchor = p.route.legs[-1 if direction=="buy" else 0]
        assert anchor.hint.pumpfun_version == "v2"
        assert len(anchor.instruction.accounts) == (27 if direction=="buy" else 26)

@pytest.mark.parametrize('protocol',['whirlpool','dlmm','clmm'])
@pytest.mark.parametrize('direction',['buy','sell'])
def test_concentrated_native_quote_simulation_and_missing_array(protocol,direction,monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a:pytest.fail('network in preparation'))
    name=f'pumpfun_{protocol}_usdc_{direction}_20261005.json'
    v=json.loads((ROOT/name).read_text());p=prepare(v)
    wire=p.compiled.message+bytes(64*p.compiled.required_signatures)
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
    assert p.route.minimum_net_amount_out==int(v['expected']['minimum_out'])
    assert p.estimated_native_residual_lamports==int(v['expected']['estimated_native_residual_lamports'])
    evidence=json.loads((ROOT/'pumpfun_concentrated_multihop_simulations_20261005.json').read_text())
    r=next(r for r in evidence['records'] if r['fixture']==name)
    assert r['response']['result']['value']['err'] is None
    assert int(r['verified_balances']['input_debit'])==int(v['amount'])
    assert int(r['verified_balances']['output_credit'])>=p.route.minimum_net_amount_out
    assert int(r['verified_balances']['wsol_delta'])>=0
    # Remove the array actually referenced by the swap, rather than an unused historical array.
    hop=p.route.legs[0 if direction=='buy' else 1].instruction
    index=11 if protocol=='whirlpool' else (16 if protocol=='dlmm' else len(hop.accounts)-1)
    address=str(hop.accounts[index].pubkey)
    v['accounts']=[a for a in v['accounts'] if a['pubkey']!=address]
    with pytest.raises(ValueError,match='[Mm]issing|[Nn]ot.*cache'):prepare(v)

@pytest.mark.parametrize('direction',['buy','sell'])
def test_actual_usdc_multihop_wire_and_residuals(direction,monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a:pytest.fail('network in preparation'))
    v=json.loads((ROOT/f'pumpfun_usdc_{direction}_20261004.json').read_text())
    p=prepare(v);wire=p.compiled.message+bytes(64*p.compiled.required_signatures)
    assert hashlib.sha256(wire).hexdigest()==v['expected']['wire_sha256']
    assert p.route.minimum_net_amount_out==int(v['expected']['minimum_out'])
    assert p.estimated_native_residual_lamports==int(v['expected']['estimated_native_residual_lamports'])
    assert [(str(m),str(a)) for m,a in p.route.estimated_intermediate_residuals]==[(r['mint'],r['amount']) for r in v['expected']['estimated_intermediate_residuals']]

@pytest.mark.parametrize('direction',['buy','sell'])
def test_reject_overconsuming_intermediate_or_wrong_wallet(direction):
    v=json.loads((ROOT/f'pumpfun_usdc_{direction}_20261004.json').read_text());p=prepare(v);payer=Pubkey.from_string(v['payer'])
    legs=(replace(p.route.legs[0],minimum_net_amount_out=p.route.legs[1].amount_in-1),p.route.legs[1])
    with pytest.raises(ValueError,match='protected intermediate credit'):
        settle_pumpfun_native_quote(replace(p.route,legs=legs),payer,False,False,'p',int(v['rent_lamports']))
    with pytest.raises(ValueError,match='different wallet'):
        settle_pumpfun_native_quote(p.route,Pubkey.new_unique(),False,False,'p',int(v['rent_lamports']))
    swaps=list(p.route.swap_instructions);ix=swaps[0]
    swaps[0]=Instruction(ix.program_id,ix.data+b'\0',ix.accounts)
    with pytest.raises(ValueError,match='differs from quoted leg'):
        settle_pumpfun_native_quote(replace(p.route,swap_instructions=tuple(swaps)),payer,False,False,'p',int(v['rent_lamports']))
    with pytest.raises(ValueError,match='multi-hop endpoints'):
        settle_pumpfun_native_quote(p.route,payer,True,False,'p',int(v['rent_lamports']))

def test_non_native_anchor_cannot_enable_other_native_curve():
    v=json.loads((ROOT/'pumpfun_usdc_buy_20261004.json').read_text())
    other=json.loads((ROOT/'pumpfun_current_0_sol_buy_20261004.json').read_text())
    usdc=v['legs'][0]['input_mint'];wsol=v['legs'][0]['output_mint'];anchor_pool=v['legs'][1]['pool']
    for a in v['accounts']:
        if a['pubkey']==anchor_pool:
            d=bytearray(base64.b64decode(a['data']));d[83:115]=bytes(Pubkey.from_string(usdc));a['data']=base64.b64encode(d).decode()
    extra=other['legs'][0]
    v['legs']=[{'pool':extra['pool'],'input_mint':extra['output_mint'],'output_mint':wsol},{'pool':v['legs'][0]['pool'],'input_mint':wsol,'output_mint':usdc},{'pool':anchor_pool,'input_mint':usdc,'output_mint':v['legs'][1]['output_mint']}]
    for a in other['accounts']:
        if a['pubkey'] in (extra['pool'],extra['output_mint']):v['accounts'].append(dict(a,slot=v['read_slot']))
    v['amount']='100000000'
    with pytest.raises(ValueError,match='requires cached trade settlement'):prepare(v)


@pytest.mark.parametrize("direction", ["Buy", "Sell"])
def test_official_aggregate_from_frozen_curves(direction, monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *a: pytest.fail("network in preparation"))
    # Synthetic chain from existing captures; these are not mainnet route quotes.
    v=json.loads((ROOT/"pumpfun_usdc_buy_20261004.json").read_text())
    extra=json.loads((ROOT/"pumpfun_current_0_sol_buy_20261004.json").read_text())
    currency=v["legs"][0]["input_mint"]; middle=extra["legs"][0]["output_mint"]; target=v["legs"][1]["output_mint"]
    def curve(a, quote):
        d=bytearray(base64.b64decode(a["data"])); d[83:115]=bytes(Pubkey.from_string(quote))
        return dict(a, data=base64.b64encode(d).decode(), slot=v["read_slot"])
    v["accounts"]=[curve(a,middle) if a["pubkey"]==v["legs"][1]["pool"] else a for a in v["accounts"]]
    v["accounts"] += [dict(a,slot=v["read_slot"]) if a["pubkey"]==middle else curve(a,currency) for a in extra["accounts"] if a["pubkey"] in (middle,extra["legs"][0]["pool"])]
    v["legs"]=[dict(pool=extra["legs"][0]["pool"],input_mint=currency,output_mint=middle),dict(pool=v["legs"][1]["pool"],input_mint=middle,output_mint=target)]
    if direction=="Sell": v["legs"]=[dict(h,input_mint=h["output_mint"],output_mint=h["input_mint"]) for h in reversed(v["legs"])]
    v["trade_type"]=direction
    options=dict(minimum_output_amount="7",buyback_recipient=v["payer"])
    p=prepare(dict(v,pump_route=options)); strict=prepare(dict(v,pump_route=dict(options,execution="official")))
    assert p.compiled.message==strict.compiled.message
    assert p.route.execution=="official" and not p.route.legs
    assert len(p.route.swap_instructions)==1 and len(p.route.setup_instructions)==3
    assert p.route.minimum_net_amount_out==7
    ix=p.route.swap_instructions[0]
    assert int.from_bytes(ix.data[8:16],"little")==int(v["amount"])
    assert int.from_bytes(ix.data[16:24],"little")==7 and len(ix.accounts)==26
