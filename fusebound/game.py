"""Main loop."""
import sys

import pygame

from .config import SW, SH, FPS
from .sfx import Audio
from . import scenes


class Game:
    def __init__(self):
        self.audio = Audio()          # must init mixer before pygame.init
        pygame.init()
        pygame.joystick.init()
        pygame.display.set_caption("Fusebound — by Janib Soomro")
        self.fullscreen = False
        self.screen = pygame.display.set_mode((SW, SH), pygame.SCALED | pygame.RESIZABLE, vsync=1)
        self.clock = pygame.time.Clock()
        def font(size, bold=True):
            try:
                return pygame.font.SysFont("ubuntu,dejavusans,freesans,arial", size, bold=bold)
            except Exception:
                return pygame.font.Font(None, size)
        self.fonts = {"title": font(96), "lg": font(56), "md": font(32), "sm": font(22),
                      "xs": font(16)}
        self.save = scenes.load_save()
        self.backdrop = scenes.Backdrop()
        self.running = True
        self.scene = scenes.TitleScene(self)
        pygame.display.set_icon(self._icon())

    def _icon(self):
        from . import art
        return pygame.transform.smoothscale(art.bomb_sprite(0, (255, 140, 60)), (32, 32))

    def set_scene(self, scene):
        self.scene = scene

    def toggle_fullscreen(self):
        pygame.display.toggle_fullscreen()
        self.fullscreen = not self.fullscreen

    def quit(self):
        self.running = False

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 20)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif e.type == pygame.JOYDEVICEADDED:
                    pygame.joystick.Joystick(e.device_index)
                else:
                    self.scene.event(e)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        pygame.quit()


def main():
    Game().run()
    sys.exit(0)
