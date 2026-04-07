"""
SWQOS Clients for Sol Trade SDK
Implements various SWQOS (Solana Write Queue Operating System) providers.
"""

import asyncio
import base64
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

import aiohttp

from ..common.types import SwqosType, SwqosRegion, TradeType


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
MIN_TIP_DEFAULT = 0.0


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


def _random_tip_account(accounts: List[str]) -> str:
    """Randomly select a tip account from the list"""
    return random.choice(accounts)


# ===== Endpoints by Region =====

JITO_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "https://ny.mainnet.block-engine.jito.wtf",
    SwqosRegion.FRANKFURT:   "https://frankfurt.mainnet.block-engine.jito.wtf",
    SwqosRegion.AMSTERDAM:   "https://amsterdam.mainnet.block-engine.jito.wtf",
    SwqosRegion.SLC:         "https://slc.mainnet.block-engine.jito.wtf",
    SwqosRegion.TOKYO:       "https://tokyo.mainnet.block-engine.jito.wtf",
    SwqosRegion.LONDON:      "https://london.mainnet.block-engine.jito.wtf",
    SwqosRegion.LOS_ANGELES: "https://ny.mainnet.block-engine.jito.wtf",
    SwqosRegion.DEFAULT:     "https://mainnet.block-engine.jito.wtf",
}

BLOXROUTE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "https://ny.solana.dex.blxrbdn.com",
    SwqosRegion.FRANKFURT:   "https://germany.solana.dex.blxrbdn.com",
    SwqosRegion.AMSTERDAM:   "https://amsterdam.solana.dex.blxrbdn.com",
    SwqosRegion.SLC:         "https://ny.solana.dex.blxrbdn.com",
    SwqosRegion.TOKYO:       "https://tokyo.solana.dex.blxrbdn.com",
    SwqosRegion.LONDON:      "https://uk.solana.dex.blxrbdn.com",
    SwqosRegion.LOS_ANGELES: "https://la.solana.dex.blxrbdn.com",
    SwqosRegion.DEFAULT:     "https://global.solana.dex.blxrbdn.com",
}

ZERO_SLOT_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.0slot.trade",
    SwqosRegion.FRANKFURT:   "http://de2.0slot.trade",
    SwqosRegion.AMSTERDAM:   "http://ams.0slot.trade",
    SwqosRegion.SLC:         "http://ny.0slot.trade",
    SwqosRegion.TOKYO:       "http://jp.0slot.trade",
    SwqosRegion.LONDON:      "http://ams.0slot.trade",
    SwqosRegion.LOS_ANGELES: "http://la.0slot.trade",
    SwqosRegion.DEFAULT:     "http://de2.0slot.trade",
}

TEMPORAL_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr1.nozomi.temporal.xyz",
    SwqosRegion.FRANKFURT:   "http://fra2.nozomi.temporal.xyz",
    SwqosRegion.AMSTERDAM:   "http://ams1.nozomi.temporal.xyz",
    SwqosRegion.SLC:         "http://ewr1.nozomi.temporal.xyz",
    SwqosRegion.TOKYO:       "http://tyo1.nozomi.temporal.xyz",
    SwqosRegion.LONDON:      "http://sgp1.nozomi.temporal.xyz",
    SwqosRegion.LOS_ANGELES: "http://pit1.nozomi.temporal.xyz",
    SwqosRegion.DEFAULT:     "http://fra2.nozomi.temporal.xyz",
}

FLASH_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.flashblock.trade",
    SwqosRegion.FRANKFURT:   "http://fra.flashblock.trade",
    SwqosRegion.AMSTERDAM:   "http://ams.flashblock.trade",
    SwqosRegion.SLC:         "http://slc.flashblock.trade",
    SwqosRegion.TOKYO:       "http://singapore.flashblock.trade",
    SwqosRegion.LONDON:      "http://london.flashblock.trade",
    SwqosRegion.LOS_ANGELES: "http://ny.flashblock.trade",
    SwqosRegion.DEFAULT:     "http://ny.flashblock.trade",
}

HELIUS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr-sender.helius-rpc.com/fast",
    SwqosRegion.FRANKFURT:   "http://fra-sender.helius-rpc.com/fast",
    SwqosRegion.AMSTERDAM:   "http://ams-sender.helius-rpc.com/fast",
    SwqosRegion.SLC:         "http://slc-sender.helius-rpc.com/fast",
    SwqosRegion.TOKYO:       "http://tyo-sender.helius-rpc.com/fast",
    SwqosRegion.LONDON:      "http://lon-sender.helius-rpc.com/fast",
    SwqosRegion.LOS_ANGELES: "http://sg-sender.helius-rpc.com/fast",
    SwqosRegion.DEFAULT:     "https://sender.helius-rpc.com/fast",
}

