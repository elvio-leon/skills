"""Mattoni comuni dei template Moviola per DaVinci Resolve.

Il design system è quello di Moviola Studio: Anton per i titoli, Inter per le
informazioni, scrittura a mano (Shadows Into Light Two, Permanent Marker),
macchina da scrivere (Special Elite), Playfair Display per citazioni e giornali,
VT323 per le scritte video. Colori: carta #F5EFE6, rosso #B5323C, verde campo
#183A2F / #0C1F19, inchiostro #22324A. Crocini di registro, grana, carta.

Si scrive in pixel di un fotogramma 1920×1080 con l'origine in alto a sinistra
(come in Moviola Studio); gli helper convertono nelle coordinate Fusion
(0..1, y verso l'alto). Le durate sono in fotogrammi a 25 fps (F()).
"""
from __future__ import annotations

import math
import random

from fusion import LEN, R, T, Conn, Expr, Exposed, F, FuID, Macro, Raw, Tool, anim_curves, checkbox, clamp01, combo, lua_str, slider

W, H = 1920, 1080
FRAME = {"Width": 1920, "Height": 1080, "UseFrameFormatSettings": 1}

CARTA = (0.961, 0.937, 0.902)
CARTA_OMBRA = (0.914, 0.875, 0.804)
ROSSO = (0.710, 0.196, 0.235)
VERDE = (0.094, 0.227, 0.184)
VERDE_SCURO = (0.047, 0.122, 0.098)
INCHIOSTRO = (0.133, 0.196, 0.290)
NERO = (0.043, 0.051, 0.047)
FOSFORO = (0.486, 1.0, 0.608)
BIANCO = (1, 1, 1)

ANTON = ("Anton", "Regular")
INTER = ("Inter", "Regular")
INTER_B = ("Inter", "Bold")
MANO = ("Shadows Into Light Two", "Regular")
PENNARELLO = ("Permanent Marker", "Regular")
MACCHINA = ("Special Elite", "Regular")
SERIF_I = ("Playfair Display", "Italic")
SERIF_B = ("Playfair Display", "Bold")
VIDEO = ("VT323", "Regular")
GOTICO = ("UnifrakturMaguntia", "Book")


# --------------------------------------------------------------------------- coordinate
def nx(px):
    return round(px / W, 5)


def ny(py):
    return round(1 - py / H, 5)


def P(px, py):
    return (nx(px), ny(py))


def PE(xexpr, yexpr):
    """Point da espressioni in pixel (stringhe Lua)."""
    return Expr(f"Point(({xexpr})/{W}, 1-({yexpr})/{H})")


# --------------------------------------------------------------------------- easing (Lua)
def eo(x):
    return f"(1-(1-{x})^3)"


def eo5(x):
    return f"(1-(1-{x})^5)"


def ei(x):
    return f"(({x})^3)"


def eio(x):
    return f"(({x})<0.5 and 4*({x})^3 or 1-((-2*({x})+2)^3)/2)"


def eexpo(x):
    return f"(({x})>=1 and 1 or 1-2^(-10*({x})))"


def eback(x, k=1.70158):
    return f"(1+{k + 1}*(({x})-1)^3+{k}*(({x})-1)^2)"


def st(a, d):
    """Avanzamento 0..1 di una fase che parte al fotogramma a e dura d (a 25 fps),
    moltiplicato per il controllo 'Velocità' del template."""
    a = F(a) if isinstance(a, (int, float)) else a
    d = F(d) if isinstance(d, (int, float)) else d
    return clamp01(f"({T}-({a})*Ctrl.Speed)/max(({d})*Ctrl.Speed,1)")


OUT = clamp01(f"{R}/max(Ctrl.OutDur,1)")      # 1 → 0 negli ultimi fotogrammi
GLIDE = f"{eio(clamp01(f'{T}/{LEN}'))}"        # 0 → 1 su tutta la clip

BASE = {
    "Speed": slider("Velocità animazioni (1 = normale, 2 = più lenta)", 1, 0.3, 3, allowed=(0.05, 20)),
    "OutDur": slider("Durata uscita (fotogrammi)", 15, 1, 60, integer=True, allowed=(1, 600)),
}
BG_OPTS = ["Trasparente", "Verde campo", "Nero", "Carta"]


def ctrl_values(controls):
    return {k: v["INP_Default"] for k, v in controls.items() if "INP_Default" in v}


# --------------------------------------------------------------------------- nodi
def canvas(name="Canvas"):
    return Tool(name, "Background", {**FRAME, "TopLeftRed": 0, "TopLeftGreen": 0, "TopLeftBlue": 0, "TopLeftAlpha": 0})


