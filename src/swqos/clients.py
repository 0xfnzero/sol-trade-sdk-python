"""
SWQOS Clients for Sol Trade SDK
Implements various SWQOS (Solana Write Queue Operating System) providers.
"""

import asyncio
import base64
import contextlib
import datetime
import json
import random
import ssl
import struct
import ipaddress
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, urlparse

import aiohttp
import base58
from solders.keypair import Keypair

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    import aioquic  # noqa: F401 - just check availability
    from aioquic.asyncio import connect as quic_connect
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.asyncio.protocol import QuicConnectionProtocol
    from aioquic.h3.connection import H3_ALPN, H3Connection
    from aioquic.h3.events import DataReceived, HeadersReceived
    from aioquic.quic.events import ConnectionTerminated, ProtocolNegotiated

    _QUIC_AVAILABLE = True
except ImportError:
    _QUIC_AVAILABLE = False
    QuicConfiguration = object  # type: ignore[misc,assignment]
    QuicConnectionProtocol = object  # type: ignore[misc,assignment]
    quic_connect = None  # type: ignore[assignment]
    H3_ALPN = []  # type: ignore[assignment]
    H3Connection = object  # type: ignore[misc,assignment]
    ConnectionTerminated = DataReceived = HeadersReceived = ProtocolNegotiated = object  # type: ignore[assignment,misc]

try:
    import grpc  # type: ignore[import-untyped]
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory  # type: ignore[import-untyped]

    _GRPC_AVAILABLE = True
except ImportError:
    grpc = None  # type: ignore[assignment]
    _GRPC_AVAILABLE = False

from ..common.types import SwqosType, SwqosRegion, TradeType

SWQOS_BLACKLISTED_TYPES = {SwqosType.NEXT_BLOCK}


def is_swqos_type_blacklisted(swqos_type: SwqosType) -> bool:
    return getattr(swqos_type, "value", swqos_type) in {
        item.value for item in SWQOS_BLACKLISTED_TYPES
    }


# ===== Constants =====

# Minimum tips in SOL for each provider
MIN_TIP_JITO = 0.00001
MIN_TIP_BLOXROUTE = 0.0001
MIN_TIP_ZERO_SLOT = 0.0001
MIN_TIP_TEMPORAL = 0.0001
MIN_TIP_FLASH_BLOCK = 0.0001
MIN_TIP_BLOCK_RAZOR = 0.0001
MIN_TIP_NODE1 = 0.0001
MIN_TIP_ASTRALANE = 0.00001
MIN_TIP_HELIUS = 0.000005  # swqos_only mode
MIN_TIP_HELIUS_NORMAL = 0.0002  # normal mode
MIN_TIP_STELLIUM = 0.0001
MIN_TIP_LIGHTSPEED = 0.0001
MIN_TIP_NEXT_BLOCK = 0.001
MIN_TIP_SOYAS = 0.001
MIN_TIP_SPEEDLANDING = 0.001
MIN_TIP_SOLAMI = 0.0001
MIN_TIP_LUNARLANDER = 0.001
MIN_TIP_GLAIVE = 0.0001
MIN_TIP_DEFAULT = 0.00001


# ===== Tip Accounts =====

JITO_TIP_ACCOUNTS = [
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
]

ZERO_SLOT_TIP_ACCOUNTS = [
    "Eb2KpSC8uMt9GmzyAEm5Eb1AAAgTjRaXWFjKyFXHZxF3",
    "FCjUJZ1qozm1e8romw216qyfQMaaWKxWsuySnumVCCNe",
    "ENxTEjSQ1YabmUpXAdCgevnHQ9MHdLv8tzFiuiYJqa13",
    "6rYLG55Q9RpsPGvqdPNJs4z5WTxJVatMB8zV3WJhs5EK",
    "Cix2bHfqPcKcM233mzxbLk14kSggUUiz2A87fJtGivXr",
]

TEMPORAL_TIP_ACCOUNTS = [
    "TEMPaMeCRFAS9EKF53Jd6KpHxgL47uWLcpFArU1Fanq",
    "noz3jAjPiHuBPqiSPkkugaJDkJscPuRhYnSpbi8UvC4",
    "noz3str9KXfpKknefHji8L1mPgimezaiUyCHYMDv1GE",
    "noz6uoYCDijhu1V7cutCpwxNiSovEwLdRHPwmgCGDNo",
    "noz9EPNcT7WH6Sou3sr3GGjHQYVkN3DNirpbvDkv9YJ",
    "nozc5yT15LazbLTFVZzoNZCwjh3yUtW86LoUyqsBu4L",
    "nozFrhfnNGoyqwVuwPAW4aaGqempx4PU6g6D9CJMv7Z",
    "nozievPk7HyK1Rqy1MPJwVQ7qQg2QoJGyP71oeDwbsu",
    "noznbgwYnBLDHu8wcQVCEw6kDrXkPdKkydGJGNXGvL7",
    "nozNVWs5N8mgzuD3qigrCG2UoKxZttxzZ85pvAQVrbP",
    "nozpEGbwx4BcGp6pvEdAh1JoC2CQGZdU6HbNP1v2p6P",
    "nozrhjhkCr3zXT3BiT4WCodYCUFeQvcdUkM7MqhKqge",
    "nozrwQtWhEdrA6W8dkbt9gnUaMs52PdAv5byipnadq3",
    "nozUacTVWub3cL4mJmGCYjKZTnE9RbdY5AP46iQgbPJ",
    "nozWCyTPppJjRuw2fpzDhhWbW355fzosWSzrrMYB1Qk",
    "nozWNju6dY353eMkMqURqwQEoM3SFgEKC6psLCSfUne",
    "nozxNBgWohjR75vdspfxR5H9ceC7XXH99xpxhVGt3Bb",
]

FLASH_BLOCK_TIP_ACCOUNTS = [
    "FLaShB3iXXTWE1vu9wQsChUKq3HFtpMAhb8kAh1pf1wi",
    "FLashhsorBmM9dLpuq6qATawcpqk1Y2aqaZfkd48iT3W",
    "FLaSHJNm5dWYzEgnHJWWJP5ccu128Mu61NJLxUf7mUXU",
    "FLaSHR4Vv7sttd6TyDF4yR1bJyAxRwWKbohDytEMu3wL",
    "FLASHRzANfcAKDuQ3RXv9hbkBy4WVEKDzoAgxJ56DiE4",
    "FLasHstqx11M8W56zrSEqkCyhMCCpr6ze6Mjdvqope5s",
    "FLAShWTjcweNT4NSotpjpxAkwxUr2we3eXQGhpTVzRwy",
    "FLasHXTqrbNvpWFB6grN47HGZfK6pze9HLNTgbukfPSk",
    "FLAShyAyBcKb39KPxSzXcepiS8iDYUhDGwJcJDPX4g2B",
    "FLAsHZTRcf3Dy1APaz6j74ebdMC6Xx4g6i9YxjyrDybR",
]

HELIUS_TIP_ACCOUNTS = [
    "4ACfpUFoaSD9bfPdeu6DBt89gB6ENTeHBXCAi87NhDEE",
    "D2L6yPZ2FmmmTKPgzaMKdhu6EWZcTpLy1Vhx8uvZe7NZ",
    "9bnz4RShgq1hAnLnZbP8kbgBg1kEmcJBYQq3gQbmnSta",
    "5VY91ws6B2hMmBFRsXkoAAdsPHBJwRfBht4DXox3xkwn",
    "2nyhqdwKcJZR2vcqCyrYsaPVdAnFoJjiksCXJ7hfEYgD",
    "2q5pghRs6arqVjRvT5gfgWfWcHWmw1ZuCzphgd5KfWGJ",
    "wyvPkWjVZz1M8fHQnMMCDTQDbkManefNNhweYk5WkcF",
    "3KCKozbAaF75qEU33jtzozcJ29yJuaLJTy2jFdzUY8bT",
    "4vieeGHPYPG2MmyPRcYjdiDmmhN3ww7hsFNap8pVN3Ey",
    "4TQLFNWK8AovT1gFvda5jfw2oJeRMKEmw7aH6MGBJ3or",
]

NODE1_TIP_ACCOUNTS = [
    "node1PqAa3BWWzUnTHVbw8NJHC874zn9ngAkXjgWEej",
    "node1UzzTxAAeBTpfZkQPJXBAqixsbdth11ba1NXLBG",
    "node1Qm1bV4fwYnCurP8otJ9s5yrkPq7SPZ5uhj3Tsv",
    "node1PUber6SFmSQgvf2ECmXsHP5o3boRSGhvJyPMX1",
    "node1AyMbeqiVN6eoQzEAwCA6Pk826hrdqdAHR7cdJ3",
    "node1YtWCoTwwVYTFLfS19zquRQzYX332hs1HEuRBjC",
]

BLOCK_RAZOR_TIP_ACCOUNTS = [
    "FjmZZrFvhnqqb9ThCuMVnENaM3JGVuGWNyCAxRJcFpg9",
    "6No2i3aawzHsjtThw81iq1EXPJN6rh8eSJCLaYZfKDTG",
    "A9cWowVAiHe9pJfKAj3TJiN9VpbzMUq6E4kEvf5mUT22",
    "Gywj98ophM7GmkDdaWs4isqZnDdFCW7B46TXmKfvyqSm",
    "68Pwb4jS7eZATjDfhmTXgRJjCiZmw1L7Huy4HNpnxJ3o",
    "4ABhJh5rZPjv63RBJBuyWzBK3g9gWMUQdTZP2kiW31V9",
    "B2M4NG5eyZp5SBQrSdtemzk5TqVuaWGQnowGaCBt8GyM",
    "5jA59cXMKQqZAVdtopv8q3yyw9SYfiE3vUCbt7p8MfVf",
    "5YktoWygr1Bp9wiS1xtMtUki1PeYuuzuCF98tqwYxf61",
    "295Avbam4qGShBYK7E9H5Ldew4B3WyJGmgmXfiWdeeyV",
    "EDi4rSy2LZgKJX74mbLTFk4mxoTgT6F7HxxzG2HBAFyK",
    "BnGKHAC386n4Qmv9xtpBVbRaUTKixjBe3oagkPFKtoy6",
    "Dd7K2Fp7AtoN8xCghKDRmyqr5U169t48Tw5fEd3wT9mq",
    "AP6qExwrbRgBAVaehg4b5xHENX815sMabtBzUzVB4v8S",
]

ASTRALANE_TIP_ACCOUNTS = [
    "astrazznxsGUhWShqgNtAdfrzP2G83DzcWVJDxwV9bF",
    "astra4uejePWneqNaJKuFFA8oonqCE1sqF6b45kDMZm",
    "astra9xWY93QyfG6yM8zwsKsRodscjQ2uU2HKNL5prk",
    "astraRVUuTHjpwEVvNBeQEgwYx9w9CFyfxjYoobCZhL",
    "astraEJ2fEj8Xmy6KLG7B3VfbKfsHXhHrNdCQx7iGJK",
    "astraubkDw81n4LuutzSQ8uzHCv4BhPVhfvTcYv8SKC",
    "astraZW5GLFefxNPAatceHhYjfA1ciq9gvfEg2S47xk",
    "astrawVNP4xDBKT7rAdxrLYiTSTdqtUr63fSMduivXK",
    "AstrA1ejL4UeXC2SBP4cpeEmtcFPZVLxx3XGKXyCW6to",
    "AsTra79FET4aCKWspPqeSFvjJNyp96SvAnrmyAxqg5b7",
    "AstrABAu8CBTyuPXpV4eSCJ5fePEPnxN8NqBaPKQ9fHR",
    "AsTRADtvb6tTmrsqULQ9Wji9PigDMjhfEMza6zkynEvV",
    "AsTRAEoyMofR3vUPpf9k68Gsfb6ymTZttEtsAbv8Bk4d",
    "AStrAJv2RN2hKCHxwUMtqmSxgdcNZbihCwc1mCSnG83W",
    "Astran35aiQUF57XZsmkWMtNCtXGLzs8upfiqXxth2bz",
    "AStRAnpi6kFrKypragExgeRoJ1QnKH7pbSjLAKQVWUum",
    "ASTRaoF93eYt73TYvwtsv6fMWHWbGmMUZfVZPo3CRU9C",
]

