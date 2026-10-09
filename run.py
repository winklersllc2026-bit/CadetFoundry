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
    try:
        httpd = serve(host, args.port, lan=args.lan)
    except OSError:
        # Something already uses the port. If it's Vanguard (the icon was clicked again), just show it -- but never
        # open some other program that happens to use the same port.
        if not _is_vanguard(url):
            print(f"Port {args.port} is used by another program, so Vanguard can't start there.")
            print(f"Close that program, or start Vanguard on another port:  python run.py --port {args.port + 1}")
            return 1
        print(f"Vanguard is already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    stats = httpd.RequestHandlerClass.app.library.stats()
    print(f"Vanguard is running at {url}")
    print(f"  Library: {stats['cards']} study cards, {len(stats['documents'])} documents, "
          f"{stats['quiz_questions']} quiz questions")
    if args.lan:
        addrs = _lan_addresses()
        if addrs:
            print("  Cadets: join the same Wi-Fi as this computer, then open in a browser:")
            for a in addrs:
                print(f"      http://{a}" + ("" if args.port == 80 else f":{args.port}"))
        else:
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


def _lan_addresses() -> list[str]:
    """This computer's addresses on its networks (what Cadets type), best guess first. Sends nothing anywhere."""
    import socket
    found: list[str] = []
    try:                                             # the address the default route would use (UDP connect sends nothing)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    return [a for a in dict.fromkeys(found) if not a.startswith(("127.", "169.254.", "0."))]


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
