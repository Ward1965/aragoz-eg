import base64
import json
import re
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, List, Optional


PROTOCOL_COLORS = {
    "VLESS": "#6366f1",
    "VMess": "#8b5cf6",
    "Trojan": "#ef4444",
    "Shadowsocks": "#f59e0b",
    "SSR": "#f97316",
    "Hysteria": "#10b981",
    "Hysteria2": "#34d399",
    "TUIC": "#06b6d4",
    "WireGuard": "#3b82f6",
    "SOCKS5": "#ec4899",
    "SOCKS4": "#f472b6",
    "HTTP": "#84cc16",
    "HTTPS": "#22c55e",
    "NaiveProxy": "#a855f7",
    "SSH": "#64748b",
    "OpenVPN": "#eab308",
    "Tor": "#78716c",
}

ALPHA2_COUNTRIES = {
    "af": "Afghanistan", "al": "Albania", "dz": "Algeria", "ad": "Andorra",
    "ao": "Angola", "ag": "Antigua and Barbuda", "ar": "Argentina", "am": "Armenia",
    "au": "Australia", "at": "Austria", "az": "Azerbaijan", "bs": "Bahamas",
    "bh": "Bahrain", "bd": "Bangladesh", "bb": "Barbados", "by": "Belarus",
    "be": "Belgium", "bz": "Belize", "bj": "Benin", "bt": "Bhutan", "bo": "Bolivia",
    "ba": "Bosnia and Herzegovina", "bw": "Botswana", "br": "Brazil", "bn": "Brunei",
    "bg": "Bulgaria", "bf": "Burkina Faso", "bi": "Burundi", "kh": "Cambodia",
    "cm": "Cameroon", "ca": "Canada", "cv": "Cape Verde", "td": "Chad", "cl": "Chile",
    "cn": "China", "co": "Colombia", "km": "Comoros", "cg": "Congo",
    "cd": "Congo (DRC)", "cr": "Costa Rica", "ci": "Côte d'Ivoire", "hr": "Croatia",
    "cu": "Cuba", "cy": "Cyprus", "cz": "Czechia", "dk": "Denmark", "dj": "Djibouti",
    "dm": "Dominica", "do": "Dominican Republic", "ec": "Ecuador", "eg": "Egypt",
    "sv": "El Salvador", "er": "Eritrea", "ee": "Estonia", "sz": "Eswatini",
    "et": "Ethiopia", "fj": "Fiji", "fi": "Finland", "fr": "France", "ga": "Gabon",
    "gm": "Gambia", "ge": "Georgia", "de": "Germany", "gh": "Ghana", "gr": "Greece",
    "gd": "Grenada", "gt": "Guatemala", "gn": "Guinea", "gw": "Guinea-Bissau",
    "gy": "Guyana", "ht": "Haiti", "hn": "Honduras", "hk": "Hong Kong",
    "hu": "Hungary", "is": "Iceland", "in": "India", "id": "Indonesia",
    "ir": "Iran", "iq": "Iraq", "ie": "Ireland", "il": "Israel", "it": "Italy",
    "jm": "Jamaica", "jp": "Japan", "jo": "Jordan", "kz": "Kazakhstan",
    "ke": "Kenya", "ki": "Kiribati", "kp": "North Korea", "kr": "South Korea",
    "kw": "Kuwait", "kg": "Kyrgyzstan", "la": "Laos", "lv": "Latvia",
    "lb": "Lebanon", "ls": "Lesotho", "lr": "Liberia", "ly": "Libya",
    "li": "Liechtenstein", "lt": "Lithuania", "lu": "Luxembourg", "mo": "Macau",
    "mg": "Madagascar", "mw": "Malawi", "my": "Malaysia", "mv": "Maldives",
    "ml": "Mali", "mt": "Malta", "mr": "Mauritania", "mu": "Mauritius",
    "mx": "Mexico", "md": "Moldova", "mc": "Monaco", "mn": "Mongolia",
    "me": "Montenegro", "ma": "Morocco", "mz": "Mozambique", "mm": "Myanmar",
    "na": "Namibia", "nr": "Nauru", "np": "Nepal", "nl": "Netherlands",
    "nz": "New Zealand", "ni": "Nicaragua", "ne": "Niger", "ng": "Nigeria",
    "mk": "North Macedonia", "no": "Norway", "om": "Oman", "pk": "Pakistan",
    "pw": "Palau", "ps": "Palestine", "pa": "Panama", "pg": "Papua New Guinea",
    "py": "Paraguay", "pe": "Peru", "ph": "Philippines", "pl": "Poland",
    "pt": "Portugal", "qa": "Qatar", "ro": "Romania", "ru": "Russia",
    "rw": "Rwanda", "ws": "Samoa", "sm": "San Marino", "sa": "Saudi Arabia",
    "sn": "Senegal", "rs": "Serbia", "sc": "Seychelles", "sl": "Sierra Leone",
    "sg": "Singapore", "sk": "Slovakia", "si": "Slovenia", "so": "Somalia",
    "za": "South Africa", "ss": "South Sudan", "es": "Spain", "lk": "Sri Lanka",
    "sd": "Sudan", "sr": "Suriname", "se": "Sweden", "ch": "Switzerland",
    "sy": "Syria", "tw": "Taiwan", "tj": "Tajikistan", "tz": "Tanzania",
    "th": "Thailand", "tl": "Timor-Leste", "tg": "Togo", "tt": "Trinidad and Tobago",
    "tn": "Tunisia", "tr": "Turkey", "tm": "Turkmenistan", "ug": "Uganda",
    "ua": "Ukraine", "ae": "United Arab Emirates", "gb": "United Kingdom",
    "us": "United States", "uy": "Uruguay", "uz": "Uzbekistan", "vu": "Vanuatu",
    "ve": "Venezuela", "vn": "Vietnam", "ye": "Yemen", "zm": "Zambia", "zw": "Zimbabwe",
}

