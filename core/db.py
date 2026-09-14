"""SQLite 数据层：课程、句子、复习卡片、练习记录、每日统计、AI 缓存。"""

import os
import sqlite3
from datetime import date, timedelta

from .config import app_dir
from .srs import Card, today_str

DB_PATH = os.path.join(app_dir(), "app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    level TEXT DEFAULT '中级',
    source TEXT DEFAULT 'builtin',
    builtin_key TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    seq INTEGER DEFAULT 0,
    en TEXT NOT NULL,
    zh TEXT DEFAULT '',
    note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER UNIQUE NOT NULL,
    ease REAL DEFAULT 2.5,
    interval REAL DEFAULT 0,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0,
    due TEXT NOT NULL,
    last_review TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL,
    rating INTEGER DEFAULT 4,
    wpm REAL DEFAULT 0,
    accuracy REAL DEFAULT 0,
    combo_max INTEGER DEFAULT 0,
    chars INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    reviewed_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS daily (
    date TEXT PRIMARY KEY,
    seconds INTEGER DEFAULT 0,
    sentences INTEGER DEFAULT 0,
    chars INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    combo_max INTEGER DEFAULT 0,
    score INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ai_cache (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pet (
    id INTEGER PRIMARY KEY CHECK (id=0),
    species TEXT DEFAULT 'cat',
    name TEXT DEFAULT '团子',
    exp INTEGER DEFAULT 0,
    unlocked TEXT DEFAULT '["cat"]'
);
CREATE TABLE IF NOT EXISTS lesson_star (
    course_id INTEGER NOT NULL,
    lesson_idx INTEGER NOT NULL,
    stars INTEGER DEFAULT 0,
    best INTEGER DEFAULT 0,
    done_at TEXT DEFAULT '',
    PRIMARY KEY (course_id, lesson_idx)
);
CREATE INDEX IF NOT EXISTS idx_sent_course ON sentences(course_id);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """为旧库补充后加的列。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(sentences)").fetchall()}
    if "phonics" not in cols:
        conn.execute("ALTER TABLE sentences ADD COLUMN phonics TEXT DEFAULT ''")


# ---------------------------------------------------------------- 课程
def list_courses():
    conn = connect()
    rows = conn.execute("SELECT * FROM courses ORDER BY id").fetchall()
    conn.close()
    return rows


def get_course(course_id):
    conn = connect()
    row = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    conn.close()
    return row


def add_course(title, description="", level="中级", source="custom", builtin_key=""):
    conn = connect()
    cur = conn.execute(
        "INSERT INTO courses (title, description, level, source, builtin_key, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (title, description, level, source, builtin_key, today_str()))
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def delete_course(course_id):
    conn = connect()
    conn.execute("DELETE FROM cards WHERE sentence_id IN "
                 "(SELECT id FROM sentences WHERE course_id=?)", (course_id,))
    conn.execute("DELETE FROM reviews WHERE sentence_id IN "
                 "(SELECT id FROM sentences WHERE course_id=?)", (course_id,))
    conn.execute("DELETE FROM sentences WHERE course_id=?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()


def add_sentences(course_id, items):
    """items: [(en, zh), (en, zh, note) 或 (en, zh, note, phonics)]

    seq 从当前最大值+1 接续：新建课程时从 0 开始，增量补句不与旧句冲突。
    """
    conn = connect()
    base = conn.execute(
        "SELECT COALESCE(MAX(seq), -1) FROM sentences WHERE course_id=?",
        (course_id,)).fetchone()[0] + 1
    for i, item in enumerate(items):
        parts = (list(item) + ["", "", ""])[:4]
        en, zh, note, phonics = parts
        conn.execute(
            "INSERT INTO sentences (course_id, seq, en, zh, note, phonics) VALUES (?,?,?,?,?,?)",
            (course_id, base + i, (en or "").strip(), zh, note, phonics))
    conn.commit()
    conn.close()


def get_course_by_key(builtin_key):
    conn = connect()
    row = conn.execute("SELECT * FROM courses WHERE builtin_key=?", (builtin_key,)).fetchone()
    conn.close()
    return row


def list_sentences(course_id):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM sentences WHERE course_id=? ORDER BY seq, id", (course_id,)).fetchall()
    conn.close()
    return rows


def count_sentences(course_id):
    conn = connect()
    n = conn.execute("SELECT COUNT(*) c FROM sentences WHERE course_id=?", (course_id,)).fetchone()["c"]
    conn.close()
    return n


def get_sentence(sid):
    conn = connect()
    row = conn.execute("SELECT * FROM sentences WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row


def sentences_by_en(texts):
    """按英文原文取出句子行（保持传入顺序，去重）。"""
    out, seen = [], set()
    conn = connect()
    for t in texts:
        if t in seen:
            continue
        seen.add(t)
        row = conn.execute("SELECT * FROM sentences WHERE en=? ORDER BY id LIMIT 1", (t,)).fetchone()
        if row is not None:
            out.append(row)
    conn.close()
    return out


def search_sentences(keyword, limit=50):
    conn = connect()
    rows = conn.execute(
        "SELECT s.*, c.title AS course_title FROM sentences s "
        "JOIN courses c ON c.id=s.course_id "
        "WHERE s.en LIKE ? OR s.zh LIKE ? LIMIT ?",
        ("%%%s%%" % keyword, "%%%s%%" % keyword, limit)).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------- 复习卡片
def get_or_create_card(sentence_id):
    conn = connect()
    row = conn.execute("SELECT * FROM cards WHERE sentence_id=?", (sentence_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO cards (sentence_id, ease, interval, reps, lapses, due) "
            "VALUES (?,2.5,0,0,0,?)", (sentence_id, today_str()))
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE sentence_id=?", (sentence_id,)).fetchone()
    conn.close()
    return _to_card(row)


def get_card(sentence_id):
    conn = connect()
    row = conn.execute("SELECT * FROM cards WHERE sentence_id=?", (sentence_id,)).fetchone()
    conn.close()
    return _to_card(row) if row else None


def _to_card(row):
    return Card(row["id"], row["sentence_id"], row["ease"], row["interval"],
                row["reps"], row["lapses"], row["due"], row["last_review"])


def save_card(card):
    conn = connect()
    conn.execute(
        "UPDATE cards SET ease=?, interval=?, reps=?, lapses=?, due=?, last_review=? WHERE id=?",
        (card.ease, card.interval, card.reps, card.lapses, card.due, card.last_review, card.id))
    conn.commit()
    conn.close()


def due_course_cards(course_id, limit=20):
    """课程内到期/未学过的句子。"""
    conn = connect()
    rows = conn.execute(
        "SELECT s.* FROM sentences s LEFT JOIN cards c ON c.sentence_id=s.id "
        "WHERE s.course_id=? AND (c.id IS NULL OR c.due<=?) ORDER BY s.seq, s.id LIMIT ?",
        (course_id, today_str(), limit)).fetchall()
    conn.close()
    return rows


def new_course_sentences(course_id, limit=20):
    """课程内还没学过的句子。"""
    conn = connect()
    rows = conn.execute(
        "SELECT s.* FROM sentences s LEFT JOIN cards c ON c.sentence_id=s.id "
        "WHERE s.course_id=? AND c.id IS NULL ORDER BY s.seq, s.id LIMIT ?",
        (course_id, limit)).fetchall()
    conn.close()
    return rows


def due_count(course_id):
    conn = connect()
    n = conn.execute(
        "SELECT COUNT(*) c FROM sentences s JOIN cards k ON k.sentence_id=s.id "
        "WHERE s.course_id=? AND k.due<=?", (course_id, today_str())).fetchone()["c"]
    conn.close()
    return n


def all_due_sentences(limit=100):
    conn = connect()
    rows = conn.execute(
        "SELECT s.*, c.title AS course_title FROM sentences s "
        "JOIN cards c2 ON c2.sentence_id=s.id JOIN courses c ON c.id=s.course_id "
        "WHERE c2.due<=? ORDER BY c2.due LIMIT ?", (today_str(), limit)).fetchall()
    conn.close()
    return rows


def srs_counts():
    conn = connect()
    due = conn.execute("SELECT COUNT(*) c FROM cards WHERE due<=?", (today_str(),)).fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    learned = conn.execute("SELECT COUNT(*) c FROM cards WHERE reps>0").fetchone()["c"]
    conn.close()
    return {"due": due, "total": total, "learned": learned}


# ---------------------------------------------------------------- 记录与统计
def add_review(sentence_id, rating, wpm, accuracy, combo_max, chars, duration_ms):
    from .srs import _now_str
    conn = connect()
    conn.execute(
        "INSERT INTO reviews (sentence_id, rating, wpm, accuracy, combo_max, chars, duration_ms, reviewed_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (sentence_id, rating, wpm, accuracy, combo_max, chars, duration_ms, _now_str()))
    conn.commit()
    conn.close()


def bump_daily(seconds=0, sentences=0, chars=0, errors=0, combo_max=0, score=0):
    d = today_str()
    conn = connect()
    conn.execute("INSERT OR IGNORE INTO daily (date) VALUES (?)", (d,))
    conn.execute(
        "UPDATE daily SET seconds=seconds+?, sentences=sentences+?, chars=chars+?, "
        "errors=errors+?, score=score+?, combo_max=MAX(combo_max,?) WHERE date=?",
        (int(seconds), sentences, chars, errors, int(score), combo_max, d))
    conn.commit()
    conn.close()


def get_daily(date_str=None):
    d = date_str or today_str()
    conn = connect()
    row = conn.execute("SELECT * FROM daily WHERE date=?", (d,)).fetchone()
    conn.close()
    if row is None:
        return {"date": d, "seconds": 0, "sentences": 0, "chars": 0,
                "errors": 0, "combo_max": 0, "score": 0}
    return dict(row)


def recent_daily(days=30):
    conn = connect()
    rows = conn.execute("SELECT * FROM daily ORDER BY date DESC LIMIT ?", (days,)).fetchall()
    conn.close()
    by_date = {r["date"]: dict(r) for r in rows}
    out = []
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append(by_date.get(d, {"date": d, "seconds": 0, "sentences": 0,
                                   "chars": 0, "errors": 0, "combo_max": 0, "score": 0}))
    return out


def overall_stats():
    conn = connect()
    row = conn.execute(
        "SELECT COUNT(*) n, AVG(wpm) wpm, AVG(accuracy) acc, MAX(combo_max) combo "
        "FROM reviews").fetchone()
    perfect = conn.execute("SELECT COUNT(*) c FROM reviews WHERE rating=5").fetchone()["c"]
    seconds = conn.execute("SELECT SUM(seconds) s FROM daily").fetchone()["s"] or 0
    conn.close()
    return {
        "reviews": row["n"] or 0,
        "avg_wpm": row["wpm"] or 0.0,
        "avg_accuracy": row["acc"] or 0.0,
        "max_combo": row["combo"] or 0,
        "perfect": perfect,
        "total_seconds": seconds,
    }


# ---------------------------------------------------------------- AI 缓存
def cache_get(key):
    conn = connect()
    row = conn.execute("SELECT value FROM ai_cache WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def cache_put(key, value):
    conn = connect()
    conn.execute("INSERT OR REPLACE INTO ai_cache (key, value, created_at) VALUES (?,?,?)",
                 (key, value, today_str()))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- 积分/宠物/关卡
def profile_get(key, default=""):
    conn = connect()
    row = conn.execute("SELECT value FROM profile WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def profile_set(key, value):
    conn = connect()
    conn.execute("INSERT OR REPLACE INTO profile (key, value) VALUES (?,?)",
                 (str(key), str(value)))
    conn.commit()
    conn.close()


def get_points():
    try:
        return int(profile_get("points", "0"))
    except (TypeError, ValueError):
        return 0


def add_points(n):
    """积分变动（n 可为负），返回变动后的余额。"""
    pts = max(0, get_points() + int(n))
    profile_set("points", pts)
    return pts


def pet_get():
    conn = connect()
    conn.execute("INSERT OR IGNORE INTO pet (id) VALUES (0)")
    row = conn.execute("SELECT * FROM pet WHERE id=0").fetchone()
    conn.close()
    return dict(row)


def pet_save(species, name, exp, unlocked):
    import json
    conn = connect()
    conn.execute(
        "UPDATE pet SET species=?, name=?, exp=?, unlocked=? WHERE id=0",
        (species, name, int(exp), json.dumps(list(unlocked))))
    conn.commit()
    conn.close()


def lesson_stars(course_id):
    """返回 {lesson_idx: stars}。"""
    conn = connect()
    rows = conn.execute(
        "SELECT lesson_idx, stars FROM lesson_star WHERE course_id=? AND stars>0",
        (course_id,)).fetchall()
    conn.close()
    return {r["lesson_idx"]: r["stars"] for r in rows}


def lesson_save_star(course_id, lesson_idx, stars, best):
    """保存关卡星级（只升不降）。"""
    conn = connect()
    conn.execute(
        "INSERT INTO lesson_star (course_id, lesson_idx, stars, best, done_at)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(course_id, lesson_idx) DO UPDATE SET"
        " stars=MAX(stars, excluded.stars), best=MAX(best, excluded.best),"
        " done_at=excluded.done_at",
        (course_id, lesson_idx, int(stars), int(best), today_str()))
    conn.commit()
    conn.close()


def sentences_range(course_id, start_seq, end_seq):
    """按 seq 区间取句（闭区间），用于关卡模式。"""
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM sentences WHERE course_id=? AND seq BETWEEN ? AND ?"
        " ORDER BY seq, id",
        (course_id, start_seq, end_seq)).fetchall()
    conn.close()
    return rows
