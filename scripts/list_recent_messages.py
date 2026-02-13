#!/usr/bin/env python3
"""List recent message senders to help whitelist them."""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os


async def list_recent_senders():
    """List recent message senders from bridge logs."""
    load_dotenv()

    bridge_url = os.getenv("BRIDGE_URL", "http://localhost:3000")

    print("=" * 60)
    print("Recent WhatsApp Messages")
    print("=" * 60)
    print()
    print("This will show the last few message senders.")
    print("Copy the sender ID to whitelist them.")
    print()

    # Note: This is a placeholder - actual implementation would need
    # the bridge to expose an endpoint with recent messages
    print("To see recent message senders:")
    print("1. Check the bridge terminal logs for 'Received message from'")
    print("2. The sender ID will be shown (e.g., '12345@lid' or '+1234567890')")
    print("3. Use that exact ID to whitelist:")
    print()
    print("   python scripts/add_contact.py '<sender_id>'")
    print()
    print("Examples:")
    print("   python scripts/add_contact.py '125438848454740@lid'")
    print("   python scripts/add_contact.py '+1234567890'")
    print()


if __name__ == "__main__":
    asyncio.run(list_recent_senders())
