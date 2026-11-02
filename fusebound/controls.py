"""Keyboard and gamepad controllers."""
import pygame

KB1 = dict(up=[pygame.K_w], down=[pygame.K_s], left=[pygame.K_a], right=[pygame.K_d],
           bomb=[pygame.K_SPACE], det=[pygame.K_LSHIFT, pygame.K_e])
KB2 = dict(up=[pygame.K_UP], down=[pygame.K_DOWN], left=[pygame.K_LEFT], right=[pygame.K_RIGHT],
           bomb=[pygame.K_RCTRL, pygame.K_RETURN, pygame.K_KP0],
           det=[pygame.K_RSHIFT, pygame.K_KP_PERIOD])
KB_ALL = {k: KB1[k] + KB2[k] + ([pygame.K_x] if k == "bomb" else [pygame.K_z] if k == "det" else [])
          for k in KB1}

VEC = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class KeyController:
    def __init__(self, mapping, label):
        self.map = mapping
        self.label = label
        self.held = []
        self.bomb = False
        self.det = False
        self.lookup = {}
        for action, keys in mapping.items():
            for k in keys:
                self.lookup[k] = action

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key in self.lookup:
            a = self.lookup[e.key]
            if a in VEC:
                if a in self.held:
                    self.held.remove(a)
                self.held.append(a)
            elif a == "bomb":
                self.bomb = True
            elif a == "det":
                self.det = True
        elif e.type == pygame.KEYUP and e.key in self.lookup:
            a = self.lookup[e.key]
            if a in self.held:
                self.held.remove(a)

    def poll(self):
        # resync with real key state in case a KEYUP was missed (focus loss)
        keys = pygame.key.get_pressed()
        self.held = [a for a in self.held if any(keys[k] for k in self.map[a])]
        d = VEC[self.held[-1]] if self.held else None
        b, t = self.bomb, self.det
        self.bomb = self.det = False
        return d, b, t


class PadController:
    def __init__(self, index, label):
        self.index = index
        self.label = label
        self.bomb = False
        self.det = False
        self.joy = None
        self._attach()

    def _attach(self):
        if self.index < pygame.joystick.get_count():
            self.joy = pygame.joystick.Joystick(self.index)

    def event(self, e):
        if self.joy is None:
            return
        if e.type == pygame.JOYBUTTONDOWN and e.instance_id == self.joy.get_instance_id():
            if e.button in (0, 3):
                self.bomb = True
            elif e.button in (1, 2):
                self.det = True

    def poll(self):
        d = None
        if self.joy is not None:
            try:
                hx, hy = self.joy.get_hat(0) if self.joy.get_numhats() else (0, 0)
                ax = self.joy.get_axis(0) if self.joy.get_numaxes() > 1 else 0
                ay = self.joy.get_axis(1) if self.joy.get_numaxes() > 1 else 0
            except pygame.error:
                hx = hy = ax = ay = 0
            if hx or hy:
                d = (hx, 0) if hx else (0, -hy)
            elif max(abs(ax), abs(ay)) > 0.5:
                d = ((1 if ax > 0 else -1), 0) if abs(ax) > abs(ay) else (0, (1 if ay > 0 else -1))
        b, t = self.bomb, self.det
        self.bomb = self.det = False
        return d, b, t


class MultiController:
    """Combines several controllers (e.g. both keyboard halves + a pad in campaign)."""
    def __init__(self, parts, label):
        self.parts = parts
        self.label = label

    def event(self, e):
        for p in self.parts:
            p.event(e)

    def poll(self):
        d, b, t = None, False, False
        for p in self.parts:
            pd, pb, pt = p.poll()
            d = d or pd
            b = b or pb
            t = t or pt
        return d, b, t
