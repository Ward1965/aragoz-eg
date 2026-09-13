import json
import re
import datetime
import sqlite3
import os
import sys
import base64
from typing import List, Dict, Optional, Tuple

from .logging_setup import get_logger

log = get_logger("storage")

import threading
_db_lock = threading.RLock()

if getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        BASE_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Aragoz Lite")
        os.makedirs(BASE_DIR, exist_ok=True)
    else:
        BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DB_PATH = os.path.join(BASE_DIR, "configs.db")

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

_DB_INITIALIZED = False


def is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    m = _ISO_DATE_RE.match(str(expires_at))
    if not m:
        return False
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" < datetime.date.today().isoformat()


# الحد الأقصى لعمر الكونفيغ/الملف: أي كونفيغ أقدم من شهر يُستبعد من النتائج فقط (لا يُحذف)
MAX_AGE_DAYS = 30


def _fresh_cutoff() -> str:
    """تاريخ بداية النافذة المسموحة (اليوم - MAX_AGE_DAYS) بصيغة ISO للمقارنة مع created_at."""
    return (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()


_FRESH_WHERE = (
    "(created_at IS NULL OR created_at = '' "
    "OR created_at LIKE '____-__-__%' OR created_at >= ?)"
)


def _fresh_params() -> list:
    return [_fresh_cutoff()]


def _time_where() -> Tuple[str, list]:
    """شروط الوقت الموحدة: يُستبعد انتهاء الصلاحية + الكونفيغات الأقدم من شهر."""
    today = datetime.date.today().isoformat()
    where = (
        "(expires_at IS NULL OR expires_at = '' OR expires_at NOT LIKE '____-__-__%' OR expires_at >= ?) "
        "AND " + _FRESH_WHERE
    )
    return where, [today] + _fresh_params()


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
    except Exception:
        pass
    return conn


def _reset_db_file():
    """حذف ملف قاعدة البيانات مع كل تشغيل حتى تُنشأ من جديد فارغة."""
    for suffix in ("", "-wal", "-shm"):
        p = DB_PATH + suffix
        try:
            if os.path.exists(p):
                os.remove(p)
                log.info("Removed %s (fresh database per launch)", p)
        except Exception as e:
            log.warning("Failed to remove %s: %s", p, e)


def init_db():
    global _DB_INITIALIZED
    with _db_lock:
        if _DB_INITIALIZED:
            return True

    conn = None
    try:
        _reset_db_file()
        conn = _get_conn()
        conn.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol TEXT NOT NULL,
                    protocol_type TEXT NOT NULL,
                    name TEXT,
                    server TEXT,
                    port INTEGER,
                    raw TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ping_ms INTEGER
                )
            """)
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_configs_dedup ON configs (protocol_type, server, port)")
        except Exception as e:
            log.debug("Dedup index already exists: %s", e)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_configs_server_port ON configs (server, port)")
        except Exception as e:
            log.debug("Server/port index failed: %s", e)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_configs_ping_ms ON configs (ping_ms)")
        except Exception as e:
            log.debug("Ping_ms index failed: %s", e)
        try:
            conn.execute("ALTER TABLE configs ADD COLUMN ping_ms INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE configs ADD COLUMN expires_at TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE configs ADD COLUMN country TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ping_cache (
                    server TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    ms INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (server, port)
                )
            """)
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("DELETE FROM configs WHERE id NOT IN (SELECT MIN(id) FROM configs GROUP BY protocol_type, server, port)")
        except Exception as e:
            log.warning("Dedup cleanup failed: %s", e)

        try:
            today = datetime.date.today().isoformat()
            deleted = conn.execute(
                "DELETE FROM configs WHERE expires_at IS NOT NULL AND expires_at != '' AND expires_at LIKE '____-__-__%' AND expires_at < ?",
                (today,),
            ).rowcount
            if deleted:
                log.info("Removed %d expired configs on startup", deleted)
        except Exception as e:
            log.warning("Expired config cleanup failed: %s", e)

        conn.commit()
        _DB_INITIALIZED = True
        log.info("Database initialized at %s", DB_PATH)
        return True
    except Exception as e:
        log.error("Failed to initialize database: %s", e)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _ensure_db():
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with _db_lock:
        if _DB_INITIALIZED:
            return
        init_db()