NODE1_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.node1.me",
    SwqosRegion.FRANKFURT:   "http://fra.node1.me",
    SwqosRegion.AMSTERDAM:   "http://ams.node1.me",
    SwqosRegion.SLC:         "http://ny.node1.me",
    SwqosRegion.TOKYO:       "http://tk.node1.me",
    SwqosRegion.LONDON:      "http://lon.node1.me",
    SwqosRegion.LOS_ANGELES: "http://ny.node1.me",
    SwqosRegion.DEFAULT:     "http://fra.node1.me",
}

BLOCK_RAZOR_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.FRANKFURT:   "http://frankfurt.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.AMSTERDAM:   "http://amsterdam.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.SLC:         "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.TOKYO:       "http://tokyo.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.LONDON:      "http://london.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.LOS_ANGELES: "http://newyork.solana.blockrazor.xyz:443/v2/sendTransaction",
    SwqosRegion.DEFAULT:     "http://frankfurt.solana.blockrazor.xyz:443/v2/sendTransaction",
}

ASTRALANE_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.gateway.astralane.io/irisb",
    SwqosRegion.FRANKFURT:   "http://fr.gateway.astralane.io/irisb",
    SwqosRegion.AMSTERDAM:   "http://ams.gateway.astralane.io/irisb",
    SwqosRegion.SLC:         "http://ny.gateway.astralane.io/irisb",
    SwqosRegion.TOKYO:       "http://jp.gateway.astralane.io/irisb",
    SwqosRegion.LONDON:      "http://ny.gateway.astralane.io/irisb",
    SwqosRegion.LOS_ANGELES: "http://lax.gateway.astralane.io/irisb",
    SwqosRegion.DEFAULT:     "http://lim.gateway.astralane.io/irisb",
}

STELLIUM_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ewr1.flashrpc.com",
    SwqosRegion.FRANKFURT:   "http://fra1.flashrpc.com",
    SwqosRegion.AMSTERDAM:   "http://ams1.flashrpc.com",
    SwqosRegion.SLC:         "http://ewr1.flashrpc.com",
    SwqosRegion.TOKYO:       "http://tyo1.flashrpc.com",
    SwqosRegion.LONDON:      "http://lhr1.flashrpc.com",
    SwqosRegion.LOS_ANGELES: "http://ewr1.flashrpc.com",
    SwqosRegion.DEFAULT:     "http://fra1.flashrpc.com",
}

NEXT_BLOCK_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "http://ny.nextblock.io",
    SwqosRegion.FRANKFURT:   "http://frankfurt.nextblock.io",
    SwqosRegion.AMSTERDAM:   "http://amsterdam.nextblock.io",
    SwqosRegion.SLC:         "http://slc.nextblock.io",
    SwqosRegion.TOKYO:       "http://tokyo.nextblock.io",
    SwqosRegion.LONDON:      "http://london.nextblock.io",
    SwqosRegion.LOS_ANGELES: "http://singapore.nextblock.io",
    SwqosRegion.DEFAULT:     "http://frankfurt.nextblock.io",
}

SOYAS_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "nyc.landing.soyas.xyz:9000",
    SwqosRegion.FRANKFURT:   "fra.landing.soyas.xyz:9000",
    SwqosRegion.AMSTERDAM:   "ams.landing.soyas.xyz:9000",
    SwqosRegion.SLC:         "nyc.landing.soyas.xyz:9000",
    SwqosRegion.TOKYO:       "tyo.landing.soyas.xyz:9000",
    SwqosRegion.LONDON:      "lon.landing.soyas.xyz:9000",
    SwqosRegion.LOS_ANGELES: "nyc.landing.soyas.xyz:9000",
    SwqosRegion.DEFAULT:     "fra.landing.soyas.xyz:9000",
}

