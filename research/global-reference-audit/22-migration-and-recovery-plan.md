# 22-Migration and Recovery Plan

**Document ID:** `22-migration-and-recovery-plan`
**Date:** 2026-11-12

---

SQLite database backups (`data/seed_memory.db.backup_*`), atomic table migrations, and graceful task restart recovery via `reconcile_orphaned_tasks()`.
