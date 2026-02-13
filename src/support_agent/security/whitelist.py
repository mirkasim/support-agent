"""Contact whitelist management."""

from pathlib import Path
from typing import Set
import yaml


class ContactWhitelist:
    """Manages whitelisted contacts for authorization.

    Only contacts in the whitelist can interact with the agent.
    """

    def __init__(self, contacts_file: Path):
        """Initialize whitelist from file.

        Args:
            contacts_file: Path to contacts.yaml file
        """
        self.contacts_file = contacts_file
        self._contacts: Set[str] = set()
        self._load_contacts()

    def _load_contacts(self) -> None:
        """Load contacts from YAML file."""
        if not self.contacts_file.exists():
            print(f"Warning: Contacts file not found: {self.contacts_file}")
            print("Creating empty contacts file...")
            self.contacts_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_contacts()
            return

        try:
            with open(self.contacts_file) as f:
                data = yaml.safe_load(f) or {}
                contacts_list = data.get("whitelisted_contacts", [])
                self._contacts = set(contacts_list)
                print(f"Loaded {len(self._contacts)} whitelisted contacts")
        except Exception as e:
            print(f"Error loading contacts: {e}")
            self._contacts = set()

    def is_whitelisted(self, contact_id: str) -> bool:
        """Check if contact is whitelisted.

        Args:
            contact_id: Contact identifier (phone number, user ID, etc.)

        Returns:
            True if contact is whitelisted, False otherwise
        """
        # Normalize contact ID (remove whitespace, etc.)
        normalized = contact_id.strip()

        # Check exact match first
        if normalized in self._contacts:
            return True

        # For phone numbers, try variations with/without + prefix
        if normalized.startswith('+'):
            # Try without +
            if normalized[1:] in self._contacts:
                return True
        else:
            # Try with +
            if f'+{normalized}' in self._contacts:
                return True

        return False

    def add_contact(self, contact_id: str) -> None:
        """Add contact to whitelist.

        Args:
            contact_id: Contact identifier to add (phone number or WhatsApp LID)
        """
        normalized = contact_id.strip()

        # Handle different identifier formats
        if '@lid' in normalized or '@s.whatsapp.net' in normalized or '@g.us' in normalized:
            # Keep WhatsApp identifiers as-is (LID or standard JID format)
            print(f"Adding WhatsApp identifier: {normalized}")
        elif normalized and normalized[0].isdigit():
            # Phone number without +, add it
            normalized = f'+{normalized}'
            print(f"Adding phone number: {normalized}")

        # Check if already exists (with variations)
        if self.is_whitelisted(normalized):
            print(f"Contact already whitelisted: {normalized}")
            return

        self._contacts.add(normalized)
        self._save_contacts()
        print(f"✅ Added contact to whitelist: {normalized}")

    def remove_contact(self, contact_id: str) -> None:
        """Remove contact from whitelist.

        Args:
            contact_id: Contact identifier to remove
        """
        normalized = contact_id.strip()
        if normalized not in self._contacts:
            print(f"Contact not in whitelist: {normalized}")
            return

        self._contacts.remove(normalized)
        self._save_contacts()
        print(f"Removed contact from whitelist: {normalized}")

    def _save_contacts(self) -> None:
        """Save contacts to YAML file."""
        try:
            with open(self.contacts_file, "w") as f:
                yaml.dump({"whitelisted_contacts": sorted(list(self._contacts))}, f)
        except Exception as e:
            print(f"Error saving contacts: {e}")

    def get_all_contacts(self) -> list[str]:
        """Get all whitelisted contacts.

        Returns:
            List of whitelisted contact IDs
        """
        return sorted(list(self._contacts))

    def reload(self) -> None:
        """Reload contacts from file."""
        self._load_contacts()

    def __len__(self) -> int:
        """Get number of whitelisted contacts."""
        return len(self._contacts)

    def __contains__(self, contact_id: str) -> bool:
        """Check if contact is whitelisted (supports 'in' operator)."""
        return self.is_whitelisted(contact_id)
