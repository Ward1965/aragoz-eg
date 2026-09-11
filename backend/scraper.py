import asyncio
import base64
import html
import json
import os
import re
from typing import List, Set, Tuple
from urllib.parse import unquote, urlparse

import aiohttp

from .logging_setup import get_logger

log = get_logger("scraper")

GITHUB_API = "https://api.github.com"
RAW_PREFIX = "https://raw.githubusercontent.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

GOOGLE_SEARCH = "https://www.google.com/search"
# استعلامات Google إضافية عن مصادر اشتراكات مباشرة (غير GitHub فقط)
GOOGLE_QUERIES = [
    "vless subscription txt raw",
    "vmess subscription base64 list",
    "free subscription v2ray site:pastebin.com",
    "v2ray config github raw subscribe",
    "wireguard config share site:github.com",
    "openvpn config free download ovpn",
    "openvpn ovpn site:pastebin.com",
    "softether vpn config share",
    "free ssh tunnel accounts site:github.com",
    "ssh account free site:pastebin.com",
    "clash subscription yaml free",
    "hysteria2 subscription free",
    "sing-box config subscription",
    "l2tp ipsec vpn config free",
    "pptp vpn config free",
    "ikev2 vpn config free",
]

# استعلامات ذكية: دمج مواضيع متعددة بفاصلة (topic:a,b,c) في أقل عدد من طلبات GitHub API
# (غير المصادق عليه: 10 بحث/دقيقة) — بدلاً من 25 طلباً منفصلاً سابقاً
SEARCH_QUERIES = [
    "topic:v2ray,topic:shadowsocks,topic:shadowsocksr,topic:v2ray-reality,topic:xray,topic:v2rayng",
    "topic:vpn-subscription,topic:proxy-subscription,topic:sing-box,topic:clash-config,topic:hysteria2,topic:tuic",
    "topic:wireguard,topic:openvpn,topic:ovpn,topic:ikev2,topic:l2tp,topic:pptp,topic:softether,topic:ssh-tunnel",
    "v2ray subscription share OR free proxy configs txt OR free vpn config",
    "vless reality subscribe OR ssr subscription txt OR free hysteria2",
    "openvpn config share OR wireguard config share OR free ovpn",
    "ikev2 vpn config OR l2tp ipsec OR pptp vpn OR softether",
    "ssh tunnel share OR free ssh accounts OR free vpn accounts txt",
]

SEARCH_PER_PAGE = 10
TOTAL_SEARCH_RESULTS = 60
MAX_TREE_SCANS = 30
MAX_DISCOVERED_URLS = 400
MAX_URLS_PER_REPO = 15

# سجلّ دائم للمصادر التي أثبتت نجاحها فعلاً (أخرجت إعدادات) — يُدمج في كل فحص
# ليثبّت النتائج ولا يتأثر بتقلّب GitHub API / Google أو انقطاعهما.
_GOOD_SOURCES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "good_sources.json")
_good_sources: Set[str] = set()
_good_sources_loaded = False


def _load_good_sources() -> Set[str]:
    global _good_sources, _good_sources_loaded
    if not _good_sources_loaded:
        _good_sources_loaded = True
        try:
            with open(_GOOD_SOURCES_PATH, "r", encoding="utf-8") as f:
                _good_sources = set(json.load(f))
            log.info("Loaded %d known-good sources", len(_good_sources))
        except FileNotFoundError:
            _good_sources = set()
        except Exception as e:
            log.warning("Failed to load good sources: %s", e)
            _good_sources = set()
    return _good_sources


def record_good_sources(urls) -> None:
    """تسجيل روابط أثبتت أنها تُخرج إعدادات صالحة (تُستخدم كبذور دائمة في الفحوص القادمة)."""
    global _good_sources
    current = _load_good_sources()
    added = {u for u in urls if u and u not in current}
    if not added:
        return
    _good_sources = current | added
    if len(_good_sources) > 5000:
        _good_sources = set(list(_good_sources)[-5000:])
    try:
        with open(_GOOD_SOURCES_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(_good_sources), f, ensure_ascii=False)
        log.info("Good sources registry: %d URLs (%d new)", len(_good_sources), len(added))
    except Exception as e:
        log.warning("Failed to save good sources: %s", e)

