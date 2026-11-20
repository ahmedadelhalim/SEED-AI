import threading
import sqlite3
from typing import Any, Dict, List, Mapping, Optional
from memory import store

class ResourceRegistry:
    """Global Resource Registry owned by SEED Core: tracks local environments, repositories, tools, and connected infrastructure."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with store.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS global_resources (
                    resource_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path_or_uri TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'registered',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()

    def register_resource(self, resource_id: str, resource_type: str, name: str, path_or_uri: str, metadata: Mapping[str, Any] = None) -> Dict[str, Any]:
        import json
        meta_json = json.dumps(dict(metadata or {}), sort_keys=True)
        with self._lock, store.connect() as db:
            db.execute("""
                INSERT INTO global_resources (resource_id, resource_type, name, path_or_uri, metadata_json, status, updated_at)
                VALUES (?, ?, ?, ?, ?, 'registered', CURRENT_TIMESTAMP)
                ON CONFLICT(resource_id) DO UPDATE SET
                    resource_type=excluded.resource_type,
                    name=excluded.name,
                    path_or_uri=excluded.path_or_uri,
                    metadata_json=excluded.metadata_json,
                    status='registered',
                    updated_at=CURRENT_TIMESTAMP
            """, (resource_id, resource_type, name, path_or_uri, meta_json))
            db.commit()
        return self.get_resource(resource_id)

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        import json
        with store.connect() as db:
            row = db.execute("SELECT * FROM global_resources WHERE resource_id = ?", (resource_id,)).fetchone()
            if not row:
                return None
            return {
                "resource_id": row["resource_id"],
                "resource_type": row["resource_type"],
                "name": row["name"],
                "path_or_uri": row["path_or_uri"],
                "metadata": json.loads(row["metadata_json"]),
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def list_resources(self, resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
        import json
        with store.connect() as db:
            if resource_type:
                rows = db.execute("SELECT * FROM global_resources WHERE resource_type = ? ORDER BY name", (resource_type,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM global_resources ORDER BY name").fetchall()
            results = []
            for row in rows:
                results.append({
                    "resource_id": row["resource_id"],
                    "resource_type": row["resource_type"],
                    "name": row["name"],
                    "path_or_uri": row["path_or_uri"],
                    "metadata": json.loads(row["metadata_json"]),
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                })
            return results

    def set_resource_status(self, resource_id: str, status: str) -> bool:
        with self._lock, store.connect() as db:
            cursor = db.execute("UPDATE global_resources SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE resource_id = ?", (status, resource_id))
            db.commit()
            return cursor.rowcount > 0

    def unregister_resource(self, resource_id: str) -> bool:
        with self._lock, store.connect() as db:
            cursor = db.execute("DELETE FROM global_resources WHERE resource_id = ?", (resource_id,))
            db.commit()
            return cursor.rowcount > 0
