"""
A small QR code maker (the same one as web/js/qr.js, in Python) -- no library, works offline. run.py uses it to
print the class Join address as a QR code in the Start Classroom window, so Cadets can scan the console too.
Byte mode, error correction level M, versions 1-10. ISO/IEC 18004: Reed-Solomon over GF(256), interleaved blocks,
all 8 masks scored, the lowest penalty kept.
"""
from __future__ import annotations

# [total codewords, EC codewords per block, (blocks, data codewords)...] for level M
_M = [None,
      (26, 10, (1, 16)), (44, 16, (1, 28)), (70, 26, (1, 44)), (100, 18, (2, 32)), (134, 24, (2, 43)),
      (172, 16, (4, 27)), (196, 18, (4, 31)), (242, 22, (2, 38), (2, 39)), (292, 22, (3, 36), (2, 37)),
      (346, 26, (4, 43), (1, 44))]
_ALIGN = [None, [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]]
_REMAINDER = [0, 0, 7, 7, 7, 7, 7, 0, 0, 0, 0]


def _mul(x: int, y: int) -> int:                  # GF(256) with x^8 + x^4 + x^3 + x^2 + 1
    z = 0
    for i in range(7, -1, -1):
        z = ((z << 1) ^ ((z >> 7) * 0x11D)) & 0x1FF
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(n: int) -> list[int]:
    r = [0] * n
    r[-1] = 1
    root = 1
    for _ in range(n):
        for j in range(n):
            r[j] = _mul(r[j], root)
            if j + 1 < n:
                r[j] ^= r[j + 1]
        root = _mul(root, 2)
    return r


def _rs_remainder(data: list[int], div: list[int]) -> list[int]:
    r = [0] * len(div)
    for b in data:
        f = b ^ r.pop(0)
        r.append(0)
        for i, d in enumerate(div):
            r[i] ^= _mul(d, f)
    return r


