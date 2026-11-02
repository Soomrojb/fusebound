"""Menus, campaign and versus scenes."""
import json
import math
import os
import random
import webbrowser

import pygame

from . import art
from .ai import Bot
from .config import (T, GW, GH, HUD, SW, SH, WORLDS, STAGES_PER_WORLD, TOTAL_STAGES,
                     PLAYER_COLORS, PLAYER_NAMES, ITEM_COLORS, ITEM_NAMES, SAVE_DIR, SAVE_FILE,
                     AUTHOR, AUTHOR_GITHUB, AUTHOR_SITE, REPO_URL, VERSION)
from .controls import KB1, KB2, KB_ALL, KeyController, PadController, MultiController
from .render import ArenaRenderer
from .world import Arena


# ---------------------------------------------------------------- helpers
def load_save():
    try:
        with open(SAVE_FILE) as f:
            d = json.load(f)
        return {"unlocked": int(d.get("unlocked", 0)), "best": int(d.get("best", 0))}
    except Exception:
        return {"unlocked": 0, "best": 0}


def write_save(data):
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
    except OSError as exc:
        print("Could not save progress:", exc)


def stage_label(s):
    return f"{s // STAGES_PER_WORLD + 1}-{s % STAGES_PER_WORLD + 1}"


def nav_action(e):
    """Map keyboard / pad events to menu actions."""
    if e.type == pygame.KEYDOWN:
        return {pygame.K_UP: "up", pygame.K_w: "up", pygame.K_DOWN: "down", pygame.K_s: "down",
                pygame.K_LEFT: "left", pygame.K_a: "left", pygame.K_RIGHT: "right", pygame.K_d: "right",
                pygame.K_RETURN: "ok", pygame.K_SPACE: "ok", pygame.K_KP_ENTER: "ok",
                pygame.K_ESCAPE: "back", pygame.K_BACKSPACE: "back"}.get(e.key)
    if e.type == pygame.JOYHATMOTION:
        x, y = e.value
        return "up" if y > 0 else "down" if y < 0 else "left" if x < 0 else "right" if x > 0 else None
    if e.type == pygame.JOYBUTTONDOWN:
        return {0: "ok", 1: "back", 7: "back", 6: "back"}.get(e.button)
    return None


def text(surf, font, s, pos, color=(255, 255, 255), anchor="center", shadow=True):
    img = font.render(s, True, color)
    r = img.get_rect(**{anchor: pos})
    if shadow:
        sh = font.render(s, True, (0, 0, 0))
        sh.set_alpha(150)
        surf.blit(sh, r.move(2, 3))
    surf.blit(img, r)
    return r