_SAVE_SQL = """
    INSERT INTO configs (protocol, protocol_type, name, server, port, raw, expires_at, country)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(protocol_type, server, port) DO UPDATE SET
        protocol = excluded.protocol,
        name = excluded.name,
        raw = excluded.raw,
        country = excluded.country,
        expires_at = CASE
            WHEN excluded.expires_at IS NULL OR excluded.expires_at = '' THEN expires_at
            ELSE excluded.expires_at
        END
"""


def save_configs(configs: List[Dict]) -> int:
    _ensure_db()
    rows = []
    skipped = 0
    seen_raw: set = set()
    for cfg in configs:
        if is_expired(cfg.get("expires_at")):
            skipped += 1
            continue
        raw = (cfg.get("raw") or "").strip()
        if raw and raw in seen_raw:
            skipped += 1
            continue
        if raw:
            seen_raw.add(raw)
        rows.append(
            (
                cfg.get("protocol", ""),
                cfg.get("protocol_type", ""),
                cfg.get("name", ""),
                (cfg.get("server", "") or "").strip(),
                cfg.get("port", 0),
                cfg.get("raw", ""),
                cfg.get("expires_at", ""),
                cfg.get("country", ""),
            )
        )
    if not rows:
        if skipped:
            log.debug("Skipped %d expired/duplicate configs", skipped)
        return 0
    conn = _get_conn()
    try:
        with _db_lock:
            conn.executemany(_SAVE_SQL, rows)
            conn.commit()
        count = len(rows)
    except Exception as e:
        log.warning("Batch save failed (%d rows), falling back to row-by-row: %s", len(rows), e)
        count = 0
        with _db_lock:
            for r in rows:
                try:
                    conn.execute(_SAVE_SQL, r)
                    count += 1
                except Exception as e2:
                    log.warning("Failed to save config row: %s", e2)
            conn.commit()
    finally:
        conn.close()
    if skipped:
        log.debug("Skipped %d expired/duplicate configs", skipped)
    return count


def get_all_configs() -> List[Dict]:
    _ensure_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM configs ORDER BY protocol_type, name").fetchall()
    conn.close()
    cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    fresh = []
    for row in rows:
        if is_expired(row["expires_at"]):
            continue
        stored = str(row["created_at"] or "")[:10]
        if stored and stored.startswith("____") is False and stored >= cutoff:
            fresh.append(dict(row))
        elif not stored or not stored.startswith(tuple("0123456789")):
            fresh.append(dict(row))
    return fresh


_SORT_KEYS = {"name", "server", "protocol", "protocol_type", "port", "country", "expires_at", "created_at"}


def search_configs(
    query: str = "",
    protocols: Optional[list] = None,
    sort_key: str = "",
    sort_dir: int = 1,
    offset: int = 0,
    limit: int = 1000,
    countries: Optional[list] = None,
    ping_cats: Optional[set] = None,
):
    _ensure_db()
    where_ts, ts_params = _time_where()
    where = [where_ts]
    params: list = ts_params

    if protocols:
        ph = ",".join("?" * len(protocols))
        where.append(f"protocol_type IN ({ph})")
        params.extend(protocols)

    if countries:
        ph = ",".join("?" * len(countries))
        where.append(f"COALESCE(country, '') IN ({ph})")
        params.extend(countries)

    if ping_cats:
        cats = set(ping_cats)
        branches = []
        if "untested" in cats:
            branches.append("ping_ms IS NULL")
        if "dead" in cats:
            branches.append("ping_ms IS NOT NULL AND ping_ms < 0")
        if "fast" in cats:
            branches.append("ping_ms >= 0 AND ping_ms < 150")
        if "mid" in cats:
            branches.append("ping_ms >= 150 AND ping_ms < 300")
        if "slow" in cats:
            branches.append("ping_ms IS NOT NULL AND ping_ms >= 300")
        if branches:
            where.append("(" + " OR ".join(branches) + ")")

    q = (query or "").strip()
    if q:
        like = "%" + q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_") + "%"
        where.append(
            "(name LIKE ? ESCAPE '\\' OR server LIKE ? ESCAPE '\\' OR protocol LIKE ? ESCAPE '\\' "
            "OR country LIKE ? ESCAPE '\\' OR raw LIKE ? ESCAPE '\\')"
        )
        params.extend([like] * 5)

    wh = " AND ".join(where)

    order = ""
    if sort_key in _SORT_KEYS:
        col = sort_key if sort_key != "protocol" else "protocol_type"
        expr = col
        if col == "port":
            expr = "CAST(port AS INTEGER)"
        elif col in ("expires_at", "created_at"):
            expr = f"CASE WHEN {col} IS NULL OR {col} = '' THEN '5999-12-31' ELSE {col} END"
        direction = "ASC" if int(sort_dir or 1) > 0 else "DESC"
        order = f" ORDER BY {expr} {direction}, id {direction}"

    conn = _get_conn()
    total = conn.execute(f"SELECT COUNT(*) FROM configs WHERE {wh}", params).fetchone()[0]
    limit_n = int(limit)
    offset_n = int(offset)
    if limit_n <= 0:
        rows = conn.execute(
            f"SELECT * FROM configs WHERE {wh}{order}",
            params,
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM configs WHERE {wh}{order} LIMIT ? OFFSET ?",
            params + [limit_n, offset_n],
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows], total


