"""
Address Lookup Table support for Solana transactions.

This module provides functionality to fetch and use Address Lookup Tables (ALT)
to reduce transaction size by storing frequently used addresses in a lookup table.
"""

from typing import List, Optional
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment


@dataclass
class AddressLookupTableAccount:
    """Represents an address lookup table account."""
    key: Pubkey
    addresses: List[Pubkey]


async def fetch_address_lookup_table_account(
    rpc: AsyncClient,
    lookup_table_address: Pubkey,
    commitment: Optional[Commitment] = None,
) -> Optional[AddressLookupTableAccount]:
    """
    Fetch an address lookup table account from the blockchain.

    Args:
        rpc: Solana RPC client
        lookup_table_address: The address of the lookup table
        commitment: Commitment level for the query

    Returns:
        AddressLookupTableAccount if found, None otherwise
    """
    try:
        response = await rpc.get_account_info(
            lookup_table_address,
            commitment=commitment or Commitment("confirmed"),
        )

        if response.value is None:
            return None

        # Parse the lookup table data
        # First 56 bytes: header (authority: 32 bytes, deactivation_slot: 8 bytes, last_extended_slot: 8 bytes, last_extended_slot_start_index: 1 byte, padding: 7 bytes)
        # Remaining bytes: addresses (each 32 bytes)
        data = response.value.data

        if len(data) < 56:
            return None

        # Skip header and parse addresses
        addresses_data = data[56:]
        addresses = []

        # Each address is 32 bytes
        for i in range(0, len(addresses_data), 32):
            if i + 32 <= len(addresses_data):
                addr_bytes = addresses_data[i:i+32]
                addresses.append(Pubkey.from_bytes(addr_bytes))

        return AddressLookupTableAccount(
            key=lookup_table_address,
            addresses=addresses,
        )

    except Exception as e:
        raise RuntimeError(f"Failed to fetch address lookup table: {e}")


class AddressLookupTableCache:
    """Cache for address lookup tables to avoid repeated RPC calls."""

    def __init__(self):
        self._cache: dict[str, AddressLookupTableAccount] = {}

    async def get_lookup_table(
        self,
        rpc: AsyncClient,
        lookup_table_address: Pubkey,
    ) -> Optional[AddressLookupTableAccount]:
        """Get lookup table from cache or fetch from RPC."""
        key = str(lookup_table_address)

        if key in self._cache:
            return self._cache[key]

        lookup_table = await fetch_address_lookup_table_account(rpc, lookup_table_address)

        if lookup_table:
            self._cache[key] = lookup_table

        return lookup_table

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def remove(self, lookup_table_address: Pubkey) -> None:
        """Remove a specific lookup table from cache."""
        key = str(lookup_table_address)
        self._cache.pop(key, None)