ALPHA3_COUNTRIES = {
    "usa": "United States", "uk": "United Kingdom", "gbr": "United Kingdom",
    "hkg": "Hong Kong", "sgp": "Singapore", "jpn": "Japan", "kor": "South Korea",
    "twn": "Taiwan", "deu": "Germany", "fra": "France", "ita": "Italy",
    "esp": "Spain", "prt": "Portugal", "nld": "Netherlands", "can": "Canada",
    "aus": "Australia", "ind": "India", "chn": "China", "rus": "Russia",
    "bra": "Brazil", "mex": "Mexico", "are": "United Arab Emirates",
    "sau": "Saudi Arabia", "tur": "Turkey", "isr": "Israel", "pol": "Poland",
    "swe": "Sweden", "nor": "Norway", "fin": "Finland", "che": "Switzerland",
    "aut": "Austria", "bel": "Belgium", "cze": "Czechia", "svk": "Slovakia",
    "hun": "Hungary", "rou": "Romania", "bgr": "Bulgaria", "grc": "Greece",
    "ukr": "Ukraine", "vnm": "Vietnam", "tha": "Thailand", "mys": "Malaysia",
    "idn": "Indonesia", "phl": "Philippines", "pak": "Pakistan", "bgd": "Bangladesh",
    "lka": "Sri Lanka", "nep": "Nepal", "irn": "Iran", "irq": "Iraq",
    "syr": "Syria", "jor": "Jordan", "lbn": "Lebanon", "kwt": "Kuwait",
    "qat": "Qatar", "egy": "Egypt", "nga": "Nigeria", "ken": "Kenya",
    "eth": "Ethiopia", "gha": "Ghana", "mar": "Morocco", "tun": "Tunisia",
    "dza": "Algeria", "zaf": "South Africa", "arg": "Argentina", "chl": "Chile",
    "col": "Colombia", "per": "Peru", "ecu": "Ecuador", "ven": "Venezuela",
    "ury": "Uruguay", "pry": "Paraguay", "bol": "Bolivia", "aze": "Azerbaijan",
    "kaz": "Kazakhstan", "uzb": "Uzbekistan", "geo": "Georgia", "arm": "Armenia",
    "est": "Estonia", "lva": "Latvia", "ltu": "Lithuania", "srb": "Serbia",
    "hrv": "Croatia", "svn": "Slovenia", "bih": "Bosnia and Herzegovina",
    "mne": "Montenegro", "mkd": "North Macedonia", "alb": "Albania", "irl": "Ireland",
}

COUNTRY_CODES = {**ALPHA2_COUNTRIES, **ALPHA3_COUNTRIES}

# full country names -> canonical display name (matched in server/remark text)
_COUNTRY_NAME_LOOKUP = {}
for _name in COUNTRY_CODES.values():
    _COUNTRY_NAME_LOOKUP.setdefault(_name.lower(), _name)

# TLDs / infra tokens that look like codes but are not proxy countries
_COUNTRY_SKIP = {
    "com", "net", "org", "io", "ai", "tv", "gg", "tk", "ga", "gq", "ml", "cf",
    "cc", "fm", "ws", "im", "je", "app", "cdn", "cloud", "web", "api", "data",
    "node", "home", "go", "run", "site", "vps", "proxy", "server", "host", "www",
    "new", "one", "two", "mail", "edge", "gate", "digital", "online",
}


