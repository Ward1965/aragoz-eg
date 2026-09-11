import re

from .fetcher import split_lines, try_base64_decode

TELEGRAM_CHANNELS = [
    "ARv2ray", "AblNet7", "Awlix_ir", "CloudCityy", "Configforvpn01",
    "DailyV2RY", "Daily_Configs", "DirectVPN", "Easy_Free_VPN", "EliV2ray",
    "FOXNT", "FOX_VPN66", "Fr33C0nfig", "FreakConfig", "FreeV2rays",
    "FreeVlessVpn", "Injastvpn", "NETMelliAnti", "Outline_Vpn", "Outline_ir",
    "ParsRoute", "PrivateVPNs", "SAVTEAM", "SafeNet_Server", "SaghiVpnX",
    "Shadownet021", "ShadowsocksM", "V2RayNG_CaFe", "V2rayNG3", "V2ray_Collector",
    "ViPVpn_v2ray", "Viturey", "VmessProtocol", "azadi_az_inja_migzare", "configV2rayForFree",
    "configV2rayNG", "custom_14", "free4allVPN", "freeland8", "i10VPN",
    "inikotesla", "iranvpnet", "msv2raynp", "networld_vpn", "oneclickvpnkeys",
    "pPal03", "proxy_kafee", "prrofile_purple", "shadowsocksshop", "sinavm",
    "singbox1", "speedconfig00", "v2rayNG_Matsuri", "v2ray_cartel", "v2ray_configs_pool",
    "v2ray_configs_pools", "v2ray_for_free", "v2ray_outlineir", "v2rayan", "v2raycollector",
    "v2rayng_021", "v2xay", "vmesskhodam", "vmessorg", "vmessprotocol",
    "vpn_ocean", "vpn_tehran", "vpnaloo", "yaney_01",
]

_CONFIG_RE = re.compile(
    r"(vless|vmess|trojan|ssr|ss|hy2|hy1|hysteria2|hysteria|tuic|wg|wireguard|socks5|socks4|socks|naive\+https|naive\+h2|naive\+quic|ssh|ikev2|l2tp|pptp|softether)://[^\s\"'<>]+",
    re.I,
)

_SUBSCRIPTION_LINK_RE = re.compile(r'href="(https?://[^"]+)"', re.I)

_IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mp3")

_HOST_BLOCK = (
    "telegram.me", "t.me", "tlgrm.me", "facebook.", "instagram.",
    "twitter.com", "x.com", "youtube.", "youtu.be", "tiktok.",
    "whatsapp.", "wa.me", "discord.", "google.com", "accounts.google",
    "play.google", "apple.com", "microsoft.com", "amazon.com",
)


def _is_useful_link(u: str) -> bool:
    low = u.lower()
    if not low.startswith(("http://", "https://")):
        return False
    if "t.me/" in low or "tg.me/" in low:
        return False
    host = low.split("/")[2] if "/" in low.split("//", 1)[-1] else ""
    if any(b in host for b in _HOST_BLOCK):
        return False
    if any(ext in low for ext in _IMG_EXT):
        return False
    return True


def _unescape(s: str) -> str:
    return (
        s.replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#x27;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
    )


def normalize_channel(ch: str):
    ch = (ch or "").strip().rstrip("/ ").replace("\t", "")
    if not ch:
        return None
    if ch.startswith("@"):
        ch = ch[1:]
    idx = ch.find("t.me/")
    if idx != -1:
        rest = ch[idx + len("t.me/"):]
        parts = rest.split("/")
        ch = parts[1] if len(parts) > 1 and parts[0].lower() in ("s", "c") else parts[0]
    else:
        ch = ch.split("/")[0]
    ch = ch.split("?")[0].strip()
    if not ch or not re.match(r"^[A-Za-z0-9_]{3,64}$", ch):
        return None
    return ch


def channel_page_url(username: str) -> str:
    return "https://t.me/s/" + username


def extract_links(html: str):
    links = []
    seen = set()
    for m in _SUBSCRIPTION_LINK_RE.findall(html):
        u = _unescape(m).strip()
        if not _is_useful_link(u):
            continue
        if u not in seen:
            seen.add(u)
            links.append(u)
    return links


def _extract_from_block(text: str, out: list):
    for line in split_lines(text):
        if _CONFIG_RE.match(line):
            out.append(line)
        else:
            decoded = try_base64_decode(line)
            if decoded and decoded != line:
                for dl in split_lines(decoded):
                    if _CONFIG_RE.match(dl):
                        out.append(dl)


def extract_codes(html: str):
    codes = []
    for tag in ("code", "pre"):
        for block in re.findall(r"<" + tag + r"[^>]*>(.*?)</" + tag + r">", html, re.S):
            _extract_from_block(_unescape(re.sub(r"<[^>]+>", "", block)).strip(), codes)
    for m in _CONFIG_RE.finditer(html):
        codes.append(_unescape(m.group(0)))
    out = []
    seen = set()
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out