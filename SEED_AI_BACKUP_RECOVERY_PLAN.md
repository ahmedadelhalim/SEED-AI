# SEED-AI Backup & Recovery Plan

## 1. Production Database Boundaries
- **Primary Production DB:** `D:\SEED-AI\data\seed_memory.db`
- **Rule:** Never execute destructive commands, direct DDL drops, or unbacked-up modifications against production paths.

## 2. Safe Backup Procedure
Before any future authorized database migration or remediation deployment:
1. Stop all active SEED-AI gateway and runner processes.
2. Create a timestamped binary backup copy of `seed_memory.db`:
   ```powershell
   Copy-Item "D:\SEED-AI\data\seed_memory.db" "D:\SEED-AI\data\seed_memory_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
   ```
3. Verify integrity using `PRAGMA integrity_check;`.

## 3. Disaster Recovery & Rollback Procedure
If verification or migration fails:
1. Terminate running processes.
2. Restore the pre-migration backup file to `data/seed_memory.db`.
3. Re-run verification suite to confirm baseline restoration.
4. Fall back to read-only safe mode if necessary.
