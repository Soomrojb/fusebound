"""Keyboard and gamepad controllers."""
import pygame

KB1 = dict(up=[pygame.K_w], down=[pygame.K_s], left=[pygame.K_a], right=[pygame.K_d],
           bomb=[pygame.K_SPACE], det=[pygame.K_LSHIFT, pygame.K_e])
KB2 = dict(up=[pygame.K_UP], down=[pygame.K_DOWN], left=[pygame.K_LEFT], right=[pygame.K_RIGHT],
           bomb=[pygame.K_RCTRL, pygame.K_RETURN, pygame.K_KP0],
           det=[pygame.K_RSHIFT, pygame.K_KP_PERIOD])
KB3 = dict(up=[pygame.K_i], down=[pygame.K_k], left=[pygame.K_j], right=[pygame.K_l],
           bomb=[pygame.K_o], det=[pygame.K_u])
DEFAULTS = {"p1": KB1, "p2": KB2, "p3": KB3}
LAYOUTS = ["p1", "p2", "p3"]
LAYOUT_NAMES = {"p1": "Keyboard 1", "p2": "Keyboard 2", "p3": "Keyboard 3"}
ACTIONS = ["up", "down", "left", "right", "bomb", "det"]
ACTION_NAMES = {"up": "Up", "down": "Down", "left": "Left", "right": "Right",
                "bomb": "Drop charge", "det": "Trigger"}
RESERVED = {pygame.K_ESCAPE, pygame.K_F11}   # pause / fullscreen, never bindable

# live, user-editable bindings (loaded from the save file at startup)
bindings = {lay: {a: list(DEFAULTS[lay][a]) for a in ACTIONS} for lay in LAYOUTS}


def reset_bindings():
    for lay in LAYOUTS:
        bindings[lay] = {a: list(DEFAULTS[lay][a]) for a in ACTIONS}


def load_bindings(data):
    """Apply saved bindings. Layouts missing from the save (e.g. a newly added one) get their
    defaults; a key already claimed by an earlier action is dropped so nothing is duplicated."""
    reset_bindings()
    seen = set(RESERVED)
    new = {}
    saved = [l for l in LAYOUTS if isinstance(data, dict) and isinstance(data.get(l), dict)]
    for lay in saved + [l for l in LAYOUTS if l not in saved]:
        new[lay] = {}
        for a in ACTIONS:
            try:
                keys = [int(k) for k in data[lay][a]]
            except Exception:
                keys = list(DEFAULTS[lay][a])
            keys = [k for k in dict.fromkeys(keys) if k not in seen]
            seen.update(keys)
            new[lay][a] = keys
    bindings.update(new)


def export_bindings():
    return {lay: {a: list(bindings[lay][a]) for a in ACTIONS} for lay in LAYOUTS}


def find_owner(key):
    """Return (layout, action) already using this key, or None."""
    for lay in LAYOUTS:
        for a in ACTIONS:
            if key in bindings[lay][a]:
                return lay, a
    return None


def campaign_map():
    """Single-player mapping: every keyboard layout plus X / Z when they are free."""
    m = {a: [k for lay in LAYOUTS for k in bindings[lay][a]] for a in ACTIONS}
    for k, a in ((pygame.K_x, "bomb"), (pygame.K_z, "det")):
        if find_owner(k) is None:
            m[a] = m[a] + [k]
    return m


_PRETTY = {"left shift": "L-Shift", "right shift": "R-Shift", "left ctrl": "L-Ctrl",
           "right ctrl": "R-Ctrl", "left alt": "L-Alt", "right alt": "R-Alt",
           "return": "Enter", ",": "Comma", ".": "Period", "/": "Slash", ";": "Semicolon",
           "'": "Quote", "-": "Minus", "=": "Equals", "[": "L-Bracket", "]": "R-Bracket",
           "up": "Up", "down": "Down", "left": "Left", "right": "Right"}


def key_label(k):
    n = pygame.key.name(k)
    if n in _PRETTY:
        return _PRETTY[n]
    if n.startswith("[") and n.endswith("]"):
        return "Num " + n[1:-1]
    return n.upper() if len(n) == 1 else n.title()


def keys_label(keys):
    return " / ".join(key_label(k) for k in keys) if keys else "(none)"


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
