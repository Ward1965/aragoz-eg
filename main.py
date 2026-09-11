import atexit
import os
import socket
import sys
import threading

from backend.logging_setup import setup_logging, get_logger

log = get_logger("main")

SINGLE_INSTANCE_PORT = 47717
_instance_socket = None


def get_frontend_path():
    if getattr(sys, "_MEIPASS", None):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "frontend", "index.html")


def _acquire_single_instance():
    global _instance_socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        _instance_socket = s

        def _cleanup_socket():
            global _instance_socket
            try:
                if _instance_socket:
                    _instance_socket.close()
                    _instance_socket = None
            except Exception:
                pass

        atexit.register(_cleanup_socket)
        return True
    except OSError:
        return False


def _build_welcome_html():
    from backend.logo_data import LOGO_MIME, LOGO_B64

    logo_html = (
        f'<img id="welcomeLogo" src="data:{LOGO_MIME};base64,{LOGO_B64}" alt="Aragoz Lite">'
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Aragoz Lite</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; overflow:hidden; background:#1e293b; font-family:'Segoe UI',Tahoma,Arial,sans-serif; }}
  .card {{ position:relative; width:100%; height:100%; margin:0;
           background:#1e293b; border:1px solid #EE88DF; border-radius:18px; padding:32px 36px 76px;
           text-align:center; color:#e2e8f0;
           animation:welcomePop .28s cubic-bezier(.34,1.56,.64,1); user-select:none; }}
  @keyframes welcomePop {{
    from {{ transform:translateY(12px) scale(.97); opacity:0; }}
    to {{ transform:translateY(0) scale(1); opacity:1; }}
  }}
  .hero {{ margin-bottom:20px; }}
  .logo-wrap {{ position:relative; display:inline-block; margin-bottom:12px; }}
  .glow {{ position:absolute; inset:-18px;
           background:radial-gradient(circle, rgba(99,102,241,0.28), transparent 70%);
           border-radius:50%; }}
  #welcomeLogo {{ position:relative; z-index:1; width:88px; height:88px; object-fit:contain; }}
  .title {{ margin:0 0 6px; font-size:24px; font-weight:700; letter-spacing:-0.02em; }}
  .tagline {{ margin:0 auto; max-width:380px; color:#94a3b8; font-size:13px; line-height:1.6; }}
  .features {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:0 0 22px; }}
  .feature {{ display:flex; flex-direction:column; align-items:flex-start; gap:8px;
              padding:14px; text-align:left; background:#334155; border:1px solid #475569;
              border-radius:12px; transition:transform .15s ease, border-color .15s ease; }}
  .feature:hover {{ transform:translateY(-2px); border-color:#6366f1; }}
  .ficon {{ display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px;
            border-radius:10px; background:var(--fc); color:#fff; }}
  .ficon svg {{ width:18px; height:18px; }}
  .feature h4 {{ margin:0; font-size:13px; font-weight:600; }}
  .feature p {{ margin:0; font-size:11.5px; line-height:1.5; color:#94a3b8; }}
  .meta {{ display:flex; align-items:center; justify-content:center; gap:10px; margin-bottom:18px; }}
  .info {{ display:inline-flex; align-items:center; gap:6px; padding:5px 12px; background:#334155;
           border:1px solid #475569; border-radius:999px; font-size:12px; }}
  .info img {{ width:18px; height:13px; border-radius:2px; }}
  .ver {{ display:inline-block; padding:5px 12px; background:rgba(245,158,11,0.12); color:#f59e0b;
          border:1px solid rgba(245,158,11,0.3); border-radius:999px; font-size:11px; font-weight:700; }}
  .cta {{ width:100%; padding:12px 24px; font-size:14px; font-weight:600; border-radius:10px;
          border:none; background:#6366f1; color:#fff; cursor:pointer; }}
  .cta:hover {{ background:#818cf8; }}
</style>
</head>
<body>
  <div class="card">
      <div class="hero">
        <div class="logo-wrap"><span class="glow"></span>{logo_html}</div>
        <h2 class="title">Aragoz Lite</h2>
        <p class="tagline">Manage your proxy configs — fetch subscriptions, scan the web, or import your own, all in one place.</p>
      </div>
      <div class="features">
        <div class="feature">
          <span class="ficon" style="--fc:#6366f1">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A3.5 3.5 0 0 1 17 18z"/><path d="M10 14l2 2 2-2M12 11v5"/></svg>
          </span>
          <div>
            <h4>Fetch</h4>
            <p>Load configs from direct subscription links or folders.</p>
          </div>
        </div>
        <div class="feature">
          <span class="ficon" style="--fc:#8b5cf6">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.7 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.7-3.8-9S9.5 5.6 12 3z"/></svg>
          </span>
          <div>
            <h4>Scan Web</h4>
            <p>Auto-discover new sources straight from the web.</p>
          </div>
        </div>
        <div class="feature">
          <span class="ficon" style="--fc:#10b981">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          </span>
          <div>
            <h4>Import &amp; Export</h4>
            <p>Import files or raw text, and copy results as text or Base64.</p>
          </div>
        </div>
      </div>
      <div class="meta">
        <span class="info"><img src="https://flagcdn.com/w40/eg.png" alt="EG"> Egypt - Port Said</span>
        <span class="ver">v1.3</span>
      </div>
      <button class="cta" onclick="pywebview.api.start_app()">Get Started</button>
    </div>
</body>
</html>"""


def _round_welcome_window_on_windows(uid):
    def worker():
        try:
            import webview.platforms.winforms as wf
        except Exception:
            return

        import time

        deadline = time.time() + 20
        form = None
        while time.time() < deadline:
            try:
                form = wf.BrowserView.instances.get(uid)
                if form is not None and form.IsHandleCreated:
                    break
            except Exception:
                pass
            time.sleep(0.05)
        if form is None:
            return

        try:
            import ctypes
            from ctypes import wintypes as wt

            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32
            gdi32.CreateRoundRectRgn.restype = wt.HRGN
            w = form.ClientSize.Width
            h = form.ClientSize.Height
            r = 18
            hrgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
            if hrgn:
                user32.SetWindowRgn(int(form.Handle), int(hrgn), True)
        except Exception as exc:
            log.debug("Rounding welcome window failed: %s", exc)

    threading.Thread(target=worker, daemon=True).start()


def main():
    setup_logging()

    if not _acquire_single_instance():
        log.warning("Another instance of Aragoz Lite is already running (port %d busy)", SINGLE_INSTANCE_PORT)
        return

    log.info("Starting Aragoz Lite - Proxy Config Manager")

    import webview
    from backend.api import JSApi

    api = JSApi()
    frontend = get_frontend_path()
    log.info("Loading frontend from %s", frontend)

    main_window = webview.create_window(
        title="Aragoz Lite - Proxy Config Manager",
        url=frontend,
        js_api=api,
        width=1280,
        height=820,
        min_size=(900, 600),
        hidden=True,
        maximized=True,
        text_select=True,
        background_color="#0f172a",
    )
    welcome_window = webview.create_window(
        title="Aragoz Lite",
        html=_build_welcome_html(),
        js_api=api,
        width=566,
        height=576,
        frameless=True,
        easy_drag=True,
        resizable=False,
        shadow=False,
    )
    api._main_window = main_window
    api._welcome_window = welcome_window
    api._window = main_window

    def _welcome_closed():
        try:
            main_window.show()
            main_window.maximize()
        except Exception as e:
            log.debug("Fallback maximize failed: %s", e)

    welcome_window.events.closed += _welcome_closed

    _round_welcome_window_on_windows(welcome_window.uid)

    log.info("Application windows created, starting event loop")
    webview.start(debug=False)
    log.info("Application exited")


if __name__ == "__main__":
    main()