def get_config_count() -> int:
    _ensure_db()
    conn = _get_conn()
    where_ts, ts_params = _time_where()
    n = conn.execute(
        "SELECT COUNT(*) FROM configs WHERE " + where_ts,
        ts_params,
    ).fetchone()[0]
    conn.close()
    return n


def get_config_by_id(config_id: int) -> Optional[Dict]:
    _ensure_db()
    conn = _get_conn()
    row = conn.execute("SELECT * FROM configs WHERE id = ?", (config_id,)).fetchone()
    conn.close()
    if not row or is_expired(row["expires_at"]):
        return None
    stored = str(row["created_at"] or "")[:10]
    cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    if stored and stored[:1].isdigit() and stored < cutoff:
        return None
    return dict(row)


def delete_config(config_id: int) -> bool:
    _ensure_db()
    conn = _get_conn()
    conn.execute("DELETE FROM configs WHERE id = ?", (config_id,))
    conn.commit()
    deleted = conn.total_changes > 0
    conn.close()
    return deleted


def clear_all_configs():
    _ensure_db()
    conn = _get_conn()
    conn.execute("DELETE FROM configs")
    conn.commit()
    conn.close()
    log.info("All configs cleared")


def delete_configs_matching(
    query: str = "",
    protocols: Optional[list] = None,
    countries: Optional[list] = None,
) -> int:
    """Delete only the configs matching the same filters as search_configs. Returns the count deleted."""
    _ensure_db()
    where_ts, ts_params = _time_where()
    where = [where_ts]
    params: list = ts_params

    if protocols:
        ph = ",".join("?" * len(protocols))
        where.append(f"protocol_type IN ({ph})")
        params.extend(protocols)

    if countries:
        ph = ",".join("?" * len(countries))
        where.append(f"COALESCE(country, '') IN ({ph})")
        params.extend(countries)

    q = (query or "").strip()
    if q:
        like = "%" + q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_") + "%"
        where.append(
            "(name LIKE ? ESCAPE '\\' OR server LIKE ? ESCAPE '\\' OR protocol LIKE ? ESCAPE '\\' "
            "OR country LIKE ? ESCAPE '\\' OR raw LIKE ? ESCAPE '\\')"
        )
        params.extend([like] * 5)

    conn = _get_conn()
    conn.execute(f"DELETE FROM configs WHERE {' AND '.join(where)}", params)
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    log.info("Deleted %d configs matching filters", deleted)
    return deleted


def delete_configs_by_ids(config_ids: List[int]) -> int:
    """Delete specific configs by id. Returns the count deleted."""
    if not config_ids:
        return 0
    _ensure_db()
    conn = _get_conn()
    for i in range(0, len(config_ids), 500):
        chunk = config_ids[i : i + 500]
        ph = ",".join("?" * len(chunk))
        conn.execute(f"DELETE FROM configs WHERE id IN ({ph})", chunk)
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    log.info("Deleted %d configs by id", deleted)
    return deleted


