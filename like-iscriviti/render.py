#!/usr/bin/env python3
"""
Animazione "Mi piace + Iscriviti" (stile YouTube) con canale alpha per DaVinci Resolve.

Ogni frame e' una funzione pura del tempo T = frame / FPS: nessun orologio reale,
nessuna casualita'. Il rendering usa Skia (antialiasing, blur gaussiano, gruppi
con opacita' via saveLayer) e i frame RGBA non premoltiplicati vengono passati
direttamente a ffmpeg, che produce un MOV ProRes 4444 con alpha.

Uso rapido:
    python3 render.py                                  # -> like-iscriviti.mov
    python3 render.py --like-text Like --subscribe-text Subscribe \
                      --subscribed-text Subscribed --out like-subscribe.mov
    python3 render.py --x 960 --y 900                  # sposta il gruppo (centro)
    python3 render.py --png-dir frames                 # salva anche frame_0001.png ...
"""

import argparse
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

W, H, FPS, DURATION = 1920, 1080, 30, 5.0
NFRAMES = int(round(FPS * DURATION))  # 150

# ---------------------------------------------------------------- colori
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (0x27, 0x27, 0x27)
RED = (0xFF, 0x00, 0x00)
BLUE = (0x3E, 0xA6, 0xFF)

# ---------------------------------------------------------------- icone (Lucide, viewBox 24x24)
THUMB_OUTLINE = (
    "M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4"
    "a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2"
    "a3.13 3.13 0 0 1 3 3.88Z"
)
THUMB_CUFF = "M7 10v12"
BELL_BODY = (
    "M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673"
    "C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326Z"
)
BELL_CLAPPER = "M10.268 21a2 2 0 0 0 3.464 0"
LUCIDE_STROKE = 1.8  # in unita' del viewBox 24


def svg_path(d):
    """Parser minimale di path SVG (M L H V C A Z, assoluti e relativi)."""
    tokens = re.findall(r"[MmLlHhVvCcAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", d)
    p = skia.Path()
    i, cmd = 0, None
    cx = cy = sx = sy = 0.0

    def num():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                p.close()
                cx, cy = sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (cx, cy) if rel else (0.0, 0.0)
        if c == "M":
            cx, cy = ox + num(), oy + num()
            p.moveTo(cx, cy)
            sx, sy = cx, cy
            cmd = "l" if rel else "L"  # coppie successive = lineto implicito
        elif c == "L":
            cx, cy = ox + num(), oy + num()
            p.lineTo(cx, cy)
        elif c == "H":
            cx = (cx if rel else 0.0) + num()
            p.lineTo(cx, cy)
        elif c == "V":
            cy = (cy if rel else 0.0) + num()
            p.lineTo(cx, cy)
        elif c == "C":
            x1, y1, x2, y2 = ox + num(), oy + num(), ox + num(), oy + num()
            cx, cy = ox + num(), oy + num()
            p.cubicTo(x1, y1, x2, y2, cx, cy)
        elif c == "A":
            rx, ry, rot = num(), num(), num()
            large, sweep = int(num()), int(num())
            cx, cy = ox + num(), oy + num()
            p.arcTo(rx, ry, rot,
                    skia.Path.ArcSize.kLarge_ArcSize if large else skia.Path.ArcSize.kSmall_ArcSize,
                    skia.PathDirection.kCW if sweep else skia.PathDirection.kCCW,
                    cx, cy)
        else:
            raise ValueError("comando SVG non supportato: " + cmd)
    return p


PATHS = {k: svg_path(v) for k, v in dict(
    thumb=THUMB_OUTLINE, cuff=THUMB_CUFF, bell=BELL_BODY, clapper=BELL_CLAPPER).items()}

# ---------------------------------------------------------------- easing / helper


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, t0, t1):
    return clamp01((t - t0) / (t1 - t0))


def ease_out_back(u, s=1.70158):
    u -= 1.0
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def ease_in_out_cubic(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_out_cubic(u):
    return 1 - (1 - u) ** 3


def ease_in_cubic(u):
    return u ** 3


def ease_in_quad(u):
    return u * u


def lerp(a, b, u):
    return a + (b - a) * u


def color(rgb, a=1.0):
    a = max(0.0, min(1.0, a))
    return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(round(a * 255)))


