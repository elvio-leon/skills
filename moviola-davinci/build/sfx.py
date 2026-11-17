"""Procedurally synthesised sound effects (48 kHz, 24-bit WAV, royalty free)."""

from __future__ import annotations

import wave

import numpy as np
from scipy import signal

SR = 48000
rng = np.random.default_rng(7)


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
def t_axis(dur):
    return np.arange(int(SR * dur)) / SR


def noise(dur):
    return rng.standard_normal(int(SR * dur))


def env_ad(n, attack, decay_curve=4.0):
    """Attack then exponential-ish decay envelope of length n samples."""
    a = max(int(attack * SR), 1)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    rest = n - a
    if rest > 0:
        e[a:] = np.exp(-decay_curve * np.linspace(0, 1, rest))
    return e


def sweep_bandpass(x, f_start, f_peak, f_end, q=2.0, peak_at=0.5):
    """Band-pass with a centre frequency that moves over time (block-wise)."""
    n = len(x)
    out = np.zeros(n)
    block = 256
    zi = None
    for i in range(0, n, block):
        p = i / n
        if p < peak_at:
            f = f_start * (f_peak / f_start) ** (p / peak_at)
        else:
            f = f_peak * (f_end / f_peak) ** ((p - peak_at) / (1 - peak_at))
        bw = f / q
        lo, hi = max(f - bw / 2, 20), min(f + bw / 2, SR / 2 - 100)
        b, a = signal.butter(2, [lo, hi], btype="band", fs=SR)
        if zi is None:
            zi = signal.lfilter_zi(b, a) * 0
        seg, zi = signal.lfilter(b, a, x[i:i + block], zi=zi)
        out[i:i + block] = seg
    return out


def lowpass(x, f, order=4):
    b, a = signal.butter(order, f, btype="low", fs=SR)
    return signal.lfilter(b, a, x)


def highpass(x, f, order=2):
    b, a = signal.butter(order, f, btype="high", fs=SR)
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo, hi], btype="band", fs=SR)
    return signal.lfilter(b, a, x)


def chirp_sine(dur, f0, f1, curve="exp"):
    t = t_axis(dur)
    if curve == "exp":
        f = f0 * (f1 / f0) ** (t / dur)
    else:
        f = f0 + (f1 - f0) * t / dur
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def bell(freq, dur, partials=((1, 1.0), (2.76, 0.4), (5.4, 0.2), (8.93, 0.08)), decay=5.0):
    t = t_axis(dur)
    y = np.zeros_like(t)
    for mult, amp in partials:
        y += amp * np.sin(2 * np.pi * freq * mult * t) * np.exp(-decay * mult ** 0.5 * t)
    return y * env_ad(len(t), 0.002, 0.0)


def place(total, parts):
    """Mix (offset_seconds, samples) pairs into one buffer."""
    out = np.zeros(int(SR * total))
    for off, x in parts:
        i = int(off * SR)
        j = min(i + len(x), len(out))
        out[i:j] += x[: j - i]
    return out


def pan(mono, positions):
    """Stereo pan with a per-sample position array (-1 left, +1 right)."""
    p = (positions + 1) * np.pi / 4
    return np.stack([mono * np.cos(p), mono * np.sin(p)], -1)


def fade_out(x, sec=0.01):
    n = min(int(sec * SR), len(x))
    x = x.copy()
    x[-n:] *= np.linspace(1, 0, n)[:, None] if x.ndim == 2 else np.linspace(1, 0, n)
    return x


def normalize(x, peak_db=-1.0):
    x = x - np.mean(x, axis=0)
    peak = np.max(np.abs(x)) or 1
    return x / peak * 10 ** (peak_db / 20)


def write_wav(path, x):
    x = fade_out(normalize(x))
    if x.ndim == 1:
        x = x[:, None]
    pcm = np.clip(x, -1, 1)
    ints = (pcm * (2 ** 23 - 1)).astype("<i4")
    raw = ints.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(raw)


# --------------------------------------------------------------------------- #
# Sounds
# --------------------------------------------------------------------------- #
def whoosh(dur=0.7, f0=250, fp=2500, f1=400, peak=0.45):
    x = sweep_bandpass(noise(dur), f0, fp, f1, q=1.6, peak_at=peak)
    t = t_axis(dur)
    e = np.where(t < dur * peak, (t / (dur * peak)) ** 2, np.exp(-5 * (t - dur * peak) / (dur * (1 - peak))))
    mono = x * e
    return pan(mono, np.linspace(-0.6, 0.6, len(mono)))


def whoosh_slow():
    return whoosh(1.4, 150, 1400, 250, 0.55)