def glow_text(surf, font, s, pos, color):
    img = font.render(s, True, color)
    r = img.get_rect(center=pos)
    flat = pygame.Surface(img.get_size())
    flat.fill((0, 0, 0))
    flat.blit(img, (0, 0))
    blur = pygame.transform.smoothscale(flat, (max(1, r.w // 6), max(1, r.h // 6)))
    blur = pygame.transform.smoothscale(blur, (r.w + 24, r.h + 24))
    blur.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_MULT)
    surf.blit(blur, r.move(-12, -12), special_flags=pygame.BLEND_RGB_ADD)
    text(surf, font, s, pos, color)


class Backdrop:
    """Animated menu background: drifting floor grid with glowing charges."""
    def __init__(self):
        self.t = 0.0
        self.rnd = random.Random(1)
        self.orbs = [[self.rnd.uniform(0, SW), self.rnd.uniform(0, SH), self.rnd.uniform(-20, 20),
                      self.rnd.uniform(-30, -10), self.rnd.choice(PLAYER_COLORS + [(255, 140, 60)]),
                      self.rnd.uniform(0, 8)] for _ in range(14)]

    def update(self, dt):
        self.t += dt
        for o in self.orbs:
            o[0] += o[2] * dt
            o[1] += o[3] * dt
            o[5] += dt * 8
            if o[1] < -40:
                o[1] = SH + 40
                o[0] = self.rnd.uniform(0, SW)

    def draw(self, surf):
        surf.fill((10, 12, 20))
        ox = int(self.t * 18) % T
        oy = ox // 2
        for y in range(-1, SH // T + 2):
            for x in range(-1, SW // T + 2):
                c = (22, 26, 40) if (x + y) % 2 else (26, 30, 46)
                pygame.draw.rect(surf, c, (x * T - ox, y * T + oy - T // 2, T, T))
        for o in self.orbs:
            spr = art.bomb_sprite(int(o[5]) % 8, o[4])
            surf.blit(spr, (o[0] - T / 2, o[1] - T / 2))
            art.blit_glow(surf, (o[0], o[1] + 3), T * 0.7, art.shade(o[4], 0.4))
        vign = art.cached(("vignette",), self._vignette)
        surf.blit(vign, (0, 0))

    def _vignette(self):
        s = pygame.Surface((SW, SH), pygame.SRCALPHA)
        for i in range(40):
            a = int(140 * (i / 40) ** 2)
            pygame.draw.rect(s, (0, 0, 0, a), (40 - i, 40 - i, SW - 2 * (40 - i), SH - 2 * (40 - i)), 3)
        return s


class Scene:
    def __init__(self, game):
        self.game = game

    def event(self, e): pass
    def update(self, dt): pass
    def draw(self, surf): pass


# ------------------------------------------------------------------- menus
class MenuScene(Scene):
    title = ""
    def __init__(self, game, items):
        super().__init__(game)
        self.items = items     # list of (label_fn_or_str, callback, lr_callback)
        self.sel = 0
        self.backdrop = game.backdrop

    def label(self, i):
        lab = self.items[i][0]
        return lab() if callable(lab) else lab

    def event(self, e):
        a = nav_action(e)
        if a == "up":
            self.sel = (self.sel - 1) % len(self.items); self.game.audio.play("menu")
        elif a == "down":
            self.sel = (self.sel + 1) % len(self.items); self.game.audio.play("menu")
        elif a in ("left", "right") and len(self.items[self.sel]) > 2 and self.items[self.sel][2]:
            self.items[self.sel][2](-1 if a == "left" else 1); self.game.audio.play("menu")
        elif a == "ok":
            self.game.audio.play("select")
            self.items[self.sel][1]()
        elif a == "back":
            self.back()

    def back(self):
        pass

    def update(self, dt):
        self.backdrop.update(dt)

    def draw_items(self, surf, y0):
        f = self.game.fonts
        for i in range(len(self.items)):
            sel = i == self.sel
            col = (255, 230, 120) if sel else (190, 200, 220)
            y = y0 + i * 52
            if sel:
                w = f["md"].size(self.label(i))[0] + 60
                pill = pygame.Surface((w, 42), pygame.SRCALPHA)
                pygame.draw.rect(pill, (255, 255, 255, 28), pill.get_rect(), border_radius=21)
                pygame.draw.rect(pill, (255, 230, 120, 120), pill.get_rect(), 2, border_radius=21)
                surf.blit(pill, (SW // 2 - w // 2, y - 21))
                spr = art.bomb_sprite(int(self.backdrop.t * 8) % 8, (255, 140, 60))
                surf.blit(pygame.transform.smoothscale(spr, (36, 36)), (SW // 2 - w // 2 - 40, y - 20))
            text(surf, f["md"], self.label(i), (SW // 2, y), col)


class TitleScene(MenuScene):
    def __init__(self, game):
        items = [
            ("Campaign", lambda: game.set_scene(CampaignSelect(game))),
            ("Versus Battle", lambda: game.set_scene(VersusSetup(game))),
            ("How to Play", lambda: game.set_scene(HelpScene(game))),
            ("Credits", lambda: game.set_scene(CreditsScene(game))),
            (lambda: "Fullscreen: " + ("On" if game.fullscreen else "Off"), game.toggle_fullscreen),
            ("Quit", game.quit),
        ]
        super().__init__(game, items)
        game.audio.play_music("menu")

    def back(self):
        self.game.quit()

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        bob = math.sin(self.backdrop.t * 2) * 6
        glow_text(surf, f["title"], "FUSEBOUND", (SW // 2, 180 + bob), (255, 190, 90))
        text(surf, f["sm"], "a grid arena of charges, crates and chain reactions", (SW // 2, 250),
             (170, 190, 220))
        self.draw_items(surf, 330)
        best = self.game.save["best"]
        text(surf, f["xs"], f"Best score {best}    ·    F11 fullscreen    ·    Esc back",
             (SW // 2, SH - 48), (120, 130, 160))
        text(surf, f["xs"], f"v{VERSION}  ·  © 2026 {AUTHOR}  ·  ormoos.com",
             (SW // 2, SH - 24), (150, 160, 190))


class CampaignSelect(MenuScene):
    def __init__(self, game):
        self.stage = min(game.save["unlocked"], TOTAL_STAGES - 1)
        items = [
            (lambda: f"Stage  <  {stage_label(self.stage)}  >", self.start, self.change),
            ("Back", lambda: game.set_scene(TitleScene(game))),
        ]
        super().__init__(game, items)

    def change(self, d):
        self.stage = max(0, min(min(self.game.save["unlocked"], TOTAL_STAGES - 1), self.stage + d))

    def start(self):
        self.game.set_scene(CampaignScene(self.game, self.stage))

    def back(self):
        self.game.set_scene(TitleScene(self.game))

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        glow_text(surf, f["lg"], "CAMPAIGN", (SW // 2, 140), (120, 220, 255))
        w = WORLDS[self.stage // STAGES_PER_WORLD]
        text(surf, f["md"], w["name"], (SW // 2, 230), w["accent"])
        text(surf, f["sm"], "Clear every enemy, then find the hidden portal under a crate.",
             (SW // 2, 280), (190, 200, 220))
        # stage dots
        for s in range(TOTAL_STAGES):
            x = SW // 2 - (TOTAL_STAGES * 26) // 2 + s * 26 + 13
            unlocked = s <= self.game.save["unlocked"]
            col = WORLDS[s // STAGES_PER_WORLD]["accent"] if unlocked else (60, 64, 80)
            pygame.draw.circle(surf, col, (x, 330), 9 if s == self.stage else 6)
        self.draw_items(surf, 420)
        text(surf, f["xs"], "Left / Right to choose any stage you have reached",
             (SW // 2, SH - 30), (120, 130, 160))


SLOT_TYPES = ["Keys: WASD", "Keys: Arrows", "Gamepad 1", "Gamepad 2", "Bot (easy)", "Bot (hard)", "Off"]


class VersusSetup(MenuScene):
    def __init__(self, game):
        self.slots = getattr(game, "versus_slots", [0, 1, 5, 4])
        self.wins = getattr(game, "versus_wins", 3)
        self.arena_idx = getattr(game, "versus_arena", 0)
        items = []
        for i in range(4):
            items.append((lambda i=i: f"{PLAYER_NAMES[i]}:  {SLOT_TYPES[self.slots[i]]}",
                          lambda i=i: self.cycle(i, 1), lambda d, i=i: self.cycle(i, d)))
        items.append((lambda: f"Wins to take the match:  {self.wins}", lambda: self.set_wins(1), self.set_wins))
        items.append((lambda: f"Arena:  {WORLDS[self.arena_idx]['name']}", lambda: self.set_arena(1), self.set_arena))
        items.append(("Start Battle", self.start))
        items.append(("Back", self.back))
        super().__init__(game, items)
        self.msg = ""

    def cycle(self, i, d):
        self.slots[i] = (self.slots[i] + d) % len(SLOT_TYPES)

    def set_wins(self, d):
        self.wins = max(1, min(9, self.wins + d))

    def set_arena(self, d):
        self.arena_idx = (self.arena_idx + d) % len(WORLDS)

    def start(self):
        active = [s for s in self.slots if SLOT_TYPES[s] != "Off"]
        if len(active) < 2:
            self.msg = "Need at least two fighters."
            return
        humans = [s for s in self.slots if s <= 3]
        if len(humans) != len(set(humans)):
            self.msg = "Each keyboard half / gamepad can only control one fighter."
            return
        self.game.versus_slots, self.game.versus_wins, self.game.versus_arena = self.slots, self.wins, self.arena_idx
        self.game.set_scene(VersusScene(self.game, list(self.slots), self.wins, self.arena_idx))

    def back(self):
        self.game.set_scene(TitleScene(self.game))

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        glow_text(surf, f["lg"], "VERSUS", (SW // 2, 100), (255, 130, 110))
        for i in range(4):
            spr = art.player_sprite(PLAYER_COLORS[i], "down", 0)
            if SLOT_TYPES[self.slots[i]] == "Off":
                spr = spr.copy(); spr.set_alpha(60)
            surf.blit(spr, (130, 190 + i * 52 - T // 2 - 4))
        self.draw_items(surf, 190)
        if self.msg:
            text(surf, f["sm"], self.msg, (SW // 2, SH - 60), (255, 120, 120))
        text(surf, f["xs"], f"Gamepads detected: {pygame.joystick.get_count()}    ·    Left/Right to change",
             (SW // 2, SH - 30), (120, 130, 160))


def open_url(url):
    try:
        webbrowser.open(url)
    except Exception as exc:
        print("Could not open browser:", exc)


class CreditsScene(MenuScene):
    def __init__(self, game):
        super().__init__(game, [
            ("Visit ormoos.com", lambda: open_url(AUTHOR_SITE)),
            ("GitHub: soomrojb", lambda: open_url(AUTHOR_GITHUB)),
            ("Back", lambda: game.set_scene(TitleScene(game))),
        ])

    def back(self):
        self.game.set_scene(TitleScene(self.game))

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        glow_text(surf, f["lg"], "CREDITS", (SW // 2, 90), (255, 200, 110))
        text(surf, f["sm"], "Created by", (SW // 2, 170), (170, 180, 210))
        glow_text(surf, f["lg"], AUTHOR, (SW // 2, 220), (120, 220, 255))
        text(surf, f["sm"], "Design · Code · Art · Sound", (SW // 2, 275), (200, 210, 230))
        text(surf, f["sm"], AUTHOR_SITE.replace("https://", ""), (SW // 2, 320), (255, 230, 120))
        text(surf, f["sm"], AUTHOR_GITHUB.replace("https://", ""), (SW // 2, 352), (255, 230, 120))
        # cast of characters
        for i in range(4):
            spr = art.player_sprite(PLAYER_COLORS[i], "down", int(self.backdrop.t * 6 + i) % 4)
            surf.blit(spr, (SW // 2 - 2 * 70 + i * 70 + 7, 385))
        self.draw_items(surf, 500)
        text(surf, f["xs"], f"Fusebound v{VERSION}  ·  MIT License  ·  {REPO_URL.replace('https://', '')}",
             (SW // 2, SH - 30), (120, 130, 160))


class HelpScene(MenuScene):
    def __init__(self, game):
        super().__init__(game, [("Back", lambda: game.set_scene(TitleScene(game)))])

    def back(self):
        self.game.set_scene(TitleScene(self.game))

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        glow_text(surf, f["lg"], "HOW TO PLAY", (SW // 2, 70), (150, 255, 170))
        lines = [
            ("Player 1", "WASD move · Space drop · L-Shift / E trigger"),
            ("Player 2", "Arrows move · R-Ctrl / Enter drop · R-Shift trigger"),
            ("Gamepad", "D-pad / stick move · A drop · B trigger"),
            ("Campaign", "Either keyboard layout works. Esc pauses."),
        ]
        y = 140
        for a, b in lines:
            text(surf, f["sm"], a, (70, y), (255, 220, 120), "midleft")
            text(surf, f["sm"], b, (210, y), (210, 220, 240), "midleft")
            y += 36
        y += 16
        for kind in ITEM_COLORS:
            surf.blit(pygame.transform.smoothscale(art.item_sprite(kind), (44, 44)), (110, y - 22))
            desc = {"bomb": "carry one more charge at a time", "fire": "blasts reach one tile further",
                    "speed": "move faster", "remote": "charges wait until you trigger them",
                    "ghost": "walk through crates", "shield": "survive one hit"}[kind]
            text(surf, f["sm"], f"{ITEM_NAMES[kind]} — {desc}", (170, y), (210, 220, 240), "midleft")
            y += 50
        text(surf, f["xs"], f"Fusebound by {AUTHOR}  ·  ormoos.com  ·  github.com/soomrojb",
             (SW // 2, SH - 105), (150, 160, 190))
        self.draw_items(surf, SH - 50)


# ------------------------------------------------------------------- HUD
def draw_stat_icons(surf, font, p, x, y, size=28):
    icons = [("bomb", str(p.max_bombs)), ("fire", str(p.fire)), ("speed", str(p.speed_lv + 1))]
    for kind, val in icons:
        surf.blit(art.cached(("icon", kind, size),
                             lambda: pygame.transform.smoothscale(art.item_sprite(kind), (size, size))),
                  (x, y - size // 2))
        text(surf, font, val, (x + size, y), (230, 235, 250), "midleft")
        x += size + (20 if size > 20 else 13)
    for kind, flag in (("remote", p.remote), ("ghost", p.ghost), ("shield", p.shield)):
        if flag:
            surf.blit(art.cached(("icon", kind, size),
                                 lambda: pygame.transform.smoothscale(art.item_sprite(kind), (size, size))),
                      (x, y - size // 2))
            x += size + 2
    return x


def hud_panel(surf):
    bar = art.cached(("hudbar",), lambda: _make_hud())
    surf.blit(bar, (0, 0))


def _make_hud():
    s = pygame.Surface((SW, HUD))
    for y in range(HUD):
        k = y / HUD
        pygame.draw.line(s, (int(20 + 10 * k), int(22 + 10 * k), int(34 + 14 * k)), (0, y), (SW, y))
    pygame.draw.line(s, (90, 100, 140), (0, HUD - 2), (SW, HUD - 2), 2)
    return s


class Overlay:
    """Pause menu shared by both game scenes."""
    def __init__(self, game, on_quit):
        self.game = game
        self.sel = 0
        self.on_quit = on_quit
        self.items = ["Resume", "Quit to Menu"]

    def event(self, e):
        a = nav_action(e)
        if a in ("up", "down"):
            self.sel = 1 - self.sel
            self.game.audio.play("menu")
        elif a == "ok":
            return "resume" if self.sel == 0 else self.on_quit()
        elif a == "back":
            return "resume"

    def draw(self, surf):
        dim = pygame.Surface((SW, SH), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surf.blit(dim, (0, 0))
        f = self.game.fonts
        glow_text(surf, f["lg"], "PAUSED", (SW // 2, SH // 2 - 80), (200, 220, 255))
        for i, it in enumerate(self.items):
            text(surf, f["md"], it, (SW // 2, SH // 2 + i * 50),
                 (255, 230, 120) if i == self.sel else (190, 200, 220))


def banner(surf, game, big, small, t, color):
    f = game.fonts
    k = min(1.0, t * 3)
    h = int(130 * k)
    band = pygame.Surface((SW, h), pygame.SRCALPHA)
    band.fill((0, 0, 0, 170))
    surf.blit(band, (0, SH // 2 - h // 2))
    if k >= 1:
        glow_text(surf, f["lg"], big, (SW // 2, SH // 2 - 18), color)
        if small:
            text(surf, f["sm"], small, (SW // 2, SH // 2 + 34), (220, 225, 240))


# --------------------------------------------------------------- campaign
class CampaignScene(Scene):
    def __init__(self, game, stage, score=0, lives=3, carry=None):
        super().__init__(game)
        self.stage = stage
        self.score = score
        self.lives = lives
        self.ctrl = MultiController([KeyController(KB_ALL, "keys"), PadController(0, "pad")], "P1")
        self.carry = carry
        self.paused = None
        self._new_arena()
        game.audio.play_music("battle")

    def _new_arena(self):
        self.arena = Arena("campaign", self.stage, [(self.ctrl, PLAYER_COLORS[0], PLAYER_NAMES[0])],
                           seed=random.randrange(1 << 30), audio=self.game.audio)
        p = self.arena.players[0]
        if self.carry:
            for k, v in self.carry.items():
                setattr(p, k, v)
        p.invuln = 2.0
        self.renderer = ArenaRenderer(self.arena)
        self.phase = "intro"
        self.pt = 0.0
        self.time_left = 200.0
        self.bonus = 0

    def event(self, e):
        if self.paused:
            r = self.paused.event(e)
            if r == "resume":
                self.paused = None
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE or \
                e.type == pygame.JOYBUTTONDOWN and e.button == 7:
            self.paused = Overlay(self.game, self._quit)
            return
        self.ctrl.event(e)

    def _quit(self):
        self.game.set_scene(TitleScene(self.game))

    def _carry_stats(self, p):
        return {k: getattr(p, k) for k in ("max_bombs", "fire", "speed_lv", "remote", "ghost", "shield")}

    def update(self, dt):
        if self.paused:
            return
        a = self.arena
        self.pt += dt
        p = a.players[0]
        if self.phase == "intro":
            inp = [(None, False, False)]
            self.ctrl.poll()
            a.update(dt, inp)
            if self.pt > 1.8:
                self.phase = "play"
        elif self.phase == "play":
            a.update(dt, [self.ctrl.poll()])
            self.time_left -= dt
            if self.time_left <= 0 and p.alive:
                p.shield = False
                a.hurt_player(p, None)
            if not p.alive:
                self.phase, self.pt = "dead", 0.0
            elif a.player_on_open_exit(p):
                self.phase, self.pt = "clear", 0.0
                self.bonus = int(self.time_left) * 10
                self.game.audio.play("clear")
        else:
            self.ctrl.poll()
            a.update(dt, [(None, False, False)])
            if self.phase == "dead" and self.pt > 2.2:
                self.lives -= 1
                if self.lives < 0:
                    self._record()
                    self.game.set_scene(ResultScene(self.game, "GAME OVER", f"Score {self.score}",
                                                    (255, 110, 100)))
                    return
                self.carry = None
                self._new_arena()
            elif self.phase == "clear" and self.pt > 2.8:
                self.score += self.bonus
                nxt = self.stage + 1
                self.game.save["unlocked"] = max(self.game.save["unlocked"], min(nxt, TOTAL_STAGES - 1))
                self._record()
                if nxt >= TOTAL_STAGES:
                    self.game.set_scene(ResultScene(self.game, "ALL WORLDS CLEARED!",
                                                    f"Final score {self.score}", (255, 220, 120), win=True))
                    return
                self.game.set_scene(CampaignScene(self.game, nxt, self.score, self.lives,
                                                  self._carry_stats(p)))
                return

        if a.score_gain:
            self.score += a.score_gain
            a.score_gain = 0
        for kind, payload in a.events:
            if kind == "score":
                x, y, pts = payload
                self.renderer.popup(x, y, str(pts), self.game.fonts["sm"])
            elif kind == "item":
                _, it = payload
                self.renderer.popup(p.x, p.y - 30, ITEM_NAMES[it], self.game.fonts["xs"])
            elif kind == "pillar":
                self.renderer.add_pillar(payload)
        a.events.clear()
        self.renderer.update(dt)

    def _record(self):
        self.game.save["best"] = max(self.game.save["best"], self.score)
        write_save(self.game.save)

    def draw(self, surf):
        surf.fill((0, 0, 0))
        self.renderer.draw(surf, HUD)
        hud_panel(surf)
        f = self.game.fonts
        a = self.arena
        p = a.players[0]
        text(surf, f["sm"], f"STAGE {stage_label(self.stage)}", (16, 20), a.world["accent"], "midleft")
        text(surf, f["xs"], a.world["name"], (16, 44), (170, 180, 210), "midleft")
        text(surf, f["md"], f"{self.score:07d}", (SW // 2 - 110, HUD // 2), (255, 255, 255))
        tl = max(0, int(self.time_left))
        text(surf, f["sm"], f"{tl // 60}:{tl % 60:02d}", (SW // 2 + 15, HUD // 2),
             (255, 120, 100) if tl < 30 else (220, 230, 255))
        # lives
        x = SW // 2 + 70
        mini = pygame.transform.smoothscale(art.player_sprite(PLAYER_COLORS[0], "down", 0), (34, 34))
        surf.blit(mini, (x, HUD // 2 - 19))
        text(surf, f["sm"], f"x{max(0, self.lives)}", (x + 36, HUD // 2), (230, 235, 250), "midleft")
        draw_stat_icons(surf, f["xs"], p, SW - 270, HUD // 2)
        left = sum(1 for e in a.enemies if e.alive)
        if left == 0 and not a.exit_revealed and self.phase == "play":
            text(surf, f["xs"], "All clear! Find the portal under a crate.", (SW // 2, HUD + 20),
                 (255, 230, 120))

        if self.phase == "intro":
            banner(surf, self.game, f"STAGE {stage_label(self.stage)}", a.world["name"], self.pt,
                   a.world["accent"])
        elif self.phase == "clear":
            banner(surf, self.game, "STAGE CLEAR", f"Time bonus +{self.bonus}", self.pt, (150, 255, 170))
        elif self.phase == "dead" and self.pt > 0.8:
            msg = "Out of lives" if self.lives <= 0 else f"{self.lives} {'life' if self.lives == 1 else 'lives'} left"
            banner(surf, self.game, "OUCH!", msg, self.pt - 0.8, (255, 120, 100))
        if self.paused:
            self.paused.draw(surf)


# ----------------------------------------------------------------- versus
class BotController:
    def __init__(self, bot):
        self.bot = bot
        self.label = "bot"
        self.arena = None
        self.player = None
        self.dt = 0.0

    def event(self, e):
        pass

    def poll(self):
        if self.arena is None or self.player is None or not self.player.alive:
            return None, False, False
        return self.bot.control(self.arena, self.player, self.dt)


class VersusScene(Scene):
    def __init__(self, game, slots, wins_needed, arena_idx):
        super().__init__(game)
        self.slots = slots
        self.wins_needed = wins_needed
        self.arena_idx = arena_idx
        self.round = 0
        self.fighters = []   # (slot index, controller)
        for i, s in enumerate(slots):
            kind = SLOT_TYPES[s]
            if kind == "Off":
                continue
            if s == 0: c = KeyController(KB1, "WASD")
            elif s == 1: c = KeyController(KB2, "Arrows")
            elif s == 2: c = PadController(0, "Pad 1")
            elif s == 3: c = PadController(1, "Pad 2")
            else: c = BotController(Bot(i * 17 + 3, 0.55 if "easy" in kind else 0.95))
            self.fighters.append((i, c))
        self.wins = {i: 0 for i, _ in self.fighters}
        self.paused = None
        self._new_round()
        game.audio.play_music("battle")

    def _new_round(self):
        self.round += 1
        specs = [(c, PLAYER_COLORS[i], PLAYER_NAMES[i]) for i, c in self.fighters]
        self.arena = Arena("versus", self.arena_idx, specs, seed=random.randrange(1 << 30),
                           audio=self.game.audio)
        for (i, c), p in zip(self.fighters, self.arena.players):
            p.slot = i
            if isinstance(c, BotController):
                c.arena, c.player = self.arena, p
                c.bot.step = c.bot.target = None
        self.renderer = ArenaRenderer(self.arena)
        self.phase, self.pt = "intro", 0.0
        self.time_left = 120.0
        self.winner = None

    def event(self, e):
        if self.paused:
            if self.paused.event(e) == "resume":
                self.paused = None
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE or \
                e.type == pygame.JOYBUTTONDOWN and e.button == 7:
            self.paused = Overlay(self.game, lambda: self.game.set_scene(TitleScene(self.game)))
            return
        for _, c in self.fighters:
            c.event(e)

    def update(self, dt):
        if self.paused:
            return
        a = self.arena
        self.pt += dt
        for _, c in self.fighters:
            if isinstance(c, BotController):
                c.dt = dt
        if self.phase == "intro":
            for _, c in self.fighters:
                if not isinstance(c, BotController):
                    c.poll()
            a.update(dt, [(None, False, False)] * len(a.players))
            if self.pt > 1.6:
                self.phase = "play"
        elif self.phase in ("play", "ending"):
            a.update(dt, [c.poll() for _, c in self.fighters])
            if a.sudden is None:
                self.time_left -= dt
                if self.time_left <= 0:
                    self.time_left = 0
                    a.start_sudden_death()
            alive = a.alive_players()
            if self.phase == "play" and len(alive) <= 1:
                self.phase, self.pt = "ending", 0.0
            if self.phase == "ending" and self.pt > 1.4:
                alive = a.alive_players()
                self.winner = alive[0] if len(alive) == 1 else None
                if self.winner:
                    self.wins[self.winner.slot] += 1
                    self.game.audio.play("win")
                self.phase, self.pt = "result", 0.0
        elif self.phase == "result":
            a.update(dt, [(None, False, False)] * len(a.players))
            if self.pt > 3.0:
                champ = [i for i, w in self.wins.items() if w >= self.wins_needed]
                if champ:
                    i = champ[0]
                    self.game.set_scene(ResultScene(self.game, f"{PLAYER_NAMES[i].upper()} WINS THE MATCH",
                                                    self._scoreline(), PLAYER_COLORS[i], win=True,
                                                    again=lambda: VersusScene(self.game, self.slots,
                                                                              self.wins_needed, self.arena_idx)))
                    return
                self._new_round()
                return
        for kind, payload in a.events:
            if kind == "pillar":
                self.renderer.add_pillar(payload)
            elif kind == "item":
                p, it = payload
                self.renderer.popup(p.x, p.y - 30, ITEM_NAMES[it], self.game.fonts["xs"])
        a.events.clear()
        self.renderer.update(dt)

    def _scoreline(self):
        return "   ".join(f"{PLAYER_NAMES[i]} {w}" for i, w in self.wins.items())

    def draw(self, surf):
        surf.fill((0, 0, 0))
        self.renderer.draw(surf, HUD)
        hud_panel(surf)
        f = self.game.fonts
        a = self.arena
        n = len(a.players)
        slot_w = (SW - 120) // 4
        for k, p in enumerate(a.players):
            x = 8 + k * slot_w + (120 if k >= 2 else 0)
            mini = pygame.transform.smoothscale(art.player_sprite(p.color, "down", 0), (40, 40))
            if not p.alive:
                mini.set_alpha(70)
            surf.blit(mini, (x, 6))
            for w in range(self.wins_needed):
                col = p.color if w < self.wins[p.slot] else (60, 64, 84)
                pygame.draw.circle(surf, col, (x + 52 + w * 13, 18), 5)
            draw_stat_icons(surf, f["xs"], p, x + 42, 44, size=18)
        tl = int(math.ceil(self.time_left))
        label = "SUDDEN DEATH" if a.sudden else f"{tl // 60}:{tl % 60:02d}"
        text(surf, f["sm"] if not a.sudden else f["xs"], label, (SW // 2, HUD // 2),
             (255, 110, 100) if a.sudden or tl <= 15 else (230, 235, 255))

        if self.phase == "intro":
            banner(surf, self.game, f"ROUND {self.round}", "Last one standing wins", self.pt, (255, 200, 110))
        elif self.phase == "result":
            if self.winner:
                banner(surf, self.game, f"{self.winner.name.upper()} WINS", self._scoreline(), self.pt,
                       self.winner.color)
            else:
                banner(surf, self.game, "DRAW", self._scoreline(), self.pt, (200, 200, 220))
        if self.paused:
            self.paused.draw(surf)


class ResultScene(MenuScene):
    def __init__(self, game, title, sub, color, win=False, again=None):
        items = []
        if again:
            items.append(("Rematch", lambda: game.set_scene(again())))
        items.append(("Main Menu", lambda: game.set_scene(TitleScene(game))))
        super().__init__(game, items)
        self.title, self.sub, self.color = title, sub, color
        game.audio.stop_music()
        if not win:
            game.audio.play("death")

    def back(self):
        self.game.set_scene(TitleScene(self.game))

    def draw(self, surf):
        self.backdrop.draw(surf)
        f = self.game.fonts
        glow_text(surf, f["lg"], self.title, (SW // 2, 220), self.color)
        text(surf, f["md"], self.sub, (SW // 2, 300), (220, 225, 240))
        self.draw_items(surf, 420)