def mix_rgb(c1, c2, u):
    # interpolazione in luce lineare: niente "fango" a meta' transizione
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    def srgb(v):
        v = 1.055 * v ** (1 / 2.4) - 0.055 if v > 0.0031308 else 12.92 * v
        return max(0, min(255, round(v * 255)))

    return tuple(srgb(lerp(lin(a), lin(b), u)) for a, b in zip(c1, c2))


def bump(u):
    """0 -> 1 -> 0, liscio (sin)."""
    return math.sin(math.pi * clamp01(u))


# ---------------------------------------------------------------- timeline (secondi)
T_LIKE_IN = (0.10, 0.70)
T_SUB_IN = (0.25, 0.85)
T_CUR_IN = (0.70, 1.45)
T_CUR_FADE = (0.70, 0.90)
T_CLICK_LIKE = 1.50
PRESS_DUR = 0.16
RING_DUR = 0.50
T_THUMB = (1.56, 2.00)
THUMB_FILL_DUR = 0.10
BURST_DUR = 0.64
T_CUR_TO_SUB = (1.70, 2.60)
T_CLICK_SUB = 2.70
T_SWAP = (2.75, 2.95)
T_BELL = (2.90, 3.90)
T_CUR_OUT = (3.30, 4.00)
T_OUT = (4.30, 4.85)


class Config:
    def __init__(self, a):
        self.like_text = a.like_text
        self.sub_text = a.subscribe_text
        self.subbed_text = a.subscribed_text
        self.cx = a.x
        self.cy = a.y

        self.f_medium = skia.Font(skia.Typeface.MakeFromFile(os.path.join(FONT_DIR, "Roboto-Medium.ttf")), 44)
        self.f_bold = skia.Font(skia.Typeface.MakeFromFile(os.path.join(FONT_DIR, "Roboto-Bold.ttf")), 44)
        for f in (self.f_medium, self.f_bold):
            f.setEdging(skia.Font.Edging.kAntiAlias)
            f.setSubpixel(True)
            f.setHinting(skia.FontHinting.kNone)
            f.setLinearMetrics(True)

        self.pill_h = 100
        self.gap = 32
        self.icon = 44           # pollice
        self.bell = 48           # campanella
        self.icon_gap = 14
        pad = 44

        like_w_txt = self.f_medium.measureText(self.like_text)
        sub_w_txt = self.f_bold.measureText(self.sub_text)
        subbed_w_txt = self.f_medium.measureText(self.subbed_text)
        # larghezze di design (330 / 420), allargate solo se il testo non ci sta
        self.like_w = max(330, math.ceil(2 * pad + self.icon + self.icon_gap + like_w_txt))
        self.sub_w = max(420, math.ceil(2 * pad + sub_w_txt),
                         math.ceil(2 * pad + self.bell + self.icon_gap + subbed_w_txt))

        total = self.like_w + self.gap + self.sub_w
        left = self.cx - total / 2
        self.like_cx = left + self.like_w / 2
        self.sub_cx = left + self.like_w + self.gap + self.sub_w / 2
        # default: Mi piace x 569-899 (centro 734), Iscriviti x 931-1351 (centro 1141)

        # bersagli del cursore (punta), relativi ai centri delle pillole
        self.cur_start = (self.cx + 600, self.cy + 340)          # (1560, 880)
        self.cur_like = (self.like_cx + 1, self.cy + 45)         # (735, 585)
        self.cur_sub = (self.sub_cx + 49, self.cy + 45)          # (1190, 585)
        self.cur_exit = (self.cx + 660, self.cy + 400)


# ---------------------------------------------------------------- disegno


def text_baseline(font, cy):
    m = font.getMetrics()
    return cy + m.fCapHeight / 2


def draw_icon(canvas, key, cx, cy, size, rgb, alpha, mode, extra=None):
    """Disegna un'icona Lucide 24x24 centrata in (cx,cy) e grande `size` px."""
    s = size / 24.0
    canvas.save()
    canvas.translate(cx, cy)
    canvas.scale(s, s)
    canvas.translate(-12, -12)
    paint = skia.Paint(AntiAlias=True, Color=color(rgb, alpha))
    if mode == "stroke":
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(LUCIDE_STROKE)
        paint.setStrokeCap(skia.Paint.kRound_Cap)
        paint.setStrokeJoin(skia.Paint.kRound_Join)
    else:
        paint.setStyle(skia.Paint.kFill_Style)
    canvas.drawPath(PATHS[key], paint)
    if extra:
        extra(canvas)
    canvas.restore()


