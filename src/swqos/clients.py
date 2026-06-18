"""
SWQOS Clients for Sol Trade SDK
Implements various SWQOS (Solana Write Queue Operating System) providers.
"""

import asyncio
import base64
import json
import random
import ssl
import struct
import datetime
import ipaddress
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from urllib.parse import urlparse

import aiohttp
import base58
from solders.keypair import Keypair

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    import aioquic  # noqa: F401 - just check availability
    from aioquic.asyncio import connect as quic_connect
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.asyncio.protocol import QuicConnectionProtocol
    _QUIC_AVAILABLE = True
except ImportError:
    _QUIC_AVAILABLE = False
    QuicConfiguration = object  # type: ignore[assignment]
    QuicConnectionProtocol = object  # type: ignore[assignment]
    quic_connect = None  # type: ignore[assignment]

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
MIN_TIP_HELIUS = 0.000005       # swqos_only mode
MIN_TIP_HELIUS_NORMAL = 0.0002  # normal mode
MIN_TIP_STELLIUM = 0.0001
MIN_TIP_LIGHTSPEED = 0.0001
MIN_TIP_NEXT_BLOCK = 0.001
MIN_TIP_SOYAS = 0.001
MIN_TIP_SPEEDLANDING = 0.001
MIN_TIP_SOLAMI = 0.0001
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


def _random_tip_account(accounts: List[str]) -> str:
    """Randomly select a tip account from the list"""
    return random.choice(accounts)


def _signature_from_serialized_transaction(transaction: bytes) -> str:
    if len(transaction) < 65 or transaction[0] != 1:
        raise TradeError(
            code=400,
            message="Only single-signature versioned transactions are supported for SWQOS submit",
        )
    return base58.b58encode(transaction[1:65]).decode("ascii")


# ===== Endpoints by Region =====

JITO_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "https://ny.mainnet.block-engine.jito.wtf",
    SwqosRegion.FRANKFURT:   "https://frankfurt.mainnet.block-engine.jito.wtf",
    SwqosRegion.AMSTERDAM:   "https://amsterdam.mainnet.block-engine.jito.wtf",
    SwqosRegion.DUBLIN:      "https://dublin.mainnet.block-engine.jito.wtf",
    SwqosRegion.SLC:         "https://slc.mainnet.block-engine.jito.wtf",
    SwqosRegion.TOKYO:       "https://tokyo.mainnet.block-engine.jito.wtf",
    SwqosRegion.SINGAPORE:   "https://singapore.mainnet.block-engine.jito.wtf",
    SwqosRegion.LONDON:      "https://london.mainnet.block-engine.jito.wtf",
    SwqosRegion.LOS_ANGELES: "https://slc.mainnet.block-engine.jito.wtf",
    SwqosRegion.DEFAULT:     "https://mainnet.block-engine.jito.wtf",
}

BLOXROUTE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "https://ny.solana.dex.blxrbdn.com",
    SwqosRegion.FRANKFURT:   "https://germany.solana.dex.blxrbdn.com",
    SwqosRegion.AMSTERDAM:   "https://amsterdam.solana.dex.blxrbdn.com",
    SwqosRegion.DUBLIN:      "https://uk.solana.dex.blxrbdn.com",
    SwqosRegion.SLC:         "https://la.solana.dex.blxrbdn.com",
    SwqosRegion.TOKYO:       "https://tokyo.solana.dex.blxrbdn.com",
    SwqosRegion.SINGAPORE:   "https://tokyo.solana.dex.blxrbdn.com",
    SwqosRegion.LONDON:      "https://uk.solana.dex.blxrbdn.com",
    SwqosRegion.LOS_ANGELES: "https://la.solana.dex.blxrbdn.com",
    SwqosRegion.DEFAULT:     "https://global.solana.dex.blxrbdn.com",
}