def save_ping_cache(entries: Dict[str, int]) -> int:
    """Persist ping results {server:port: ms} so the filter survives restarts."""
    _ensure_db()
    conn = _get_conn()
    rows = []
    for key, ms in entries.items():
        try:
            server, _, port = key.rpartition(":")
            if not server or not port.isdigit():
                continue
            rows.append((server, int(port), int(ms)))
        except (ValueError, TypeError):
            continue
    if not rows:
        return 0
    try:
        conn.execute("DELETE FROM ping_cache")
        conn.executemany(
            "INSERT OR REPLACE INTO ping_cache (server, port, ms) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception as e:
        log.warning("Failed to save ping cache: %s", e)
        conn.rollback()
    finally:
        conn.close()
    return len(rows)


def load_ping_cache() -> Dict[str, int]:
    _ensure_db()
    conn = _get_conn()
    rows = conn.execute("SELECT server, port, ms FROM ping_cache").fetchall()
    conn.close()
    return {f"{row['server']}:{int(row['port'])}": int(row['ms']) for row in rows}


def clear_ping_cache():
    _ensure_db()
    conn = _get_conn()
    conn.execute("DELETE FROM ping_cache")
    conn.commit()
    conn.close()


def update_ping_ms(entries: Dict[str, int]) -> int:
    """Write per-server ping results onto the configs table (column ping_ms)."""
    if not entries:
        return 0
    _ensure_db()
    rows = []
    for key, ms in entries.items():
        try:
            server, _, port = key.rpartition(":")
            if not server or not port.isdigit():
                continue
            rows.append((int(ms), server, int(port)))
        except (ValueError, TypeError):
            continue
    if not rows:
        return 0
    conn = _get_conn()
    try:
        with _db_lock:
            conn.executemany(
                "UPDATE configs SET ping_ms = ? WHERE server = ? AND port = ?",
                rows,
            )
            conn.commit()
        return conn.total_changes
    except Exception as e:
        log.warning("Failed to update ping_ms: %s", e)
        conn.rollback()
        return 0
    finally:
        conn.close()


def clear_ping_ms():
    _ensure_db()
    conn = _get_conn()
    try:
        with _db_lock:
            conn.execute("UPDATE configs SET ping_ms = NULL")
            conn.commit()
    except Exception as e:
        log.warning("Failed to clear ping_ms: %s", e)
    finally:
        conn.close()


def get_ping_stats_sql() -> Dict[str, int]:
    """Fast SQL-based ping stats matching the old in-Python get_ping_stats."""
    _ensure_db()
    where_ts, ts_params = _time_where()
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN ping_ms IS NULL THEN 1 ELSE 0 END) AS untested, "
            "SUM(CASE WHEN ping_ms IS NOT NULL AND ping_ms < 0 THEN 1 ELSE 0 END) AS dead, "
            "SUM(CASE WHEN ping_ms >= 0 AND ping_ms < 150 THEN 1 ELSE 0 END) AS fast, "
            "SUM(CASE WHEN ping_ms >= 150 AND ping_ms < 300 THEN 1 ELSE 0 END) AS mid, "
            "SUM(CASE WHEN ping_ms IS NOT NULL AND ping_ms >= 300 THEN 1 ELSE 0 END) AS slow, "
            "COUNT(*) AS total "
            "FROM configs WHERE " + where_ts,
            ts_params,
        ).fetchone()
    except Exception as e:
        log.warning("get_ping_stats_sql failed: %s", e)
        return {"fast": 0, "mid": 0, "slow": 0, "dead": 0, "untested": 0, "total": 0}
    finally:
        conn.close()
    return {
        "fast": int(row["fast"] or 0),
        "mid": int(row["mid"] or 0),
        "slow": int(row["slow"] or 0),
        "dead": int(row["dead"] or 0),
        "untested": int(row["untested"] or 0),
        "total": int(row["total"] or 0),
    }


_DEAD_LINKS_PATH = os.path.join(BASE_DIR, "dead_links.json")
_dead_links: Optional[set] = None


def _load_dead_set() -> set:
    global _dead_links
    if _dead_links is None:
        _dead_links = set()
        try:
            with open(_DEAD_LINKS_PATH, "r", encoding="utf-8") as f:
                _dead_links = set(json.load(f))
            log.debug("Loaded %d dead links", len(_dead_links))
        except FileNotFoundError:
            _dead_links = set()
        except Exception as e:
            log.warning("Failed to load dead links: %s", e)
            _dead_links = set()
    return _dead_links


def is_dead_link(url: str) -> bool:
    return url in _load_dead_set()


def clear_dead_links():
    global _dead_links
    _dead_links = set()
    try:
        with open(_DEAD_LINKS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)
        log.info("Startup: cleared dead-links cache")
    except Exception as e:
        log.warning("Failed to clear dead links: %s", e)


def mark_dead_link(url: str):
    global _dead_links
    dead = _load_dead_set()
    if url in dead:
        return
    dead.add(url)
    if len(dead) > 10000:
        dead = set(list(dead)[-10000:])
        _dead_links = dead
    try:
        with open(_DEAD_LINKS_PATH, "w", encoding="utf-8") as f:
            json.dump(list(dead), f, ensure_ascii=False)
    except Exception as e:
        log.warning("Failed to save dead links: %s", e)


