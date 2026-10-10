"""
Start Vanguard.

    python run.py              open on this device (http://127.0.0.1:8780)
    python run.py --lan        also reachable from other devices on this Wi-Fi/hotspot
    python run.py --no-browser don't open a browser window (kiosk / handheld setups)
"""
import argparse
import sys
import threading
import webbrowser

from vanguard import store
from vanguard.network import lan_addresses
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
    ap.add_argument("--port", type=int, default=8780)   # its own port: never mistaken for another app
    ap.add_argument("--lan", action="store_true", help="listen on all network interfaces")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--kiosk", action="store_true", help="open full-screen with no address bar (handhelds)")
    args = ap.parse_args()

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    url = f"http://127.0.0.1:{args.port}"
    _start_portable_ai()
    httpd = None
    for port in range(args.port, args.port + 10):
        url = f"http://127.0.0.1:{port}"
        try:
            httpd = serve(host, port, lan=args.lan)
            args.port = port
            break
        except OSError:
            # Something already uses the port. The same Vanguard (its icon clicked again, same data): just show it.
            # Another Vanguard with different data (a USB drive while the computer's own copy runs) or another
            # program: never show that one -- try the next port.
            other = _vanguard_instance(url)
            if other is not None and other == store.data_id():
                print(f"Vanguard is already running at {url}")
                if not args.no_browser:
                    webbrowser.open(url)
                return 0
            what = "another Vanguard (different data)" if other is not None else "another program"
            print(f"Port {port} is used by {what} — trying {port + 1}.")
    if httpd is None:
        print(f"Ports {args.port}–{args.port + 9} are all in use. Close another program, or choose one: "
              f"python run.py --port 8800")
        return 1
    stats = httpd.RequestHandlerClass.app.library.stats()
    print(f"Vanguard is running at {url}")
    print(f"  Library: {stats['cards']} study cards, {len(stats['documents'])} documents, "
          f"{stats['quiz_questions']} quiz questions")
    if args.lan:
        addrs = lan_addresses()
        if addrs:
            print("  Cadets: join the same Wi-Fi as this computer, then open in a browser:")
            for a in addrs:
                print(f"      http://{a}" + ("" if args.port == 80 else f":{args.port}"))
        else:
            print("  Other devices on this network can connect to this computer's address, port", args.port)
    print("  Press Ctrl+C to stop (or Me > Quit Vanguard).")
    # Start Classroom opens the Join screen (a big QR code for the projector); the app is one click from it.
    show = url + ("/join" if args.lan else "/")
    if args.kiosk:
        threading.Timer(0.8, lambda: open_kiosk(url)).start()
    elif not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(show)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    return 0


def _start_portable_ai() -> None:
    """USB mode (tools/make_usb.py --with-ai): the drive carries Ollama and a model. If no Ollama is answering yet,
    start the drive's copy with its models folder on the drive. It runs in the same console window, so closing that
    window (or Me > Quit Vanguard) stops it too -- nothing keeps running on the school's computer."""
    import atexit
    import os
    import subprocess
    exe = os.environ.get("VANGUARD_OLLAMA")
    if not exe or not os.path.exists(exe):
        return
    from vanguard import engine
    if engine.local_models() is not None:            # an Ollama is already running on this computer: use it
        return
    env = dict(os.environ, OLLAMA_MODELS=os.path.join(os.path.dirname(exe), "models"), OLLAMA_HOST="127.0.0.1:11434")
    try:
        proc = subprocess.Popen([exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"  Offline AI on this drive couldn't start ({e}). Vanguard works without it.")
        return
    atexit.register(proc.terminate)
    print("  Offline AI: starting from this drive (the first answer can take a minute while the model loads).")


def _vanguard_instance(url: str) -> str | None:
    """The data ID of the Vanguard answering at `url` ("" if it's an older Vanguard without one), or None if what
    answers isn't Vanguard."""
    import json
    import urllib.request
    if not _is_vanguard(url):
        return None
    try:
        with urllib.request.urlopen(url + "/api/lock", timeout=3) as r:
            return str(json.loads(r.read()).get("instance") or "")
    except Exception:
        return ""


def _is_vanguard(url: str) -> bool:
    """Whatever answers at `url` identifies itself as Vanguard (its Server header)."""
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/api/lock", timeout=3) as r:
            return r.headers.get("Server", "").startswith("Vanguard")
    except Exception as e:                          # an HTTP error still carries the header
        headers = getattr(e, "headers", None)
        return bool(headers and headers.get("Server", "").startswith("Vanguard"))


if __name__ == "__main__":
    sys.exit(main())
