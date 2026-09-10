import os
import socket
import sys
import threading
import time

import webview
from backend.api import JSApi

SINGLE_INSTANCE_PORT = 47717


def get_frontend_path():
    if getattr(sys, "_MEIPASS", None):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "frontend", "index.html")


def main():
    if not _acquire_single_instance():
        print("Another instance of Aragoz Lite is already running.")
        return

    api = JSApi()
    frontend = get_frontend_path()

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
            except Exception:
                pass

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
    webview.start(debug=False)


def _acquire_single_instance():
    global _instance_socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        _instance_socket = s
        return True
    except OSError:
        return False


_instance_socket = None

if __name__ == "__main__":
    main()
