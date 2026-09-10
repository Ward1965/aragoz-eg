# Aragoz Lite

> A lightweight, multi-platform desktop proxy config manager — fetch, parse, manage and export proxy/VPN configs from GitHub repos, Telegram channels, and subscription links.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.9+-yellow)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.0-orange)

---

## Features

### Multi-Source Config Discovery
- **GitHub Crawling** — Automatically discovers repos containing proxy configs via GitHub API search, without re-fetching known sources.
- **Telegram Channels** — Fetches shared config links from 69+ public Telegram channels (2-phase fetching: channels → message links).
- **Subscription Links** — Supports any raw URL: base64-encoded subscription lists, plain text config lists, Clash YAML, sing-box JSON.
- **Dead Link Filtering** — Automatically detects and remembers permanent errors (403, 404, SSL failures, DNS failures) to skip broken sources.

### 17 Protocol Parsers
| Protocol | URI Scheme | Format |
|---|---|---|
| VLESS | `vless://` | URI + query params |
| VMess | `vmess://` | Base64 JSON |
| Trojan | `trojan://` | URI + query params |
| Shadowsocks | `ss://` | Base64 + URI |
| Hysteria2 | `hy2://` | URI + query params |
| Hysteria | `hysteria://` | URI + query params |
| TUIC | `tuic://` | URI + query params |
| WireGuard | `wg://` | URI / wg-quick config |
| SSR | `ssr://` | Base64 URI |
| NaiveProxy | `naive://` | URI + query params |
| SOCKS4/4a | `socks4://` | URI |
| SOCKS5 | `socks5://` | URI |
| HTTP Proxy | `http://` | URI with auth |
| HTTPS Proxy | `https://` | URI with auth |
| Clash YAML | — | YAML block list |
| sing-box JSON | — | JSON proxy groups |
| WireGuard URI | `wg://` | Base64 JSON |

### Smart Parsing & Dedup
- Automatic protocol detection from URI scheme or text structure.
- Config deduplication (exact + normalized).
- Country detection via GeoLite2 database (offline, bundled).
- Expiry date parsing with remaining-days calculation.

### Beautiful Dark UI
- Modern dark theme with glassmorphism effects.
- Animated welcome screen with logo, description and Get Started.
- Responsive sidebar with protocol badges and count.
- Country flags (via flagcdn) for each config.
- Sortable columns (Name, Protocol, Server, Port, Country).
- Live text search with instant filtering.
- Config detail modal showing all extracted fields.
- QR code generation for any config.
- Copy to clipboard with one click.

### Multi-Format Export
- **Copy URL** — Single config URI to clipboard.
- **Copy All** — All configs as newline-separated URIs.
- **Base64 Export** — Subscription-ready base64-encoded string.
- **Clash YAML** — Ready-to-use Clash/V2RayN subscription format.
- **JSON Export** — Full config objects with all metadata.

### Country Intelligence
- Offline GeoIP lookup (GeoLite2, ~6MB bundled).
- Country filter sidebar with count per country.
- Country badge with flag icon in table rows.

---

## Architecture

```
aragoz-lite/
├── main.py                    # Entry point — pywebview window + single instance lock
├── backend/
│   ├── api.py                 # JS API bridge (JSApi class) — all exposed methods
│   ├── fetcher.py             # Async HTTP fetcher (aiohttp)
│   ├── parsers.py             # 17+ protocol parsers + Clash/sing-box
│   ├── scraper.py             # GitHub + Telegram source discovery
│   ├── storage.py             # SQLite storage, export, dead link tracking
│   └── logo_data.py           # Embedded app logo (base64)
├── frontend/
│   ├── index.html             # Main UI structure
│   ├── style.css              # Dark theme + glassmorphism design
│   └── app.js                 # Frontend logic, table, filters, modals
├── requirements.txt           # Python dependencies
├── aragoz.ico                 # Windows icon
├── aragoz.icns                # macOS icon
├── build_mac.sh               # macOS build script (Intel/ARM/Universal)
├── build_linux.sh             # Linux build script (GTK/WebKit2GTK)
└── .github/
    └── workflows/
        └── build-mac.yml      # GitHub Actions: auto-build macOS on push
```

