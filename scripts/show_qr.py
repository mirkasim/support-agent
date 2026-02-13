#!/usr/bin/env python3
"""Generate and display QR code image for WhatsApp linking."""

import asyncio
import aiohttp
import base64
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv
import os


async def show_qr_code():
    """Fetch QR code, save as image, and open it."""
    load_dotenv()

    bridge_url = os.getenv("BRIDGE_URL", "http://localhost:3000")
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    qr_image_path = output_dir / "whatsapp_qr.png"

    print("=" * 60)
    print("WhatsApp QR Code Generator")
    print("=" * 60)
    print()

    async with aiohttp.ClientSession() as session:
        # Check bridge status
        print(f"Connecting to bridge at {bridge_url}...")
        try:
            async with session.get(f"{bridge_url}/health") as response:
                if response.status != 200:
                    print(f"❌ Error: Bridge is not running at {bridge_url}")
                    print("Please start the bridge first:")
                    print("  cd bridge && npm run dev")
                    return False
        except Exception as e:
            print(f"❌ Error connecting to bridge: {e}")
            print("Please start the bridge first:")
            print("  cd bridge && npm run dev")
            return False

        print("✅ Bridge is running")
        print()

        # Get QR code
        print("Fetching QR code...")
        try:
            async with session.get(f"{bridge_url}/api/qr") as response:
                data = await response.json()

                if "qr" in data:
                    qr_data_url = data["qr"]

                    # Extract base64 data from data URL
                    # Format: data:image/png;base64,iVBORw0KGgo...
                    if qr_data_url.startswith("data:image/png;base64,"):
                        base64_data = qr_data_url.split(",", 1)[1]

                        # Decode and save as PNG
                        image_data = base64.b64decode(base64_data)

                        with open(qr_image_path, "wb") as f:
                            f.write(image_data)

                        print("✅ QR code saved to:", qr_image_path)
                        print()
                        print("=" * 60)
                        print("Opening QR Code Image...")
                        print("=" * 60)
                        print()
                        print("Scan this QR code with WhatsApp:")
                        print("1. Open WhatsApp on your phone")
                        print("2. Go to Settings > Linked Devices")
                        print("3. Tap 'Link a Device'")
                        print("4. Scan the QR code from the opened image")
                        print()

                        # Open the image with default viewer
                        try:
                            if sys.platform == "darwin":  # macOS
                                subprocess.run(["open", str(qr_image_path)])
                            elif sys.platform == "win32":  # Windows
                                subprocess.run(["start", str(qr_image_path)], shell=True)
                            else:  # Linux
                                subprocess.run(["xdg-open", str(qr_image_path)])

                            print("✅ QR code image opened!")
                            print()
                        except Exception as e:
                            print(f"⚠️ Could not auto-open image: {e}")
                            print(f"Please manually open: {qr_image_path}")
                            print()

                        # Wait for authentication
                        print("Waiting for authentication (checking every 3 seconds)...")
                        print("Press Ctrl+C to stop")
                        print()

                        for i in range(40):  # Check for 2 minutes
                            await asyncio.sleep(3)

                            try:
                                async with session.get(f"{bridge_url}/api/status") as status_response:
                                    status = await status_response.json()
                                    if status.get("authenticated"):
                                        print()
                                        print("=" * 60)
                                        print("🎉 Success! WhatsApp is now linked!")
                                        print("=" * 60)
                                        print()
                                        print("You can now:")
                                        print("1. Add contacts: python scripts/add_contact.py +1234567890")
                                        print("2. Start the agent: python -m support_agent.main")
                                        return True
                                    else:
                                        # Show progress indicator
                                        dots = "." * ((i % 3) + 1)
                                        print(f"\rWaiting{dots}   ", end="", flush=True)
                            except:
                                pass

                        print()
                        print("⏱️ Timeout - QR code may have expired")
                        print("Please run this script again to get a new QR code")
                        return False

                    else:
                        print("❌ Unexpected QR code format")
                        return False

                elif "message" in data:
                    print(data["message"])
                    if "Already authenticated" in data["message"]:
                        print()
                        print("✅ WhatsApp is already linked!")
                        print()
                        print("You can now:")
                        print("1. Add contacts: python scripts/add_contact.py +1234567890")
                        print("2. Start the agent: python -m support_agent.main")
                        return True
                    return False
                else:
                    print("❌ Could not get QR code")
                    print("Response:", data)
                    return False

        except Exception as e:
            print(f"❌ Error fetching QR code: {e}")
            return False


if __name__ == "__main__":
    try:
        result = asyncio.run(show_qr_code())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelled by user")
        sys.exit(1)
