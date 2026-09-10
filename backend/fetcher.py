import asyncio
import base64
import aiohttp
from typing import List, Dict, Tuple


async def fetch_url(url: str, timeout: int = 30, session=None) -> str:
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            resp.raise_for_status()
            return await resp.text()
    finally:
        if own_session:
            await session.close()


def try_base64_decode(text: str) -> str:
    try:
        decoded = base64.b64decode(text.strip()).decode("utf-8")
        if any(proto in decoded for proto in [
            "vless://", "vmess://", "trojan://", "ss://", "ssr://",
            "hy2://", "hysteria://", "hysteria2://", "hy1://", "tuic://",
            "wg://", "socks://", "naive+",
            "http://", "https://"
        ]):
            return decoded
    except Exception:
        pass
    return text


def split_lines(raw: str) -> List[str]:
    raw = raw.strip()
    if not raw:
        return []
    if "\r\n" in raw:
        lines = raw.split("\r\n")
    elif "\n" in raw:
        lines = raw.split("\n")
    else:
        lines = raw.split("\r")
    return [line.strip() for line in lines if line.strip()]


async def fetch_source(url: str, timeout: int = 30, session=None, raw: bool = False) -> Tuple[str, str, str]:
    try:
        content = await fetch_url(url, timeout=timeout, session=session)
        if raw:
            return url, content, ""
        decoded = try_base64_decode(content)
        lines = split_lines(decoded)
        return url, "\n".join(lines), ""
    except asyncio.TimeoutError:
        return url, "", "Timeout"
    except aiohttp.ClientError as e:
        return url, "", f"Network error: {e}"
    except Exception as e:
        return url, "", str(e)


async def fetch_all_sources(urls: List[str], progress_cb=None, cancel_check=None) -> List[Dict]:
    sources = []
    batch_size = 8
    for i in range(0, len(urls), batch_size):
        if cancel_check and cancel_check():
            break
        batch = urls[i:i + batch_size]
        tasks = [fetch_source(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, result in zip(batch, results):
            if isinstance(result, Exception):
                sources.append({"url": url, "content": "", "error": str(result)})
            else:
                src_url, content, error = result
                sources.append({"url": src_url, "content": content, "error": error})
        if progress_cb:
            progress_cb(min(i + len(batch), len(urls)), len(urls))
    return sources


def read_local_file(filepath: str) -> List[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = split_lines(f.read())
        urls = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("http://") or line.startswith("https://"):
                    urls.append(line)
                else:
                    urls.append(line)
        return urls
    except Exception:
        return []
