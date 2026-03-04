"""
Per-field action logging for form fill auditing.

Logs every individual field fill action to SQLite for debugging,
optimization, and tracking which fields succeed/fail across ATS portals.
"""

import sqlite3
import time
from datetime import datetime


class FieldLogger:
    """Logs individual field fill actions to the database."""

    def __init__(self, db_conn):
        """Initialize with an existing SQLite connection.

        Args:
            db_conn: sqlite3.Connection instance (from Database class)
        """
        self.conn = db_conn
        self._ensure_table()

    def _ensure_table(self):
        """Create field_actions table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS field_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                page_number INTEGER DEFAULT 1,
                field_label TEXT,
                field_type TEXT,
                field_name TEXT,
                intended_value TEXT,
                actual_value TEXT,
                source TEXT,
                confidence REAL DEFAULT 0.0,
                success BOOLEAN DEFAULT 1,
                error_message TEXT DEFAULT '',
                retry_count INTEGER DEFAULT 0,
                duration_ms REAL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_field_actions_app "
            "ON field_actions(application_id)"
        )
        self.conn.commit()

    def log_action(self, application_id, page_number, action,
                   success=True, actual_value="", error_message="",
                   duration_ms=0.0):
        """Log a single field fill action.

        Args:
            application_id: FK to applications table
            page_number: Which page of the form (1-indexed)
            action: FillAction dataclass instance
            success: Whether the fill succeeded
            actual_value: What was actually set (may differ from intended)
            error_message: Error text if failed
            duration_ms: How long the fill took in milliseconds
        """
        try:
            # Handle both FillAction objects and dicts
            if hasattr(action, 'field'):
                label = action.field.label if action.field else ""
                field_type = action.field.field_type if action.field else ""
                field_name = action.field.name if action.field else ""
                intended = action.intended_value or ""
                source = action.source or ""
                confidence = action.confidence or 0.0
            else:
                # Dict-based fallback
                label = action.get("label", "")
                field_type = action.get("field_type", "")
                field_name = action.get("name", "")
                intended = action.get("intended_value", "")
                source = action.get("source", "")
                confidence = action.get("confidence", 0.0)

            self.conn.execute("""
                INSERT INTO field_actions
                (application_id, page_number, field_label, field_type,
                 field_name, intended_value, actual_value, source,
                 confidence, success, error_message, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                application_id, page_number,
                label[:500], field_type, field_name[:200],
                intended[:2000], actual_value[:2000],
                source, confidence,
                1 if success else 0,
                error_message[:1000], duration_ms
            ))
            self.conn.commit()
        except Exception as e:
            print(f"    [FieldLogger] Warning: failed to log action: {e}")

    def log_actions_batch(self, application_id, page_number, actions_results):
        """Log multiple field actions at once.

        Args:
            application_id: FK to applications table
            page_number: Which page of the form
            actions_results: List of (action, success, actual_value, error_msg, duration_ms) tuples
        """
        for action, success, actual_value, error_msg, duration_ms in actions_results:
            self.log_action(
                application_id, page_number, action,
                success=success, actual_value=actual_value,
                error_message=error_msg, duration_ms=duration_ms
            )

    def get_field_stats(self, application_id):
        """Get per-field fill statistics for an application.

        Returns:
            List of dicts with field action details
        """
        cursor = self.conn.execute("""
            SELECT field_label, field_type, source, confidence,
                   success, error_message, retry_count, duration_ms
            FROM field_actions
            WHERE application_id = ?
            ORDER BY created_at
        """, (application_id,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_success_rate_by_source(self):
        """Get fill success rate grouped by source (profile/rule/ai/batch_ai).

        Returns:
            List of dicts: [{source, total, successes, rate}, ...]
        """
        cursor = self.conn.execute("""
            SELECT source,
                   COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                   ROUND(
                       100.0 * SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) / COUNT(*),
                       1
                   ) as rate
            FROM field_actions
            WHERE source != 'skip'
            GROUP BY source
        """)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_common_failures(self, limit=20):
        """Get the most commonly failed field labels.

        Returns:
            List of dicts: [{field_label, fail_count, last_error}, ...]
        """
        cursor = self.conn.execute("""
            SELECT field_label,
                   COUNT(*) as fail_count,
                   error_message as last_error
            FROM field_actions
            WHERE success = 0
            GROUP BY field_label
            ORDER BY fail_count DESC
            LIMIT ?
        """, (limit,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
