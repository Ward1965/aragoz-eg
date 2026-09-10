import asyncio
import base64
import re
from typing import List, Set
from urllib.parse import urlparse

import aiohttp

GITHUB_API = "https://api.github.com"
RAW_PREFIX = "https://raw.githubusercontent.com"

SEARCH_QUERIES = [
    "topic:v2ray",
    "topic:shadowsocks",
    "topic:shadowsocksr",
    "topic:vpn-subscription",
    "topic:proxy-subscription",
    "topic:sing-box",
    "topic:clash-config",
    "topic:hysteria2",
    "topic:tuic",
    "topic:v2ray-reality",
    "topic:xray",
    "v2ray subscription share",
    "free proxy configs txt",
    "vless reality subscribe",
    "ssr subscription txt",
    "wireguard config share",
    "free hysteria tuic subscription",
]

SEARCH_PER_PAGE = 5
TOTAL_SEARCH_RESULTS = 20
MAX_DISCOVERED_URLS = 60

# روابط مصدر معروفة ومستقرة تُستخدم كبذرة إضافية حتى لو تعطل discovery
KNOWN_SOURCES = [
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
]

_URL_RE = re.compile(r"https?://[^\s\)\]\}\"'`<>]+")


async def _get_json(session, url: str, params=None):
    try:
        async with session.get(url, params=params if params is not None else {}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:
        return None
    return None


async def _get_text(session, url: str):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        return None
    return None


async def _search_repos(session, query: str, per_page: int) -> List[str]:
    data = await _get_json(
        session,
        f"{GITHUB_API}/search/repositories",
        params={
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": str(per_page),
        },
    )
    if not data:
        return []
    return [item["full_name"] for item in data.get("items", [])]


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
    if any(kw in lower for kw in ("subscribe", "sub_share", "sub_list", "share", "config", "vless", "vmess", "trojan", "ss://", "ssr", "hy2", "hysteria", "tuic", "wireguard", "wg", "naive", "proxy", "reality")):
        return True
    return bool(re.search(r"\.(txt|list|conf|yaml|yml|json)$", lower, re.IGNORECASE))


async def _extract_readme_urls(session, repo: str) -> Set[str]:
    raw = await _get_json(session, f"{GITHUB_API}/repos/{repo}/readme")
    if not raw or "content" not in raw:
        return set()
    try:
        content = base64.b64decode(raw["content"].replace("\n", "")).decode("utf-8", "ignore")
    except Exception:
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


async def discover_github_urls(progress_cb=None, cancel_check=None) -> List[str]:
    found: Set[str] = set()
    seen_repos: Set[str] = set()

    def report(stage: str, current: int, total: int, detail: str = ""):
        if progress_cb:
            progress_cb(stage, current, total, detail)

    try:
        async with aiohttp.ClientSession(headers={"Accept": "application/vnd.github+json", "User-Agent": "AragozLite/1.0"}) as session:
            collected = []
            for query in SEARCH_QUERIES:
                if cancel_check and cancel_check():
                    break
                report("discovering", 0, len(SEARCH_QUERIES), f"Searching: {query}")
                repos = await _search_repos(session, query, SEARCH_PER_PAGE)
                collected.extend(repos)
                if len(collected) >= TOTAL_SEARCH_RESULTS:
                    break
                await asyncio.sleep(1.2)

            seen_repos_count = 1
            for repo in collected:
                if cancel_check and cancel_check():
                    break
                repo = repo.strip()
                if not repo or repo in seen_repos:
                    continue
                seen_repos.add(repo)
                report("discovering", seen_repos_count, len(collected), f"Scanning repo: {repo}")
                seen_repos_count += 1

                urls = await _extract_readme_urls(session, repo)
                if urls:
                    found |= urls

                default_url = await _get_text(session, f"{RAW_PREFIX}/{repo}/HEAD/sub/sub_share.txt")
                if default_url and any(p in default_url for p in ("vless://", "vmess://", "trojan://", "ss://", "ssr://", "hy2://", "hysteria://", "hysteria2://", "tuic://", "wg://", "naive+")):
                    found.add(f"{RAW_PREFIX}/{repo}/HEAD/sub/sub_share.txt")

                await asyncio.sleep(1.0)

                if len(found) >= MAX_DISCOVERED_URLS:
                    break
    except Exception:
        pass

    report("discovering", len(found), len(found), "Discovery complete")
    return sorted(list(found))[:MAX_DISCOVERED_URLS]