### Tech Stack
- **Backend:** Python 3.9+, aiohttp (async HTTP), SQLite, GeoLite2
- **Frontend:** Vanilla HTML/CSS/JS — no frameworks, no build tools
- **Desktop:** pywebview (lightweight native window, no Electron)
- **Build:** PyInstaller (single .exe / .app / binary)

---

## Installation

### Prerequisites
- Python 3.9 or later
- pip

### Quick Start
```bash
# Clone the repository
git clone https://github.com/Ward1965/aragoz.git
cd aragoz

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Build Executable

**Windows:**
```bash
pyinstaller --noconfirm --onefile --windowed \
  --name "Aragoz Lite" \
  --icon aragoz.ico \
  --add-data "frontend;frontend" \
  --collect-all webview --collect-all aiohttp \
  --hidden-import clr --hidden-import webview.platforms.winforms \
  main.py
```
Output: `dist/Aragoz Lite.exe`

**macOS (on a Mac):**
```bash
bash build_mac.sh universal2   # or: x86_64 | arm64
```
Output: `dist/Aragoz Lite.app`

**Linux (on Linux with GTK + WebKit2GTK):**
```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt install libgtk-3-0t64 libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1 gir1.2-gtk-3.0

bash build_linux.sh
```
Output: `dist/Aragoz Lite`

### Automated macOS Build (GitHub Actions)
Push to `main` or trigger manually:
- Actions → Build macOS → Run workflow
- Builds both Intel (`macos-13`) and Apple Silicon (`macos-14`)
- Download `.zip` artifacts from the run summary

---

## Usage

1. Launch the app — the welcome screen appears on first run.
2. Click **Get Started** to enter the main interface.
3. **Add sources:** Paste raw URLs or subscription links in the Sources box, one per line.
4. Click **Fetch Configs** — the app crawls all sources asynchronously.
5. Browse, search, filter and sort configs in the table.
6. **Copy** individual configs, **view details**, or **generate QR codes**.
7. Use **Export** buttons to copy all or export as Base64 / Clash YAML / JSON.

### Supported Source Types
| Type | Example |
|---|---|
| Raw GitHub file | `https://raw.githubusercontent.com/user/repo/main/configs.txt` |
| Subscription URL | Any base64-encoded subscription link |
| Telegram channel | Auto-discovered via search (69+ channels indexed) |
| Clash YAML | Single `.yaml` files with proxy lists |
| sing-box JSON | JSON with `outbounds` array |
| Plain text | Any file with one config URI per line |

---

## Dead Link Detection

The app automatically tracks permanently broken sources:
- HTTP 400/401/403/404/405/410/413/414/415/451 errors
- DNS resolution failures
- SSL certificate errors
- Connection refused / host unreachable

Dead links are stored in `dead_links.json` (max 10,000 entries) and skipped on subsequent fetches, dramatically reducing scan time.

---

## Telegram Support

Aragoz Lite can crawl public Telegram channels for shared proxy configs:
- Searches Telegram via `t.me` web endpoints (no API key needed).
- 2-phase architecture: discover channels → extract message links → parse configs.
- Configurable concurrency: 14 channels simultaneously, 20 links simultaneously.
- Timeout protection per request (10s per link, 20s per channel).

---

## Export Formats

| Format | Use Case |
|---|---|
| Copy URL | Quick paste into any client |
| Copy All | Batch import to clipboard |
| Base64 Subscription | Import to V2RayN, NekoBox, etc. |
| Clash YAML | Import to Clash, Clash Meta, mihomo |
| JSON | Programmatic use, custom tools |

---

## Platform Notes

| Platform | Status | Notes |
|---|---|---|
| Windows | Native build | Single .exe via PyInstaller |
| macOS (Apple Silicon) | Native build | `.app` bundle, ad-hoc signed |
| macOS (Intel) | Supported | Build via `build_mac.sh x86_64` |
| Linux | Supported | Requires GTK3 + WebKit2GTK |

> **Note:** macOS and Linux builds must be created on their respective platforms — PyInstaller does not support cross-compilation.

---

## License

MIT

---

## Acknowledgements

- [pywebview](https://pywebview.flowrl.com/) — Lightweight desktop webview
- [aiohttp](https://docs.aiohttp.org/) — Async HTTP client
- [GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) — Country database
- [flagcdn](https://flagcdn.com/) — Country flag images