# روابط مصدر معروفة ومستقرة تُستخدم كبذرة إضافية حتى لو تعطل discovery
KNOWN_SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_share.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_list.txt",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/base/all.txt",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/_base/all.txt",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/all/configs.txt",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/all/configs_base64.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no1.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no2.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no3.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no4.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no5.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no6.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no7.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no8.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no9.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/main/v2ray_configs_no10.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub1.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub2.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub3.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub4.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub5.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub6.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub7.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub8.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub9.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub10.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub11.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub12.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub13.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub14.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/ss.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/ssr.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/trojan.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/V2Ray-Config-By-EbraSha-All-Type.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/V2Ray-Config-By-EbraSha.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/ssr_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/ss_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/trojan_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/vless_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/vmess_configs.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/Best-Results/clash.yaml",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/Best-Results/proxies.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/shadowsocks.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/vless.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/vmess.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/trojan.txt",
    "https://raw.githubusercontent.com/crackbest/V2ray-Config/main/config.txt",
    "https://raw.githubusercontent.com/zhuhaiuk/free-nodes/main/nodes.txt",
    "https://raw.githubusercontent.com/zhuhaiuk/free-nodes/main/clash_config.yaml",

    # === من ConfigCrawler Spec — مصادير Seed إضافية ===
    "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subs/bundles/all.txt",
    "https://raw.githubusercontent.com/4n0nymou3/multi-proxy-config-fetcher/refs/heads/main/configs/proxy_configs.txt",
    "https://github.com/skywrt/v2ray-configs/raw/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/alexantSWE/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/all_configs.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/T3stAcc/V2Ray/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/coldwater-10/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/727301208/V2ray-Configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/all_configs.txt",
    "https://raw.githubusercontent.com/longlon/v2ray-config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/kawainime/V2ray-config/main/configs.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
]

_URL_RE = re.compile(r"https?://[^\s\)\]\}\"'`<>]+")

# امتدادات/كلمات تشير إلى ملفات اشتراكات حقيقية داخل المستودعات
_CONFIG_EXTS = (".txt", ".list", ".conf", ".yaml", ".yml", ".json", ".sub", ".clash", ".base64")
_CONFIG_HINTS = (
    "config", "sub", "node", "nodes", "subscribe", "vless", "vmess", "trojan", "ssr",
    "proxy", "share", "list", "reality", "wireguard", "wg", "hysteria", "hy2", "tuic",
    "openvpn", "ovpn", "ikev2", "l2tp", "softether", "pptp", "ssh", "clash", "sing-box",
    "singbox", "free", "collector", "pool",
)
_SKIP_HINTS = (
    "node_modules", ".github/", "images/", "img/", "icon", "logo", "asset",
    "doc/", "readme", "release", "download", "apk", ".exe", ".png", ".jpg",
    ".webp", ".svg", ".ico", "screenshot", ".map",
)


def _is_promising_config_path(path: str) -> bool:
    lower = path.lower()
    if any(s in lower for s in _SKIP_HINTS):
        return False
    if not lower.endswith(_CONFIG_EXTS):
        return False
    return any(h in lower for h in _CONFIG_HINTS)


# --- Google search discovery (non-GitHub sources) ---

_GOOGLE_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
]


def _is_google_blocked(text: str) -> bool:
    low = text.lower()
    return (
        "unusual traffic" in low
        or "enablejs=1" in low and "consent.google" in text
        or "captcha" in low and "google" in low
        or "not a robot" in low
        or ("/httpservice/retry/enablejs" in text and "https://support.google.com/websearch" in text)
    )


def _extract_google_urls(text: str) -> Set[str]:
    """استخراج روابط النتائج من صفحة Google (تتغلب على /url?q= و القوالب)."""
    urls: Set[str] = set()
    for m in re.finditer(r'href="(/url\?q=|https?://)[^"&]*', text):
        v = m.group(0)[6:]
        if v.startswith("/url?q="):
            v = v[len("/url?q="):]
        v = unquote(v)
        if v.startswith("http"):
            urls.add(v.split("&")[0])
    for m in re.finditer(r'url\?q=(https?[^&;"]+)', text):
        urls.add(unquote(m.group(1)))
    return urls


def _extract_ddg_urls(text: str) -> Set[str]:
    """استخراج الروابط من DuckDuckGo HTML (بصيغة uddg=)."""
    urls: Set[str] = set()
    for m in re.finditer(r'uddg=([^&\"]+)', text):
        try:
            urls.add(unquote(m.group(1)))
        except Exception:
            urls.add(m.group(1))
    return urls


