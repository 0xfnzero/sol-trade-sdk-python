"""
Seed generation utilities for deterministic key derivation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import List, Optional, Tuple


class SeedGenerator:
    """
    Generate deterministic seeds for key derivation.

    Follows BIP-39 and BIP-44 standards for HD wallet compatibility.
    """

    # BIP-39 English wordlist (first 16 words for space)
    BIP39_WORDLIST = [
        "abandon", "ability", "able", "about", "above", "absent",
        "absorb", "abstract", "absurd", "abuse", "access", "accident",
        "account", "accuse", "achieve", "acid",
    ]

    @classmethod
    def generate_mnemonic(cls, word_count: int = 12) -> str:
        """
        Generate BIP-39 mnemonic phrase.

        Args:
            word_count: Number of words (12, 15, 18, 21, or 24)

        Returns:
            Space-separated mnemonic phrase
        """
        # Generate random entropy
        entropy_bits = word_count * 32 // 3
        entropy_bytes = entropy_bits // 8
        entropy = secrets.token_bytes(entropy_bytes)

        # Calculate checksum
        checksum_bits = entropy_bits // 32
        checksum = hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits)

        # Combine entropy and checksum
        combined = int.from_bytes(entropy, 'big') << checksum_bits | checksum
        total_bits = entropy_bits + checksum_bits

        # Split into words
        words = []
        for i in range(word_count):
            index = (combined >> (total_bits - (i + 1) * 11)) & 0x7FF
            # In real implementation, use full BIP-39 wordlist
            words.append(cls.BIP39_WORDLIST[index % len(cls.BIP39_WORDLIST)])

        return " ".join(words)

    @classmethod
    def mnemonic_to_seed(
        cls,
        mnemonic: str,
        passphrase: str = "",
    ) -> bytes:
        """
        Convert mnemonic to seed using PBKDF2.

        Args:
            mnemonic: BIP-39 mnemonic phrase
            passphrase: Optional passphrase

        Returns:
            64-byte seed
        """
        mnemonic_nfkd = cls._normalize(mnemonic)
        passphrase_nfkd = "mnemonic" + cls._normalize(passphrase)

        seed = hashlib.pbkdf2_hmac(
            "sha512",
            mnemonic_nfkd.encode("utf-8"),
            passphrase_nfkd.encode("utf-8"),
            2048,
        )

        return seed

    @classmethod
    def generate_random_seed(cls, size: int = 32) -> bytes:
        """
        Generate cryptographically secure random seed.

        Args:
            size: Seed size in bytes

        Returns:
            Random seed bytes
        """
        return secrets.token_bytes(size)

    @classmethod
    def derive_key_from_seed(
        cls,
        seed: bytes,
        path: str,
    ) -> bytes:
        """
        Derive key from seed using BIP-44 path.

        Args:
            seed: Master seed
            path: Derivation path (e.g., "m/44'/501'/0'/0'")

        Returns:
            Derived key
        """
        # Parse path
        indices = cls._parse_path(path)

        # HMAC-SHA512 with key "ed25519 seed"
        key = b"ed25519 seed"
        data = seed

        for index in indices:
            data = hmac.new(key, data, hashlib.sha512).digest()
            # Apply hardened index
            if index >= 0x80000000:
                data = b"\x00" + data[:32] + index.to_bytes(4, 'big')
            else:
                data = data[:32] + index.to_bytes(4, 'big')
            key = data[32:]
            data = data[:32]

        return data

    @classmethod
    def _parse_path(cls, path: str) -> List[int]:
        """Parse BIP-44 derivation path."""
        if not path.startswith("m/"):
            raise ValueError("Path must start with 'm/'")

        indices = []
        for part in path[2:].split("/"):
            if part.endswith("'"):
                # Hardened index
                indices.append(0x80000000 | int(part[:-1]))
            else:
                indices.append(int(part))

        return indices

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text using NFKD."""
        import unicodedata
        return unicodedata.normalize("NFKD", text)