def swipe():
    x = sweep_bandpass(noise(0.35), 1200, 6000, 3000, q=2.5, peak_at=0.35)
    mono = x * env_ad(len(x), 0.05, 6)
    return pan(mono, np.linspace(-1, 1, len(mono)))


def riser(dur=3.0):
    t = t_axis(dur)
    n = sweep_bandpass(noise(dur), 200, 8000, 9000, q=1.2, peak_at=0.98)
    tone = sum(chirp_sine(dur, 110 * m, 880 * m) * a for m, a in ((1, 0.5), (1.5, 0.3), (2, 0.2)))
    tone *= 1 + 0.3 * np.sin(2 * np.pi * (3 + 9 * t / dur) * t)
    y = (0.8 * n + 0.35 * tone) * (t / dur) ** 2.2
    return pan(y, 0.4 * np.sin(2 * np.pi * 0.7 * t))


def impact(dur=2.2):
    t = t_axis(dur)
    sub = chirp_sine(dur, 90, 32) * np.exp(-2.2 * t)
    body = lowpass(noise(dur), 900) * np.exp(-9 * t) * 2.5
    click = highpass(noise(0.02), 2000) * env_ad(int(0.02 * SR), 0.0005, 8)
    y = np.tanh(1.8 * (sub + body)) + place(dur, [(0, click * 0.6)])
    rev = lowpass(noise(dur), 2500) * np.exp(-2.5 * t) * 0.08
    return y + rev


def meme_boom(dur=1.6):
    t = t_axis(dur)
    y = chirp_sine(dur, 75, 45) * np.exp(-2.8 * t)
    y += 0.5 * chirp_sine(dur, 150, 90) * np.exp(-5 * t)
    return np.tanh(3.2 * y) * env_ad(len(t), 0.004, 0.0)


def pop():
    y = chirp_sine(0.12, 1100, 250) * env_ad(int(0.12 * SR), 0.001, 7)
    return y + 0.15 * highpass(noise(0.12), 3000) * env_ad(int(0.12 * SR), 0.0005, 40)


def click():
    c1 = bandpass(noise(0.012), 1500, 7000) * env_ad(int(0.012 * SR), 0.0003, 9)
    c2 = bandpass(noise(0.012), 1200, 5000) * env_ad(int(0.012 * SR), 0.0003, 9) * 0.7
    return place(0.09, [(0, c1), (0.055, c2)])


def key_stroke(seed_shift=0.0):
    d = 0.07
    body = bandpass(noise(d), 800 + 400 * seed_shift, 4500) * env_ad(int(d * SR), 0.0004, 12)
    thock = np.sin(2 * np.pi * (140 + 60 * seed_shift) * t_axis(d)) * env_ad(int(d * SR), 0.001, 18) * 0.6
    return body + thock


def typewriter_loop(dur=4.0):
    parts, t = [], 0.02
    while t < dur - 0.1:
        parts.append((t, key_stroke(rng.random()) * (0.6 + 0.4 * rng.random())))
        t += rng.uniform(0.07, 0.19)
    return place(dur, parts)


def typewriter_ding():
    return place(1.6, [(0.0, key_stroke(0.2)), (0.08, bell(2093, 1.5, decay=2.5) * 0.6)])


def notification():
    return place(1.2, [(0, bell(1318.5, 1.0, decay=4)), (0.12, bell(1975.5, 1.0, decay=4))])


def success():
    notes = [523.25, 659.25, 783.99, 1046.5]
    return place(1.6, [(i * 0.09, bell(f, 1.2, decay=3.5) * (0.8 + 0.1 * i)) for i, f in enumerate(notes)])


def error():
    t = t_axis(0.22)
    tone = signal.square(2 * np.pi * 120 * t) * 0.5 + signal.square(2 * np.pi * 126 * t) * 0.5
    tone = lowpass(tone, 2500) * env_ad(len(t), 0.005, 1.5)
    return place(0.6, [(0, tone), (0.28, tone)])


def glitch(dur=0.9):
    out = np.zeros(int(SR * dur))
    i = 0
    while i < len(out):
        n = int(rng.uniform(0.015, 0.08) * SR)
        kind = rng.integers(0, 4)
        t = np.arange(n) / SR
        if kind == 0:
            seg = signal.square(2 * np.pi * rng.uniform(80, 1200) * t)
        elif kind == 1:
            seg = noise(n / SR)
            step = rng.integers(8, 40)
            seg = np.repeat(seg[::step], step)[:n]
        elif kind == 2:
            seg = np.sin(2 * np.pi * rng.uniform(2000, 6000) * t)
        else:
            seg = np.zeros(n)
        seg = np.round(seg * 6) / 6 * rng.uniform(0.3, 1)
        out[i:i + n] = seg[: len(out) - i]
        i += n
    return lowpass(out, 9000)


