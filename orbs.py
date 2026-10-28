"""
Thinking orbs: a small animated orb drawn with braille dots while Clishe
waits (for the AI, mostly), so a pause looks like work and not a hang.

The geometry of the nine orbs is ported from thinking-orbs 0.3.2 by Jakub
Antalik (MIT License, see NOTICE.md): each frame function returns the same
dots as the original, then `render` draws them onto a braille grid (each
character holds 2x4 dots) in four shades of grey.

    python3 orbs.py run --state composing --caption "Let me think..."
        draws until it is stopped (SIGTERM or Ctrl-C), then erases itself.
        Nothing is drawn in the first 0.3 s, so a quick answer never
        flashes an orb.
    python3 orbs.py demo
        shows all nine, one after another (`clishe orbs`).
"""
import math
import os
import signal
import sys
import time
from typing import Callable, Dict, List, Tuple

# A dot is (x, y, white, alpha) in a size x size box; a line is
# (x1, y1, x2, y2, white, alpha). `white` is the original's ink scale:
# 0 is full ink, 1 is none.
Dot = Tuple[float, float, float, float]
Line = Tuple[float, float, float, float, float, float]

# ---------- shared math (ported as-is) ----------


def _round(x):
    """JavaScript's Math.round (halves go up), not Python's banker's
    rounding: 2.5 must be 3 for the counts to match the original."""
    return math.floor(x + 0.5)


def _lerp(a, b, f):
    return a + (b - a) * f


def _frac(x):
    return x - math.floor(x)


def _hash(a, b):
    h = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return h - math.floor(h)