ZERO_SLOT_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.0slot.trade",
    SwqosRegion.FRANKFURT:   "http://de2.0slot.trade",
    SwqosRegion.AMSTERDAM:   "http://ams.0slot.trade",
    SwqosRegion.DUBLIN:      "http://ams.0slot.trade",
    SwqosRegion.SLC:         "http://la.0slot.trade",
    SwqosRegion.TOKYO:       "http://jp.0slot.trade",
    SwqosRegion.SINGAPORE:   "http://jp.0slot.trade",
    SwqosRegion.LONDON:      "http://ams.0slot.trade",
    SwqosRegion.LOS_ANGELES: "http://la.0slot.trade",
    SwqosRegion.DEFAULT:     "http://de2.0slot.trade",
}

TEMPORAL_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr1.nozomi.temporal.xyz",
    SwqosRegion.FRANKFURT:   "http://fra2.nozomi.temporal.xyz",
    SwqosRegion.AMSTERDAM:   "http://ams1.nozomi.temporal.xyz",
    SwqosRegion.DUBLIN:      "http://lon1.nozomi.temporal.xyz",
    SwqosRegion.SLC:         "http://lax1.nozomi.temporal.xyz",
    SwqosRegion.TOKYO:       "http://tyo1.nozomi.temporal.xyz",
    SwqosRegion.SINGAPORE:   "http://sgp1.nozomi.temporal.xyz",
    SwqosRegion.LONDON:      "http://lon1.nozomi.temporal.xyz",
    SwqosRegion.LOS_ANGELES: "http://lax1.nozomi.temporal.xyz",
    SwqosRegion.DEFAULT:     "http://fra2.nozomi.temporal.xyz",
}

FLASH_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.flashblock.trade",
    SwqosRegion.FRANKFURT:   "http://fra.flashblock.trade",
    SwqosRegion.AMSTERDAM:   "http://ams.flashblock.trade",
    SwqosRegion.DUBLIN:      "http://london.flashblock.trade",
    SwqosRegion.SLC:         "http://slc.flashblock.trade",
    SwqosRegion.TOKYO:       "http://tokyo.flashblock.trade",
    SwqosRegion.SINGAPORE:   "http://singapore.flashblock.trade",
    SwqosRegion.LONDON:      "http://london.flashblock.trade",
    SwqosRegion.LOS_ANGELES: "http://slc.flashblock.trade",
    SwqosRegion.DEFAULT:     "http://fra.flashblock.trade",
}

HELIUS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr-sender.helius-rpc.com/fast",
    SwqosRegion.FRANKFURT:   "http://fra-sender.helius-rpc.com/fast",
    SwqosRegion.AMSTERDAM:   "http://ams-sender.helius-rpc.com/fast",
    SwqosRegion.DUBLIN:      "http://lon-sender.helius-rpc.com/fast",
    SwqosRegion.SLC:         "http://slc-sender.helius-rpc.com/fast",
    SwqosRegion.TOKYO:       "http://tyo-sender.helius-rpc.com/fast",
    SwqosRegion.SINGAPORE:   "http://sg-sender.helius-rpc.com/fast",
    SwqosRegion.LONDON:      "http://lon-sender.helius-rpc.com/fast",
    SwqosRegion.LOS_ANGELES: "http://slc-sender.helius-rpc.com/fast",
    SwqosRegion.DEFAULT:     "https://sender.helius-rpc.com/fast",
}

NODE1_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.node1.me",
    SwqosRegion.FRANKFURT:   "http://fra.node1.me",
    SwqosRegion.AMSTERDAM:   "http://ams.node1.me",
    SwqosRegion.DUBLIN:      "http://lon.node1.me",
    SwqosRegion.SLC:         "http://ny.node1.me",
    SwqosRegion.TOKYO:       "http://tk.node1.me",
    SwqosRegion.SINGAPORE:   "http://tk.node1.me",
    SwqosRegion.LONDON:      "http://lon.node1.me",
    SwqosRegion.LOS_ANGELES: "http://ny.node1.me",
    SwqosRegion.DEFAULT:     "http://fra.node1.me",
}