def _codewords(data_bytes: bytes, ver: int) -> list[int]:
    total, ec_len, *groups = _M[ver]
    data_len = sum(n * k for n, k in groups)
    bits: list[int] = []

    def put(v: int, n: int) -> None:
        bits.extend((v >> i) & 1 for i in range(n - 1, -1, -1))
    put(4, 4)
    put(len(data_bytes), 8 if ver < 10 else 16)
    for b in data_bytes:
        put(b, 8)
    put(0, min(4, data_len * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    pad = 0xEC
    while len(bits) < data_len * 8:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    blocks, ecs, div, at = [], [], _rs_divisor(ec_len), 0
    for n, k in groups:
        for _ in range(n):
            blk = data[at:at + k]
            at += k
            blocks.append(blk)
            ecs.append(_rs_remainder(blk, div))
    out = []
    for i in range(max(len(b) for b in blocks)):
        out.extend(b[i] for b in blocks if i < len(b))
    for i in range(ec_len):
        out.extend(e[i] for e in ecs)
    if len(out) != total:
        raise ValueError("QR: codeword count")
    return out


_MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
          lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
          lambda x, y: (x * y) % 2 + (x * y) % 3 == 0, lambda x, y: ((x * y) % 2 + (x * y) % 3) % 2 == 0,
          lambda x, y: ((x + y) % 2 + (x * y) % 3) % 2 == 0]


def make(text: str) -> list[list[bool]]:
    """The QR code as rows of modules (True = dark), without the quiet zone."""
    data_bytes = text.encode("utf-8")
    ver = 1
    while ver <= 10:
        cap = sum(n * k for n, k in _M[ver][2:]) - (2 if ver < 10 else 3)
        if len(data_bytes) <= cap:
            break
        ver += 1
    if ver > 10:
        raise ValueError("Too long for a QR code")
    size = ver * 4 + 17
    mod = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def setm(x: int, y: int, dark: bool) -> None:
        mod[y][x] = dark
        fn[y][x] = True

    for i in range(size):                                         # timing
        setm(6, i, i % 2 == 0)
        setm(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):          # finders + separators
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y, d = cx + dx, cy + dy, max(abs(dx), abs(dy))
                if 0 <= x < size and 0 <= y < size:
                    setm(x, y, d not in (2, 4))
    al = _ALIGN[ver]
    last = len(al) - 1
    for i, ay in enumerate(al):
        for j, ax in enumerate(al):
            if (i, j) in ((0, 0), (0, last), (last, 0)):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setm(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask: int) -> None:
        data = (0 << 3) | mask                                    # level M = 00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        fbits = ((data << 10) | rem) ^ 0x5412

        def bit(i: int) -> bool:
            return (fbits >> i) & 1 == 1
        for i in range(6):
            setm(8, i, bit(i))
        setm(8, 7, bit(6))
        setm(8, 8, bit(7))
        setm(7, 8, bit(8))
        for i in range(9, 15):
            setm(14 - i, 8, bit(i))
        for i in range(8):
            setm(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            setm(8, size - 15 + i, bit(i))
        setm(8, size - 8, True)                                   # the dark module

    draw_format(0)                                                # reserves the format areas
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        vbits = (ver << 12) | rem
        for i in range(18):
            b = (vbits >> i) & 1 == 1
            a, c = size - 11 + (i % 3), i // 3
            setm(a, c, b)
            setm(c, a, b)
    data = _codewords(data_bytes, ver)
    i = 0
    nbits = len(data) * 8 + _REMAINDER[ver]
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                up = ((right + 1) & 2) == 0
                y = size - 1 - vert if up else vert
                if not fn[y][x] and i < nbits:
                    mod[y][x] = i < len(data) * 8 and ((data[i >> 3] >> (7 - (i & 7))) & 1) == 1
                    i += 1
        right -= 2

    def apply_mask(m: int) -> None:
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and _MASKS[m](x, y):
                    mod[y][x] = not mod[y][x]

    def penalty() -> int:
        p = 0

        def line(cells: list[bool]) -> None:
            nonlocal p
            run = 1
            for k in range(1, size + 1):
                if k < size and cells[k] == cells[k - 1]:
                    run += 1
                else:
                    if run >= 5:
                        p += run - 2
                    run = 1
            s = "".join("1" if c else "0" for c in cells)
            for pat in ("10111010000", "00001011101"):
                k = s.find(pat)
                while k >= 0:
                    p += 40
                    k = s.find(pat, k + 1)
        for k in range(size):
            line(mod[k])
            line([mod[y][k] for y in range(size)])
        for y in range(size - 1):
            for x in range(size - 1):
                c = mod[y][x]
                if c == mod[y][x + 1] == mod[y + 1][x] == mod[y + 1][x + 1]:
                    p += 3
        dark = sum(c for row in mod for c in row)
        return p + 10 * int(abs(dark * 20 / (size * size) - 10))

    best, best_score = 0, None
    for m in range(8):
        apply_mask(m)
        draw_format(m)
        s = penalty()
        if best_score is None or s < best_score:
            best, best_score = m, s
        apply_mask(m)                                             # undo (XOR)
    apply_mask(best)
    draw_format(best)
    return mod


def terminal(text: str) -> str:
    """The QR code for a console window: two rows of modules per line using half-block characters, light on dark
    reversed so phones read it on a black console (dark modules print as spaces, light ones as blocks), with the
    4-module quiet zone."""
    m = make(text)
    n = len(m) + 8
    grid = [[False] * n for _ in range(4)] + [[False] * 4 + row + [False] * 4 for row in m] + [[False] * n for _ in range(5)]
    lines = []
    for y in range(0, n, 2):
        top, bottom = grid[y], grid[y + 1]
        # a light module is drawn (the console background is dark); upper half, lower half, full, or none
        lines.append("".join({(False, False): "█", (False, True): "▀", (True, False): "▄", (True, True): " "}
                             [(top[x], bottom[x])] for x in range(n)))
    return "\n".join(lines)