def extract_country(server: str, name: str = "") -> str:
    if not server and not name:
        return ""
    text = f"{server or ''} {name or ''}".lower()
    for part in re.split(r"[\s,]|//|@", text):
        if not part:
            continue
        for tok in re.split(r"[^a-z0-9]+", part):
            if not tok or tok in _COUNTRY_SKIP:
                continue
            if 2 <= len(tok) <= 3:
                res = COUNTRY_CODES.get(tok)
                if res:
                    return res
    sorted_names = sorted(_COUNTRY_NAME_LOOKUP, key=len, reverse=True)
    for nme in sorted_names:
        if nme in text:
            return _COUNTRY_NAME_LOOKUP[nme]
    return ""


def _decode_b64(s: str) -> str:
    try:
        s = s.strip()
        padding = 4 - len(s) % 4
        if padding != 4:
            s += "=" * padding
        return base64.b64decode(s).decode("utf-8")
    except Exception:
        return ""


def _parse_expiry_value(val: str):
    val = val.strip().strip("\"'")
    if not val:
        return None
    if val.isdigit():
        ts = int(val)
        if ts > 1e12:
            ts = ts / 1000.0
        if 1_000_000_000 < ts < 4_100_000_000:
            try:
                return datetime.utcfromtimestamp(ts).date().isoformat()
            except Exception:
                pass
        return None
    m = re.match(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", val)
    if m:
        try:
            y, mo, d = (int(x) for x in m.groups())
            return date(y, mo, d).isoformat()
        except Exception:
            pass
    return None


def extract_expiry(text: str) -> str:
    if not text:
        return ""
    decoded = unquote(text)
    m = re.search(r"(?:expire|expires|expiry|expire_at|expires_at)[=:]\s*([^&\s;,]+)", decoded, re.IGNORECASE)
    if m:
        v = _parse_expiry_value(m.group(1))
        if v:
            return v
    for sep in ("-", "/", "."):
        m = re.search(r"\b(\d{4})" + re.escape(sep) + r"(\d{1,2})" + re.escape(sep) + r"(\d{1,2})\b", decoded)
        if m:
            try:
                y, mo, d = (int(x) for x in m.groups())
                return date(y, mo, d).isoformat()
            except Exception:
                pass
    for m in re.finditer(r"[?&]([a-z_]+)=(\d{10})", text, re.IGNORECASE):
        if not re.match(r"(?:expir|time|date)", m.group(1), re.IGNORECASE):
            continue
        v = _parse_expiry_value(m.group(2))
        if v:
            return v
    return ""


def _parse_query_string(qs: str) -> Dict[str, str]:
    params = {}
    if not qs:
        return params
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = unquote(v)
    return params


def _safe_get(url_obj, key: str, default: str = "") -> str:
    val = url_obj.query.get(key, [default])
    if isinstance(val, list):
        return val[0] if val else default
    return val


def parse_vless(line: str) -> Optional[Dict]:
    try:
        match = re.match(r"vless://([^@]+)@([^:]+):(\d+)", line)
        if not match:
            return None
        uuid = match.group(1)
        server = match.group(2)
        port = int(match.group(3))

        remark_match = re.search(r"#(.+)$", line)
        remark = unquote(remark_match.group(1)) if remark_match else f"{server}:{port}"

        qs_match = re.search(r"\?(.+?)(?:#.*)?$", line)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        security = params.get("security", "none")
        sni = params.get("sni", "")
        fp = params.get("fp", "")
        pbk = params.get("pbk", "")
        sid = params.get("sid", "")
        spx = params.get("spx", "")
        alpn = params.get("alpn", "")
        flow = params.get("flow", "")
        net = params.get("net", "tcp")
        type_ = params.get("type", "tcp")
        host = params.get("host", "")
        path = params.get("path", "")
        tls_type = params.get("tls", "")

        protocol_detail = "VLESS"
        if security == "reality":
            protocol_detail = "VLESS + Reality"
        elif flow:
            protocol_detail = "VLESS + XTLS"
        elif security == "tls" or tls_type:
            protocol_detail = "VLESS + TLS"

        return {
            "protocol": protocol_detail,
            "protocol_type": "VLESS",
            "name": remark,
            "server": server,
            "port": port,
            "uuid": uuid,
            "security": security,
            "sni": sni,
            "fingerprint": fp,
            "public_key": pbk,
            "short_id": sid,
            "spider_x": spx,
            "alpn": alpn,
            "flow": flow,
            "network": net or type_,
            "host": host,
            "path": path,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_vmess(line: str) -> Optional[Dict]:
    try:
        decoded = _decode_b64(line.replace("vmess://", ""))
        if not decoded:
            return None
        data = json.loads(decoded)
        return {
            "protocol": "VMess",
            "protocol_type": "VMess",
            "name": data.get("ps", f"{data.get('add', '')}:{data.get('port', '')}"),
            "server": data.get("add", ""),
            "port": int(data.get("port", 0)),
            "uuid": data.get("id", ""),
            "alter_id": int(data.get("aid", 0)),
            "security": data.get("scy", "auto"),
            "network": data.get("net", "tcp"),
            "type": data.get("type", "none"),
            "host": data.get("host", ""),
            "path": data.get("path", ""),
            "tls": data.get("tls", ""),
            "sni": data.get("sni", ""),
            "alpn": data.get("alpn", ""),
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_trojan(line: str) -> Optional[Dict]:
    try:
        match = re.match(r"trojan://([^@]+)@([^:]+):(\d+)", line)
        if not match:
            return None
        password = match.group(1)
        server = match.group(2)
        port = int(match.group(3))

        remark_match = re.search(r"#(.+)$", line)
        remark = unquote(remark_match.group(1)) if remark_match else f"{server}:{port}"

        qs_match = re.search(r"\?(.+?)(?:#.*)?$", line)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        sni = params.get("sni", "")
        security = params.get("security", "tls")
        alpn = params.get("alpn", "")
        peer = params.get("peer", "")
        type_ = params.get("type", "tcp")
        host = params.get("host", "")
        path = params.get("path", "")

        return {
            "protocol": "Trojan + TLS" if security == "tls" else "Trojan",
            "protocol_type": "Trojan",
            "name": remark,
            "server": server,
            "port": port,
            "password": password,
            "security": security,
            "sni": sni or peer,
            "alpn": alpn,
            "network": type_,
            "host": host,
            "path": path,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_shadowsocks(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        if cleaned.startswith("ss://"):
            cleaned = cleaned[5:]

        remark = ""
        remark_match = re.search(r"#(.+)$", cleaned)
        if remark_match:
            remark = unquote(remark_match.group(1))
            cleaned = cleaned[: remark_match.start()]

        if "@" in cleaned:
            before_at, after_at = cleaned.split("@", 1)
            decoded = _decode_b64(before_at)
            if ":" in decoded:
                method, password = decoded.split(":", 1)
            else:
                method, password = decoded, ""
            server_port = after_at.split("?")[0]
            if ":" in server_port:
                server, port = server_port.rsplit(":", 1)
                port = int(port.split("#")[0])
            else:
                server, port = server_port, 0
        else:
            decoded = _decode_b64(cleaned.split("?")[0])
            if ":" in decoded:
                method_pass, server_port = decoded.rsplit("@", 1) if "@" in decoded else (decoded, "")
                if "@" in decoded:
                    method_pass, server_port = decoded.rsplit("@", 1)
                    method, password = method_pass.split(":", 1)
                else:
                    method, password = decoded, ""
                if ":" in server_port:
                    server, port = server_port.rsplit(":", 1)
                    port = int(port)
                else:
                    server, port = server_port, 0
            else:
                return None

        if not remark:
            remark = f"{server}:{port}"

        return {
            "protocol": "Shadowsocks",
            "protocol_type": "Shadowsocks",
            "name": remark,
            "server": server,
            "port": port,
            "password": password,
            "cipher": method,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_hysteria2(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        if cleaned.startswith("hy2://"):
            cleaned = cleaned[6:]

        remark = ""
        remark_match = re.search(r"#(.+)$", cleaned)
        if remark_match:
            remark = unquote(remark_match.group(1))
            cleaned = cleaned[: remark_match.start()]

        match = re.match(r"([^@]+)@([^:]+):(\d+)", cleaned)
        if not match:
            return None
        password = match.group(1)
        server = match.group(2)
        port = int(match.group(3))

        qs_match = re.search(r"\?(.+?)$", cleaned)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        sni = params.get("sni", "")
        insecure = params.get("insecure", "0") == "1"
        obfs = params.get("obfs", "")
        obfs_password = params.get("obfs-password", "")
        pin_sha256 = params.get("pinSHA256", "")

        if not remark:
            remark = f"{server}:{port}"

        return {
            "protocol": "Hysteria2",
            "protocol_type": "Hysteria2",
            "name": remark,
            "server": server,
            "port": port,
            "password": password,
            "sni": sni,
            "insecure": insecure,
            "obfs": obfs,
            "obfs_password": obfs_password,
            "pin_sha256": pin_sha256,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_tuic(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        if cleaned.startswith("tuic://"):
            cleaned = cleaned[7:]

        remark = ""
        remark_match = re.search(r"#(.+)$", cleaned)
        if remark_match:
            remark = unquote(remark_match.group(1))
            cleaned = cleaned[: remark_match.start()]

        match = re.match(r"([^@]+)@([^:]+):(\d+)", cleaned)
        if not match:
            return None
        uuid_password = match.group(1)
        server = match.group(2)
        port = int(match.group(3))

        parts = uuid_password.split(":", 1)
        uuid = parts[0]
        password = parts[1] if len(parts) > 1 else ""

        qs_match = re.search(r"\?(.+?)$", cleaned)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        sni = params.get("sni", "")
        congestion_control = params.get("congestion_control", "bbr")
        alpn = params.get("alpn", "")
        udp_relay_mode = params.get("udp_relay_mode", "native")
        insecure = params.get("insecure", "0") == "1"

        if not remark:
            remark = f"{server}:{port}"

        return {
            "protocol": "TUIC",
            "protocol_type": "TUIC",
            "name": remark,
            "server": server,
            "port": port,
            "uuid": uuid,
            "password": password,
            "sni": sni,
            "congestion_control": congestion_control,
            "alpn": alpn,
            "udp_relay_mode": udp_relay_mode,
            "insecure": insecure,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_wireguard(line: str) -> Optional[Dict]:
    try:
        data = {}

        if line.lstrip().lower().startswith("wireguard://"):
            cleaned = line[12:]
            remark = ""
            remark_match = re.search(r"#(.+)$", cleaned)
            if remark_match:
                remark = unquote(remark_match.group(1))
                cleaned = cleaned[: remark_match.start()]
            if cleaned.startswith("?"):
                qs_match = re.search(r"\?(.+)$", cleaned)
                params = _parse_query_string(qs_match.group(1)) if qs_match else {}
                data = {k: v for k, v in params.items()}
                data["name"] = remark
        elif "=" in line:
            for part in line.split(","):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    data[key.strip()] = val.strip()

            if "[peer]" in line.lower():
                for m in re.finditer(r"(\w+)\s*=\s*([^\n,]+)", line):
                    data[m.group(1).strip()] = m.group(2).strip()

            remark = data.get("name", "") or data.get("Name", "")

        if not data:
            return None

        endpoint = data.get("Endpoint", "") or data.get("endpoint", "")
        server = endpoint.split(":")[0]
        port_str = endpoint.split(":")[-1]
        port = int(port_str) if port_str.isdigit() else 0

        if not server:
            return None

        if not remark:
            remark = f"WireGuard {server}"

        return {
            "protocol": "WireGuard",
            "protocol_type": "WireGuard",
            "name": remark,
            "server": server,
            "port": port,
            "private_key": data.get("PrivateKey", "") or data.get("privateKey", ""),
            "public_key": data.get("PublicKey", "") or data.get("publicKey", ""),
            "address": data.get("Address", "") or data.get("address", ""),
            "dns": data.get("DNS", "") or data.get("dns", ""),
            "allowed_ips": data.get("AllowedIPs", "") or data.get("allowedips", ""),
            "endpoint": endpoint,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_ssr(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        if cleaned.lower().startswith("ssr://"):
            cleaned = cleaned[6:]
        decoded = _decode_b64(cleaned)
        if not decoded:
            return None

        params = {}
        main = decoded
        if "/?" in decoded:
            main, qs = decoded.split("/?", 1)
            params = _parse_query_string(qs)

        parts = main.split(":")
        if len(parts) < 6:
            return None
        server = parts[0]
        try:
            port = int(parts[1])
        except Exception:
            return None
        ssr_protocol = parts[2]
        method = parts[3]
        obfs = parts[4]
        password = _decode_b64(":".join(parts[5:]))

        remarks = params.get("remarks", "")
        if remarks:
            decoded_remark = _decode_b64(remarks)
            remarks = decoded_remark or remarks
        obfsparam = params.get("obfsparam", "")
        decoded_obfs = _decode_b64(obfsparam)
        protocolparam = params.get("protocolparam", "")
        decoded_proto = _decode_b64(protocolparam)
        group = params.get("group", "")
        if group:
            decoded_group = _decode_b64(group)
            group = decoded_group or group

        name = unquote(remarks) if remarks else f"{server}:{port}"

        return {
            "protocol": "SSR",
            "protocol_type": "SSR",
            "name": name,
            "server": server,
            "port": port,
            "password": password,
            "cipher": method,
            "ssr_protocol": ssr_protocol,
            "obfs": obfs,
            "obfs_param": decoded_obfs or obfsparam,
            "protocol_param": decoded_proto or protocolparam,
            "group": group,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_hysteria(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        if cleaned.lower().startswith("hysteria://"):
            cleaned = cleaned[11:]
        elif cleaned.lower().startswith("hy1://"):
            cleaned = cleaned[6:]

        remark = ""
        remark_match = re.search(r"#(.+)$", cleaned)
        if remark_match:
            remark = unquote(remark_match.group(1))
            cleaned = cleaned[: remark_match.start()]

        match = re.match(r"([^?/]+)", cleaned)
        if not match:
            return None
        hostport = match.group(1)
        if ":" not in hostport:
            return None
        server, port_str = hostport.rsplit(":", 1)
        try:
            port = int(port_str)
        except Exception:
            return None

        qs_match = re.search(r"\?(.+)$", cleaned)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        protocol = params.get("protocol", "udp")
        auth = params.get("auth", "") or params.get("auth_str", "")
        upmbps = params.get("upmbps", "")
        downmbps = params.get("downmbps", "")
        sni = params.get("sni", "")
        alpn = params.get("alpn", "")
        obfs = params.get("obfs", "")
        obfs_param = params.get("obfsParam", "")
        insecure = params.get("insecure", "0") == "1"

        if not remark:
            remark = f"{server}:{port}"

        return {
            "protocol": "Hysteria",
            "protocol_type": "Hysteria",
            "name": remark,
            "server": server,
            "port": port,
            "password": auth,
            "sni": sni,
            "alpn": alpn,
            "hysteria_protocol": protocol,
            "obfs": obfs,
            "obfs_param": obfs_param,
            "up_mbps": upmbps,
            "down_mbps": downmbps,
            "insecure": insecure,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_naive(line: str) -> Optional[Dict]:
    try:
        m = re.match(r"(naive\+https|naive\+h2|naive\+quic|naive)://([^@/#]*@)?([^/#@]+):(\d+)?", line)
        if not m:
            return None
        scheme = m.group(1)
        cred = (m.group(2) or "").rstrip("@")
        server = m.group(3)
        port_str = m.group(4) or "443"

        remark = ""
        remark_match = re.search(r"#(.+)$", line)
        if remark_match:
            remark = unquote(remark_match.group(1))

        username = ""
        password = ""
        if ":" in cred:
            username, password = cred.split(":", 1)
            username = unquote(username)
            password = unquote(password)

        try:
            port = int(port_str)
        except Exception:
            port = 443

        if not remark:
            remark = f"{server}:{port}"

        return {
            "protocol": "NaiveProxy",
            "protocol_type": "NaiveProxy",
            "name": remark,
            "server": server,
            "port": port,
            "username": username,
            "password": password,
            "h2": "naive+h2" in scheme or "naive+quic" in scheme,
            "quic": "naive+quic" in scheme,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_wg_uri(line: str) -> Optional[Dict]:
    try:
        if not line.lower().startswith("wg://"):
            return None
        clean = line[5:]
        frag = re.search(r"#.*$", clean)
        if frag:
            clean = clean[: frag.start()]
        qs_match = re.search(r"\?(.+$)", clean)
        params = _parse_query_string(qs_match.group(1)) if qs_match else {}

        remark = ""
        remark_match = re.search(r"#(.+)$", line)
        if remark_match:
            remark = unquote(remark_match.group(1))

        endpoint = params.get("endpoint", "")
        server = params.get("server", "")
        port = 0
        if endpoint and ":" in endpoint:
            server = endpoint.rsplit(":", 1)[0]
            try:
                port = int(endpoint.rsplit(":", 1)[1])
            except Exception:
                port = 0
        elif ":" in server and server.count(":") == 1:
            server, port_str = server.rsplit(":", 1)
            try:
                port = int(port_str)
            except Exception:
                port = 0
        else:
            try:
                port = int(params.get("port", "0"))
            except Exception:
                port = 0

        if not server:
            return None

        if not remark:
            remark = f"WireGuard {server}"

        return {
            "protocol": "WireGuard",
            "protocol_type": "WireGuard",
            "name": remark,
            "server": server,
            "port": port,
            "public_key": params.get("publicKey", ""),
            "private_key": params.get("privateKey", ""),
            "preshared_key": params.get("presharedKey", ""),
            "address": params.get("address", ""),
            "dns": params.get("dns", ""),
            "allowed_ips": params.get("allowedIPs", "") or params.get("allowed_ips", ""),
            "mtu": params.get("mtu", ""),
            "endpoint": endpoint,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_socks(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        proto_label = "SOCKS5"
        if cleaned.lower().startswith("socks5://"):
            cleaned = cleaned[9:]
            proto_label = "SOCKS5"
        elif cleaned.lower().startswith("socks4://"):
            cleaned = cleaned[9:]
            proto_label = "SOCKS4"
        elif cleaned.startswith("socks://"):
            cleaned = cleaned[8:]
            proto_label = "SOCKS5"

        remark = ""
        remark_match = re.search(r"#(.+)$", cleaned)
        if remark_match:
            remark = unquote(remark_match.group(1))
            cleaned = cleaned[: remark_match.start()]

        match = re.match(r"([^:]+):(\d+)", cleaned)
        if not match:
            return None

        server = match.group(1)
        port = int(match.group(2))

        if not remark:
            remark = f"{proto_label} {server}:{port}"

        return {
            "protocol": proto_label,
            "protocol_type": proto_label,
            "name": remark,
            "server": server,
            "port": port,
            "raw": line.strip(),
        }
    except Exception:
        return None


def parse_http_proxy(line: str) -> Optional[Dict]:
    try:
        cleaned = line.strip()
        proto = "HTTP"
        if cleaned.startswith("https://"):
            proto = "HTTPS"
            cleaned = cleaned[8:]
        elif cleaned.startswith("http://"):
            cleaned = cleaned[7:]

        match = re.match(r"([^:]+):(\d+)", cleaned)
        if not match:
            return None

        server = match.group(1)
        port = int(match.group(2))

        return {
            "protocol": proto,
            "protocol_type": "HTTP",
            "name": f"{proto} Proxy {server}:{port}",
            "server": server,
            "port": port,
            "raw": line.strip(),
        }
    except Exception:
        return None


PARSERS = {
    "vless://": parse_vless,
    "vmess://": parse_vmess,
    "trojan://": parse_trojan,
    "ss://": parse_shadowsocks,
    "ssr://": parse_ssr,
    "hy2://": parse_hysteria2,
    "hysteria2://": parse_hysteria2,
    "hysteria://": parse_hysteria,
    "hy1://": parse_hysteria,
    "tuic://": parse_tuic,
    "socks5://": parse_socks,
    "socks4://": parse_socks,
    "socks://": parse_socks,
    "wireguard://": parse_wireguard,
    "wg://": parse_wg_uri,
    "naive+https://": parse_naive,
    "naive+h2://": parse_naive,
    "naive+quic://": parse_naive,
    "http://": parse_http_proxy,
    "https://": parse_http_proxy,
}


def parse_line(line: str) -> Optional[Dict]:
    line = line.strip()
    if not line:
        return None

    if line.lower().startswith("[") and "endpoint" in line.lower():
        result = parse_wireguard(line)
        if result:
            return result

    for prefix, parser in PARSERS.items():
        if line.lower().startswith(prefix):
            return parser(line)

    return None


CLASH_TYPE_MAP = {
    "ss": "Shadowsocks",
    "ssr": "SSR",
    "vmess": "VMess",
    "trojan": "Trojan",
    "vless": "VLESS",
    "socks5": "SOCKS5",
    "socks4": "SOCKS4",
    "http": "HTTP",
    "https": "HTTPS",
    "hysteria": "Hysteria",
    "hysteria2": "Hysteria2",
    "tuic": "TUIC",
    "wireguard": "WireGuard",
    "naive": "NaiveProxy",
    "ssh": "SSH",
}


def _parse_clash_block(block: str) -> Optional[Dict]:
    block = block.strip()
    if not block:
        return None
    name_match = re.match(r"-?\s*name:\s*([^\n]+)", block, re.DOTALL)
    if not name_match:
        return None
    name = name_match.group(1).strip().strip("\"'\u201c\u201d")

    fields = {}
    for m in re.finditer(r"^\s{2,12}([\w][\w.-]*):\s*(.*)$", block, re.MULTILINE):
        key = m.group(1).strip()
        val = m.group(2).strip().strip("\"'\u201c\u201d")
        fields[key] = val

    ctype = fields.get("type", "").lower()
    proto = CLASH_TYPE_MAP.get(ctype)
    if not proto:
        return None

    server = fields.get("server", "")
    port = fields.get("port", "0")
    try:
        port = int(port)
    except Exception:
        port = 0
    if not server:
        return None

    entry = {
        "protocol": proto,
        "protocol_type": proto,
        "name": name or f"{server}:{port}",
        "server": server,
        "port": port,
        "raw": block,
    }

    if ctype in ("ss", "vmess"):
        entry["password"] = fields.get("password", "")
        entry["cipher"] = fields.get("cipher", "") or fields.get("method", "")
    if ctype in ("vmess", "vless", "trojan", "tuic"):
        entry["uuid"] = fields.get("uuid", "") or fields.get("password", "")
        entry["alter_id"] = fields.get("alterId", "") or fields.get("alter_id", "")
    if ctype in ("vless", "trojan", "hysteria2", "tuic"):
        sni = fields.get("sni", "") or fields.get("servername", "")
        entry["sni"] = sni or ""
        entry["flow"] = fields.get("flow", "")
        security = fields.get("tls", "") or fields.get("security", "")
        if ctype == "vless":
            if "reality" in block.lower():
                entry["protocol"] = "VLESS + Reality"
            elif entry.get("flow"):
                entry["protocol"] = "VLESS + XTLS"
            elif security and security not in ("0", "false", "none"):
                entry["protocol"] = "VLESS + TLS"
        entry["network"] = fields.get("network", "") or fields.get("type", "")
        entry["host"] = fields.get("ws-opts.host", "") or fields.get("servername", "")
    if ctype == "trojan":
        entry["password"] = fields.get("password", "")
    return entry


def parse_clash_yaml(text: str) -> List[Dict]:
    if "proxies:" not in text:
        return []
    results = []
    blocks = re.split(r"\n\s+-\s+name:", text)
    for block in blocks[1:]:
        result = _parse_clash_block("name:" + block)
        if result:
            results.append(result)
    return results


def parse_singbox_json(text: str) -> List[Dict]:
    try:
        data = json.loads(text)
    except Exception:
        return []
    outbounds = data.get("outbounds", [])
    if not isinstance(outbounds, list):
        return []
    results = []
    for ob in outbounds:
        if not isinstance(ob, dict):
            continue
        ctype = ob.get("type", "").lower()
        proto = CLASH_TYPE_MAP.get(ctype)
        if not proto:
            continue
        server = ob.get("server", "")
        port = ob.get("server_port", 0)
        if not server:
            continue
        entry = {
            "protocol": proto,
            "protocol_type": proto,
            "name": ob.get("tag", "") or f"{server}:{port}",
            "server": server,
            "port": int(port),
            "raw": ob.get("tag", "") or f"{server}:{port}",
            "uuid": ob.get("uuid", "") or ob.get("password", ""),
            "password": ob.get("password", ""),
            "sni": "",
            "network": "",
            "flow": ob.get("flow", ""),
        }
        if ctype == "vless":
            if ob.get("reality"):
                entry["protocol"] = "VLESS + Reality"
            elif entry.get("flow"):
                entry["protocol"] = "VLESS + XTLS"
            elif ob.get("tls"):
                entry["protocol"] = "VLESS + TLS"
        tls = ob.get("tls", {}) or {}
        if isinstance(tls, dict):
            entry["sni"] = tls.get("server_name", "")
            entry["security"] = "tls" if tls else "none"
        entry["raw"] = json.dumps(ob, ensure_ascii=False)
        results.append(entry)
    return results


def _try_parse_structured(lines: List[str]) -> List[Dict]:
    if not lines:
        return []
    combined = "\n".join(lines)
    if "proxies:" in combined:
        return parse_clash_yaml(combined)
    if "outbounds" in combined and combined.strip().startswith("{"):
        return parse_singbox_json(combined)
    return []


def parse_all(lines: List[str]) -> List[Dict]:
    configs = []
    seen = set()

    for cfg in _try_parse_structured(lines):
        key = (cfg.get("server", ""), cfg.get("port", 0), cfg.get("protocol_type", ""))
        if key not in seen:
            seen.add(key)
            cfg["expires_at"] = extract_expiry(f"{cfg.get('raw', '')} {cfg.get('name', '')}")
            cfg["country"] = extract_country(cfg.get("server", ""), cfg.get("name", ""))
            configs.append(cfg)

    for line in lines:
        result = parse_line(line)
        if result:
            key = (result.get("server", ""), result.get("port", 0), result.get("protocol_type", ""))
            if key not in seen:
                seen.add(key)
                result["expires_at"] = extract_expiry(f"{line} {result.get('name', '')}")
                result["country"] = extract_country(result.get("server", ""), result.get("name", ""))
                configs.append(result)
    return configs


def get_protocol_color(protocol: str) -> str:
    return PROTOCOL_COLORS.get(protocol, "#6b7280")