def solid(name, rgb, mask=None, alpha=1, extra=None):
    i = {**FRAME, "TopLeftRed": rgb[0], "TopLeftGreen": rgb[1], "TopLeftBlue": rgb[2], "TopLeftAlpha": alpha}
    if mask:
        i["EffectMask"] = Conn(mask, "Mask")
    i.update(extra or {})
    return Tool(name, "Background", i)


def rect(name, x, y, w, h, angle=0, soft=0.0, prev=None, mode=None, extra=None):
    """Maschera rettangolare in pixel (centro x,y). Valori o espressioni Lua in pixel."""
    i = {"Center": _pt(x, y), "Width": _sz(w, W), "Height": _sz(h, H), "SoftEdge": soft}
    if angle:
        i["Angle"] = Expr(angle) if isinstance(angle, str) else angle
    if prev:
        i["EffectMask"] = Conn(prev, "Mask")
    if mode:
        i["PaintMode"] = FuID(mode)
    i.update(extra or {})
    return Tool(name, "RectangleMask", i)


def ellipse(name, x, y, w, h, soft=0.0, prev=None, mode=None, ring=None, extra=None):
    i = {"Center": _pt(x, y), "Width": _sz(w, W), "Height": _sz(h, H), "SoftEdge": soft}
    if prev:
        i["EffectMask"] = Conn(prev, "Mask")
    if mode:
        i["PaintMode"] = FuID(mode)
    if ring:
        i["Solid"] = 0
        i["BorderWidth"] = Expr(f"({ring})/{W}") if isinstance(ring, str) else round(ring / W, 5)
    i.update(extra or {})
    return Tool(name, "EllipseMask", i)


def _pt(x, y):
    if isinstance(x, str) or isinstance(y, str):
        return PE(x, y)
    return P(x, y)


def _sz(v, ref):
    if isinstance(v, str):
        return Expr(f"({v})/{ref}")
    return round(v / ref, 5)


def polyline_raw(pts, closed=True):
    """pts: offset in pixel dal centro della maschera (y verso il basso)."""
    rows = ",\n".join(f"{{ Linear = true, X = {dx / W:.5f}, Y = {-dy / W:.5f} }}" for dx, dy in pts)
    return Raw("Polyline {\n Closed = %s,\n Points = {\n%s\n }\n}" % ("true" if closed else "false", rows))


def poly(name, cx, cy, pts, closed=True, stroke=None, write=None, prev=None, mode=None, soft=0.0, extra=None):
    """Maschera poligonale. stroke = spessore in px per un contorno (Solid 0);
    write = espressione 0..1 per disegnarlo progressivamente."""
    i = {"MaskWidth": 1920, "MaskHeight": 1080, "PixelAspect": (1, 1), "ClippingMode": FuID("None"),
         "Center": _pt(cx, cy), "Polyline": polyline_raw(pts, closed), "SoftEdge": soft}
    if stroke:
        i["Solid"] = 0
        i["BorderWidth"] = round(stroke / W, 5)
    if write is not None:
        i["WriteLength"] = Expr(write)
        i["WritePosition"] = Expr(f"({write})/2")
    if prev:
        i["EffectMask"] = Conn(prev, "Mask")
    if mode:
        i["PaintMode"] = FuID(mode)
    i.update(extra or {})
    t = Tool(name, "PolylineMask", i)
    t.extra = "\t\t\t\t\tDrawMode = \"InsertAndModify\",\n\t\t\t\t\tDrawMode2 = \"InsertAndModify\","
    return t


def text(name, value, font, size_px, rgb, x, y, align=-1, track=1.0, alpha=1, extra=None):
    """Text+ (align -1 sinistra, 0 centro, 1 destra). x,y = ancoraggio in px (y = centro riga)."""
    i = {**FRAME, "StyledText": value, "Font": font[0], "Style": font[1],
         "Size": Expr(f"({size_px})/{W}") if isinstance(size_px, str) else round(size_px / W, 5),
         "VerticalJustificationNew": 3, "HorizontalJustificationNew": 3,
         "HorizontalLeftCenterRight": align, "Center": _pt(x, y),
         "Red1": rgb[0], "Green1": rgb[1], "Blue1": rgb[2], "Alpha1": alpha, "ElementShape1": 0,
         "CharacterSpacing": Expr(track) if isinstance(track, str) else track}
    i.update(extra or {})
    return Tool(name, "TextPlus", i)


def shadow(alpha=0.6, soft=10, off=(0.0, -0.003)):
    return {"Enabled3": 1, "ElementShape3": 0, "Red3": 0, "Green3": 0, "Blue3": 0, "Alpha3": alpha,
            "Offset3": off, "Softness3": 1, "SoftnessX3": soft, "SoftnessY3": soft, "PriorityBack3": 5, "PriorityBack1": 10}


