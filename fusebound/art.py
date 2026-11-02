"""Procedural, anti-aliased art. Everything is drawn in code at 3x and smoothscaled."""
import math
import random

import pygame

from .config import T, GW, GH, PILLAR, CRATE, ITEM_COLORS

SS = 3  # supersampling factor
_cache = {}


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def supersample(w, h, fn):
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    fn(big, SS)
    return pygame.transform.smoothscale(big, (w, h))


def cached(key, maker):
    s = _cache.get(key)
    if s is None:
        s = maker()
        _cache[key] = s
    return s


# ------------------------------------------------------------------- glow
def glow(radius, color):
    """Radial gradient meant to be blitted with BLEND_RGB_ADD."""
    radius = max(2, int(radius))
    def make():
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        for i in range(radius, 0, -1):
            k = (1 - i / radius) ** 2
            pygame.draw.circle(s, shade(color, k), (radius, radius), i)
        return s
    return cached(("glow", radius, color), make)


def blit_glow(surf, pos, radius, color):
    radius = max(2, int(radius) // 3 * 3)
    color = tuple(min(255, (int(c) + 8) // 16 * 16) for c in color)
    if color == (0, 0, 0):
        return
    g = glow(radius, color)
    surf.blit(g, (pos[0] - g.get_width() // 2, pos[1] - g.get_height() // 2),
              special_flags=pygame.BLEND_RGB_ADD)


# ----------------------------------------------------------- environment
def arena_background(world, grid, seed=0):
    """Floor + pillars + their shadows, rendered once per level."""
    rnd = random.Random(seed)
    surf = pygame.Surface((GW * T, GH * T))
    surf.fill(world["bg"])
    f1, f2 = world["floor"], world["floor2"]
    for y in range(GH):
        for x in range(GW):
            r = pygame.Rect(x * T, y * T, T, T)
            base = f1 if (x + y) % 2 == 0 else f2
            base = shade(base, rnd.uniform(0.95, 1.05))
            pygame.draw.rect(surf, base, r)
            pygame.draw.rect(surf, shade(base, 0.82), r, 1)
            # little floor details
            if rnd.random() < 0.25:
                cx, cy = r.x + rnd.randint(8, T - 8), r.y + rnd.randint(8, T - 8)
                pygame.draw.circle(surf, shade(base, 0.88), (cx, cy), rnd.randint(1, 3))
            pygame.draw.line(surf, shade(base, 1.12), r.topleft, (r.right - 1, r.top))
    # shadows cast by pillars (down-right)
    shadow = pygame.Surface((GW * T, GH * T), pygame.SRCALPHA)
    for y in range(GH):
        for x in range(GW):
            if grid[y][x] == PILLAR:
                pygame.draw.rect(shadow, (0, 0, 0, 90),
                                 (x * T + 7, y * T + 9, T, T), border_radius=8)
    surf.blit(shadow, (0, 0))
    pil = pillar_sprite(world)
    for y in range(GH):
        for x in range(GW):
            if grid[y][x] == PILLAR:
                surf.blit(pil, (x * T, y * T))
    return surf


def pillar_sprite(world):
    def make():
        base, hi = world["pillar"], world["pillar_hi"]
        def draw(s, k):
            w = T * k
            pygame.draw.rect(s, shade(base, 0.6), (0, 0, w, w), border_radius=7 * k)
            pygame.draw.rect(s, base, (2 * k, 2 * k, w - 4 * k, w - 7 * k), border_radius=6 * k)
            top = pygame.Rect(7 * k, 6 * k, w - 14 * k, w - 18 * k)
            pygame.draw.rect(s, mix(base, hi, 0.35), top, border_radius=5 * k)
            pygame.draw.rect(s, mix(base, hi, 0.75), top, 2 * k, border_radius=5 * k)
            pygame.draw.line(s, hi, (5 * k, 4 * k), (w - 9 * k, 4 * k), 2 * k)
            # bolts
            for bx, by in ((12, 12), (T - 12, 12), (12, T - 18), (T - 12, T - 18)):
                pygame.draw.circle(s, shade(base, 0.7), (bx * k, by * k), 3 * k)
                pygame.draw.circle(s, hi, (bx * k - k, by * k - k), 1 * k)
        return supersample(T, T, draw)
    return cached(("pillar", world["name"]), make)


def crate_sprite(world):
    def make():
        base, hi = world["crate"], world["crate_hi"]
        def draw(s, k):
            w = T * k
            m = 4 * k
            pygame.draw.rect(s, (0, 0, 0, 80), (m + 4 * k, m + 6 * k, w - 2 * m, w - 2 * m),
                             border_radius=6 * k)
            body = pygame.Rect(m, m, w - 2 * m, w - 2 * m - 2 * k)
            pygame.draw.rect(s, shade(base, 0.7), body, border_radius=6 * k)
            inner = body.inflate(-8 * k, -8 * k)
            pygame.draw.rect(s, base, inner, border_radius=4 * k)
            # planks
            for i in range(1, 3):
                y = inner.top + inner.height * i // 3
                pygame.draw.line(s, shade(base, 0.75), (inner.left, y), (inner.right, y), 2 * k)
            # diagonal brace
            pygame.draw.line(s, mix(base, hi, 0.6), inner.topleft, inner.bottomright, 5 * k)
            pygame.draw.line(s, shade(base, 0.65), (inner.left, inner.top + 5 * k),
                             (inner.right - 5 * k, inner.bottom), 2 * k)
            pygame.draw.rect(s, hi, body, 2 * k, border_radius=6 * k)
            pygame.draw.line(s, mix(hi, (255, 255, 255), 0.4),
                             (body.left + 6 * k, body.top + 2 * k),
                             (body.right - 6 * k, body.top + 2 * k), 2 * k)
            for cx, cy in (body.topleft, body.topright, body.bottomleft, body.bottomright):
                cx += (6 if cx == body.left else -6) * k
                cy += (6 if cy == body.top else -6) * k
                pygame.draw.circle(s, hi, (cx, cy), 2 * k)
        return supersample(T, T, draw)
    return cached(("crate", world["name"]), make)


# ----------------------------------------------------------------- player
DIRS = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}


def player_sprite(color, facing, frame, flash=False):
    key = ("player", color, facing, frame, flash)
    def make():
        dx, dy = DIRS[facing]
        bob = [0, -2, 0, -2][frame]
        step = [0, 1, 0, -1][frame]
        body_c = (255, 255, 255) if flash else color
        def draw(s, k):
            cx = T / 2 * k
            base_y = (T - 8) * k
            # shadow
            pygame.draw.ellipse(s, (0, 0, 0, 90), (cx - 16 * k, base_y - 5 * k, 32 * k, 10 * k))
            # feet
            for side in (-1, 1):
                off = step * side * 3 if facing in ("down", "up") else 0
                fx = cx + side * 9 * k + (dx * 2 * k)
                fy = base_y - 4 * k - off * k
                if facing in ("left", "right"):
                    fx = cx + side * 6 * k + step * side * 3 * k
                    fy = base_y - 4 * k
                pygame.draw.ellipse(s, (40, 44, 60), (fx - 6 * k, fy - 4 * k, 12 * k, 8 * k))
            by = bob * k
            # body
            body = pygame.Rect(cx - 15 * k, 24 * k + by, 30 * k, 22 * k)
            pygame.draw.rect(s, shade(body_c, 0.55), body.move(0, 2 * k), border_radius=10 * k)
            pygame.draw.rect(s, body_c, body, border_radius=10 * k)
            pygame.draw.rect(s, shade(body_c, 1.25), (body.x + 5 * k, body.y + 3 * k,
                                                      body.w - 10 * k, 4 * k), border_radius=2 * k)
            # chest light
            if facing != "up":
                pygame.draw.circle(s, (255, 255, 255), (cx + dx * 6 * k, body.centery + 2 * k), 3 * k)
            # head
            hc = (cx, 18 * k + by)
            pygame.draw.circle(s, shade(body_c, 0.55), (hc[0], hc[1] + 2 * k), 15 * k)
            pygame.draw.circle(s, mix(body_c, (255, 255, 255), 0.25), hc, 15 * k)
            pygame.draw.circle(s, (255, 255, 255), (hc[0] - 6 * k, hc[1] - 7 * k), 3 * k)
            # visor and eyes
            if facing != "up":
                vx = hc[0] + dx * 5 * k
                visor = pygame.Rect(vx - 11 * k, hc[1] - 4 * k, 22 * k, 11 * k)
                pygame.draw.rect(s, (20, 24, 36), visor, border_radius=5 * k)
                for side in (-1, 1):
                    if facing in ("left", "right") and side == -dx:
                        continue
                    ex = vx + side * 5 * k + dx * 2 * k
                    pygame.draw.circle(s, (120, 255, 255), (ex, hc[1] + 1 * k), 3 * k)
                    pygame.draw.circle(s, (255, 255, 255), (ex, hc[1] + 1 * k), 1 * k)
            else:
                pygame.draw.rect(s, shade(body_c, 0.7), (hc[0] - 8 * k, hc[1] - 2 * k, 16 * k, 4 * k),
                                 border_radius=2 * k)
            # antenna
            ax = hc[0] - dx * 3 * k
            pygame.draw.line(s, (60, 64, 80), (ax, hc[1] - 13 * k), (ax + 3 * k, hc[1] - 21 * k), 2 * k)
            pygame.draw.circle(s, (255, 240, 120), (ax + 3 * k, hc[1] - 22 * k), 3 * k)
        return supersample(T, T, draw)
    return cached(key, make)


def player_death_sprite(color, t):
    """t in 0..1; the robot shrinks and fades as it collapses."""
    base = player_sprite(color, "down", 0, True)
    size = max(2, int(T * (1 - t * 0.7)))
    s = pygame.transform.smoothscale(base, (size, int(size * (1 - t * 0.4)) + 1))
    s.set_alpha(int(255 * (1 - t)))
    return s


# ---------------------------------------------------------------- enemies
def enemy_sprite(kind, frame, flash=False):
    key = ("enemy", kind, frame, flash)
    def make():
        ph = frame / 4 * 2 * math.pi
        def draw(s, k):
            cx, cy = T / 2 * k, T / 2 * k
            pygame.draw.ellipse(s, (0, 0, 0, 80), (cx - 16 * k, (T - 13) * k, 32 * k, 9 * k))
            if kind == "blob":
                c = (120, 230, 110) if not flash else (255, 255, 255)
                sq = math.sin(ph) * 3
                r = pygame.Rect(cx - (18 + sq) * k, cy - (12 - sq) * k, (36 + 2 * sq) * k, (30 - sq) * k)
                r.bottom = (T - 9) * k
                pygame.draw.ellipse(s, shade(c, 0.6), r.move(0, 2 * k))
                pygame.draw.ellipse(s, c, r)
                pygame.draw.ellipse(s, shade(c, 1.3), (r.x + 7 * k, r.y + 4 * k, 10 * k, 6 * k))
                for side in (-1, 1):
                    ex = cx + side * 7 * k
                    pygame.draw.circle(s, (255, 255, 255), (ex, r.centery), 5 * k)
                    pygame.draw.circle(s, (20, 30, 20), (ex + side * k, r.centery + k), 2.5 * k)
            elif kind == "spark":
                c = (255, 230, 80) if not flash else (255, 255, 255)
                pts = []
                for i in range(16):
                    a = i / 16 * 2 * math.pi + ph / 4
                    rr = (20 if i % 2 == 0 else 11) * k
                    pts.append((cx + math.cos(a) * rr, cy - 2 * k + math.sin(a) * rr))
                pygame.draw.polygon(s, shade(c, 0.7), pts)
                pygame.draw.circle(s, c, (cx, cy - 2 * k), 12 * k)
                pygame.draw.circle(s, (255, 255, 230), (cx, cy - 2 * k), 7 * k)
                for side in (-1, 1):
                    pygame.draw.line(s, (60, 40, 0), (cx + side * 6 * k, cy - 6 * k),
                                     (cx + side * 2 * k, cy - 3 * k), 2 * k)
                    pygame.draw.circle(s, (60, 40, 0), (cx + side * 4 * k, cy), 2 * k)
            elif kind == "hunter":
                c = (240, 70, 80) if not flash else (255, 255, 255)
                bob = math.sin(ph) * 2 * k
                pts = [(cx, cy - 20 * k + bob), (cx + 18 * k, cy + bob), (cx + 10 * k, cy + 14 * k + bob),
                       (cx - 10 * k, cy + 14 * k + bob), (cx - 18 * k, cy + bob)]
                pygame.draw.polygon(s, shade(c, 0.55), [(x, y + 3 * k) for x, y in pts])
                pygame.draw.polygon(s, c, pts)
                pygame.draw.polygon(s, shade(c, 1.3), pts, 2 * k)
                pygame.draw.circle(s, (30, 10, 14), (cx, cy + bob), 8 * k)
                pygame.draw.circle(s, (255, 220, 80), (cx, cy + bob), 5 * k)
                pygame.draw.circle(s, (255, 255, 255), (cx - 2 * k, cy - 2 * k + bob), 2 * k)
                # thrusters
                for side in (-1, 1):
                    pygame.draw.circle(s, (255, 160, 60), (cx + side * 8 * k, cy + 17 * k + bob),
                                       (3 + (frame % 2)) * k)
            elif kind == "wisp":
                c = (180, 150, 255) if not flash else (255, 255, 255)
                wob = math.sin(ph) * 3 * k
                body = pygame.Surface(s.get_size(), pygame.SRCALPHA)
                pygame.draw.circle(body, (*c, 190), (cx, cy - 4 * k + wob), 16 * k)
                pygame.draw.rect(body, (*c, 190), (cx - 16 * k, cy - 4 * k + wob, 32 * k, 16 * k))
                for i in range(4):
                    off = math.sin(ph + i) * 3 * k
                    pygame.draw.circle(body, (*c, 190), (cx - 12 * k + i * 8 * k, cy + 12 * k + wob + off), 5 * k)
                s.blit(body, (0, 0))
                for side in (-1, 1):
                    pygame.draw.ellipse(s, (40, 20, 70), (cx + side * 7 * k - 3 * k, cy - 9 * k + wob, 6 * k, 9 * k))
            elif kind == "brute":
                c = (150, 160, 180) if not flash else (255, 255, 255)
                stomp = abs(math.sin(ph)) * 2 * k
                r = pygame.Rect(cx - 19 * k, cy - 16 * k - stomp, 38 * k, 32 * k)
                pygame.draw.rect(s, shade(c, 0.5), r.move(0, 3 * k), border_radius=6 * k)
                pygame.draw.rect(s, c, r, border_radius=6 * k)
                pygame.draw.rect(s, shade(c, 0.75), r.inflate(-10 * k, -10 * k), border_radius=4 * k)
                pygame.draw.rect(s, (30, 30, 40), (r.x + 7 * k, r.y + 9 * k, r.w - 14 * k, 8 * k),
                                 border_radius=3 * k)
                pygame.draw.circle(s, (255, 120, 40), (r.x + 13 * k, r.y + 13 * k), 3 * k)
                pygame.draw.circle(s, (255, 120, 40), (r.right - 13 * k, r.y + 13 * k), 3 * k)
                for side in (-1, 1):
                    pygame.draw.rect(s, shade(c, 0.6), (cx + side * 22 * k - 5 * k, cy - 6 * k - stomp,
                                                        10 * k, 16 * k), border_radius=4 * k)
        return supersample(T, T, draw)
    return cached(key, make)


# ------------------------------------------------------------------- bomb
def bomb_sprite(frame, color=(255, 120, 60)):
    key = ("bomb", frame, color)
    def make():
        pulse = 1 + 0.07 * math.sin(frame / 8 * 2 * math.pi)
        def draw(s, k):
            cx, cy = T / 2 * k, T / 2 * k + 3 * k
            r = 17 * pulse * k
            pygame.draw.ellipse(s, (0, 0, 0, 90), (cx - 16 * k, cy + 12 * k, 32 * k, 9 * k))
            pygame.draw.circle(s, (18, 20, 30), (cx, cy), r)
            pygame.draw.circle(s, (45, 50, 70), (cx - 3 * k, cy - 3 * k), r * 0.8)
            pygame.draw.circle(s, (18, 20, 30), (cx, cy), r, int(2 * k))
            # glowing core ring
            pygame.draw.circle(s, color, (cx, cy), r * 0.45)
            pygame.draw.circle(s, mix(color, (255, 255, 255), 0.6), (cx, cy), r * 0.25)
            pygame.draw.circle(s, (220, 230, 255), (cx - 7 * k, cy - 8 * k), 3 * k)
            # fuse cap
            pygame.draw.rect(s, (90, 96, 120), (cx - 5 * k, cy - r - 4 * k, 10 * k, 7 * k), border_radius=2 * k)
        return supersample(T, T, draw)
    return cached(key, make)


# ------------------------------------------------------------------ items
def item_sprite(kind):
    def make():
        c = ITEM_COLORS[kind]
        def draw(s, k):
            m = 7 * k
            box = pygame.Rect(m, m, T * k - 2 * m, T * k - 2 * m)
            pygame.draw.rect(s, (0, 0, 0, 100), box.move(3 * k, 4 * k), border_radius=9 * k)
            pygame.draw.rect(s, (24, 26, 38), box, border_radius=9 * k)
            pygame.draw.rect(s, c, box, 3 * k, border_radius=9 * k)
            cx, cy = box.center
            if kind == "bomb":
                pygame.draw.circle(s, (230, 235, 255), (cx, cy + 2 * k), 11 * k)
                pygame.draw.circle(s, c, (cx, cy + 2 * k), 5 * k)
                pygame.draw.rect(s, (230, 235, 255), (cx - 3 * k, cy - 13 * k, 6 * k, 6 * k))
            elif kind == "fire":
                pts = [(cx, cy - 14 * k), (cx + 10 * k, cy), (cx + 8 * k, cy + 10 * k),
                       (cx, cy + 13 * k), (cx - 8 * k, cy + 10 * k), (cx - 10 * k, cy)]
                pygame.draw.polygon(s, c, pts)
                pygame.draw.polygon(s, (255, 230, 120), [(cx, cy - 4 * k), (cx + 5 * k, cy + 5 * k),
                                                         (cx, cy + 10 * k), (cx - 5 * k, cy + 5 * k)])
            elif kind == "speed":
                for i in range(2):
                    ox = (i * 9 - 6) * k
                    pygame.draw.lines(s, c, False, [(cx + ox - 5 * k, cy - 10 * k), (cx + ox + 5 * k, cy),
                                                    (cx + ox - 5 * k, cy + 10 * k)], 5 * k)
            elif kind == "remote":
                pygame.draw.rect(s, (230, 235, 255), (cx - 7 * k, cy - 2 * k, 14 * k, 15 * k), border_radius=3 * k)
                pygame.draw.circle(s, c, (cx, cy + 5 * k), 3 * k)
                for i in range(1, 3):
                    pygame.draw.arc(s, c, (cx - 6 * k * i, cy - 6 * k - 6 * k * i, 12 * k * i, 12 * k * i),
                                    math.radians(45), math.radians(135), 3 * k)
            elif kind == "ghost":
                pygame.draw.circle(s, c, (cx, cy - 3 * k), 10 * k)
                pygame.draw.rect(s, c, (cx - 10 * k, cy - 3 * k, 20 * k, 12 * k))
                for i in range(3):
                    pygame.draw.circle(s, c, (cx - 7 * k + i * 7 * k, cy + 9 * k), 4 * k)
                for side in (-1, 1):
                    pygame.draw.circle(s, (24, 26, 38), (cx + side * 4 * k, cy - 4 * k), 2.5 * k)
            elif kind == "shield":
                pts = [(cx, cy - 14 * k), (cx + 12 * k, cy - 8 * k), (cx + 10 * k, cy + 5 * k),
                       (cx, cy + 14 * k), (cx - 10 * k, cy + 5 * k), (cx - 12 * k, cy - 8 * k)]
                pygame.draw.polygon(s, c, pts)
                pygame.draw.polygon(s, (255, 250, 210), [(cx, cy - 8 * k), (cx + 6 * k, cy - 4 * k),
                                                         (cx, cy + 8 * k), (cx - 6 * k, cy - 4 * k)])
        return supersample(T, T, draw)
    return cached(("item", kind), make)


def portal_draw(surf, center, t, active, accent):
    """Animated exit portal, drawn every frame."""
    cx, cy = center
    col = accent if active else (110, 110, 130)
    blit_glow(surf, center, T * (0.75 if active else 0.45), shade(col, 0.6))
    pygame.draw.ellipse(surf, (8, 8, 14), (cx - 20, cy - 14, 40, 28))
    for i in range(3):
        a = t * (3 if active else 1) + i * 2.1
        rx = 20 - i * 5
        ry = 14 - i * 3.5
        rect = pygame.Rect(0, 0, rx * 2, ry * 2)
        rect.center = (cx, cy)
        pygame.draw.arc(surf, mix(col, (255, 255, 255), i * 0.3), rect, a, a + 3.6, 3)