BLOXROUTE_TIP_ACCOUNTS = [
    "HWEoBxYs7ssKuudEjzjmpfJVX7Dvi7wescFsVx2L5yoY",
    "95cfoy472fcQHaw4tPGBTKpn6ZQnfEPfBgDQx6gcRmRg",
    "3UQUKjhMKaY2S6bjcQD6yHB7utcZt5bfarRCmctpRtUd",
    "FogxVNs6Mm2w9rnGL1vkARSwJxvLE8mujTv3LK8RnUhF",
]

STELLIUM_TIP_ACCOUNTS = [
    "ste11JV3MLMM7x7EJUM2sXcJC1H7F4jBLnP9a9PG8PH",
    "ste11MWPjXCRfQryCshzi86SGhuXjF4Lv6xMXD2AoSt",
    "ste11p5x8tJ53H1NbNQsRBg1YNRd4GcVpxtDw8PBpmb",
    "ste11p7e2KLYou5bwtt35H7BM6uMdo4pvioGjJXKFcN",
    "ste11TMV68LMi1BguM4RQujtbNCZvf1sjsASpqgAvSX",
]

LIGHTSPEED_TIP_ACCOUNTS = [
    "53PhM3UTdMQWu5t81wcd35AHGc5xpmHoRjem7GQPvXjA",
    "9tYF5yPDC1NP8s6diiB3kAX6ZZnva9DM3iDwJkBRarBB",
]

NEXT_BLOCK_TIP_ACCOUNTS = [
    "NextbLoCkVtMGcV47JzewQdvBpLqT9TxQFozQkN98pE",
    "NexTbLoCkWykbLuB1NkjXgFWkX9oAtcoagQegygXXA2",
    "NeXTBLoCKs9F1y5PJS9CKrFNNLU1keHW71rfh7KgA1X",
    "NexTBLockJYZ7QD7p2byrUa6df8ndV2WSd8GkbWqfbb",
    "neXtBLock1LeC67jYd1QdAa32kbVeubsfPNTJC1V5At",
    "nEXTBLockYgngeRmRrjDV31mGSekVPqZoMGhQEZtPVG",
    "NEXTbLoCkB51HpLBLojQfpyVAMorm3zzKg7w9NFdqid",
    "nextBLoCkPMgmG8ZgJtABeScP35qLa2AMCNKntAP7Xc",
]

SOYAS_TIP_ACCOUNTS = [
    "soyas4s6L8KWZ8rsSk1mF3d1mQScoTGGAgjk98bF8nP",
    "soyascXFW5wEEYiwfEmHy2pNwomqzvggJosGVD6TJdY",
    "soyasDBdKjADwPz3xk82U3TNPRDKEWJj7wWLajNHZ1L",
    "soyasE2abjBAynmHbGWgEwk4ctBy7JMTUCNrMbjcnyH",
    "soyasi59njacMUPvo3TM5paHjeK8pYSdovXgFi32gRt",
    "soyasQYhJxv8uZgWDxhg72td6piAf7XTkoyWHtSATEz",
    "soyastP66xyYC8XADXZjdMM5BAVGD2YRvz8dwtLsqb8",
    "soyasvdgUJWYcUCzDxpmjUnNjH7KamXLXTzLwFvdVPE",
    "soyasvxAunisNxaoRxkKGjNir7KmbwYnr37JmefkX9G",
    "soyas5doVFUwH8s5zK8gEvCL5KR5ogDmf52LsrJEZ9h",
]

SPEEDLANDING_TIP_ACCOUNTS = [
    "SpEEdz8S1KorkMZqjMUxfxrmWwofmp6ReNP2Nx6CUmq",
    "SpeeDy3GJM4wcrQmk1itRFWgidvxX4rwjTLMv78wwjE",
    "SPeEdva37vW8vRtqgYjprQs1g3965icfVN5Rt7SMAyh",
    "speEdrSEpox5GUfHWcBc7tQjRuSfUin2yvB7qoYvvJh",
    "SPeEDmkHkN3A2roSZf6aZyEMsmrGqTHKqwP51y2Y4rV",
    "SpeedLdTJXh2RKpXEaP8JCxkWoUVXhtdPQ1EnxBJMxc",
    "SpEediGKLbbXndSYTzwmz6Z3NDgHQLDcTDEvGFkSMH9",
    "speede8xCcUq2Tiv1efXeTuE3k9TDNq8TnGKaKSc6J4",
]

SOLAMI_TIP_ACCOUNTS = [
    "15qWd4huAkoxvhDsHMfpUn27TW1YBYMMJJ2jkAkbeam",
    "9XuGciSwr5wb7dLTQm91JhuBTvj3GG8WjuRDc3obeam",
    "kiQioJNyFG7pU36ELLsRKXkeT48kFbk3b6rSgrWbeam",
    "kjmVhW1UzJrW2sU5bY5NtZ79jpvjSStsj37Pzmabeam",
    "kREnjPWFpt4AHeY5pijPmyXaCrMnbatUQJo7d3Xbeam",
    "praRZG6N6MdbsT4EFpKgZJWReZGXQhAMFcH68oCbeam",
    "SqoKQKU5uwBxovq3R7yEBxFwptc4z7vwoghU3M9beam",
    "sV72TY66T1RfmDSeHPPbwX6wwJ3bBv5hd4ehJ8tbeam",
    "swf8MyEeLo7gtRUo27UuJj6naCASUrypU7dbteSbeam",
    "uiuaQsxA47JybQAVN4FTfYuoEDkMiXV1r591Aewbeam",
]

LUNARLANDER_TIP_ACCOUNTS = [
    "moon17L6BgxXRX5uHKudAmqVF96xia9h8ygcmG2sL3F",
    "moon26Sek222Md7ZydcAGxoKG832DK36CkLrS3PQY4c",
    "moon7fwyajcVstMoBnVy7UBcTx87SBtNoGGAaH2Cb8V",
    "moonBtH9HvLHjLqi9ivyrMVKgFUsSfrz9BwQ9khhn1u",
    "moonCJg8476LNFLptX1qrK8PdRsA1HD1R6XWyu9MB93",
    "moonF2sz7qwAtdETnrgxNbjonnhGGjd6r4W4UC9284s",
    "moonKfftMiGSak3cezvhEqvkPSzwrmQxQHXuspC96yj",
    "moonQBUKBpkifLcTd78bfxxt4PYLwmJ5admLW6cBBs8",
    "moonXwpKwoVkMegt5Bc776cSW793X1irL5hHV1vJ3JA",
    "moonZ6u9E2fgk6eWd82621eLPHt9zuJuYECXAYjMY1C",
]

GLAIVE_TIP_ACCOUNTS = [
    "GLaiv4GMRYQmthatDS98uQT4HoucgxWT8NeJz6oSwxeU",
    "GLaivL5uPrDpvd1wTtvat38KGqb5WLhEdqQfnmNd3oNr",
    "GLaivinAWh21NaJMhtExtD5G2gZs1xnvaYVZmwqobWZL",
    "GLaivJSUL71FcocYa8tks5vpVyYzvaDMHtyrzfQF2ABr",
    "GLaivRU6eDKrta3p3psFAWPEFLzCjeMHGpPUuQqTjtyv",
    "GLaivq5dU8qHayz9Qf13LjPfVy3SmUhbmickfGiZdmfh",
]


def _random_tip_account(accounts: List[str]) -> str:
    """Randomly select a tip account from the list"""
    return random.choice(accounts)


def _signature_from_serialized_transaction(transaction: bytes) -> str:
    """V1 signatures trail the message; legacy/v0 signatures precede it."""
    if transaction and transaction[0] == 129:
        def invalid():
            raise TradeError(code=400, message="Malformed or non-single-signature V1 transaction")
        if not 106 <= len(transaction) <= 4096 or transaction[1] != 1:
            invalid()
        mask = int.from_bytes(transaction[4:8], "little")
        instructions, count = transaction[40:42]
        if mask & ~31 or mask & 3 in (1, 2) or not 1 <= count <= 64 or instructions > 64 or transaction[2] != 0 or transaction[3] > count - 1:
            invalid()
        offset = 42 + count * 32 + (8 if mask & 3 else 0) + sum(4 for bit in (4, 8, 16) if mask & bit)
        headers = offset
        offset += instructions * 4
        end = len(transaction) - 64
        if offset > end:
            invalid()
        if len({bytes(transaction[42+32*i:74+32*i]) for i in range(count)}) != count:
            invalid()
        if mask & 16:
            heap=int.from_bytes(transaction[headers-4:headers],"little")
            if not 32768 <= heap <= 262144 or heap % 1024: invalid()
        for i in range(instructions):
            h = headers + i * 4
            program, accounts = transaction[h:h + 2]
            if not 0 < program < count or offset + accounts > end:
                invalid()
            if any(index >= count for index in transaction[offset:offset + accounts]):
                invalid()
            offset += accounts + int.from_bytes(transaction[h + 2:h + 4], "little")
            if offset > end:
                invalid()
        if offset != end:
            invalid()
        return base58.b58encode(transaction[offset:]).decode("ascii")
    if len(transaction) < 65 or transaction[0] != 1:
        raise TradeError(code=400, message="Only single-signature transactions are supported for SWQOS submit")
    return base58.b58encode(transaction[1:65]).decode("ascii")


# ===== Endpoints by Region =====

JITO_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "https://ny.mainnet.block-engine.jito.wtf",
    SwqosRegion.FRANKFURT: "https://frankfurt.mainnet.block-engine.jito.wtf",
    SwqosRegion.AMSTERDAM: "https://amsterdam.mainnet.block-engine.jito.wtf",
    SwqosRegion.DUBLIN: "https://dublin.mainnet.block-engine.jito.wtf",
    SwqosRegion.SLC: "https://slc.mainnet.block-engine.jito.wtf",
    SwqosRegion.TOKYO: "https://tokyo.mainnet.block-engine.jito.wtf",
    SwqosRegion.SINGAPORE: "https://singapore.mainnet.block-engine.jito.wtf",
    SwqosRegion.LONDON: "https://london.mainnet.block-engine.jito.wtf",
    SwqosRegion.LOS_ANGELES: "https://slc.mainnet.block-engine.jito.wtf",
    SwqosRegion.DEFAULT: "https://mainnet.block-engine.jito.wtf",
}

BLOXROUTE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "https://ny.solana.dex.blxrbdn.com",
    SwqosRegion.FRANKFURT: "https://germany.solana.dex.blxrbdn.com",
    SwqosRegion.AMSTERDAM: "https://amsterdam.solana.dex.blxrbdn.com",
    SwqosRegion.DUBLIN: "https://uk.solana.dex.blxrbdn.com",
    SwqosRegion.SLC: "https://la.solana.dex.blxrbdn.com",
    SwqosRegion.TOKYO: "https://tokyo.solana.dex.blxrbdn.com",
    SwqosRegion.SINGAPORE: "https://tokyo.solana.dex.blxrbdn.com",
    SwqosRegion.LONDON: "https://uk.solana.dex.blxrbdn.com",
    SwqosRegion.LOS_ANGELES: "https://la.solana.dex.blxrbdn.com",
    SwqosRegion.DEFAULT: "https://global.solana.dex.blxrbdn.com",
}

ZERO_SLOT_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.0slot.trade",
    SwqosRegion.FRANKFURT: "http://de2.0slot.trade",
    SwqosRegion.AMSTERDAM: "http://ams.0slot.trade",
    SwqosRegion.DUBLIN: "http://ams.0slot.trade",
    SwqosRegion.SLC: "http://la.0slot.trade",
    SwqosRegion.TOKYO: "http://jp.0slot.trade",
    SwqosRegion.SINGAPORE: "http://jp.0slot.trade",
    SwqosRegion.LONDON: "http://ams.0slot.trade",
    SwqosRegion.LOS_ANGELES: "http://la.0slot.trade",
    SwqosRegion.DEFAULT: "http://de2.0slot.trade",
}

