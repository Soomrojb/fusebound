"""Procedurally synthesized sound effects and music (no external assets)."""
import array
import math
import random
import threading

import pygame

RATE = 22050


def _osc(kind, phase):
    p = phase % 1.0
    if kind == "sin":
        return math.sin(phase * 2 * math.pi)
    if kind == "sq":
        return 1.0 if p < 0.5 else -1.0
    if kind == "tri":
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if kind == "saw":
        return 2 * p - 1
    return 0.0


def _note(n):
    """MIDI note number to frequency."""
    return 440.0 * 2 ** ((n - 69) / 12)


class Audio:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        self.music = {}
        self.current_music = None
        self.channel = None
        self.music_vol = 0.45
        self.sfx_vol = 0.8
        try:
            pygame.mixer.pre_init(RATE, -16, 1, 512)
            pygame.mixer.init(RATE, -16, 1, 512)
            freq, _, ch = pygame.mixer.get_init()
            self.rate, self.channels = freq, ch
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(1)
            self.ok = True
        except Exception as exc:  # no audio device: run silently
            print("Audio disabled:", exc)
            return
        self._build_sfx()
        self._pending_music = None
        threading.Thread(target=self._build_music, daemon=True).start()

    # ------------------------------------------------------------------ utils
    def _sound(self, samples, vol=1.0):
        data = array.array("h")
        ch = self.channels
        for s in samples:
            v = int(max(-1.0, min(1.0, s * vol)) * 32000)
            for _ in range(ch):
                data.append(v)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _render(self, dur, fn):
        n = int(self.rate * dur)
        return [fn(i / self.rate, i / n) for i in range(n)]

    # -------------------------------------------------------------------- sfx
    def _build_sfx(self):
        r = self.rate
        rnd = random.Random(7)

        # bomb placed: soft descending blip
        ph = [0.0]
        def place(t, u):
            ph[0] += (320 - 180 * u) / r
            return _osc("sin", ph[0]) * (1 - u) ** 2
        self.sounds["place"] = self._sound(self._render(0.09, place), 0.7)

        # explosion: filtered noise + low thump
        lp = [0.0]
        ph2 = [0.0]
        def boom(t, u):
            cutoff = 0.5 * (1 - u) ** 1.5 + 0.02
            lp[0] += cutoff * (rnd.uniform(-1, 1) - lp[0])
            ph2[0] += (90 - 50 * u) / r
            env = math.exp(-u * 5)
            return (lp[0] * 2.2 + _osc("sin", ph2[0]) * 0.8 * math.exp(-u * 8)) * env
        self.sounds["boom"] = self._sound(self._render(0.75, boom), 0.85)

        # power-up: rising arpeggio
        def arp(notes, step, kind="sq", vol=0.35):
            ph3 = [0.0]
            total = step * len(notes)
            def f(t, u):
                i = min(int(t / step), len(notes) - 1)
                ph3[0] += _note(notes[i]) / r
                local = (t - i * step) / step
                return _osc(kind, ph3[0]) * (1 - local * 0.6) * (1 - u * 0.5)
            return self._sound(self._render(total, f), vol)
        self.sounds["pickup"] = arp([72, 76, 79, 84], 0.05)
        self.sounds["menu"] = arp([79], 0.04, "sq", 0.2)
        self.sounds["select"] = arp([72, 79], 0.05, "sq", 0.25)
        self.sounds["clear"] = arp([67, 72, 76, 79, 76, 79, 84, 84], 0.11, "sq", 0.3)
        self.sounds["portal"] = arp([60, 67, 72, 79, 84, 91], 0.06, "tri", 0.45)
        self.sounds["win"] = arp([72, 72, 76, 79, 77, 81, 84, 84, 84], 0.12, "sq", 0.3)

        # death: wobbling descending square
        ph4 = [0.0]
        def death(t, u):
            f = 700 * (1 - u) + 90 + math.sin(t * 50) * 40
            ph4[0] += f / r
            return _osc("sq", ph4[0]) * (1 - u)
        self.sounds["death"] = self._sound(self._render(0.7, death), 0.3)

        # enemy hit: short noise crack
        def crack(t, u):
            return rnd.uniform(-1, 1) * (1 - u) ** 3
        self.sounds["hit"] = self._sound(self._render(0.12, crack), 0.5)

        # sudden-death block drop
        ph5 = [0.0]
        def thud(t, u):
            ph5[0] += (140 - 100 * u) / r
            return (_osc("tri", ph5[0]) + rnd.uniform(-0.3, 0.3)) * (1 - u) ** 2
        self.sounds["thud"] = self._sound(self._render(0.15, thud), 0.6)

        for s in self.sounds.values():
            s.set_volume(self.sfx_vol)

    # ------------------------------------------------------------------ music
    def _song(self, bpm, prog, lead_pattern, bars_per_chord, kind_lead="sq", drums=True):
        r = self.rate
        beat = 60.0 / bpm
        sixteenth = beat / 4
        bars = len(prog) * bars_per_chord
        total = bars * 4 * beat
        n = int(total * r)
        out = [0.0] * n
        rnd = random.Random(3)

        # bass (triangle, eighth notes)
        ph = 0.0
        for i in range(n):
            t = i / r
            bar = int(t / (4 * beat))
            root = prog[(bar // bars_per_chord) % len(prog)][0]
            eighth = int(t / (beat / 2))
            note = root - 24 + (12 if eighth % 4 == 3 else 0)
            ph += _note(note) / r
            local = (t % (beat / 2)) / (beat / 2)
            out[i] += _osc("tri", ph) * 0.32 * (1 - local * 0.5)

        # lead arpeggio (sixteenth notes)
        ph = 0.0
        for i in range(n):
            t = i / r
            step = int(t / sixteenth)
            bar = int(t / (4 * beat))
            chord = prog[(bar // bars_per_chord) % len(prog)]
            idx = lead_pattern[step % len(lead_pattern)]
            if idx is None:
                continue
            note = chord[idx % len(chord)] + 12 * (idx // len(chord))
            ph += _note(note) / r
            local = (t % sixteenth) / sixteenth
            out[i] += _osc(kind_lead, ph) * 0.10 * (1 - local) ** 0.7

        # drums
        if drums:
            spb = beat * r
            for b in range(int(bars * 4)):
                start = int(b * spb)
                # kick on every beat
                kp = 0.0
                for j in range(int(0.15 * r)):
                    if start + j >= n:
                        break
                    u = j / (0.15 * r)
                    kp += (120 - 80 * u) / r
                    out[start + j] += math.sin(kp * 2 * math.pi) * 0.45 * (1 - u) ** 2
                # hat on off-beats, snare on 2 and 4
                hs = int(start + spb / 2)
                for j in range(int(0.04 * r)):
                    if hs + j < n:
                        out[hs + j] += rnd.uniform(-1, 1) * 0.08 * (1 - j / (0.04 * r))
                if b % 2 == 1:
                    for j in range(int(0.12 * r)):
                        if start + j < n:
                            u = j / (0.12 * r)
                            out[start + j] += rnd.uniform(-1, 1) * 0.22 * (1 - u) ** 2
        return out

    def _build_music(self):
        try:
            am, f, c, g, e = [57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62], [52, 56, 59]
            dm = [50, 53, 57]
            battle = self._song(
                150, [am, f, c, g, am, f, dm, e],
                [3, None, 4, 5, 3, 4, None, 5, 6, 5, 4, None, 3, 4, 5, None], 1)
            menu = self._song(
                96, [am, f, c, g],
                [0, 2, 4, 2, 3, 2, 4, None, 0, 2, 4, 5, 4, 2, None, None], 2, "tri", drums=False)
            self.music["battle"] = self._sound(battle, 0.9)
            self.music["menu"] = self._sound(menu, 0.9)
            if self._pending_music:
                self.play_music(self._pending_music)
        except Exception as exc:
            print("Music generation failed:", exc)

    # --------------------------------------------------------------- playback
    def play(self, name):
        if self.ok and name in self.sounds:
            self.sounds[name].play()

    def play_music(self, name):
        if not self.ok:
            return
        if name not in self.music:
            self._pending_music = name
            return
        if self.current_music == name and self.channel and self.channel.get_busy():
            return
        self.stop_music()
        self.current_music = name
        snd = self.music[name]
        snd.set_volume(self.music_vol)
        self.channel = pygame.mixer.Channel(0)
        self.channel.play(snd, loops=-1, fade_ms=600)

    def stop_music(self):
        self._pending_music = None
        if self.ok and self.channel:
            self.channel.fadeout(300)
        self.current_music = None
        self.channel = None
