import json
import re
import datetime
import sqlite3
import os
import sys
import base64
from typing import List, Dict, Optional


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


def is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    m = _ISO_DATE_RE.match(str(expires_at))
    if not m:
        return False
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" < datetime.date.today().isoformat()


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    try:
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_configs_dedup ON configs (protocol_type, server, port)")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE configs ADD COLUMN expires_at TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE configs ADD COLUMN country TEXT")
        except Exception:
            pass
        try:
            conn.execute("DELETE FROM configs WHERE id NOT IN (SELECT MIN(id) FROM configs GROUP BY protocol_type, server, port)")
        except Exception:
            pass
        try:
            today = datetime.date.today().isoformat()
            conn.execute("DELETE FROM configs WHERE expires_at IS NOT NULL AND expires_at != '' AND expires_at LIKE '____-__-__%' AND expires_at < ?", (today,))
        except Exception:
            pass
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def save_configs(configs: List[Dict]) -> int:
    conn = _get_conn()
    count = 0
    for cfg in configs:
        if is_expired(cfg.get("expires_at")):
            continue
        try:
            conn.execute(
                """
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
                """,
                (
                    cfg.get("protocol", ""),
                    cfg.get("protocol_type", ""),
                    cfg.get("name", ""),
                    cfg.get("server", ""),
                    cfg.get("port", 0),
                    cfg.get("raw", ""),
                    cfg.get("expires_at", ""),
                    cfg.get("country", ""),
                ),
            )
            count += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return count


def get_all_configs() -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM configs ORDER BY protocol_type, name").fetchall()
    conn.close()
    return [dict(row) for row in rows if not is_expired(row["expires_at"])]


_SORT_KEYS = {"name", "server", "protocol", "protocol_type", "port", "country", "expires_at", "created_at"}


def search_configs(
    query: str = "",
    protocols: Optional[list] = None,
    sort_key: str = "",
    sort_dir: int = 1,
    offset: int = 0,
    limit: int = 1000,
    countries: Optional[list] = None,
):
    today = datetime.date.today().isoformat()
    where = [
        "(expires_at IS NULL OR expires_at = '' OR expires_at NOT LIKE '____-__-__%' OR expires_at >= ?)"
    ]
    params: list = [today]

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
    rows = conn.execute(
        f"SELECT * FROM configs WHERE {wh}{order} LIMIT ? OFFSET ?",
        params + [int(limit), int(offset)],
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows], total


def get_config_count() -> int:
    conn = _get_conn()
    today = datetime.date.today().isoformat()
    n = conn.execute(
        "SELECT COUNT(*) FROM configs WHERE (expires_at IS NULL OR expires_at = '' OR expires_at NOT LIKE '____-__-__%' OR expires_at >= ?)",
        (today,),
    ).fetchone()[0]
    conn.close()
    return n


def get_config_by_id(config_id: int) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM configs WHERE id = ?", (config_id,)).fetchone()
    conn.close()
    if not row or is_expired(row["expires_at"]):
        return None
    return dict(row)


def delete_config(config_id: int) -> bool:
    conn = _get_conn()
    conn.execute("DELETE FROM configs WHERE id = ?", (config_id,))
    conn.commit()
    deleted = conn.total_changes > 0
    conn.close()
    return deleted


def clear_all_configs():
    conn = _get_conn()
    conn.execute("DELETE FROM configs")
    conn.commit()
    conn.close()


_DEAD_LINKS_PATH = os.path.join(BASE_DIR, "dead_links.json")
_dead_links: Optional[set] = None


def _load_dead_set() -> set:
    global _dead_links
    if _dead_links is None:
        _dead_links = set()
        try:
            with open(_DEAD_LINKS_PATH, "r", encoding="utf-8") as f:
                _dead_links = set(json.load(f))
        except Exception:
            _dead_links = set()
    return _dead_links


def is_dead_link(url: str) -> bool:
    return url in _load_dead_set()


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
    except Exception:
        pass


def get_protocol_counts() -> Dict[str, int]:
    conn = _get_conn()
    today = datetime.date.today().isoformat()
    rows = conn.execute(
        "SELECT protocol_type, COUNT(*) as count FROM configs "
        "WHERE (expires_at IS NULL OR expires_at = '' OR expires_at NOT LIKE '____-__-__%' OR expires_at >= ?) "
        "GROUP BY protocol_type ORDER BY count DESC",
        (today,),
    ).fetchall()
    conn.close()
    return {row["protocol_type"]: row["count"] for row in rows}


def get_country_counts(top: int = 30) -> List[Dict]:
    conn = _get_conn()
    today = datetime.date.today().isoformat()
    rows = conn.execute(
        "SELECT COALESCE(NULLIF(country, ''), '(unknown)') AS country, COUNT(*) as count FROM configs "
        "WHERE (expires_at IS NULL OR expires_at = '' OR expires_at NOT LIKE '____-__-__%' OR expires_at >= ?) "
        "GROUP BY COALESCE(NULLIF(country, ''), '(unknown)') ORDER BY count DESC LIMIT ?",
        (today, int(top)),
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
        entry = {k: v for k, v in cfg.items() if k != "id" and k != "created_at" and k != "raw"}
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


init_db()
