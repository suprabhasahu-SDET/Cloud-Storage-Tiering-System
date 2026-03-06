"""
Cloud Storage Tiering System - Comprehensive Test Suite
Assignment: Cloud Storage Tiering API Testing

Test Strategy:
- Unit tests for individual API endpoints
- Integration tests for tier transition workflows
- Edge case tests for boundary conditions
- Security and concurrency tests
"""

import pytest
import requests
import time
import threading
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

#
# Configuration
# 
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
HEADERS = {"Content-Type": "application/json"}
AUTH_HEADERS = {**HEADERS, "Authorization": f"Bearer {os.getenv('API_TOKEN', 'test-token')}"}

# File size boundaries
MIN_FILE_SIZE = 1 * 1024 * 1024        # 1 MB (minimum for tiering)
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB (maximum for tiering)


# 
#  Fixtures
#
def create_temp_file(size_bytes: int, filename: str = "test_file.bin") -> tuple:
    """Create an in-memory file of the given size for upload."""
    content = b"A" * size_bytes
    return (filename, content, "application/octet-stream")


def upload_file(size_bytes: int = MIN_FILE_SIZE, filename: str = "test.bin") -> dict:
    """Helper: upload a file and return response JSON."""
    files = {"file": create_temp_file(size_bytes, filename)}
    resp = requests.post(f"{BASE_URL}/files", files=files, headers={"Authorization": AUTH_HEADERS.get("Authorization", "")})
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()


@pytest.fixture
def uploaded_file():
    """Fixture: upload a file, yield its ID, then delete it."""
    data = upload_file()
    file_id = data["fileId"]
    yield file_id
    requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)


#
# PART 1 — FILE OPERATIONS (CRUD)
# 

class TestFileUpload:
    """POST /files"""

    def test_upload_valid_file(self):
        """Standard upload should return 201 with a fileId."""
        data = upload_file(MIN_FILE_SIZE)
        assert "fileId" in data
        assert data["tier"] == "hot"          # new files start in Hot tier
        requests.delete(f"{BASE_URL}/files/{data['fileId']}", headers=AUTH_HEADERS)

    def test_upload_exact_minimum_size(self):
        """File exactly at 1 MB boundary should succeed."""
        data = upload_file(MIN_FILE_SIZE, "boundary_min.bin")
        assert data["fileId"]
        requests.delete(f"{BASE_URL}/files/{data['fileId']}", headers=AUTH_HEADERS)

    def test_upload_below_minimum_size(self):
        """File below 1 MB should be rejected (400 or 422)."""
        files = {"file": create_temp_file(MIN_FILE_SIZE - 1, "too_small.bin")}
        resp = requests.post(f"{BASE_URL}/files", files=files, headers={"Authorization": AUTH_HEADERS["Authorization"]})
        assert resp.status_code in (400, 422), f"Expected rejection, got {resp.status_code}"

    def test_upload_zero_byte_file(self):
        """Zero-byte file should be rejected."""
        files = {"file": create_temp_file(0, "empty.bin")}
        resp = requests.post(f"{BASE_URL}/files", files=files, headers={"Authorization": AUTH_HEADERS["Authorization"]})
        assert resp.status_code in (400, 422), f"Expected rejection, got {resp.status_code}"

    def test_upload_just_under_1mb(self):
        """1 MB - 1 byte should be rejected (boundary edge case)."""
        files = {"file": create_temp_file(MIN_FILE_SIZE - 1, "just_under.bin")}
        resp = requests.post(f"{BASE_URL}/files", files=files, headers={"Authorization": AUTH_HEADERS["Authorization"]})
        assert resp.status_code in (400, 422)

    def test_upload_returns_correct_content_type(self):
        """Response Content-Type should be application/json."""
        files = {"file": create_temp_file(MIN_FILE_SIZE)}
        resp = requests.post(f"{BASE_URL}/files", files=files, headers={"Authorization": AUTH_HEADERS["Authorization"]})
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_upload_unauthenticated(self):
        """Request without auth should return 401."""
        files = {"file": create_temp_file(MIN_FILE_SIZE)}
        resp = requests.post(f"{BASE_URL}/files", files=files)
        assert resp.status_code == 401


