# main.py — news-image-20261122
# Draws a 1024x1024 newspaper front page summing up Sunday 22 November 2026.
# Stdlib only (math, os, struct, zlib). Own PNG writer, own bitmap fonts drawn
# from code — no Pillow, no system fonts, no network, deterministic output.
import math
import os
import struct
import zlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

W, H = 1024, 1024
SS = 3  # supersampling factor: draw at 3x, downsample for smooth edges

# ---------- palette ----------
NAVY = (13, 22, 58)
NAVY2 = (24, 38, 88)
CREAM = (246, 240, 226)
PAPER = (252, 249, 240)
INK = (18, 18, 18)
GREY = (110, 108, 100)
MAROON = (148, 32, 40)
MAROON2 = (178, 52, 58)
GOLD = (214, 178, 94)
TEAL = (28, 112, 102)
TEAL2 = (52, 140, 128)
TAN = (176, 124, 52)
TAN2 = (198, 150, 78)
SLATE = (74, 92, 122)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (196, 38, 38)
GREEN = (34, 128, 74)
BLUE = (38, 84, 160)
YELLOW = (232, 196, 64)
ORANGE = (214, 110, 40)
LIGHT = (238, 232, 216)
LINE = (200, 192, 172)

# ---------- PNG writer (signature + IHDR + zlib IDAT + IEND, RGB, filter 0) ----------
def _png_chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    c += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return c


def write_png(path, w, h, rgb):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    blob = sig + _png_chunk(b"IHDR", ihdr)
    blob += _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    blob += _png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(blob)


