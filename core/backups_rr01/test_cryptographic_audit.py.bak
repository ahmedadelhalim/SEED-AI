"""
Unit tests for SEED-AI Cryptographic Audit Ledger (Work Package RR-01)
"""

import sqlite3
import pytest
from core.cryptographic_audit import CryptographicAuditLedger
from memory.store import connect, DB_PATH


def test_genesis_initialization_and_chain_verification():
    CryptographicAuditLedger.initialize_ledger()
    valid, violations = CryptographicAuditLedger.verify_ledger()
    assert valid is True
    assert len(violations) == 0


def test_append_and_verification():
    CryptographicAuditLedger.initialize_ledger()
    event = CryptographicAuditLedger.append_event("security_event", {"action": "permission_granted"}, actor="admin")
    assert event["sequence_id"] > 1
    assert len(event["current_hash"]) == 64

    valid, violations = CryptographicAuditLedger.verify_ledger()
    assert valid is True
    assert len(violations) == 0


def test_tamper_detection():
    CryptographicAuditLedger.initialize_ledger()
    CryptographicAuditLedger.append_event("test_event", {"data": "sensitive"}, actor="user")

    # Tamper with the database directly
    with connect() as db:
        db.execute("UPDATE audit_ledger SET details = 'tampered_data' WHERE sequence_id = 2")
        db.commit()

    valid, violations = CryptographicAuditLedger.verify_ledger()
    assert valid is False
    assert len(violations) > 0
    assert any(v["error"] == "hash_tamper_detected" for v in violations)


def test_retention_enforcement():
    CryptographicAuditLedger.initialize_ledger()
    stats = CryptographicAuditLedger.enforce_retention(retention_days=365)
    assert "retention_days" in stats
    assert stats["retention_days"] == 365
    assert "archived_records" in stats