def shutter():
    a = bandpass(noise(0.03), 1500, 9000) * env_ad(int(0.03 * SR), 0.0005, 10)
    b = bandpass(noise(0.05), 800, 6000) * env_ad(int(0.05 * SR), 0.0005, 7) * 0.8
    thunk = np.sin(2 * np.pi * 180 * t_axis(0.05)) * env_ad(int(0.05 * SR), 0.001, 12) * 0.4
    return place(0.25, [(0, a), (0.09, b + thunk)])


def tick_tock(dur=4.0):
    tick = bandpass(noise(0.02), 3000, 9000) * env_ad(int(0.02 * SR), 0.0003, 14)
    tock = bandpass(noise(0.025), 1200, 4000) * env_ad(int(0.025 * SR), 0.0003, 12)
    return place(dur, [(k * 0.5, tick if k % 2 == 0 else tock) for k in range(int(dur / 0.5))])


def bass_drop(dur=2.5):
    t = t_axis(dur)
    y = chirp_sine(dur, 160, 38) * np.clip(t / 0.03, 0, 1) * np.exp(-0.9 * t)
    return np.tanh(2.5 * y)


def cash():
    coins = [(0.12 + k * 0.035 + rng.uniform(0, 0.02),
              bell(rng.uniform(3500, 5500), 0.25, partials=((1, 1), (2.3, 0.5)), decay=18) * 0.35)
             for k in range(10)]
    drawer = lowpass(noise(0.08), 1500) * env_ad(int(0.08 * SR), 0.001, 6) * 0.8
    return place(1.3, [(0, drawer), (0.05, bell(2637, 1.1, decay=3.5) * 0.9)] + coins)


def heartbeat(dur=3.0):
    beat = np.sin(2 * np.pi * 55 * t_axis(0.15)) * env_ad(int(0.15 * SR), 0.005, 9)
    parts = []
    for k in range(int(dur / 0.85)):
        parts += [(k * 0.85, beat), (k * 0.85 + 0.22, beat * 0.7)]
    return np.tanh(2 * place(dur, parts))


def suspense(dur=5.0):
    t = t_axis(dur)
    y = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * a
            for f, a in ((55, 0.6), (58.3, 0.5), (82.4, 0.3), (110.5, 0.2)))
    y *= np.clip(t / 1.5, 0, 1) * np.clip((dur - t) / 1.0, 0, 1)
    air = lowpass(noise(dur), 600) * 0.15 * np.clip(t / dur, 0, 1)
    return pan(y + air, 0.3 * np.sin(2 * np.pi * 0.1 * t))


def ding():
    return bell(1760, 1.4, decay=3.2)


SOUNDS = [
    ("Transizioni", "whoosh_veloce", whoosh, "Passaggio rapido: tagli, zoom, whip pan"),
    ("Transizioni", "whoosh_lento", whoosh_slow, "Passaggio ampio per transizioni lente"),
    ("Transizioni", "swipe", swipe, "Swipe breve da sinistra a destra (grafiche, testi)"),
    ("Transizioni", "riser_3s", riser, "Crescendo di tensione prima di una rivelazione"),
    ("Impatti", "impatto_boom", impact, "Colpo cinematografico profondo"),
    ("Impatti", "boom_meme", meme_boom, "Boom saturato stile meme per momenti comici"),
    ("Impatti", "bass_drop", bass_drop, "Caduta di basso per il drop o il reveal"),
    ("UI", "pop", pop, "Comparsa di testi, emoji, icone"),
    ("UI", "click_mouse", click, "Click sul pulsante iscriviti / tutorial"),
    ("UI", "notifica_ding", notification, "Notifica / campanella"),
    ("UI", "successo", success, "Obiettivo raggiunto, risposta giusta"),
    ("UI", "errore", error, "Risposta sbagliata, errore"),
    ("UI", "ding", ding, "Ding singolo per evidenziare un punto"),
    ("Testo", "macchina_da_scrivere_loop", typewriter_loop, "Da abbinare al titolo Macchina da Scrivere"),
    ("Testo", "macchina_da_scrivere_ding", typewriter_ding, "Fine riga della macchina da scrivere"),
    ("Varie", "glitch_digitale", glitch, "Da abbinare a transizione/titolo Glitch"),
    ("Varie", "scatto_fotocamera", shutter, "Fermo immagine, foto, screenshot"),
    ("Varie", "tic_tac_orologio", tick_tock, "Tempo che passa, countdown"),
    ("Varie", "cassa_soldi", cash, "Soldi, guadagni, prezzi"),
    ("Varie", "battito_cuore", heartbeat, "Tensione, suspense"),
    ("Varie", "drone_suspense", suspense, "Tappeto sonoro di tensione"),
]