def _vnoise(x, y):
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a, b = _hash(xi, yi), _hash(xi + 1, yi)
    c, d = _hash(xi, yi + 1), _hash(xi + 1, yi + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def _fib_dir(i, n):
    golden = math.pi * (3 - math.sqrt(5))
    y = 1 - 2 * (i + 0.5) / n
    rad = math.sqrt(1 - y * y)
    a = i * golden
    return rad * math.cos(a), y, rad * math.sin(a)


def _angle_delta(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def _proj(yaw, tilt, cx, cy, scale):
    st, ct, sy, cyw = math.sin(tilt), math.cos(tilt), math.sin(yaw), math.cos(yaw)

    def project(x, y, z):
        x1 = x * cyw + z * sy
        z1 = -x * sy + z * cyw
        y1 = y * ct - z1 * st
        z2 = y * st + z1 * ct
        return cx + x1 * scale, cy - y1 * scale, z2
    return project


def _ghost_sphere(pt, R, n, dots):
    for i in range(n):
        d = _fib_dir(i, n)
        px, py, z = pt(d[0] * R, d[1] * R, d[2] * R)
        depth = (z / R + 1) / 2
        dots.append((px, py, 0.78, 0.1 + 0.22 * depth))


def _lat_lon(rings, lon_density):
    """(cos lat, sin lat, lon) for a dotted sphere of `rings` latitudes."""
    for li in range(rings + 1):
        lat = -math.pi / 2 + li / rings * math.pi
        cos_lat, sin_lat = math.cos(lat), math.sin(lat)
        count = max(1, _round(abs(cos_lat) * lon_density))
        for lj in range(count):
            yield li, cos_lat, sin_lat, lj / count * 2 * math.pi


# ---------- the nine frames ----------

def _frame_orbits(size, t, o):
    cx = cy = size / 2
    R = size / 2 * 0.82
    pt = _proj(t * 0.12, 0.3, cx, cy, 1)
    dots = []
    particles = o.get("particles", 3)
    for orb in range(o.get("orbitN", 12)):
        h1, h2, h3 = _hash(orb, 1.7), _hash(orb, 5.2), _hash(orb, 8.9)
        ro = R * (0.45 + 0.52 * h1)
        th, phi = h1 * 2 * math.pi, math.acos(2 * h2 - 1)
        nx, ny, nz = math.sin(phi) * math.cos(th), math.cos(phi), math.sin(phi) * math.sin(th)
        ux, uy, uz = -ny, nx, 0.0
        ul = max(1e-6, math.sqrt(ux * ux + uy * uy))
        ux, uy = ux / ul, uy / ul
        vx, vy, vz = ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux
        speed = (0.25 + 0.55 * h3) * (1 if h3 > 0.5 else -1)
        ghost_n = o.get("ghostN", 40)

        def on_orbit(a):
            ca, sa = math.cos(a), math.sin(a)
            return pt((ux * ca + vx * sa) * ro, (uy * ca + vy * sa) * ro, (uz * ca + vz * sa) * ro)
        for k in range(ghost_n):
            px, py, z = on_orbit(k / ghost_n * 2 * math.pi)
            depth = (z / ro + 1) / 2
            dots.append((px, py, 0.72, o.get("ghostA", 0.5) * (0.4 + 0.6 * depth)))
        for m in range(particles):
            px, py, z = on_orbit(t * speed + m / particles * 2 * math.pi + h2 * 6)
            depth = (z / ro + 1) / 2
            dots.append((px, py, 0.3 - 0.22 * depth, 1.0))
    return dots, []


def _frame_globe(size, t, o):
    spin = 0.5
    tilt = 0.4 + 0.06 * math.sin(t * 0.35)
    pt = _proj(t * spin, tilt, size / 2, size / 2, size / 2 * 0.82)
    scan = t * (spin + (1.7 - spin) * o.get("scanMul", 1))
    dim = o.get("dimBase", 1)
    dots = []
    for _, cos_lat, sin_lat, lon in _lat_lon(o.get("latRings", 17), o.get("lonDensity", 44)):
        px, py, z = pt(cos_lat * math.cos(lon), sin_lat, cos_lat * math.sin(lon))
        depth = (z + 1) / 2
        d = _angle_delta(lon + t * spin, scan)
        boost = math.exp(-(d * d) / 0.18) * max(0, z)
        dots.append((px, py, o.get("inkFar", 0.62) - o.get("inkSpan", 0.54) * depth,
                     dim + (1 - dim) * min(1, boost)))
    return dots, []


def _moves(count):
    out = []
    for i in range(count):
        axis = min(2, math.floor(_hash(i, 2.3) * 3))
        lo = -1 + 0.5 * min(3, math.floor(_hash(i, 5.9) * 4))
        sign = 1 if _hash(i, 7.7) < 0.5 else -1
        out.append((axis, lo, lo + 0.5, sign * math.pi / 2))
    return out


def _solve_cycle(time_, count, slot_dur, rest):
    cyc = 2 * count * slot_dur + rest
    tc = time_ % cyc
    amount, active = [0.0] * count, -1
    if tc < 2 * count * slot_dur:
        slot = math.floor(tc / slot_dur)
        p = (tc - slot * slot_dur) / slot_dur
        ep = 1 - (1 - min(1, p / 0.7)) ** 3
        if slot < count:
            for i in range(slot):
                amount[i] = 1
            amount[slot], active = ep, slot
        else:
            u = 2 * count - 1 - slot
            for i in range(u):
                amount[i] = 1
            amount[u], active = 1 - ep, u
    return amount, active


def _apply_moves(x, y, z, moves, amount, active):
    in_active = False
    for i, (axis, lo, hi, ang) in enumerate(moves):
        if amount[i] <= 0:
            continue
        coord = (x, y, z)[axis]
        if coord < lo or coord >= hi:
            continue
        if i == active:
            in_active = True
        a = ang * amount[i]
        ca, sa = math.cos(a), math.sin(a)
        if axis == 0:
            y, z = y * ca - z * sa, y * sa + z * ca
        elif axis == 1:
            x, z = x * ca + z * sa, -x * sa + z * ca
        else:
            x, y = x * ca - y * sa, x * sa + y * ca
    return x, y, z, in_active


def _frame_rubik(size, t, o):
    pt = _proj(t * 0.55, 0.35 + 0.1 * math.sin(t * 0.9), size / 2, size / 2, size / 2 * 0.82)
    count = o.get("moveCount", 14)
    moves = _moves(count)
    amount, active = _solve_cycle(t, count, 0.42, 1.2)
    dots = []
    for _, cos_lat, sin_lat, lon in _lat_lon(o.get("latRings", 15), o.get("lonDensity", 40)):
        x, y, z, hot = _apply_moves(cos_lat * math.cos(lon), sin_lat, cos_lat * math.sin(lon),
                                    moves, amount, active)
        px, py, zr = pt(x, y, z)
        depth = (zr + 1) / 2
        dots.append((px, py, o.get("inkFar", 0.62) - o.get("inkSpan", 0.54) * depth - (0.14 if hot else 0), 1.0))
    return dots, []


def _frame_wave(size, t, o):
    R = size / 2 * 0.874
    pt = _proj(t * 0.18, 0.38, size / 2, size / 2, 1)
    dots = []
    rings = o.get("rings", 15)
    waves = {}
    for ri, cos_lat, sin_lat, lon in _lat_lon(rings, o.get("lonDensity", 40)):
        if ri not in waves:
            waves[ri] = 0.62 * math.sin(t * 2.1 - ri * 0.52) + 0.38 * math.sin(t * 1.27 + ri * 0.83)
        w = waves[ri]
        rr = R * (0.88 + 0.105 * w)
        px, py, z = pt(cos_lat * math.cos(lon) * rr, sin_lat * rr, cos_lat * math.sin(lon) * rr)
        depth = (z / R + 1) / 2
        dots.append((px, py, 0.66 - 0.56 * depth - 0.1 * max(0, w), 1.0))
    return dots, []


def _frame_web(size, t, o):
    R = size / 2 * 0.8 * o.get("spread", 1)
    pt = _proj(t * 0.12, 0.32, size / 2, size / 2, R)
    n, thr = o.get("nodeN", 30), o.get("thr", 0.72)
    nodes = []
    for i in range(n):
        d = _fib_dir(i, n)
        x = d[0] + 0.3 * (_vnoise(i * 0.31 + 9, t * 0.24) - 0.5) * 2
        y = d[1] + 0.3 * (_vnoise(i * 0.53 + 27, t * 0.21) - 0.5) * 2
        z = d[2] + 0.3 * (_vnoise(i * 0.77 + 55, t * 0.27) - 0.5) * 2
        ln = math.sqrt(x * x + y * y + z * z)
        nodes.append((x / ln, y / ln, z / ln))
    lines, dots = [], []
    for i in range(n):
        for j in range(i + 1, n):
            dist = math.dist(nodes[i], nodes[j])
            if dist >= thr:
                continue
            x1, y1, z1 = pt(*nodes[i])
            x2, y2, z2 = pt(*nodes[j])
            depth = ((z1 + z2) / 2 + 1) / 2
            lines.append((x1, y1, x2, y2, 0.42, (1 - dist / thr) * (0.3 + 0.55 * depth)))
    for node in nodes:
        px, py, z = pt(*node)
        dots.append((px, py, 0.55 - 0.45 * (z + 1) / 2, 1.0))
    for s in range(o.get("signals", 5)):
        seg = math.floor(t * 0.55 + s * 7.31)
        a = math.floor(_hash(seg, s * 3.1 + 1.7) * n)
        b = math.floor(_hash(seg, s * 5.7 + 4.2) * n)
        if a == b:
            continue
        f = _frac(t * 0.55 + s * 7.31)
        x, y, z = (_lerp(nodes[a][k], nodes[b][k], f) for k in range(3))
        ln = max(1e-6, math.sqrt(x * x + y * y + z * z))
        px, py, zr = pt(x / ln, y / ln, z / ln)
        dots.append((px, py, 0.05, 0.5 + 0.5 * (zr + 1) / 2))
    return dots, lines


def _frame_braid(size, t, o):
    R = size / 2 * 0.76
    pt = _proj(t * 0.4, 0.3, size / 2, size / 2, 1)
    dots = []
    _ghost_sphere(pt, R, o.get("ghostN", 150), dots)
    n, turns = o.get("strandN", 52), o.get("turns", 3)
    for s in range(3):
        phase = s / 3 * 2 * math.pi
        for i in range(n):
            u = (_frac(i / n + t * 0.045) * 2 - 1) * 0.96
            surf = math.sqrt(max(0, 1 - u * u))
            end_fade = min(1, (1 - abs(u)) / 0.1)
            a = u * math.pi * turns + phase
            weave = 1 + 0.075 * math.sin(u * math.pi * turns * 2 + phase * 2 + t * 0.8)
            rr = surf * R * weave
            px, py, zr = pt(math.cos(a) * rr, u * R * weave, math.sin(a) * rr)
            depth = (zr / R + 1) / 2
            dots.append((px, py, 0.55 - 0.45 * depth, end_fade * (0.45 + 0.55 * depth)))
    return dots, []


def _frame_ribbon(size, t, o):
    R = size / 2 * 0.78
    spin = o.get("spin", 1)
    cam_tilt = 0.3
    face_on = bool(o.get("faceOn"))
    pt = _proj(t * 0.1 * spin, cam_tilt, size / 2, size / 2, 1)
    dots = []
    _ghost_sphere(pt, R, o.get("ghostN", 150), dots)
    ya = t * 0.24 * spin
    ta = -cam_tilt if face_on else 0.55 + 0.3 * math.sin(t * 0.18) * spin
    ux, uy, uz = math.cos(ya), 0.0, math.sin(ya)
    vx, vy, vz = -uz * math.sin(ta), math.cos(ta), ux * math.sin(ta)
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    wob_mul = o.get("wobMul", 1)
    base_r = R / (1 + 0.85 * 0.23 * wob_mul) if face_on else R
    lanes = max(1, _round(o.get("lanes", 5) * o.get("bandMul", 1)))
    segs = o.get("segs", 88)
    for w in range(lanes):
        lane_off = (w - (lanes - 1) / 2) * 0.075
        edge = abs(w - (lanes - 1) / 2) / max(1, (lanes - 1) / 2)
        for k in range(segs):
            a = k / segs * 2 * math.pi
            wob = (0.16 * math.sin(a * 3 - t * 1.7 + w * 0.22) + 0.07 * math.sin(a * 5 + t * 1.1)) * wob_mul
            radial = 1 + wob if face_on else 1
            off = lane_off if face_on else lane_off + wob
            ca, sa = math.cos(a), math.sin(a)
            x, y, z = ux * ca + vx * sa + nx * off, uy * ca + vy * sa + ny * off, uz * ca + vz * sa + nz * off
            ln = math.sqrt(x * x + y * y + z * z)
            rr = base_r * radial
            px, py, zr = pt(x / ln * rr, y / ln * rr, z / ln * rr)
            depth = (zr / R + 1) / 2
            dots.append((px, py, 0.52 - 0.44 * depth + 0.18 * edge, 0.4 + 0.6 * depth))
    return dots, []


def _poly_path(verts):
    lengths = [math.dist(verts[i], verts[(i + 1) % len(verts)]) for i in range(len(verts))]
    total = sum(lengths)

    def at(f):
        target, i = f * total, 0
        while target > lengths[i] and i < len(verts) - 1:
            target -= lengths[i]
            i += 1
        a, b = verts[i], verts[(i + 1) % len(verts)]
        ff = min(1, target / lengths[i]) if lengths[i] else 0
        return a[0] + (b[0] - a[0]) * ff, a[1] + (b[1] - a[1]) * ff
    return at


def _circle(f):
    a = -math.pi / 2 + f * 2 * math.pi
    return math.cos(a) * 0.24, math.sin(a) * 0.24


_SHAPES = [_circle,
           _poly_path([(0, -0.26), (0.24, 0.16), (-0.24, 0.16)]),
           _poly_path([(0, -0.2), (0.2, -0.2), (0.2, 0.2), (-0.2, 0.2), (-0.2, -0.2)])]
_HOLD, _MORPH = 1.4, 0.9


def _frame_morph(size, t, o):
    seg_len = _HOLD + _MORPH
    tc = t % (seg_len * len(_SHAPES))
    k = math.floor(tc / seg_len)
    local = tc - k * seg_len
    m = 0.0
    if local > _HOLD:
        x = (local - _HOLD) / _MORPH
        m = x * x * (3 - 2 * x)
    spread = o.get("spread", 1)
    pa, pb = _SHAPES[k], _SHAPES[(k + 1) % len(_SHAPES)]
    M = 160
    pts = []
    for i in range(M):
        a, b = pa(i / M), pb(i / M)
        pts.append(((a[0] + (b[0] - a[0]) * m) * spread, (a[1] + (b[1] - a[1]) * m) * spread))
    lengths = [math.dist(pts[i], pts[(i + 1) % M]) for i in range(M)]
    total = sum(lengths)
    n = max(6, _round(34 * o.get("iconD", 1)))
    pulse = 1 + 0.02 * math.sin(local * 3.1)
    dots, seg, acc, c2 = [], 0, 0.0, size / 2
    for k2 in range(n):
        target = k2 / n * total
        while acc + lengths[seg] < target and seg < M - 1:
            acc += lengths[seg]
            seg += 1
        a, b = pts[seg], pts[(seg + 1) % M]
        f = min(1, (target - acc) / lengths[seg]) if lengths[seg] else 0
        x = (a[0] + (b[0] - a[0]) * f) * pulse
        y = (a[1] + (b[1] - a[1]) * f) * pulse
        dots.append((c2 + x * size, c2 + y * size, 0.1, 1.0))
    return dots, []


# ---------- states, profiles and the tuned 64px presets ----------

FRAMES: Dict[str, Callable] = {
    "orbits": _frame_orbits, "globe": _frame_globe, "rubik": _frame_rubik, "wave": _frame_wave,
    "web": _frame_web, "braid": _frame_braid, "ribbon": _frame_ribbon, "ring": _frame_ribbon,
    "morph": _frame_morph,
}
# The nine states, with what each one shows.
STATES = {
    "working": ("orbits", "particles on tilted orbits"),
    "searching": ("globe", "a scan line sweeps a dotted globe"),
    "solving": ("rubik", "bands scramble, then click back"),
    "listening": ("wave", "a wave rolls through the rings"),
    "connecting": ("web", "a constellation wires itself"),
    "weaving": ("braid", "three strands plait round the sphere"),
    "composing": ("ribbon", "an undulating band"),
    "breathing": ("ring", "a ring slowly morphing"),
    "shaping": ("morph", "circle, triangle, square"),
}
_BASE = {
    "globe": {"latRings": 17, "lonDensity": 44},
    "orbits": {"orbitN": 12, "ghostN": 40, "ghostA": 0.5, "particles": 3},
    "rubik": {"latRings": 15, "lonDensity": 40, "moveCount": 14},
    "wave": {"rings": 15, "lonDensity": 40},
    "web": {"nodeN": 30, "thr": 0.72, "signals": 5},
    "braid": {"strandN": 52, "turns": 3, "ghostN": 150},
    "ribbon": {"lanes": 5, "segs": 88, "ghostN": 150},
    "ring": {"lanes": 5, "segs": 88, "ghostN": 0, "faceOn": 1},
    "morph": {"iconD": 1},
}
# (speed, count) for the 64px design, plus any extra knobs.
_PRESET = {
    "orbits": (1.885, 1, {}),
    "globe": (2.015, 0.42, {"scanMul": 4.08, "dimBase": 0.45}),
    "rubik": (1.82, 0.35, {}),
    "wave": (4.388, 0.341, {}),
    "web": (3.315, 1.35, {}),
    "braid": (1.625, 0.5, {}),
    "ribbon": (2.34, 0.25, {"spin": 0, "bandMul": 3.9, "wobMul": 1}),
    "ring": (3.24, 0.25, {"spin": 0, "bandMul": 3.627, "wobMul": 0.368}),
    "morph": (2.405, 0.702, {"spread": 1.45}),
}
_COUNT_PAIRS = [("latRings", "lonDensity"), ("rings", "lonDensity"), ("lanes", "segs")]
_COUNT_KEYS = ["orbitN", "ghostN", "nodeN", "strandN", "signals"]


def _resolve(state: str):
    """(frame function, speed, options) for a state at the 64px design."""
    mode = STATES[state][0]
    speed, count, extra = _PRESET[mode]
    o = dict(_BASE[mode])
    if count != 1:
        rt, done = math.sqrt(count), set()
        for a, b in _COUNT_PAIRS:
            if a in o and b in o and not done & {a, b}:
                o[a], o[b] = max(2, _round(o[a] * rt)), max(2, _round(o[b] * rt))
                done |= {a, b}
        for k in _COUNT_KEYS:
            if o.get(k) and k not in done:
                o[k] = max(1, _round(o[k] * count))
        if "iconD" in o:
            o["iconD"] = max(0.02, o["iconD"] * count)
    o.update(extra)
    return FRAMES[mode], speed, o


# ---------- drawing with braille ----------

SIZE = 64
COLS, ROWS = 12, 6
THRESHOLD = 0.12
_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
_GREYS = (240, 245, 250, 255)  # 256-colour greys, far to near


def frame(state: str, seconds: float) -> Tuple[List[Dot], List[Line]]:
    fn, speed, o = _resolve(state)
    return fn(SIZE, seconds * speed, o)


def render(state: str, seconds: float, cols: int = COLS, rows: int = ROWS,
           color: bool = True) -> List[str]:
    """One frame of `state` as `rows` strings of `cols` braille characters
    (with 256-colour shading when `color`)."""
    dots, lines = frame(state, seconds)
    w, h = cols * 2, rows * 4
    level = [0.0] * (w * h)

    def plot(x, y, v):
        gx, gy = math.floor(x / SIZE * w), math.floor(y / SIZE * h)
        if 0 <= gx < w and 0 <= gy < h and v > level[gy * w + gx]:
            level[gy * w + gx] = v

    for x1, y1, x2, y2, white, a in lines:
        if a < 0.02:  # the original drops these before drawing
            continue
        steps = max(1, math.ceil(max(abs(x2 - x1) / SIZE * w, abs(y2 - y1) / SIZE * h)))
        v = max(THRESHOLD + 0.01, (1 - white) * a)
        for k in range(steps + 1):
            plot(_lerp(x1, x2, k / steps), _lerp(y1, y2, k / steps), v)
    for x, y, white, a in dots:
        if a >= 0.02:
            plot(x, y, (1 - min(1, max(0, white))) * a)
    out = []
    for r in range(rows):
        cells = []
        for c in range(cols):
            bits, best = 0, 0.0
            for dy in range(4):
                for dx in range(2):
                    v = level[(r * 4 + dy) * w + c * 2 + dx]
                    if v > THRESHOLD:
                        bits |= _BITS[dy][dx]
                        best = max(best, v)
            ch = chr(0x2800 + bits) if bits else " "
            if color and bits:
                ch = f"\033[38;5;{_GREYS[min(3, int(best * 4))]}m{ch}\033[0m"
            cells.append(ch)
        out.append("".join(cells))
    return out


# ---------- running in the terminal ----------

FPS = 20
DELAY = 0.3  # nothing is drawn before this, so quick answers don't flash


def run(state: str, caption: str = "", out=None, seconds: float = 0, color: bool = True) -> None:
    """Animate `state` until stopped (or for `seconds`), then erase it."""
    out = out or sys.stdout
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    drawn = False
    start = time.monotonic()
    try:
        time.sleep(DELAY)
        while not stop and (not seconds or time.monotonic() - start < seconds):
            art = render(state, time.monotonic() - start, color=color)
            buf = "\033[?25l" if not drawn else ""
            for i, line in enumerate(art):
                text = "  " + line + (f"   {caption}" if caption and i == ROWS // 2 else "")
                buf += text + "\033[K\n"
            buf += f"\033[{ROWS}A"
            out.write(buf)
            out.flush()
            drawn = True
            time.sleep(1 / FPS)
    except KeyboardInterrupt:
        pass
    finally:
        if drawn:
            out.write("\033[J\033[?25h")
            out.flush()


def demo(out=None, each: float = 3.5, color: bool = True) -> None:
    """All nine, one after another, with their names (`clishe orbs`)."""
    out = out or sys.stdout
    try:
        for state, (_, what) in STATES.items():
            run(state, f"{state}: {what}", out=out, seconds=each, color=color)
    except KeyboardInterrupt:
        pass


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="orbs.py")
    parser.add_argument("what", choices=["run", "demo"])
    parser.add_argument("--state", default="composing", choices=sorted(STATES))
    parser.add_argument("--caption", default="")
    parser.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args(argv)
    color = not os.environ.get("NO_COLOR")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if args.what == "demo":
        demo(color=color)
    else:
        run(args.state, args.caption, seconds=args.seconds, color=color)
    return 0


if __name__ == "__main__":
    sys.exit(main())