def get_protocol_counts() -> Dict[str, int]:
    _ensure_db()
    conn = _get_conn()
    where_ts, ts_params = _time_where()
    rows = conn.execute(
        "SELECT protocol_type, COUNT(*) as count FROM configs "
        "WHERE " + where_ts + " "
        "GROUP BY protocol_type ORDER BY count DESC",
        ts_params,
    ).fetchall()
    conn.close()
    return {row["protocol_type"]: row["count"] for row in rows}


def get_total_configs() -> int:
    _ensure_db()
    conn = _get_conn()
    where_ts, ts_params = _time_where()
    n = conn.execute(
        "SELECT COUNT(*) FROM configs WHERE " + where_ts,
        ts_params,
    ).fetchone()[0]
    conn.close()
    return int(n)


def get_country_counts(top: int = 30) -> List[Dict]:
    _ensure_db()
    conn = _get_conn()
    where_ts, ts_params = _time_where()
    ts_params = ts_params + [int(top)]
    rows = conn.execute(
        "SELECT COALESCE(NULLIF(country, ''), '(unknown)') AS country, COUNT(*) as count FROM configs "
        "WHERE " + where_ts + " "
        "GROUP BY COALESCE(NULLIF(country, ''), '(unknown)') ORDER BY count DESC LIMIT ?",
        ts_params,
    ).fetchall()
    conn.close()
    return [{"country": row["country"], "count": row["count"]} for row in rows]


def export_as_text(configs: List[Dict]) -> str:
    lines = []
    for cfg in configs:
        raw = cfg.get("raw", "")
        if raw:
            lines.append(raw)
    return "\n".join(lines)


def export_as_base64(configs: List[Dict]) -> str:
    text = export_as_text(configs)
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def save_to_json(configs: List[Dict], filepath: str):
    clean = []
    for cfg in configs:
        entry = {k: v for k, v in cfg.items() if k not in ("id", "created_at", "raw")}
        clean.append(entry)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)


def load_from_json(filepath: str) -> List[Dict]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CLASH_TYPES = {
    "VLESS": "vless",
    "VMESS": "vmess",
    "TROJAN": "trojan",
    "SHADOWSOCKS": "ss",
    "HYSTERIA2": "hysteria2",
    "TUIC": "tuic",
    "WIREGUARD": "wireguard",
    "SOCKS5": "socks5",
    "SOCKS4": "socks4",
    "HTTP": "http",
    "HTTPS": "http",
}


def _yq(s) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_clash_yaml(configs: List[Dict]) -> str:
    if not configs:
        return "proxies: []\n"
    blocks = []
    for cfg in configs:
        ctype = CLASH_TYPES.get(str(cfg.get("protocol_type", "")).upper())
        server = cfg.get("server", "") or ""
        if not ctype or not server:
            continue
        name = cfg.get("name") or f"{server}:{cfg.get('port', 0)}"
        entry = [
            "  - name: " + _yq(name),
            "    type: " + ctype,
            "    server: " + _yq(server),
            "    port: " + str(int(cfg.get("port") or 0)),
            "    udp: true",
        ]

        def opt(key, yaml_key=None, as_bool=False):
            val = cfg.get(key)
            if val in (None, "", 0):
                return
            if as_bool:
                entry.append("    {}: true".format(yaml_key or key))
            else:
                entry.append("    {}: {}".format(yaml_key or key, _yq(val)))

        if ctype == "vmess":
            entry.append("    cipher: auto")
            opt("uuid")
            opt("alter_id", "alterId")
            opt("network")
            opt("host")
            opt("path")
            if cfg.get("tls"):
                entry.append("    tls: true")
            opt("sni", "servername")
        elif ctype == "vless":
            opt("uuid")
            opt("flow")
            opt("network")
            security = cfg.get("security")
            if security not in (None, "", "none", "0", "false"):
                entry.append("    tls: true")
            opt("sni", "servername")
        elif ctype == "trojan":
            opt("password")
            opt("sni", "servername")
            opt("alpn")
        elif ctype == "ss":
            opt("cipher")
            opt("password")
        elif ctype == "hysteria2":
            opt("password")
            opt("sni")
        elif ctype == "tuic":
            opt("uuid")
            opt("password")
            opt("sni")
            opt("congestion_control", "congestion-controller")
        elif ctype == "wireguard":
            opt("private_key", "private-key")
            opt("public_key", "public-key")
            opt("address")
            opt("dns")
        blocks.append("\n".join(entry))
    return "proxies:\n" + "\n".join(blocks) + "\n"
