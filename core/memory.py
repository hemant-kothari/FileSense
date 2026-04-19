"""
Memory Store — SQLite-backed persistent index of all described files.

Provides:
  - Global file index with FTS5 full-text search (porter stemmer)
  - Per-file evolution narratives (60–200 word rolling summaries)
  - Description history ring buffer (20 entries in SQLite, 5 in sidecar)
  - Project stats and security audit data across all indexed folders

Thread model: thread-local SQLite connections with WAL journal mode.
Multiple reader threads are fine; writes are serialised by SQLite WAL.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


# DB path

def _db_path() -> Path:
    # Import lazily to avoid circular imports at module load
    from config import load_config
    cfg = load_config()
    p = Path(cfg.get("memory_db_path", str(Path.home() / ".filesense" / "memory.db")))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# Thread-local connection pool

_local = threading.local()


def _conn() -> sqlite3.Connection:
    """Return the thread-local SQLite connection, creating it if needed."""
    if not hasattr(_local, "db") or _local.db is None:
        db = sqlite3.connect(str(_db_path()), timeout=15, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=NORMAL")
        _local.db = db
    return _local.db


def close_thread_connection():
    """Call from QThread.finished to cleanly close the thread's connection."""
    if hasattr(_local, "db") and _local.db is not None:
        try:
            _local.db.close()
        except Exception:
            pass
        _local.db = None


# Schema DDL

_DDL_STMTS = [
    # Main file index
    """
    CREATE TABLE IF NOT EXISTS files (
        path            TEXT PRIMARY KEY,
        folder          TEXT NOT NULL,
        name            TEXT NOT NULL,
        short_desc      TEXT    DEFAULT '',
        long_desc       TEXT    DEFAULT '',
        narrative       TEXT    DEFAULT '',
        tags            TEXT    DEFAULT '[]',
        sensitive       INTEGER DEFAULT 0,
        manual_lock     INTEGER DEFAULT 0,
        last_updated    TEXT    DEFAULT '',
        last_error      TEXT    DEFAULT '',
        file_size_bytes INTEGER DEFAULT 0,
        file_ext        TEXT    DEFAULT ''
    )
    """,
    # Description history (kept in SQLite; last 20 per file)
    """
    CREATE TABLE IF NOT EXISTS file_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        path        TEXT NOT NULL,
        short_desc  TEXT DEFAULT '',
        long_desc   TEXT DEFAULT '',
        source      TEXT DEFAULT 'ai',
        recorded_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_path ON file_history(path)",
    "CREATE INDEX IF NOT EXISTS idx_files_folder  ON files(folder)",
    "CREATE INDEX IF NOT EXISTS idx_files_sensitive ON files(sensitive)",
    "CREATE INDEX IF NOT EXISTS idx_files_ext ON files(file_ext)",

    # FTS5 virtual table (content-table backed by `files`)
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
        name,
        short_desc,
        long_desc,
        narrative,
        tags,
        content='files',
        content_rowid='rowid',
        tokenize='porter ascii'
    )
    """,

    # Triggers to keep FTS in sync with files
    """
    CREATE TRIGGER IF NOT EXISTS files_ai
    AFTER INSERT ON files BEGIN
        INSERT INTO files_fts(rowid, name, short_desc, long_desc, narrative, tags)
        VALUES (new.rowid, new.name, new.short_desc,
                new.long_desc, new.narrative, new.tags);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS files_ad
    AFTER DELETE ON files BEGIN
        INSERT INTO files_fts(files_fts, rowid, name, short_desc, long_desc, narrative, tags)
        VALUES ('delete', old.rowid, old.name, old.short_desc,
                old.long_desc, old.narrative, old.tags);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS files_au
    AFTER UPDATE ON files BEGIN
        INSERT INTO files_fts(files_fts, rowid, name, short_desc, long_desc, narrative, tags)
        VALUES ('delete', old.rowid, old.name, old.short_desc,
                old.long_desc, old.narrative, old.tags);
        INSERT INTO files_fts(rowid, name, short_desc, long_desc, narrative, tags)
        VALUES (new.rowid, new.name, new.short_desc,
                new.long_desc, new.narrative, new.tags);
    END
    """,
]