def stack(layers, base="Canvas", prefix="Liv"):
    """[(tool, blend|None)] composti in ordine sopra base. Ritorna (tools, ultimo)."""
    tools, prev = [], base
    for i, item in enumerate(layers, 1):
        src, blend = item[0], item[1]
        mode = item[2] if len(item) > 2 else None
        inp = {"Background": Conn(prev), "Foreground": Conn(src), "PerformDepthMerge": 0}
        if blend is not None:
            inp["Blend"] = Expr(blend) if isinstance(blend, str) else blend
        if mode:
            inp["ApplyMode"] = FuID(mode)
        tools.append(Tool(f"{prefix}{i}", "Merge", inp))
        prev = f"{prefix}{i}"
    return tools, prev


def grain(name="Grana", scale=110, contrast=1.6):
    return Tool(name, "FastNoise", {**FRAME, "Detail": 6, "XScale": scale, "Contrast": contrast, "Brightness": 0,
                                    "SeetheRate": 0.9, "Color1Alpha": 1, "Color2Alpha": 1})


def ground_tools(prefix="Fondo"):
    """Sfondi opzionali (verde campo con vignetta, nero, carta) guidati da Ctrl.Bg."""
    return [
        solid(prefix + "Verde", VERDE),
        ellipse(prefix + "VignMask", 960, 540, 2300, 1500, soft=0.25, extra={"Invert": 1}),
        solid(prefix + "Vign", (0, 0, 0), prefix + "VignMask", alpha=0.55),
        solid(prefix + "Nero", NERO),
        solid(prefix + "Carta", CARTA),
        Tool(prefix + "Fibra", "FastNoise", {**FRAME, "Detail": 4, "XScale": 6, "Contrast": 0.8, "Brightness": 0.1,
                                             "Color1Red": 0.80, "Color1Green": 0.74, "Color1Blue": 0.64,
                                             "Color2Red": 1, "Color2Green": 1, "Color2Blue": 1}),
    ]


def ground_layers(prefix="Fondo"):
    return [(prefix + "Verde", "Ctrl.Bg==1 and 1 or 0"), (prefix + "Nero", "Ctrl.Bg==2 and 1 or 0"),
            (prefix + "Carta", "Ctrl.Bg==3 and 1 or 0"), (prefix + "Fibra", "Ctrl.Bg==3 and 0.5 or 0", "Multiply"),
            (prefix + "Vign", "Ctrl.Bg>0 and 1 or 0")]


def grain_layer(name="Grana", amount="Ctrl.Grain"):
    """Grana sulla composizione (solo se c'è uno sfondo pieno, così il trasparente resta pulito)."""
    return (name, f"({amount})*(Ctrl.Bg>0 and 0.35 or 0)", "Overlay")


def reg_frame(prefix, x0, y0, x1, y1, prog, alpha=0.5, rgb=CARTA, thick=2):
    """Cornice di registro: lati che crescono dagli angoli + crocini."""
    w, h = x1 - x0, y1 - y0
    tools, prev = [], None
    k = 0
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        hl = f"({w / 2})*({prog})"
        vl = f"({h / 2})*({prog})"
        k += 1
        tools.append(rect(f"{prefix}H{k}", f"{cx}+({sx})*{hl}/2", cy, hl, thick, prev=prev))
        prev = f"{prefix}H{k}"
        tools.append(rect(f"{prefix}V{k}", cx, f"{cy}+({sy})*{vl}/2", thick, vl, prev=prev))
        prev = f"{prefix}V{k}"
    tools.append(solid(prefix, rgb, prev, alpha=alpha))
    cprev = None
    for k, (cx, cy) in enumerate(((x0, y0), (x1, y0), (x0, y1), (x1, y1)), 1):
        tools.append(rect(f"{prefix}CH{k}", cx, cy, 32, thick, prev=cprev))
        cprev = f"{prefix}CH{k}"
        tools.append(rect(f"{prefix}CV{k}", cx, cy, thick, 32, prev=cprev))
        cprev = f"{prefix}CV{k}"
    tools.append(solid(prefix + "Croci", rgb, cprev, alpha=min(1, alpha * 1.8)))
    return tools, [(prefix, f"{clamp01(f'({prog})*3')}"), (prefix + "Croci", f"{clamp01(f'({prog})*2')}")]


