"""
This computer's addresses on its networks -- what Cadets type (or scan) to join a class. Sends nothing anywhere.
"""
from __future__ import annotations

import socket


def lan_addresses() -> list[str]:
    """IPv4 addresses other devices can reach, best guess first."""
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


def class_urls(port: int) -> list[str]:
    return [f"http://{a}" + ("" if port == 80 else f":{port}") + "/" for a in lan_addresses()]
