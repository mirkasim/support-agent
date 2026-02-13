#!/usr/bin/env python3
"""Setup script for WhatsApp QR code linking."""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os


async def setup_whatsapp():
    """Display QR code for WhatsApp linking."""
    load_dotenv()

    bridge_url = os.getenv("BRIDGE_URL", "http://localhost:3000")

    print("=" * 60)
    print("WhatsApp Setup - QR Code Linking")
    print("=" * 60)
    print()

    async with aiohttp.ClientSession() as session:
        # Check bridge status
        print(f"Connecting to bridge at {bridge_url}...")
        try:
            async with session.get(f"{bridge_url}/health") as response:
                if response.status != 200:
                    print(f"Error: Bridge is not running at {bridge_url}")
                    print("Please start the bridge first:")
                    print("  cd bridge && npm install && npm run dev")
                    return
        except Exception as e:
            print(f"Error connecting to bridge: {e}")
            print("Please start the bridge first:")
            print("  cd bridge && npm install && npm run dev")
            return

        print("Bridge is running")
        print()

        # Get QR code
        print("Fetching QR code...")
        async with session.get(f"{bridge_url}/api/qr") as response:
            data = await response.json()

            if "qr" in data:
                qr_data_url = data["qr"]
                print()
                print("=" * 60)
                print("QR Code Ready!")
                print("=" * 60)
                print()
                print("Option 1: Open this URL in your browser to see the QR code:")
                print(qr_data_url[:100] + "...")
                print()
                print("Option 2: Check the bridge terminal - QR code is printed there")
                print()
                print("Scan this QR code with WhatsApp:")
                print("1. Open WhatsApp on your phone")
                print("2. Go to Settings > Linked Devices")
                print("3. Tap 'Link a Device'")
                print("4. Scan the QR code")
                print()
                print("Waiting for authentication...")

                # Wait for authentication
                for i in range(30):
                    await asyncio.sleep(2)
                    async with session.get(f"{bridge_url}/api/status") as status_response:
                        status = await status_response.json()
                        if status.get("authenticated"):
                            print()
                            print("=" * 60)
                            print("Success! WhatsApp is now linked!")
                            print("=" * 60)
                            return

                print()
                print("Timeout - QR code may have expired")
                print("Please run this script again")

            elif "message" in data:
                print(data["message"])
                if "Already authenticated" in data["message"]:
                    print()
                    print("WhatsApp is already linked!")
            else:
                print("Could not get QR code")
                print("Response:", data)


if __name__ == "__main__":
    asyncio.run(setup_whatsapp())
