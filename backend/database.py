"""Tiny SQLite persistence: sensor history and the alert log survive restarts."""
import json
import sqlite3
import threading
from pathlib import Path

from . import config

_lock = threading.Lock()
_conn = None
_inserts = 0


def init() -> None:
    global _conn
    if config.DB_PATH != ":memory:":
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    with _lock:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                ts REAL NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_readings_node_ts ON readings(node_id, ts);
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                node_id TEXT,
                node_name TEXT,
                hazard TEXT,
                level TEXT NOT NULL,
                score INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                reasons TEXT,
                action TEXT,
                image TEXT
            );
            CREATE TABLE IF NOT EXISTS sightings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                count INTEGER,
                lat REAL,
                lon REAL,
                camera TEXT,
                image TEXT,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                channel TEXT NOT NULL,
                min_level TEXT NOT NULL,
                created REAL NOT NULL,
                UNIQUE(phone, channel)
            );
            """
        )
        _conn.commit()


def insert_reading(node_id: str, ts: float, payload: dict) -> None:
    global _inserts
    with _lock:
        _conn.execute(
            "INSERT INTO readings(node_id, ts, payload) VALUES (?,?,?)", (node_id, ts, json.dumps(payload))
        )
        _inserts += 1
        if _inserts % 500 == 0:  # keep the file small: newest 3000 rows per node
            _conn.execute(
                """DELETE FROM readings WHERE id IN (
                     SELECT id FROM (
                       SELECT id, ROW_NUMBER() OVER (PARTITION BY node_id ORDER BY ts DESC) AS rn FROM readings
                     ) WHERE rn > 3000)"""
            )
        _conn.commit()


def node_history(node_id: str, limit: int = 100) -> list:
    with _lock:
        rows = _conn.execute(
            "SELECT ts, payload FROM readings WHERE node_id=? ORDER BY ts DESC LIMIT ?", (node_id, limit)
        ).fetchall()
    out = []
    for r in reversed(rows):
        item = json.loads(r["payload"])
        item["ts"] = r["ts"]
        out.append(item)
    return out


def insert_alert(alert: dict) -> int:
    with _lock:
        cur = _conn.execute(
            """INSERT INTO alerts(ts, kind, node_id, node_name, hazard, level, score, title, message, reasons, action, image)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                alert["ts"],
                alert["kind"],
                alert.get("node_id"),
                alert.get("node_name"),
                alert.get("hazard"),
                alert["level"],
                alert.get("score"),
                alert["title"],
                alert["message"],
                json.dumps(alert.get("reasons", [])),
                alert.get("action"),
                alert.get("image"),
            ),
        )
        _conn.commit()
        return cur.lastrowid


def recent_alerts(limit: int = 30) -> list:
    with _lock:
        rows = _conn.execute("SELECT * FROM alerts ORDER BY ts DESC, id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d["reasons"] or "[]")
        out.append(d)
    return out


# ---------------------------------------------------------------- subscribers
def add_subscriber(name: str, phone: str, channel: str, min_level: str, created: float) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO subscribers(name, phone, channel, min_level, created) VALUES (?,?,?,?,?) "
            "ON CONFLICT(phone, channel) DO UPDATE SET name=excluded.name, min_level=excluded.min_level",
            (name, phone, channel, min_level, created),
        )
        _conn.commit()
        row = _conn.execute("SELECT id FROM subscribers WHERE phone=? AND channel=?", (phone, channel)).fetchone()
        return row["id"]


def list_subscribers() -> list:
    with _lock:
        rows = _conn.execute("SELECT * FROM subscribers ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_subscriber(sub_id: int):
    with _lock:
        row = _conn.execute("SELECT * FROM subscribers WHERE id=?", (sub_id,)).fetchone()
    return dict(row) if row else None


def delete_subscriber(sub_id: int) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM subscribers WHERE id=?", (sub_id,))
        _conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------- sightings
def insert_sighting(s: dict) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO sightings(ts, kind, label, count, lat, lon, camera, image, note) VALUES (?,?,?,?,?,?,?,?,?)",
            (s["ts"], s["kind"], s["label"], s.get("count"), s.get("lat"), s.get("lon"), s.get("camera"), s.get("image"), s.get("note", "")),
        )
        _conn.commit()
        return cur.lastrowid


def recent_sightings(limit: int = 40) -> list:
    with _lock:
        rows = _conn.execute("SELECT * FROM sightings ORDER BY ts DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