TEMPORAL_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ewr1.nozomi.temporal.xyz",
    SwqosRegion.FRANKFURT: "http://fra2.nozomi.temporal.xyz",
    SwqosRegion.AMSTERDAM: "http://ams1.nozomi.temporal.xyz",
    SwqosRegion.DUBLIN: "http://lon1.nozomi.temporal.xyz",
    SwqosRegion.SLC: "http://lax1.nozomi.temporal.xyz",
    SwqosRegion.TOKYO: "http://tyo1.nozomi.temporal.xyz",
    SwqosRegion.SINGAPORE: "http://sgp1.nozomi.temporal.xyz",
    SwqosRegion.LONDON: "http://lon1.nozomi.temporal.xyz",
    SwqosRegion.LOS_ANGELES: "http://lax1.nozomi.temporal.xyz",
    SwqosRegion.DEFAULT: "http://fra2.nozomi.temporal.xyz",
}

FLASH_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.flashblock.trade",
    SwqosRegion.FRANKFURT: "http://fra.flashblock.trade",
    SwqosRegion.AMSTERDAM: "http://ams.flashblock.trade",
    SwqosRegion.DUBLIN: "http://london.flashblock.trade",
    SwqosRegion.SLC: "http://slc.flashblock.trade",
    SwqosRegion.TOKYO: "http://tokyo.flashblock.trade",
    SwqosRegion.SINGAPORE: "http://singapore.flashblock.trade",
    SwqosRegion.LONDON: "http://london.flashblock.trade",
    SwqosRegion.LOS_ANGELES: "http://slc.flashblock.trade",
    SwqosRegion.DEFAULT: "http://fra.flashblock.trade",
}

HELIUS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ewr-sender.helius-rpc.com/fast",
    SwqosRegion.FRANKFURT: "http://fra-sender.helius-rpc.com/fast",
    SwqosRegion.AMSTERDAM: "http://ams-sender.helius-rpc.com/fast",
    SwqosRegion.DUBLIN: "http://lon-sender.helius-rpc.com/fast",
    SwqosRegion.SLC: "http://slc-sender.helius-rpc.com/fast",
    SwqosRegion.TOKYO: "http://tyo-sender.helius-rpc.com/fast",
    SwqosRegion.SINGAPORE: "http://sg-sender.helius-rpc.com/fast",
    SwqosRegion.LONDON: "http://lon-sender.helius-rpc.com/fast",
    SwqosRegion.LOS_ANGELES: "http://slc-sender.helius-rpc.com/fast",
    SwqosRegion.DEFAULT: "https://sender.helius-rpc.com/fast",
}

NODE1_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.node1.me",
    SwqosRegion.FRANKFURT: "http://fra.node1.me",
    SwqosRegion.AMSTERDAM: "http://ams.node1.me",
    SwqosRegion.DUBLIN: "http://lon.node1.me",
    SwqosRegion.SLC: "http://ny.node1.me",
    SwqosRegion.TOKYO: "http://tk.node1.me",
    SwqosRegion.SINGAPORE: "http://tk.node1.me",
    SwqosRegion.LONDON: "http://lon.node1.me",
    SwqosRegion.LOS_ANGELES: "http://ny.node1.me",
    SwqosRegion.DEFAULT: "http://fra.node1.me",
}

BLOCK_RAZOR_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://newyork.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.FRANKFURT: "http://frankfurt.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.AMSTERDAM: "http://amsterdam.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.DUBLIN: "http://london.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.SLC: "http://newyork.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.TOKYO: "http://tokyo.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.SINGAPORE: "http://singapore.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.LONDON: "http://london.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.LOS_ANGELES: "http://losangeles.solana.blockrazor.xyz:443/sendTransaction",
    SwqosRegion.DEFAULT: "http://frankfurt.solana.blockrazor.xyz:443/sendTransaction",
}

BLOCK_RAZOR_GRPC_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "newyork.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.FRANKFURT: "frankfurt.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.AMSTERDAM: "amsterdam.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.DUBLIN: "london.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.SLC: "newyork.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.TOKYO: "tokyo.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.SINGAPORE: "singapore.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.LONDON: "london.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.LOS_ANGELES: "losangeles.solana-grpc.blockrazor.xyz:80",
    SwqosRegion.DEFAULT: "frankfurt.solana-grpc.blockrazor.xyz:80",
}

ASTRALANE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.gateway.astralane.io/irisb",
    SwqosRegion.FRANKFURT: "http://fr.gateway.astralane.io/irisb",
    SwqosRegion.AMSTERDAM: "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.DUBLIN: "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.SLC: "http://la.gateway.astralane.io/irisb",
    SwqosRegion.TOKYO: "http://jp.gateway.astralane.io/irisb",
    SwqosRegion.SINGAPORE: "http://sg.gateway.astralane.io/irisb",
    SwqosRegion.LONDON: "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.LOS_ANGELES: "http://la.gateway.astralane.io/irisb",
    SwqosRegion.DEFAULT: "https://edge.astralane.io/irisb",
}

ASTRALANE_QUIC_HOSTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "ny.gateway.astralane.io",
    SwqosRegion.FRANKFURT: "fr.gateway.astralane.io",
    SwqosRegion.AMSTERDAM: "ams.gateway.astralane.io",
    SwqosRegion.DUBLIN: "ams.gateway.astralane.io",
    SwqosRegion.SLC: "la.gateway.astralane.io",
    SwqosRegion.TOKYO: "jp.gateway.astralane.io",
    SwqosRegion.SINGAPORE: "sg.gateway.astralane.io",
    SwqosRegion.LONDON: "ams.gateway.astralane.io",
    SwqosRegion.LOS_ANGELES: "la.gateway.astralane.io",
    SwqosRegion.DEFAULT: "lim.gateway.astralane.io",
}

STELLIUM_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ewr1.flashrpc.com",
    SwqosRegion.FRANKFURT: "http://fra1.flashrpc.com",
    SwqosRegion.AMSTERDAM: "http://ams1.flashrpc.com",
    SwqosRegion.DUBLIN: "http://lhr1.flashrpc.com",
    SwqosRegion.SLC: "http://ewr1.flashrpc.com",
    SwqosRegion.TOKYO: "http://tyo1.flashrpc.com",
    SwqosRegion.SINGAPORE: "http://tyo1.flashrpc.com",
    SwqosRegion.LONDON: "http://lhr1.flashrpc.com",
    SwqosRegion.LOS_ANGELES: "http://ewr1.flashrpc.com",
    SwqosRegion.DEFAULT: "http://fra1.flashrpc.com",
}

NEXT_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.nextblock.io",
    SwqosRegion.FRANKFURT: "http://fra.nextblock.io",
    SwqosRegion.AMSTERDAM: "http://ams.nextblock.io",
    SwqosRegion.DUBLIN: "http://dublin.nextblock.io",
    SwqosRegion.SLC: "http://slc.nextblock.io",
    SwqosRegion.TOKYO: "http://tokyo.nextblock.io",
    SwqosRegion.SINGAPORE: "http://sgp.nextblock.io",
    SwqosRegion.LONDON: "http://london.nextblock.io",
    SwqosRegion.LOS_ANGELES: "http://slc.nextblock.io",
    SwqosRegion.DEFAULT: "http://fra.nextblock.io",
}

SOYAS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "nyc.landing.soyas.xyz:9000",
    SwqosRegion.FRANKFURT: "fra.landing.soyas.xyz:9000",
    SwqosRegion.AMSTERDAM: "ams.landing.soyas.xyz:9000",
    SwqosRegion.DUBLIN: "lon.landing.soyas.xyz:9000",
    SwqosRegion.SLC: "nyc.landing.soyas.xyz:9000",
    SwqosRegion.TOKYO: "tyo.landing.soyas.xyz:9000",
    SwqosRegion.SINGAPORE: "tyo.landing.soyas.xyz:9000",
    SwqosRegion.LONDON: "lon.landing.soyas.xyz:9000",
    SwqosRegion.LOS_ANGELES: "nyc.landing.soyas.xyz:9000",
    SwqosRegion.DEFAULT: "fra.landing.soyas.xyz:9000",
}

SPEEDLANDING_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "nyc.speedlanding.trade:17778",
    SwqosRegion.FRANKFURT: "fra.speedlanding.trade:17778",
    SwqosRegion.AMSTERDAM: "ams.speedlanding.trade:17778",
    SwqosRegion.DUBLIN: "ams.speedlanding.trade:17778",
    SwqosRegion.SLC: "nyc.speedlanding.trade:17778",
    SwqosRegion.TOKYO: "tyo.speedlanding.trade:17778",
    SwqosRegion.SINGAPORE: "sgp.speedlanding.trade:17778",
    SwqosRegion.LONDON: "ams.speedlanding.trade:17778",
    SwqosRegion.LOS_ANGELES: "nyc.speedlanding.trade:17778",
    SwqosRegion.DEFAULT: "fra.speedlanding.trade:17778",
}

SOLAMI_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "beam.solami.dev:11000",
    SwqosRegion.FRANKFURT: "beam.solami.dev:11000",
    SwqosRegion.AMSTERDAM: "beam.solami.dev:11000",
    SwqosRegion.DUBLIN: "beam.solami.dev:11000",
    SwqosRegion.SLC: "beam.solami.dev:11000",
    SwqosRegion.TOKYO: "beam.solami.dev:11000",
    SwqosRegion.SINGAPORE: "beam.solami.dev:11000",
    SwqosRegion.LONDON: "beam.solami.dev:11000",
    SwqosRegion.LOS_ANGELES: "beam.solami.dev:11000",
    SwqosRegion.DEFAULT: "beam.solami.dev:11000",
}

LUNARLANDER_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://nyc-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.FRANKFURT: "http://fra-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.AMSTERDAM: "http://ams-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.DUBLIN: "http://ams-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.SLC: "http://ash-2.prod.lunar-lander.hellomoon.io",
    SwqosRegion.TOKYO: "http://tyo-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.SINGAPORE: "http://tyo-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.LONDON: "http://fra-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.LOS_ANGELES: "http://nyc-1.prod.lunar-lander.hellomoon.io",
    SwqosRegion.DEFAULT: "http://nyc-1.prod.lunar-lander.hellomoon.io",
}

LUNARLANDER_QUIC_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "nyc-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.FRANKFURT: "fra-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.AMSTERDAM: "ams-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.DUBLIN: "ams-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.SLC: "ash-2.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.TOKYO: "tyo-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.SINGAPORE: "tyo-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.LONDON: "fra-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.LOS_ANGELES: "nyc-1.prod.lunar-lander.hellomoon.io:16888",
    SwqosRegion.DEFAULT: "nyc-1.prod.lunar-lander.hellomoon.io:16888",
}

GLAIVE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "http://ny.glaive.trade",
    SwqosRegion.FRANKFURT: "http://fra.glaive.trade",
    SwqosRegion.AMSTERDAM: "http://ams1.glaive.trade",
    SwqosRegion.DUBLIN: "http://lon.glaive.trade",
    SwqosRegion.SLC: "http://ny.glaive.trade",
    SwqosRegion.TOKYO: "http://ams1.glaive.trade",
    SwqosRegion.SINGAPORE: "http://fra.glaive.trade",
    SwqosRegion.LONDON: "http://lon.glaive.trade",
    SwqosRegion.LOS_ANGELES: "http://ny.glaive.trade",
    SwqosRegion.DEFAULT: "http://ams1.glaive.trade",
}

GLAIVE_QUIC_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK: "ny.glaive.trade:4000",
    SwqosRegion.FRANKFURT: "fra.glaive.trade:4000",
    SwqosRegion.AMSTERDAM: "ams1.glaive.trade:4000",
    SwqosRegion.DUBLIN: "lon.glaive.trade:4000",
    SwqosRegion.SLC: "ny.glaive.trade:4000",
    SwqosRegion.TOKYO: "ams1.glaive.trade:4000",
    SwqosRegion.SINGAPORE: "fra.glaive.trade:4000",
    SwqosRegion.LONDON: "lon.glaive.trade:4000",
    SwqosRegion.LOS_ANGELES: "ny.glaive.trade:4000",
    SwqosRegion.DEFAULT: "ams1.glaive.trade:4000",
}


