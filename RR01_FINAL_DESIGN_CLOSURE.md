# RR-01 Final Design Closure

## 1. Problem Statement
Genesis creation hashed sequence prefix `0`, while verification used database-allocated `sequence_id = 1`, causing a hash chain verification mismatch.

## 2. Root Cause
Discrepancy between hardcoded genesis sequence prefix serialization and dynamic SQLite primary key allocation.

## 3. Approved Solution Architecture
1. **Canonical Hashing (`v2`):**
   ```python
   content = f"{sequence_id}|{event_type}|{details}|{actor}|{created_at}|{prev_hash}"
   return hashlib.sha256(content.encode("utf-8")).hexdigest()
   ```
2. **Atomic Transactions (`BEGIN IMMEDIATE`):**
   - Genesis and event appends use `BEGIN IMMEDIATE` to serialize writes, insert placeholders to obtain `lastrowid`, compute canonical hashes with actual sequence IDs, update records, and commit (with full rollback on failure).
3. **Backward-Compatible Versioning (`v1` / `v2`):**
   - `verify_ledger()` validates new records against canonical `v2` format, and provides transparent fallback verification for legacy genesis records (`sequence_id == 1` with prefix `0`) without database rewriting or migrations.
4. **Test Isolation:**
   - Fixtures explicitly patch `memory.store.DB_PATH` and set `SEED_DATABASE_PATH` to isolated `tmp_path` instances.
