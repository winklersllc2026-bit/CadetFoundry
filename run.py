"""
Start Cadet Foundry.

    python run.py              open on this device (http://127.0.0.1:8780)
    python run.py --lan        also reachable from other devices on this Wi-Fi/hotspot
    python run.py --no-browser don't open a browser window (kiosk / handheld setups)
"""
import argparse
import os
import sys
import threading
import webbrowser

from cadetfoundry import sample, store
from cadetfoundry.network import lan_addresses
from cadetfoundry.server import reopen, serve


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
    in the data folder."""
    from cadetfoundry import store
    store.DATA.mkdir(parents=True, exist_ok=True)
    log = store.DATA / "cadetfoundry.log"
    if log.exists() and log.stat().st_size > 1_000_000:
        log.replace(log.with_suffix(".log.old"))
    sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)


def write_pid() -> None:
    """The running server's process id, next to the log, so the installer can close Cadet Foundry before an update.
    Written only once this process really serves -- a second click that just shows the running Cadet Foundry must never
    overwrite (and then delete) the running one's id, or an update can't close it."""
    import atexit
    import os
    from cadetfoundry import store
    pid = store.DATA / "cadetfoundry.pid"
    pid.write_text(str(os.getpid()), encoding="ascii")
    mine = str(os.getpid())
    atexit.register(lambda: pid.read_text(encoding="ascii").strip() == mine and pid.unlink(missing_ok=True)
                    if pid.exists() else None)


def _print_join_qr(address: str) -> None:
    """The Join address as a QR code in this window, for phones to scan (the projector's Join screen shows a bigger
    one). With exactly one class set up, its join code is built in, so a Cadet who scans lands in that class."""
    from cadetfoundry import instructor, qr
    codes = instructor.join_codes()
    target = address
    if len(codes) == 1:
        code, unit = next(iter(codes.items()))
        target = f"{address}?join={code}"
    try:
        print()
        print(qr.terminal(target))
        if len(codes) == 1:
            print(f"  Scan to join {unit['name']} (join code {code}).")
        else:
            print("  Scan to join." + (" Cadets type their class's join code when they sign up." if codes else ""))
        print()
    except UnicodeEncodeError:                      # a console that can't draw block characters: the address is enough
        pass


def main() -> int:
    if sys.stdout is None:
        quiet_start()
    else:                                           # a Windows console can't print every character; never crash on it
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Cadet Foundry")
    ap.add_argument("--port", type=int, default=8780)   # its own port: never mistaken for another app
    ap.add_argument("--lan", action="store_true", help="listen on all network interfaces")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--kiosk", action="store_true", help="open full-screen with no address bar (handhelds)")
    args = ap.parse_args()

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    url = f"http://127.0.0.1:{args.port}"
    if not sample.ACTIVE:                          # the sample class never starts the AI or anything else
        _start_portable_ai()
    httpd = None
    for port in range(args.port, args.port + 10):
        url = f"http://127.0.0.1:{port}"
        try:
            httpd = serve(host, port, lan=args.lan)
            args.port = port
            break
        except OSError:
            # Something already uses the port. The same Cadet Foundry (its icon clicked again, same data): just show it.
            # Another Cadet Foundry with different data (a USB drive while the computer's own copy runs) or another
            # program: never show that one -- try the next port.
            other = _instance_data_id(url)
            if other is not None and other == store.data_id():
                if _serves_pages(url):
                    print(f"Cadet Foundry is already running at {url}")
                    if not args.no_browser:
                        webbrowser.open(url)
                    return 0
                # Same data folder, but it can't show its pages: a leftover copy whose program files were removed
                # (an uninstall while it ran). Close it and take its place -- otherwise every click would open a
                # "Not Found" page forever.
                print(f"A Cadet Foundry at {url} isn't working (its pages are missing) — closing it.")
                if _close_broken(url, port):
                    try:
                        httpd = serve(host, port, lan=args.lan)
                        args.port = port
                        break
                    except OSError:
                        pass
                print(f"  Couldn't close it — using port {port + 1} instead.")
                continue
            what = "another Cadet Foundry (different data)" if other is not None else "another program"
            print(f"Port {port} is used by {what} — trying {port + 1}.")
    if httpd is None:
        print(f"Ports {args.port}–{args.port + 9} are all in use. Close another program, or choose one: "
              f"python run.py --port 8800")
        return 1
    if sample.ACTIVE:                               # a separate copy with made-up Cadets (cadetfoundry/sample.py)
        threading.Thread(target=sample.build, args=(args.port, httpd.RequestHandlerClass.app), daemon=True).start()
        sample.watch_idle(httpd)
    if sys.stdout is not None and getattr(sys.stdout, "name", "").endswith("cadetfoundry.log"):
        write_pid()                                 # the icon's quiet Cadet Foundry: the installer closes it by this id
    stats = httpd.RequestHandlerClass.app.library.stats()
    print(f"Cadet Foundry is running at {url}")
    print(f"  Library: {stats['cards']} study cards, {len(stats['documents'])} documents, "
          f"{stats['quiz_questions']} quiz questions")
    _print_mode(args.lan, args.port)
    print("  Press Ctrl+C to stop (or Me > Quit Cadet Foundry).")
    # Started with --lan (the classroom), it opens the Join screen (a big QR code for the projector).
    show = url + ("/join" if args.lan else "/")
    if args.kiosk:
        threading.Timer(0.8, lambda: open_kiosk(url)).start()
    elif not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(show)).start()
    current = {"httpd": httpd}                      # turning phones on/off restarts the server: Quit stops the current one
    icon = _tray(url, current, quiet=args.no_browser)
    while True:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            break
        httpd.server_close()
        want = getattr(httpd, "switch_lan", None)   # the instructor's "Open class to phones" (or close it)
        if want is None:                            # Quit Cadet Foundry
            break
        try:
            httpd = reopen(args.port, want)
            current["httpd"] = httpd
            args.lan = want
        except OSError:
            print("  Couldn't switch class mode — the port didn't free up. Staying as before.")
            try:
                httpd = reopen(args.port, args.lan)
            except OSError:
                print(f"  Port {args.port} isn't available any more. Start Cadet Foundry again.")
                return 1
        print()
        print("Class is now " + ("OPEN to phones on this Wi-Fi." if args.lan else "on this computer only."))
        _print_mode(args.lan, args.port)
    httpd.server_close()
    if icon:
        icon.stop()                                 # the taskbar icon goes with it
    sample.stop_child()                             # a sample class this Cadet Foundry opened closes with it
    return 0


def _tray(url: str, current: dict, quiet: bool = False):
    """The taskbar icon while Cadet Foundry runs (Windows): hover says it's running and where it saves; click opens it;
    right-click has Open and Quit. Not for --no-browser (kiosks, demo boxes, tests) or the sample class."""
    if sys.platform != "win32" or quiet or sample.ACTIVE or os.environ.get("CADETFOUNDRY_NO_TRAY"):
        return None
    from cadetfoundry import tray, usb_home
    home = usb_home.home()
    where = f"USB drive {home['drive']}" if home["where"] == "usb" else "this computer"
    marker = store.DATA / "tray_hint_shown"
    hint = "" if marker.exists() else "It runs in the background. Click this icon to open it; right-click it to quit."

    def quit_now():
        threading.Thread(target=current["httpd"].shutdown, daemon=True).start()

    tip = "Cadet Foundry is running" + chr(10) + f"Saved on {where}"
    icon = tray.Tray(lambda: webbrowser.open(url), quit_now, tip, hint)
    if icon.start() and hint:
        try:
            marker.write_text("1", encoding="ascii")
        except OSError:
            pass
    return icon


def _print_mode(lan: bool, port: int) -> None:
    """In classroom mode: the addresses Cadets type and a QR code to scan."""
    if not lan:
        return
    addrs = lan_addresses()
    if addrs:
        print("  Cadets: join the same Wi-Fi as this computer, then open in a browser:")
        for a in addrs:
            print(f"      http://{a}" + ("" if port == 80 else f":{port}"))
        _print_join_qr(f"http://{addrs[0]}" + ("" if port == 80 else f":{port}") + "/")
    else:
        print("  Other devices on this network can connect to this computer's address, port", port)


def _start_portable_ai() -> None:
    """USB mode (tools/make_usb.py --with-ai): the drive carries Ollama and a model. If no Ollama is answering yet,
    start the drive's copy with its models folder on the drive. It runs in the same console window, so closing that
    window (or Me > Quit Cadet Foundry) stops it too -- nothing keeps running on the school's computer."""
    import atexit
    import os
    import subprocess
    exe = os.environ.get("CADETFOUNDRY_OLLAMA")
    if not exe or not os.path.exists(exe):
        return
    from cadetfoundry import engine
    if engine.local_models() is not None:            # an Ollama is already running on this computer: use it
        return
    env = dict(os.environ, OLLAMA_MODELS=os.path.join(os.path.dirname(exe), "models"), OLLAMA_HOST="127.0.0.1:11434")
    try:
        proc = subprocess.Popen([exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"  Offline AI on this drive couldn't start ({e}). Cadet Foundry works without it.")
        return
    atexit.register(proc.terminate)
    print("  Offline AI: starting from this drive (the first answer can take a minute while the model loads).")


def _instance_data_id(url: str) -> str | None:
    """The data ID of the Cadet Foundry answering at `url` ("" if it's an older Cadet Foundry without one), or None if what
    answers isn't Cadet Foundry."""
    import json
    import urllib.request
    if not _is_cadet_foundry(url):
        return None
    try:
        with urllib.request.urlopen(url + "/api/lock", timeout=3) as r:
            return str(json.loads(r.read()).get("instance") or "")
    except Exception:
        return ""


def _serves_pages(url: str) -> bool:
    """The Cadet Foundry at `url` can show its app page (a leftover whose program files were deleted can't)."""
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/", timeout=5) as r:
            return r.status == 200 and b"<html" in r.read(4096).lower()
    except Exception:
        return False


def _close_broken(url: str, port: int) -> bool:
    """Close a broken Cadet Foundry that uses our data folder. First politely (/api/quit answers this computer); for an
    older version, end the process that owns the port -- only after checking it's Cadet Foundry with our data folder."""
    import json
    import time
    import urllib.request
    try:
        req = urllib.request.Request(url + "/api/quit", data=b"{}", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass
    for _ in range(10):
        time.sleep(0.5)
        if _instance_data_id(url) is None:
            return True
    if sys.platform != "win32":
        return False
    import subprocess
    try:                                             # who owns the port (Windows has no lsof)
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    pids = {line.split()[-1] for line in out.splitlines()
            if "LISTENING" in line and line.split()[1:2] and line.split()[1].endswith(f":{port}")}
    for pid in pids:
        if pid.isdigit() and int(pid) != os.getpid():
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=10)
    for _ in range(10):
        time.sleep(0.5)
        if _instance_data_id(url) is None:
            return True
    return False


def _is_cadet_foundry(url: str) -> bool:
    """Whatever answers at `url` identifies itself as Cadet Foundry (its Server header)."""
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/api/lock", timeout=3) as r:
            return r.headers.get("Server", "").startswith("CadetFoundry")
    except Exception as e:                          # an HTTP error still carries the header
        headers = getattr(e, "headers", None)
        return bool(headers and headers.get("Server", "").startswith("CadetFoundry"))


if __name__ == "__main__":
    sys.exit(main())
