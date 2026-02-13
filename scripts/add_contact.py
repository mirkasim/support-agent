#!/usr/bin/env python3
"""Add a contact to the whitelist."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from support_agent.security.whitelist import ContactWhitelist
from support_agent.config import load_settings


def add_contact(contact_id: str):
    """Add a contact to the whitelist.

    Args:
        contact_id: Contact ID (phone number in E.164 format, e.g., +1234567890)
    """
    settings = load_settings()
    contacts_file = settings.config_dir / "contacts.yaml"

    whitelist = ContactWhitelist(contacts_file)

    print(f"Adding contact: {contact_id}")
    whitelist.add_contact(contact_id)

    print()
    print("Current whitelisted contacts:")
    for contact in whitelist.get_all_contacts():
        print(f"  - {contact}")

    print()
    print("Done!")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("=" * 60)
        print("Add Contact to Whitelist")
        print("=" * 60)
        print()
        print("Usage: python add_contact.py <identifier>")
        print()
        print("The identifier can be:")
        print("  1. Phone number: +1234567890 (E.164 format)")
        print("  2. WhatsApp LID: 125438848454740@lid")
        print()
        print("Examples:")
        print("  python add_contact.py +1234567890")
        print("  python add_contact.py 125438848454740@lid")
        print()
        print("To find the correct identifier:")
        print("  1. Send a test message from WhatsApp")
        print("  2. Check the bridge logs for 'Received message from'")
        print("  3. Copy the sender ID shown and use it here")
        print()
        sys.exit(1)

    contact_id = sys.argv[1]
    add_contact(contact_id)


if __name__ == "__main__":
    main()