# ===== Error Handling =====


@dataclass
class TradeError(Exception):
    """Trade error with detailed information"""

    code: int
    message: str
    instruction_index: Optional[int] = None

    def __str__(self) -> str:
        return f"TradeError(code={self.code}, message={self.message})"


def _raise_for_http_status(resp: Any, body: Any = None) -> None:
    status = getattr(resp, "status", 200)
    if 200 <= status < 300:
        return
    message = ""
    if isinstance(body, dict):
        err = body.get("error") or body.get("reason") or body.get("message")
        if isinstance(err, dict):
            message = str(err.get("message") or err)
        elif err:
            message = str(err)
    elif body is not None:
        message = str(body)
    message = message.strip() or getattr(resp, "reason", "") or "HTTP error"
    raise TradeError(code=status, message=f"HTTP error: {message}")


def _extract_signature(data: Any) -> str:
    if isinstance(data, dict):
        value = data.get("signature", data.get("result"))
        if isinstance(value, str) and value:
            return value
    elif isinstance(data, str) and data:
        return data
    raise TradeError(code=500, message="missing transaction signature in submit response")


# ===== Interfaces =====


class SwqosClient(ABC):
    """Abstract base class for SWQOS clients"""

    @abstractmethod
    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        """
        Send a transaction via the SWQOS provider.

        Args:
            trade_type: Type of trade (buy/sell)
            transaction: Raw transaction bytes
            wait_confirmation: Whether to wait for confirmation

        Returns:
            Transaction signature as base58 string
        """
        pass

    @abstractmethod
    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        """Send multiple transactions via the SWQOS provider"""
        pass

    @abstractmethod
    def get_tip_account(self) -> str:
        """Get the tip account for this provider"""
        pass

    @abstractmethod
    def get_swqos_type(self) -> SwqosType:
        """Get the SWQOS type"""
        pass

    @abstractmethod
    def min_tip_sol(self) -> float:
        """Get minimum tip in SOL"""
        pass


# ===== HTTP Client Base =====


class HTTPClientMixin:
    """Mixin for HTTP client functionality"""

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=3)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=4,
                keepalive_timeout=300,
            )
            cls._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return cls._session

    @classmethod
    async def close_session(cls) -> None:
        if cls._session and not cls._session.closed:
            await cls._session.close()


def _should_fallback_transport(error: Exception) -> bool:
    if isinstance(error, TradeError):
        return error.code >= 500 or error.code in {408, 425}
    if _GRPC_AVAILABLE and isinstance(error, grpc.aio.AioRpcError):
        return error.code() in {
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.INTERNAL,
        }
    return isinstance(error, (asyncio.TimeoutError, ConnectionError, OSError, aiohttp.ClientError))


class FallbackSwqosClient(SwqosClient):
    """Try the provider's preferred transport, then its official fallback."""

    def __init__(self, primary: SwqosClient, fallback: SwqosClient):
        self.primary = primary
        self.fallback = fallback

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        try:
            return await self.primary.send_transaction(trade_type, transaction, wait_confirmation)
        except Exception as error:
            if not _should_fallback_transport(error):
                raise
            return await self.fallback.send_transaction(trade_type, transaction, wait_confirmation)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        try:
            return await self.primary.send_transactions(trade_type, transactions, wait_confirmation)
        except Exception as error:
            if not _should_fallback_transport(error):
                raise
            return await self.fallback.send_transactions(
                trade_type, transactions, wait_confirmation
            )

    def get_tip_account(self) -> str:
        return self.primary.get_tip_account()

    def get_swqos_type(self) -> SwqosType:
        return self.primary.get_swqos_type()

    def min_tip_sol(self) -> float:
        return self.primary.min_tip_sol()


# ===== Jito Client =====


class JitoClient(SwqosClient, HTTPClientMixin):
    """
    Jito SWQOS client implementation.

    Single tx:  POST {endpoint}/api/v1/transactions  (sendTransaction JSON-RPC)
    Bundle:     POST {endpoint}/api/v1/bundles       (sendBundle JSON-RPC, params = [base64, ...])
    Auth:       Header  x-jito-auth: {token}
                URL query param  ?uuid={token}  (appended when token present)
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(JITO_TIP_ACCOUNTS)

    def _build_url(self, path: str) -> str:
        url = f"{self.endpoint}{path}"
        if self.auth_token:
            url = f"{url}?uuid={self.auth_token}"
        return url

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["x-jito-auth"] = self.auth_token
        return headers

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        session = await self.get_session()
        url = self._build_url("/api/v1/transactions")
        headers = self._build_headers()

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        """Send multiple transactions as a Jito bundle"""
        if not transactions:
            return []

        encoded_txs = [base64.b64encode(tx).decode() for tx in transactions]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [encoded_txs],
        }

        session = await self.get_session()
        url = self._build_url("/api/v1/bundles")
        headers = self._build_headers()

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        bundle_id = _extract_signature(data)
        # Return bundle_id for each transaction as placeholder
        return [bundle_id] * len(transactions)

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.JITO

    def min_tip_sol(self) -> float:
        return MIN_TIP_JITO


# ===== Bloxroute Client =====


class BloxrouteClient(SwqosClient, HTTPClientMixin):
    """
    Bloxroute SWQOS client implementation.

    URL:    {endpoint}/api/v2/submit
    Auth:   Header  Authorization: {token}  (plain token, no Bearer prefix)
    Body:   {"transaction": {"content": "<base64>"}, "frontRunningProtection": false, "useStakedRPCs": true}
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(BLOXROUTE_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "transaction": {"content": encoded},
            "frontRunningProtection": False,
            "useStakedRPCs": True,
        }

        session = await self.get_session()
        url = f"{self.endpoint}/api/v2/submit"

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "reason" in data and data.get("reason"):
            raise TradeError(code=500, message=data["reason"])

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.BLOXROUTE

    def min_tip_sol(self) -> float:
        return MIN_TIP_BLOXROUTE


# ===== ZeroSlot Client =====


class ZeroSlotClient(SwqosClient, HTTPClientMixin):
    """
    ZeroSlot SWQOS client implementation.

    Note: Rust SDK uses bincode serialization over a raw TCP connection.
    Python fallback uses JSON-RPC sendTransaction with api-key as URL query param.

    URL:    {endpoint}?api-key={token}
    Body:   standard JSON-RPC sendTransaction (base64 encoding)
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(ZERO_SLOT_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        if self.auth_token:
            return f"{self.endpoint}?api-key={self.auth_token}"
        return self.endpoint

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "application/json"}

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.ZERO_SLOT

    def min_tip_sol(self) -> float:
        return MIN_TIP_ZERO_SLOT


# ===== Temporal Client =====

TEMPORAL_MAX_BATCH_SIZE = 16
TEMPORAL_MIN_TX_SIZE = 66
TEMPORAL_MAX_TX_SIZE = 1232


def _encode_temporal_batch(transactions: List[bytes]) -> bytes:
    if not transactions:
        raise TradeError(400, "Temporal batch cannot be empty")
    if len(transactions) > TEMPORAL_MAX_BATCH_SIZE:
        raise TradeError(
            400,
            f"Temporal batch has {len(transactions)} transactions; maximum is {TEMPORAL_MAX_BATCH_SIZE}",
        )
    body = bytearray()
    for transaction in transactions:
        if not TEMPORAL_MIN_TX_SIZE <= len(transaction) <= TEMPORAL_MAX_TX_SIZE:
            raise TradeError(
                400,
                f"Temporal transaction size {len(transaction)} is outside "
                f"{TEMPORAL_MIN_TX_SIZE}..{TEMPORAL_MAX_TX_SIZE} bytes",
            )
        body.extend(struct.pack(">H", len(transaction)))
        body.extend(transaction)
    return bytes(body)


def _temporal_endpoint_parts(endpoint: str) -> tuple[str, int]:
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    if not parsed.hostname:
        raise TradeError(400, f"invalid Temporal endpoint: {endpoint}")
    return parsed.hostname, parsed.port or 443


class _TemporalH3Protocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._http: Any = None
        self._responses: Dict[int, asyncio.Future] = {}
        self._statuses: Dict[int, int] = {}
        self._bodies: Dict[int, bytearray] = {}

    def quic_event_received(self, event: Any) -> None:
        if isinstance(event, ConnectionTerminated):
            error = TradeError(
                503,
                f"Temporal HTTP/3 connection closed: {event.reason_phrase or event.error_code}",
            )
            for future in self._responses.values():
                if not future.done():
                    future.set_exception(error)
            return
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic)
        if self._http is None:
            return
        for http_event in self._http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                headers = dict(http_event.headers)
                self._statuses[http_event.stream_id] = int(headers.get(b":status", b"500"))
                if http_event.stream_ended:
                    self._finish(http_event.stream_id)
            elif isinstance(http_event, DataReceived):
                self._bodies.setdefault(http_event.stream_id, bytearray()).extend(http_event.data)
                if http_event.stream_ended:
                    self._finish(http_event.stream_id)

    def _finish(self, stream_id: int) -> None:
        future = self._responses.get(stream_id)
        if future is not None and not future.done():
            future.set_result(
                (self._statuses.get(stream_id, 500), bytes(self._bodies.get(stream_id, b"")))
            )

    async def send_batch(self, authority: str, path: str, body: bytes) -> None:
        if self._http is None:
            raise TradeError(503, "Temporal HTTP/3 connection is not ready")
        stream_id = self._quic.get_next_available_stream_id()
        future = asyncio.get_running_loop().create_future()
        self._responses[stream_id] = future
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", authority.encode()),
                (b":path", path.encode()),
                (b"content-type", b"application/octet-stream"),
                (b"content-length", str(len(body)).encode()),
            ],
        )
        self._http.send_data(stream_id=stream_id, data=body, end_stream=True)
        self.transmit()
        try:
            status, response_body = await asyncio.wait_for(future, timeout=3.0)
        finally:
            self._responses.pop(stream_id, None)
            self._statuses.pop(stream_id, None)
            self._bodies.pop(stream_id, None)
        if not 200 <= status < 300:
            message = response_body.decode(errors="replace").strip() or str(status)
            raise TradeError(status, f"Temporal HTTP/3 error: {message}")


class TemporalClient(SwqosClient, HTTPClientMixin):
    """
    Temporal (Nozomi) SWQOS client implementation.

    URL:    {endpoint}/?c={token}   (auth in URL param, not header)
    Body:   official compact binary Batch Send framing
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(TEMPORAL_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        params = urlencode({"c": self.auth_token}) if self.auth_token else ""
        return f"{self.endpoint}/api/sendBatch{f'?{params}' if params else ''}"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "application/octet-stream"}

        async with session.post(
            url, data=_encode_temporal_batch([transaction]), headers=headers
        ) as resp:
            text = await resp.text()

        _raise_for_http_status(resp, text)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures: List[str] = []
        session = await self.get_session()
        for start in range(0, len(transactions), TEMPORAL_MAX_BATCH_SIZE):
            batch = transactions[start : start + TEMPORAL_MAX_BATCH_SIZE]
            async with session.post(
                self._build_url(),
                data=_encode_temporal_batch(batch),
                headers={"Content-Type": "application/octet-stream"},
            ) as resp:
                text = await resp.text()
            _raise_for_http_status(resp, text)
            signatures.extend(_signature_from_serialized_transaction(tx) for tx in batch)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.TEMPORAL

    def min_tip_sol(self) -> float:
        return MIN_TIP_TEMPORAL


