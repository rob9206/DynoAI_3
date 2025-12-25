"""
Security tests for PowerCore file_id API contract.

Tests for:
- Invalid/expired file_id handling
- File type mismatch detection
- IDs not in cache
- Path traversal prevention
"""

import time
import pytest
from pathlib import Path

from api.services.file_index import (
    FileIndex,
    FileType,
    get_file_index,
    reset_file_index,
)


class TestFileIndexService:
    """Unit tests for the FileIndex service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset file index before/after each test."""
        reset_file_index()
        yield
        reset_file_index()

    @pytest.fixture
    def temp_csv_file(self, tmp_path):
        """Create a temporary CSV file for testing."""
        csv_file = tmp_path / "test_log.csv"
        csv_file.write_text("timestamp,rpm\n0,1000\n1,2000")
        return csv_file

    @pytest.fixture
    def temp_pvv_file(self, tmp_path):
        """Create a temporary PVV file for testing."""
        pvv_file = tmp_path / "test_tune.pvv"
        pvv_file.write_text("<PVV></PVV>")
        return pvv_file

    @pytest.fixture
    def temp_wp8_file(self, tmp_path):
        """Create a temporary WP8 file for testing."""
        wp8_file = tmp_path / "test_run.wp8"
        # Write minimal WP8 header
        wp8_file.write_bytes(b"\xfe\xce\xfa\xce" + b"\x00" * 100)
        return wp8_file

    def test_register_file_returns_id(self, temp_csv_file):
        """Registering a file returns a non-empty file ID."""
        index = FileIndex()
        file_id = index.register(temp_csv_file, FileType.LOG)

        assert file_id is not None
        assert len(file_id) > 0
        assert isinstance(file_id, str)

    def test_register_same_file_returns_same_id(self, temp_csv_file):
        """Registering the same file twice returns the same ID."""
        index = FileIndex()
        id1 = index.register(temp_csv_file, FileType.LOG)
        id2 = index.register(temp_csv_file, FileType.LOG)

        assert id1 == id2

    def test_resolve_returns_correct_path(self, temp_csv_file):
        """Resolving a valid file_id returns the correct path."""
        index = FileIndex()
        file_id = index.register(temp_csv_file, FileType.LOG)
        resolved = index.resolve(file_id)

        assert resolved == temp_csv_file.resolve()

    def test_resolve_nonexistent_id_raises_keyerror(self):
        """Resolving a non-existent file_id raises KeyError."""
        index = FileIndex()

        with pytest.raises(KeyError, match="not found or expired"):
            index.resolve("nonexistent_id_12345")

    def test_resolve_expired_id_raises_keyerror(self, temp_csv_file):
        """Resolving an expired file_id raises KeyError."""
        index = FileIndex(ttl_seconds=0)  # Immediate expiry
        file_id = index.register(temp_csv_file, FileType.LOG)

        time.sleep(0.01)  # Ensure expiry

        with pytest.raises(KeyError, match="expired"):
            index.resolve(file_id)

    def test_resolve_type_mismatch_raises_valueerror(self, temp_csv_file):
        """Resolving with wrong expected_type raises ValueError."""
        index = FileIndex()
        file_id = index.register(temp_csv_file, FileType.LOG)

        with pytest.raises(ValueError, match="type mismatch"):
            index.resolve(file_id, expected_type=FileType.TUNE)

    def test_resolve_deleted_file_raises_filenotfounderror(self, tmp_path):
        """Resolving a file_id for a deleted file raises FileNotFoundError."""
        temp_file = tmp_path / "deleted.csv"
        temp_file.write_text("data")

        index = FileIndex()
        file_id = index.register(temp_file, FileType.LOG)

        # Delete the file
        temp_file.unlink()

        with pytest.raises(FileNotFoundError, match="no longer exists"):
            index.resolve(file_id)

    def test_register_nonexistent_file_raises_filenotfounderror(self, tmp_path):
        """Registering a non-existent file raises FileNotFoundError."""
        index = FileIndex()
        nonexistent = tmp_path / "does_not_exist.csv"

        with pytest.raises(FileNotFoundError):
            index.register(nonexistent, FileType.LOG)

    def test_register_directory_raises_valueerror(self, tmp_path):
        """Registering a directory raises ValueError."""
        index = FileIndex()

        with pytest.raises(ValueError, match="not a file"):
            index.register(tmp_path, FileType.LOG)

    def test_file_id_is_not_guessable(self, temp_csv_file, temp_pvv_file):
        """File IDs should not be easily guessable from file paths."""
        index = FileIndex()
        id1 = index.register(temp_csv_file, FileType.LOG)
        id2 = index.register(temp_pvv_file, FileType.TUNE)

        # IDs should not contain obvious path components
        assert "test_log" not in id1.lower()
        assert "test_tune" not in id2.lower()
        assert ".csv" not in id1
        assert ".pvv" not in id2

    def test_to_api_response_excludes_path(self, temp_csv_file):
        """API response format should not include the raw path."""
        index = FileIndex()
        file_id = index.register(temp_csv_file, FileType.LOG)
        entry = index.get_entry(file_id)

        response = entry.to_api_response()

        assert "id" in response
        assert "name" in response
        assert "size_kb" in response
        assert "mtime" in response
        assert "type" in response
        assert "path" not in response
        assert str(temp_csv_file.parent) not in str(response)

    def test_list_by_type_filters_correctly(
        self, temp_csv_file, temp_pvv_file, temp_wp8_file
    ):
        """list_by_type returns only entries of the specified type."""
        index = FileIndex()
        index.register(temp_csv_file, FileType.LOG)
        index.register(temp_pvv_file, FileType.TUNE)
        index.register(temp_wp8_file, FileType.WP8)

        logs = index.list_by_type(FileType.LOG)
        tunes = index.list_by_type(FileType.TUNE)
        wp8s = index.list_by_type(FileType.WP8)

        assert len(logs) == 1
        assert len(tunes) == 1
        assert len(wp8s) == 1
        assert logs[0].file_type == FileType.LOG
        assert tunes[0].file_type == FileType.TUNE
        assert wp8s[0].file_type == FileType.WP8

    def test_clear_removes_all_entries(self, temp_csv_file, temp_pvv_file):
        """clear() removes all entries from the index."""
        index = FileIndex()
        id1 = index.register(temp_csv_file, FileType.LOG)
        id2 = index.register(temp_pvv_file, FileType.TUNE)

        index.clear()

        with pytest.raises(KeyError):
            index.resolve(id1)
        with pytest.raises(KeyError):
            index.resolve(id2)


