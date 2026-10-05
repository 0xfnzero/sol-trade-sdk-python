"""Factory parity for Glaive / LunarLander."""

import uuid

from src.common.types import SwqosRegion, SwqosTransport, SwqosType
from src.swqos.clients import ClientFactory, SwqosConfig, MIN_TIP_GLAIVE, MIN_TIP_LUNARLANDER


def test_lunarlander_http_factory():
    client = ClientFactory.create_client(
        SwqosConfig(
            type=SwqosType.LUNAR_LANDER,
            region=SwqosRegion.DEFAULT,
            api_key="test",
            transport=SwqosTransport.HTTP,
        ),
        "http://localhost:8899",
    )
    assert client.get_swqos_type() == SwqosType.LUNAR_LANDER
    assert client.min_tip_sol() == MIN_TIP_LUNARLANDER


def test_glaive_http_factory():
    client = ClientFactory.create_client(
        SwqosConfig(
            type=SwqosType.GLAIVE,
            region=SwqosRegion.DEFAULT,
            api_key=str(uuid.uuid4()),
            transport=SwqosTransport.HTTP,
        ),
        "http://localhost:8899",
    )
    assert client.get_swqos_type() == SwqosType.GLAIVE
    assert client.min_tip_sol() == MIN_TIP_GLAIVE
