import json,base64,copy
from pathlib import Path
import pytest
from examples.cached_trade import prepare
@pytest.mark.parametrize('side',['buy','sell'])
def test_cached_holder_bank(side):
 v=json.loads((Path(__file__).parent/f'fixtures/pump_holder_cached_{side}_20261009.json').read_text())
 p=prepare(v)
 assert p.route.legs[0].estimated_net_amount_out==int(v['expected']['estimated_out'])
 assert p.route.minimum_net_amount_out==int(v['expected']['minimum_out'])
 for value in [0,2]:
  bad=copy.deepcopy(v)
  a=next(a for a in bad['accounts']if a['pubkey']==v['legs'][0]['pool']);b=bytearray(base64.b64decode(a['data']))
  if value==0:b[49:81]=bytes(32)
  else:b[124]=value
  a['data']=base64.b64encode(b).decode()
  with pytest.raises(ValueError,match='holder-reward'):prepare(bad)
