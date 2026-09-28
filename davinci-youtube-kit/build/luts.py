"""Creative color looks exported as 33-point .cube LUTs (Rec.709 in / out)."""

from __future__ import annotations

import numpy as np

SIZE = 33


def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def saturation(c, s):
    y = luma(c)[..., None]
    return y + (c - y) * s


def contrast(c, k, pivot=0.45):
    """Soft S-curve contrast (k > 1 adds contrast)."""
    x = np.clip(c, 0, 1)
    lo = pivot * (x / pivot) ** k
    hi = 1 - (1 - pivot) * ((1 - x) / (1 - pivot)) ** k
    return np.where(x < pivot, lo, hi)


def fade(c, black=0.0, white=1.0):
    return black + c * (white - black)


def split_tone(c, shadow_rgb, highlight_rgb, amount=1.0):
    y = luma(c)[..., None]
    ws = (1 - y) ** 2
    wh = y ** 2
    return c + amount * (ws * np.array(shadow_rgb) + wh * np.array(highlight_rgb))


def gamma(c, g):
    return np.clip(c, 0, 1) ** (1 / g)


def skin_protect(orig, graded, amount=0.5):
    """Pull orange/skin hues back toward the original so faces stay natural."""
    r, g, b = orig[..., 0], orig[..., 1], orig[..., 2]
    skin = np.clip(1 - np.abs((r - g) / (r + 1e-4) - 0.28) * 3, 0, 1) * (r > g) * (g > b)
    skin = skin[..., None] * amount
    return graded * (1 - skin) + orig * skin


def teal_orange(c):
    o = c
    c = contrast(c, 1.12)
    c = split_tone(c, (-0.06, 0.02, 0.07), (0.05, 0.018, -0.045))
    y = luma(c)[..., None]
    warm = np.clip((c[..., 0] - c[..., 2])[..., None] * 3, 0, 1)
    c = y + (c - y) * (1.0 + 0.25 * warm)  # boost warm hues
    c = skin_protect(o, c, 0.25)
    return saturation(c, 1.08)


def warm_cinema(c):
    c = contrast(c, 1.08)
    c = split_tone(c, (0.02, 0.0, -0.03), (0.08, 0.04, -0.06))
    c = fade(c, 0.02, 0.98)
    return saturation(c, 1.05)


def cool_modern(c):
    c = contrast(c, 1.1)
    c = split_tone(c, (-0.03, 0.0, 0.05), (-0.02, 0.01, 0.04))
    c = saturation(c, 0.9)
    return gamma(c, 1.03)


def vintage(c):
    c = saturation(c, 0.72)
    c = split_tone(c, (0.02, 0.03, 0.0), (0.06, 0.03, -0.05))
    c = contrast(c, 0.92)
    c = fade(c, 0.07, 0.94)
    c[..., 1] = c[..., 1] * 0.98 + 0.01
    return c


def moody(c):
    c = gamma(c, 0.9)
    c = contrast(c, 1.18)
    c = split_tone(c, (-0.02, 0.01, 0.03), (0.03, 0.015, -0.02))
    c = saturation(c, 0.75)
    return fade(c, 0.02, 0.95)


def vivid(c):
    c = contrast(c, 1.12)
    c = saturation(c, 1.35)
    return gamma(c, 1.04)


def bw_film(c):
    y = c[..., 0] * 0.3 + c[..., 1] * 0.59 + c[..., 2] * 0.11
    y = contrast(y[..., None].repeat(3, -1), 1.3)
    return fade(y, 0.015, 0.985)


def pastel(c):
    c = saturation(c, 0.82)
    c = contrast(c, 0.88)
    c = fade(c, 0.06, 1.0)
    c = split_tone(c, (0.02, 0.0, 0.04), (0.03, 0.02, 0.0))
    return gamma(c, 1.08)


LOOK_FUNCS = {
    "TealOrange": teal_orange,
    "CaldoCinema": warm_cinema,
    "FreddoModerno": cool_modern,
    "Vintage": vintage,
    "Moody": moody,
    "VivaceYT": vivid,
    "BiancoNeroFilm": bw_film,
    "Pastello": pastel,
}


def cube_text(key: str, title: str) -> str:
    x = np.linspace(0, 1, SIZE)
    # .cube order: red changes fastest, then green, then blue.
    b, g, r = np.meshgrid(x, x, x, indexing="ij")
    grid = np.stack([r, g, b], -1).reshape(-1, 3)
    out = np.clip(LOOK_FUNCS[key](grid.copy()), 0, 1)
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {SIZE}", "DOMAIN_MIN 0.0 0.0 0.0",
             "DOMAIN_MAX 1.0 1.0 1.0"]
    lines += [f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in out]
    return "\n".join(lines) + "\n"