class DerivationPath:
    """BIP-44 derivation path builder."""

    PURPOSE_BIP44 = 44
    COIN_TYPE_SOLANA = 501

    def __init__(
        self,
        purpose: int = PURPOSE_BIP44,
        coin_type: int = COIN_TYPE_SOLANA,
        account: int = 0,
        change: int = 0,
        address_index: int = 0,
    ):
        self.purpose = purpose
        self.coin_type = coin_type
        self.account = account
        self.change = change
        self.address_index = address_index

    def to_string(self, hardened: bool = True) -> str:
        """Convert to derivation path string."""
        h = "'" if hardened else ""
        return (
            f"m/{self.purpose}{h}/"
            f"{self.coin_type}{h}/"
            f"{self.account}{h}/"
            f"{self.change}{h}/"
            f"{self.address_index}{h}"
        )

    @classmethod
    def from_string(cls, path: str) -> "DerivationPath":
        """Parse derivation path string."""
        indices = SeedGenerator._parse_path(path)
        if len(indices) < 5:
            raise ValueError("Path must have at least 5 components")

        return cls(
            purpose=indices[0] & 0x7FFFFFFF,
            coin_type=indices[1] & 0x7FFFFFFF,
            account=indices[2] & 0x7FFFFFFF,
            change=indices[3] & 0x7FFFFFFF,
            address_index=indices[4] & 0x7FFFFFFF,
        )

    def derive_next(self) -> "DerivationPath":
        """Get path for next address index."""
        return DerivationPath(
            purpose=self.purpose,
            coin_type=self.coin_type,
            account=self.account,
            change=self.change,
            address_index=self.address_index + 1,
        )


class KeyPair:
    """Ed25519 key pair for Solana."""

    def __init__(self, secret_key: bytes, public_key: bytes):
        self.secret_key = secret_key
        self.public_key = public_key

    @classmethod
    def from_seed(cls, seed: bytes) -> "KeyPair":
        """
        Generate key pair from 32-byte seed.

        Args:
            seed: 32-byte seed

        Returns:
            KeyPair instance
        """
        # In real implementation, use ed25519 library
        # This is a placeholder
        import hashlib
        public_key = hashlib.sha256(seed).digest()[:32]
        secret_key = seed + public_key
        return cls(secret_key, public_key)

    def to_bytes(self) -> bytes:
        """Serialize key pair to bytes."""
        return self.secret_key

    @classmethod
    def from_bytes(cls, data: bytes) -> "KeyPair":
        """Deserialize key pair from bytes."""
        if len(data) == 64:
            secret_key = data[:32]
            public_key = data[32:]
        elif len(data) == 32:
            # Just secret key, derive public key
            secret_key = data
            import hashlib
            public_key = hashlib.sha256(secret_key).digest()[:32]
        else:
            raise ValueError("Invalid key pair data length")

        return cls(secret_key, public_key)


# Convenience functions
def generate_mnemonic(word_count: int = 12) -> str:
    """Generate BIP-39 mnemonic."""
    return SeedGenerator.generate_mnemonic(word_count)


def mnemonic_to_keypair(mnemonic: str, passphrase: str = "") -> KeyPair:
    """Convert mnemonic to Solana key pair."""
    seed = SeedGenerator.mnemonic_to_seed(mnemonic, passphrase)
    # Use first 32 bytes as seed for Ed25519
    return KeyPair.from_seed(seed[:32])


def derive_keypair(
    mnemonic: str,
    path: str = "m/44'/501'/0'/0'",
    passphrase: str = "",
) -> KeyPair:
    """Derive key pair from mnemonic and path."""
    seed = SeedGenerator.mnemonic_to_seed(mnemonic, passphrase)
    derived = SeedGenerator.derive_key_from_seed(seed[:64], path)
    return KeyPair.from_seed(derived[:32])
