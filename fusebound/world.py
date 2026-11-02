"""Core simulation: arena grid, players, enemies, charges and blasts."""
import math
import random
from collections import deque

from .config import (T, GW, GH, FLOOR, PILLAR, CRATE, BOMB_TIME, FLAME_TIME, BREAK_TIME,
                     ITEMS, ENEMY_INFO, WORLDS, STAGES_PER_WORLD)

DIR_VEC = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
VEC_DIR = {v: k for k, v in DIR_VEC.items()}
NEIGH = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def cell_of(x, y):
    return int(x // T), int(y // T)


def center_of(c):
    return c[0] * T + T / 2, c[1] * T + T / 2


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "color", "size", "glow", "grav")

    def __init__(self, x, y, vx, vy, life, color, size, glow=False, grav=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max = life
        self.color, self.size, self.glow, self.grav = color, size, glow, grav


class Player:
    def __init__(self, idx, cell, color, name, controller):
        self.idx = idx
        self.color = color
        self.name = name
        self.controller = controller
        self.x, self.y = center_of(cell)
        self.spawn = cell
        self.reset_stats()
        self.alive = True
        self.dying = 0.0
        self.facing = "down"
        self.anim = 0.0
        self.moving = False
        self.invuln = 0.0
        self.active_bombs = 0
        self.wins = 0
        self.kills = 0

    def reset_stats(self):
        self.max_bombs = 1
        self.fire = 2
        self.speed_lv = 0
        self.remote = False
        self.ghost = False
        self.shield = False

    @property
    def speed(self):
        return (3.3 + 0.55 * self.speed_lv) * T

    @property
    def cell(self):
        return cell_of(self.x, self.y)


class Enemy:
    def __init__(self, kind, cell, rnd):
        self.kind = kind
        spd, hp, pts = ENEMY_INFO[kind]
        self.speed = spd * T
        self.hp = hp
        self.points = pts
        self.x, self.y = center_of(cell)
        self.target = cell
        self.prev = cell
        self.dir = rnd.choice(list(DIR_VEC.values()))
        self.anim = rnd.random() * 4
        self.flash = 0.0
        self.alive = True
        self.dying = 0.0
        self.think = 0.0

    @property
    def cell(self):
        return cell_of(self.x, self.y)

    @property
    def phasing(self):
        return self.kind == "wisp"


class Bomb:
    def __init__(self, cell, owner, power, remote):
        self.cell = cell
        self.owner = owner
        self.power = power
        self.remote = remote
        self.timer = BOMB_TIME if not remote else 999.0
        self.t = 0.0
        self.exploded = False


class Blast:
    """Visual record of one explosion (center + arm lengths)."""
    def __init__(self, cell, arms):
        self.cell = cell
        self.arms = arms   # dict dir_vec -> length in cells
        self.t = 0.0


def stage_world(stage):
    return WORLDS[min(stage // STAGES_PER_WORLD, len(WORLDS) - 1)]


class Arena:
    def __init__(self, mode, stage, player_specs, seed=None, audio=None):
        """mode: 'campaign' or 'versus'. player_specs: list of (controller, color, name)."""
        self.mode = mode
        self.stage = stage
        self.world = stage_world(stage) if mode == "campaign" else WORLDS[stage % len(WORLDS)]
        self.rnd = random.Random(seed)
        self.audio = audio
        self.grid = [[FLOOR] * GW for _ in range(GH)]
        self.hidden = {}
        self.items = {}
        self.bombs = []
        self.bomb_at = {}
        self.flames = {}
        self.blasts = []
        self.breaking = {}
        self.particles = []
        self.enemies = []
        self.players = []
        self.exit_cell = None
        self.exit_revealed = False
        self.portal_open = False
        self.time = 0.0
        self.shake = 0.0
        self.events = []        # (kind, payload) consumed by the scene
        self.sudden = None      # sudden-death spiral state
        self.score_gain = 0
        self._build(player_specs)

    # ------------------------------------------------------------ generation
    def _build(self, specs):
        g = self.grid
        for y in range(GH):
            for x in range(GW):
                if x in (0, GW - 1) or y in (0, GH - 1) or (x % 2 == 0 and y % 2 == 0):
                    g[y][x] = PILLAR
        if self.mode == "campaign":
            spawns = [(1, 1)]
        else:
            spawns = [(1, 1), (GW - 2, GH - 2), (GW - 2, 1), (1, GH - 2)]
        safe = set()
        for sx, sy in spawns[:max(1, len(specs))]:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (0, 2), (-2, 0), (0, -2)):
                safe.add((sx + dx, sy + dy))

        density = 0.62 if self.mode == "versus" else 0.45 + 0.02 * (self.stage % STAGES_PER_WORLD) + 0.03 * (self.stage // STAGES_PER_WORLD)
        crates = []
        for y in range(1, GH - 1):
            for x in range(1, GW - 1):
                if g[y][x] == FLOOR and (x, y) not in safe and self.rnd.random() < density:
                    g[y][x] = CRATE
                    crates.append((x, y))

        for i, (ctrl, color, name) in enumerate(specs):
            p = Player(i, spawns[i], color, name, ctrl)
            self.players.append(p)

        if self.mode == "campaign":
            self.rnd.shuffle(crates)
            far = sorted(crates, key=lambda c: -(abs(c[0] - 1) + abs(c[1] - 1)))
            self.exit_cell = far[self.rnd.randint(0, max(0, len(far) // 3))]
            self.hidden[self.exit_cell] = "exit"
            pool = [c for c in crates if c != self.exit_cell]
            n_items = 2 if self.stage % STAGES_PER_WORLD != STAGES_PER_WORLD - 1 else 3
            weights = {"bomb": 4, "fire": 4, "speed": 2, "remote": 1, "ghost": 1, "shield": 1}
            for c in pool[:n_items]:
                self.hidden[c] = self._weighted(weights)
            self._spawn_enemies()
        else:
            weights = {"bomb": 5, "fire": 5, "speed": 3, "remote": 1, "ghost": 1, "shield": 2}
            for c in crates:
                if self.rnd.random() < 0.34:
                    self.hidden[c] = self._weighted(weights)
            self.round_time = 120.0

    def _weighted(self, weights):
        total = sum(weights.values())
        r = self.rnd.uniform(0, total)
        for k, w in weights.items():
            r -= w
            if r <= 0:
                return k
        return "bomb"

    def _spawn_enemies(self):
        s = self.stage
        pool = ["blob"]
        if s >= 2: pool.append("spark")
        if s >= 5: pool.append("hunter")
        if s >= 9: pool.append("wisp")
        if s >= 13: pool.append("brute")
        count = min(4 + s // 2 + (2 if s % STAGES_PER_WORLD == STAGES_PER_WORLD - 1 else 0), 13)
        free = [(x, y) for y in range(1, GH - 1) for x in range(1, GW - 1)
                if self.grid[y][x] == FLOOR and abs(x - 1) + abs(y - 1) >= 7]
        self.rnd.shuffle(free)
        for i in range(min(count, len(free))):
            # newer enemy types are more likely
            w = [1 + j * 0.8 for j in range(len(pool))]
            kind = self.rnd.choices(pool, weights=w)[0]
            self.enemies.append(Enemy(kind, free[i], self.rnd))

    # ---------------------------------------------------------------- queries
    def in_bounds(self, c):
        return 0 <= c[0] < GW and 0 <= c[1] < GH

    def tile(self, c):
        return self.grid[c[1]][c[0]] if self.in_bounds(c) else PILLAR

    def blocked_for_player(self, c, p):
        t = self.tile(c)
        if t == PILLAR:
            return True
        if t == CRATE and not (p.ghost and c not in self.breaking):
            return True
        return c in self.bomb_at

    def blocked_for_enemy(self, c, e):
        t = self.tile(c)
        if t == PILLAR:
            return True
        if t == CRATE and not e.phasing:
            return True
        if c in self.bomb_at:
            return True
        if e.kind in ("hunter", "brute") and c in self.flames:
            return True
        return False

    def alive_players(self):
        return [p for p in self.players if p.alive]

    # --------------------------------------------------------------- movement
    def move_player(self, p, d, dt):
        """Grid-locked movement with corner assist. d: (dx,dy) or None."""
        if d is None or not p.alive:
            p.moving = False
            return
        p.facing = VEC_DIR[d]
        dist = p.speed * dt
        dx, dy = d
        c = p.cell
        cx, cy = center_of(c)
        blocked = lambda cell: self.blocked_for_player(cell, p)
        moved = False
        if dx:
            off = p.y - cy
            ahead = (c[0] + dx, c[1])
            if abs(off) > 0.5:
                s = 1 if off > 0 else -1
                side_ahead = (c[0] + dx, c[1] + s)
                side = (c[0], c[1] + s)
                if not blocked(ahead) or abs(p.x - cx) * dx < -0.5:
                    p.y -= math.copysign(min(dist, abs(off)), off); moved = True
                elif abs(off) > T * 0.18 and not blocked(side_ahead) and not blocked(side):
                    p.y += s * dist; moved = True
                else:
                    pass
                if moved:
                    p.moving = True
                    return
            else:
                p.y = cy
            nx = p.x + dx * dist
            if blocked(ahead):
                nx = min(nx, max(p.x, cx)) if dx > 0 else max(nx, min(p.x, cx))
            moved = abs(nx - p.x) > 1e-6
            if not moved and abs(off) <= 0.5:
                # try corner-slide around the obstacle we are facing
                pass
            p.x = nx
        else:
            off = p.x - cx
            ahead = (c[0], c[1] + dy)
            if abs(off) > 0.5:
                s = 1 if off > 0 else -1
                side_ahead = (c[0] + s, c[1] + dy)
                side = (c[0] + s, c[1])
                if not blocked(ahead) or abs(p.y - cy) * dy < -0.5:
                    p.x -= math.copysign(min(dist, abs(off)), off); moved = True
                elif abs(off) > T * 0.18 and not blocked(side_ahead) and not blocked(side):
                    p.x += s * dist; moved = True
                if moved:
                    p.moving = True
                    return
            else:
                p.x = cx
            ny = p.y + dy * dist
            if blocked(ahead):
                ny = min(ny, max(p.y, cy)) if dy > 0 else max(ny, min(p.y, cy))
            moved = abs(ny - p.y) > 1e-6
            p.y = ny
        p.moving = moved

    def update_enemy(self, e, dt):
        e.anim += dt * 6
        if e.flash > 0:
            e.flash -= dt
        tx, ty = center_of(e.target)
        dist = e.speed * dt
        # target became blocked (bomb dropped) -> turn back
        if e.target != e.cell and self.blocked_for_enemy(e.target, e) and e.target in self.bomb_at:
            e.target, e.prev = e.prev, e.target
            tx, ty = center_of(e.target)
        ddx, ddy = tx - e.x, ty - e.y
        d = math.hypot(ddx, ddy)
        if d > dist:
            e.x += ddx / d * dist
            e.y += ddy / d * dist
            return
        e.x, e.y = tx, ty
        e.think -= dt
        here = e.target
        opts = [v for v in NEIGH if not self.blocked_for_enemy((here[0] + v[0], here[1] + v[1]), e)]
        if not opts:
            return
        nd = None
        if e.kind in ("hunter", "brute", "wisp"):
            nd = self._chase_dir(e, here, 8 if e.kind != "wisp" else 12)
        if nd is None:
            fwd = e.dir if e.dir in opts else None
            turn_bias = 0.25 if e.kind == "blob" else 0.5
            if fwd and (len(opts) <= 2 or self.rnd.random() > turn_bias):
                nd = fwd
                if len(opts) > 1 and self.rnd.random() < 0.05:
                    nd = self.rnd.choice(opts)
            else:
                back = (-e.dir[0], -e.dir[1])
                choices = [o for o in opts if o != back] or opts
                nd = self.rnd.choice(choices)
        e.dir = nd
        e.prev = here
        e.target = (here[0] + nd[0], here[1] + nd[1])

    def _chase_dir(self, e, start, max_d):
        targets = {p.cell for p in self.alive_players()}
        if not targets:
            return None
        if min(abs(t[0] - start[0]) + abs(t[1] - start[1]) for t in targets) > max_d:
            return None
        q = deque([start])
        first = {start: None}
        while q:
            c = q.popleft()
            if c in targets and c != start:
                return first[c]
            for v in NEIGH:
                n = (c[0] + v[0], c[1] + v[1])
                if n in first or self.blocked_for_enemy(n, e):
                    continue
                first[n] = v if c == start else first[c]
                q.append(n)
        return None

    # ------------------------------------------------------------------ bombs
    def place_bomb(self, p):
        if not p.alive or p.active_bombs >= p.max_bombs:
            return False
        c = p.cell
        if c in self.bomb_at or self.tile(c) != FLOOR:
            return False
        b = Bomb(c, p, p.fire, p.remote)
        self.bombs.append(b)
        self.bomb_at[c] = b
        p.active_bombs += 1
        self._sfx("place")
        return True

    def remote_detonate(self, p):
        own = [b for b in self.bombs if b.owner is p and b.remote]
        if own:
            own[0].timer = 0.0

    def blast_cells(self, cell, power):
        """Cells a blast would cover (ignores chain reactions)."""
        cells = [cell]
        for v in NEIGH:
            for i in range(1, power + 1):
                c = (cell[0] + v[0] * i, cell[1] + v[1] * i)
                t = self.tile(c)
                if t == PILLAR:
                    break
                cells.append(c)
                if t == CRATE or c in self.bomb_at:
                    break
        return cells

    def _explode(self, first):
        queue = [first]
        while queue:
            b = queue.pop()
            if b.exploded:
                continue
            b.exploded = True
            self.bombs.remove(b)
            self.bomb_at.pop(b.cell, None)
            b.owner.active_bombs = max(0, b.owner.active_bombs - 1)
            arms = {}
            self._ignite(b.cell, b.owner)
            for v in NEIGH:
                n = 0
                for i in range(1, b.power + 1):
                    c = (b.cell[0] + v[0] * i, b.cell[1] + v[1] * i)
                    t = self.tile(c)
                    if t == PILLAR:
                        break
                    if t == CRATE:
                        if c not in self.breaking:
                            self.breaking[c] = BREAK_TIME
                            self._debris(c)
                        break
                    n = i
                    self._ignite(c, b.owner)
                    if c in self.bomb_at:
                        queue.append(self.bomb_at[c])
                        break
                    if c in self.items:
                        del self.items[c]
                        self._puff(c)
                        break
                arms[v] = n
            self.blasts.append(Blast(b.cell, arms))
            self.shake = min(14, self.shake + 6)
            self._sfx("boom")
            cx, cy = center_of(b.cell)
            for _ in range(18):
                a = self.rnd.uniform(0, 2 * math.pi)
                sp = self.rnd.uniform(40, 220)
                self.particles.append(Particle(cx, cy, math.cos(a) * sp, math.sin(a) * sp,
                                               self.rnd.uniform(0.3, 0.7),
                                               self.rnd.choice([(255, 200, 80), (255, 120, 40), (255, 240, 200)]),
                                               self.rnd.uniform(2, 5), glow=True))

    def _ignite(self, c, owner):
        self.flames[c] = (FLAME_TIME, owner)

    def _debris(self, c):
        cx, cy = center_of(c)
        col = self.world["crate_hi"]
        for _ in range(12):
            a = self.rnd.uniform(0, 2 * math.pi)
            sp = self.rnd.uniform(60, 200)
            self.particles.append(Particle(cx, cy, math.cos(a) * sp, math.sin(a) * sp - 80,
                                           self.rnd.uniform(0.4, 0.8), col, self.rnd.uniform(2, 4),
                                           grav=500))

    def _puff(self, c):
        cx, cy = center_of(c)
        for _ in range(10):
            a = self.rnd.uniform(0, 2 * math.pi)
            sp = self.rnd.uniform(20, 90)
            self.particles.append(Particle(cx, cy, math.cos(a) * sp, math.sin(a) * sp,
                                           0.5, (200, 200, 220), 3))

    def _sfx(self, name):
        if self.audio:
            self.audio.play(name)

    # ----------------------------------------------------------------- update
    def update(self, dt, inputs):
        """inputs: list per player of (dir, bomb_pressed, detonate_pressed)."""
        self.time += dt
        self.shake = max(0.0, self.shake - dt * 30)

        for p, (d, bomb, det) in zip(self.players, inputs):
            if p.alive:
                self.move_player(p, d, dt)
                if p.moving:
                    p.anim += dt * 10
                if bomb:
                    self.place_bomb(p)
                if det and p.remote:
                    self.remote_detonate(p)
                if p.invuln > 0:
                    p.invuln -= dt
            elif p.dying < 1.0:
                p.dying = min(1.0, p.dying + dt * 1.2)

        for b in list(self.bombs):
            b.t += dt
            if not b.exploded:
                b.timer -= dt
                if b.timer <= 0:
                    self._explode(b)

        for c in list(self.flames):
            left, owner = self.flames[c]
            left -= dt
            if left <= 0:
                del self.flames[c]
            else:
                self.flames[c] = (left, owner)
        for bl in self.blasts:
            bl.t += dt
        self.blasts = [bl for bl in self.blasts if bl.t < FLAME_TIME]

        for c in list(self.breaking):
            self.breaking[c] -= dt
            if self.breaking[c] <= 0:
                del self.breaking[c]
                self.grid[c[1]][c[0]] = FLOOR
                h = self.hidden.pop(c, None)
                if h == "exit":
                    self.exit_revealed = True
                elif h:
                    self.items[c] = h

        # player damage and pickups
        for p in self.players:
            if not p.alive:
                continue
            c = p.cell
            if c in self.flames and p.invuln <= 0:
                self.hurt_player(p, self.flames[c][1])
            if not p.alive:
                continue
            if c in self.items:
                self.apply_item(p, self.items.pop(c))

        # enemies
        for e in self.enemies:
            if not e.alive:
                e.dying += dt * 1.6
                continue
            self.update_enemy(e, dt)
            c = e.cell
            if c in self.flames and e.flash <= 0:
                e.hp -= 1
                e.flash = 0.8
                self._sfx("hit")
                if e.hp <= 0:
                    e.alive = False
                    self.score_gain += e.points
                    self.events.append(("score", (e.x, e.y, e.points)))
            for p in self.players:
                if p.alive and p.invuln <= 0 and math.hypot(p.x - e.x, p.y - e.y) < T * 0.55:
                    self.hurt_player(p, None)
        self.enemies = [e for e in self.enemies if e.alive or e.dying < 1.0]

        if self.mode == "campaign" and not self.portal_open and self.exit_revealed and \
                not any(e.alive for e in self.enemies):
            self.portal_open = True
            self._sfx("portal")

        if self.sudden is not None:
            self._update_sudden(dt)

        # particles
        for pt in self.particles:
            pt.life -= dt
            pt.x += pt.vx * dt
            pt.y += pt.vy * dt
            pt.vy += pt.grav * dt
            pt.vx *= 0.96
            pt.vy *= 0.96 if pt.grav == 0 else 1
        self.particles = [pt for pt in self.particles if pt.life > 0]

    def hurt_player(self, p, killer):
        if p.shield:
            p.shield = False
            p.invuln = 1.5
            self._sfx("hit")
            return
        p.alive = False
        p.dying = 0.0
        self.shake = 12
        self._sfx("death")
        if killer is not None and killer is not p:
            killer.kills += 1
        self.events.append(("death", p))

    def apply_item(self, p, kind):
        if kind == "bomb":
            p.max_bombs = min(8, p.max_bombs + 1)
        elif kind == "fire":
            p.fire = min(9, p.fire + 1)
        elif kind == "speed":
            p.speed_lv = min(5, p.speed_lv + 1)
        elif kind == "remote":
            p.remote = True
        elif kind == "ghost":
            p.ghost = True
        elif kind == "shield":
            p.shield = True
        self.score_gain += 50
        self._sfx("pickup")
        self.events.append(("item", (p, kind)))
        cx, cy = center_of(p.cell)
        from .config import ITEM_COLORS
        for _ in range(14):
            a = self.rnd.uniform(0, 2 * math.pi)
            self.particles.append(Particle(cx, cy, math.cos(a) * 120, math.sin(a) * 120, 0.5,
                                           ITEM_COLORS[kind], 3, glow=True))

    def player_on_open_exit(self, p):
        if not (self.portal_open and p.alive):
            return False
        ex, ey = center_of(self.exit_cell)
        return math.hypot(p.x - ex, p.y - ey) < T * 0.3

    # ----------------------------------------------------------- sudden death
    def start_sudden_death(self):
        order = []
        x0, y0, x1, y1 = 1, 1, GW - 2, GH - 2
        while x0 <= x1 and y0 <= y1:
            for x in range(x0, x1 + 1): order.append((x, y0))
            for y in range(y0 + 1, y1 + 1): order.append((x1, y))
            if y0 < y1:
                for x in range(x1 - 1, x0 - 1, -1): order.append((x, y1))
            if x0 < x1:
                for y in range(y1 - 1, y0, -1): order.append((x0, y))
            x0, y0, x1, y1 = x0 + 1, y0 + 1, x1 - 1, y1 - 1
        self.sudden = {"order": order, "i": 0, "t": 0.0, "falling": []}

    def _update_sudden(self, dt):
        s = self.sudden
        s["t"] += dt
        while s["t"] > 0.22 and s["i"] < len(s["order"]):
            s["t"] -= 0.22
            c = s["order"][s["i"]]
            s["i"] += 1
            if self.tile(c) == PILLAR:
                continue
            s["falling"].append([c, 0.35])
        for f in s["falling"]:
            f[1] -= dt
            if f[1] <= 0:
                c = f[0]
                self.grid[c[1]][c[0]] = PILLAR
                self.items.pop(c, None)
                self.hidden.pop(c, None)
                self.breaking.pop(c, None)
                if c in self.bomb_at:
                    b = self.bomb_at.pop(c)
                    b.exploded = True
                    self.bombs.remove(b)
                    b.owner.active_bombs = max(0, b.owner.active_bombs - 1)
                for p in self.players:
                    if p.alive and p.cell == c:
                        p.shield = False
                        self.hurt_player(p, None)
                self.shake = max(self.shake, 4)
                self._sfx("thud")
                self.events.append(("pillar", c))
        s["falling"] = [f for f in s["falling"] if f[1] > 0]