class TemporalQuicClient(SwqosClient):
    """Persistent Temporal HTTP/3 client using the official Batch Send format."""

    def __init__(self, rpc_url: str, endpoint: str, auth_token: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.auth_token = auth_token or ""
        self._tip_account = _random_tip_account(TEMPORAL_TIP_ACCOUNTS)
        self._connection: Any = None
        self._protocol: Optional[_TemporalH3Protocol] = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> _TemporalH3Protocol:
        if not _QUIC_AVAILABLE:
            raise TradeError(501, "Temporal QUIC requires sol-trade-sdk[quic]")
        if self._protocol is not None:
            return self._protocol
        host, port = _temporal_endpoint_parts(self.endpoint)
        config = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
        config.verify_mode = ssl.CERT_REQUIRED
        config.server_name = host
        self._connection = quic_connect(
            host,
            port,
            configuration=config,
            create_protocol=_TemporalH3Protocol,
        )
        self._protocol = await self._connection.__aenter__()
        return self._protocol

    async def _invalidate(self) -> None:
        connection = self._connection
        self._connection = None
        self._protocol = None
        if connection is not None:
            try:
                await connection.__aexit__(None, None, None)
            except Exception:
                pass

    async def _send_batch(self, transactions: List[bytes]) -> List[str]:
        body = _encode_temporal_batch(transactions)
        host, port = _temporal_endpoint_parts(self.endpoint)
        authority = host if port == 443 else f"{host}:{port}"
        path = f"/api/sendBatch?{urlencode({'c': self.auth_token})}"
        async with self._lock:
            try:
                protocol = await self._connect()
                await protocol.send_batch(authority, path, body)
            except Exception as error:
                if not _should_fallback_transport(error):
                    raise
                await self._invalidate()
                protocol = await self._connect()
                await protocol.send_batch(authority, path, body)
        return [_signature_from_serialized_transaction(tx) for tx in transactions]

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        return (await self._send_batch([transaction]))[0]

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures: List[str] = []
        for start in range(0, len(transactions), TEMPORAL_MAX_BATCH_SIZE):
            signatures.extend(
                await self._send_batch(transactions[start : start + TEMPORAL_MAX_BATCH_SIZE])
            )
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.TEMPORAL

    def min_tip_sol(self) -> float:
        return MIN_TIP_TEMPORAL


# ===== FlashBlock Client =====


class FlashBlockClient(SwqosClient, HTTPClientMixin):
    """
    FlashBlock SWQOS client implementation.

    URL:    {endpoint}/api/v2/submit-batch
    Auth:   Header  Authorization: {token}  (plain token, no Bearer prefix)
    Body:   {"transactions": ["<base64>"]}
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(FLASH_BLOCK_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {"transactions": [encoded]}

        session = await self.get_session()
        url = f"{self.endpoint}/api/v2/submit-batch"

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if isinstance(data, dict) and "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        # Response may be a list of results or a dict
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict):
                if "error" in item:
                    raise TradeError(code=500, message=str(item["error"]))
                return _extract_signature(item)
        if isinstance(data, dict):
            return _extract_signature(data)
        return _extract_signature(str(data))

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        if not transactions:
            return []

        encoded_txs = [base64.b64encode(tx).decode() for tx in transactions]
        payload = {"transactions": encoded_txs}

        session = await self.get_session()
        url = f"{self.endpoint}/api/v2/submit-batch"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if isinstance(data, list):
            results = []
            for item in data:
                if isinstance(item, dict):
                    if "error" in item:
                        raise TradeError(code=500, message=str(item["error"]))
                    results.append(_extract_signature(item))
                else:
                    results.append(_extract_signature(str(item)))
            return results

        if isinstance(data, dict) and "error" in data:
            raise TradeError(code=500, message=str(data["error"]))

        return [str(data)]

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.FLASH_BLOCK

    def min_tip_sol(self) -> float:
        return MIN_TIP_FLASH_BLOCK


# ===== Helius Client =====


class HeliusClient(SwqosClient, HTTPClientMixin):
    """
    Helius SWQOS client implementation.

    URL:    {endpoint}?api-key={api_key}
    Auth:   URL query param api-key= (no Authorization header)
    Body:   JSON-RPC sendTransaction with id="1" (string), skipPreflight=true, maxRetries=0
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: Optional[str] = None,
        swqos_only: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.swqos_only = swqos_only
        self._tip_account = _random_tip_account(HELIUS_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        params = {}
        if self.api_key:
            params["api-key"] = self.api_key
        if self.swqos_only:
            params["swqos_only"] = "true"
        if not params:
            return self.endpoint
        separator = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{separator}{urlencode(params)}"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "sendTransaction",
            "params": [
                encoded,
                {
                    "encoding": "base64",
                    "skipPreflight": True,
                    "maxRetries": 0,
                },
            ],
        }

        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "application/json"}

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.HELIUS

    def min_tip_sol(self) -> float:
        if self.swqos_only:
            return MIN_TIP_HELIUS
        return MIN_TIP_HELIUS_NORMAL


# ===== Default RPC Client =====


class DefaultClient(SwqosClient, HTTPClientMixin):
    """Default RPC client implementation"""

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        session = await self.get_session()
        headers = {"Content-Type": "application/json"}

        async with session.post(self.rpc_url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        signature = _extract_signature(data)
        if wait_confirmation:
            # Explicit observation after acknowledgement; submission-only has no reads.
            from ..trading.executor import poll_for_confirmation_error
            ok, error = await poll_for_confirmation_error(self.rpc_url, signature)
            if not ok:
                failure = TradeError(code=500, message=error or "Transaction failed to confirm")
                failure.signature = signature
                raise failure
        return signature

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return ""

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.DEFAULT

    def min_tip_sol(self) -> float:
        return MIN_TIP_DEFAULT


# ===== Node1 Client =====


class Node1Client(SwqosClient, HTTPClientMixin):
    """
    Node1 SWQOS client implementation.

    URL:    {endpoint}  (endpoint itself, e.g. http://ny.node1.me)
    Auth:   Header  api-key: {token}
    Body:   JSON-RPC sendTransaction with skipPreflight=true
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(NODE1_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64", "skipPreflight": True},
            ],
        }

        session = await self.get_session()
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["api-key"] = self.auth_token

        async with session.post(self.endpoint, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.NODE1

    def min_tip_sol(self) -> float:
        return MIN_TIP_NODE1


# ===== BlockRazor Client =====


def _blockrazor_message_types() -> tuple[Any, Any]:
    if not _GRPC_AVAILABLE:
        raise TradeError(501, "BlockRazor gRPC requires grpcio and protobuf")

    file_descriptor = descriptor_pb2.FileDescriptorProto()
    file_descriptor.name = "blockrazor/server.proto"
    file_descriptor.package = "serverpb"
    file_descriptor.syntax = "proto3"

    request = file_descriptor.message_type.add()
    request.name = "SendBinaryRequest"
    for name, number, field_type in (
        ("binaryTransaction", 1, descriptor_pb2.FieldDescriptorProto.TYPE_BYTES),
        ("mode", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
        ("safeWindow", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT32),
        ("revertProtection", 4, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
    ):
        field = request.field.add()
        field.name = name
        field.number = number
        field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        field.type = field_type

    response = file_descriptor.message_type.add()
    response.name = "SendResponse"
    signature = response.field.add()
    signature.name = "signature"
    signature.number = 1
    signature.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    signature.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_descriptor)
    request_type = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("serverpb.SendBinaryRequest")
    )
    response_type = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("serverpb.SendResponse")
    )
    return request_type, response_type


class BlockRazorClient(SwqosClient, HTTPClientMixin):
    """
    BlockRazor SWQOS client implementation.

    URL:    {endpoint}/sendTransaction
    Auth:   apikey request header
    Body:   official JSON request with a base64 transaction
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
        mev_protection: bool = False,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self.mev_protection = mev_protection
        self._tip_account = _random_tip_account(BLOCK_RAZOR_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        session = await self.get_session()
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["apikey"] = self.auth_token
        payload = {
            "transaction": base64.b64encode(transaction).decode(),
            "mode": "sandwichMitigation" if self.mev_protection else "fast",
            "safeWindow": 3,
            "revertProtection": False,
        }

        async with session.post(self.endpoint, json=payload, headers=headers) as resp:
            text = await resp.text()

        _raise_for_http_status(resp, text)

        if text.strip():
            try:
                data = json.loads(text)
                if isinstance(data, dict) and "error" in data:
                    error = data["error"]
                    code = error.get("code", 500) if isinstance(error, dict) else 500
                    message = (
                        error.get("message", str(error)) if isinstance(error, dict) else str(error)
                    )
                    raise TradeError(code=code, message=message)
                return _extract_signature(data)
            except json.JSONDecodeError:
                return _extract_signature(text.strip())

        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.BLOCK_RAZOR

    def min_tip_sol(self) -> float:
        return MIN_TIP_BLOCK_RAZOR


class BlockRazorGrpcClient(SwqosClient):
    """BlockRazor's preferred gRPC SendBinaryTransaction transport."""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
        mev_protection: bool = False,
    ):
        if not _GRPC_AVAILABLE:
            raise TradeError(501, "BlockRazor gRPC requires grpcio and protobuf")
        request_type, response_type = _blockrazor_message_types()
        target = endpoint.removeprefix("http://").removeprefix("https://")
        self.rpc_url = rpc_url
        self.endpoint = target
        self.auth_token = auth_token or ""
        self.mev_protection = mev_protection
        self._tip_account = _random_tip_account(BLOCK_RAZOR_TIP_ACCOUNTS)
        self._request_type = request_type
        self._response_type = response_type
        self._channel: Any = None
        self._send: Any = None

    def _ensure_send(self) -> Any:
        """Create grpc.aio objects only while an event loop is running."""
        if self._send is not None:
            return self._send
        self._channel = grpc.aio.insecure_channel(self.endpoint)
        self._send = self._channel.unary_unary(
            "/serverpb.Server/SendBinaryTransaction",
            request_serializer=lambda value: value.SerializeToString(),
            response_deserializer=self._response_type.FromString,
        )
        return self._send

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        request = self._request_type(
            binaryTransaction=transaction,
            mode="sandwichMitigation" if self.mev_protection else "fast",
            safeWindow=3,
            revertProtection=False,
        )
        metadata = (("apikey", self.auth_token),) if self.auth_token else ()
        response = await self._ensure_send()(request, metadata=metadata, timeout=3.0)
        if not response.signature:
            raise TradeError(502, "BlockRazor gRPC returned an empty signature")
        return str(response.signature)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        return [
            await self.send_transaction(trade_type, transaction, wait_confirmation)
            for transaction in transactions
        ]

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._send = None

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.BLOCK_RAZOR

    def min_tip_sol(self) -> float:
        return MIN_TIP_BLOCK_RAZOR


# ===== Astralane Client =====


class AstralaneClient(SwqosClient, HTTPClientMixin):
    """
    Astralane SWQOS client implementation.

    URL:    {endpoint}?api-key={token}&method=sendTransaction
    Body:   raw serialized transaction bytes (application/octet-stream)
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(ASTRALANE_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        params = {}
        if self.auth_token:
            params["api-key"] = self.auth_token
        params["method"] = "sendTransaction"
        separator = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{separator}{urlencode(params)}"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "application/octet-stream"}

        async with session.post(url, data=transaction, headers=headers) as resp:
            text = await resp.text()

        if resp.status < 200 or resp.status >= 300:
            message = text.strip() or getattr(resp, "reason", "") or "HTTP error"
            raise TradeError(code=resp.status, message=f"HTTP error: {message}")

        if text:
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    if "error" in data:
                        raise TradeError(
                            code=(
                                data["error"].get("code", 500)
                                if isinstance(data["error"], dict)
                                else 500
                            ),
                            message=(
                                data["error"].get("message", str(data["error"]))
                                if isinstance(data["error"], dict)
                                else str(data["error"])
                            ),
                        )
                    if isinstance(data.get("result"), str):
                        return str(data["result"])
                    if isinstance(data.get("signature"), str):
                        return str(data["signature"])
            except json.JSONDecodeError:
                return str(text.strip())

        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.ASTRALANE

    def min_tip_sol(self) -> float:
        return MIN_TIP_ASTRALANE


# ===== Stellium Client =====


class StelliumClient(SwqosClient, HTTPClientMixin):
    """
    Stellium SWQOS client implementation.

    URL:    {endpoint}/{token}  (token appended to path)
    Body:   standard JSON-RPC sendTransaction (base64 encoding)
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(STELLIUM_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        if self.auth_token:
            return f"{self.endpoint}/{self.auth_token}"
        return self.endpoint

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64"},
            ],
        }

        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "application/json"}

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.STELLIUM

    def min_tip_sol(self) -> float:
        return MIN_TIP_STELLIUM


