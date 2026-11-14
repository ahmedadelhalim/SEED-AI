
import sqlite3

path = r"D:\SEED-AI\data\seed_memory.db"

with sqlite3.connect(path) as db:
    rows = db.execute("""
        SELECT e.id, e.task_id, e.event_type, e.details
        FROM events e
        WHERE e.task_id = 4
        ORDER BY e.id
    """).fetchall()

    for row in rows:
        print(row)

    assert any(
        row[2] == "workspace_access_denied"
        for row in rows
    ), "Rejected access was not recorded"

print("SECURITY_AUDIT_VERIFIED")