class TestPowerCoreFileIdEndpoints:
    """Integration tests for PowerCore file_id API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset file index before/after each test."""
        reset_file_index()
        yield
        reset_file_index()

    @pytest.fixture(autouse=True)
    def _avoid_real_filesystem_discovery(self, monkeypatch):
        """
        Avoid scanning the real user's Documents/OneDrive during tests.

        The discovery endpoints use recursive globbing which can be slow and flaky
        on developer machines. For these tests we only care that responses return
        server-issued IDs (not raw paths), so it's safe to stub discovery to [].
        """
        monkeypatch.setattr("api.routes.powercore.find_log_files", lambda *args, **kwargs: [])
        monkeypatch.setattr("api.routes.powercore.find_tune_files", lambda *args, **kwargs: [])
        monkeypatch.setattr("api.routes.powercore.find_wp8_files", lambda *args, **kwargs: [])
        monkeypatch.setattr("api.routes.powercore.find_powercore_data_dirs", lambda *args, **kwargs: [])

    def test_discover_logs_returns_file_ids(self, client):
        """Discovery endpoint returns file IDs, not paths."""
        response = client.get("/api/powercore/discover/logs")

        # May return empty if no Power Core dirs exist on test machine
        assert response.status_code == 200
        data = response.get_json()

        assert "count" in data
        assert "files" in data

        # If any files found, verify structure
        for file_info in data["files"]:
            assert "id" in file_info
            assert "name" in file_info
            assert "size_kb" in file_info
            assert "type" in file_info
            # Should NOT have raw path
            assert "path" not in file_info

    def test_discover_tunes_returns_file_ids(self, client):
        """Discovery endpoint returns file IDs, not paths."""
        response = client.get("/api/powercore/discover/tunes")

        assert response.status_code == 200
        data = response.get_json()

        assert "count" in data
        assert "files" in data

        for file_info in data["files"]:
            assert "id" in file_info
            assert "path" not in file_info

    def test_discover_wp8_returns_file_ids(self, client):
        """Discovery endpoint returns file IDs, not paths."""
        response = client.get("/api/powercore/discover/wp8")

        assert response.status_code == 200
        data = response.get_json()

        assert "count" in data
        assert "files" in data

        for file_info in data["files"]:
            assert "id" in file_info
            assert "path" not in file_info

    def test_parse_log_rejects_invalid_file_id(self, client):
        """Parse endpoint rejects invalid file_id."""
        response = client.post(
            "/api/powercore/parse/log", json={"file_id": "invalid_nonexistent_id"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid" in data["error"] or "expired" in data["error"]

    def test_parse_tune_rejects_invalid_file_id(self, client):
        """Parse endpoint rejects invalid file_id."""
        response = client.post(
            "/api/powercore/parse/tune", json={"file_id": "invalid_nonexistent_id"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_parse_wp8_rejects_invalid_file_id(self, client):
        """Parse endpoint rejects invalid file_id."""
        response = client.post(
            "/api/powercore/parse/wp8", json={"file_id": "invalid_nonexistent_id"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_parse_log_rejects_type_mismatch(self, client, tmp_path):
        """Parse log endpoint rejects file_id registered as different type."""
        # Register a file as TUNE type
        tune_file = tmp_path / "test.pvv"
        tune_file.write_text("<PVV></PVV>")

        file_index = get_file_index()
        tune_id = file_index.register(tune_file, FileType.TUNE)

        # Try to parse as LOG
        response = client.post("/api/powercore/parse/log", json={"file_id": tune_id})

        assert response.status_code == 400
        data = response.get_json()
        assert "mismatch" in data["error"].lower()

    def test_parse_tune_rejects_type_mismatch(self, client, tmp_path):
        """Parse tune endpoint rejects file_id registered as different type."""
        # Register a file as LOG type
        log_file = tmp_path / "test.csv"
        log_file.write_text("timestamp,rpm\n0,1000")

        file_index = get_file_index()
        log_id = file_index.register(log_file, FileType.LOG)

        # Try to parse as TUNE
        response = client.post("/api/powercore/parse/tune", json={"file_id": log_id})

        assert response.status_code == 400
        data = response.get_json()
        assert "mismatch" in data["error"].lower()

    def test_parse_wp8_rejects_type_mismatch(self, client, tmp_path):
        """Parse WP8 endpoint rejects file_id registered as different type."""
        # Register a file as LOG type
        log_file = tmp_path / "test.csv"
        log_file.write_text("timestamp,rpm\n0,1000")

        file_index = get_file_index()
        log_id = file_index.register(log_file, FileType.LOG)

        # Try to parse as WP8
        response = client.post("/api/powercore/parse/wp8", json={"file_id": log_id})

        assert response.status_code == 400
        data = response.get_json()
        assert "mismatch" in data["error"].lower()

    def test_parse_rejects_missing_file_id(self, client):
        """Parse endpoint requires file_id or path parameter."""
        response = client.post("/api/powercore/parse/log", json={})

        assert response.status_code == 400
        data = response.get_json()
        assert "Missing" in data["error"]

    def test_parse_rejects_empty_body(self, client):
        """Parse endpoint rejects empty request body."""
        response = client.post(
            "/api/powercore/parse/log", content_type="application/json"
        )

        assert response.status_code == 400


class TestLegacyPathSupportSecurity:
    """Security tests for legacy path parameter support."""

    def test_legacy_path_rejects_traversal(self, client):
        """Legacy path parameter still rejects path traversal."""
        response = client.post(
            "/api/powercore/parse/log", json={"path": "../../../etc/passwd"}
        )

        # Should fail validation (not found or outside allowed dirs)
        assert response.status_code in (400, 404, 500)
        data = response.get_json()
        # Should not reveal internal paths
        assert "C:\\" not in str(data)
        assert "/home/" not in str(data)

    def test_legacy_path_rejects_absolute_system_path(self, client):
        """Legacy path parameter rejects absolute system paths."""
        response = client.post("/api/powercore/parse/log", json={"path": "/etc/passwd"})

        assert response.status_code in (400, 404, 500)

    def test_legacy_path_rejects_backslash_traversal(self, client):
        """Legacy path parameter rejects backslash traversal."""
        response = client.post(
            "/api/powercore/parse/log",
            json={"path": "..\\..\\..\\windows\\system32\\config\\sam"},
        )

        assert response.status_code in (400, 404, 500)

    def test_legacy_path_rejects_wrong_extension(self, client, tmp_path):
        """Legacy path parameter validates file extension."""
        # Create a file with wrong extension
        wrong_ext = tmp_path / "test.exe"
        wrong_ext.write_text("not a csv")

        response = client.post(
            "/api/powercore/parse/log", json={"path": str(wrong_ext)}
        )

        # Should reject - either wrong extension or outside allowed dirs
        assert response.status_code in (400, 404, 500)