# ===== Lightspeed Client =====


class LightspeedClient(SwqosClient, HTTPClientMixin):
    """
    Lightspeed (SolanaVibeStation) SWQOS client implementation.

    URL:    Must be provided via custom_url
            Format: https://<tier>.rpc.solanavibestation.com/lightspeed?api_key=<key>
    Body:   JSON-RPC sendTransaction with extra params (skipPreflight, preflightCommitment, maxRetries)
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(LIGHTSPEED_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {
                    "encoding": "base64",
                    "skipPreflight": True,
                    "preflightCommitment": "processed",
                    "maxRetries": 0,
                },
            ],
        }

        session = await self.get_session()
        headers = {"Content-Type": "application/json"}

        async with session.post(self.endpoint, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        return _extract_signature(data)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.LIGHTSPEED

    def min_tip_sol(self) -> float:
        return MIN_TIP_LIGHTSPEED


# ===== NextBlock Client =====


class NextBlockClient(SwqosClient, HTTPClientMixin):
    """
    NextBlock SWQOS client implementation.

    URL:    {endpoint}/api/v2/submit
    Auth:   Header  Authorization: {token}
    Body:   {"transaction": {"content": "<base64>"}, "frontRunningProtection": false}
    """

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.auth_token = auth_token
        self._tip_account = _random_tip_account(NEXT_BLOCK_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        payload = {
            "transaction": {"content": encoded},
            "frontRunningProtection": False,
        }

        session = await self.get_session()
        url = f"{self.endpoint}/api/v2/submit"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token or "",
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        _raise_for_http_status(resp, data)
        if isinstance(data, dict) and "reason" in data and data.get("reason"):
            raise TradeError(code=500, message=data["reason"])
        if isinstance(data, dict) and "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=(
                    data["error"].get("message", str(data["error"]))
                    if isinstance(data["error"], dict)
                    else str(data["error"])
                ),
            )

        if isinstance(data, dict):
            return _extract_signature(data)
        return _extract_signature(str(data))

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures = []
        for tx in transactions:
            sig = await self.send_transaction(trade_type, tx, wait_confirmation)
            signatures.append(sig)
        return signatures

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.NEXT_BLOCK

    def min_tip_sol(self) -> float:
        return MIN_TIP_NEXT_BLOCK


# ===== QUIC helper =====


def _make_solana_tpu_quic_config(
    server_name: str,
    api_key: Optional[str] = None,
) -> "QuicConfiguration":
    """
    Build a QuicConfiguration with a self-signed Ed25519 cert and ALPN "solana-tpu",
    matching the pattern used by solana-tls-utils / go-solana-tpu.
    """
    from aioquic.quic.configuration import QuicConfiguration

    if api_key:
        try:
            keypair_bytes = base58.b58decode(api_key.strip())
        except Exception as exc:
            raise TradeError(
                code=400,
                message=f"Solami api_token base58 decode failed: {exc}",
            ) from exc
        if len(keypair_bytes) != 64:
            raise TradeError(
                code=400,
                message=(
                    "Solami api_token must be a base58-encoded 64-byte Solana keypair, "
                    f"got {len(keypair_bytes)} bytes"
                ),
            )
        keypair = Keypair.from_bytes(keypair_bytes)
        private_key = Ed25519PrivateKey.from_private_bytes(bytes(keypair.secret()))
    else:
        private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Self-signed cert: NotBefore 1975, NotAfter 4096 (same as Rust solana-tls-utils)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Solana node")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(1975, 1, 1))
        .not_valid_after(datetime.datetime(4096, 1, 1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address("0.0.0.0"))]),
            critical=False,
        )
        .sign(private_key, None)  # Ed25519 doesn't use a hash algorithm
    )

    cfg = QuicConfiguration(
        alpn_protocols=["solana-tpu"],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
        server_name=server_name,
    )
    cfg.certificate = cert
    cfg.private_key = private_key
    return cfg


def _host_port_from_http(endpoint: str, port: int) -> tuple[str, int]:
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if not host:
        host = endpoint.removeprefix("http://").removeprefix("https://").split("/", 1)[0]
        if ":" in host:
            host = host.rsplit(":", 1)[0]
    return host, port


def _make_node1_quic_config(server_name: str) -> "QuicConfiguration":
    from aioquic.quic.configuration import QuicConfiguration

    return QuicConfiguration(
        alpn_protocols=["h3"],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
        server_name=server_name,
    )


def _make_astralane_quic_config(api_key: str) -> "QuicConfiguration":
    from aioquic.quic.configuration import QuicConfiguration

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, api_key)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        )
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
        .sign(private_key, hashes.SHA256())
    )
    cfg = QuicConfiguration(
        alpn_protocols=["astralane-tpu"],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
        server_name="astralane",
    )
    cfg.certificate = cert
    cfg.private_key = private_key
    return cfg


class _SolanaTPUProtocol(QuicConnectionProtocol):
    """Minimal QUIC protocol: opens a unidirectional stream, writes bytes, closes."""

    def __init__(self, *args: Any, tx_bytes: bytes, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tx_bytes = tx_bytes
        self._done = asyncio.Event()

    def quic_event_received(self, event: Any) -> None:
        pass  # we only send, no responses expected

    async def send_tx(self) -> None:
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=True)
        self._quic.send_stream_data(stream_id, self._tx_bytes, end_stream=True)
        self.transmit()
        # Give the stack a moment to flush before closing
        await asyncio.sleep(0.05)


async def _send_via_quic(
    host: str,
    port: int,
    server_name: str,
    tx_bytes: bytes,
    api_key: Optional[str] = None,
) -> None:
    """Connect via QUIC ALPN=solana-tpu and send raw transaction bytes."""
    if not _QUIC_AVAILABLE:
        raise TradeError(
            code=501,
            message="QUIC not available: install 'aioquic' and 'cryptography' packages.",
        )
    cfg = _make_solana_tpu_quic_config(server_name, api_key)

    async with quic_connect(
        host,
        port,
        configuration=cfg,
        create_protocol=lambda *a, **kw: _SolanaTPUProtocol(*a, tx_bytes=tx_bytes, **kw),
    ) as protocol:
        assert isinstance(protocol, _SolanaTPUProtocol)
        await protocol.send_tx()


class _Node1QuicProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._buffers: Dict[int, bytearray] = {}
        self._done: Dict[int, asyncio.Future] = {}

    def quic_event_received(self, event: Any) -> None:
        from aioquic.quic.events import StreamDataReceived

        if isinstance(event, StreamDataReceived):
            self._buffers.setdefault(event.stream_id, bytearray()).extend(event.data)
            if event.end_stream and event.stream_id in self._done:
                future = self._done[event.stream_id]
                if not future.done():
                    future.set_result(bytes(self._buffers.get(event.stream_id, b"")))

    async def send_and_read(self, payload: bytes) -> bytes:
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
        loop = asyncio.get_running_loop()
        self._done[stream_id] = loop.create_future()
        self._quic.send_stream_data(stream_id, payload, end_stream=True)
        self.transmit()
        return await asyncio.wait_for(self._done[stream_id], timeout=5.0)


async def _node1_quic_submit(endpoint: str, api_key: str, tx_bytes: bytes) -> None:
    if not _QUIC_AVAILABLE:
        raise TradeError(501, "QUIC not available: install sol-trade-sdk[quic].")
    if len(tx_bytes) > 1232:
        raise TradeError(400, f"Node1 QUIC transaction too large: {len(tx_bytes)} > 1232")
    api_key_bytes = uuid.UUID(api_key).bytes
    host, port = _host_port_from_http(endpoint, 16666)
    cfg = _make_node1_quic_config(host)
    async with quic_connect(
        host, port, configuration=cfg, create_protocol=_Node1QuicProtocol
    ) as protocol:
        assert isinstance(protocol, _Node1QuicProtocol)
        auth_reply = await protocol.send_and_read(api_key_bytes)
        if auth_reply != b"\x00":
            code = auth_reply[0] if auth_reply else -1
            raise TradeError(401, f"Node1 QUIC auth rejected: {code}")
        response = await protocol.send_and_read(tx_bytes)
        if len(response) < 6:
            raise TradeError(500, "Node1 QUIC response too short")
        status = int.from_bytes(response[:2], "big")
        msg_len = int.from_bytes(response[2:6], "big")
        msg = response[6 : 6 + msg_len].decode("utf-8", errors="replace")
        if status != 200:
            raise TradeError(status, f"Node1 QUIC submit failed: {msg}")


class _AstralanePersistentProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.termination_error: Optional[TradeError] = None
        self._ping_id = 0

    def quic_event_received(self, event: Any) -> None:
        if isinstance(event, ConnectionTerminated):
            if event.error_code == 1:
                self.termination_error = TradeError(401, "Astralane QUIC rejected the API key")
            elif event.error_code == 2:
                self.termination_error = TradeError(429, "Astralane QUIC connection limit exceeded")
            else:
                reason = event.reason_phrase or f"application error {event.error_code}"
                self.termination_error = TradeError(503, f"Astralane QUIC closed: {reason}")

    async def send_transaction(self, transaction: bytes) -> None:
        if self.termination_error is not None:
            raise self.termination_error
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=True)
        self._quic.send_stream_data(stream_id, transaction, end_stream=True)
        self.transmit()
        await asyncio.sleep(0)
        if self.termination_error is not None:
            raise self.termination_error

    def keep_alive(self) -> None:
        if self.termination_error is not None:
            return
        self._ping_id += 1
        self._quic.send_ping(self._ping_id)
        self.transmit()


class Node1QuicClient(SwqosClient):
    """Node1 QUIC client using UUID auth and bidirectional streams."""

    def __init__(self, rpc_url: str, endpoint: str, api_key: str):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.api_key = api_key

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        await _node1_quic_submit(self.endpoint, self.api_key, transaction)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures: List[str] = []
        for transaction in transactions:
            signatures.append(
                await self.send_transaction(trade_type, transaction, wait_confirmation)
            )
        return signatures

    def get_tip_account(self) -> str:
        return random.choice(NODE1_TIP_ACCOUNTS)

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.NODE1

    def min_tip_sol(self) -> float:
        return MIN_TIP_NODE1


class AstralaneQuicClient(SwqosClient):
    """Persistent Astralane QUIC TPU client with keepalive and reconnect."""

    def __init__(self, rpc_url: str, endpoint: str, api_key: str):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.api_key = api_key
        if endpoint.startswith(("http://", "https://")):
            self._host, self._port = _host_port_from_http(endpoint, 7000)
        else:
            host_port = endpoint.rsplit(":", 1)
            self._host = host_port[0]
            self._port = (
                int(host_port[1]) if len(host_port) == 2 and host_port[1].isdigit() else 7000
            )
        self._connection: Any = None
        self._protocol: Optional[_AstralanePersistentProtocol] = None
        self._lock = asyncio.Lock()
        self._keepalive_task: Optional[asyncio.Task] = None

    async def _connect(self) -> _AstralanePersistentProtocol:
        if not _QUIC_AVAILABLE:
            raise TradeError(501, "QUIC not available: install sol-trade-sdk[quic].")
        if not self.api_key:
            raise TradeError(401, "Astralane QUIC requires an API key")
        if self._protocol is not None and self._protocol.termination_error is None:
            return self._protocol
        await self._invalidate()
        self._connection = quic_connect(
            self._host,
            self._port,
            configuration=_make_astralane_quic_config(self.api_key),
            create_protocol=_AstralanePersistentProtocol,
        )
        self._protocol = await self._connection.__aenter__()
        if self._keepalive_task is None or self._keepalive_task.done():
            self._keepalive_task = asyncio.create_task(self._keepalive())
        return self._protocol

    async def _invalidate(self) -> None:
        connection = self._connection
        self._connection = None
        self._protocol = None
        if connection is not None:
            with contextlib.suppress(Exception):
                await connection.__aexit__(None, None, None)

    async def _keepalive(self) -> None:
        while True:
            await asyncio.sleep(25)
            protocol = self._protocol
            if protocol is not None:
                protocol.keep_alive()

    async def close(self) -> None:
        task = self._keepalive_task
        self._keepalive_task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._invalidate()

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        if len(transaction) > 1232:
            raise TradeError(
                400, f"Astralane QUIC transaction too large: {len(transaction)} > 1232"
            )
        async with self._lock:
            try:
                protocol = await self._connect()
                await protocol.send_transaction(transaction)
            except Exception as error:
                if not _should_fallback_transport(error):
                    raise
                await self._invalidate()
                protocol = await self._connect()
                await protocol.send_transaction(transaction)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures: List[str] = []
        for transaction in transactions:
            signatures.append(
                await self.send_transaction(trade_type, transaction, wait_confirmation)
            )
        return signatures

    def get_tip_account(self) -> str:
        return random.choice(ASTRALANE_TIP_ACCOUNTS)

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.ASTRALANE

    def min_tip_sol(self) -> float:
        return MIN_TIP_ASTRALANE


# ===== Soyas Client =====


class SoyasClient(SwqosClient):
    """
    Soyas SWQOS client.

    Transport: QUIC with self-signed Ed25519 cert, ALPN "solana-tpu".
    Endpoint:  host:port (e.g. nyc.landing.soyas.xyz:9000)
    SNI:       "soyas-landing" (matches Rust SDK SOYAS_SERVER constant)
    Requires:  pip install aioquic cryptography
    """

    _SERVER_NAME = "soyas-landing"

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint  # host:port
        self.api_key = api_key
        self._tip_account = _random_tip_account(SOYAS_TIP_ACCOUNTS)
        # Parse host:port
        parts = endpoint.rsplit(":", 1)
        self._host = parts[0]
        self._port = int(parts[1]) if len(parts) == 2 else 9000

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        await _send_via_quic(self._host, self._port, self._SERVER_NAME, transaction)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        for tx in transactions:
            await self.send_transaction(trade_type, tx, wait_confirmation)
        return [_signature_from_serialized_transaction(tx) for tx in transactions]

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.SOYAS

    def min_tip_sol(self) -> float:
        return MIN_TIP_SOYAS


# ===== Speedlanding Client =====


class SpeedlandingClient(SwqosClient):
    """
    Speedlanding SWQOS client.

    Transport: QUIC with self-signed Ed25519 cert, ALPN "solana-tpu".
    Endpoint:  host:port (e.g. nyc.speedlanding.trade:17778)
    SNI:       fixed "speed-landing" to match Rust SDK.
    Requires:  pip install aioquic cryptography
    """

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint  # host:port
        self.api_key = api_key
        self._tip_account = _random_tip_account(SPEEDLANDING_TIP_ACCOUNTS)
        # Parse host:port
        parts = endpoint.rsplit(":", 1)
        self._host = parts[0]
        self._port = int(parts[1]) if len(parts) == 2 else 17778
        self._server_name = "speed-landing"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        await _send_via_quic(self._host, self._port, self._server_name, transaction)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        for tx in transactions:
            await self.send_transaction(trade_type, tx, wait_confirmation)
        return [_signature_from_serialized_transaction(tx) for tx in transactions]

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.SPEEDLANDING

    def min_tip_sol(self) -> float:
        return MIN_TIP_SPEEDLANDING


# ===== Solami Client =====


class SolamiClient(SwqosClient):
    """
    Solami SWQOS client.

    Transport: QUIC with self-signed Ed25519 cert, ALPN "solana-tpu".
    Endpoint:  host:port (Rust v5.0.2 defaults every region to beam.solami.dev:11000)
    SNI:       "solami-beam"
    Requires:  pip install aioquic cryptography
    """

    _SERVER_NAME = "solami-beam"

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.api_key = api_key
        self._tip_account = _random_tip_account(SOLAMI_TIP_ACCOUNTS)
        parts = endpoint.rsplit(":", 1)
        self._host = parts[0]
        self._port = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 11000

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        if not self.api_key:
            raise TradeError(
                code=400,
                message="Solami api_token is required and must be a base58-encoded Solana keypair",
            )
        await _send_via_quic(
            self._host,
            self._port,
            self._SERVER_NAME,
            transaction,
            self.api_key,
        )
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        for tx in transactions:
            await self.send_transaction(trade_type, tx, wait_confirmation)
        return [_signature_from_serialized_transaction(tx) for tx in transactions]

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.SOLAMI

    def min_tip_sol(self) -> float:
        return MIN_TIP_SOLAMI


class LunarLanderClient(SwqosClient, HTTPClientMixin):
    """LunarLander HTTP: POST /send-bin with x-api-key."""

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or ""
        self._tip_account = _random_tip_account(LUNARLANDER_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        url = f"{self.endpoint}/send-bin"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=transaction,
                headers={
                    "Content-Type": "application/octet-stream",
                    "x-api-key": self.api_key,
                },
            ) as resp:
                body = await resp.read()
                if resp.status >= 400:
                    raise TradeError(
                        code=resp.status,
                        message=f"LunarLander send failed: {resp.status} {body[:200]!r}",
                    )
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        out = []
        for tx in transactions:
            out.append(await self.send_transaction(trade_type, tx, wait_confirmation))
        return out

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.LUNAR_LANDER

    def min_tip_sol(self) -> float:
        return MIN_TIP_LUNARLANDER


class LunarLanderQuicClient(SwqosClient):
    """LunarLander QUIC best-effort (default in Rust when transport unset)."""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: str = "",
        mev_protection: bool = False,
    ):
        self.rpc_url = rpc_url
        parts = endpoint.rsplit(":", 1)
        self._host = parts[0]
        self._port = int(parts[1]) if len(parts) == 2 else 16888
        self.api_key = api_key
        self.mev_protection = mev_protection
        self._tip_account = _random_tip_account(LUNARLANDER_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        if len(transaction) > 1232:
            raise TradeError(
                400, f"LunarLander QUIC transaction too large: {len(transaction)} > 1232"
            )
        if not _QUIC_AVAILABLE:
            raise TradeError(501, "QUIC not available: install sol-trade-sdk[quic].")
        # Client cert CN = API key; ALPN lunar-lander-tpu.
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.api_key or "lunar")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(
                datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
            )
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
            )
            .sign(private_key, hashes.SHA256())
        )
        from aioquic.quic.configuration import QuicConfiguration

        cfg = QuicConfiguration(
            alpn_protocols=["lunar-lander-tpu"],
            is_client=True,
            verify_mode=ssl.CERT_NONE,
        )
        cfg.certificate = cert
        cfg.private_key = private_key

        class _Proto(QuicConnectionProtocol):
            def __init__(inner_self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                inner_self._tx = transaction
                inner_self._done = asyncio.Event()

            def quic_event_received(inner_self, event: Any) -> None:
                if isinstance(event, ProtocolNegotiated):
                    stream_id = inner_self._quic.get_next_available_stream_id(
                        is_unidirectional=True
                    )
                    inner_self._quic.send_stream_data(
                        stream_id, inner_self._tx, end_stream=True
                    )
                    inner_self._done.set()
                elif isinstance(event, ConnectionTerminated):
                    inner_self._done.set()

            async def wait_done(inner_self) -> None:
                await inner_self._done.wait()

        async with quic_connect(
            self._host, self._port, configuration=cfg, create_protocol=_Proto
        ) as protocol:
            await protocol.wait_done()
            await asyncio.sleep(0.05)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        out = []
        for tx in transactions:
            out.append(await self.send_transaction(trade_type, tx, wait_confirmation))
        return out

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.LUNAR_LANDER

    def min_tip_sol(self) -> float:
        return MIN_TIP_LUNARLANDER


def _validate_glaive_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    try:
        parsed = uuid.UUID(key)
    except Exception as exc:
        raise ValueError("Glaive API key must be a valid UUID v4") from exc
    if parsed.version != 4:
        raise ValueError("Glaive API key must be a UUID v4")
    return key


def _build_glaive_auth_frame(api_key: str, mev_protection: bool) -> bytes:
    parsed = uuid.UUID(_validate_glaive_api_key(api_key))
    frame = bytearray(17)
    frame[:16] = parsed.bytes
    if mev_protection:
        frame[16] = 1 << 0
    return bytes(frame)


def _build_glaive_binary_url(endpoint: str, api_key: str, mev_protection: bool) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Glaive HTTP endpoint must use http or https")
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/binary"):
        path = "/binary" if path in ("", "/") else f"{path}/binary"
    query = {"api-key": api_key}
    if mev_protection:
        query["mev-protect"] = "true"
    return f"{parsed.scheme}://{parsed.netloc}{path}?{urlencode(query)}"


class GlaiveClient(SwqosClient, HTTPClientMixin):
    """Glaive HTTP binary submit."""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: str,
        mev_protection: bool = False,
    ):
        key = _validate_glaive_api_key(api_key)
        self.rpc_url = rpc_url
        self.submit_url = _build_glaive_binary_url(endpoint, key, mev_protection)
        self._tip_account = _random_tip_account(GLAIVE_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        expected = _signature_from_serialized_transaction(transaction)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.submit_url,
                data=transaction,
                headers={"Content-Type": "application/octet-stream"},
            ) as resp:
                body = await resp.read()
                try:
                    parsed = json.loads(body)
                except Exception as exc:
                    raise TradeError(
                        code=500, message=f"Glaive returned invalid JSON: {body[:200]!r}"
                    ) from exc
                if isinstance(parsed, dict) and parsed.get("error"):
                    err = parsed["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    raise TradeError(code=500, message=f"Glaive rejected transaction: {msg}")
                if resp.status >= 400:
                    raise TradeError(code=resp.status, message=f"Glaive HTTP {resp.status}")
                result = parsed.get("result") if isinstance(parsed, dict) else None
                if result != expected:
                    raise TradeError(
                        code=500,
                        message="Glaive returned a signature that does not match the submitted transaction",
                    )
        return expected

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        out = []
        for tx in transactions:
            out.append(await self.send_transaction(trade_type, tx, wait_confirmation))
        return out

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.GLAIVE

    def min_tip_sol(self) -> float:
        return MIN_TIP_GLAIVE


class GlaiveQuicClient(SwqosClient):
    """Glaive QUIC (SNI glaive-intake, default when transport unset)."""

    def __init__(
        self,
        rpc_url: str,
        endpoint: str,
        api_key: str,
        mev_protection: bool = False,
    ):
        key = _validate_glaive_api_key(api_key)
        self.rpc_url = rpc_url
        parts = endpoint.rsplit(":", 1)
        self._host = parts[0]
        self._port = int(parts[1]) if len(parts) == 2 else 4000
        self._auth_frame = _build_glaive_auth_frame(key, mev_protection)
        self._tip_account = _random_tip_account(GLAIVE_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        if len(transaction) > 1232:
            raise TradeError(
                code=400,
                message=f"Glaive QUIC transaction too large: {len(transaction)} > 1232",
            )
        if not _QUIC_AVAILABLE:
            raise TradeError(501, "QUIC not available: install sol-trade-sdk[quic].")
        cfg = _make_solana_tpu_quic_config("glaive-intake")
        cfg.server_name = "glaive-intake"

        class _Proto(QuicConnectionProtocol):
            def __init__(inner_self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                inner_self._auth = self._auth_frame
                inner_self._tx = transaction
                inner_self._done = asyncio.Event()

            def quic_event_received(inner_self, event: Any) -> None:
                if isinstance(event, ProtocolNegotiated):
                    auth_id = inner_self._quic.get_next_available_stream_id(
                        is_unidirectional=True
                    )
                    inner_self._quic.send_stream_data(
                        auth_id, inner_self._auth, end_stream=True
                    )
                    tx_id = inner_self._quic.get_next_available_stream_id(
                        is_unidirectional=True
                    )
                    inner_self._quic.send_stream_data(
                        tx_id, inner_self._tx, end_stream=True
                    )
                    inner_self._done.set()
                elif isinstance(event, ConnectionTerminated):
                    inner_self._done.set()

            async def wait_done(inner_self) -> None:
                await inner_self._done.wait()

        async with quic_connect(
            self._host, self._port, configuration=cfg, create_protocol=_Proto
        ) as protocol:
            await protocol.wait_done()
            await asyncio.sleep(0.05)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        out = []
        for tx in transactions:
            out.append(await self.send_transaction(trade_type, tx, wait_confirmation))
        return out

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.GLAIVE

    def min_tip_sol(self) -> float:
        return MIN_TIP_GLAIVE


# ===== Client Factory =====


@dataclass
class SwqosConfig:
    """Configuration for SWQOS client"""

    type: SwqosType
    region: SwqosRegion = SwqosRegion.DEFAULT
    custom_url: Optional[str] = None
    api_key: Optional[str] = None
    mev_protection: bool = False
    transport: Optional[Any] = None
    astralane_transport: Optional[Any] = None
    swqos_only: Optional[bool] = None


class ClientFactory:
    """Factory for creating SWQOS clients"""

    @staticmethod
    def _normalize_region(region: Any) -> SwqosRegion:
        if isinstance(region, SwqosRegion):
            return region
        value = getattr(region, "value", region)
        try:
            return SwqosRegion(value)
        except ValueError:
            return SwqosRegion.DEFAULT

    @staticmethod
    def create_client(config: SwqosConfig, rpc_url: str) -> SwqosClient:
        """Create a SWQOS client from configuration"""
        if is_swqos_type_blacklisted(config.type):
            raise ValueError(f"SWQOS type is blacklisted by Rust v5.0.2 parity: {config.type}")
        region = ClientFactory._normalize_region(config.region)
        swqos_type = getattr(config.type, "value", config.type)

        if swqos_type == SwqosType.JITO.value:
            endpoint = config.custom_url or JITO_ENDPOINTS.get(
                region, JITO_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return JitoClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.BLOXROUTE.value:
            endpoint = config.custom_url or BLOXROUTE_ENDPOINTS.get(
                region, BLOXROUTE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return BloxrouteClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.ZERO_SLOT.value:
            endpoint = config.custom_url or ZERO_SLOT_ENDPOINTS.get(
                region, ZERO_SLOT_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return ZeroSlotClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.TEMPORAL.value:
            endpoint = config.custom_url or TEMPORAL_ENDPOINTS.get(
                region, TEMPORAL_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            transport = getattr(
                getattr(config, "transport", None), "value", getattr(config, "transport", None)
            )
            if config.custom_url and transport is None:
                return TemporalClient(rpc_url, endpoint, config.api_key)
            if transport == "Http":
                return TemporalClient(rpc_url, endpoint, config.api_key)
            if transport == "Grpc":
                raise TradeError(400, "Temporal does not provide a gRPC transaction-submission API")
            quic_client = TemporalQuicClient(rpc_url, endpoint, config.api_key)
            if transport == "Quic":
                return quic_client
            if transport is not None:
                raise TradeError(400, f"Unsupported Temporal transport: {transport}")
            return FallbackSwqosClient(
                quic_client, TemporalClient(rpc_url, endpoint, config.api_key)
            )

        elif swqos_type == SwqosType.FLASH_BLOCK.value:
            endpoint = config.custom_url or FLASH_BLOCK_ENDPOINTS.get(
                region, FLASH_BLOCK_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return FlashBlockClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.HELIUS.value:
            endpoint = config.custom_url or HELIUS_ENDPOINTS.get(
                region, HELIUS_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return HeliusClient(
                rpc_url, endpoint, config.api_key, swqos_only=bool(config.swqos_only)
            )

        elif swqos_type == SwqosType.NODE1.value:
            transport = getattr(
                getattr(config, "transport", None), "value", getattr(config, "transport", None)
            )
            endpoint = config.custom_url or NODE1_ENDPOINTS.get(
                region, NODE1_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            if transport == "Quic":
                return Node1QuicClient(
                    rpc_url,
                    f"{_host_port_from_http(endpoint, 16666)[0]}:16666",
                    config.api_key or "",
                )
            return Node1Client(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.BLOCK_RAZOR.value:
            http_endpoint = config.custom_url or BLOCK_RAZOR_ENDPOINTS.get(
                region, BLOCK_RAZOR_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            transport = getattr(
                getattr(config, "transport", None), "value", getattr(config, "transport", None)
            )
            if config.custom_url and transport is None:
                return BlockRazorClient(
                    rpc_url,
                    http_endpoint,
                    config.api_key,
                    mev_protection=config.mev_protection,
                )
            if transport == "Http":
                return BlockRazorClient(
                    rpc_url,
                    http_endpoint,
                    config.api_key,
                    mev_protection=config.mev_protection,
                )
            if transport == "Quic":
                raise TradeError(
                    400, "BlockRazor does not provide a QUIC transaction-submission API"
                )
            grpc_endpoint = config.custom_url or BLOCK_RAZOR_GRPC_ENDPOINTS.get(
                region, BLOCK_RAZOR_GRPC_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            grpc_client = BlockRazorGrpcClient(
                rpc_url,
                grpc_endpoint,
                config.api_key,
                mev_protection=config.mev_protection,
            )
            if transport == "Grpc":
                return grpc_client
            if transport is not None:
                raise TradeError(400, f"Unsupported BlockRazor transport: {transport}")
            return FallbackSwqosClient(
                grpc_client,
                BlockRazorClient(
                    rpc_url,
                    http_endpoint,
                    config.api_key,
                    mev_protection=config.mev_protection,
                ),
            )

        elif swqos_type == SwqosType.ASTRALANE.value:
            base_endpoint = config.custom_url or ASTRALANE_ENDPOINTS.get(
                region, ASTRALANE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            mode = getattr(
                getattr(config, "astralane_transport", None),
                "value",
                getattr(config, "astralane_transport", None),
            )
            if config.custom_url and mode is None:
                return AstralaneClient(rpc_url, base_endpoint, config.api_key)
            if mode == "Plain":
                return AstralaneClient(
                    rpc_url, base_endpoint.replace("/irisb", "/iris"), config.api_key
                )
            if mode == "Binary":
                return AstralaneClient(rpc_url, base_endpoint, config.api_key)
            if mode == "Quic":
                if config.custom_url:
                    if config.custom_url.startswith(("http://", "https://")):
                        host, port = _host_port_from_http(
                            config.custom_url, 9000 if config.mev_protection else 7000
                        )
                        quic_endpoint = f"{host}:{port}"
                    else:
                        quic_endpoint = config.custom_url
                else:
                    host = ASTRALANE_QUIC_HOSTS.get(
                        region, ASTRALANE_QUIC_HOSTS[SwqosRegion.DEFAULT]
                    )
                    quic_endpoint = f"{host}:{9000 if config.mev_protection else 7000}"
                return AstralaneQuicClient(rpc_url, quic_endpoint, config.api_key or "")
            if mode is not None:
                raise TradeError(400, f"Unsupported Astralane transport: {mode}")
            host = ASTRALANE_QUIC_HOSTS.get(region, ASTRALANE_QUIC_HOSTS[SwqosRegion.DEFAULT])
            quic_endpoint = f"{host}:{9000 if config.mev_protection else 7000}"
            return FallbackSwqosClient(
                AstralaneQuicClient(rpc_url, quic_endpoint, config.api_key or ""),
                AstralaneClient(rpc_url, base_endpoint, config.api_key),
            )

        elif swqos_type == SwqosType.STELLIUM.value:
            endpoint = config.custom_url or STELLIUM_ENDPOINTS.get(
                region, STELLIUM_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return StelliumClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.LIGHTSPEED.value:
            # Lightspeed requires custom_url with api_key embedded
            endpoint = config.custom_url or ""
            return LightspeedClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.NEXT_BLOCK.value:
            endpoint = config.custom_url or NEXT_BLOCK_ENDPOINTS.get(
                region, NEXT_BLOCK_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return NextBlockClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.SOYAS.value:
            endpoint = config.custom_url or SOYAS_ENDPOINTS.get(
                region, SOYAS_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return SoyasClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.SPEEDLANDING.value:
            endpoint = config.custom_url or SPEEDLANDING_ENDPOINTS.get(
                region, SPEEDLANDING_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return SpeedlandingClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.SOLAMI.value:
            endpoint = config.custom_url or SOLAMI_ENDPOINTS.get(
                region, SOLAMI_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return SolamiClient(rpc_url, endpoint, config.api_key)

        elif swqos_type in (SwqosType.LUNAR_LANDER.value, "LunarLander"):
            transport = getattr(config, "transport", None)
            transport_value = getattr(transport, "value", transport)
            if transport_value == "Grpc":
                raise ValueError("LunarLander does not support the gRPC transport")
            use_quic = transport is None or transport_value == "Quic"
            if use_quic:
                endpoint = config.custom_url or LUNARLANDER_QUIC_ENDPOINTS.get(
                    region, LUNARLANDER_QUIC_ENDPOINTS[SwqosRegion.DEFAULT]
                )
                if config.custom_url and str(config.custom_url).startswith("http"):
                    parsed = urlparse(config.custom_url)
                    endpoint = f"{parsed.hostname}:16888"
                return LunarLanderQuicClient(
                    rpc_url,
                    endpoint,
                    config.api_key or "",
                    bool(getattr(config, "mev_protection", False)),
                )
            endpoint = config.custom_url or LUNARLANDER_ENDPOINTS.get(
                region, LUNARLANDER_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return LunarLanderClient(rpc_url, endpoint, config.api_key)

        elif swqos_type in (SwqosType.GLAIVE.value, "Glaive"):
            transport = getattr(config, "transport", None)
            transport_value = getattr(transport, "value", transport) if transport else "Quic"
            if transport is None:
                transport_value = "Quic"
            if transport_value == "Grpc":
                raise ValueError("Glaive does not support the gRPC transport")
            if transport_value == "Quic":
                endpoint = config.custom_url or GLAIVE_QUIC_ENDPOINTS.get(
                    region, GLAIVE_QUIC_ENDPOINTS[SwqosRegion.DEFAULT]
                )
                if config.custom_url and str(config.custom_url).startswith("http"):
                    parsed = urlparse(config.custom_url)
                    endpoint = f"{parsed.hostname}:4000"
                return GlaiveQuicClient(
                    rpc_url, endpoint, config.api_key or "", bool(config.mev_protection)
                )
            endpoint = config.custom_url or GLAIVE_ENDPOINTS.get(
                region, GLAIVE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return GlaiveClient(
                rpc_url, endpoint, config.api_key or "", bool(config.mev_protection)
            )

        elif swqos_type == SwqosType.DEFAULT.value:
            return DefaultClient(rpc_url)

        else:
            raise ValueError(f"Unsupported SWQOS type: {config.type}")


# ===== Convenience function for creating clients =====


def create_swqos_client(
    swqos_type: SwqosType,
    rpc_url: str,
    auth_token: Optional[str] = None,
    region: SwqosRegion = SwqosRegion.DEFAULT,
    custom_url: Optional[str] = None,
    mev_protection: bool = False,
) -> SwqosClient:
    """Convenience function to create a SWQOS client"""
    config = SwqosConfig(
        type=swqos_type,
        region=region,
        custom_url=custom_url,
        api_key=auth_token,
        mev_protection=mev_protection,
    )
    return ClientFactory.create_client(config, rpc_url)


def create_cached_wire_submit(client):
    """Adapt a raw-byte SWQOS client to CachedTradeExecutor; never polls confirmation."""
    async def submit(wire, direction):
        if direction not in ("Buy", "Sell"):
            raise TradeError(code=400, message="Explicit Buy/Sell required")
        expected = _signature_from_serialized_transaction(wire)
        returned = await client.send_transaction(
            TradeType.BUY if direction == "Buy" else TradeType.SELL,
            bytes(wire),
            False,
        )
        if returned != expected:
            raise TradeError(code=400,message="Submission signature does not match raw transaction")
        return returned
    return submit