def _looks_like_any_subscription(url: str) -> bool:
    """تحقق عام من أن الرابط محتمل أن يكون ملف اشتراك (ليس GitHub فقط).
    يشترط: امتداد ملف تكوين مباشر، أو host معروف للملفات الخام."""
    lower = url.lower()
    host = ""
    try:
        host = urlparse(lower).netloc
    except Exception:
        pass
    if not host:
        return False
    if any(s in lower for s in _SKIP_HINTS):
        return False
    # روابط GitHub/gist يجب أن تشير لملف (blob/raw)، وليس صفحة مستودع أو قناة
    if host in ("github.com", "gist.github.com") and "/blob/" not in lower and "/raw/" not in lower:
        return False

    has_hint = any(kw in lower for kw in (
        "vless", "vmess", "trojan", "ss://", "ssr", "hy2", "hysteria", "tuic",
        "wireguard", "wg", "naive", "proxy", "reality", "openvpn", "ovpn",
        "ikev2", "l2tp", "pptp", "softether", "ssh", "subscription", "subscribe",
        "config", "sub", "nodes", "node", "share", "free-vpn", "clash",
    ))
    # امتداد ملف تكوين مباشر
    config_ext = re.search(r"\.(txt|list|conf|yaml|yml|json|sub|clash|base64|ovpn|cfg|vpn|zip|tar|gz)(\?|$)", lower)

    # hosts معروفة بالتخزين الخام للملفات
    raw_hosts = (
        "raw.githubusercontent.com", "gist.githubusercontent.com",
        "pastebin.com", "paste.ee", "pastebin.pl", "paste.rs",
        "dpaste.com", "hastebin.com", "gitee.com",
    )

    if host in raw_hosts:
        return config_ext and has_hint
    if host in ("github.com", "gist.github.com"):
        return config_ext and has_hint
    # روابط من محركات أخرى عمومية (حقول Google Docs وs3 وغيرها): امتداد + hint
    return bool(config_ext and has_hint)


def _normalize_config_url(url: str) -> str:
    url = url.strip().rstrip(",.;")
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if parsed.scheme not in ("http", "https"):
        return ""
    # GitHub blob -> raw
    if parsed.netloc == "github.com" and "/blob/" in parsed.path:
        url = url.replace("github.com/", RAW_PREFIX.replace("https://", "") + "/", 1).replace("/blob/", "/", 1)
    # gist page -> raw
    if parsed.netloc == "gist.github.com" and "/raw/" not in parsed.path:
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}/raw"
    # روابط github بالشجرة refs/heads/<branch> -> /main/ القياسية
    url = re.sub(r"(raw\.githubusercontent\.com/[^/]+/[^/]+)/refs/heads/[^/]+/", r"\1/main/", url)
    return url


