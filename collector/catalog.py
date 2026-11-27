"""SQLite storage for YouTube links, search provenance, and review decisions."""

from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3


STATUSES = ("pending", "accepted", "rejected")


@contextmanager
def connect(config):
    folder = Path(config["output_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "catalog.sqlite3")
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                class_name TEXT NOT NULL,
                language TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                channel TEXT,
                duration REAL,
                license TEXT,
                date_accessed TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')),
                PRIMARY KEY (class_name, language, video_id)
            );
            CREATE TABLE IF NOT EXISTS keywords (
                class_name TEXT NOT NULL,
                language TEXT NOT NULL,
                video_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                PRIMARY KEY (class_name, language, video_id, keyword),
                FOREIGN KEY (class_name, language, video_id)
                    REFERENCES videos (class_name, language, video_id)
            );
        """)
        yield db
    finally:
        db.close()


def video_key(video):
    return video["class_name"], video["language"], video["video_id"]


def count_active(db, class_name, language):
    return db.execute("""
        SELECT count(*) FROM videos
        WHERE class_name = ? AND language = ? AND status != 'rejected'
        """, (class_name, language)).fetchone()[0]


def save_videos(db, videos, *, quota=None):
    """Add unique links and their keywords, preserving saved decisions."""
    added = 0
    with db:
        db.execute("BEGIN IMMEDIATE")
        max_new = None
        if quota is not None:
            class_name, language, target = quota
            max_new = max(0, target - count_active(db, class_name, language))
        for video in videos:
            key = video_key(video)
            if max_new is None or added < max_new:
                result = db.execute("""
                    INSERT INTO videos (
                        class_name, language, video_id, title, channel, duration,
                        license, date_accessed, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (class_name, language, video_id) DO NOTHING
                    """, (
                        *key, video.get("title"), video.get("channel"),
                        video.get("duration"), video.get("license"),
                        video.get("date_accessed", date.today().isoformat()),
                        video.get("status", "pending"),
                    ))
                added += result.rowcount
            else:
                exists = db.execute("""
                    SELECT 1 FROM videos WHERE class_name = ? AND language = ? AND video_id = ?
                    """, key).fetchone()
                if not exists:
                    continue
            db.execute("""
                UPDATE videos SET title = coalesce(title, ?), channel = coalesce(channel, ?),
                    duration = coalesce(duration, ?), license = coalesce(license, ?)
                WHERE class_name = ? AND language = ? AND video_id = ?
                """, (video.get("title"), video.get("channel"), video.get("duration"),
                      video.get("license"), *key))
            db.executemany("""
                INSERT INTO keywords VALUES (?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """, ((*key, keyword) for keyword in video.get("keywords", ())))
    return added


def list_videos(db, *, language=None, status=None):
    filters = []
    params = []
    if language is not None:
        filters.append("videos.language = ?")
        params.append(language)
    if status is not None:
        filters.append("videos.status = ?")
        params.append(status)

    where = "WHERE " + " AND ".join(filters) if filters else ""
    rows = db.execute(f"""
        SELECT videos.*, keywords.keyword
        FROM videos
        LEFT JOIN keywords USING (class_name, language, video_id)
        {where}
        ORDER BY class_name, language, date_accessed, video_id, keyword
        """, params)
    videos = {}
    for row in rows:
        video = dict(row)
        keyword = video.pop("keyword")
        saved = videos.setdefault(video_key(video), {**video, "keywords": []})
        if keyword is not None:
            saved["keywords"].append(keyword)
    return list(videos.values())


def set_status(db, key, status):
    with db:
        result = db.execute("""
            UPDATE videos SET status = ?
            WHERE class_name = ? AND language = ? AND video_id = ?
            """, (status, *key))
    return result.rowcount == 1


def progress(db):
    rows = db.execute("""
        SELECT class_name, language, status, count(*) AS total FROM videos
        GROUP BY class_name, language, status ORDER BY class_name, language
    """)
    counts = {}
    for row in rows:
        key = row["class_name"], row["language"]
        statuses = counts.setdefault(key, dict.fromkeys(STATUSES, 0))
        statuses[row["status"]] = row["total"]
    return counts