def stroke_paint(rgb, alpha, width):
    p = skia.Paint(AntiAlias=True, Color=color(rgb, alpha), Style=skia.Paint.kStroke_Style,
                   StrokeWidth=width)
    p.setStrokeCap(skia.Paint.kRound_Cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def pill_layer(canvas, cx, cy, w, h, scale, alpha, bg_rgb, content):
    """Pillola con ombra: un unico layer (opacita' di gruppo corretta)."""
    if alpha <= 0.0005 or scale <= 0:
        return
    canvas.save()
    canvas.translate(cx, cy)
    canvas.scale(scale, scale)
    canvas.saveLayerAlpha(None, int(round(clamp01(alpha) * 255)))
    rect = skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h)
    rr = skia.RRect.MakeRectXY(rect, h / 2, h / 2)
    # ombra: nero 35%, blur 22 px (sigma = 11), offset y 10
    shadow = skia.Paint(AntiAlias=True, Color=color(BLACK, 0.35),
                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 11.0))
    canvas.save()
    canvas.translate(0, 10)
    canvas.drawRRect(rr, shadow)
    canvas.restore()
    canvas.drawRRect(rr, skia.Paint(AntiAlias=True, Color=color(bg_rgb)))
    content(canvas)
    canvas.restore()
    canvas.restore()


CURSOR_PTS = [(0, 0), (0, 17.2), (4.1, 13.3), (7.0, 19.6), (9.6, 18.5), (6.8, 12.3), (12.4, 12.3)]


def cursor_path():
    p = skia.Path()
    p.moveTo(*CURSOR_PTS[0])
    for pt in CURSOR_PTS[1:]:
        p.lineTo(*pt)
    p.close()
    return p


CURSOR_PATH = cursor_path()


def draw_cursor(canvas, x, y, alpha, scale=1.0):
    if alpha <= 0.0005:
        return
    s = 60.0 / 19.6 * scale  # ~60 px di altezza
    canvas.save()
    canvas.translate(x, y)
    canvas.scale(s, s)
    canvas.saveLayerAlpha(None, int(round(clamp01(alpha) * 255)))
    sh = skia.Paint(AntiAlias=True, Color=color(BLACK, 0.45),
                    MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4.0 / s))
    canvas.save()
    canvas.translate(1.2 / s * 2, 4.0 / s)
    canvas.drawPath(CURSOR_PATH, sh)
    canvas.restore()
    canvas.drawPath(CURSOR_PATH, skia.Paint(AntiAlias=True, Color=color(WHITE)))
    border = stroke_paint(BLACK, 1.0, 2.6 / s)
    canvas.drawPath(CURSOR_PATH, border)
    canvas.restore()
    canvas.restore()


# ---------------------------------------------------------------- stato animato


def appear(t, t0, t1):
    u = prog(t, t0, t1)
    scale = lerp(0.55, 1.0, ease_out_back(u)) if u > 0 else 0.55
    alpha = ease_out_cubic(prog(t, t0, t0 + (t1 - t0) * 0.55))
    return scale, alpha


def press(t, t_click):
    u = prog(t, t_click, t_click + PRESS_DUR)
    return 1.0 - 0.07 * bump(u) if 0 < u < 1 else 1.0


def disappear(t):
    u = prog(t, *T_OUT)
    return lerp(1.0, 0.65, ease_in_cubic(u)), 1.0 - ease_in_quad(u)


def cursor_state(t, c):
    if t < T_CUR_IN[0]:
        return c.cur_start, 0.0
    alpha = ease_out_cubic(prog(t, *T_CUR_FADE))
    if t < T_CUR_TO_SUB[0]:
        u = ease_in_out_cubic(prog(t, *T_CUR_IN))
        pos = (lerp(c.cur_start[0], c.cur_like[0], u), lerp(c.cur_start[1], c.cur_like[1], u))
    elif t < T_CUR_OUT[0]:
        u = ease_in_out_cubic(prog(t, *T_CUR_TO_SUB))
        pos = (lerp(c.cur_like[0], c.cur_sub[0], u), lerp(c.cur_like[1], c.cur_sub[1], u))
    else:
        u = prog(t, *T_CUR_OUT)
        e = ease_in_cubic(u)
        pos = (lerp(c.cur_sub[0], c.cur_exit[0], e), lerp(c.cur_sub[1], c.cur_exit[1], e))
        alpha *= 1.0 - ease_out_cubic(prog(t, T_CUR_OUT[0] + 0.15, T_CUR_OUT[1]))
    return pos, alpha


