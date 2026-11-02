"""Bot opponents for versus mode."""
import random
from collections import deque

from .config import T, CRATE, BOMB_TIME
from .world import NEIGH, center_of


def danger_map(arena, extra=None):
    """cell -> seconds until a blast covers it (0 for active flames)."""
    bombs = [(b.cell, b.power, (b.timer if not b.remote else 1.2)) for b in arena.bombs]
    if extra:
        bombs.append(extra)
    times = [t for _, _, t in bombs]
    covers = [set(arena.blast_cells(c, pw)) for c, pw, _ in bombs]
    # propagate chain reactions
    changed = True
    while changed:
        changed = False
        for i, (ci, _, _) in enumerate(bombs):
            for j in range(len(bombs)):
                if i != j and ci in covers[j] and times[j] < times[i]:
                    times[i] = times[j]
                    changed = True
    d = {}
    for cov, t in zip(covers, times):
        for c in cov:
            if t < d.get(c, 99):
                d[c] = t
    for c in arena.flames:
        d[c] = 0.0
    for c in arena.breaking:
        d.setdefault(c, 99)
    return d


class Bot:
    def __init__(self, seed, skill=0.8):
        self.rnd = random.Random(seed)
        self.skill = skill
        self.step = None
        self.target = None
        self.think = 0.0
        self.want_bomb = False
        self.want_det = False

    def _bfs(self, arena, p, start, danger, avoid_danger=True, max_depth=40):
        step_time = T / p.speed
        first = {start: None}
        depth = {start: 0}
        q = deque([start])
        order = []
        while q:
            c = q.popleft()
            order.append(c)
            if depth[c] >= max_depth:
                continue
            for v in NEIGH:
                n = (c[0] + v[0], c[1] + v[1])
                if n in first or arena.blocked_for_player(n, p):
                    continue
                arrive = (depth[c] + 1) * step_time
                t = danger.get(n)
                if t is not None:
                    if t == 0.0:
                        continue
                    if avoid_danger:
                        continue
                    if abs(t - arrive) < 0.6 + step_time:
                        continue
                first[n] = v if c == start else first[c]
                depth[n] = depth[c] + 1
                q.append(n)
        return order, first, depth

    def _escape(self, arena, p, start, danger):
        order, first, depth = self._bfs(arena, p, start, danger, avoid_danger=False, max_depth=12)
        for c in order:
            if c not in danger:
                return first[c], depth[c]
        return None, None

    def decide(self, arena, p):
        start = p.cell
        danger = danger_map(arena)
        self.want_bomb = False
        self.want_det = False
        opponents = [o for o in arena.alive_players() if o is not p]

        if start in danger:
            v, _ = self._escape(arena, p, start, danger)
            self.step = v
            return

        if p.remote and any(b.owner is p for b in arena.bombs):
            own_cover = set()
            for b in arena.bombs:
                if b.owner is p:
                    own_cover.update(arena.blast_cells(b.cell, b.power))
            if start not in own_cover:
                self.want_det = True

        # should we drop a charge here?
        if p.active_bombs < p.max_bombs and start not in arena.bomb_at:
            cover = arena.blast_cells(start, p.fire)
            crates = sum(1 for c in cover if arena.tile(c) == CRATE)
            hits = sum(1 for o in opponents if o.cell in cover)
            near = any(abs(o.cell[0] - start[0]) + abs(o.cell[1] - start[1]) <= 1 for o in opponents)
            if hits or crates or near:
                timer = BOMB_TIME if not p.remote else 1.2
                d2 = danger_map(arena, (start, p.fire, timer))
                arena.bomb_at[start] = True  # treat as blocking while planning
                try:
                    v, steps = self._escape(arena, p, start, d2)
                finally:
                    del arena.bomb_at[start]
                if v is not None and steps * (T / p.speed) < timer - 0.5:
                    if self.rnd.random() < self.skill or hits:
                        self.want_bomb = True
                        self.step = v
                        return

        # pick a goal
        order, first, depth = self._bfs(arena, p, start, danger, avoid_danger=True, max_depth=30)
        best, best_score = None, -1e9
        for c in order:
            if c == start:
                continue
            score = -depth[c] * 1.0
            if c in arena.items:
                score += 14
            adj_crate = any(arena.tile((c[0] + v[0], c[1] + v[1])) == CRATE for v in NEIGH)
            if adj_crate and p.active_bombs < p.max_bombs:
                score += 6
            for o in opponents:
                od = abs(o.cell[0] - c[0]) + abs(o.cell[1] - c[1])
                if od <= 2:
                    score += 5 - od
            score += self.rnd.random() * 1.5
            if score > best_score:
                best, best_score = c, score
        self.step = first.get(best) if best else None

    def control(self, arena, p, dt):
        self.think -= dt
        reached = False
        if self.step is not None and self.target is not None:
            tx, ty = center_of(self.target)
            along = (tx - p.x) * self.step[0] + (ty - p.y) * self.step[1]
            reached = along <= 1.0
        if self.think <= 0 or reached or self.step is None and self.think <= 0:
            self.think = 0.15 + (1 - self.skill) * 0.25
            start = p.cell
            self.decide(arena, p)
            self.target = (start[0] + self.step[0], start[1] + self.step[1]) if self.step else None
        bomb, det = self.want_bomb, self.want_det
        self.want_bomb = self.want_det = False
        return self.step, bomb, det
