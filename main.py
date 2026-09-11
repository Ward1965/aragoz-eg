import atexit
import os
import socket
import sys
import threading
import time

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

    window = webview.create_window(
        title="Aragoz Lite - Proxy Config Manager",
        url=frontend,
        js_api=api,
        width=1280,
        height=820,
        min_size=(900, 600),
        maximized=True,
        text_select=True,
    )
    api._window = window

    def _maximize_on_thread():
        def _maximize():
            try:
                window.maximize()
            except Exception as e:
                log.debug("Maximize attempt failed: %s", e)

        threading.Thread(target=_maximize, daemon=True).start()

    def _keep_maximized_watchdog():
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            try:
                window.maximize()
            except Exception:
                pass
            time.sleep(0.5)

    window.events.loaded += _maximize_on_thread
    window.events.shown += _maximize_on_thread
    threading.Thread(target=_keep_maximized_watchdog, daemon=True).start()

    log.info("Application window created, starting event loop")
    webview.start(debug=False)
    log.info("Application exited")


if __name__ == "__main__":
    main()