def bell_angle(t):
    u = prog(t, *T_BELL)
    if u <= 0 or u >= 1:
        return 0.0
    cycles = 3.5
    env = (1 - u) ** 2
    # normalizza in modo che il primo picco valga esattamente 26 gradi
    u_peak = 1 / (4 * cycles)
    norm = 26.0 / ((1 - u_peak) ** 2)
    return norm * env * math.sin(2 * math.pi * cycles * u)


def ring(canvas, t, t_click, pos):
    u = prog(t, t_click, t_click + RING_DUR)
    if not 0 < u < 1:
        return
    r = lerp(12, 52, ease_out_cubic(u))
    a = (1 - u) ** 1.5
    canvas.drawCircle(pos[0], pos[1], r, stroke_paint(WHITE, a * 0.95, lerp(4.0, 1.5, u)))


def burst(canvas, t, center):
    u = prog(t, T_THUMB[0], T_THUMB[0] + BURST_DUR)
    if not 0 < u < 1:
        return
    e = ease_out_cubic(u)
    r_out = lerp(34, 92, e)
    length = lerp(18, 8, u)
    a = 1 - ease_in_quad(u)
    for k in range(6):
        ang = math.radians(-90 + k * 60)
        rgb = WHITE if k % 2 == 0 else BLUE
        x0, y0 = center[0] + math.cos(ang) * (r_out - length), center[1] + math.sin(ang) * (r_out - length)
        x1, y1 = center[0] + math.cos(ang) * r_out, center[1] + math.sin(ang) * r_out
        canvas.drawLine(x0, y0, x1, y1, stroke_paint(rgb, a, 4.5))


# ---------------------------------------------------------------- frame


def render_frame(canvas, t, c):
    canvas.clear(skia.ColorTRANSPARENT)
    out_scale, out_alpha = disappear(t)

    # --- Mi piace
    like_scale, like_alpha = appear(t, *T_LIKE_IN)
    like_scale *= press(t, T_CLICK_LIKE) * out_scale
    like_alpha *= out_alpha

    content_w = c.icon + c.icon_gap + c.f_medium.measureText(c.like_text)
    icon_cx = -content_w / 2 + c.icon / 2           # coordinate locali della pillola
    text_x = -content_w / 2 + c.icon + c.icon_gap

    ut = prog(t, *T_THUMB)
    thumb_rot = -22.0 * bump(ut)
    thumb_scale = 1.0 + 0.5 * bump(ut)
    fill_a = ease_out_cubic(prog(t, T_THUMB[0], T_THUMB[0] + THUMB_FILL_DUR))

    def like_content(cv):
        cv.save()
        cv.translate(icon_cx, 0)
        cv.rotate(thumb_rot)
        cv.scale(thumb_scale, thumb_scale)
        if fill_a < 1:
            draw_icon(cv, "thumb", 0, 0, c.icon, WHITE, 1 - fill_a, "stroke")
            draw_icon(cv, "cuff", 0, 0, c.icon, WHITE, 1 - fill_a, "stroke")
        if fill_a > 0:
            def cuff_line(cc):
                # linea del polsino ritagliata nel pieno, come l'icona "filled"
                cc.drawPath(PATHS["cuff"], stroke_paint(GREY, fill_a, LUCIDE_STROKE * 0.85))
            draw_icon(cv, "thumb", 0, 0, c.icon, WHITE, fill_a, "stroke")
            draw_icon(cv, "thumb", 0, 0, c.icon, WHITE, fill_a, "fill", extra=cuff_line)
        cv.restore()
        cv.drawString(c.like_text, text_x, text_baseline(c.f_medium, 0), c.f_medium,
                      skia.Paint(AntiAlias=True, Color=color(WHITE)))

    pill_layer(canvas, c.like_cx, c.cy, c.like_w, c.pill_h, like_scale, like_alpha, GREY, like_content)

    # --- Iscriviti / Iscritto
    sub_scale, sub_alpha = appear(t, *T_SUB_IN)
    sub_scale *= press(t, T_CLICK_SUB) * out_scale
    sub_alpha *= out_alpha
    k = ease_in_out_cubic(prog(t, *T_SWAP))
    bg = mix_rgb(RED, GREY, k)
    angle = bell_angle(t)

    k_old = 1 - prog(k, 0.0, 0.6)   # il vecchio contenuto sparisce per primo
    k_new = prog(k, 0.4, 1.0)       # il nuovo entra quando il vecchio e' quasi sparito

    def sub_content(cv):
        if k_old > 0:
            tw = c.f_bold.measureText(c.sub_text)
            cv.drawString(c.sub_text, -tw / 2, text_baseline(c.f_bold, 0), c.f_bold,
                          skia.Paint(AntiAlias=True, Color=color(WHITE, k_old)))
        if k_new > 0:
            tw = c.f_medium.measureText(c.subbed_text)
            cw = c.bell + c.icon_gap + tw
            bx = -cw / 2 + c.bell / 2
            cv.save()
            # perno in alto: sommita' della campana (y=2 nel viewBox 24)
            pivot_y = -c.bell / 2 + 2 * c.bell / 24
            cv.translate(bx, pivot_y)
            cv.rotate(angle)
            cv.translate(0, -pivot_y)

            def clapper(cc):
                cc.drawPath(PATHS["clapper"], stroke_paint(WHITE, k_new, 2.2))
            draw_icon(cv, "bell", 0, 0, c.bell, WHITE, k_new, "fill", extra=clapper)
            draw_icon(cv, "bell", 0, 0, c.bell, WHITE, k_new, "stroke")
            cv.restore()
            cv.drawString(c.subbed_text, -cw / 2 + c.bell + c.icon_gap,
                          text_baseline(c.f_medium, 0), c.f_medium,
                          skia.Paint(AntiAlias=True, Color=color(WHITE, k_new)))

    pill_layer(canvas, c.sub_cx, c.cy, c.sub_w, c.pill_h, sub_scale, sub_alpha, bg, sub_content)

    # --- effetti sopra le pillole
    s_like = like_scale
    thumb_center = (c.like_cx + icon_cx * s_like, c.cy)
    burst(canvas, t, thumb_center)
    ring(canvas, t, T_CLICK_LIKE, c.cur_like)
    ring(canvas, t, T_CLICK_SUB, c.cur_sub)

    # --- cursore
    pos, ca = cursor_state(t, c)
    cs = min(press(t, T_CLICK_LIKE), press(t, T_CLICK_SUB))
    draw_cursor(canvas, pos[0], pos[1], ca, scale=lerp(1.0, cs, 1.3) if cs < 1 else 1.0)


