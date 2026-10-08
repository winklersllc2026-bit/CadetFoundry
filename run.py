"""
Start Vanguard.

    python run.py              open on this device (http://127.0.0.1:8765)
    python run.py --lan        also reachable from other devices on this Wi-Fi/hotspot
    python run.py --no-browser don't open a browser window (kiosk / handheld setups)
"""
import argparse
import sys
import threading
import webbrowser

from vanguard.server import serve


def open_kiosk(url: str) -> None:
    """Full-screen, no address bar or tabs: Edge or Chrome/Chromium in kiosk mode; plain browser otherwise."""
    import os
    import shutil
    import subprocess
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chromium-browser"), shutil.which("chromium"), shutil.which("google-chrome"),
    ]
    for exe in candidates:
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, "--kiosk", url, "--edge-kiosk-type=fullscreen", "--no-first-run",
                              "--disable-features=Translate"])
            return
    webbrowser.open(url)


def quiet_start() -> None:
    """Started with pythonw.exe (the Windows installer's icon): there's no console, so output goes to a log file
    in the data folder, and the process id is written next to it so the installer can close Vanguard on update."""
    import atexit
    import os
    from vanguard import store
    store.DATA.mkdir(parents=True, exist_ok=True)
    log = store.DATA / "vanguard.log"
    if log.exists() and log.stat().st_size > 1_000_000:
        log.replace(log.with_suffix(".log.old"))
    sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
    pid = store.DATA / "vanguard.pid"
    pid.write_text(str(os.getpid()), encoding="ascii")
    atexit.register(lambda: pid.unlink(missing_ok=True))


def main() -> int:
    if sys.stdout is None:
        quiet_start()
    else:                                           # a Windows console can't print every character; never crash on it
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Vanguard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--lan", action="store_true", help="listen on all network interfaces")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--kiosk", action="store_true", help="open full-screen with no address bar (handhelds)")
    args = ap.parse_args()

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    url = f"http://127.0.0.1:{args.port}"
    try:
        httpd = serve(host, args.port, lan=args.lan)
    except OSError:                                 # already running (the icon was clicked again): just show it
        print(f"Vanguard is already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    stats = httpd.RequestHandlerClass.app.library.stats()
    print(f"Vanguard is running at {url}")
    print(f"  Library: {stats['cards']} study cards, {len(stats['documents'])} documents, "
          f"{stats['quiz_questions']} quiz questions")
    if args.lan:
        print("  Other devices on this network can connect to this computer's address, port", args.port)
    print("  Press Ctrl+C to stop (or Me > Quit Vanguard).")
    if args.kiosk:
        threading.Timer(0.8, lambda: open_kiosk(url)).start()
    elif not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
