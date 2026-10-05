"""Glaive / LunarLander SWQoS parity smoke tests (Rust 5.0.2)."""

from src.common.types import SwqosRegion, SwqosType
from src.swqos.clients import (
    GLAIVE_ENDPOINTS,
    GLAIVE_QUIC_ENDPOINTS,
    LUNARLANDER_ENDPOINTS,
    LUNARLANDER_QUIC_ENDPOINTS,
    MIN_TIP_GLAIVE,
    MIN_TIP_LUNARLANDER,
    ClientFactory,
    GlaiveClient,
    GlaiveQuicClient,
    LunarLanderClient,
    LunarLanderQuicClient,
    SwqosConfig,
    _build_glaive_auth_frame,
    _build_glaive_binary_url,
)
from src.swqos.providers import SwqosClientFactory
from src.swqos.providers import SwqosType as ProviderSwqosType


TEST_UUID = "00112233-4455-4677-8899-aabbccddeeff"


def test_endpoints_and_min_tips_match_rust():
    assert MIN_TIP_LUNARLANDER == 0.001
    assert MIN_TIP_GLAIVE == 0.0001
    assert LUNARLANDER_ENDPOINTS[SwqosRegion.FRANKFURT] == (
        "http://fra-1.prod.lunar-lander.hellomoon.io"
    )
    assert LUNARLANDER_QUIC_ENDPOINTS[SwqosRegion.FRANKFURT] == (
        "fra-1.prod.lunar-lander.hellomoon.io:16888"
    )
    assert GLAIVE_ENDPOINTS[SwqosRegion.FRANKFURT] == "http://fra.glaive.trade"
    assert GLAIVE_QUIC_ENDPOINTS[SwqosRegion.FRANKFURT] == "fra.glaive.trade:4000"


def test_factory_defaults_to_quic():
    lunar = ClientFactory.create_client(
        SwqosConfig(type=SwqosType.LUNAR_LANDER, region=SwqosRegion.FRANKFURT, api_key="k"),
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


def test_glaive_http_and_auth_frame():
    from src.common.types import SwqosType as _  # noqa: F401
    # transport Http via string value used by factory
    http = ClientFactory.create_client(
        SwqosConfig(
            type=SwqosType.GLAIVE,
            region=SwqosRegion.FRANKFURT,
            api_key=TEST_UUID,
            transport=type("T", (), {"value": "Http"})(),
        ),
        "https://rpc.example",
    )
    assert isinstance(http, GlaiveClient)

    url = _build_glaive_binary_url("http://fra.glaive.trade", TEST_UUID, True)
    assert "/binary" in url
    assert f"api-key={TEST_UUID}" in url
    assert "mev-protect=true" in url

    frame = _build_glaive_auth_frame(TEST_UUID, True)
    assert frame[:16] == bytes.fromhex("00112233445546778899aabbccddeeff")
    assert frame[16] == 1


def test_glaive_rejects_grpc():
    try:
        ClientFactory.create_client(
            SwqosConfig(
                type=SwqosType.GLAIVE,
                region=SwqosRegion.FRANKFURT,
                api_key=TEST_UUID,
                transport=type("T", (), {"value": "Grpc"})(),
            ),
            "https://rpc.example",
        )
        assert False, "expected gRPC rejection"
    except ValueError as exc:
        assert "gRPC" in str(exc)


def test_provider_factory_lists_new_types():
    supported = SwqosClientFactory.get_supported_types()
    assert ProviderSwqosType.LUNAR_LANDER in supported
    assert ProviderSwqosType.GLAIVE in supported
