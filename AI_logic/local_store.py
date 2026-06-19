"""
Local SQLite storage for conversation context.
Drop-in replacement for airtable.py — same API, no cloud dependency.
Uses standard library sqlite3 (no SQLAlchemy needed).
"""
import os
import sqlite3
from datetime import datetime, timedelta

# ── Database setup ──────────────────────────────────────────────
_db_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
os.makedirs(_db_dir, exist_ok=True)

_db_path = os.path.join(_db_dir, 'conversations.sqlite')


def _get_conn():
    """Get a new sqlite3 connection with row_factory for dict-like access."""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn


# Auto-create table on module load
with _get_conn() as conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_age TEXT UNIQUE NOT NULL,
            summary TEXT DEFAULT '',
            last_contact TEXT DEFAULT '',
            not_to_rise INTEGER DEFAULT 0
        )
    ''')
    conn.commit()


# ── Public API (compatible with airtable.py) ────────────────────

def get_record(name_age):
    """Return the stored summary for a given name_age, or None."""
    with _get_conn() as conn:
        row = conn.execute(
            'SELECT summary FROM conversations WHERE name_age = ?',
            (name_age,)
        ).fetchone()
        return row['summary'] if row else None


def upsert_record(name_age, summary=None, not_to_rise=None):
    """Insert or update a conversation record."""
    today = datetime.today().strftime('%d-%m-%Y')
    with _get_conn() as conn:
        existing = conn.execute(
            'SELECT id FROM conversations WHERE name_age = ?',
            (name_age,)
        ).fetchone()

        if existing:
            # Build dynamic UPDATE to only set provided fields
            updates = ['last_contact = ?']
            params = [today]
            if summary is not None:
                updates.append('summary = ?')
                params.append(summary)
            if not_to_rise is not None:
                updates.append('not_to_rise = ?')
                params.append(1 if not_to_rise else 0)
            params.append(name_age)
            conn.execute(
                f'UPDATE conversations SET {", ".join(updates)} WHERE name_age = ?',
                params
            )
        else:
            conn.execute(
                'INSERT INTO conversations (name_age, summary, last_contact, not_to_rise) '
                'VALUES (?, ?, ?, ?)',
                (name_age, summary or '', today, 1 if not_to_rise else 0)
            )
        conn.commit()


def girls_to_rise():
    """Return name_age list for girls contacted 3-7 days ago, not marked 'not_to_rise'."""
    start_date = datetime.today() - timedelta(days=2)
    end_date = datetime.today() - timedelta(days=8)
    result = []
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT name_age, last_contact FROM conversations WHERE not_to_rise = 0'
        ).fetchall()
        for row in rows:
            if not row['last_contact']:
                continue
            try:
                date_of_record = datetime.strptime(row['last_contact'], '%d-%m-%Y')
            except ValueError:
                continue
            if start_date > date_of_record > end_date:
                result.append(row['name_age'])
    return result


def remove_expired_girls():
    """Remove records where last_contact is more than 7 days ago
    and not_to_rise is False."""
    expiration_date = datetime.today() - timedelta(days=7)
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT id, last_contact FROM conversations WHERE not_to_rise = 0'
        ).fetchall()
        ids_to_delete = []
        for row in rows:
            if not row['last_contact']:
                continue
            try:
                date_of_record = datetime.strptime(row['last_contact'], '%d-%m-%Y')
            except ValueError:
                continue
            if date_of_record < expiration_date:
                ids_to_delete.append(row['id'])
        if ids_to_delete:
            placeholders = ','.join('?' * len(ids_to_delete))
            conn.execute(
                f'DELETE FROM conversations WHERE id IN ({placeholders})',
                ids_to_delete
            )
            conn.commit()