BLOCK_RAZOR_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.FRANKFURT:   "http://frankfurt.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.AMSTERDAM:   "http://amsterdam.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.DUBLIN:      "http://london.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.SLC:         "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.TOKYO:       "http://tokyo.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.SINGAPORE:   "http://tokyo.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.LONDON:      "http://london.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.LOS_ANGELES: "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.DEFAULT:     "http://frankfurt.solana.blockrazor.xyz:443/v2/sendTransaction",
}

ASTRALANE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.gateway.astralane.io/irisb",
    SwqosRegion.FRANKFURT:   "http://fr.gateway.astralane.io/irisb",
    SwqosRegion.AMSTERDAM:   "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.DUBLIN:      "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.SLC:         "http://la.gateway.astralane.io/irisb",
    SwqosRegion.TOKYO:       "http://jp.gateway.astralane.io/irisb",
    SwqosRegion.SINGAPORE:   "http://sg.gateway.astralane.io/irisb",
    SwqosRegion.LONDON:      "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.LOS_ANGELES: "http://la.gateway.astralane.io/irisb",
    SwqosRegion.DEFAULT:     "https://edge.astralane.io/irisb",
}

ASTRALANE_QUIC_HOSTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "ny.gateway.astralane.io",
    SwqosRegion.FRANKFURT:   "fr.gateway.astralane.io",
    SwqosRegion.AMSTERDAM:   "ams.gateway.astralane.io",
    SwqosRegion.DUBLIN:      "ams.gateway.astralane.io",
    SwqosRegion.SLC:         "la.gateway.astralane.io",
    SwqosRegion.TOKYO:       "jp.gateway.astralane.io",
    SwqosRegion.SINGAPORE:   "sg.gateway.astralane.io",
    SwqosRegion.LONDON:      "ams.gateway.astralane.io",
    SwqosRegion.LOS_ANGELES: "la.gateway.astralane.io",
    SwqosRegion.DEFAULT:     "lim.gateway.astralane.io",
}

STELLIUM_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr1.flashrpc.com",
    SwqosRegion.FRANKFURT:   "http://fra1.flashrpc.com",
    SwqosRegion.AMSTERDAM:   "http://ams1.flashrpc.com",
    SwqosRegion.DUBLIN:      "http://lhr1.flashrpc.com",
    SwqosRegion.SLC:         "http://ewr1.flashrpc.com",
    SwqosRegion.TOKYO:       "http://tyo1.flashrpc.com",
    SwqosRegion.SINGAPORE:   "http://tyo1.flashrpc.com",
    SwqosRegion.LONDON:      "http://lhr1.flashrpc.com",
    SwqosRegion.LOS_ANGELES: "http://ewr1.flashrpc.com",
    SwqosRegion.DEFAULT:     "http://fra1.flashrpc.com",
}

NEXT_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.nextblock.io",
    SwqosRegion.FRANKFURT:   "http://fra.nextblock.io",
    SwqosRegion.AMSTERDAM:   "http://ams.nextblock.io",
    SwqosRegion.DUBLIN:      "http://dublin.nextblock.io",
    SwqosRegion.SLC:         "http://slc.nextblock.io",
    SwqosRegion.TOKYO:       "http://tokyo.nextblock.io",
    SwqosRegion.SINGAPORE:   "http://sgp.nextblock.io",
    SwqosRegion.LONDON:      "http://london.nextblock.io",
    SwqosRegion.LOS_ANGELES: "http://slc.nextblock.io",
    SwqosRegion.DEFAULT:     "http://fra.nextblock.io",
}

SOYAS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "nyc.landing.soyas.xyz:9000",
    SwqosRegion.FRANKFURT:   "fra.landing.soyas.xyz:9000",
    SwqosRegion.AMSTERDAM:   "ams.landing.soyas.xyz:9000",
    SwqosRegion.DUBLIN:      "lon.landing.soyas.xyz:9000",
    SwqosRegion.SLC:         "nyc.landing.soyas.xyz:9000",
    SwqosRegion.TOKYO:       "tyo.landing.soyas.xyz:9000",
    SwqosRegion.SINGAPORE:   "tyo.landing.soyas.xyz:9000",
    SwqosRegion.LONDON:      "lon.landing.soyas.xyz:9000",
    SwqosRegion.LOS_ANGELES: "nyc.landing.soyas.xyz:9000",
    SwqosRegion.DEFAULT:     "fra.landing.soyas.xyz:9000",
}

