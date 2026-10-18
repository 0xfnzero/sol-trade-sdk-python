"""Deployed SBF execution, not a quote mock or wire-only validation."""
import pytest
from examples.pumpswap_bank_replay import execute


@pytest.mark.parametrize('is_buy', [True, False])
@pytest.mark.parametrize('use_alt', [False, True])
@pytest.mark.parametrize('reject', [False, True])
def test_pumpswap_deployed_bank_repeatability(is_buy, use_alt, reject):
    assert execute(is_buy, use_alt, reject) == execute(is_buy, use_alt, reject)


@pytest.mark.parametrize('is_buy', [True, False])
@pytest.mark.parametrize('reject', [False, True])
def test_pumpswap_three_hop_deployed_bank_repeatability(is_buy, reject):
    assert execute(is_buy, True, reject, True) == execute(is_buy, True, reject, True)