def init_db():
    """Create all tables, indexes, and triggers if they do not exist."""
    c = _conn()
    for stmt in _DDL_STMTS:
        c.execute(stmt)
    c.commit()


def rebuild_fts():
    """Rebuild the FTS5 index from the files table (use after bulk imports)."""
    _conn().execute("INSERT INTO files_fts(files_fts) VALUES('rebuild')")
    _conn().commit()


# ── Write ─────────────────────────────────────────────────────────────────────

def index_file(
    path: str,
    folder: str,
    name: str,
    short_desc: str = "",
    long_desc: str = "",
    narrative: str = "",
    tags: list = None,
    sensitive: bool = False,
    manual_lock: bool = False,
    last_updated: str = "",
    last_error: str = "",
    file_size_bytes: int = 0,
):
    """
    Upsert a file record into the index.
    FTS5 stays in sync automatically via the au/ai triggers.
    """
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    file_ext  = Path(name).suffix.lower()

    _conn().execute(
        """
        INSERT INTO files
            (path, folder, name, short_desc, long_desc, narrative,
             tags, sensitive, manual_lock, last_updated, last_error,
             file_size_bytes, file_ext)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(path) DO UPDATE SET
            folder          = excluded.folder,
            name            = excluded.name,
            short_desc      = excluded.short_desc,
            long_desc       = excluded.long_desc,
            narrative       = excluded.narrative,
            tags            = excluded.tags,
            sensitive       = excluded.sensitive,
            manual_lock     = excluded.manual_lock,
            last_updated    = excluded.last_updated,
            last_error      = excluded.last_error,
            file_size_bytes = excluded.file_size_bytes,
            file_ext        = excluded.file_ext
        """,
        (path, folder, name, short_desc, long_desc, narrative,
         tags_json, int(sensitive), int(manual_lock), last_updated, last_error,
         file_size_bytes, file_ext),
    )
    _conn().commit()


def update_narrative(path: str, narrative: str):
    """Lightweight update — only the narrative field."""
    _conn().execute(
        "UPDATE files SET narrative=? WHERE path=?", (narrative, path)
    )
    _conn().commit()


def update_error(path: str, error: str):
    """Record a description error without clobbering other fields."""
    _conn().execute(
        "UPDATE files SET last_error=? WHERE path=?", (error, path)
    )
    _conn().commit()


def remove_file(path: str):
    """Remove a file from the index (called when file is deleted)."""
    _conn().execute("DELETE FROM files WHERE path=?", (path,))
    _conn().commit()


def add_history_entry(path: str, short_desc: str, long_desc: str, source: str = "ai"):
    """
    Push a description snapshot to the history ring buffer.
    Keeps the 20 most recent entries per file.
    """
    c = _conn()
    c.execute(
        """
        INSERT INTO file_history (path, short_desc, long_desc, source, recorded_at)
        VALUES (?,?,?,?,?)
        """,
        (path, short_desc, long_desc, source, datetime.now().isoformat()),
    )
    # Prune — keep newest 20
    c.execute(
        """
        DELETE FROM file_history
        WHERE path = ? AND id NOT IN (
            SELECT id FROM file_history WHERE path = ?
            ORDER BY id DESC LIMIT 20
        )
        """,
        (path, path),
    )
    c.commit()


# Read

def get_file_record(path: str) -> Optional[dict]:
    """Return the full index record for a file, or None."""
    row = _conn().execute(
        "SELECT * FROM files WHERE path=?", (path,)
    ).fetchone()
    if not row:
        return None
    rec = dict(row)
    try:
        rec["tags"] = json.loads(rec.get("tags", "[]"))
    except Exception:
        rec["tags"] = []
    return rec


def get_narrative(path: str) -> str:
    """Return the stored narrative for a file (empty string if none)."""
    row = _conn().execute(
        "SELECT narrative FROM files WHERE path=?", (path,)
    ).fetchone()
    return (row["narrative"] or "") if row else ""