SPEEDLANDING_ENDPOINTS: Dict[SwqosRegion, str] = {
    SwqosRegion.NEW_YORK:    "nyc.speedlanding.trade:17778",
    SwqosRegion.FRANKFURT:   "fra.speedlanding.trade:17778",
    SwqosRegion.AMSTERDAM:   "ams.speedlanding.trade:17778",
    SwqosRegion.SLC:         "nyc.speedlanding.trade:17778",
    SwqosRegion.TOKYO:       "tyo.speedlanding.trade:17778",
    SwqosRegion.LONDON:      "fra.speedlanding.trade:17778",
    SwqosRegion.LOS_ANGELES: "nyc.speedlanding.trade:17778",
    SwqosRegion.DEFAULT:     "fra.speedlanding.trade:17778",
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


# ===== Soyas Client =====

class SoyasClient(SwqosClient):
    """
    Soyas SWQOS client.

    Transport: QUIC with mTLS (Keypair-based certificate).
    Endpoint:  host:port (e.g. nyc.landing.soyas.xyz:9000)
    Auth:      Solana Keypair (base58) used as mTLS client certificate.
    Note:      QUIC is not natively supported in Python. Use the Rust SDK for
               full QUIC support. This client holds config for future integration.
    """

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.api_key = api_key
        self._tip_account = _random_tip_account(SOYAS_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        raise TradeError(
            code=501,
            message="Soyas requires QUIC transport with mTLS; not supported in Python SDK. Use the Rust SDK.",
        )

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        raise TradeError(
            code=501,
            message="Soyas requires QUIC transport with mTLS; not supported in Python SDK. Use the Rust SDK.",
        )

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

    Transport: QUIC with mTLS (Keypair-based certificate).
    Endpoint:  host:port (e.g. nyc.speedlanding.trade:17778)
    Auth:      Solana Keypair (base58) used as mTLS client certificate.
    Note:      QUIC is not natively supported in Python. Use the Rust SDK for
               full QUIC support. This client holds config for future integration.
    """

    def __init__(self, rpc_url: str, endpoint: str, api_key: Optional[str] = None):
        self.rpc_url = rpc_url
        self.endpoint = endpoint
        self.api_key = api_key
        self._tip_account = _random_tip_account(SPEEDLANDING_TIP_ACCOUNTS)

    async def send_transaction(
        self,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool = False,
    ) -> str:
        raise TradeError(
            code=501,
            message="Speedlanding requires QUIC transport with mTLS; not supported in Python SDK. Use the Rust SDK.",
        )

    async def send_transactions(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = False,
    ) -> List[str]:
        raise TradeError(
            code=501,
            message="Speedlanding requires QUIC transport with mTLS; not supported in Python SDK. Use the Rust SDK.",
        )

    def get_tip_account(self) -> str:
        return self._tip_account

    def get_swqos_type(self) -> SwqosType:
        return SwqosType.SPEEDLANDING

    def min_tip_sol(self) -> float:
        return MIN_TIP_SPEEDLANDING


# ===== Client Factory =====

@dataclass
class SwqosConfig:
    """Configuration for SWQOS client"""
    type: SwqosType
    region: SwqosRegion = SwqosRegion.DEFAULT
    custom_url: Optional[str] = None
    api_key: Optional[str] = None
    mev_protection: bool = False


class ClientFactory:
    """Factory for creating SWQOS clients"""

    @staticmethod
    def create_client(config: SwqosConfig, rpc_url: str) -> SwqosClient:
        """Create a SWQOS client from configuration"""

        if config.type == SwqosType.JITO:
            endpoint = config.custom_url or JITO_ENDPOINTS.get(
                config.region, JITO_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return JitoClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.BLOXROUTE:
            endpoint = config.custom_url or BLOXROUTE_ENDPOINTS.get(
                config.region, BLOXROUTE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return BloxrouteClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.ZERO_SLOT:
            endpoint = config.custom_url or ZERO_SLOT_ENDPOINTS.get(
                config.region, ZERO_SLOT_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return ZeroSlotClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.TEMPORAL:
            endpoint = config.custom_url or TEMPORAL_ENDPOINTS.get(
                config.region, TEMPORAL_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return TemporalClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.FLASH_BLOCK:
            endpoint = config.custom_url or FLASH_BLOCK_ENDPOINTS.get(
                config.region, FLASH_BLOCK_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return FlashBlockClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.HELIUS:
            endpoint = config.custom_url or HELIUS_ENDPOINTS.get(
                config.region, HELIUS_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return HeliusClient(rpc_url, endpoint, config.api_key, swqos_only=False)

        elif config.type == SwqosType.NODE1:
            endpoint = config.custom_url or NODE1_ENDPOINTS.get(
                config.region, NODE1_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return Node1Client(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.BLOCK_RAZOR:
            endpoint = config.custom_url or BLOCK_RAZOR_ENDPOINTS.get(
                config.region, BLOCK_RAZOR_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return BlockRazorClient(
                rpc_url, endpoint, config.api_key, mev_protection=config.mev_protection
            )

        elif config.type == SwqosType.ASTRALANE:
            endpoint = config.custom_url or ASTRALANE_ENDPOINTS.get(
                config.region, ASTRALANE_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return AstralaneClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.STELLIUM:
            endpoint = config.custom_url or STELLIUM_ENDPOINTS.get(
                config.region, STELLIUM_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return StelliumClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.LIGHTSPEED:
            # Lightspeed requires custom_url with api_key embedded
            endpoint = config.custom_url or ""
            return LightspeedClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.NEXT_BLOCK:
            endpoint = config.custom_url or NEXT_BLOCK_ENDPOINTS.get(
                config.region, NEXT_BLOCK_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return NextBlockClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.SOYAS:
            endpoint = config.custom_url or SOYAS_ENDPOINTS.get(
                config.region, SOYAS_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return SoyasClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.SPEEDLANDING:
            endpoint = config.custom_url or SPEEDLANDING_ENDPOINTS.get(
                config.region, SPEEDLANDING_ENDPOINTS[SwqosRegion.DEFAULT]
            )
            return SpeedlandingClient(rpc_url, endpoint, config.api_key)

        elif config.type == SwqosType.DEFAULT:
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
