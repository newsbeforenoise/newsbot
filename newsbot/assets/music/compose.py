"""Original, royalty-free background loops for the News Before Noise reels.
Pure synthesis (numpy) - no samples, no third-party audio."""
import sys
import numpy as np
from scipy.signal import butter, sosfilt
import wave

SR = 44100
rng = np.random.default_rng(7)

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[n] + 12 * (o + 1) - 69) / 12)


def lp(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "low", fs=SR, output="sos"), x)


def hp(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "high", fs=SR, output="sos"), x)


def env(n, a, d, s, r, total):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    hold = max(total - a - d - r, 0)
    e = np.concatenate([np.linspace(0, 1, a, False), np.linspace(1, s, d, False), np.full(hold, s),
                        np.linspace(s, 0, r)])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def epiano(f, dur, vel=0.5):
    """Warm Rhodes-ish tone: sine + soft bell partial, gentle tremolo."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 3)
            + 0.08 * np.sin(2 * np.pi * 7.01 * f * t) * np.exp(-t * 9))
    tone *= 1 + 0.08 * np.sin(2 * np.pi * 4.2 * t)
    return vel * tone * env(n, 0.01, 0.6, 0.45, 0.6, n)


def pad(f, dur, vel=0.18):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * (1 + d) * t + p) for d, p in [(-0.004, 0), (0, 1.3), (0.005, 2.1)])
    return lp(vel * x / 3 * env(n, 0.9, 0.5, 0.8, 1.2, n), 1800)


def bass(f, dur, vel=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return vel * np.sin(2 * np.pi * f * t) * env(n, 0.01, 0.25, 0.6, 0.15, n)


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 70 * np.exp(-t * 30)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def snare():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 1500) * np.exp(-t * 18)
    return 0.22 * noise + 0.12 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)


def hat(vel=0.08):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return vel * hp(rng.standard_normal(n), 7000) * np.exp(-t * 70)


def add(buf, x, at):
    i = int(at * SR)
    end = min(i + len(x), len(buf))
    if i < len(buf):
        buf[i:end] += x[: end - i]


def chord_notes(sym):
    """'Fmaj7/4' -> list of note names in octave 4."""
    return sym


def song(prog, bpm, bars, swing=0.0, drums=True, arp=True, seed=1):
    beat = 60 / bpm
    total = bars * 4 * beat + 2.0
    L = np.zeros(int(total * SR))
    R = np.zeros(int(total * SR))
    r = np.random.default_rng(seed)
    for bar in range(bars):
        notes, root = prog[bar % len(prog)]
        t0 = bar * 4 * beat
        # chord: strum slightly
        for k, nm in enumerate(notes):
            x = epiano(hz(nm), 4 * beat + 0.4, 0.22)
            pan = 0.35 + 0.3 * k / max(len(notes) - 1, 1)
            add(L, x * (1 - pan), t0 + 0.012 * k)
            add(R, x * pan, t0 + 0.012 * k)
            p = pad(hz(nm) / 2, 4 * beat + 1.0)
            add(L, p, t0); add(R, p, t0)
        # bass: root on 1 and the "and" of 3
        add(L, bass(hz(root), 1.6 * beat), t0); add(R, bass(hz(root), 1.6 * beat), t0)
        add(L, bass(hz(root), 1.0 * beat, 0.35), t0 + 2.5 * beat); add(R, bass(hz(root), 1.0 * beat, 0.35), t0 + 2.5 * beat)
        if arp:
            seq = notes + notes[::-1][1:-1]
            for i in range(8):
                at = t0 + i * beat / 2 + (swing * beat / 2 if i % 2 else 0)
                nm = seq[i % len(seq)]
                f = hz(nm) * 2
                x = epiano(f, 0.5, 0.07 + 0.03 * r.random())
                pan = 0.2 + 0.6 * r.random()
                add(L, x * (1 - pan), at); add(R, x * pan, at)
        if drums and bar >= 1:
            for b in range(4):
                at = t0 + b * beat
                if b in (0, 2):
                    add(L, kick() * 0.55, at); add(R, kick() * 0.55, at)
                if b in (1, 3):
                    s = snare(); add(L, s, at); add(R, s * 0.9, at)
                for h in range(2):
                    hat_at = at + h * beat / 2 + (swing * beat / 2 if h else 0)
                    x = hat(0.05 + 0.03 * r.random()); add(L, x * 0.7, hat_at); add(R, x, hat_at)
    # lo-fi warmth: gentle low-pass, a little vinyl hiss, soft saturation
    hiss = lp(rng.standard_normal(len(L)), 6000) * 0.004
    L = np.tanh(1.3 * lp(L, 9000) + hiss)
    R = np.tanh(1.3 * lp(R, 9000) + hiss)
    # simple stereo room reverb (a few decaying echoes)
    for d, g in [(0.031, 0.18), (0.047, 0.14), (0.089, 0.1), (0.143, 0.07)]:
        k = int(d * SR)
        L[k:] += g * R[:-k]
        R[k:] += g * L[:-k]
    st = np.stack([L, R], 1)
    st /= np.max(np.abs(st)) + 1e-9
    st *= 0.6
    # fades
    n = len(st)
    fi, fo = int(0.6 * SR), int(2.5 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return st


TRACKS = {
    # 1) warm lo-fi, Fmaj7 - Em7 - Dm7 - Cmaj7
    "nbn_lofi_sunrise": dict(prog=[(["F3", "A3", "C4", "E4"], "F2"), (["E3", "G3", "B3", "D4"], "E2"),
                                   (["D3", "F3", "A3", "C4"], "D2"), (["C3", "E3", "G3", "B3"], "C2")],
                             bpm=84, bars=10, swing=0.18, seed=1),
    # 2) calm & hopeful, Am9 feel - Fmaj7 - Cmaj7 - G6
    "nbn_calm_open": dict(prog=[(["A3", "C4", "E4", "B4"], "A2"), (["F3", "A3", "C4", "E4"], "F2"),
                                (["C3", "E3", "G3", "B3"], "C2"), (["G3", "B3", "D4", "E4"], "G2")],
                          bpm=90, bars=11, swing=0.1, seed=2),
    # 3) soft focus, Dmaj7 - Bm7 - Gmaj7 - A6 (no snare-heavy feel: lighter drums)
    "nbn_soft_focus": dict(prog=[(["D3", "F#3", "A3", "C#4"], "D2"), (["B2", "D3", "F#3", "A3"], "B1"),
                                 (["G3", "B3", "D4", "F#4"], "G2"), (["A3", "C#4", "E4", "F#4"], "A2")],
                           bpm=78, bars=9, swing=0.15, seed=3),
}

if __name__ == "__main__":
    out = sys.argv[1]
    for name, kw in TRACKS.items():
        st = song(**kw)
        pcm = (st * 32767).astype("<i2")
        with wave.open(f"{out}/{name}.wav", "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        print(name, round(len(st) / SR, 1), "s")
