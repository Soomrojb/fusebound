"""Global constants for Fusebound."""
import os

T = 56                    # tile size in logical pixels
GW, GH = 15, 13           # arena size in tiles
HUD = 64                  # height of the HUD bar
SW, SH = GW * T, GH * T + HUD
FPS = 60

FLOOR, PILLAR, CRATE = 0, 1, 2

BOMB_TIME = 2.6
FLAME_TIME = 0.55
BREAK_TIME = 0.45

ITEMS = ["bomb", "fire", "speed", "remote", "ghost", "shield"]
ITEM_COLORS = {
    "bomb": (110, 170, 255),
    "fire": (255, 140, 60),
    "speed": (120, 255, 160),
    "remote": (255, 90, 200),
    "ghost": (190, 160, 255),
    "shield": (255, 225, 90),
}
ITEM_NAMES = {
    "bomb": "+1 Charge", "fire": "+1 Blast", "speed": "Speed Up",
    "remote": "Remote Trigger", "ghost": "Phase Walk", "shield": "Shield",
}

WORLDS = [
    dict(name="Neon Foundry", bg=(12, 14, 22), floor=(36, 40, 56), floor2=(41, 46, 64),
         pillar=(64, 74, 104), pillar_hi=(130, 150, 205), crate=(140, 92, 58),
         crate_hi=(205, 148, 92), accent=(80, 220, 255)),
    dict(name="Frost Circuit", bg=(10, 18, 26), floor=(34, 52, 68), floor2=(39, 59, 77),
         pillar=(58, 72, 100), pillar_hi=(140, 165, 210), crate=(150, 200, 225),
         crate_hi=(235, 250, 255), accent=(150, 240, 255)),
    dict(name="Ember Ruins", bg=(22, 10, 8), floor=(60, 38, 32), floor2=(68, 44, 36),
         pillar=(104, 60, 44), pillar_hi=(220, 140, 90), crate=(120, 80, 40),
         crate_hi=(210, 160, 80), accent=(255, 150, 60)),
    dict(name="Void Garden", bg=(14, 8, 22), floor=(34, 30, 52), floor2=(40, 34, 62),
         pillar=(70, 50, 110), pillar_hi=(170, 130, 240), crate=(60, 110, 80),
         crate_hi=(120, 210, 150), accent=(200, 120, 255)),
]
STAGES_PER_WORLD = 5
TOTAL_STAGES = len(WORLDS) * STAGES_PER_WORLD

PLAYER_COLORS = [(80, 200, 255), (255, 110, 90), (140, 240, 120), (250, 210, 80)]
PLAYER_NAMES = ["Volt", "Ember", "Moss", "Sol"]

ENEMY_INFO = {
    #        speed(tiles/s) hp  points
    "blob":   (1.6, 1, 100),
    "spark":  (2.6, 1, 200),
    "hunter": (2.2, 1, 400),
    "wisp":   (1.4, 1, 800),
    "brute":  (1.9, 2, 1000),
}

SAVE_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "fusebound")
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")

AUTHOR = "Janib Soomro"
AUTHOR_GITHUB = "https://github.com/soomrojb"
AUTHOR_SITE = "https://ormoos.com"
REPO_URL = "https://github.com/soomrojb/fusebound"
VERSION = "1.0.0"
