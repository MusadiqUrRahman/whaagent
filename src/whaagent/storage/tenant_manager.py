"""Tenant-scoped database management."""

import logging
from pathlib import Path
from typing import Dict

from whaagent.storage.database import Database

logger = logging.getLogger(__name__)


class TenantManager:
    """Manages tenant-scoped database connections.

    Each tenant gets its own SQLite database file for complete isolation.
    Connections are cached per tenant.
    """

    def __init__(self, base_path: Path | str | None = None) -> None:
        """Initialize the tenant manager.

        Args:
            base_path: Base directory for tenant databases.
                       Defaults to ~/.local/share/whaagent
        """
        if base_path is None:
            base_path = Path.home() / ".local" / "share" / "whaagent"
        self._base_path = Path(base_path)
        self._databases: Dict[str, Database] = {}

    def get_database(self, tenant_id: str) -> Database:
        """Get or create a database connection for a tenant.

        Args:
            tenant_id: Unique identifier for the tenant.

        Returns:
            Database instance for the tenant.
        """
        if tenant_id not in self._databases:
            db_path = self._get_tenant_db_path(tenant_id)
            self._databases[tenant_id] = Database(db_path)
            logger.info("Created database for tenant %s: %s", tenant_id, db_path)
        return self._databases[tenant_id]

    def _get_tenant_db_path(self, tenant_id: str) -> Path:
        """Get the database path for a tenant.

        Sanitizes tenant_id to prevent path traversal.
        """
        # First replace ../ sequences with __ (two underscores each)
        safe_id = tenant_id.replace("../", "__")
        # Replace other slashes with underscores
        safe_id = safe_id.replace("/", "_")
        # Remove dots entirely (except those that were part of ../)
        safe_id = safe_id.replace(".", "")
        # Then replace any remaining special chars with underscores
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in safe_id)
        return self._base_path / "tenants" / safe_id / "whaagent.db"

    def close_all(self) -> None:
        """Close all database connections."""
        for tenant_id, db in self._databases.items():
            try:
                db.close()
                logger.debug("Closed database for tenant %s", tenant_id)
            except Exception as e:
                logger.warning("Error closing database for tenant %s: %s", tenant_id, e)
        self._databases.clear()

    def list_tenants(self) -> list[str]:
        """List all tenants with databases."""
        tenants_dir = self._base_path / "tenants"
        if not tenants_dir.exists():
            return []
        return [d.name for d in tenants_dir.iterdir() if d.is_dir() and (d / "whaagent.db").exists()]
