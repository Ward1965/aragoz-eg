# Aragoz Lite

**Aragoz Lite** is a lightweight desktop app that discovers, fetches, parses, organizes and exports proxy / VPN configs (VLESS, VMess, Trojan, Shadowsocks, Hysteria2, TUIC, WireGuard, SOCKS, HTTP/S and more) from subscriptions, GitHub sources, Telegram channels and the open web — all in one place.

Built with **pywebview** (native window + HTML/CSS/JS UI) — no Electron, no heavyweight framework.

![Dark mode UI](https://img.shields.io/badge/theme-dark-blueviolet)
![Python](https://img.shields.io/badge/python-3.10%2B-informational)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- **Scan Web (Auto)** — discovers new config sources from GitHub repositories / raw files, Google and DuckDuckGo search results (`MAX_DISCOVERED_URLS = 400`).
- **Smart source registry** — verified sources (`good_sources.json`) are reused across scans so results stay stable and grow over time.
- **Fetch URLs / subscriptions** — paste one link or a list; plain text and Base64 subscription payloads are decoded automatically.
- **Telegram channels** — fetch and expand config links from Telegram channel pages.
- **Import** — from a local file or raw pasted text.
- **Protocol parsing & dedup** — URI parsers for every major protocol, plus structured parsers for **Clash YAML** and **Sing-box JSON** sources; duplicates are removed and each config keeps its original source attribution.
- **Live table** — search as you type, filter by protocol / country / ping status, per-protocol counts, details modal, QR code, one-click copy.
- **Latency tests** — ping one config or *Ping All* on the currently filtered scope (async, batched).
- **Export** — copy as text, Base64 subscription, or save to file (per filtered selection).
- **Dark-first UI** — clean dark theme (light toggle available), keyboard shortcuts, single-instance guard, sudden white-flash-free native window.
- **Clean start** — fresh DB, ping and dead-link caches on every launch (you always start from a clean table).

## Supported protocols & formats

| URI schemes | Also parsed |
|---|---|
| `vless://`, `vmess://`, `trojan://` | SSR, Hysteria, Hysteria2, NaiveProxy |
| `ss://` | WireGuard (`wireguard://` + `wg-quick` blocks), TUIC |
| `hy2://` / `hysteria2://` / `hysteria://` / `hy1://` | SOCKS4 / SOCKS5 / SOCKS |
| `tuic://`, `wireguard://` | HTTP / HTTPS proxies, gateway accounts |
| `socks://`, `socks4://`, `socks5://` | OpenVPN, SSH, IKEv2, L2TP, PPTP, SoftEther |

- **Structured sources:** Clash YAML (`proxies:`) and Sing-box JSON (v2/v1 `outbounds`).
- **Metadata extraction:** country (server/ISO lookup), expiry dates (ISO / timestamp), remarks, and per-source attribution.
- Configs older than **30 days** (by `expires_at`) are filtered out on read.

## Requirements

- Python **3.10+**
- Windows 10/11 ships with **WebView2** runtime (used by pywebview). macOS uses **WebKit**, Linux uses **GTK WebKit** (see below).

## Run from source

```bash
git clone https://github.com/Ward1965/aragoz.git
cd aragoz
pip install -r requirements.txt
python main.py
```

> On Linux you also need system WebKit/GTK packages, e.g. (Debian/Ubuntu):
> `sudo apt install python3-gi gir1.2-webkit2-4.0 libcairo2-dev pkg-config`
>
> On macOS: `pip install "pywebview[cocoa]"` pulls the required PyObjC frameworks.

## Build executables

The project ships a cross-platform PyInstaller spec (`Aragoz Lite.spec`) and a CI workflow that builds all three targets automatically.

### Locally with PyInstaller

```bash
pip install pyinstaller
pyinstaller --noconfirm "Aragoz Lite.spec"
```

- **Windows** → `dist/Aragoz Lite.exe` (single file, no console).
- **macOS** (Intel or Apple Silicon) → `dist/Aragoz Lite` (single-file Mach-O binary). Build it **on** macOS.
- **Linux** → `dist/Aragoz Lite` (single-file ELF binary). Build it **on** Linux with the GTK/WebKit dev packages installed.

> One-file mode uses `_MEIPASS` for frontend assets; DBs/logs are written next to the executable on Windows/Linux and under `~/Library/Application Support/Aragoz Lite` on macOS.

### GitHub Actions (recommended)

Pushing a release tag (or any push with workflow dispatch) builds **Windows**, **macOS (arm64)** and **Linux** on native runners and attaches the artifacts/release. See [`.github/workflows/build.yml`](.github/workflows/build.yml).

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+F` | Focus search |
| `Ctrl+R` | Scan web |
| `Ctrl+L` | Focus URL input |
| `Ctrl+E` | Export configs |
| `Ctrl+I` | Import from file |
| `Ctrl+D` | Show config details |

## Project structure

```
aragoZ-lite/
├── main.py                 # pywebview entry: welcome window + main window (maximize on start)
├── Aragoz Lite.spec        # cross-platform PyInstaller spec
├── requirements.txt
├── backend/
│   ├── api.py              # JSApi exposed to JS (fetch, scan, import/export, ping, QR …)
│   ├── fetcher.py          # aiohttp streaming fetch (timeouts by progress, chunk batches)
│   ├── scraper.py          # web discovery (GitHub/Google/DDG), seeds + good-source registry
│   ├── parsers.py          # protocol URI parsers + Clash YAML / Sing-box JSON
│   ├── storage.py          # SQLite storage, caching, dead-links, ping maps
│   └── logging_setup.py    # rotating file logger
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── good_sources.json       # (runtime) verified source list, preserved across scans
├── configs.db              # (runtime) SQLite database, recreated on each start
└── .github/workflows/build.yml
```

## Data & runtime files

| File | Purpose |
|---|---|
| `configs.db` | SQLite store; recreated fresh every launch (clean start). |
| `good_sources.json` | Persisted list of sources whose content parsed successfully (drives stable discovery). |
| `dead_links.json` | Failed URLs cache; cleared at startup so links are re-tested each run. |
| `logs/aragoz.log` | Rotating application logs. |

## Disclaimer

This tool only fetches, lists and reorganizes public config URLs. **You are responsible** for how you use the configs and for complying with your local laws and the terms of the sources you fetch. The project does not host any of the retrieved content.