async def discover_google_urls(progress_cb=None, cancel_check=None, max_urls: int = 120, query_limit: int = 8) -> List[str]:
    """Smart web discovery: Google أولاً (HTML ثابت gbv=1)، وإن حُجب → DuckDuckGo HTML
    (يعرض نتائج محرك Google). النتيجة: روابط مباشرة لملفات اشتراكات عبر أي host."""
    found: Set[str] = set()

    def report(stage, current, total, detail=""):
        if progress_cb:
            progress_cb(stage, current, total, detail)

    queries = GOOGLE_QUERIES[:query_limit]
    headers = {
        "User-Agent": _GOOGLE_USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            google_blocked = False
            for i, query in enumerate(queries):
                if cancel_check and cancel_check():
                    break
                report("websearch", i + 1, len(queries), f"Web search: {query[:40]}")

                collected: Set[str] = set()
                # 1) حاول Google بصيغة HTML الأساسية (gbv=1) — بلا JS
                if not google_blocked:
                    try:
                        async with session.get(
                            GOOGLE_SEARCH,
                            params={"q": query, "num": "20", "gbv": "1", "hl": "en", "filter": "0"},
                            timeout=aiohttp.ClientTimeout(total=40),
                        ) as resp:
                            if resp.status == 200:
                                body = await resp.text(errors="ignore")
                                if _is_google_blocked(body):
                                    google_blocked = True
                                else:
                                    collected |= _extract_google_urls(body)
                    except Exception as e:
                        log.debug("Google fetch failed for %s: %s", query, e)

                    if not collected:
                        # 2) Google بصيغة عادية إن كانت gbv لا ترجع شيئاً
                        try:
                            async with session.get(
                                GOOGLE_SEARCH,
                                params={"q": query, "num": "20", "hl": "en"},
                                timeout=aiohttp.ClientTimeout(total=40),
                            ) as resp:
                                if resp.status == 200:
                                    body = await resp.text(errors="ignore")
                                    if not _is_google_blocked(body):
                                        collected |= _extract_google_urls(body)
                        except Exception as e:
                            log.debug("Google plain fetch failed for %s: %s", query, e)

                # 3) DuckDuckGo HTML إن لم يصلنا شيء من Google
                if not collected:
                    try:
                        async with session.get(
                            "https://html.duckduckgo.com/html/",
                            params={"q": query},
                            timeout=aiohttp.ClientTimeout(total=40),
                        ) as resp:
                            if resp.status == 200:
                                body = await resp.text(errors="ignore")
                                collected |= _extract_ddg_urls(body)
                    except Exception as e:
                        log.debug("DuckDuckGo fetch failed for %s: %s", query, e)

                for u in collected:
                    u = _normalize_config_url(u)
                    if u and _looks_like_any_subscription(u):
                        found.add(u)
                        if len(found) >= max_urls:
                            break

                await asyncio.sleep(2.5)
                if len(found) >= max_urls:
                    break
    except Exception as e:
        log.error("Web discovery failed: %s", e)

    report("websearch", len(found), len(found), "Web search complete")
    log.info("Web discovery: %d URLs found", len(found))
    return sorted(list(found))[:max_urls]


def _git_headers():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AragozLite/1.0"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


async def _get_json(session, url: str, params=None, api_limit_hit: List[bool] = None):
    try:
        async with session.get(url, params=params if params is not None else {}, timeout=aiohttp.ClientTimeout(total=30), headers=_git_headers()) as resp:
            if resp.status == 200:
                return await resp.json()
            if resp.status in (403, 429):
                if api_limit_hit is not None:
                    api_limit_hit[0] = True
                log.warning("GitHub API rate limit hit for %s", url)
    except Exception as e:
        log.debug("Failed to fetch JSON from %s: %s", url, e)
    return None


async def _get_text(session, url: str):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        log.debug("Failed to fetch text from %s: %s", url, e)
    return None


async def _search_repos(session, query: str, per_page: int, api_limit_hit: List[bool]) -> List[Tuple[str, str]]:
    if api_limit_hit[0]:
        return []
    data = await _get_json(
        session,
        f"{GITHUB_API}/search/repositories",
        params={
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": str(per_page),
        },
        api_limit_hit=api_limit_hit,
    )
    if not data:
        return []
    return [
        (item["full_name"], item.get("default_branch") or "main")
        for item in data.get("items", [])
    ]


def _looks_like_subscription(url: str) -> bool:
    lower = url.lower()
    if not url.startswith("https://raw.githubusercontent.com/"):
        return False
    path = urlparse(url).path.strip("/")
    segments = [s for s in path.split("/") if s]
    if len(segments) < 4:
        return False
    if lower.endswith((".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".css", ".js", ".woff", ".woff2", ".ttf", ".map")):
        return False
    if any(kw in lower for kw in ("subscribe", "sub_share", "sub_list", "share", "config", "vless", "vmess", "trojan", "ss://", "ssr", "hy2", "hysteria", "tuic", "wireguard", "wg", "naive", "proxy", "reality", "openvpn", "ovpn", "ikev2", "l2tp", "pptp", "softether", "ssh")):
        return True
    return bool(re.search(r"\.(txt|list|conf|yaml|yml|json)$", lower, re.IGNORECASE))


async def _fetch_raw_readme(session, repo: str, branch: str) -> str:
    """قراءة README عبر raw.githubusercontent (مجاناً، لا تستهلك حصة GitHub API)."""
    for name in ("README.md", "readme.md", "Readme.md", "README.txt", "README"):
        content = await _get_text(session, f"{RAW_PREFIX}/{repo}/{branch}/{name}")
        if content:
            return content
    return ""


async def _extract_readme_urls(session, repo: str, branch: str = "main") -> Set[str]:
    content = await _fetch_raw_readme(session, repo, branch)
    if not content:
        return set()
    urls = set(_URL_RE.findall(content))
    fixed = set()
    for u in urls:
        u = u.rstrip(",.;")
        try:
            parsed = urlparse(u)
            fixed.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
        except Exception:
            fixed.add(u)
    return {u for u in fixed if _looks_like_subscription(u)}


async def _scan_repo_tree(session, repo: str, branch: str, api_limit_hit: List[bool]) -> Set[str]:
    """Smart scan: مسح شجرة المستودع بالكامل بحثاً عن ملفات الاشتراكات."""
    if api_limit_hit[0]:
        return set()
    data = await _get_json(session, f"{GITHUB_API}/repos/{repo}/git/trees/{branch}", params={"recursive": "1"}, api_limit_hit=api_limit_hit)
    if not data:
        return set()
    urls: Set[str] = set()
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if _is_promising_config_path(path):
            urls.add(f"{RAW_PREFIX}/{repo}/{branch}/{path}")
        if len(urls) >= MAX_URLS_PER_REPO:
            break
    return urls


async def discover_github_urls(progress_cb=None, cancel_check=None) -> List[str]:
    found: Set[str] = set()
    seen_repos: Set[str] = set()
    api_limit_hit = [False]

    def report(stage: str, current: int, total: int, detail: str = ""):
        if progress_cb:
            progress_cb(stage, current, total, detail)

    try:
        async with aiohttp.ClientSession(headers=_git_headers()) as session:
            collected: List[Tuple[str, str]] = []
            for query in SEARCH_QUERIES:
                if cancel_check and cancel_check() or api_limit_hit[0]:
                    break
                report("discovering", 0, len(SEARCH_QUERIES), f"Searching: {query[:50]}")
                repos = await _search_repos(session, query, SEARCH_PER_PAGE, api_limit_hit)
                collected.extend(repos)
                if len(collected) >= TOTAL_SEARCH_RESULTS:
                    break
                await asyncio.sleep(0.25)

            seen_repos_count = 1
            tree_scans = 0
            for repo, branch in collected:
                if cancel_check and cancel_check():
                    break
                repo = repo.strip()
                if not repo or repo in seen_repos:
                    continue
                seen_repos.add(repo)
                report("discovering", seen_repos_count, len(collected), f"Scanning repo: {repo}")
                seen_repos_count += 1

                if tree_scans < MAX_TREE_SCANS and not api_limit_hit[0]:
                    urls = await _scan_repo_tree(session, repo, branch, api_limit_hit)
                    tree_scans += 1
                    if urls:
                        found |= urls

                readme_urls = await _extract_readme_urls(session, repo, branch)
                if readme_urls:
                    found |= readme_urls

                await asyncio.sleep(0.2)

                if len(found) >= MAX_DISCOVERED_URLS:
                    break
    except Exception as e:
        log.error("Discovery failed: %s", e)

    if api_limit_hit[0]:
        log.warning("GitHub API rate limit reached; continuing with KNOWN_SOURCES and discovered URLs")

    found |= set(KNOWN_SOURCES)
    report("discovering", len(found), len(found), "Discovery complete")
    log.info("Discovery complete: %d URLs found from %d repos", len(found), len(seen_repos))
    return sorted(list(found))[:MAX_DISCOVERED_URLS]


async def discover_all_urls(progress_cb=None, cancel_check=None) -> List[str]:
    """Smart discovery: GitHub أولاً ثم Google للمصادر غير المُكتشفة، ثم الدمج والختم.
    يُدمج دائماً: السجلّ الدائم للمصادر الناجحة + المصادر المعروفة (KNOWN_SOURCES)."""
    combined: Set[str] = set()

    combined |= _load_good_sources()
    combined |= set(KNOWN_SOURCES)

    github_urls = await discover_github_urls(progress_cb, cancel_check)
    combined |= set(github_urls)

    try:
        google_urls = await discover_google_urls(
            progress_cb, cancel_check, max_urls=120, query_limit=8
        )
        # أضف روابط Google الجديدة فقط (غير المكررة) ما دام لدينا سعة
        remaining = MAX_DISCOVERED_URLS - len(combined)
        if remaining > 0:
            for u in google_urls:
                if u in combined:
                    continue
                if u.startswith(RAW_PREFIX):
                    continue  # روابط raw.github مكررة عبر مسار GitHub
                combined.add(u)
                if len(combined) >= MAX_DISCOVERED_URLS:
                    break
    except Exception as e:
        log.error("Google discovery failed: %s", e)

    if progress_cb:
        progress_cb("discovering", len(combined), len(combined), "Combined discovery complete")
    log.info("Combined discovery complete: %d URLs", len(combined))
    # أولوية البذور: السجلّ الدائم ثم المصادر المعروفة أولاً، ثم الباقي — حتى لا تُقتطع عند السقف
    ordered = list(_load_good_sources()) + list(KNOWN_SOURCES)
    rest = sorted(u for u in combined if u not in ordered)
    result = list(dict.fromkeys(ordered + rest))[:MAX_DISCOVERED_URLS]
    return result