# ---------------------------------------------------------------- main


def frame_rgba(surface, canvas, t, c):
    render_frame(canvas, t, c)
    img = surface.makeImageSnapshot()
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    img.readPixels(info, arr, W * 4, 0, 0)
    return arr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--like-text", default="Mi piace")
    ap.add_argument("--subscribe-text", default="Iscriviti")
    ap.add_argument("--subscribed-text", default="Iscritto")
    ap.add_argument("--x", type=float, default=W / 2, help="centro orizzontale del gruppo (px, default 960)")
    ap.add_argument("--y", type=float, default=H / 2, help="centro verticale delle pillole (px, default 540)")
    ap.add_argument("--out", default=os.path.join(HERE, "like-iscriviti.mov"))
    ap.add_argument("--png-dir", default=None, help="salva anche la sequenza PNG RGBA (frame_0001.png ...)")
    ap.add_argument("--no-mov", action="store_true", help="solo PNG, niente MOV")
    a = ap.parse_args()

    c = Config(a)
    surface = skia.Surface.MakeRaster(
        skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    canvas = surface.getCanvas()

    if a.png_dir:
        os.makedirs(a.png_dir, exist_ok=True)

    ff = None
    if not a.no_mov:
        if not shutil.which("ffmpeg"):
            sys.exit("ffmpeg non trovato nel PATH")
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuva444p10le",
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
            "-alpha_bits", "16", "-vendor", "apl0",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-color_range", "tv", "-movflags", "+write_colr",
            a.out,
        ]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for f in range(NFRAMES):
        t = f / FPS
        arr = frame_rgba(surface, canvas, t, c)
        if ff:
            ff.stdin.write(arr.tobytes())
        if a.png_dir:
            img = skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType,
                                       alphaType=skia.kUnpremul_AlphaType)
            img.save(os.path.join(a.png_dir, f"frame_{f + 1:04d}.png"), skia.kPNG)
        if (f + 1) % 30 == 0 or f + 1 == NFRAMES:
            print(f"frame {f + 1}/{NFRAMES}", flush=True)
    if ff:
        ff.stdin.close()
        if ff.wait() != 0:
            sys.exit("ffmpeg ha restituito un errore")
        print("scritto", a.out)


if __name__ == "__main__":
    main()
