"""
SQLite database for comprehensive job application logging.

Tracks every job interaction - not just successes, but discovered, opened,
attempted, failed, and skipped jobs with full application metadata.
"""

import sqlite3
import json
import os
from datetime import datetime


class Database:
    def __init__(self, db_path="seekmate.db"):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self.init_tables()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def init_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seek_job_id TEXT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                salary TEXT,
                job_url TEXT NOT NULL,
                external_url TEXT,
                description TEXT,
                date_discovered DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_applied DATETIME,
                status TEXT DEFAULT 'discovered',
                UNIQUE(job_url)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                application_type TEXT,
                resume_used TEXT,
                cover_letter_used TEXT,
                ai_responses TEXT,
                submission_status TEXT,
                failure_reason TEXT,
                captcha_triggered BOOLEAN DEFAULT 0,
                email_verification BOOLEAN DEFAULT 0,
                pages_completed INTEGER DEFAULT 0,
                duration_seconds REAL,
                ats_portal TEXT,
                agent_version TEXT,
                prompt_version TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                error_type TEXT,
                error_message TEXT,
                page_url TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                outcome TEXT,
                response_time_hours REAL,
                email_subject TEXT,
                detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(job_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_job ON failures(job_id)")

        self.conn.commit()

    def log_job(self, job_data):
        """Log a discovered job. Returns job_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO jobs (seek_job_id, title, company, location, salary,
                    job_url, external_url, description, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data.get("seek_job_id"),
                job_data.get("title", "Unknown"),
                job_data.get("company"),
                job_data.get("location"),
                job_data.get("salary"),
                job_data.get("job_url", ""),
                job_data.get("external_url"),
                job_data.get("description"),
                job_data.get("status", "discovered"),
            ))
            self.conn.commit()

            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM jobs WHERE job_url = ?", (job_data.get("job_url", ""),))
                row = cursor.fetchone()
                return row["id"] if row else None

            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"    [DB] Error logging job: {e}")
            return None

    def log_application(self, app_data):
        """Log an application attempt. Returns application_id."""
        cursor = self.conn.cursor()
        try:
            ai_responses = app_data.get("ai_responses")
            if isinstance(ai_responses, dict):
                ai_responses = json.dumps(ai_responses)

            cursor.execute("""
                INSERT INTO applications (job_id, application_type, resume_used, cover_letter_used,
                    ai_responses, submission_status, failure_reason, captcha_triggered,
                    email_verification, pages_completed, duration_seconds, ats_portal,
                    agent_version, prompt_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_data.get("job_id"),
                app_data.get("application_type", "long_form"),
                app_data.get("resume_used"),
                app_data.get("cover_letter_used"),
                ai_responses,
                app_data.get("submission_status", "attempted"),
                app_data.get("failure_reason"),
                app_data.get("captcha_triggered", False),
                app_data.get("email_verification", False),
                app_data.get("pages_completed", 0),
                app_data.get("duration_seconds"),
                app_data.get("ats_portal"),
                app_data.get("agent_version", "1.0.0"),
                app_data.get("prompt_version", "1.0"),
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"    [DB] Error logging application: {e}")
            return None

    def log_failure(self, job_id, error_type, error_message, page_url=None, retry_count=0):
        """Log a failure event."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO failures (job_id, error_type, error_message, page_url, retry_count)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, error_type, error_message, page_url, retry_count))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"    [DB] Error logging failure: {e}")

    def update_status(self, job_id, status, date_applied=None):
        """Update job status (discovered, opened, attempted, applied, failed, skipped)."""
        cursor = self.conn.cursor()
        try:
            if date_applied:
                cursor.execute("UPDATE jobs SET status = ?, date_applied = ? WHERE id = ?",
                               (status, date_applied, job_id))
            else:
                cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"    [DB] Error updating status: {e}")

    def log_email_outcome(self, job_id, outcome, email_subject=None, response_time_hours=None):
        """Log employer email outcome (interview, rejection, offer, no_response)."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO email_outcomes (job_id, outcome, email_subject, response_time_hours)
                VALUES (?, ?, ?, ?)
            """, (job_id, outcome, email_subject, response_time_hours))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"    [DB] Error logging outcome: {e}")

    def get_stats(self):
        """Get summary statistics."""
        cursor = self.conn.cursor()
        stats = {}
        try:
            cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
            stats["jobs_by_status"] = {row["status"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) as total FROM applications WHERE submission_status = 'submitted'")
            stats["total_submitted"] = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM applications WHERE submission_status = 'failed'")
            stats["total_failed"] = cursor.fetchone()["total"]

            cursor.execute("SELECT AVG(duration_seconds) as avg_duration FROM applications WHERE duration_seconds > 0")
            row = cursor.fetchone()
            stats["avg_duration_seconds"] = round(row["avg_duration"], 1) if row["avg_duration"] else 0

            cursor.execute("SELECT COUNT(*) as total FROM applications WHERE captcha_triggered = 1")
            stats["captcha_count"] = cursor.fetchone()["total"]

            cursor.execute("SELECT error_type, COUNT(*) as count FROM failures GROUP BY error_type")
            stats["failures_by_type"] = {row["error_type"]: row["count"] for row in cursor.fetchall()}

        except sqlite3.Error as e:
            print(f"    [DB] Error getting stats: {e}")

        return stats

    def get_recent_jobs(self, limit=50):
        """Get recent jobs with application data for dashboard display."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT j.id, j.title, j.company, j.location, j.job_url, j.status,
                       j.date_discovered, j.date_applied,
                       a.ats_portal, a.duration_seconds, a.pages_completed,
                       a.submission_status, a.failure_reason, a.captcha_triggered,
                       a.resume_used
                FROM jobs j
                LEFT JOIN applications a ON a.job_id = j.id
                ORDER BY j.date_discovered DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"    [DB] Error getting recent jobs: {e}")
            return []

    def get_status_counts(self):
        """Get count of jobs by each status."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
            return {row["status"]: row["count"] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"    [DB] Error getting status counts: {e}")
            return {}

    def job_already_applied(self, job_url):
        """Check if a job URL has already been applied to."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM jobs WHERE job_url = ? AND status = 'applied'", (job_url,))
        return cursor.fetchone() is not None

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