SPEEDLANDING_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "nyc.speedlanding.trade:17778",
    SwqosRegion.FRANKFURT:   "fra.speedlanding.trade:17778",
    SwqosRegion.AMSTERDAM:   "ams.speedlanding.trade:17778",
    SwqosRegion.DUBLIN:      "ams.speedlanding.trade:17778",
    SwqosRegion.SLC:         "nyc.speedlanding.trade:17778",
    SwqosRegion.TOKYO:       "tyo.speedlanding.trade:17778",
    SwqosRegion.SINGAPORE:   "sgp.speedlanding.trade:17778",
    SwqosRegion.LONDON:      "ams.speedlanding.trade:17778",
    SwqosRegion.LOS_ANGELES: "nyc.speedlanding.trade:17778",
    SwqosRegion.DEFAULT:     "fra.speedlanding.trade:17778",
}

SOLAMI_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "beam.solami.dev:11000",
    SwqosRegion.FRANKFURT:   "beam.solami.dev:11000",
    SwqosRegion.AMSTERDAM:   "beam.solami.dev:11000",
    SwqosRegion.DUBLIN:      "beam.solami.dev:11000",
    SwqosRegion.SLC:         "beam.solami.dev:11000",
    SwqosRegion.TOKYO:       "beam.solami.dev:11000",
    SwqosRegion.SINGAPORE:   "beam.solami.dev:11000",
    SwqosRegion.LONDON:      "beam.solami.dev:11000",
    SwqosRegion.LOS_ANGELES: "beam.solami.dev:11000",
    SwqosRegion.DEFAULT:     "beam.solami.dev:11000",
}


# ===== Error Handling =====

@dataclass
class TradeError(Exception):
    """Trade error with detailed information"""
    code: int
    message: str
    instruction_index: Optional[int] = None

    def __str__(self):
        return f"TradeError(code={self.code}, message={self.message})"


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
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()


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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        return data["result"]

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500),
                message=data["error"].get("message", "Unknown error"),
            )

        bundle_id = data["result"]
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

        if "reason" in data and data.get("reason"):
            raise TradeError(code=500, message=data["reason"])

        return data.get("signature", data.get("result", ""))

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

class TemporalClient(SwqosClient, HTTPClientMixin):
    """
    Temporal (Nozomi) SWQOS client implementation.

    URL:    {endpoint}/?c={token}   (auth in URL param, not header)
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
        self._tip_account = _random_tip_account(TEMPORAL_TIP_ACCOUNTS)

    def _build_url(self) -> str:
        if self.auth_token:
            return f"{self.endpoint}/?c={self.auth_token}"
        return f"{self.endpoint}/"

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if isinstance(data, dict) and "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        # Response may be a list of results or a dict
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict):
                if "error" in item:
                    raise TradeError(code=500, message=str(item["error"]))
                return item.get("signature", item.get("result", ""))
        if isinstance(data, dict):
            return data.get("signature", data.get("result", ""))
        return str(data)

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

        if isinstance(data, list):
            results = []
            for item in data:
                if isinstance(item, dict):
                    if "error" in item:
                        raise TradeError(code=500, message=str(item["error"]))
                    results.append(item.get("signature", item.get("result", "")))
                else:
                    results.append(str(item))
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
        if self.api_key:
            return f"{self.endpoint}?api-key={self.api_key}"
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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

class BlockRazorClient(SwqosClient, HTTPClientMixin):
    """
    BlockRazor SWQOS client implementation.

    URL:    {endpoint}?auth={token}&mode={mode}
            mode = "fast" | "sandwichMitigation"
    Content-Type: text/plain
    Body:   raw base64 string (not JSON)
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

    def _build_url(self) -> str:
        mode = "sandwichMitigation" if self.mev_protection else "fast"
        url = self.endpoint
        params = []
        if self.auth_token:
            params.append(f"auth={self.auth_token}")
        params.append(f"mode={mode}")
        return f"{url}?{'&'.join(params)}"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        session = await self.get_session()
        url = self._build_url()
        headers = {"Content-Type": "text/plain"}

        async with session.post(url, data=encoded, headers=headers) as resp:
            text = await resp.text()

        # BlockRazor returns the signature as plain text or JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "error" in data:
                    raise TradeError(code=500, message=str(data["error"]))
                return data.get("signature", data.get("result", text))
        except (json.JSONDecodeError, ValueError):
            pass

        return text.strip()

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