# ---------- supersampled canvas ----------
class Canvas:
    def __init__(self, w, h, ss=SS):
        self.w, self.h, self.ss = w, h, ss
        self.px = bytearray(w * ss * h * ss * 3)

    def _set(self, x, y, c):
        # x, y in supersampled pixels; silently clip
        if 0 <= x < self.w * self.ss and 0 <= y < self.h * self.ss:
            i = (y * self.w * self.ss + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x, y, w, h, c, fill=True):
        # x, y, w, h in display pixels (floats ok); fills the SS block
        if not fill:
            self.rect(x, y, w, 1.0, c)
            self.rect(x, y + h - 1.0, w, 1.0, c)
            self.rect(x, y, 1.0, h, c)
            self.rect(x + w - 1.0, y, 1.0, h, c)
            return
        x0 = int(round(x * self.ss)); y0 = int(round(y * self.ss))
        x1 = int(round((x + w) * self.ss)); y1 = int(round((y + h) * self.ss))
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(self.w * self.ss, x1); y1 = min(self.h * self.ss, y1)
        for yy in range(y0, y1):
            base = (yy * self.w * self.ss + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = c

    def line(self, x0, y0, x1, y1, c, t=1.0):
        # thick line in display pixels (Bresenham + thickness via rects)
        dx = x1 - x0; dy = y1 - y0
        n = int(max(abs(dx), abs(dy)) * self.ss) + 1
        r = t / 2.0
        for i in range(n + 1):
            t_ = i / max(1, n)
            self.rect(x0 + dx * t_ - r, y0 + dy * t_ - r, t, t, c)

    def circle(self, cx, cy, r, c, fill=True):
        rr = int(math.ceil(r * self.ss))
        cx0 = int(round(cx * self.ss)); cy0 = int(round(cy * self.ss))
        for dy in range(-rr, rr + 1):
            for dx in range(-rr, rr + 1):
                d = math.sqrt(dx * dx + dy * dy) / self.ss
                if fill and d <= r:
                    self._set(cx0 + dx, cy0 + dy, c)
                elif (not fill) and abs(d - r) <= 0.6:
                    self._set(cx0 + dx, cy0 + dy, c)

    def poly(self, pts, c):
        # filled polygon, display-pixel points; scanline fill
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = int(math.floor(min(ys))); y1 = int(math.ceil(max(ys)))
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(len(pts)):
                ax, ay = pts[i]; bx, by = pts[(i + 1) % len(pts)]
                if (ay <= y < by) or (by <= y < ay):
                    t_ = (y - ay) / (by - ay) if by != ay else 0
                    xs.append(ax + t_ * (bx - ax))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(xs[k], y, xs[k + 1] - xs[k], 1, c)

    def arc(self, cx, cy, r, a0, a1, c, t=1.0):
        # arc in display pixels; angles in radians
        n = max(8, int(abs(a1 - a0) * r * self.ss))
        px = py = None
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            x = cx + r * math.cos(a); y = cy + r * math.sin(a)
            if px is not None:
                self.line(px, py, x, y, c, t)
            px, py = x, y

    def downsample(self):
        # 3x3 box average -> 1024x1024 RGB bytes
        out = bytearray(self.w * self.h * 3)
        sw = self.w * self.ss
        for y in range(self.h):
            for x in range(self.w):
                r = g = b = 0
                for dy in range(self.ss):
                    base = ((y * self.ss + dy) * sw + x * self.ss) * 3
                    for dx in range(self.ss):
                        i = base + dx * 3
                        r += self.px[i]; g += self.px[i + 1]; b += self.px[i + 2]
                n = self.ss * self.ss
                o = (y * self.w + x) * 3
                out[o] = r // n; out[o + 1] = g // n; out[o + 2] = b // n
        return bytes(out)

# ---------- bitmap fonts (hand-drawn in this session) ----------
# FONT8: 8 wide x 12 tall, bold sans. Caps rows 1-9, baseline row 9,
# x-height rows 4-9, descenders rows 10-11. '#' = ink, '.' = empty.
FONT8 = {
"A": ["........", ".######.", "##....##", "##....##", "##....##", "########",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"B": ["........", "#######.", "##....##", "##....##", "##....##", "#######.",
      "##....##", "##....##", "##....##", "#######.", "........", "........"],
"C": ["........", ".######.", "##....##", "##......", "##......", "##......",
      "##......", "##......", "##....##", ".######.", "........", "........"],
"D": ["........", "######..", "##....##", "##....##", "##....##", "##....##",
      "##....##", "##....##", "##....##", "######..", "........", "........"],
"E": ["........", "########", "##......", "##......", "##......", "#######.",
      "##......", "##......", "##......", "########", "........", "........"],
"F": ["........", "########", "##......", "##......", "##......", "#######.",
      "##......", "##......", "##......", "##......", "........", "........"],
"G": ["........", ".######.", "##....##", "##......", "##......", "##..####",
      "##....##", "##....##", "##....##", ".#####..", "........", "........"],
"H": ["........", "##....##", "##....##", "##....##", "##....##", "########",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"I": ["........", "########", "...##...", "...##...", "...##...", "...##...",
      "...##...", "...##...", "...##...", "########", "........", "........"],
"J": ["........", "....####", ".....##.", ".....##.", ".....##.", ".....##.",
      ".....##.", "##...##.", "##...##.", ".#####..", "........", "........"],
"K": ["........", "##....##", "##...##.", "##..##..", "##.##...", "####....",
      "##.##...", "##..##..", "##...##.", "##....##", "........", "........"],
"L": ["........", "##......", "##......", "##......", "##......", "##......",
      "##......", "##......", "##......", "########", "........", "........"],
"M": ["........", "##....##", "###..###", "##.##.##", "##.##.##", "##.##.##",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"N": ["........", "##....##", "###...##", "##.#..##", "##..#.##", "##...###",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"O": ["........", ".######.", "##....##", "##....##", "##....##", "##....##",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"P": ["........", "#######.", "##....##", "##....##", "##....##", "#######.",
      "##......", "##......", "##......", "##......", "........", "........"],
"Q": ["........", ".######.", "##....##", "##....##", "##....##", "##....##",
      "##..#.##", "##...###", "##....##", ".#####.#", "........", "........"],
"R": ["........", "#######.", "##....##", "##....##", "##....##", "#######.",
      "##..##..", "##...##.", "##....##", "##....##", "........", "........"],
"S": ["........", ".######.", "##....##", "##......", "##......", ".######.",
      "......##", "......##", "##....##", ".######.", "........", "........"],
"T": ["........", "########", "...##...", "...##...", "...##...", "...##...",
      "...##...", "...##...", "...##...", "...##...", "........", "........"],
"U": ["........", "##....##", "##....##", "##....##", "##....##", "##....##",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"V": ["........", "##....##", "##....##", "##....##", "##....##", "##....##",
      "##....##", ".##..##.", ".##..##.", "..####..", "........", "........"],
"W": ["........", "##....##", "##....##", "##....##", "##....##", "##.##.##",
      "##.##.##", "##.##.##", "###..###", "##....##", "........", "........"],
"X": ["........", "##....##", ".##..##.", ".##..##.", "..####..", "..####..",
      ".##..##.", ".##..##.", "##....##", "##....##", "........", "........"],
"Y": ["........", "##....##", "##....##", ".##..##.", "..####..", "...##...",
      "...##...", "...##...", "...##...", "...##...", "........", "........"],
"Z": ["........", "########", "......##", ".....##.", "....##..", "...##...",
      "..##....", ".##.....", "##......", "########", "........", "........"],
}

FONT8.update({
"a": ["........", "........", "........", "........", ".######.", "......##",
      ".######.", "##....##", "##....##", ".#####.#", "........", "........"],
"b": ["........", "##......", "##......", "##......", "######..", "##....##",
      "##....##", "##....##", "##....##", "######..", "........", "........"],
"c": ["........", "........", "........", "........", ".######.", "##....##",
      "##......", "##......", "##....##", ".######.", "........", "........"],
"d": ["........", "......##", "......##", "......##", ".######.", "##....##",
      "##....##", "##....##", "##....##", ".#####.#", "........", "........"],
"e": ["........", "........", "........", "........", ".######.", "##....##",
      "########", "##......", "##....##", ".######.", "........", "........"],
"f": ["........", "...####.", "..##....", "..##....", "#######.", "..##....",
      "..##....", "..##....", "..##....", "..##....", "........", "........"],
"g": ["........", "........", "........", "........", ".#####.#", "##....##",
      "##....##", "##....##", ".######.", "......##", ".#####..", "........"],
"h": ["........", "##......", "##......", "##......", "######..", "##....##",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"i": ["........", "........", "..##....", "........", "..##....", "..##....",
      "..##....", "..##....", "..##....", "..##....", "........", "........"],
"j": ["........", "........", ".....##.", "........", ".....##.", ".....##.",
      ".....##.", ".....##.", "##...##.", ".#####..", "........", "........"],
"k": ["........", "##......", "##......", "##......", "##...##.", "##..##..",
      "####....", "##..##..", "##...##.", "##....##", "........", "........"],
"l": ["........", "..##....", "..##....", "..##....", "..##....", "..##....",
      "..##....", "..##....", "..##....", "..##....", "........", "........"],
"m": ["........", "........", "........", "........", "###.###.", "##.##.##",
      "##.##.##", "##.##.##", "##.##.##", "##.##.##", "........", "........"],
"n": ["........", "........", "........", "........", "######..", "##....##",
      "##....##", "##....##", "##....##", "##....##", "........", "........"],
"o": ["........", "........", "........", "........", ".######.", "##....##",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"p": ["........", "........", "........", "........", "######..", "##....##",
      "##....##", "##....##", "######..", "##......", "##......", "##......"],
"q": ["........", "........", "........", "........", ".######.", "##....##",
      "##....##", "##....##", ".######.", "......##", "......##", "......##"],
"r": ["........", "........", "........", "........", "##.###..", "##...##.",
      "##......", "##......", "##......", "##......", "........", "........"],
"s": ["........", "........", "........", "........", ".######.", "##....##",
      "##......", ".######.", "......##", ".######.", "........", "........"],
"t": ["........", "..##....", "..##....", "..##....", "#######.", "..##....",
      "..##....", "..##....", "..##....", "...###..", "........", "........"],
"u": ["........", "........", "........", "........", "##....##", "##....##",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"v": ["........", "........", "........", "........", "##....##", "##....##",
      "##....##", "##....##", ".##..##.", "..####..", "........", "........"],
"w": ["........", "........", "........", "........", "##....##", "##....##",
      "##.##.##", "##.##.##", "##.##.##", ".##..##.", "........", "........"],
"x": ["........", "........", "........", "........", "##....##", ".##..##.",
      "..####..", "..####..", ".##..##.", "##....##", "........", "........"],
"y": ["........", "........", "........", "........", "##....##", "##....##",
      "##....##", "##....##", ".#####..", ".....##.", ".####...", "........"],
"z": ["........", "........", "........", "........", "########", "......##",
      ".....##.", "...##...", "..##....", "########", "........", "........"],
"0": ["........", ".######.", "##....##", "##...###", "##..#.##", "##.#..##",
      "###...##", "##....##", "##....##", ".######.", "........", "........"],
"1": ["........", "...##...", "..###...", "...##...", "...##...", "...##...",
      "...##...", "...##...", "...##...", ".######.", "........", "........"],
"2": ["........", ".######.", "##....##", "......##", ".....##.", "...###..",
      "..##....", ".##.....", "##......", "########", "........", "........"],
"3": ["........", ".######.", "##....##", "......##", "......##", "..#####.",
      "......##", "......##", "##....##", ".######.", "........", "........"],
"4": ["........", "....##..", "...###..", "..##.#..", ".##..##.", "########",
      ".....##.", ".....##.", ".....##.", ".....##.", "........", "........"],
"5": ["........", "########", "##......", "##......", "#######.", "......##",
      "......##", "......##", "##....##", ".######.", "........", "........"],
"6": ["........", ".######.", "##......", "##......", "#######.", "##....##",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"7": ["........", "########", "......##", ".....##.", "....##..", "...##...",
      "...##...", "...##...", "...##...", "...##...", "........", "........"],
"8": ["........", ".######.", "##....##", "##....##", "##....##", ".######.",
      "##....##", "##....##", "##....##", ".######.", "........", "........"],
"9": ["........", ".######.", "##....##", "##....##", "##....##", ".######.",
      "......##", "......##", "......##", ".######.", "........", "........"],
" ": ["........"] * 12,
".": ["........", "........", "........", "........", "........", "........",
      "........", "........", "........", "..##....", "..##....", "........"],
",": ["........", "........", "........", "........", "........", "........",
      "........", "........", "........", "..##....", "..##....", ".##....."],
":": ["........", "........", "........", "........", "..##....", "..##....",
      "........", "..##....", "..##....", "........", "........", "........"],
";": ["........", "........", "........", "........", "..##....", "..##....",
      "........", "..##....", "..##....", "..##....", ".##.....", "........"],
"'": ["........", "..##....", "..##....", "..##....", "........", "........",
      "........", "........", "........", "........", "........", "........"],
'"': ["........", "..##..##", "..##..##", "..##..##", "........", "........",
      "........", "........", "........", "........", "........", "........"],
"-": ["........", "........", "........", "........", "........", "........",
      ".######.", "........", "........", "........", "........", "........"],
"/": ["........", "......##", ".....##.", "....##..", "...##...", "...##...",
      "..##....", ".##.....", "##......", "##......", "........", "........"],
"(": ["........", "....##..", "...##...", "..##....", "..##....", "..##....",
      "..##....", "..##....", "...##...", "....##..", "........", "........"],
")": ["........", "..##....", "...##...", "....##..", "....##..", "....##..",
      "....##..", "....##..", "...##...", "..##....", "........", "........"],
"%": ["........", "##....##", "##...##.", "....##..", "...##...", "..##....",
      ".##.....", ".##...##", "##....##", "........", "........", "........"],
"$": ["........", "...##...", ".######.", "##..##..", "##......", ".#####..",
      ".....##.", "##...##.", ".#####..", "...##...", "........", "........"],
"+": ["........", "........", "........", "........", "...##...", "...##...",
      ".######.", "...##...", "...##...", "........", "........", "........"],
"=": ["........", "........", "........", "........", "########", "........",
      "........", "########", "........", "........", "........", "........"],
"•": ["........", "........", "........", "........", "........", "..####..",
      "..####..", "..####..", "........", "........", "........", "........"],
"*": ["........", "........", "##.##.##", "..####..", "########", "..####..",
      "##.##.##", "........", "........", "........", "........", "........"],
"á": ["........", "....##..", "...##...", "........", ".######.", "......##",
      ".######.", "##....##", "##....##", ".#####.#", "........", "........"],
"é": ["........", "....##..", "...##...", "........", ".######.", "##....##",
      "########", "##......", "##....##", ".######.", "........", "........"],
"í": ["........", "....##..", "...##...", "........", "..##....", "..##....",
      "..##....", "..##....", "..##....", "..##....", "........", "........"],
"!": ["........", "..##....", "..##....", "..##....", "..##....", "..##....",
      "..##....", "..##....", "........", "..##....", "........", "........"],
"?": ["........", ".######.", "##....##", "......##", ".....##.", "...##...",
      "...##...", "........", "...##...", "...##...", "........", "........"],
"_": ["........", "........", "........", "........", "........", "........",
      "........", "........", "........", "........", "########", "........"],
"#": ["........", "........", ".##..##.", ".##..##.", "########", ".##..##.",
      "########", ".##..##.", ".##..##.", "........", "........", "........"],
"~": ["........", "........", "........", "........", "........", "..##.##.",
      ".##.##..", "........", "........", "........", "........", "........"],
"—": ["........", "........", "........", "........", "........", "........",
      "########", "........", "........", "........", "........", "........"],
"’": ["........", "..##....", "..##....", "..##....", "........", "........",
      "........", "........", "........", "........", "........", "........"],
})

# FONT5: 5 wide x 7 tall, bold sans for small print. Caps rows 0-5, baseline
# row 5, x-height rows 2-5, descenders row 6.
FONT5 = {
"A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "....."],
"B": ["####.", "#...#", "#...#", "####.", "#...#", "####.", "....."],
"C": [".###.", "#...#", "#....", "#....", "#...#", ".###.", "....."],
"D": ["####.", "#...#", "#...#", "#...#", "#...#", "####.", "....."],
"E": ["#####", "#....", "#....", "####.", "#....", "#####", "....."],
"F": ["#####", "#....", "#....", "####.", "#....", "#....", "....."],
"G": [".###.", "#...#", "#....", "#.###", "#...#", ".###.", "....."],
"H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "....."],
"I": ["#####", "..#..", "..#..", "..#..", "..#..", "#####", "....."],
"J": ["..###", "...#.", "...#.", "...#.", "#..#.", ".##..", "....."],
"K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#...#", "....."],
"L": ["#....", "#....", "#....", "#....", "#....", "#####", "....."],
"M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "....."],
"N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "....."],
"O": [".###.", "#...#", "#...#", "#...#", "#...#", ".###.", "....."],
"P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "....."],
"Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", ".##.#", "....."],
"R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "....."],
"S": [".####", "#....", ".###.", "....#", "#...#", ".###.", "....."],
"T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "....."],
"U": ["#...#", "#...#", "#...#", "#...#", "#...#", ".###.", "....."],
"V": ["#...#", "#...#", "#...#", "#...#", ".#.#.", "..#..", "....."],
"W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#.", "....."],
"X": ["#...#", ".#.#.", "..#..", "..#..", ".#.#.", "#...#", "....."],
"Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "....."],
"Z": ["#####", "....#", "...#.", "..#..", ".#...", "#####", "....."],
"a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".###."],
"b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
"c": [".....", ".....", ".###.", "#...#", "#....", "#...#", ".###."],
"d": ["....#", "....#", ".###.", "#...#", "#...#", "#...#", ".####"],
"e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
"f": ["..##.", ".#...", ".#...", "#####", ".#...", ".#...", ".#..."],
"g": [".....", ".....", ".###.", "#...#", "#...#", ".####", "....#"],
"h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
"i": [".....", "..#..", ".....", "..#..", "..#..", "..#..", "..#.."],
"j": [".....", "...#.", ".....", "...#.", "...#.", "...#.", ".##.."],
"k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
"l": ["..#..", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
"m": [".....", ".....", "##.##", "#####", "#.#.#", "#.#.#", "#.#.#"],
"n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
"o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
"p": [".....", ".....", "####.", "#...#", "#...#", "####.", "#...."],
"q": [".....", ".....", ".###.", "#...#", "#...#", ".####", "....#"],
"r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
"s": [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
"t": ["..#..", "..#..", "#####", "..#..", "..#..", "..#..", ".###."],
"u": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".###."],
"v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
"w": [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
"x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
"y": [".....", ".....", "#...#", "#...#", "#...#", ".####", "....#"],
"z": [".....", ".....", "#####", "....#", "...#.", "..#..", "#####"],
}

FONT5.update({
"0": [".###.", "#...#", "#...#", "#...#", "#...#", ".###.", "....."],
"1": ["..#..", ".##..", "..#..", "..#..", "..#..", ".###.", "....."],
"2": [".###.", "#...#", "....#", "...#.", "..#..", "#####", "....."],
"3": [".###.", "#...#", "....#", "..##.", "....#", ".###.", "....."],
"4": ["...#.", "..##.", ".#.#.", "#####", "...#.", "...#.", "....."],
"5": ["#####", "#....", "####.", "....#", "#...#", ".###.", "....."],
"6": [".###.", "#....", "####.", "#...#", "#...#", ".###.", "....."],
"7": ["#####", "....#", "...#.", "..#..", "..#..", "..#..", "....."],
"8": [".###.", "#...#", "#...#", ".###.", "#...#", ".###.", "....."],
"9": [".###.", "#...#", "#...#", ".####", "....#", ".###.", "....."],
" ": ["....."] * 7,
".": [".....", ".....", ".....", ".....", ".....", "..#..", "....."],
",": [".....", ".....", ".....", ".....", ".....", "..#..", ".#..."],
":": [".....", ".....", "..#..", ".....", "..#..", ".....", "....."],
";": [".....", ".....", "..#..", ".....", "..#..", "..#..", ".#..."],
"'": ["..#..", "..#..", ".....", ".....", ".....", ".....", "....."],
'"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
"-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
"/": ["....#", "...#.", "..#..", "..#..", ".#...", "#....", "....."],
"(": ["...#.", "..#..", "..#..", "..#..", "..#..", "...#.", "....."],
")": [".#...", "..#..", "..#..", "..#..", "..#..", ".#...", "....."],
"%": ["#.#..", "#.#..", "..#..", ".#...", "..#.#", "..#.#", "....."],
"$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
"+": [".....", ".....", "..#..", ".###.", "..#..", ".....", "....."],
"=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
"•": [".....", ".....", ".....", ".###.", ".###.", ".....", "....."],
"*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
"á": ["...#.", "..#..", ".....", ".###.", "....#", ".####", "#...#"],
"é": ["...#.", "..#..", ".....", ".###.", "#...#", "#####", ".###."],
"í": ["...#.", "..#..", ".....", "..#..", "..#..", "..#..", "..#.."],
"!": ["..#..", "..#..", "..#..", "..#..", ".....", "..#..", "....."],
"?": [".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."],
"_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
"#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", "....."],
"~": [".....", ".....", ".....", ".##.#", "#.#.#", ".....", "....."],
"—": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
"’": ["..#..", "..#..", ".....", ".....", ".....", ".....", "....."],
})


# ---------- text drawing ----------
def _font_of(font):
    return FONT8 if font == 8 else FONT5


def _glyph(font, ch):
    f = _font_of(font)
    g = f.get(ch)
    if g is None:
        g = f.get("?", f[" "])
    return g


def _gw(font):
    return 8 if font == 8 else 5


def text_w(text, font, scale):
    # advance per glyph = (glyph width + 1 tracking) * scale
    return len(text) * (_gw(font) + 1) * scale


def _stamp(cv, x, y, font, ch, scale, color, bold):
    # stamp one glyph: (x, y) = top-left in display px; scale in display px
    # per font pixel. bold widens every ink cell by 1 supersampled px right.
    g = _glyph(font, ch)
    gh = len(g); gw = len(g[0])
    for ry in range(gh):
        row = g[ry]
        for rx in range(gw):
            if row[rx] != "#":
                continue
            cx = x + rx * scale
            cy = y + ry * scale
            w = scale + (1.0 / SS if bold else 0.0)
            cv.rect(cx, cy, w, scale, color)


def draw_text(cv, x, y, text, font, scale, color, bold=True, heavy=False):
    # heavy = double-stamp 1 display px apart (display text, no dilation);
    # bold = +1 supersampled px dilation (body text). Returns end x.
    adv = (_gw(font) + 1) * scale
    cx = x
    for ch in text:
        if heavy:
            _stamp(cv, cx, y, font, ch, scale, color, False)
            _stamp(cv, cx + 1.0, y, font, ch, scale, color, False)
        else:
            _stamp(cv, cx, y, font, ch, scale, color, bold)
        cx += adv
    return cx


def draw_text_c(cv, cx, y, text, font, scale, color, bold=True, heavy=False):
    w = text_w(text, font, scale)
    return draw_text(cv, cx - w / 2.0, y, text, font, scale, color, bold, heavy)


def wrap(text, font, scale, max_w):
    words = text.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_w(trial, font, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_justified_line(cv, x, y, line, font, scale, max_w, color, bold=True):
    # Stretch one wrapped line to exactly max_w by widening its word gaps.
    # Falls back to left-aligned when the line has <2 words, already fills
    # the width, or a gap would grow past ~2x one space width (gappy).
    # Wrapped lines usually fall 40-65px short, i.e. up to ~9px per gap,
    # so a 1x guard left almost every line left-aligned.
    words = line.split(" ")
    if len(words) < 2:
        draw_text(cv, x, y, line, font, scale, color, bold=bold)
        return
    gaps = len(words) - 1
    space_adv = (_gw(font) + 1) * scale
    extra = max_w - text_w(line, font, scale)
    if extra <= 0 or extra / gaps > 2 * space_adv:
        draw_text(cv, x, y, line, font, scale, color, bold=bold)
        return
    per = extra / gaps
    cx = x
    for wi, wd in enumerate(words):
        draw_text(cv, cx, y, wd, font, scale, color, bold=bold)
        cx += text_w(wd, font, scale)
        if wi < gaps:
            cx += space_adv + per

# ---------- story data (verified Sun 22 Nov 2026, >=2 outlets each) ----------
TICKER = ("Iran strikes US bases in Bahrain  •  COP31 vote at 13:00 WIB  •  "
          "Bitcoin back above $60,000  •  Barcelona fight back to beat Villarreal 3–2")

STATS = [
    ("4th", "IRAN ATTACKS BAHRAIN"),
    ("$60,000", "BITCOIN REBOUNDS"),
    ("720/9", "INDIA RECORD TOTAL"),
    ("3–2", "BARCELONA COMEBACK"),
    ("36", "CIKANDE MISSING"),
    ("704", "POLRI ROTATED"),
]

CHIPS = [
    ("ASIA-PACIFIC", 10), ("SPORT", 10), ("EUROPE", 3), ("MIDDLE EAST", 2),
    ("AMERICAS", 2), ("GLOBAL", 2), ("AFRICA", 1),
]

# (chip, headline, body, sources, visual, visual label)
CARDS = [
    ("MIDDLE EAST • SECURITY",
     "Iran strikes US bases in Bahrain",
     "IRGC missiles and drones hit Patriot radars at al-Riffa and Awali late "
     "Saturday; Bahrain says defences intercepted several. A civilian facility "
     "was hit; no injuries reported.",
     "Al Jazeera; Reuters", "bahrain", "4th ATTACK IN 9 DAYS"),
    ("GLOBAL • CLIMATE",
     "COP31 final text put to vote",
     "The final package was put to the vote at 13:00 WIB, but the latest "
     "draft still omits fossil fuels explicitly. Outcome pending; Panama "
     "threatens to block any deal without them.",
     "Reuters; AFP", "cop31", "VOTE 13:00 WIB"),
    ("ASIA-PACIFIC • DISASTER",
     "Candy-factory fire kills 3; 36 still missing",
     "Fire broke out Saturday evening at PT Fonusa Agung Mulia in Cikande, "
     "Serang. Rescuers searched Sunday; 15 survived, 4 were injured, 36 are "
     "still unaccounted for.",
     "Kantor SAR Banten; Reuters", "cikande", "3 KILLED • 36 MISSING"),
    ("GLOBAL • MARKETS",
     "Bitcoin rebounds above $60,000",
     "Bitcoin traded near $60,000 on Sunday, up about 2% after sliding towards "
     "$55,000 on Saturday. Ether rose 3.7%; the Fear and Greed index sat at 8-12, "
     "Extreme Fear.",
     "CoinMarketCap; Finnhub", "bitcoin", "$55K TO $60K"),
    ("SPORT • CRICKET",
     "India declare 720/9 — a record in New Zealand",
     "India posted the highest Test total ever in New Zealand on day four in "
     "Wellington. Rahul made 136 and Pant 128 off 153 balls; India lead by 352.",
     "SuperSport; IANS", "cricket", "720/9 • RECORD IN NZ"),
    ("SPORT • FOOTBALL",
     "Barcelona fight back to beat Villarreal 3–2",
     "Villarreal led 2–0 in seven minutes (Buchanan 5', Oluwaseyi 7'). "
     "Barcelona hit back: Gerard Martin 57', Fermin Lopez 61', Navarro own "
     "goal 67'. Barcelona lead on 36 points, three clear of Real.",
     "Reuters; AP", "barca", "BARCA 3–2 • COMEBACK"),
    ("MIDDLE EAST • GAZA",
     "Aid-van strike kills 3; Gaza toll passes 1,660",
     "An Israeli strike hit a World Central Kitchen aid vehicle in Gaza City on "
     "Saturday. At least 4 were killed Saturday; the toll since the ceasefire "
     "reached 1,661.",
     "Reuters; Al Jazeera", "gaza", "TOLL 1,661"),
    ("ASIA-PACIFIC • POLITICS",
     "Police rotate 704 officers, replace 6 chiefs",
     "Chief Suyudi rotated 704 senior and mid-ranking officers in four telegrams "
     "dated 20 November. Six new regional chiefs were named, including in Papua "
     "and DIY.",
     "Detik; Liputan6", "polri", "704 • 6 KAPOLDA"),
    ("SPORT • FORMULA 1",
     "Verstappen wins chaotic Las Vegas GP",
     "Verstappen held off Mercedes and both McLarens over 50 laps; Norris 2nd "
     "(+0.64s), Piastri 3rd. Russell hit the wall on Lap 49 and finished 9th.",
     "PlanetF1; RacingNews365", "f1", "VER WINS • NOR 2nd • PIA 3rd"),
    ("AMERICAS • TECH",
     "Tesla unveils FSD v15 with 'Reality View'",
     "Tesla announced a new self-driving visualisation, claiming 25 times better "
     "handling of safety-critical cases. A wide release is planned for December.",
     "Electrek; Gizmodo", "tesla", "25× BETTER"),
]

# (headline, sources)
BRIEFS = [
    ("Russia opens crypto trading; retail cap 300,000 rubles a year",
     "Bank of Russia; CryptoNews"),
    ("Reform UK: ban foreign graduates who skip loan repayments",
     "The Sun; The Telegraph"),
    ("76ers edge Bucks 132–129 in Saturday-night thriller",
     "NBA; ESPN"),
    ("NHL: Lindholm scores 4, Blues win 9–6, Scheifele sets Jets record",
     "TSN; Flashscore"),
    ("SpaceX to launch NROL-136 spy satellites tonight, 19:23 WIB",
     "Spaceflight Now; SpaceX"),
    ("Nepal PM Shah arrives in Delhi for first India visit",
     "Radio Nepal; IANS"),
    ("SCO forum ends in Delhi; Pakistan minister first in India in 3 yrs",
     "ANI; MEA"),
    ("BMKG: heavy rain in 8 provinces today as cyclone seed 96S nears",
     "ANTARA; BMKG"),
    ("Pakistan forces kill 15 terrorists in two Mastung operations",
     "Dawn; Geo News"),
    ("Australia hits back at US report saying AUKUS weakens US Navy",
     "Reuters"),
    ("China opposes FCC ban on Chinese telecoms, warns of countermeasures",
     "Reuters"),
    ("Anupama retains world snooker title 3–1, back-to-back",
     "PTI; The Bridge"),
    ("Ukraine runs power-outage schedules after Friday's mass strikes",
     "Ukrenergo; DTEK"),
    ("South Africa wildfire: 24 homes destroyed, 25,000 hectares burned",
     "IOL; IQAir"),
    ("ATP final tonight: Zverev vs Alcaraz for $5.17 million",
     "ATP; BBC"),
    ("Liverpool vs Man Utd tonight — Pochettino's first game in charge",
     "Premier League; The Times"),
    ("Ireland beat South Africa 20–17; France reach Nations final",
     "BBC; SuperSport"),
    ("Malen scores four as Roma thrash Parma 5–1",
     "SuperSport; AS Roma"),
    ("MotoGP tonight: Márquez gets second title shot after sprint crash",
     "Autosport; The Race"),
    ("Unions demand Jakarta revise 2027 wage to Rp6.42m",
     "iNews; Jawawa"),
]

# ---------- visuals (one drawn scene per story, label bar at the bottom) ----------
def vlabel(cv, x, y, w, h, text, bar=NAVY, fg=WHITE):
    # dark label bar across the bottom of the visual box; text shrinks to fit
    cv.rect(x, y + h - 16, w, 16, bar)
    sc = 0.8
    while text_w(text, 5, sc) > w - 8 and sc > 0.55:
        sc -= 0.03
    draw_text_c(cv, x + w / 2.0, y + h - 13.5, text, 5, sc, fg, bold=True)


def v_bahrain(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (16, 30, 66))
    # Saudi land left, Qatar peninsula, Bahrain island with a Patriot radar
    cv.poly([(x + 8, y + 36), (x + 52, y + 28), (x + 58, y + 54), (x + 44, y + 74),
             (x + 14, y + 70)], (58, 96, 140))
    cv.poly([(x + 66, y + 40), (x + 86, y + 36), (x + 92, y + 52), (x + 78, y + 62),
             (x + 64, y + 56)], (58, 96, 140))
    # Patriot radar dish + launcher on the island shore
    cv.arc(x + 58, y + 36, 7, -2.6, -0.5, (200, 210, 225), 1.6)
    cv.line(x + 58, y + 36, x + 58, y + 46, (200, 210, 225), 1.6)
    cv.rect(x + 50, y + 46, 16, 5, (150, 160, 180))
    cv.circle(x + 74, y + 68, 4, GOLD, fill=True)  # Bahrain island
    cv.circle(x + 74, y + 68, 7, GOLD, fill=False)
    # three missile arcs from the upper right (Iran) down to Bahrain
    cv.arc(x + 108, y + 8, 34, 1.2, 2.4, RED, 3.0)
    cv.arc(x + 108, y + 8, 24, 1.2, 2.4, (232, 120, 110), 2.4)
    cv.arc(x + 108, y + 8, 15, 1.3, 2.4, YELLOW, 1.8)
    cv.circle(x + 88, y + 26, 3, RED, fill=True)
    cv.circle(x + 82, y + 38, 3, RED, fill=True)
    # explosion burst where the missiles land, above the island
    cv.poly([(x + 74, y + 48), (x + 77, y + 53), (x + 83, y + 51), (x + 79, y + 57),
             (x + 85, y + 59), (x + 78, y + 60), (x + 80, y + 66), (x + 74, y + 62),
             (x + 68, y + 66), (x + 70, y + 60), (x + 63, y + 59), (x + 69, y + 57),
             (x + 65, y + 51), (x + 71, y + 53)], YELLOW)
    cv.circle(x + 74, y + 58, 3, ORANGE, fill=True)
    # burning civilian facility on the Saudi shore
    cv.rect(x + 10, y + 66, 16, 10, (90, 70, 60))
    cv.poly([(x + 13, y + 66), (x + 16, y + 56), (x + 19, y + 62), (x + 22, y + 54),
             (x + 25, y + 66)], (232, 120, 40))
    cv.circle(x + 15, y + 52, 3, (120, 116, 110), fill=True)
    cv.circle(x + 19, y + 48, 3, (100, 96, 90), fill=True)
    # tanker in the Strait of Hormuz, bottom right
    cv.rect(x + 86, y + 70, 24, 6, (30, 30, 34))
    cv.rect(x + 104, y + 64, 6, 6, (200, 200, 200))
    cv.line(x + 86, y + 76, x + 110, y + 76, (58, 96, 140), 1.2)
    draw_text(cv, x + 8, y + 8, "BAHRAIN", 5, 0.8, GOLD, bold=True)
    draw_text(cv, x + 8, y + 18, "GULF", 5, 0.8, (150, 180, 220), bold=True)
    draw_text(cv, x + 86, y + 58, "HORMUZ", 5, 0.55, (150, 180, 220), bold=True)
    vlabel(cv, x, y, w, h, label)


def v_cop31(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (24, 84, 72))
    # six mini flags of negotiating blocs along the top
    for i, col in enumerate([BLUE, GREEN, RED, GOLD, WHITE, ORANGE]):
        fx = 8 + i * 14
        cv.rect(x + fx, y + 6, 10, 7, col)
        cv.rect(x + fx, y + 6, 10, 7, WHITE, fill=False)
    draw_text(cv, x + 92, y + 6, "ANTALYA", 5, 0.55, (200, 220, 210), bold=True)
    # clock for the 13:00 WIB vote: hour hand at 1, minute hand at 12
    cv.circle(x + 24, y + 36, 15, CREAM, fill=True)
    cv.circle(x + 24, y + 36, 15, NAVY, fill=False)
    cv.line(x + 24, y + 36, x + 32, y + 23, NAVY, 1.8)
    cv.line(x + 24, y + 36, x + 24, y + 21, NAVY, 1.8)
    cv.circle(x + 24, y + 36, 2, RED, fill=True)
    draw_text(cv, x + 44, y + 26, "13:00", 8, 0.85, WHITE, bold=True, heavy=True)
    draw_text(cv, x + 44, y + 42, "WIB", 8, 0.95, GOLD, bold=True, heavy=True)
    # headline goal: 35% electricity by 2035
    draw_text(cv, x + 86, y + 24, "35%", 8, 1.0, GOLD, bold=True, heavy=True)
    draw_text(cv, x + 82, y + 42, "BY 2035", 5, 0.6, (200, 220, 210), bold=True)
    # delegate desks in a row facing a podium with a microphone
    for dx in range(6):
        cv.rect(x + 8 + dx * 10, y + 56, 7, 5, (200, 210, 205))
    cv.rect(x + 74, y + 52, 18, 10, (176, 124, 52))
    cv.line(x + 83, y + 52, x + 83, y + 46, (200, 210, 225), 1.4)
    cv.circle(x + 83, y + 45, 2, (200, 210, 225), fill=True)
    # "fossil fuels" struck through, big
    draw_text(cv, x + 8, y + 66, "fossil fuels", 5, 0.85, (210, 220, 228), bold=True)
    cv.line(x + 6, y + 73, x + 78, y + 73, RED, 2.2)
    # gavel at bottom right
    cv.rect(x + 92, y + 66, 12, 5, (176, 124, 52))
    cv.line(x + 96, y + 70, x + 110, y + 78, (120, 76, 52), 2.2)
    vlabel(cv, x, y, w, h, label)


def v_cikande(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (66, 30, 24))
    # factory name + smoke puffs rising from the chimney
    draw_text(cv, x + 8, y + 6, "PT FONUSA", 5, 0.6, (220, 200, 180), bold=True)
    cv.circle(x + 96, y + 8, 5, (150, 146, 140), fill=True)
    cv.circle(x + 100, y + 16, 6, (130, 126, 120), fill=True)
    cv.circle(x + 94, y + 24, 5, (110, 106, 100), fill=True)
    cv.circle(x + 102, y + 30, 4, (90, 86, 80), fill=True)
    # factory: sawtooth roof, chimney, big two-tone flame
    cv.poly([(x + 10, y + 62), (x + 10, y + 40), (x + 26, y + 30), (x + 42, y + 40),
             (x + 58, y + 30), (x + 74, y + 40), (x + 90, y + 30), (x + 106, y + 40),
             (x + 106, y + 62)], (120, 76, 52))
    cv.rect(x + 92, y + 26, 8, 36, (120, 76, 52))
    cv.poly([(x + 48, y + 60), (x + 56, y + 26), (x + 62, y + 42), (x + 68, y + 20),
             (x + 74, y + 42), (x + 80, y + 28), (x + 86, y + 60)], (232, 120, 40))
    cv.poly([(x + 56, y + 60), (x + 62, y + 38), (x + 67, y + 50), (x + 72, y + 36),
             (x + 78, y + 60)], YELLOW)
    # second smaller flame licking the roof edge + embers
    cv.poly([(x + 88, y + 60), (x + 92, y + 44), (x + 96, y + 54), (x + 100, y + 46),
             (x + 104, y + 60)], (232, 120, 40))
    cv.circle(x + 40, y + 24, 2, ORANGE, fill=True)
    cv.circle(x + 70, y + 16, 2, YELLOW, fill=True)
    # rescue truck with a ladder at the bottom right
    cv.rect(x + 84, y + 64, 26, 10, RED)
    cv.rect(x + 104, y + 68, 6, 6, (200, 200, 200))
    cv.circle(x + 90, y + 76, 3, INK, fill=True)
    cv.circle(x + 104, y + 76, 3, INK, fill=True)
    cv.line(x + 84, y + 64, x + 66, y + 46, (200, 200, 200), 1.4)
    draw_text(cv, x + 12, y + 62, "3", 8, 1.4, WHITE, bold=True, heavy=True)
    draw_text(cv, x + 32, y + 70, "KILLED", 5, 0.75, (240, 200, 180), bold=True)
    vlabel(cv, x, y, w, h, label)


def v_bitcoin(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (14, 22, 40))
    # faint price gridlines: $60k / $57k / $55k levels
    for gy in (16, 38, 60):
        cv.line(x + 6, y + gy, x + 110, y + gy, (40, 56, 84), 1.0)
    # big candlesticks climbing from $55k (low left) to $60k (high right);
    # each tuple is (cx, y_high, y_low) with y_high above y_low
    candles = [(8, 52, 64, 1), (26, 46, 58, 1), (44, 52, 62, 0), (62, 36, 48, 1),
               (80, 28, 40, 1), (98, 18, 30, 1)]
    for cx, top, bot, up in candles:
        col = GREEN if up else RED
        cv.rect(x + cx, y + top, 12, bot - top, col)
        cv.line(x + cx + 6, y + top - 5, x + cx + 6, y + bot + 5, col, 1.4)
    # bold rising arrow $55K -> $60K
    cv.line(x + 10, y + 60, x + 104, y + 14, GOLD, 2.6)
    cv.line(x + 104, y + 14, x + 92, y + 14, GOLD, 2.6)
    cv.line(x + 104, y + 14, x + 104, y + 26, GOLD, 2.6)
    draw_text(cv, x + 8, y + 4, "$60K", 5, 0.8, GOLD, bold=True)
    draw_text(cv, x + 8, y + 70, "$55K", 5, 0.8, (150, 170, 200), bold=True)
    # Extreme Fear tag, top right
    draw_text(cv, x + 66, y + 4, "EXTREME FEAR", 5, 0.6, (232, 120, 110), bold=True)
    # Fear & Greed gauge, bottom right: red fear zone, needle at 9
    cv.arc(x + 94, y + 78, 13, math.pi, 2 * math.pi, (90, 96, 110), 2.0)
    cv.arc(x + 94, y + 78, 13, math.pi, math.pi + 0.5, RED, 2.0)
    cv.line(x + 94, y + 78, x + 84, y + 70, WHITE, 1.6)
    cv.circle(x + 94, y + 78, 2, WHITE, fill=True)
    draw_text(cv, x + 78, y + 62, "FEAR 9", 5, 0.6, (232, 120, 110), bold=True)
    vlabel(cv, x, y, w, h, label)


def v_cricket(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (20, 88, 52))
    # scoreboard: record total + the two centurions
    cv.rect(x + 8, y + 6, w - 16, 36, (10, 50, 30))
    draw_text_c(cv, x + w / 2.0, y + 10, "720/9", 8, 1.5, WHITE, bold=True, heavy=True)
    draw_text_c(cv, x + w / 2.0, y + 30, "RAHUL 136 • PANT 128", 5, 0.55, GOLD, bold=True)
    # crowd: one dotted row in the stands
    for i in range(14):
        col = [WHITE, GOLD, RED, (200, 210, 225)][i % 4]
        cv.circle(x + 10 + i * 7, y + 46, 1, col, fill=True)
    # pitch strip, batsman, big bat + ball + stumps
    cv.rect(x + 8, y + 50, w - 16, 30, (150, 128, 84))
    # batsman figure at the crease, holding the bat
    cv.circle(x + 20, y + 54, 3, (30, 30, 34), fill=True)
    cv.line(x + 20, y + 57, x + 20, y + 66, (30, 30, 34), 1.8)
    cv.line(x + 20, y + 66, x + 15, y + 76, (30, 30, 34), 1.8)
    cv.line(x + 20, y + 66, x + 25, y + 76, (30, 30, 34), 1.8)
    cv.line(x + 20, y + 60, x + 28, y + 64, (30, 30, 34), 1.6)
    cv.line(x + 26, y + 58, x + 40, y + 72, (214, 178, 94), 3.2)
    cv.rect(x + 38, y + 70, 12, 7, (214, 178, 94))
    cv.circle(x + 90, y + 58, 6, RED, fill=True)
    cv.circle(x + 90, y + 58, 6, WHITE, fill=False)
    cv.line(x + 84, y + 68, x + 84, y + 80, YELLOW, 1.8)
    cv.line(x + 90, y + 68, x + 90, y + 80, YELLOW, 1.8)
    cv.line(x + 96, y + 68, x + 96, y + 80, YELLOW, 1.8)
    vlabel(cv, x, y, w, h, label)


def v_barca(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (246, 240, 226))
    cv.rect(x, y, w, 4, MAROON)
    # venue + the three goal minutes (57', 61', 67')
    draw_text(cv, x + 8, y + 34, "CAMP NOU", 5, 0.6, (120, 110, 100), bold=True)
    draw_text(cv, x + 44, y + 34, "57' • 61' • 67'", 5, 0.6, MAROON, bold=True)
    # goal net behind the ball
    cv.rect(x + w / 2.0 - 26, y + 46, 52, 26, WHITE)
    for gx in range(-26, 27, 8):
        cv.line(x + w / 2.0 + gx, y + 46, x + w / 2.0 + gx, y + 72, (180, 180, 180), 0.8)
    for gy in range(46, 73, 8):
        cv.line(x + w / 2.0 - 26, y + gy, x + w / 2.0 + 26, y + gy, (180, 180, 180), 0.8)
    draw_text_c(cv, x + w / 2.0, y + 10, "3–2", 8, 2.1, MAROON, bold=True, heavy=True)
    # football: bigger white ball with black patches
    cv.circle(x + w / 2.0, y + 60, 17, WHITE, fill=True)
    cv.circle(x + w / 2.0, y + 60, 17, INK, fill=False)
    cv.poly([(x + w / 2.0 - 4, y + 54), (x + w / 2.0 + 4, y + 54),
             (x + w / 2.0 + 2, y + 62), (x + w / 2.0 - 2, y + 62)], INK)
    cv.line(x + w / 2.0, y + 43, x + w / 2.0, y + 54, INK, 1.2)
    cv.line(x + w / 2.0 - 14, y + 56, x + w / 2.0 - 4, y + 58, INK, 1.2)
    cv.line(x + w / 2.0 + 14, y + 56, x + w / 2.0 + 4, y + 58, INK, 1.2)
    # striker silhouette shooting, left of the goal
    cv.circle(x + 16, y + 48, 3, (30, 30, 60), fill=True)
    cv.line(x + 16, y + 51, x + 16, y + 62, (30, 30, 60), 1.8)
    cv.line(x + 16, y + 62, x + 10, y + 72, (30, 30, 60), 1.8)
    cv.line(x + 16, y + 62, x + 24, y + 70, (30, 30, 60), 1.8)
    cv.line(x + 16, y + 54, x + 26, y + 58, (30, 30, 60), 1.6)
    # diving keeper, right of the goal
    cv.circle(x + 100, y + 50, 3, (200, 160, 40), fill=True)
    cv.line(x + 100, y + 53, x + 92, y + 60, (200, 160, 40), 1.8)
    cv.line(x + 92, y + 60, x + 86, y + 70, (200, 160, 40), 1.8)
    cv.line(x + 92, y + 60, x + 98, y + 70, (200, 160, 40), 1.8)
    # confetti around the ball
    for cx, cy, col in [(14, 16, GOLD), (100, 14, MAROON), (10, 44, TEAL),
                        (104, 40, GOLD), (22, 74, MAROON), (96, 76, TEAL)]:
        cv.circle(x + cx, y + cy, 2, col, fill=True)
    vlabel(cv, x, y, w, h, label)


def v_gaza(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (196, 172, 128))
    # Gaza City skyline behind the van, one damaged block with smoke
    for bx, bw, bh in [(6, 16, 18), (26, 12, 14), (42, 18, 16), (86, 14, 30), (104, 10, 22)]:
        cv.rect(x + bx, y + 40 - bh, bw, bh, (150, 128, 96))
    cv.poly([(x + 64, y + 40), (x + 70, y + 26), (x + 76, y + 40)], (150, 128, 96))
    cv.circle(x + 70, y + 22, 3, (120, 116, 110), fill=True)
    cv.circle(x + 73, y + 17, 3, (100, 96, 90), fill=True)
    # aid van: bigger white box van with a large red cross, on a road
    cv.rect(x, y + 66, w, 14, (90, 84, 76))
    cv.rect(x + 10, y + 28, 68, 32, WHITE)
    cv.rect(x + 78, y + 40, 26, 20, WHITE)
    cv.rect(x + 40, y + 36, 8, 16, RED)
    cv.rect(x + 35, y + 41, 18, 7, RED)
    draw_text(cv, x + 56, y + 38, "WCK", 5, 0.7, RED, bold=True)
    cv.circle(x + 28, y + 62, 8, INK, fill=True)
    cv.circle(x + 86, y + 62, 8, INK, fill=True)
    cv.circle(x + 28, y + 62, 3, GREY, fill=True)
    cv.circle(x + 86, y + 62, 3, GREY, fill=True)
    # rubble pile on the road, right
    cv.poly([(x + 96, y + 66), (x + 100, y + 60), (x + 104, y + 66)], (110, 104, 96))
    cv.poly([(x + 104, y + 66), (x + 108, y + 61), (x + 112, y + 66)], (90, 84, 76))
    draw_text(cv, x + 10, y + 6, "1,661", 8, 1.25, MAROON, bold=True, heavy=True)
    draw_text(cv, x + 76, y + 8, "GAZA CITY", 5, 0.6, INK, bold=True)
    vlabel(cv, x, y, w, h, label)


def v_polri(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (18, 28, 62))
    # shield badge, bigger
    cv.poly([(x + 34, y + 8), (x + 64, y + 15), (x + 64, y + 42), (x + 34, y + 62),
             (x + 4, y + 42), (x + 4, y + 15)], GOLD)
    cv.poly([(x + 34, y + 14), (x + 58, y + 20), (x + 58, y + 40), (x + 34, y + 56),
             (x + 10, y + 40), (x + 10, y + 20)], NAVY)
    draw_text_c(cv, x + 34, y + 26, "704", 8, 1.25, GOLD, bold=True, heavy=True)
    draw_text(cv, x + 74, y + 28, "6", 8, 1.4, WHITE, bold=True, heavy=True)
    draw_text(cv, x + 74, y + 50, "NEW", 5, 0.7, (170, 190, 220), bold=True)
    draw_text(cv, x + 74, y + 60, "CHIEFS", 5, 0.7, (170, 190, 220), bold=True)
    # telegram number, top right
    draw_text(cv, x + 72, y + 8, "ST/2598", 5, 0.55, GOLD, bold=True)
    # row of officers below the shield + six dots for the six new chiefs
    for i in range(4):
        ox = 12 + i * 14
        cv.circle(x + ox, y + 68, 3, (200, 200, 200), fill=True)
        cv.rect(x + ox - 4, y + 71, 8, 7, (40, 60, 110))
    for i in range(6):
        cv.circle(x + 76 + i * 6, y + 74, 1, GOLD, fill=True)
    vlabel(cv, x, y, w, h, label)


def v_f1(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (12, 12, 20))
    # chequered strip at top + waving flag at the right end
    for i in range(10):
        cv.rect(x + i * 12, y + 5, 12, 7, WHITE if i % 2 == 0 else INK)
        cv.rect(x + i * 12, y + 12, 12, 7, INK if i % 2 == 0 else WHITE)
    cv.line(x + 108, y + 5, x + 108, y + 22, (200, 200, 200), 1.2)
    cv.rect(x + 108, y + 5, 8, 6, WHITE)
    cv.rect(x + 108, y + 11, 8, 6, INK)
    # chasing pack: Norris (papaya, #2) and Piastri (orange, #3) behind Verstappen
    cv.poly([(x + 12, y + 30), (x + 24, y + 25), (x + 44, y + 25), (x + 52, y + 29),
             (x + 58, y + 30), (x + 58, y + 36), (x + 12, y + 36)], (232, 120, 40))
    cv.circle(x + 22, y + 37, 6, INK, fill=True)
    cv.circle(x + 48, y + 37, 6, INK, fill=True)
    draw_text(cv, x + 32, y + 28, "2", 5, 0.6, WHITE, bold=True)
    cv.poly([(x + 66, y + 26), (x + 76, y + 22), (x + 96, y + 22), (x + 104, y + 26),
             (x + 108, y + 27), (x + 108, y + 33), (x + 66, y + 33)], (232, 150, 40))
    cv.circle(x + 76, y + 34, 6, INK, fill=True)
    cv.circle(x + 98, y + 34, 6, INK, fill=True)
    draw_text(cv, x + 84, y + 25, "3", 5, 0.6, WHITE, bold=True)
    # speed lines behind the lead car
    for sy, sl in [(44, 30), (50, 44), (56, 58)]:
        cv.line(x + 6, y + sy, x + 6 + sl, y + sy, (90, 90, 100), 1.6)
    # track kerb dashes, behind the lead car
    for i in range(6):
        cv.rect(x + 6 + i * 18, y + 74, 9, 3, RED if i % 2 == 0 else WHITE)
    # bigger, lower F1 car silhouette (Verstappen, red, #1)
    cv.poly([(x + 12, y + 58), (x + 28, y + 48), (x + 62, y + 48), (x + 78, y + 54),
             (x + 102, y + 56), (x + 102, y + 68), (x + 12, y + 68)], RED)
    cv.rect(x + 6, y + 44, 7, 20, RED)
    cv.circle(x + 30, y + 70, 10, INK, fill=True)
    cv.circle(x + 30, y + 70, 4, GREY, fill=True)
    cv.circle(x + 86, y + 70, 10, INK, fill=True)
    cv.circle(x + 86, y + 70, 4, GREY, fill=True)
    draw_text(cv, x + 46, y + 54, "1", 5, 0.8, WHITE, bold=True)
    vlabel(cv, x, y, w, h, label)


def v_tesla(cv, x, y, w, h, label):
    cv.rect(x, y, w, h, (16, 34, 64))
    # camera view cone + car, with sensor arcs sweeping ahead
    cv.poly([(x + 58, y + 16), (x + 18, y + 52), (x + 98, y + 52)], (52, 110, 150))
    cv.poly([(x + 58, y + 16), (x + 34, y + 52), (x + 82, y + 52)], (78, 140, 180))
    cv.arc(x + 58, y + 52, 26, -2.4, -0.7, (120, 190, 220), 1.4)
    cv.arc(x + 58, y + 52, 34, -2.4, -0.7, (90, 160, 200), 1.2)
    # detected objects inside the cone: a pedestrian and a cyclist, boxed
    cv.circle(x + 49, y + 31, 3, WHITE, fill=True)
    cv.line(x + 49, y + 34, x + 49, y + 42, WHITE, 1.6)
    cv.line(x + 49, y + 42, x + 45, y + 50, WHITE, 1.6)
    cv.line(x + 49, y + 42, x + 53, y + 50, WHITE, 1.6)
    cv.rect(x + 42, y + 26, 15, 26, GREEN, fill=False)
    cv.circle(x + 88, y + 31, 3, WHITE, fill=True)
    cv.line(x + 88, y + 34, x + 88, y + 42, WHITE, 1.6)
    cv.circle(x + 82, y + 46, 4, WHITE, fill=False)
    cv.circle(x + 94, y + 46, 4, WHITE, fill=False)
    cv.rect(x + 78, y + 26, 20, 26, GREEN, fill=False)
    cv.poly([(x + 22, y + 56), (x + 34, y + 48), (x + 72, y + 48), (x + 92, y + 56),
             (x + 92, y + 66), (x + 22, y + 66)], (220, 226, 232))
    cv.circle(x + 38, y + 68, 7, INK, fill=True)
    cv.circle(x + 80, y + 68, 7, INK, fill=True)
    # road with lane dashes below the car
    cv.rect(x + 8, y + 74, w - 16, 4, (40, 44, 56))
    for dx in range(3):
        cv.rect(x + 16 + dx * 34, y + 75, 14, 2, (220, 220, 210))
    draw_text(cv, x + 8, y + 6, "25×", 8, 1.15, GOLD, bold=True, heavy=True)
    draw_text(cv, x + 70, y + 8, "FSD v15", 5, 0.7, WHITE, bold=True)
    vlabel(cv, x, y, w, h, label)


VISUALS = {
    "bahrain": v_bahrain, "cop31": v_cop31, "cikande": v_cikande,
    "bitcoin": v_bitcoin, "cricket": v_cricket, "barca": v_barca,
    "gaza": v_gaza, "polri": v_polri, "f1": v_f1, "tesla": v_tesla,
}

# glyphs used by the story text but not in the base sets
FONT8.update({
"–": ["........", "........", "........", "........", "........", "........",
      "########", "........", "........", "........", "........", "........"],
"×": ["........", "........", "........", "........", "........", ".##..##.",
      "..####..", "..####..", ".##..##.", "........", "........", "........"],
})
FONT5.update({
"–": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
"×": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
})


# ---------- layout ----------
def build():
    cv = Canvas(W, H)
    cv.rect(0, 0, W, H, CREAM)

    # masthead
    cv.rect(0, 0, W, 86, NAVY)
    draw_text(cv, 16, 12, "10 TOP STORIES", 5, 0.8, GOLD, bold=True)
    draw_text(cv, 16, 26, "• 20 BRIEFS", 5, 0.8, (170, 190, 220), bold=True)
    draw_text_c(cv, W / 2.0, 4, "THE WORLD IN ONE DAY", 8, 3.2, WHITE,
                bold=True, heavy=True)
    draw_text_c(cv, W / 2.0, 47, "SUNDAY, 22 NOVEMBER 2026", 8, 1.4, GOLD,
                bold=True, heavy=True)
    draw_text_c(cv, W / 2.0, 68,
                "Thirty stories from a world that did not slow down",
                5, 0.8, (200, 210, 225), bold=True)
    cv.circle(948, 43, 26, GOLD, fill=True)
    # "30": digit ink spans font rows 1..9, so the glyph top sits at
    # circle centre - (1 + 9/2) * scale to centre the ink vertically
    draw_text_c(cv, 948, 29.8, "30", 8, 2.4, NAVY, bold=True, heavy=True)
    draw_text_c(cv, 948, 70, "STORIES", 5, 0.65, WHITE, bold=True)

    # ticker
    cv.rect(0, 86, W, 26, MAROON)
    draw_text_c(cv, W / 2.0, 92, TICKER, 5, 0.85, WHITE, bold=True)

    # stat strip: 6 tiles, two calm alternating tones
    tile_w, tile_h, gap = 161, 66, 8
    for i, (num, lab) in enumerate(STATS):
        tx = 8 + i * (tile_w + gap)
        ty = 118
        bg = (255, 255, 255) if i % 2 == 0 else (222, 228, 236)
        cv.rect(tx, ty, tile_w, tile_h, bg)
        cv.rect(tx, ty, tile_w, tile_h, (196, 190, 180), fill=False)
        draw_text_c(cv, tx + tile_w / 2.0, ty + 8, num, 8, 1.5,
                    MAROON if i % 2 == 0 else NAVY, bold=True, heavy=True)
        draw_text_c(cv, tx + tile_w / 2.0, ty + 44, lab, 5, 0.75, INK, bold=True)

    # region chips
    chip_y = 192
    total = 0
    widths = []
    for name, n in CHIPS:
        t = "%s %d" % (name, n)
        wch = text_w(t, 5, 0.75) + 14
        widths.append(wch)
        total += wch
    total += 6 * (len(CHIPS) - 1)
    cx = (W - total) / 2.0
    for (name, n), wch in zip(CHIPS, widths):
        t = "%s %d" % (name, n)
        cv.rect(cx, chip_y, wch, 24, NAVY)
        draw_text_c(cv, cx + wch / 2.0, chip_y + 6, t, 5, 0.75, WHITE, bold=True)
        cx += wch + 6

    # 10 story cards: 2 columns x 5 rows
    card_w, card_h = 496, 112
    for idx, (chip, headline, body, sources, vis, vlab) in enumerate(CARDS):
        col, row = idx % 2, idx // 2
        x = 8 + col * (card_w + 8)
        y = 224 + row * (card_h + 8)
        cv.rect(x, y, card_w, card_h, WHITE)
        cv.rect(x, y, card_w, card_h, (200, 196, 188), fill=False)
        VISUALS[vis](cv, x + 8, y + 8, 116, 96, vlab)
        tx = x + 132
        draw_text(cv, tx, y + 8, chip, 5, 0.8, MAROON, bold=True)
        hl = wrap(headline, 8, 1.05, 356)
        hy = y + 22
        for ln in hl[:2]:
            draw_text(cv, tx, hy, ln, 8, 1.05, INK, bold=True, heavy=True)
            hy += 14
        by = hy + 2
        bl = wrap(body, 5, 1.1, 356)
        shown = bl[:4]
        for li, ln in enumerate(shown):
            # last line of the paragraph stays left-aligned; a shown 4th
            # line is justified too when the paragraph is truncated there
            last_para = (li == len(shown) - 1 and len(bl) <= 4)
            if last_para:
                draw_text(cv, tx, by, ln, 5, 1.1, (52, 52, 52), bold=True)
            else:
                draw_justified_line(cv, tx, by, ln, 5, 1.1, 356,
                                    (52, 52, 52), bold=True)
            by += 10
        draw_text(cv, tx, y + 98, "Sources: " + sources, 5, 0.75, GREY, bold=True)

    # briefs
    by0 = 824
    draw_text(cv, 8, by0, "ALSO TODAY — 20 MORE BRIEFS", 8, 1.0, NAVY,
              bold=True, heavy=True)
    cv.line(8, by0 + 20, W - 8, by0 + 20, NAVY, 1.4)
    col_x = [8, 344, 680]
    for i, (headline, sources) in enumerate(BRIEFS):
        col, row = i % 3, i // 3
        bx = col_x[col]
        by = by0 + 28 + row * 19
        draw_text(cv, bx, by, "•", 5, 0.8, MAROON, bold=True)
        bl = wrap(headline, 5, 0.8, 322)
        ly = by
        for ln in bl[:2]:
            draw_text(cv, bx + 8, ly, ln, 5, 0.8, INK, bold=True)
            ly += 9

    # footer
    draw_text_c(cv, W / 2.0, 976,
                "Sources: Al Jazeera, Reuters, AFP, BBC, Detik, Liputan6, "
                "ANTARA, BMKG, CoinMarketCap, Finnhub, ATP, Premier League",
                5, 0.65, GREY, bold=True)
    draw_text_c(cv, W / 2.0, 986,
                "Facts checked against live reports as of 22 Nov 2026. "
                "Figures are provisional and may change as stories develop.",
                5, 0.65, GREY, bold=True)
    cv.rect(0, 998, W, 26, NAVY)
    draw_text_c(cv, W / 2.0, 1006, "THE WORLD IN ONE DAY", 5, 0.75, WHITE,
                bold=True)
    return cv


def main():
    out = os.path.join(os.environ.get("MAKEFUN_OUTPUT_DIR", SCRIPT_DIR),
                       "entry.png")
    cv = build()
    write_png(out, W, H, cv.downsample())
    return out


if __name__ == "__main__":
    print(main())
