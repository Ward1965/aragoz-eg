import asyncio
import json
import re
import socket
import threading
import time
from typing import List, Dict, Optional

import aiohttp

from .logging_setup import get_logger
from .errors import AppError, ErrorCode
from .fetcher import fetch_all_sources, fetch_source, fetch_with_retry
from .parsers import parse_all, get_protocol_color
from .scraper import record_good_sources
from .storage import (
    save_configs,
    get_all_configs,
    get_config_by_id,
    delete_config,
    clear_all_configs,
    get_protocol_counts,
    export_as_text,
    export_as_base64,
    save_to_json,
    to_clash_yaml,
    search_configs,
    get_config_count,
    get_country_counts,
    is_dead_link,
    mark_dead_link,
    delete_configs_matching,
    delete_configs_by_ids,
)

log = get_logger("api")


def _parse_filters(filters: str):
    """Return (protocols, countries) from the JSON filter payload."""
    protocols: List[str] = []
    countries: List[str] = []
    if filters:
        try:
            parsed = json.loads(filters)
            if isinstance(parsed, list):
                protocols = [p for p in parsed if isinstance(p, str)]
            elif isinstance(parsed, dict):
                p = parsed.get("protocols")
                if isinstance(p, list):
                    protocols = [x for x in p if isinstance(x, str)]
                c = parsed.get("countries")
                if isinstance(c, list):
                    countries = [x for x in c if isinstance(x, str)]
        except (json.JSONDecodeError, TypeError) as e:
            log.debug("Failed to parse filters: %s", e)
    return protocols, countries


_PERMANENT_RE = re.compile(
    r"(?i)Network error: (400|401|403|404|405|410|413|414|415|451),|"
    r"Cannot connect to host|getaddrinfo|SSLCertVerification|certificate verify failed|"
    r"SSL: CERTIFICATE_VERIFY_FAILED|Name or service not known|No address associated"
)


def _is_permanent_error(err: str) -> bool:
    if not err:
        return False
    return bool(_PERMANENT_RE.search(err))


