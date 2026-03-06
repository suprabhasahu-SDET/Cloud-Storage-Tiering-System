Cloud Storage Tiering System
Comprehensive Test Strategy & Documentation

1. Overview
This document defines the complete test strategy for Lucidity's Cloud Storage Tiering System — a platform that automatically moves file data between Hot (SSD), Warm (HDD), and Cold (Object Storage) tiers based on access frequency.
The goal is to validate that all API endpoints are correct, tier transitions respect the defined rules, edge cases are handled gracefully, and the system is resilient under concurrent load.

2. System Under Test
2.1 Tier Transition Rules
Condition	Transition	Notes
No access for 30+ days	Hot → Warm	Boundary: exactly 30 days included
No access for 90+ days	Warm → Cold	Boundary: exactly 90 days included
Recent file access	Cold → Warm → Hot	Triggered on read; promotion on next tiering run
File size < 1 MB	No tiering	File is stored but skipped by tiering engine
File size > 10 GB	Rejected at upload	Returns 400/413 immediately

2.2 APIs Under Test
Method	Endpoint	Purpose
POST	/files	Upload a file
GET	/files/{fileId}	Download a file
GET	/files/{fileId}/metadata	Retrieve file metadata
DELETE	/files/{fileId}	Delete a file
POST	/admin/tiering/run	Manually trigger the tiering engine
GET	/admin/stats	Retrieve storage tier usage statistics


3. Test Strategy

3.1 Functional Testing
Verify each endpoint against its specification — covering the happy path, error paths, and boundary values.
•	Upload: valid files, zero-byte, below 1 MB, above 10 GB, duplicate names
•	Download: existing file, deleted file, nonexistent ID
•	Metadata: field presence, correct initial tier, size accuracy
•	Delete: existing, already-deleted (idempotency), nonexistent
•	Admin: manual tiering trigger, stats field validation, auth enforcement

3.2 Edge & Boundary Testing
Focus on values at and around defined limits to catch off-by-one errors in both the API validation layer and the tiering logic.
Scenario	Input	Expected Result
Zero-byte file	0 bytes	400 Bad Request
1 byte below minimum	1,048,575 bytes	400 Bad Request
Exact minimum	1,048,576 bytes (1 MB)	201 Created, tier: hot
Exactly 10 GB	10,737,418,240 bytes	201 Created
1 byte above maximum	10,737,418,241 bytes	400 / 413 Rejected
Exactly 30-day boundary	last_accessed = 30 days ago	Transitions to warm
29-day access	last_accessed = 29 days ago	Remains in hot
Exactly 90-day boundary	last_accessed = 90 days ago	Transitions to cold

3.3 Performance & Reliability
Baseline latency targets to ensure acceptable user experience:
Operation	Target SLA	Test Method
•   Metadata lookup	< 500 ms (p95)	Stopwatch assertion in test
•   File upload (1 MB)	< 5 s	Timed test case
•   Admin stats	< 1 s	Timed test case


3.4 Security Testing
Validate authentication enforcement and resistance to common injection attacks.
•	All protected endpoints must return 401 for missing/invalid tokens
•	SQL injection payloads in fileId must return 400 or 404, never 500
•	Path traversal sequences (../../) in fileId must be rejected
•	Error responses must not expose internal file paths or stack traces
•	Oversized Content-Length header must be rejected without consuming memory

3.5 Concurrency Testing
Validate system correctness when multiple clients interact simultaneously.
•	10 parallel uploads must all succeed independently
•	20 parallel reads of the same file must all return 200
•	Simultaneous tiering runs must not cause double-transitions or skipped tiers

4. Test Implementation Notes
4.1 Framework & Language
Tests are written in Python using pytest. The requests library handles HTTP calls. All tests are parameterized where applicable and grouped into classes by endpoint.
4.2 Tier Transition Mocking
Real tier transitions require waiting 30–90 days. Tests use a mock-timestamp admin endpoint (POST /admin/files/{fileId}/mock-timestamp) to simulate aged files, then trigger POST /admin/tiering/run to force evaluation. This makes tier-transition tests deterministic and fast.
4.3 Test Isolation
Each test that creates a file is responsible for deleting it in teardown (via pytest fixtures). This ensures a clean state and prevents cross-test interference.
4.4 Environment Variables
Variable	Default	Description
API_BASE_URL	http://localhost:8000	Base URL of the API under test
API_TOKEN	test-token	Bearer token for authentication


5. Known Bugs
The following bugs were identified during testing. Full details are in bug_report.md.
ID	Severity	Summary	Status
BUG-001	High	Files < 1 MB accepted but never tiered	Open
BUG-002	Medium	Concurrent tiering runs cause incorrect tier assignments	Open


6. Deliverables
•	test_storage_tiering.py — full automated test suite (pytest)
•	bug_report.md — 2 documented bugs with repro steps and proposed fixes
•	test_strategy.md — this document
•	pytest.ini — test runner configuration

Run tests with:
  API_BASE_URL=http://your-server pytest -v
