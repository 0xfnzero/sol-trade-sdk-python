"""Minimal factory parity tests for LunarLander / Glaive SWQOS clients."""

import pytest

from src.common.types import SwqosRegion, SwqosType
from src.swqos.clients import (
    ClientFactory,
    GlaiveClient,
    GlaiveQuicClient,
    GLAIVE_ENDPOINTS,
    GLAIVE_QUIC_ENDPOINTS,
    LUNARLANDER_ENDPOINTS,
    LUNARLANDER_QUIC_ENDPOINTS,
    LunarLanderClient,
    LunarLanderQuicClient,
    MIN_TIP_GLAIVE,
    MIN_TIP_LUNARLANDER,
    SwqosConfig,
    _build_glaive_binary_url,
)


TEST_UUID = "550e8400-e29b-41d4-a716-446655440000"


class _Transport:
    def __init__(self, value: str):
        self.value = value


def test_tip_floors_and_endpoints():
    assert MIN_TIP_LUNARLANDER == 0.001
    assert MIN_TIP_GLAIVE == 0.0001
    assert (
        LUNARLANDER_ENDPOINTS[SwqosRegion.FRANKFURT]
        == "http://fra-1.prod.lunar-lander.hellomoon.io"
    )
    assert (
        LUNARLANDER_QUIC_ENDPOINTS[SwqosRegion.FRANKFURT]
        == "fra-1.prod.lunar-lander.hellomoon.io:16888"
    )
    assert GLAIVE_ENDPOINTS[SwqosRegion.FRANKFURT] == "http://fra.glaive.trade"
    assert GLAIVE_QUIC_ENDPOINTS[SwqosRegion.FRANKFURT] == "fra.glaive.trade:4000"


def test_glaive_binary_url():
    url = _build_glaive_binary_url("http://fra.glaive.trade", TEST_UUID, True)
    assert url == f"http://fra.glaive.trade/binary?api-key={TEST_UUID}&mev-protect=true"


def test_factory_defaults_to_quic():
    lunar = ClientFactory.create_client(
        SwqosConfig(type=SwqosType.LUNAR_LANDER, region=SwqosRegion.FRANKFURT, api_key="key"),
        "https://rpc.example",
    )
    assert isinstance(lunar, LunarLanderQuicClient)
    assert lunar.min_tip_sol() == MIN_TIP_LUNARLANDER

    glaive = ClientFactory.create_client(
        SwqosConfig(type=SwqosType.GLAIVE, region=SwqosRegion.FRANKFURT, api_key=TEST_UUID),
        "https://rpc.example",
    )
    assert isinstance(glaive, GlaiveQuicClient)
    assert glaive.min_tip_sol() == MIN_TIP_GLAIVE


def test_factory_http_transport():
    lunar = ClientFactory.create_client(
        SwqosConfig(
            type=SwqosType.LUNAR_LANDER,
            region=SwqosRegion.FRANKFURT,
            api_key="key",
            transport=_Transport("Http"),
        ),
        "https://rpc.example",
    )
    assert isinstance(lunar, LunarLanderClient)

    glaive = ClientFactory.create_client(
        SwqosConfig(
            type=SwqosType.GLAIVE,
            region=SwqosRegion.FRANKFURT,
            api_key=TEST_UUID,
            transport=_Transport("Http"),
        ),
        "https://rpc.example",
    )
    assert isinstance(glaive, GlaiveClient)


def test_glaive_rejects_grpc_and_bad_uuid():
    with pytest.raises(ValueError, match="gRPC"):
        ClientFactory.create_client(
            SwqosConfig(
                type=SwqosType.GLAIVE,
                api_key=TEST_UUID,
                transport=_Transport("Grpc"),
            ),
            "https://rpc.example",
        )

    with pytest.raises(ValueError, match="UUID v4"):
        ClientFactory.create_client(
            SwqosConfig(
                type=SwqosType.GLAIVE,
                api_key="not-a-uuid",
                transport=_Transport("Http"),
            ),
            "https://rpc.example",
        )
