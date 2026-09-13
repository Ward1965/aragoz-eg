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
    base, html = None, None
    if getattr(sys, "_MEIPASS", None):
        base = sys._MEIPASS
    cand = []
    if base:
        cand.append(os.path.join(base, "frontend", "index.html"))
    cand.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "frontend", "index.html"))
    cand.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "index.html"))
    for c in cand:
        if c and os.path.isfile(c):
            html = c
            break
    if html is None:
        html = cand[-1]
    return html


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

    def _excepthook(tp, val, tb):
        import traceback
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "logs", "exe_crash.txt"), "a") as f:
                traceback.print_exception(tp, val, tb, file=f)
        except Exception:
            pass

    sys.excepthook = _excepthook

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
    api._main_window = main_window
    api._window = main_window
    log.debug("windows created")

    def _close_boot_splash():
        try:
            import pyi_splash
            pyi_splash.close()
        except Exception:
            pass

    def _show_main():
        try:
            main_window.show()
            main_window.maximize()
        except Exception as e:
            log.debug("Main window show failed: %s", e)

    def _main_loaded():
        _close_boot_splash()
        _show_main()

    main_window.events.loaded += _main_loaded

    log.info("Application windows created, starting event loop")
    webview.start(debug=False)
    log.info("Application exited")


if __name__ == "__main__":
    main()