class JSApi:
    def __init__(self):
        self._configs: List[Dict] = []
        self._progress = {"phase": "idle", "current": 0, "total": 0, "detail": ""}
        self._cancelled = False
        self._dead_skipped = 0
        self._bg_result = None
        self._bg_error = None
        self._bg_lock = threading.Lock()
        self._ping_build = {"done": 0, "total": 0, "results": []}
        self._ping_map: Dict[str, int] = {}
        self._ping_session: Dict[str, int] = {}
        self._ping_on_insert = False
        try:
            from .storage import clear_ping_cache, clear_all_configs, clear_dead_links
            clear_all_configs()
            clear_ping_cache()
            clear_dead_links()
            log.info("Startup: cleared all configs, ping cache and dead-links cache (clean start)")
        except Exception as e:
            log.warning("Failed to clean state at startup: %s", e)
        log.info("JSApi initialized")

    def _reset_cancel(self):
        self._cancelled = False
        self._dead_skipped = 0

    def cancel(self) -> str:
        self._cancelled = True
        self._set_progress("idle", 0, 0, "Cancelled")
        log.info("Operation cancelled by user")
        return json.dumps({"success": True})

    def _set_progress(self, phase: str, current: int = 0, total: int = 0, detail: str = ""):
        self._progress = {"phase": phase, "current": current, "total": total, "detail": detail}

    def get_progress(self) -> str:
        payload = dict(self._progress)
        try:
            payload["count"] = get_config_count()
        except Exception:
            payload["count"] = 0
        return json.dumps(payload)

    def start_bg(self, task_name: str, urls_text: str = "", ping_on_insert: int = 0) -> str:
        self._reset_cancel()
        self._ping_on_insert = bool(ping_on_insert)
        if self._ping_on_insert:
            self._ping_session = {}
        if task_name in ("auto_fetch", "fetch_urls", "fetch_telegram"):
            from .storage import clear_ping_cache
            clear_ping_cache()
            self._ping_map = {}
            self._ping_session = {}
            log.info("Search started: cleared ping cache (configs accumulated)")
        with self._bg_lock:
            self._bg_result = None
            self._bg_error = None
        self._set_progress("starting", 0, 0, "Starting...")
        t = threading.Thread(target=self._bg_worker, args=(task_name, urls_text), daemon=True)
        t.start()
        log.info("Background task started: %s (ping_on_insert=%s)", task_name, self._ping_on_insert)
        return json.dumps({"status": "started"})

    def _bg_worker(self, task_name, urls_text):
        try:
            if task_name == "auto_fetch":
                result = self.auto_fetch_sync()
            elif task_name == "fetch_urls":
                result = self.fetch_urls_sync(urls_text)
            elif task_name == "fetch_telegram":
                result = self.fetch_telegram_sync(urls_text)
            elif task_name == "ping_all":
                result = self.ping_all_sync()
            else:
                result = json.dumps({"error": f"Unknown task: {task_name}"})
            with self._bg_lock:
                self._bg_result = result
        except Exception as e:
            log.error("Background task %s failed: %s", task_name, e)
            with self._bg_lock:
                self._bg_error = str(e)
                self._set_progress("error", 0, 0, str(e))

    def get_bg_result(self) -> str:
        with self._bg_lock:
            if self._bg_error:
                return json.dumps({"error": self._bg_error})
            if self._bg_result is not None:
                return self._bg_result
        return json.dumps({"status": "running"})

    def auto_fetch_sync(self) -> str:
        from .scraper import discover_all_urls

        def disc_progress(stage, current, total, detail=""):
            self._set_progress(stage, current, total, detail)

        urls = self._run_async(discover_all_urls(disc_progress, cancel_check=lambda: self._cancelled), timeout=300)
        if not urls:
            self._set_progress("done", 0, 0, "")
            log.warning("No sources auto-discovered")
            return json.dumps({"configs": [], "errors": ["No sources auto-discovered from the web"], "total": 0, "discovered": [], "cancelled": self._cancelled})

        self._set_progress("fetching", 0, len(urls), "")

        def fetch_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching sources")

        result = self._process_sources(urls, discovered=urls, fetch_progress=fetch_progress, cancel_check=lambda: self._cancelled)
        self._set_progress("done", 0, 0, "")
        return result

    def fetch_urls_sync(self, urls_text: str) -> str:
        all_lines = [u.strip() for u in urls_text.strip().split("\n") if u.strip()]
        urls = [l for l in all_lines if re.match(r"^https?://", l.lower())]
        bad = [l for l in all_lines if not re.match(r"^https?://", l.lower())]

        if not urls:
            return json.dumps({
                "configs": [], "errors": ["No valid subscription URLs found"],
                "total": 0, "discovered": [], "cancelled": False,
            })

        log.info("Fetching %d user-provided URLs", len(urls))
        self._set_progress("fetching", 0, len(urls), "Fetching sources")

        def fetch_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching sources")

        result = self._process_sources(urls, fetch_progress=fetch_progress, cancel_check=lambda: self._cancelled)
        if bad:
            data = json.loads(result)
            data["errors"] = [f"Skipped invalid URL: {u}" for u in bad] + data["errors"]
            result = json.dumps(data)
        self._set_progress("done", 0, 0, "")
        return result

    def fetch_telegram_sync(self, channels_text: str = "") -> str:
        from .telegram import (
            TELEGRAM_CHANNELS,
            normalize_channel,
            channel_page_url,
            extract_codes,
            extract_links,
        )

        channels = []
        if (channels_text or "").strip():
            for line in channels_text.split("\n"):
                ch = normalize_channel(line)
                if ch and ch not in channels:
                    channels.append(ch)
        else:
            for ch in TELEGRAM_CHANNELS:
                ch = normalize_channel(ch)
                if ch and ch not in channels:
                    channels.append(ch)

        if not channels:
            return json.dumps({
                "configs": [], "errors": ["No Telegram channels found"],
                "total": 0, "discovered": [], "cancelled": False,
            })

        urls = [channel_page_url(ch) for ch in channels]
        before_total = 0
        self._set_progress("telegram", 0, len(urls), "Scanning Telegram channels")
        log.info("Fetching from %d Telegram channels", len(channels))

        def tg_progress(current, total):
            self._set_progress("telegram", current, total, "Scanning Telegram channels")

        def link_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching subscription links from channels")

        errors = self._run_async(
            self._telegram_pipeline(urls, tg_progress, link_progress, cancel_check=lambda: self._cancelled),
            timeout=900,
        )

        after_total = get_config_count()
        added = max(0, after_total - before_total)
        self._configs = []
        log.info("Telegram fetch complete: %d channels, %d configs added", len(channels), added)
        self._set_progress("done", 0, 0, "")
        return json.dumps({
            "configs": [], "errors": errors,
            "total": after_total, "added": added,
            "discovered": [], "sources": len(channels),
            "cancelled": self._cancelled, "skipped": self._dead_skipped,
        })

    def _run_async(self, coro, timeout=120):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=timeout)
        else:
            return loop.run_until_complete(coro)

    async def _stream_sources(
        self,
        urls: List[str],
        on_batch,
        progress_cb=None,
        cancel_check=None,
        batch_size: int = 8,
        raw: bool = False,
        timeout: int = 90,
        concurrency: int = 96,
    ):
        errors: List[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "text/plain,text/html,application/json,*/*;q=0.8",
        }
        connector = aiohttp.TCPConnector(limit=concurrency, ttl_dns_cache=300)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            sem = asyncio.Semaphore(concurrency)

            async def fetch_one(url):
                async with sem:
                    if cancel_check and cancel_check():
                        return None
                    if is_dead_link(url):
                        self._dead_skipped += 1
                        return None
                    resp = await fetch_with_retry(url, session, raw=raw, timeout=timeout, retries=2)
                    if resp[2] and not resp[1] and _is_permanent_error(resp[2]):
                        mark_dead_link(url)
                    return resp

            tasks = [asyncio.create_task(fetch_one(u)) for u in urls]
            done = 0
            for coro in asyncio.as_completed(tasks):
                if cancel_check and cancel_check():
                    break
                try:
                    resp = await coro
                except Exception as e:
                    errors.append(str(e))
                    resp = None
                if resp:
                    url, content, err = resp
                    if err:
                        errors.append(f"{url}: {err}")
                    on_batch([{"url": url, "content": content, "error": err}])
                done += 1
                if progress_cb:
                    progress_cb(done, len(urls))
        return errors

    def _sink_parse_save(self, batch_srcs: List[Dict]):
        lines = []
        for src in batch_srcs:
            if src.get("content"):
                lines.extend(src["content"].split("\n"))
        configs = parse_all(lines)
        if configs:
            saved = save_configs(configs)
            log.debug("Parsed %d configs, saved %d new", len(configs), saved)
            if saved > 0 and self._ping_on_insert:
                self._ping_new_rows(configs)
            good = []
            for src in batch_srcs:
                content = src.get("content")
                if content and parse_all(content.split("\n")):
                    good.append(src.get("url"))
            if good:
                record_good_sources(good)

    def _ping_new_rows(self, configs: List[Dict]):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        unique = {}
        for cfg in configs:
            server = (cfg.get("server") or "").strip()
            port = int(cfg.get("port", 0) or 0)
            if not server or port <= 0:
                continue
            key = f"{server}:{port}"
            if key not in unique:
                unique[key] = (server, port)
        targets = list(unique.values())
        if not targets:
            return

        def _test(item):
            server, port = item
            key = f"{server}:{port}"
            try:
                start = time.time()
                sock = socket.create_connection((server, port), timeout=1.2)
                sock.close()
                return key, round((time.time() - start) * 1000)
            except socket.timeout:
                return key, -1
            except OSError:
                return key, -1
            except Exception:
                return key, -1

        workers = min(len(targets), 32)
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [ex.submit(_test, t) for t in targets]
            for fut in as_completed(futures):
                if self._cancelled:
                    break
                key, ms = fut.result()
                self._ping_map[key] = ms
                if self._ping_on_insert:
                    self._ping_session[key] = ms
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        log.debug("Pinged-on-insert: %d rows", len(targets))
        try:
            from .storage import save_ping_cache
            save_ping_cache(self._ping_map)
        except Exception as e:
            log.warning("Failed to persist ping cache: %s", e)

    def _is_plausible_subscription(self, url: str) -> bool:
        try:
            host = str(url.split("://", 1)[1].split("/", 1)[0]).lower()
        except Exception:
            return False
        if not host:
            return False
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
            return False
        if re.match(r"^\[?[0-9a-f:]+\]?$", host):
            return False
        return True

    async def _telegram_pipeline(
        self,
        channel_urls: List[str],
        on_channel_progress,
        on_link_progress,
        cancel_check=None,
    ) -> List[str]:
        from .telegram import extract_codes, extract_links

        errors: List[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            chan_sem = asyncio.Semaphore(14)

            async def fetch_channel(url: str):
                async with chan_sem:
                    if cancel_check and cancel_check():
                        return None
                    if is_dead_link(url):
                        self._dead_skipped += 1
                        return None
                    resp = await fetch_with_retry(url, session, raw=True, timeout=20, retries=1)
                    if resp[2] and not resp[1] and _is_permanent_error(resp[2]):
                        mark_dead_link(url)
                    return resp

            links = []
            links_seen = set()
            channel_tasks = [asyncio.create_task(fetch_channel(u)) for u in channel_urls]
            done_count = 0
            for coro in asyncio.as_completed(channel_tasks):
                if cancel_check and cancel_check():
                    break
                try:
                    resp = await coro
                except Exception as e:
                    errors.append(str(e))
                    resp = None
                if resp:
                    url, content, err = resp
                    if err:
                        errors.append(f"{url}: {err}")
                    elif content:
                        codes = extract_codes(content)
                        if codes:
                            cfgs = parse_all(codes)
                            if cfgs:
                                save_configs(cfgs)
                                if self._ping_on_insert:
                                    self._ping_new_rows(cfgs)
                        for l in extract_links(content):
                            if l not in links_seen and self._is_plausible_subscription(l):
                                links_seen.add(l)
                                links.append(l)
                done_count += 1
                on_channel_progress(done_count, len(channel_urls))

            link_sem = asyncio.Semaphore(20)
            links = links[:500]

            async def fetch_link(url: str):
                async with link_sem:
                    if cancel_check and cancel_check():
                        return None
                    if is_dead_link(url):
                        self._dead_skipped += 1
                        return None
                    resp = await fetch_with_retry(url, session, raw=False, timeout=10, retries=1)
                    if resp[2] and not resp[1] and _is_permanent_error(resp[2]):
                        mark_dead_link(url)
                    return resp

            link_done = 0
            link_tasks = [asyncio.create_task(fetch_link(u)) for u in links]
            for coro in asyncio.as_completed(link_tasks):
                if cancel_check and cancel_check():
                    break
                try:
                    resp = await coro
                except Exception as e:
                    errors.append(str(e))
                    resp = None
                if resp:
                    url, content, err = resp
                    if err:
                        errors.append(f"{url}: {err}")
                    elif content:
                        self._sink_parse_save([{"url": url, "content": content, "error": ""}])
                link_done += 1
                on_link_progress(link_done, len(link_tasks))

        return errors

    def _process_sources(self, urls: List[str], discovered=None, fetch_progress=None, cancel_check=None, timeout=1800) -> str:
        errors = []
        before_total = get_config_count()
        errors = self._run_async(
            self._stream_sources(urls, self._sink_parse_save, fetch_progress, cancel_check),
            timeout=timeout,
        )
        after_total = get_config_count()
        added = max(0, after_total - before_total)
        self._configs = []
        log.info("Processing complete: %d sources, %d configs added (total: %d)", len(urls), added, after_total)
        return json.dumps({
            "configs": [],
            "errors": errors,
            "total": after_total,
            "added": added,
            "discovered": discovered or [],
            "sources": len(urls),
            "cancelled": bool(cancel_check and cancel_check()),
            "skipped": self._dead_skipped,
        })

    def fetch_sources(self, urls_text: str) -> str:
        self._reset_cancel()
        all_lines = [u.strip() for u in urls_text.strip().split("\n") if u.strip()]
        if not all_lines:
            return self.auto_fetch()

        urls = []
        bad = []
        for line in all_lines:
            if re.match(r"^https?://", line.lower()):
                urls.append(line)
            else:
                bad.append(line)
        if not urls:
            return json.dumps({
                "configs": [],
                "errors": ["No valid subscription URLs found - only http/https links are accepted"],
                "total": 0,
                "discovered": [],
                "cancelled": False,
            })

        log.info("Fetching %d user-provided URLs", len(urls))

        def fetch_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching sources")

        self._set_progress("fetching", 0, len(urls), "Fetching sources")
        result = self._process_sources(urls, fetch_progress=fetch_progress, cancel_check=lambda: self._cancelled)
        if bad:
            data = json.loads(result)
            data["errors"] = [f"Skipped invalid URL (not http/https): {u}" for u in bad] + data["errors"]
            result = json.dumps(data)
        return result

    def discover_sources(self) -> str:
        from .scraper import discover_all_urls

        self._reset_cancel()

        def disc_progress(stage, current, total, detail=""):
            self._set_progress(stage, current, total, detail)

        urls = self._run_async(discover_all_urls(disc_progress, cancel_check=lambda: self._cancelled), timeout=300)
        log.info("Discovered %d URLs", len(urls))
        return json.dumps({"urls": urls, "total": len(urls)})

    def auto_fetch(self) -> str:
        from .scraper import discover_all_urls

        self._reset_cancel()

        def disc_progress(stage, current, total, detail=""):
            self._set_progress(stage, current, total, detail)

        urls = self._run_async(discover_all_urls(disc_progress, cancel_check=lambda: self._cancelled), timeout=300)
        if not urls:
            self._set_progress("done", 0, 0, "")
            log.warning("No sources auto-discovered")
            return json.dumps({"configs": [], "errors": ["No sources auto-discovered from the web"], "total": 0, "discovered": [], "cancelled": self._cancelled})

        self._set_progress("fetching", 0, len(urls), "")

        def fetch_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching sources")

        result = self._process_sources(urls, discovered=urls, fetch_progress=fetch_progress, cancel_check=lambda: self._cancelled)
        self._set_progress("done", 0, 0, "")
        return result

    def import_from_file(self, filepath: str = "") -> str:
        import webview as wv

        if not filepath:
            try:
                result = self._window.create_file_dialog(
                    wv.FileDialog.OPEN,
                    file_types=("Text files (*.txt;*.list;*.conf)", "All files (*.*)"),
                )
            except Exception as e:
                log.error("File dialog unavailable: %s", e)
                return json.dumps({"error": "File dialog unavailable", "configs": []})
            if not result:
                return json.dumps({"configs": [], "total": 0, "cancelled": True})
            filepath = result if isinstance(result, str) else result[0]

        self._set_progress("importing", 0, 0, "Reading file...")
        log.info("Importing from file: %s", filepath)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.error("Cannot read file %s: %s", filepath, e)
            return json.dumps({"error": f"Cannot read file: {e}", "configs": []})

        url_lines = []
        config_lines = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if re.match(r"^(vless|vmess|trojan|ssr|ss|hy2|hy1|hysteria2|hysteria|tuic|socks5|socks4|socks|wireguard|wg|naive\+https|naive\+h2|naive\+quic|ssh|ikev2|l2tp|pptp|softether)://", lower):
                config_lines.append(line)
            elif lower.startswith(("http://", "https://")):
                url_lines.append(line)
            else:
                config_lines.append(line)

        all_lines = list(config_lines)
        errors = []
        if url_lines:
            self._set_progress("importing", 0, len(url_lines), "Fetching URLs from file")

            def fetch_progress(current, total):
                self._set_progress("importing", current, total, "Fetching URLs from file")

            active_urls = [u for u in url_lines if not is_dead_link(u)]
            self._dead_skipped += len(url_lines) - len(active_urls)
            sources = self._run_async(fetch_all_sources(active_urls, progress_cb=fetch_progress))
            for src in sources:
                if src["error"]:
                    if not src.get("content") and _is_permanent_error(src["error"]):
                        mark_dead_link(src["url"])
                    errors.append(f"{src['url']}: {src['error']}")
                if src["content"]:
                    all_lines.extend(src["content"].split("\n"))

        self._set_progress("importing", 1, 1, "Parsing and saving configs...")
        configs = parse_all(all_lines)
        if configs:
            save_configs(configs)
        total = get_config_count()
        self._configs = []
        log.info("Import complete: %d configs total", total)
        return json.dumps({
            "configs": [],
            "errors": errors,
            "total": total,
            "added": total,
            "discovered": [],
        })

    def import_raw_text(self, text: str) -> str:
        lines = text.strip().split("\n")
        configs = parse_all(lines)
        if configs:
            save_configs(configs)
        total = get_config_count()
        self._configs = []
        log.info("Raw text import: %d configs total", total)
        return json.dumps({
            "configs": [],
            "errors": [],
            "total": total,
        })

    def _filtered_configs(self, query: str = "", filters: str = "", limit: int = 200000) -> List[Dict]:
        protocols, countries = _parse_filters(filters)
        rows, _ = search_configs(query, protocols, "", 1, 0, limit, countries)
        return rows

    def fetch_telegram(self, channels_text: str = "") -> str:
        from .telegram import (
            TELEGRAM_CHANNELS,
            normalize_channel,
            channel_page_url,
            extract_codes,
            extract_links,
        )

        self._reset_cancel()
        channels = []
        if (channels_text or "").strip():
            for line in channels_text.split("\n"):
                ch = normalize_channel(line)
                if ch and ch not in channels:
                    channels.append(ch)
        else:
            for ch in TELEGRAM_CHANNELS:
                ch = normalize_channel(ch)
                if ch and ch not in channels:
                    channels.append(ch)

        if not channels:
            return json.dumps({
                "configs": [],
                "errors": ["No Telegram channels found - enter channel links (@name or t.me/s/name)"],
                "total": 0,
                "discovered": [],
                "cancelled": False,
            })

        urls = [channel_page_url(ch) for ch in channels]
        before_total = 0
        self._set_progress("telegram", 0, len(urls), "Scanning Telegram channels")
        log.info("Fetching from %d Telegram channels", len(channels))

        def tg_progress(current, total):
            self._set_progress("telegram", current, total, "Scanning Telegram channels")

        def link_progress(current, total):
            self._set_progress("fetching", current, total, "Fetching subscription links from channels")

        errors = self._run_async(
            self._telegram_pipeline(urls, tg_progress, link_progress, cancel_check=lambda: self._cancelled),
            timeout=900,
        )

        after_total = get_config_count()
        added = max(0, after_total - before_total)
        self._configs = []
        log.info("Telegram fetch complete: %d channels, %d configs added", len(channels), added)
        return json.dumps({
            "configs": [],
            "errors": errors,
            "total": after_total,
            "added": added,
            "discovered": [],
            "sources": len(channels),
            "cancelled": self._cancelled,
            "skipped": self._dead_skipped,
        })

    def get_configs(
        self,
        query: str = "",
        filters: str = "",
        sort_key: str = "",
        sort_dir: int = 1,
        offset: int = 0,
        limit: int = 1000,
        ping: str = "",
    ) -> str:
        protocols, countries = _parse_filters(filters)
        limit = max(1, min(int(limit), 4000))
        offset = max(0, int(offset))
        rows, total = search_configs(
            query,
            protocols,
            sort_key,
            int(sort_dir if str(sort_dir).lstrip("-").isdigit() else 1),
            offset,
            limit,
            countries,
        )
        if ping:
            cats = {x for x in str(ping).split(",") if x}
            if cats:
                def _cat(key):
                    ms = self._ping_map.get(key)
                    if ms is None:
                        return "untested"
                    if ms < 0:
                        return "dead"
                    if ms < 150:
                        return "fast"
                    if ms < 300:
                        return "mid"
                    return "slow"
                all_rows, _ = search_configs(
                    query, protocols, sort_key,
                    int(sort_dir if str(sort_dir).lstrip("-").isdigit() else 1),
                    0, 200000, countries,
                )
                filtered = [
                    r for r in all_rows
                    if _cat(f"{(r.get('server') or '').strip()}:{int(r.get('port') or 0)}") in cats
                ]
                total = len(filtered)
                rows = filtered[offset: offset + limit]
        self._configs = rows
        return json.dumps({"configs": self._to_frontend(rows), "total": total})

    def get_raw(self, config_id: int) -> str:
        cfg = get_config_by_id(config_id)
        return json.dumps({"raw": cfg.get("raw", "") if cfg else "", "found": bool(cfg)})

    def get_config_detail(self, config_id: int) -> str:
        cfg = get_config_by_id(config_id)
        if not cfg:
            return json.dumps({"error": "Config not found"})
        detail = {k: v for k, v in cfg.items() if k != "raw"}
        detail["raw"] = cfg.get("raw", "")
        return json.dumps(detail)

    def get_app_logo(self) -> str:
        from .logo_data import LOGO_MIME, LOGO_B64
        return json.dumps({"mime": LOGO_MIME, "data": LOGO_B64})

    def delete_config(self, config_id: int) -> str:
        delete_config(config_id)
        return json.dumps({"success": True})

    def clear_all(self) -> str:
        clear_all_configs()
        self._configs = []
        return json.dumps({"success": True})

    def delete_filtered(
        self,
        query: str = "",
        filters: str = "",
        ping: str = "",
    ) -> str:
        """Delete only the rows matching the current filters/search/ping (not everything)."""
        protocols, countries = _parse_filters(filters)
        cats = {x for x in str(ping).split(",") if x}
        if cats:
            all_rows, _ = search_configs(
                query,
                protocols,
                "",
                1,
                0,
                200000,
                countries,
            )

            def _cat(key):
                ms = self._ping_map.get(key)
                if ms is None:
                    return "untested"
                if ms < 0:
                    return "dead"
                if ms < 150:
                    return "fast"
                if ms < 300:
                    return "mid"
                return "slow"

            ids = [
                r.get("id")
                for r in all_rows
                if _cat(f"{(r.get('server') or '').strip()}:{int(r.get('port') or 0)}") in cats
            ]
            deleted = delete_configs_by_ids([i for i in ids if i is not None])
        else:
            deleted = delete_configs_matching(query, protocols, countries)
        self._configs = []
        return json.dumps({"success": True, "deleted": deleted})

    def export_text(self, query: str = "", filters: str = "") -> str:
        configs = self._filtered_configs(query, filters)
        return export_as_text(configs)

    def export_base64(self, query: str = "", filters: str = "") -> str:
        configs = self._filtered_configs(query, filters)
        return export_as_base64(configs)

    def export_file(self, filetype: str = "txt", query: str = "", filters: str = "") -> str:
        import webview as wv

        definitions = {
            "txt": ("configs.txt", ".txt", "Text files (*.txt)"),
            "b64": ("subscription.b64", ".b64", "Base64 subscription (*.b64)"),
            "json": ("configs.json", ".json", "JSON files (*.json)"),
            "yaml": ("clash.yaml", ".yaml", "YAML files (*.yaml)"),
        }
        filetype = (filetype or "txt").lower()
        if filetype not in definitions:
            return json.dumps({"error": "Unsupported export type"})
        default_name, ext, file_filter = definitions[filetype]

        try:
            result = self._window.create_file_dialog(
                wv.FileDialog.SAVE,
                save_filename=default_name,
                file_types=(file_filter, "All files (*.*)"),
            )
        except Exception as e:
            log.error("File dialog unavailable: %s", e)
            return json.dumps({"error": f"File dialog unavailable: {e}"})
        if not result:
            return json.dumps({"cancelled": True})
        filepath = result if isinstance(result, str) else result[0]

        configs = self._filtered_configs(query, filters)
        if not configs:
            return json.dumps({"error": "No configs to export"})

        try:
            if filetype == "txt":
                content = export_as_text(configs)
            elif filetype == "b64":
                content = export_as_base64(configs)
            elif filetype == "json":
                clean = [
                    {k: v for k, v in c.items() if k not in ("id", "raw", "created_at")}
                    for c in configs
                ]
                content = json.dumps(clean, indent=2, ensure_ascii=False)
            else:
                content = to_clash_yaml(configs)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            log.info("Exported %d configs to %s (%s)", len(configs), filepath, filetype)
        except Exception as e:
            log.error("Cannot write file %s: %s", filepath, e)
            return json.dumps({"error": f"Cannot write file: {e}"})
        return json.dumps({"success": True, "path": filepath})

    def export_json(self, filepath: str) -> str:
        configs = get_all_configs()
        save_to_json(configs, filepath)
        return json.dumps({"success": True, "path": filepath})

    def get_qr(self, config_id: int, content: str = "") -> str:
        import qrcode.image.svg

        text = content or ""
        if not text and config_id:
            cfg = get_config_by_id(config_id)
            text = cfg.get("raw", "") if cfg else ""

        text = text.strip()
        if not text:
            return json.dumps({"error": "No content to encode"})
        if len(text) > 4000:
            return json.dumps({"error": "Content too long for QR code"})

        try:
            img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
            svg = img.to_string().decode("utf-8")
            return json.dumps({"svg": svg, "text": text})
        except Exception as e:
            log.error("QR generation failed: %s", e)
            return json.dumps({"error": f"QR generation failed: {e}"})

    def get_protocol_counts(self) -> str:
        counts = get_protocol_counts()
        return json.dumps(
            {
                "total": sum(counts.values()),
                "items": [
                    {"type": t, "count": c, "color": get_protocol_color(t)}
                    for t, c in counts.items()
                ],
            }
        )

    def get_country_counts(self) -> str:
        from .storage import get_total_configs
        items = get_country_counts()
        return json.dumps({"total": get_total_configs(), "items": items})

    def test_latency(self, server: str, port: int) -> str:
        try:
            start = time.time()
            sock = socket.create_connection((server, int(port)), timeout=3)
            sock.close()
            ms = round((time.time() - start) * 1000)
            self._ping_map[f"{server}:{int(port)}"] = ms
            return json.dumps({"ms": ms, "ok": True})
        except socket.timeout:
            self._ping_map[f"{server}:{int(port)}"] = -1
            return json.dumps({"ms": -1, "ok": False, "error": "timeout"})
        except OSError as e:
            self._ping_map[f"{server}:{int(port)}"] = -1
            return json.dumps({"ms": -1, "ok": False, "error": str(e)})

    def test_latency_batch(self, ids: str = "") -> str:
        from concurrent.futures import ThreadPoolExecutor
        id_list = [int(x) for x in str(ids).split(",") if x.strip().isdigit()]
        if not id_list:
            return json.dumps({"error": "No config IDs provided"})
        id_list = id_list[:1000]

        def _test(cid):
            cfg = get_config_by_id(cid)
            if not cfg:
                return cid, {"ms": -1, "ok": False, "error": "not found"}
            server = cfg.get("server", "")
            port = int(cfg.get("port", 0) or 0)
            if not server or port <= 0:
                return cid, {"ms": -1, "ok": False, "error": "no server"}
            try:
                start = time.time()
                sock = socket.create_connection((server, port), timeout=3)
                sock.close()
                return cid, {"ms": round((time.time() - start) * 1000), "ok": True}
            except socket.timeout:
                return cid, {"ms": -1, "ok": False, "error": "timeout"}
            except OSError as e:
                return cid, {"ms": -1, "ok": False, "error": str(e)}

        workers = min(len(id_list), 200)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = dict(ex.map(_test, id_list))
        return json.dumps(results)

    def ping_all_sync(self) -> str:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from .storage import get_all_configs

        def key_of(s, p):
            return f"{s}:{p}"

        rows = get_all_configs()
        weights = {}
        unique = {}
        for cfg in rows:
            server = (cfg.get("server") or "").strip()
            port = int(cfg.get("port", 0) or 0)
            if not server or port <= 0:
                continue
            key = key_of(server, port)
            weights[key] = weights.get(key, 0) + 1
            if key not in unique:
                unique[key] = {"server": server, "port": port}
        targets = list(unique.values())
        total = sum(weights.values())
        self._ping_build = {"done": 0, "total": total, "results": []}
        if total == 0:
            self._set_progress("ping_done", 0, 0, "")
            return json.dumps({"done": 0, "total": 0})

        def _test(item):
            server = item["server"]
            port = item["port"]
            try:
                start = time.time()
                sock = socket.create_connection((server, port), timeout=1.2)
                sock.close()
                return key_of(server, port), {"ms": round((time.time() - start) * 1000), "ok": True}
            except socket.timeout:
                return key_of(server, port), {"ms": -1, "ok": False, "error": "timeout"}
            except OSError as e:
                return key_of(server, port), {"ms": -1, "ok": False, "error": str(e)}
            except Exception:
                return key_of(server, port), {"ms": -1, "ok": False, "error": "invalid"}

        workers = min(total, 800)
        done = 0
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [ex.submit(_test, t) for t in targets]
            for fut in as_completed(futures):
                if self._cancelled:
                    log.info("ping_all cancelled at %d/%d", done, total)
                    ex.shutdown(wait=False, cancel_futures=True)
                    self._ping_build["done"] = done
                    self._set_progress("cancelled", done, total, "")
                    return json.dumps({"done": done, "total": total, "cancelled": True})
                key, res = fut.result()
                self._ping_build["results"].append({"key": key, "ms": res.get("ms", -1), "ok": res.get("ok", False), "error": res.get("error", "")})
                self._ping_map[key] = res.get("ms", -1)
                done += weights.get(key, 1)
                self._ping_build["done"] = done
                if done % 500 == 0 or done >= total:
                    log.info("ping_all progress %d/%d", done, total)
                    self._set_progress("pinging", done, total, f"Tested {done}/{total}")
        except Exception as e:
            log.error("ping_all error: %s", e, exc_info=True)
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        ex.shutdown(wait=False)
        log.info("ping_all finished %d/%d", done, total)
        self._set_progress("ping_done", total, total, "")
        try:
            from .storage import save_ping_cache
            save_ping_cache(self._ping_map)
        except Exception as e:
            log.warning("Failed to persist ping cache: %s", e)
        return json.dumps({"done": total, "total": total})

    def clear_ping(self) -> str:
        self._ping_map.clear()
        self._ping_build = {"done": 0, "total": 0, "results": []}
        try:
            from .storage import clear_ping_cache
            clear_ping_cache()
        except Exception as e:
            log.warning("Failed to clear ping cache: %s", e)
        log.info("Ping results cleared")
        return json.dumps({"ok": True})

    def get_ping_map(self) -> str:
        """Return full {server:port: ms} map so the UI can render filters instantly."""
        return json.dumps({"map": {k: v for k, v in self._ping_map.items()}})

    def get_ping_session(self) -> str:
        """Return pings recorded during the current ping-on-insert session."""
        return json.dumps({"map": {k: v for k, v in self._ping_session.items()}})

    def get_ping_stats(self) -> str:
        from .storage import get_all_configs

        rows = get_all_configs()
        counts = {"fast": 0, "mid": 0, "slow": 0, "dead": 0, "untested": 0, "total": len(rows)}
        for cfg in rows:
            server = (cfg.get("server") or "").strip()
            port = int(cfg.get("port", 0) or 0)
            if not server or port <= 0:
                continue
            ms = self._ping_map.get(f"{server}:{port}")
            if ms is None:
                counts["untested"] += 1
            elif ms < 0:
                counts["dead"] += 1
            elif ms < 150:
                counts["fast"] += 1
            elif ms < 300:
                counts["mid"] += 1
            else:
                counts["slow"] += 1
        return json.dumps(counts)

    def get_ping_progress(self) -> str:
        pb = getattr(self, "_ping_build", {"done": 0, "total": 0, "results": []})
        return json.dumps({"done": pb["done"], "total": pb["total"], "count": len(pb["results"])})

    def get_ping_batch(self, since: int = 0) -> str:
        pb = getattr(self, "_ping_build", {"results": []})
        results = pb["results"]
        batch = results[since:]
        return json.dumps({"since": len(results), "batch": batch})

    def _to_frontend(self, configs: List[Dict]) -> List[Dict]:
        result = []
        for cfg in configs:
            entry = {
                "id": cfg.get("id", 0),
                "protocol": cfg.get("protocol", ""),
                "protocol_type": cfg.get("protocol_type", ""),
                "name": cfg.get("name", ""),
                "server": cfg.get("server", ""),
                "port": cfg.get("port", 0),
                "expires_at": cfg.get("expires_at", "") or "",
                "country": cfg.get("country", ""),
                "color": get_protocol_color(cfg.get("protocol_type", "")),
            }
            result.append(entry)
        return result