def get_history(path: str, limit: int = 5) -> list[dict]:
    """
    Return the last `limit` description snapshots for a file,
    newest first.
    """
    rows = _conn().execute(
        """
        SELECT short_desc, long_desc, source, recorded_at
        FROM file_history
        WHERE path = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (path, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_tags(path: str) -> list[str]:
    """Return the tag list for a file."""
    row = _conn().execute(
        "SELECT tags FROM files WHERE path=?", (path,)
    ).fetchone()
    if not row:
        return []
    try:
        return json.loads(row["tags"] or "[]")
    except Exception:
        return []


# Search

def search(
    query: str,
    folder: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Full-text search across all indexed files using FTS5 (porter stemmer).
    Falls back to LIKE search if the FTS query is malformed.
    Returns list of dicts: {path, name, folder, short_desc, score}.
    """
    if not query.strip():
        return []

    # Sanitise for FTS5 — wrap in quotes to allow phrase search
    safe_q = '"' + query.replace('"', '""') + '"'
    c = _conn()

    try:
        if folder:
            rows = c.execute(
                """
                SELECT f.path, f.name, f.folder, f.short_desc, f.tags,
                       fts.rank AS score
                FROM files_fts fts
                JOIN files f ON f.rowid = fts.rowid
                WHERE files_fts MATCH ? AND f.folder = ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (safe_q, folder, limit),
            ).fetchall()
        else:
            rows = c.execute(
                """
                SELECT f.path, f.name, f.folder, f.short_desc, f.tags,
                       fts.rank AS score
                FROM files_fts fts
                JOIN files f ON f.rowid = fts.rowid
                WHERE files_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (safe_q, limit),
            ).fetchall()

    except sqlite3.OperationalError:
        # FTS query syntax error — fall back to LIKE
        like = f"%{query}%"
        if folder:
            rows = c.execute(
                """
                SELECT path, name, folder, short_desc, tags, 0 AS score
                FROM files
                WHERE folder = ?
                  AND (name LIKE ? OR short_desc LIKE ?
                       OR long_desc LIKE ? OR narrative LIKE ?)
                LIMIT ?
                """,
                (folder, like, like, like, like, limit),
            ).fetchall()
        else:
            rows = c.execute(
                """
                SELECT path, name, folder, short_desc, tags, 0 AS score
                FROM files
                WHERE name LIKE ? OR short_desc LIKE ?
                   OR long_desc LIKE ? OR narrative LIKE ?
                LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()

    results = []
    for r in rows:
        rec = dict(r)
        try:
            rec["tags"] = json.loads(rec.get("tags", "[]"))
        except Exception:
            rec["tags"] = []
        results.append(rec)
    return results


def search_by_tag(tag: str, folder: Optional[str] = None) -> list[dict]:
    """Find all files that contain a specific tag (exact match)."""
    tag_escaped = tag.replace('"', '\\"')
    like = f'%"{tag_escaped}"%'
    c = _conn()
    if folder:
        rows = c.execute(
            "SELECT path, name, folder, short_desc, tags FROM files "
            "WHERE folder=? AND tags LIKE ?",
            (folder, like),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT path, name, folder, short_desc, tags FROM files "
            "WHERE tags LIKE ?",
            (like,),
        ).fetchall()

    results = []
    for r in rows:
        rec = dict(r)
        try:
            rec["tags"] = json.loads(rec.get("tags", "[]"))
        except Exception:
            rec["tags"] = []
        # Double-check exact membership (JSON LIKE can false-positive)
        if tag in rec["tags"]:
            results.append(rec)
    return results


# Stats

def get_stats(folder: Optional[str] = None) -> dict:
    """
    Aggregate stats for a specific folder or the entire index.

    Returns:
        total_files, total_size, sensitive, manual, ai_described,
        no_description, has_error, ext_breakdown
    """
    c = _conn()
    p = (folder,) if folder else ()
    w = "WHERE folder=?" if folder else ""

    def q(sql, params=()):
        return c.execute(sql, params).fetchone()[0]

    total      = q(f"SELECT COUNT(*) FROM files {w}", p)
    sensitive  = q(f"SELECT COUNT(*) FROM files {w}{'AND' if folder else 'WHERE'} sensitive=1",
                   (folder, ) if folder else ())
    manual     = q(f"SELECT COUNT(*) FROM files {w}{'AND' if folder else 'WHERE'} manual_lock=1",
                   (folder, ) if folder else ())
    no_desc    = q(f"SELECT COUNT(*) FROM files {w}{'AND' if folder else 'WHERE'} "
                   f"(short_desc='' OR short_desc IS NULL)",
                   (folder, ) if folder else ())
    has_error  = q(f"SELECT COUNT(*) FROM files {w}{'AND' if folder else 'WHERE'} "
                   f"last_error!=''",
                   (folder, ) if folder else ())
    total_size = q(f"SELECT COALESCE(SUM(file_size_bytes),0) FROM files {w}", p)

    if folder:
        ext_rows = c.execute(
            "SELECT file_ext, COUNT(*) as cnt FROM files WHERE folder=? "
            "GROUP BY file_ext ORDER BY cnt DESC LIMIT 12",
            (folder,),
        ).fetchall()
    else:
        ext_rows = c.execute(
            "SELECT file_ext, COUNT(*) as cnt FROM files "
            "GROUP BY file_ext ORDER BY cnt DESC LIMIT 12"
        ).fetchall()

    return {
        "total_files":    total,
        "total_size":     total_size,
        "sensitive":      sensitive,
        "manual":         manual,
        "ai_described":   max(0, total - manual - no_desc),
        "no_description": no_desc,
        "has_error":      has_error,
        "ext_breakdown":  [dict(r) for r in ext_rows],
    }


def get_sensitive_files(folder: Optional[str] = None) -> list[dict]:
    """Return all sensitive-flagged files for the security audit panel."""
    c = _conn()
    if folder:
        rows = c.execute(
            """
            SELECT path, name, folder, short_desc, tags, last_updated
            FROM files
            WHERE sensitive=1 AND folder=?
            ORDER BY last_updated DESC
            """,
            (folder,),
        ).fetchall()
    else:
        rows = c.execute(
            """
            SELECT path, name, folder, short_desc, tags, last_updated
            FROM files WHERE sensitive=1
            ORDER BY last_updated DESC
            """
        ).fetchall()

    results = []
    for r in rows:
        rec = dict(r)
        try:
            rec["tags"] = json.loads(rec.get("tags", "[]"))
        except Exception:
            rec["tags"] = []
        results.append(rec)
    return results


def get_never_described(folder: Optional[str] = None) -> list[dict]:
    """Return files that have never been described."""
    c = _conn()
    if folder:
        rows = c.execute(
            "SELECT path, name, folder FROM files "
            "WHERE folder=? AND (short_desc='' OR short_desc IS NULL)",
            (folder,),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT path, name, folder FROM files "
            "WHERE short_desc='' OR short_desc IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Bulk indexing ─────────────────────────────────────────────────────────────

def index_from_sidecar(folder_path: str, sidecar: dict):
    """
    Bulk-index all file entries from a loaded sidecar dict.
    Called when a folder is first opened — fast catch-up for existing data.
    """
    for name, entry in sidecar.get("files", {}).items():
        full_path = os.path.join(folder_path, name)
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0
        index_file(
            path            = full_path,
            folder          = folder_path,
            name            = name,
            short_desc      = entry.get("short_desc", ""),
            long_desc       = entry.get("long_desc", ""),
            narrative       = entry.get("narrative", ""),
            tags            = entry.get("tags", []),
            sensitive       = entry.get("sensitive_detected", False),
            manual_lock     = entry.get("manual_lock", False),
            last_updated    = entry.get("last_updated", ""),
            last_error      = entry.get("last_error", ""),
            file_size_bytes = size,
        )

        # Also seed the SQLite history from the sidecar's history array
        for snap in reversed(entry.get("history", [])):
            add_history_entry(
                full_path,
                snap.get("short", ""),
                snap.get("long", ""),
                snap.get("source", "ai"),
            )
