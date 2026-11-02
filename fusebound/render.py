"""Draws an Arena (world layer + effects)."""
import math

import pygame

from . import art
from .config import T, GW, GH, CRATE, PILLAR, BREAK_TIME, FLAME_TIME, BOMB_TIME, ITEM_COLORS
from .world import center_of, NEIGH


class ArenaRenderer:
    def __init__(self, arena):
        self.arena = arena
        self.bg = art.arena_background(arena.world, arena.grid, seed=arena.stage * 31 + 7)
        self.layer = pygame.Surface((GW * T, GH * T))
        self.crate = art.crate_sprite(arena.world)
        self.pillar = art.pillar_sprite(arena.world)
        self.popups = []   # [x, y, text, life]

    def add_pillar(self, c):
        self.bg.blit(self.pillar, (c[0] * T, c[1] * T))

    def popup(self, x, y, text, font):
        self.popups.append([x, y, font.render(text, True, (255, 255, 255)), 1.0])

    def update(self, dt):
        for p in self.popups:
            p[1] -= 30 * dt
            p[3] -= dt
        self.popups = [p for p in self.popups if p[3] > 0]

    def draw(self, screen, top):
        a = self.arena
        L = self.layer
        L.blit(self.bg, (0, 0))
        t = a.time
        glows = []

        # crates (static and breaking)
        for y in range(1, GH - 1):
            row = a.grid[y]
            for x in range(1, GW - 1):
                if row[x] == CRATE:
                    c = (x, y)
                    if c in a.breaking:
                        k = a.breaking[c] / BREAK_TIME
                        size = int(T * (0.4 + 0.6 * k))
                        spr = pygame.transform.smoothscale(self.crate, (size, size))
                        spr.set_alpha(int(255 * k))
                        L.blit(spr, (x * T + (T - size) // 2, y * T + (T - size) // 2))
                        glows.append(((x * T + T // 2, y * T + T // 2), T * 0.6, (120, 60, 20)))
                    else:
                        L.blit(self.crate, (x * T, y * T))

        # exit portal
        if a.exit_revealed and a.exit_cell:
            art.portal_draw(L, center_of(a.exit_cell), t, a.portal_open, a.world["accent"])

        # items
        for c, kind in a.items.items():
            bob = math.sin(t * 4 + c[0]) * 3
            cx, cy = center_of(c)
            glows.append(((cx, cy), T * 0.55, art.shade(ITEM_COLORS[kind], 0.45)))
            L.blit(art.item_sprite(kind), (c[0] * T, c[1] * T + bob))

        # charges
        for b in a.bombs:
            urgent = (not b.remote) and b.timer < 0.7
            color = (255, 90, 200) if b.remote else ((255, 60, 60) if urgent and int(t * 16) % 2 else b.owner.color)
            frame = int(b.t * (16 if urgent else 8)) % 8
            L.blit(art.bomb_sprite(frame, color), (b.cell[0] * T, b.cell[1] * T))
            k = 0.35 + 0.35 * (1 - min(1, b.timer / BOMB_TIME)) if not b.remote else 0.4
            glows.append((center_of(b.cell), T * 0.7, art.shade(color, k)))
            # fuse spark
            sx, sy = center_of(b.cell)
            glows.append(((sx, sy - 18), 9 + 3 * math.sin(t * 30), (255, 220, 120)))

        # actors, sorted by y for overlap
        actors = []
        for p in a.players:
            if p.alive or p.dying < 1.0:
                actors.append((p.y, "p", p))
        for e in a.enemies:
            actors.append((e.y, "e", e))
        actors.sort(key=lambda it: it[0])
        for _, kind, obj in actors:
            if kind == "p":
                self._draw_player(L, obj, t, glows)
            else:
                self._draw_enemy(L, obj, glows)

        # falling sudden-death blocks
        if a.sudden:
            for c, left in a.sudden["falling"]:
                k = left / 0.35
                pygame.draw.ellipse(L, (0, 0, 0), (c[0] * T + 8, c[1] * T + 14, T - 16, T - 24), 0)
                L.blit(self.pillar, (c[0] * T, c[1] * T - int(k * T * 3)))

        # blasts
        for bl in a.blasts:
            self._draw_blast(L, bl, glows)

        # particles
        for pt in a.particles:
            k = pt.life / pt.max
            if pt.glow:
                glows.append(((pt.x, pt.y), pt.size * 3 * k + 2, art.shade(pt.color, k * 0.8)))
            else:
                pygame.draw.circle(L, pt.color, (pt.x, pt.y), max(1, pt.size * k))

        for pos, r, col in glows:
            art.blit_glow(L, pos, r, col)

        for x, y, surf, life in self.popups:
            surf.set_alpha(int(255 * min(1, life * 2)))
            L.blit(surf, (x - surf.get_width() // 2, y - surf.get_height() // 2))

        ox = oy = 0
        if a.shake > 0:
            ox = int(a.rnd.uniform(-a.shake, a.shake) * 0.5)
            oy = int(a.rnd.uniform(-a.shake, a.shake) * 0.5)
        screen.blit(L, (ox, top + oy))

    def _draw_player(self, L, p, t, glows):
        if not p.alive:
            spr = art.player_death_sprite(p.color, p.dying)
            L.blit(spr, (p.x - spr.get_width() / 2, p.y + T / 2 - spr.get_height() - 4))
            return
        frame = int(p.anim) % 4 if p.moving else 0
        flash = p.invuln > 0 and int(t * 20) % 2 == 0
        spr = art.player_sprite(p.color, p.facing, frame, flash)
        if p.ghost and p.cell is not None and self.arena.tile(p.cell) == CRATE:
            spr = spr.copy()
            spr.set_alpha(140)
        L.blit(spr, (p.x - T / 2, p.y - T / 2 - 6))
        if p.shield:
            r = T * 0.48 + math.sin(t * 6) * 2
            pygame.draw.circle(L, (255, 230, 120), (p.x, p.y - 6), r, 2)
            glows.append(((p.x, p.y - 6), T * 0.6, (60, 50, 20)))

    def _draw_enemy(self, L, e, glows):
        frame = int(e.anim) % 4
        spr = art.enemy_sprite(e.kind, frame, e.flash > 0 and int(e.flash * 20) % 2 == 0)
        if not e.alive:
            k = max(0.0, 1 - e.dying)
            size = max(2, int(T * (0.5 + k * 0.5)))
            spr = pygame.transform.smoothscale(spr, (size, size))
            spr.set_alpha(int(255 * k))
            L.blit(spr, (e.x - size / 2, e.y - size / 2))
            glows.append(((e.x, e.y), T * 0.8 * k + 2, (90, 90, 120)))
            return
        L.blit(spr, (e.x - T / 2, e.y - T / 2 - 4))
        if e.kind in ("wisp", "spark"):
            glows.append(((e.x, e.y), T * 0.5, (50, 40, 70) if e.kind == "wisp" else (70, 60, 10)))

    def _draw_blast(self, L, bl, glows):
        u = bl.t / FLAME_TIME
        grow = min(1.0, u * 7)
        k = (0.35 + 0.65 * grow) * (1 - u ** 3)
        cx, cy = center_of(bl.cell)
        layers = [((255, 110, 30), 0.86), ((255, 200, 70), 0.6), ((255, 250, 230), 0.32)]
        for col, wf in layers:
            w = max(2, int(T * wf * k))
            for v, n in bl.arms.items():
                if n <= 0:
                    continue
                length = n * T * grow + w / 2 * 0.6
                ex, ey = cx + v[0] * length, cy + v[1] * length
                rect = pygame.Rect(0, 0, 0, 0)
                rect.width = int(abs(ex - cx)) + w
                rect.height = int(abs(ey - cy)) + w
                rect.left = int(min(cx, ex) - w / 2)
                rect.top = int(min(cy, ey) - w / 2)
                pygame.draw.rect(L, col, rect, border_radius=w // 2)
            pygame.draw.circle(L, col, (cx, cy), w * 0.62)
        glows.append(((cx, cy), T * 1.1 * k + 2, (200, 100, 30)))
        for v, n in bl.arms.items():
            for i in range(1, n + 1):
                glows.append(((cx + v[0] * i * T, cy + v[1] * i * T), T * 0.7 * k + 2, (150, 70, 20)))
