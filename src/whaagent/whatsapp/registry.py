"""WhatsApp phone number to tenant ID registry."""

from typing import Optional

from whaagent.config import WhatsAppTenantConfig


class WhatsAppRegistry:
    """Maps phone numbers to tenant IDs for WhatsApp message routing.

    This registry provides bidirectional lookup between phone numbers and
    tenant IDs, initialized from configuration data on startup.
    """

    def __init__(self, tenants: list[WhatsAppTenantConfig]) -> None:
        """Initialize from config tenants.

        Args:
            tenants: List of WhatsApp tenant configurations.
        """
        self._phone_to_tenant: dict[str, str] = {}
        self._tenant_to_phone: dict[str, str] = {}

        # Initialize from tenant configurations
        for tenant in tenants:
            if tenant.phone and tenant.id:
                self.register(tenant.id, tenant.phone)

    def register(self, tenant_id: str, phone: str) -> None:
        """Register a phone→tenant mapping.

        Args:
            tenant_id: The tenant identifier.
            phone: The WhatsApp phone number.
        """
        # Remove any existing mappings for this phone or tenant
        existing_tenant = self._phone_to_tenant.get(phone)
        existing_phone = self._tenant_to_phone.get(tenant_id)

        if existing_tenant:
            del self._tenant_to_phone[existing_tenant]
        if existing_phone:
            del self._phone_to_tenant[existing_phone]

        # Add new mapping
        self._phone_to_tenant[phone] = tenant_id
        self._tenant_to_phone[tenant_id] = phone

    def lookup_by_phone(self, phone: str) -> Optional[str]:
        """Look up tenant_id by phone number.

        Args:
            phone: The WhatsApp phone number to look up.

        Returns:
            The tenant ID if found, None otherwise.
        """
        return self._phone_to_tenant.get(phone)

    def lookup_by_tenant(self, tenant_id: str) -> Optional[str]:
        """Look up phone by tenant_id.

        Args:
            tenant_id: The tenant identifier to look up.

        Returns:
            The phone number if found, None otherwise.
        """
        return self._tenant_to_phone.get(tenant_id)

    def get_all_tenants(self) -> list[str]:
        """Get all registered tenant IDs.

        Returns:
            List of all tenant IDs.
        """
        return list(self._tenant_to_phone.keys())

    def get_all_phones(self) -> list[str]:
        """Get all registered phone numbers.

        Returns:
            List of all phone numbers.
        """
        return list(self._phone_to_tenant.keys())
