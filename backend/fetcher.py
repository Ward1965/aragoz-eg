import asyncio
import base64
import datetime
import email.utils
import socket
import aiohttp
from typing import List, Dict, Optional, Tuple

from .logging_setup import get_logger

log = get_logger("fetcher")

# لا نجلب ملفات/كونفيغات قديمة: أي ملف مصدر لم يُعدّل منذ أكثر من شهر يُستبعد
STALE_AGE_DAYS = 30

PROTOCOL_PREFIXES = (
    "vless://", "vmess://", "trojan://", "ss://", "ssr://",
    "hy2://", "hysteria://", "hysteria2://", "hy1://", "tuic://",
    "wg://", "socks://", "socks4://", "socks5://",
    "naive+https://", "naive+h2://", "naive+quic://",
    "ssh://", "ikev2://", "l2tp://", "pptp://", "softether://",
    "http://", "https://",
)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = 0.5
CHUNK_SIZE = 32
INTERNET_PROBE_HOSTS = (("1.1.1.1", 53), ("8.8.8.8", 53), ("github.com", 443))


def has_internet(timeout: float = 2.0) -> bool:
    """فحص سريع لوجود اتصال بالشبكة دون إجراء عمليات HTTP حقيقية."""
    for host, port in INTERNET_PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
        except Exception:
            continue
    return False


def _parse_last_modified(header: str) -> Optional[datetime.datetime]:
    """تفسير رأس Last-Modified (HTTP-date) إلى datetime aware UTC."""
    try:
        dt = email.utils.parsedate_to_datetime(header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _is_stale(header: str) -> bool:
    """هل الملف أقدم من STALE_AGE_DAYS وفق رأس Last-Modified؟"""
    if not header:
        return False
    modified = _parse_last_modified(header)
    if modified is None:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - modified
    return age.total_seconds() > STALE_AGE_DAYS * 86400


async def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT, session=None) -> Tuple[str, str]:
    """جلب محتوى URL + رأس Last-Modified (إن وجد)."""
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        # مهلة ذكية: لا مهلة إجمالية (لا تقتل الملفات الكبيرة التي تتدفق بثبات)،
        # بل مهلة لكل قراءة/اتصال — تتوقف فقط عند توقّف التدفق الفعلي.
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=None, connect=30, sock_read=max(30, timeout * 2)),
        ) as resp:
            resp.raise_for_status()
            content = await resp.text()
            last_modified = resp.headers.get("Last-Modified", "")
            return content, last_modified
    finally:
        if own_session:
            await session.close()


def try_base64_decode(text: str) -> str:
    try:
        decoded = base64.b64decode(text.strip()).decode("utf-8")
        if any(proto in decoded for proto in PROTOCOL_PREFIXES):
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


async def fetch_source(url: str, timeout: int = DEFAULT_TIMEOUT, session=None, raw: bool = False) -> Tuple[str, str, str]:
    try:
        content, last_modified = await fetch_url(url, timeout=timeout, session=session)
        if _is_stale(last_modified):
            log.info("Skipping stale source (%s): last modified %s > %d days", url, last_modified, STALE_AGE_DAYS)
            return url, "", f"Stale source (last modified > {STALE_AGE_DAYS} days)"
        if raw:
            return url, content, ""
        decoded = try_base64_decode(content)
        lines = split_lines(decoded)
        return url, "\n".join(lines), ""
    except asyncio.TimeoutError:
        log.warning("Timeout fetching %s after %ds", url, timeout)
        return url, "", "Timeout"
    except aiohttp.ClientError as e:
        log.warning("Network error fetching %s: %s", url, e)
        return url, "", f"Network error: {e}"
    except Exception as e:
        log.error("Unexpected error fetching %s: %s", url, e)
        return url, "", str(e)


async def fetch_with_retry(
    url: str,
    session,
    raw: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Tuple[str, str, str]:
    import re
    transient = re.compile(r"(?i)timeout|timed\s?out|429|50[234]|connect")
    last_resp = None
    for attempt in range(retries + 1):
        resp = await fetch_source(url, timeout=timeout, session=session, raw=raw)
        last_resp = resp
        _, content, err = resp
        if not err or attempt >= retries or not transient.search(err):
            return resp
        delay = DEFAULT_RETRY_DELAY * (2 ** attempt)
        log.debug("Retrying %s (attempt %d/%d) after %.1fs delay", url, attempt + 1, retries, delay)
        await asyncio.sleep(delay)
    return last_resp or (url, "", "Max retries exceeded")


async def fetch_all_sources(urls: List[str], progress_cb=None, cancel_check=None) -> List[Dict]:
    log.info("Fetching %d sources (chunk_size=%d)", len(urls), CHUNK_SIZE)
    sources = []
    for i in range(0, len(urls), CHUNK_SIZE):
        if cancel_check and cancel_check():
            log.info("Fetch cancelled at %d/%d", i, len(urls))
            break
        batch = urls[i : i + CHUNK_SIZE]
        tasks = [fetch_with_retry(url, session=None) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, result in zip(batch, results):
            if isinstance(result, Exception):
                log.error("Failed to fetch %s: %s", url, result)
                sources.append({"url": url, "content": "", "error": str(result)})
            else:
                src_url, content, error = result
                sources.append({"url": src_url, "content": content, "error": error})
        if progress_cb:
            progress_cb(min(i + len(batch), len(urls)), len(urls))
    log.info("Fetch complete: %d sources processed", len(sources))
    return sources


def read_local_file(filepath: str) -> List[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = split_lines(f.read())
        urls = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
        log.info("Read %d lines from %s", len(urls), filepath)
        return urls
    except Exception as e:
        log.error("Failed to read file %s: %s", filepath, e)
        return []
