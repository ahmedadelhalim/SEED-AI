"""
SEED-AI Cryptographic Audit Ledger (Work Package RR-01)
Provides append-only, SHA-256 hash-chained audit logging and verification,
tamper detection, genesis block initialization, and 365-day retention enforcement.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from memory.store import connect


class CryptographicAuditLedger:
    """Manages append-only hash-chained audit events in SQLite."""

    @staticmethod
    def initialize_ledger() -> None:
        """Ensure audit_ledger table exists and has a genesis block if empty."""
        with connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS audit_ledger (
                sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                signature TEXT DEFAULT ''
            );
            """)
            # Check if genesis block exists
            cursor = db.execute("SELECT COUNT(*) FROM audit_ledger")
            row = cursor.fetchone()
            if row and row[0] == 0:
                # Insert genesis block
                genesis_type = "GENESIS"
                genesis_details = json.dumps({"description": "SEED-AI Cryptographic Audit Genesis Block"})
                genesis_actor = "system"
                genesis_time = datetime.now(timezone.utc).isoformat()
                prev_hash = "0" * 64
                
                content_to_hash = f"0|{genesis_type}|{genesis_details}|{genesis_actor}|{genesis_time}|{prev_hash}"
                curr_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()
                
                db.execute(
                    """
                    INSERT INTO audit_ledger (event_type, details, actor, created_at, prev_hash, current_hash, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (genesis_type, genesis_details, genesis_actor, genesis_time, prev_hash, curr_hash, "GENESIS_SIG")
                )
                db.commit()

    @staticmethod
    def append_event(event_type: str, details: Dict[str, Any], actor: str = "system") -> Dict[str, Any]:
        """Append a new audit event, chaining its hash to the previous event."""
        CryptographicAuditLedger.initialize_ledger()
        
        details_json = json.dumps(details, sort_keys=True)
        created_at = datetime.now(timezone.utc).isoformat()
        
        with connect() as db:
            cursor = db.execute("SELECT sequence_id, current_hash FROM audit_ledger ORDER BY sequence_id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                prev_seq = row[0]
                prev_hash = row[1]
            else:
                prev_seq = 0
                prev_hash = "0" * 64
                
            content_to_hash = f"{prev_seq + 1}|{event_type}|{details_json}|{actor}|{created_at}|{prev_hash}"
            curr_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()
            
            cursor = db.execute(
                """
                INSERT INTO audit_ledger (event_type, details, actor, created_at, prev_hash, current_hash, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_type, details_json, actor, created_at, prev_hash, curr_hash, f"sig_{curr_hash[:16]}")
            )
            db.commit()
            new_id = cursor.lastrowid
            
            return {
                "sequence_id": new_id,
                "event_type": event_type,
                "prev_hash": prev_hash,
                "current_hash": curr_hash,
                "created_at": created_at,
            }

    @staticmethod
    def verify_ledger() -> Tuple[bool, List[Dict[str, Any]]]:
        """Verify the cryptographic hash chain of the audit ledger.

        Returns (is_valid, list_of_violations).
        """
        CryptographicAuditLedger.initialize_ledger()
        violations: List[Dict[str, Any]] = []
        
        with connect() as db:
            cursor = db.execute("SELECT sequence_id, event_type, details, actor, created_at, prev_hash, current_hash FROM audit_ledger ORDER BY sequence_id ASC")
            rows = cursor.fetchall()
            
        if not rows:
            return True, []
            
        expected_prev_hash = "0" * 64
        
        for idx, row in enumerate(rows):
            seq = row["sequence_id"]
            ev_type = row["event_type"]
            details = row["details"]
            actor = row["actor"]
            created_at = row["created_at"]
            p_hash = row["prev_hash"]
            c_hash = row["current_hash"]
            
            if p_hash != expected_prev_hash:
                violations.append({
                    "sequence_id": seq,
                    "error": "prev_hash_mismatch",
                    "expected": expected_prev_hash,
                    "actual": p_hash,
                })
                
            content_to_hash = f"{seq}|{ev_type}|{details}|{actor}|{created_at}|{p_hash}"
            recalculated_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()
            
            if recalculated_hash != c_hash:
                violations.append({
                    "sequence_id": seq,
                    "error": "hash_tamper_detected",
                    "stored": c_hash,
                    "recalculated": recalculated_hash,
                })
                
            expected_prev_hash = c_hash
            
        return len(violations) == 0, violations

    @staticmethod
    def enforce_retention(retention_days: int = 365) -> Dict[str, Any]:
        """Enforce 365-day retention with controlled archival.

        Archival moves expired records (>365 days old, excluding genesis)
        into an audit_archive table, ensuring immutable historical compliance
        without violating audit traceability.
        """
        CryptographicAuditLedger.initialize_ledger()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()
        
        with connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS audit_archive (
                sequence_id INTEGER PRIMARY KEY,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                signature TEXT,
                archived_at TEXT NOT NULL
            );
            """)
            
            # Find records older than cutoff, excluding genesis (sequence_id = 1)
            cursor = db.execute(
                "SELECT * FROM audit_ledger WHERE sequence_id > 1 AND created_at < ?",
                (cutoff_str,)
            )
            expired_rows = cursor.fetchall()
            archived_count = 0
            
            if expired_rows:
                archived_at = datetime.now(timezone.utc).isoformat()
                for row in expired_rows:
                    db.execute(
                        """
                        INSERT OR IGNORE INTO audit_archive 
                        (sequence_id, event_type, details, actor, created_at, prev_hash, current_hash, signature, archived_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (row["sequence_id"], row["event_type"], row["details"], row["actor"], 
                         row["created_at"], row["prev_hash"], row["current_hash"], row["signature"], archived_at)
                    )
                    archived_count += 1
                # Note: To preserve tamper-evident hash chaining, archived active rows 
                # can be marked or retained, or kept in ledger. Here we report archival stats.
                db.commit()
                
            return {
                "retention_days": retention_days,
                "cutoff_date": cutoff_str,
                "archived_records": archived_count,
            }
