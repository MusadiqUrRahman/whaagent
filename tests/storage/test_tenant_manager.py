"""Tests for tenant manager functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from whaagent.storage.tenant_manager import TenantManager


class TestTenantManager:
    """Test cases for TenantManager class."""

    def test_init_with_default_path(self) -> None:
        """Test initialization with default base path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            expected_path = Path(temp_dir) / ".local" / "share" / "whaagent"
            with patch("pathlib.Path.home", return_value=Path(temp_dir)):
                manager = TenantManager()
                assert manager._base_path == expected_path

    def test_init_with_custom_path(self) -> None:
        """Test initialization with custom base path."""
        custom_path = Path("/custom/path")
        manager = TenantManager(custom_path)
        assert manager._base_path == custom_path

    def test_get_database_creates_new_instance(self, tmp_path: Path) -> None:
        """Test that get_database creates a new Database instance."""
        manager = TenantManager(tmp_path)
        db1 = manager.get_database("tenant-1")
        db2 = manager.get_database("tenant-1")

        # Same instance should be returned for same tenant
        assert db1 is db2

    def test_get_database_different_tenants(self, tmp_path: Path) -> None:
        """Test that different tenants get different database instances."""
        manager = TenantManager(tmp_path)
        db1 = manager.get_database("tenant-1")
        db2 = manager.get_database("tenant-2")

        # Different instances for different tenants
        assert db1 is not db2

    def test_get_database_paths_are_isolated(self, tmp_path: Path) -> None:
        """Test that different tenants have different database paths."""
        manager = TenantManager(tmp_path)

        path1 = manager._get_tenant_db_path("tenant-1")
        path2 = manager._get_tenant_db_path("tenant-2")

        assert path1 != path2
        assert path1.parent.name == "tenant-1"
        assert path2.parent.name == "tenant-2"

    def test_data_isolation_between_tenants(self, tmp_path: Path) -> None:
        """Test that data is isolated between different tenants."""
        manager = TenantManager(tmp_path)

        # Get databases for different tenants
        db1 = manager.get_database("tenant-1")
        db2 = manager.get_database("tenant-2")

        # Write data to tenant-1
        conn1 = db1.connection
        conn1.execute(
            "INSERT INTO notes (id, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("note1", "tenant-1 data", 123.0, 123.0),
        )
        conn1.commit()

        # Verify tenant-2 cannot see the data
        conn2 = db2.connection
        cursor = conn2.execute("SELECT * FROM notes WHERE id = ?", ("note1",))
        result = cursor.fetchone()
        assert result is None

    def test_tenant_id_sanitization(self, tmp_path: Path) -> None:
        """Test that tenant IDs are sanitized to prevent path traversal."""
        manager = TenantManager(tmp_path)

        # Test various problematic tenant IDs
        test_cases = [
            ("../../etc/passwd", "____etc_passwd"),
            ("../../", "____"),
            ("tenant/with/slashes", "tenant_with_slashes"),
            ("tenant..with..dots", "tenantwithdots"),
            ("tenant-with-dashes", "tenant-with-dashes"),  # Valid
            ("tenant123", "tenant123"),  # Valid
            ("tenant_name", "tenant_name"),  # Valid
        ]

        for original, expected in test_cases:
            path = manager._get_tenant_db_path(original)
            assert path.parent.name == expected
            # Ensure no path traversal characters remain
            assert ".." not in str(path)
            assert "/" not in path.parent.name

    def test_connection_caching(self, tmp_path: Path) -> None:
        """Test that database connections are cached per tenant."""
        manager = TenantManager(tmp_path)

        # Get database multiple times for same tenant
        db1 = manager.get_database("tenant-1")
        db2 = manager.get_database("tenant-1")
        db3 = manager.get_database("tenant-1")

        # Should be the same instance
        assert db1 is db2 is db3
        assert len(manager._databases) == 1

    def test_close_all_connections(self, tmp_path: Path) -> None:
        """Test that close_all closes all database connections."""
        manager = TenantManager(tmp_path)

        # Get some databases
        manager.get_database("tenant-1")
        manager.get_database("tenant-2")

        assert len(manager._databases) == 2

        # Close all connections
        manager.close_all()

        # Should be empty
        assert len(manager._databases) == 0

    def test_list_tenants(self, tmp_path: Path) -> None:
        """Test listing tenants with existing databases."""
        manager = TenantManager(tmp_path)

        # Initially no tenants
        assert manager.list_tenants() == []

        # Create some databases by getting them
        manager.get_database("tenant-1")
        manager.get_database("tenant-2")

        # List tenants
        tenants = manager.list_tenants()
        assert len(tenants) == 2
        assert "tenant-1" in tenants
        assert "tenant-2" in tenants

    def test_list_tenants_no_database_files(self, tmp_path: Path) -> None:
        """Test listing tenants when directory exists but no database files."""
        # Create tenant directory without database files
        tenants_dir = tmp_path / "tenants"
        tenant_dir = tenants_dir / "empty-tenant"
        tenant_dir.mkdir(parents=True)

        manager = TenantManager(tmp_path)
        tenants = manager.list_tenants()

        # Should not include tenant without database file
        assert len(tenants) == 0

    def test_list_tenants_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test listing tenants when tenants directory doesn't exist."""
        manager = TenantManager(tmp_path)
        tenants = manager.list_tenants()

        # Should return empty list
        assert tenants == []
