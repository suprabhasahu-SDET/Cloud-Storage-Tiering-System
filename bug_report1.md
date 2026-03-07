# Bug Report —  Cloud Storage Tiering System
Bug should be filed /raised by some tools like jira, Bugzilla. Here based on the current company  which tool they are using we can proceed with that.
---

## Bug #1 — Files Below 1 MB Are Accepted but Never Tiered

**Severity:** High  
**Component:** POST /files  
**Reported by:** Reporte name (QA Engineer)  
**Date:** 08-03-2026

### Summary
Files smaller than 1 MB can be uploaded successfully but the tiering engine silently skips them. They remain in the Hot tier indefinitely with no error, misleading callers into thinking the file is being managed.

### Test Steps to Reproduce
1. Upload a file of 512 KB (below the 1 MB minimum)
2. Note: the API returns `201 Created` with a `fileId`
3. Wait 90+ days (or use mock timestamp)
4. Trigger `POST /admin/tiering/run`
5. Check `GET /files/{fileId}/metadata` — tier remains `"hot"` forever

### Expected Behavior
The API should reject files below 1 MB at upload time with `400 Bad Request` and a clear error message:

```json
{
  "error": "FILE_TOO_SMALL",
  "message": "Minimum file size for tiering is 1 MB. Received: 524288 bytes."
}
```

### Actual Behavior
- Upload returns `201 Created`
- File is stored but excluded from tiering silently
- Metadata shows `tier: "hot"` indefinitely

### Logs / Evidence
```
POST /files HTTP/1.1 → 201 Created
{"fileId": "abc123", "tier": "hot", "size": 524288}

# 91 days later (mocked)
POST /admin/tiering/run → 200 OK
GET /files/abc123/metadata → {"tier": "hot"}   ← still hot, never tiered
```

### Proposed Fix
Add a size guard in the upload handler before persisting:

```python
if file.size < 1_048_576:  # 1 MB
    raise HTTPException(status_code=400, detail={
        "error": "FILE_TOO_SMALL",
        "message": f"Minimum file size is 1 MB. Got {file.size} bytes."
    })
```

---

## Bug #2 — Tiering Run Is Not Idempotent Under Concurrent Requests

**Severity:** Medium  
**Component:** POST /admin/tiering/run  
**Reported by:** Reporte name (QA Engineer)   
**Date:**  08-03-2026
### Summary
When two or more concurrent requests hit `POST /admin/tiering/run`, the tiering engine runs multiple times in parallel. This can cause a file to be evaluated mid-transition, resulting in incorrect tier assignments (e.g., a file skipping Warm and jumping directly to Cold).

### Steps to Reproduce
1. Upload 5 files, set their last-access timestamps to 32 days ago
2. Send 3 simultaneous `POST /admin/tiering/run` requests
3. Check metadata for all 5 files

### Expected Behavior
Only one tiering job runs at a time. Subsequent concurrent requests should either:
- Return `202 Accepted` (job already running), or  
- Queue and execute after the active job completes

All files should end up in the `warm` tier.

### Actual Behavior
Race condition causes 1–2 files to land in `cold` after a single tiering trigger, skipping the `warm` step.

### Logs / Evidence
```
# Three concurrent requests
POST /admin/tiering/run → 200 OK  (thread 1)
POST /admin/tiering/run → 200 OK  (thread 2)
POST /admin/tiering/run → 200 OK  (thread 3)

# Result — inconsistent tiers
GET /files/id1/metadata → {"tier": "warm"}  ✓
GET /files/id2/metadata → {"tier": "cold"}  ✗ (should be warm)
GET /files/id3/metadata → {"tier": "cold"}  ✗ (should be warm)
```

### Proposed Fix
Introduce a some distributed lock before starting the tiering job. So for that I don't have a Knowledge.

```