class TestFileDownload:
    """GET /files/{fileId}"""

    def test_download_existing_file(self, uploaded_file):
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.content) == MIN_FILE_SIZE

    def test_download_non_existent_file(self):
        resp = requests.get(f"{BASE_URL}/files/non_existent_id_xyz", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_download_after_delete(self, uploaded_file):
        requests.delete(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_download_unauthenticated(self, uploaded_file):
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}")
        assert resp.status_code == 401


class TestFileMetadata:
    """GET /files/{fileId}/metadata"""

    def test_metadata_contains_required_fields(self, uploaded_file):
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}/metadata", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "fileId" in data
        assert "tier" in data
        assert "size" in data
        assert "lastAccessedAt" in data
        assert "createdAt" in data

    def test_metadata_initial_tier_is_hot(self, uploaded_file):
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}/metadata", headers=AUTH_HEADERS)
        assert resp.json()["tier"] == "hot"

    def test_metadata_size_matches_upload(self):
        data = upload_file(MIN_FILE_SIZE, "size_check.bin")
        file_id = data["fileId"]
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["size"] == MIN_FILE_SIZE
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)

    def test_metadata_non_existent_file(self):
        resp = requests.get(f"{BASE_URL}/files/bad_id/metadata", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestFileDelete:
    """DELETE /files/{fileId}"""

    def test_delete_existing_file(self, uploaded_file):
        resp = requests.delete(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        assert resp.status_code in (200, 204)

    def test_delete_non_existent_file(self):
        resp = requests.delete(f"{BASE_URL}/files/does_not_exist", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_idempotency(self, uploaded_file):
        requests.delete(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        resp2 = requests.delete(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
        assert resp2.status_code == 404

# PART 2 — ADMIN OPERATIONS

class TestAdminOperations:
    """POST /admin/tiering/run and GET /admin/stats"""

    def test_trigger_manual_tiering(self):
        resp = requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        assert resp.status_code in (200, 202)

    def test_get_usage_stats(self):
        resp = requests.get(f"{BASE_URL}/admin/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "hotTierCount" in data or "hot" in data
        assert "warmTierCount" in data or "warm" in data
        assert "coldTierCount" in data or "cold" in data

    def test_admin_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/admin/tiering/run")
        assert resp.status_code == 401

    def test_stats_non_negative_counts(self):
        resp = requests.get(f"{BASE_URL}/admin/stats", headers=AUTH_HEADERS)
        data = resp.json()
        for v in data.values():
            if isinstance(v, (int, float)):
                assert v >= 0


# 
# PART 3 — TIER TRANSITION TESTS (mocked timestamps)
#

class TestTierTransitions:
    """
    Validate automatic tiering logic using mocked last-access timestamps.
    The API is expected to expose a test/debug endpoint or support
    overriding the 'last_accessed_at' field for testing purposes.
    """

    def _set_last_access(self, file_id: str, days_ago: int):
        """Simulate aging a file by patching its last_accessed_at timestamp."""
        fake_time = (datetime.utcnow() - timedelta(days=days_ago)).isoformat() + "Z"
        resp = requests.patch(
            f"{BASE_URL}/admin/files/{file_id}/mock-timestamp",
            json={"lastAccessedAt": fake_time},
            headers=AUTH_HEADERS,
        )
        return resp

    def test_hot_to_warm_after_30_days(self):
        """File not accessed for 30+ days must move Hot → Warm."""
        data = upload_file()
        file_id = data["fileId"]
        self._set_last_access(file_id, 31)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["tier"] == "warm", f"Expected warm, got {meta['tier']}"
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)

    def test_warm_to_cold_after_90_days(self):
        """File not accessed for 90+ days must move Warm → Cold."""
        data = upload_file()
        file_id = data["fileId"]
        self._set_last_access(file_id, 91)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["tier"] == "cold", f"Expected cold, got {meta['tier']}"
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)

    def test_cold_to_warm_on_access(self):
        """Accessing a Cold file should promote it to Warm (then eventually Hot)."""
        data = upload_file()
        file_id = data["fileId"]
        self._set_last_access(file_id, 91)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        # Access the file — triggers promotion
        requests.get(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["tier"] in ("warm", "hot"), f"Expected warm/hot after access, got {meta['tier']}"
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)

    def test_file_stays_hot_within_29_days(self):
        """File accessed 29 days ago must remain in Hot tier."""
        data = upload_file()
        file_id = data["fileId"]
        self._set_last_access(file_id, 29)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["tier"] == "hot", f"Expected hot, got {meta['tier']}"
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)

    def test_boundary_exactly_30_days(self):
        """File at exactly 30-day boundary should transition to Warm."""
        data = upload_file()
        file_id = data["fileId"]
        self._set_last_access(file_id, 30)
        requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
        meta = requests.get(f"{BASE_URL}/files/{file_id}/metadata", headers=AUTH_HEADERS).json()
        assert meta["tier"] == "warm"
        requests.delete(f"{BASE_URL}/files/{file_id}", headers=AUTH_HEADERS)


#
# PART 4 — CONCURRENCY TESTS
#

class TestConcurrency:
    """Validate system behavior under concurrent load."""

    def test_concurrent_uploads(self):
        """10 simultaneous uploads should all succeed."""
        results = []
        errors = []

        def do_upload():
            try:
                data = upload_file(MIN_FILE_SIZE, "concurrent.bin")
                results.append(data["fileId"])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_upload) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Upload errors: {errors}"
        assert len(results) == 10, f"Only {len(results)}/10 uploads succeeded"
        # Cleanup
        for fid in results:
            requests.delete(f"{BASE_URL}/files/{fid}", headers=AUTH_HEADERS)

    def test_concurrent_reads_same_file(self, uploaded_file):
        """20 simultaneous reads of the same file should all return 200."""
        status_codes = []

        def do_read():
            r = requests.get(f"{BASE_URL}/files/{uploaded_file}", headers=AUTH_HEADERS)
            status_codes.append(r.status_code)

        threads = [threading.Thread(target=do_read) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(sc == 200 for sc in status_codes), f"Non-200 responses: {status_codes}"

    def test_concurrent_tiering_run(self):
        """Multiple simultaneous tiering runs should not corrupt state."""
        responses = []

        def run_tiering():
            r = requests.post(f"{BASE_URL}/admin/tiering/run", headers=AUTH_HEADERS)
            responses.append(r.status_code)

        threads = [threading.Thread(target=run_tiering) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r in (200, 202, 409) for r in responses), f"Unexpected status codes: {responses}"


# 
# PART 5 — SECURITY TESTS
# 

class TestSecurity:
    """Basic security validation."""

    def test_invalid_token_rejected(self):
        bad_headers = {"Authorization": "Bearer totally_invalid_token_xxxx"}
        resp = requests.get(f"{BASE_URL}/files/some_id", headers=bad_headers)
        assert resp.status_code == 401

    def test_sql_injection_in_file_id(self):
        malicious_id = "' OR '1'='1"
        resp = requests.get(f"{BASE_URL}/files/{malicious_id}", headers=AUTH_HEADERS)
        assert resp.status_code in (400, 404), f"Possible SQL injection vulnerability: {resp.status_code}"

    def test_path_traversal_in_file_id(self):
        malicious_id = "../../etc/passwd"
        resp = requests.get(f"{BASE_URL}/files/{malicious_id}", headers=AUTH_HEADERS)
        assert resp.status_code in (400, 404)

    def test_oversized_file_rejected(self):
        """File exceeding 10 GB limit should be rejected."""
        # We mock the Content-Length header rather than sending actual data
        resp = requests.post(
            f"{BASE_URL}/files",
            headers={**AUTH_HEADERS, "Content-Length": str(MAX_FILE_SIZE + 1)},
        )
        assert resp.status_code in (400, 413, 422)

    def test_responses_do_not_leak_internal_paths(self, uploaded_file):
        resp = requests.get(f"{BASE_URL}/files/{uploaded_file}/metadata", headers=AUTH_HEADERS)
        body = resp.text.lower()
        assert "/var/" not in body
        assert "/home/" not in body
        assert "stack trace" not in body


# 
# PART 6 — PERFORMANCE / RELIABILITY
#

class TestPerformance:
    """Basic performance smoke tests."""

    def test_metadata_response_time_under_500ms(self, uploaded_file):
        start = time.time()
        requests.get(f"{BASE_URL}/files/{uploaded_file}/metadata", headers=AUTH_HEADERS)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Metadata took {elapsed_ms:.0f}ms (expected <500ms)"

    def test_upload_response_time_under_5s(self):
        start = time.time()
        data = upload_file(MIN_FILE_SIZE)
        elapsed = time.time() - start
        assert elapsed < 5, f"Upload took {elapsed:.2f}s (expected <5s)"
        requests.delete(f"{BASE_URL}/files/{data['fileId']}", headers=AUTH_HEADERS)

    def test_admin_stats_response_time_under_1s(self):
        start = time.time()
        requests.get(f"{BASE_URL}/admin/stats", headers=AUTH_HEADERS)
        elapsed = time.time() - start
        assert elapsed < 1, f"Stats took {elapsed:.2f}s (expected <1s)"
