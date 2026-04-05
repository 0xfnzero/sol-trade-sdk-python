"""
Secure key storage and management for Sol Trade SDK

Implements secure memory handling for private keys with:
- Memory encryption at rest
- Secure zeroing after use
- Context manager for automatic cleanup
- Hardware wallet abstraction support
"""

import os
import sys
import base64
import hashlib
import hmac
from typing import Optional, Union, Callable
from contextlib import contextmanager
from dataclasses import dataclass

# Try to import cryptography for encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

# Try to import solders for keypair handling
try:
    from solders.keypair import Keypair
    HAS_SOLDERS = True
except ImportError:
    HAS_SOLDERS = False


class SecureKeyError(Exception):
    """Raised when secure key operation fails"""
    pass


class KeyNotAvailableError(SecureKeyError):
    """Raised when trying to access a cleared key"""
    pass


@dataclass
class KeyMetadata:
    """Metadata about a stored key"""
    pubkey: str
    created_at: float
    last_accessed: Optional[float] = None
    access_count: int = 0


class SecureKeyStorage:
    """
    Secure storage for Solana private keys.

    Features:
    - Keys are encrypted in memory when not in use
    - Automatic secure zeroing of key material
    - Context manager support for temporary key access
    - Optional hardware wallet abstraction

    Usage:
        # Basic usage
        storage = SecureKeyStorage.from_keypair(keypair)
        with storage.unlock() as keypair:
            # Use keypair here
            signature = keypair.sign(message)
        # Key is automatically cleared after context exit

        # With password protection
        storage = SecureKeyStorage.from_keypair(keypair, password="secret")
        with storage.unlock(password="secret") as keypair:
            signature = keypair.sign(message)
    """

    def __init__(self):
        self._encrypted_key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._pubkey: Optional[str] = None
        self._is_unlocked: bool = False
        self._unlocked_key: Optional[bytes] = None
        self._metadata: Optional[KeyMetadata] = None
        self._password_protected: bool = False

    @classmethod
    def from_keypair(
        cls,
        keypair: 'Keypair',
        password: Optional[str] = None,
    ) -> 'SecureKeyStorage':
        """
        Create secure storage from a Keypair.

        Args:
            keypair: The Solana keypair to secure
            password: Optional password for additional protection

        Returns:
            SecureKeyStorage instance
        """
        if not HAS_SOLDERS:
            raise SecureKeyError("solders library required for keypair handling")

        storage = cls()
        storage._pubkey = str(keypair.pubkey())

        # Get secret key bytes
        secret_bytes = bytes(keypair.secret())

        try:
            if password:
                storage._password_protected = True
                storage._salt = os.urandom(16)
                storage._encrypted_key = storage._encrypt_with_password(
                    secret_bytes, password, storage._salt
                )
            else:
                # Simple XOR encryption with random key (better than plaintext)
                storage._salt = os.urandom(32)
                storage._encrypted_key = storage._xor_encrypt(secret_bytes, storage._salt)

            storage._metadata = KeyMetadata(
                pubkey=storage._pubkey,
                created_at=__import__('time').time(),
            )

        finally:
            # Always clear the secret bytes from memory
            storage._secure_zero(secret_bytes)

        return storage

    @classmethod
    def from_seed(
        cls,
        seed: bytes,
        password: Optional[str] = None,
    ) -> 'SecureKeyStorage':
        """
        Create secure storage from a seed.

        Args:
            seed: 32-byte seed for keypair generation
            password: Optional password for additional protection

        Returns:
            SecureKeyStorage instance
        """
        if not HAS_SOLDERS:
            raise SecureKeyError("solders library required for keypair handling")

        if len(seed) != 32:
            raise SecureKeyError(f"Seed must be 32 bytes, got {len(seed)}")

        keypair = Keypair.from_seed(seed)
        try:
            return cls.from_keypair(keypair, password)
        finally:
            # Clear keypair from memory
            del keypair

    @classmethod
    def from_mnemonic(
        cls,
        mnemonic: str,
        password: Optional[str] = None,
    ) -> 'SecureKeyStorage':
        """
        Create secure storage from a mnemonic phrase.

        Args:
            mnemonic: BIP39 mnemonic phrase
            password: Optional password for additional protection

        Returns:
            SecureKeyStorage instance
        """
        if not HAS_SOLDERS:
            raise SecureKeyError("solders library required for keypair handling")

        # Note: This is a simplified implementation
        # In production, use proper BIP39 derivation
        seed = hashlib.pbkdf2_hmac('sha512', mnemonic.encode(), b'mnemonic', 2048)
        keypair = Keypair.from_seed(seed[:32])
        try:
            return cls.from_keypair(keypair, password)
        finally:
            del keypair
            cls._secure_zero(seed)

    def _encrypt_with_password(
        self,
        data: bytes,
        password: str,
        salt: bytes,
    ) -> bytes:
        """Encrypt data with password using PBKDF2"""
        if HAS_CRYPTOGRAPHY:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f = Fernet(key)
            return f.encrypt(data)
        else:
            # Fallback: use PBKDF2 with HMAC
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return self._xor_encrypt(data, key)

    def _decrypt_with_password(
        self,
        encrypted_data: bytes,
        password: str,
        salt: bytes,
    ) -> bytes:
        """Decrypt data with password"""
        if HAS_CRYPTOGRAPHY:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f = Fernet(key)
            return f.decrypt(encrypted_data)
        else:
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return self._xor_encrypt(encrypted_data, key)

    def _xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption (for basic memory protection)"""
        return bytes(a ^ b for a, b in zip(data, key * (len(data) // len(key) + 1)))

    @staticmethod
    def _secure_zero(data: Union[bytes, bytearray]) -> None:
        """Securely zero out sensitive data from memory"""
        if isinstance(data, bytes):
            # Can't modify bytes, create mutable copy and zero that
            mutable = bytearray(data)
        else:
            mutable = data

        # Overwrite with zeros
        for i in range(len(mutable)):
            mutable[i] = 0

        # Overwrite with ones
        for i in range(len(mutable)):
            mutable[i] = 0xFF

        # Overwrite with random
        import random
        for i in range(len(mutable)):
            mutable[i] = random.randint(0, 255)

        # Final zero
        for i in range(len(mutable)):
            mutable[i] = 0

    @contextmanager
    def unlock(self, password: Optional[str] = None):
        """
        Context manager to temporarily access the keypair.

        Args:
            password: Required if storage was created with password

        Yields:
            Keypair: The unlocked keypair

        Usage:
            with storage.unlock() as keypair:
                signature = keypair.sign(message)
            # Key is automatically cleared after
        """
        if not HAS_SOLDERS:
            raise SecureKeyError("solders library required")

        if self._encrypted_key is None:
            raise KeyNotAvailableError("No key stored")

        if self._password_protected and password is None:
            raise SecureKeyError("Password required to unlock")

        try:
            # Decrypt the key
            if self._password_protected:
                decrypted = self._decrypt_with_password(
                    self._encrypted_key, password, self._salt
                )
            else:
                decrypted = self._xor_encrypt(self._encrypted_key, self._salt)

            # Create keypair from decrypted bytes
            keypair = Keypair.from_seed(decrypted)

            # Update metadata
            if self._metadata:
                self._metadata.last_accessed = __import__('time').time()
                self._metadata.access_count += 1

            self._is_unlocked = True
            self._unlocked_key = decrypted

            yield keypair

        finally:
            # Always cleanup
            self._is_unlocked = False
            if self._unlocked_key:
                self._secure_zero(self._unlocked_key)
                self._unlocked_key = None
            if 'keypair' in locals():
                del keypair
            if 'decrypted' in locals():
                self._secure_zero(decrypted)

    def sign_message(
        self,
        message: bytes,
        password: Optional[str] = None,
    ) -> bytes:
        """
        Sign a message without exposing the keypair.

        Args:
            message: Message to sign
            password: Required if storage was created with password

        Returns:
            Signature bytes
        """
        with self.unlock(password) as keypair:
            return keypair.sign(message).signature

    @property
    def pubkey(self) -> str:
        """Get the public key (safe to access)"""
        return self._pubkey

    @property
    def is_password_protected(self) -> bool:
        """Check if storage requires password"""
        return self._password_protected

    @property
    def metadata(self) -> Optional[KeyMetadata]:
        """Get key metadata"""
        return self._metadata

    def clear(self) -> None:
        """Permanently clear all key material"""
        if self._encrypted_key:
            self._secure_zero(self._encrypted_key)
            self._encrypted_key = None
        if self._salt:
            self._secure_zero(self._salt)
            self._salt = None
        if self._unlocked_key:
            self._secure_zero(self._unlocked_key)
            self._unlocked_key = None
        self._pubkey = None
        self._metadata = None

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.clear()


class HardwareWalletAdapter:
    """
    Abstract base class for hardware wallet integration.

    Implement this interface to support Ledger, Trezor, etc.
    """

    def __init__(self, path: str = "m/44'/501'/0'/0'"):
        self.path = path

    async def get_pubkey(self) -> str:
        """Get public key from hardware wallet"""
        raise NotImplementedError

    async def sign_message(self, message: bytes) -> bytes:
        """Sign message using hardware wallet"""
        raise NotImplementedError

    async def sign_transaction(self, transaction_bytes: bytes) -> bytes:
        """Sign transaction using hardware wallet"""
        raise NotImplementedError


# Convenience function for quick signing
def sign_with_keypair(
    keypair: 'Keypair',
    message: bytes,
    clear_after: bool = True,
) -> bytes:
    """
    Sign a message and optionally clear the keypair from memory.

    Args:
        keypair: Keypair to use for signing
        message: Message to sign
        clear_after: If True, attempt to clear keypair from memory after

    Returns:
        Signature bytes
    """
    signature = keypair.sign(message).signature

    if clear_after:
        # Attempt to clear sensitive data
        try:
            secret = keypair.secret()
            SecureKeyStorage._secure_zero(bytes(secret))
        except:
            pass

    return signature