def hand_ellipse_pts(rx, ry, seed=3, turns=1.12, n=72):
    r = random.Random(seed)
    ph = [r.random() * 6.28 for _ in range(4)]
    pts = []
    a0 = -2.3 + r.random() * 0.6
    for i in range(n + 1):
        t = i / n
        a = a0 + t * math.pi * 2 * turns
        k = 1 + 0.04 * math.sin(t * 7 + ph[0]) + 0.05 * t
        pts.append((math.cos(a) * rx * k, math.sin(a) * ry * k * (1 + 0.03 * math.sin(t * 5 + ph[1]))))
    return pts


def torn_rect_pts(w, h, amp=6, step=10, seed=7):
    """Rettangolo con bordi strappati (offset dal centro, px)."""
    r = random.Random(seed)
    pts = []

    def edge(x0, y0, x1, y1, nxv, nyv):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(L / step))
        for i in range(n):
            t = i / n
            d = r.random() * amp + (amp * 2.2 if r.random() < 0.05 else 0)
            pts.append((x0 + (x1 - x0) * t + nxv * d - w / 2, y0 + (y1 - y0) * t + nyv * d - h / 2))
    edge(0, 0, w, 0, 0, 1)
    edge(w, 0, w, h, -1, 0)
    edge(w, h, 0, h, 0, -1)
    edge(0, h, 0, 0, 1, 0)
    return pts


def tear_line_pts(x0, x1, amp=26, seed=5, step=9):
    r = random.Random(seed)
    pts, drift = [], 0
    x = x0
    while x <= x1 + step:
        drift = drift * 0.8 + (r.random() - 0.5) * amp * 0.9
        pts.append((x, drift + (r.random() - 0.5) * amp * 0.35 + math.sin(x * 0.004 + seed) * amp * 0.8))
        x += step
    return pts


def color_exposed(tool, label, group, prefix="TopLeft"):
    return [Exposed(tool, f"{prefix}Red", label, group=group), Exposed(tool, f"{prefix}Green", group=group),
            Exposed(tool, f"{prefix}Blue", group=group)]


def text_color_exposed(tool, label, group):
    return [Exposed(tool, "Red1", label, group=group), Exposed(tool, "Green1", group=group), Exposed(tool, "Blue1", group=group)]


def link_color(tools, names, src, prefix="TopLeft"):
    """I solidi in names prendono il colore da src (che è esposto)."""
    for t in tools:
        if t.name in names:
            for c in ("Red", "Green", "Blue"):
                t.inputs[f"{prefix}{c}"] = Expr(f"{src}.TopLeft{c}")


def title(name, tools, controls, exposed, last, center=(0.5, 0.5), size=None, fade=True):
    """Titolo: tutto sopra un Canvas trasparente, Ctrl = Merge finale con i controlli."""
    inp = {"Background": Conn("Canvas"), "Foreground": Conn(last), "Center": center, "PerformDepthMerge": 0,
           **ctrl_values(controls)}
    if fade:
        inp["Blend"] = Expr(OUT)
    if size is not None:
        inp["Size"] = Expr(size) if isinstance(size, str) else size
    ctrl = Tool("Ctrl", "Merge", inp, controls=controls)
    ex = exposed + [Exposed("Ctrl", k) for k in controls]
    return Macro(name, [canvas(), *tools, ctrl], "Ctrl", ex)


def texp(tool, label):
    return Exposed(tool, "StyledText", label)


def lua_lines(field):
    """Snippet Lua: tabella delle righe non vuote di un campo di testo."""
    return (f"local src=({field}.StyledText.Value or '')\n"
            "local L={} for l0 in string.gmatch(src..'\\n','([^\\n]*)\\n') do local l=string.gsub(l0,'^%s+','') l=string.gsub(l,'%s+$','') if l~='' then table.insert(L,l) end end\n")


def lua_split():
    return ("local function split(s) local a={} for p0 in string.gmatch(s..'|','([^|]*)|') do local p=string.gsub(p0,'^%s+','') p=string.gsub(p,'%s+$','') table.insert(a,p) end return a end\n"
            "local function num(s) s=string.gsub(s or '','%.','') s=string.gsub(s,',','.') s=string.gsub(s,'[^%d%.%-]','') return tonumber(s) or 0 end\n"
            "local function fmt(v,d) local s=string.format('%.'..(d or 0)..'f',v) local i,f=string.match(s,'^(%-?%d+)%.?(%d*)$') i=i or s local r=string.reverse(i) r=string.gsub(r,'(%d%d%d)','%1.') r=string.reverse(r) r=string.gsub(r,'^%.','') r=string.gsub(r,'^%-%.','-') if f and f~='' then r=r..','..f end return r end\n"
            "local function dec(s) local f=string.match(s or '',',(%d+)') return f and #f or 0 end\n")