# ===== Astralane Client =====

class AstralaneClient(SwqosClient, HTTPClientMixin):
    """
    Astralane SWQOS client implementation.

    Note: Rust SDK uses bincode serialization (octet-stream).
    Python fallback uses JSON-RPC format (simplified implementation).

    URL:    {endpoint}?api-key={token}&method=sendTransaction
    Body:   JSON-RPC sendTransaction (base64 encoding)
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
        params = []
        if self.auth_token:
            params.append(f"api-key={self.auth_token}")
        params.append("method=sendTransaction")
        return f"{self.endpoint}?{'&'.join(params)}"

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        encoded = base64.b64encode(transaction).decode()

        # Simplified JSON-RPC fallback (Rust SDK uses bincode/octet-stream)
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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        return data["result"]

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

        if isinstance(data, dict) and "reason" in data and data.get("reason"):
            raise TradeError(code=500, message=data["reason"])
        if isinstance(data, dict) and "error" in data:
            raise TradeError(
                code=data["error"].get("code", 500) if isinstance(data["error"], dict) else 500,
                message=data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"]),
            )

        if isinstance(data, dict):
            return data.get("signature", data.get("result", ""))
        return str(data)

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

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    cfg = QuicConfiguration(
        alpn_protocols=["solana-tpu"],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
        server_name=server_name,
    )
    cfg.load_cert_chain(certfile=None, keyfile=None)  # will be overridden below
    # Load the generated cert/key directly into the SSL context
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
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(hours=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
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

    def __init__(self, *args, tx_bytes: bytes, **kwargs):
        super().__init__(*args, **kwargs)
        self._tx_bytes = tx_bytes
        self._done = asyncio.Event()

    def quic_event_received(self, event) -> None:
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
        await protocol.send_tx()


class _Node1QuicProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffers: Dict[int, bytearray] = {}
        self._done: Dict[int, asyncio.Future] = {}

    def quic_event_received(self, event) -> None:
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
    async with quic_connect(host, port, configuration=cfg, create_protocol=_Node1QuicProtocol) as protocol:
        auth_reply = await protocol.send_and_read(api_key_bytes)
        if auth_reply != b"\x00":
            code = auth_reply[0] if auth_reply else -1
            raise TradeError(401, f"Node1 QUIC auth rejected: {code}")
        response = await protocol.send_and_read(tx_bytes)
        if len(response) < 6:
            raise TradeError(500, "Node1 QUIC response too short")
        status = int.from_bytes(response[:2], "big")
        msg_len = int.from_bytes(response[2:6], "big")
        msg = response[6:6 + msg_len].decode("utf-8", errors="replace")
        if status != 200:
            raise TradeError(status, f"Node1 QUIC submit failed: {msg}")


async def _astralane_quic_submit(endpoint: str, api_key: str, tx_bytes: bytes) -> None:
    if not _QUIC_AVAILABLE:
        raise TradeError(501, "QUIC not available: install sol-trade-sdk[quic].")
    if len(tx_bytes) > 1232:
        raise TradeError(400, f"Astralane QUIC transaction too large: {len(tx_bytes)} > 1232")
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        host, port = _host_port_from_http(endpoint, 7000)
    else:
        host_port = endpoint.rsplit(":", 1)
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) == 2 and host_port[1].isdigit() else 7000
    cfg = _make_astralane_quic_config(api_key)
    async with quic_connect(
        host,
        port,
        configuration=cfg,
        create_protocol=lambda *a, **kw: _SolanaTPUProtocol(*a, tx_bytes=tx_bytes, **kw),
    ) as protocol:
        await protocol.send_tx()


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
            signatures.append(await self.send_transaction(trade_type, transaction, wait_confirmation))
        return signatures

    def get_tip_account(self) -> str:
        return random.choice(NODE1_TIP_ACCOUNTS)

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.NODE1

    def min_tip_sol(self) -> float:
        return MIN_TIP_NODE1


class AstralaneQuicClient(SwqosClient):
    """Astralane QUIC TPU client using API key as client certificate CN."""

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
        await _astralane_quic_submit(self.endpoint, self.api_key, transaction)
        return _signature_from_serialized_transaction(transaction)

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        signatures: List[str] = []
        for transaction in transactions:
            signatures.append(await self.send_transaction(trade_type, transaction, wait_confirmation))
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
    SNI:       derived from hostname (e.g. "nyc.speedlanding.trade"),
               falls back to "speed-landing" for bare IPs (matches Rust SDK).
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
        # Derive SNI: use hostname unless it's a bare IP
        try:
            ipaddress.ip_address(self._host)
            self._server_name = "speed-landing"
        except ValueError:
            self._server_name = self._host

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
    Endpoint:  host:port (Rust v4.0.21 defaults every region to beam.solami.dev:11000)
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
            raise ValueError(f"SWQOS type is blacklisted by Rust v4.0.21 parity: {config.type}")
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
            return TemporalClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.FLASH_BLOCK.value:
            endpoint = config.custom_url or FLASH_BLOCK_ENDPOINTS.get(
                region, FLASH_BLOCK_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return FlashBlockClient(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.HELIUS.value:
            endpoint = config.custom_url or HELIUS_ENDPOINTS.get(
                region, HELIUS_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return HeliusClient(rpc_url, endpoint, config.api_key, swqos_only=bool(config.swqos_only))

        elif swqos_type == SwqosType.NODE1.value:
            transport = getattr(getattr(config, "transport", None), "value", getattr(config, "transport", None))
            endpoint = config.custom_url or NODE1_ENDPOINTS.get(
                region, NODE1_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            if transport == "Quic":
                return Node1QuicClient(rpc_url, f"{_host_port_from_http(endpoint, 16666)[0]}:16666", config.api_key)
            return Node1Client(rpc_url, endpoint, config.api_key)

        elif swqos_type == SwqosType.BLOCK_RAZOR.value:
            endpoint = config.custom_url or BLOCK_RAZOR_ENDPOINTS.get(
                region, BLOCK_RAZOR_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return BlockRazorClient(
                rpc_url, endpoint, config.api_key, mev_protection=config.mev_protection
            )

        elif swqos_type == SwqosType.ASTRALANE.value:
            endpoint = config.custom_url or ASTRALANE_ENDPOINTS.get(
                region, ASTRALANE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            mode = getattr(
                getattr(config, "astralane_transport", None),
                "value",
                getattr(config, "astralane_transport", None),
            )
            if mode == "Plain":
                endpoint = endpoint.replace("/irisb", "/iris")
            elif mode == "Quic":
                if config.custom_url:
                    if config.custom_url.startswith(("http://", "https://")):
                        host, port = _host_port_from_http(config.custom_url, 9000 if config.mev_protection else 7000)
                        endpoint = f"{host}:{port}"
                    else:
                        endpoint = config.custom_url
                else:
                    host = ASTRALANE_QUIC_HOSTS.get(region, ASTRALANE_QUIC_HOSTS[SwqosRegion.DEFAULT])
                    endpoint = f"{host}:{9000 if config.mev_protection else 7000}"
                return AstralaneQuicClient(rpc_url, endpoint, config.api_key)
            return AstralaneClient(rpc_url, endpoint, config.api_key)

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
