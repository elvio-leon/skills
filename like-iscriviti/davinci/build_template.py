#!/usr/bin/env python3
"""
Genera il template Fusion "Mi piace Iscriviti" per DaVinci Resolve (Edit page > Titles).

Output (nella cartella davinci/):
  Mi piace Iscriviti.setting   template da copiare in .../Fusion/Templates/Edit/Titles/
  Mi piace Iscriviti.png       icona 104x58 per l'Effects Library
  Mi piace Iscriviti.drfx      pacchetto (zip) da installare con doppio clic

Il template ricostruisce l'animazione di render.py con nodi Fusion nativi:
pillole = Background + RectangleMask, testi = Text+, icone e cursore = PolylineMask
(contorni calcolati qui con Skia a partire dalle icone Lucide), animazione = espressioni
Lua che leggono il tempo in secondi (time / fps della timeline). Le larghezze delle
pillole si adattano al testo leggendo il DataWindow dei nodi Text+.

Uso:
  python3 davinci/build_template.py            # genera i file
  python3 davinci/build_template.py --check    # genera e verifica (sintassi Lua + espressioni)
"""

import math
import os
import sys
import zipfile

import skia

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import render as R  # noqa: E402  (icone, timeline e funzioni di riferimento)

NAME = "Mi piace Iscriviti"
MACRO = "LikeIscriviti"
W, H = 1920.0, 1080.0
CX, CY = 960.0, 540.0

# ----------------------------------------------------------------- tipografia
# Text+ Size e' relativo alla larghezza del frame: altezza riga (ascender+descender
# hhea) = 0.80 * Size * W  =>  Size = em_px * (asc+desc)/UPM / (0.8 * W).
ROBOTO_LINE = (1900 + 500) / 2048.0
TEXT_PX = 44.0
TEXT_SIZE = TEXT_PX * ROBOTO_LINE / (0.8 * W)

ICON = 44.0          # pollice
BELL = 48.0          # campanella
ICON_GAP = 14.0
PAD = 44.0

# larghezze di riserva (se il DataWindow non fosse leggibile) misurate con Roboto
_cfg = R.Config(type("A", (), dict(like_text="Mi piace", subscribe_text="Iscriviti",
                                   subscribed_text="Iscritto", x=CX, y=CY))())
FB_LIKE = _cfg.f_medium.measureText("Mi piace")
FB_SUB = _cfg.f_bold.measureText("Iscriviti")
FB_SUBBED = _cfg.f_medium.measureText("Iscritto")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


COL_LIKE = hex_rgb("272727")
COL_SUB = hex_rgb("FF0000")
COL_SUBBED = hex_rgb("272727")
COL_TEXT = (1.0, 1.0, 1.0)
COL_ACCENT = hex_rgb("3EA6FF")

# ----------------------------------------------------------------- geometria


def stroke_fill(path, width, cap=skia.Paint.kRound_Cap, join=skia.Paint.kRound_Join):
    p = skia.Paint(Style=skia.Paint.kStroke_Style, StrokeWidth=width, StrokeCap=cap, StrokeJoin=join)
    out = skia.Path()
    p.getFillPath(path, out, None, 8.0)
    return out


def union(*paths):
    acc = paths[0]
    for p in paths[1:]:
        acc = skia.Op(acc, p, skia.PathOp.kUnion_PathOp)
    return skia.Simplify(acc)


def difference(a, b):
    return skia.Simplify(skia.Op(a, b, skia.PathOp.kDifference_PathOp))


def transformed(path, sx, tx=0.0, ty=0.0):
    m = skia.Matrix()
    m.setScaleTranslate(sx, sx, tx, ty)
    out = skia.Path(path)
    out.transform(m)
    return out


def contours(path, tol=0.08):
    """Appiattisce il path in poligoni (lista di liste di (x,y)), tolleranza in px."""
    polys, cur = [], []
    it = skia.Path.Iter(path, False)

    def add_curve(fn, n):
        for i in range(1, n + 1):
            cur.append(fn(i / n))

    while True:
        verb, pts = it.next()
        if verb == skia.Path.Verb.kDone_Verb:
            break
        if verb == skia.Path.Verb.kMove_Verb:
            if len(cur) > 2:
                polys.append(cur)
            cur = [(pts[0].x(), pts[0].y())]
        elif verb == skia.Path.Verb.kLine_Verb:
            cur.append((pts[1].x(), pts[1].y()))
        elif verb in (skia.Path.Verb.kQuad_Verb, skia.Path.Verb.kConic_Verb, skia.Path.Verb.kCubic_Verb):
            P = [(q.x(), q.y()) for q in pts]
            w = it.conicWeight() if verb == skia.Path.Verb.kConic_Verb else 1.0
            span = sum(math.dist(P[i], P[i + 1]) for i in range(len(P) - 1))
            n = max(2, int(math.ceil(math.sqrt(span / tol))))
            if verb == skia.Path.Verb.kCubic_Verb:
                def f(t, P=P):
                    a = (1 - t) ** 3
                    b = 3 * (1 - t) ** 2 * t
                    c = 3 * (1 - t) * t * t
                    d = t ** 3
                    return (a * P[0][0] + b * P[1][0] + c * P[2][0] + d * P[3][0],
                            a * P[0][1] + b * P[1][1] + c * P[2][1] + d * P[3][1])
            else:
                def f(t, P=P, w=w):
                    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t * w, t * t
                    den = a + b + c
                    return ((a * P[0][0] + b * P[1][0] + c * P[2][0]) / den,
                            (a * P[0][1] + b * P[1][1] + c * P[2][1]) / den)
            add_curve(f, n)
        elif verb == skia.Path.Verb.kClose_Verb:
            pass
    if len(cur) > 2:
        polys.append(cur)
    # togli il punto finale duplicato e i punti quasi coincidenti
    clean = []
    for poly in polys:
        q = [poly[0]]
        for pt in poly[1:]:
            if math.dist(pt, q[-1]) > 1e-3:
                q.append(pt)
        if math.dist(q[0], q[-1]) < 1e-3:
            q.pop()
        clean.append(q)
    return clean


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def classify(polys):
    """Ritorna lista di (poly, is_hole) con fori = contorni annidati in numero dispari."""
    out = []
    for i, p in enumerate(polys):
        probe = p[0]
        depth = sum(1 for j, q in enumerate(polys) if j != i and abs(area(q)) > abs(area(p))
                    and point_in_poly(probe, q))
        out.append((p, depth % 2 == 1))
    # prima i contorni pieni, poi i fori (cosi' la catena di maschere e' Add.. poi Subtract..)
    out.sort(key=lambda e: e[1])
    return out


def icon_px(path, size):
    """Icona Lucide 24x24 -> px, centrata nell'origine."""
    s = size / 24.0
    return transformed(path, s, -12 * s, -12 * s)


def build_shapes():
    P = R.PATHS
    sw = R.LUCIDE_STROKE
    shapes = {}
    # pollice contorno: tratto del profilo + tratto del polsino
    thumb_line = union(stroke_fill(P["thumb"], sw), stroke_fill(P["cuff"], sw))
    shapes["thumb_outline"] = icon_px(thumb_line, ICON)
    # pollice pieno: (riempimento + tratto) meno la linea del polsino
    full = union(skia.Path(P["thumb"]), stroke_fill(P["thumb"], sw))
    shapes["thumb_fill"] = icon_px(difference(full, stroke_fill(P["cuff"], sw * 0.85)), ICON)
    # campanella piena con batacchio
    bell = union(skia.Path(P["bell"]), stroke_fill(P["bell"], sw), stroke_fill(P["clapper"], 2.2))
    shapes["bell"] = icon_px(bell, BELL)
    # cursore: punta nell'origine, ~60 px di altezza, bordo nero 2.6 px centrato sul profilo
    cs = 60.0 / 19.6
    cur = transformed(R.CURSOR_PATH, cs)
    border = stroke_fill(cur, 2.6, skia.Paint.kButt_Cap, skia.Paint.kRound_Join)
    shapes["cursor_black"] = union(cur, border)
    shapes["cursor_white"] = difference(cur, border)
    shapes["cursor_shadow"] = cur
    # lineette: capsula 14 x 4.5 px orientata lungo la direzione k
    for k in range(6):
        ang = math.radians(-90 + k * 60)
        dx, dy = math.cos(ang) * 7, math.sin(ang) * 7
        seg = skia.Path()
        seg.moveTo(-dx, -dy)
        seg.lineTo(dx, dy)
        shapes[f"burst{k}"] = stroke_fill(seg, 4.5)
    return {k: classify(contours(v)) for k, v in shapes.items()}


# ----------------------------------------------------------------- serializzazione Lua


class Raw(str):
    """Testo Lua da scrivere cosi' com'e'."""


class Ctor(dict):
    """Tabella Lua preceduta da un costruttore Fusion, es. Input { ... }."""

    def __init__(self, name, *a, **kw):
        super().__init__(*a, **kw)
        self.ctor = name


def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fmt_num(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = f"{v:.9g}"
    return s


def lua(v, ind=0):
    pad = "\t" * ind
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (int, float, bool)):
        return fmt_num(v)
    if isinstance(v, (list, tuple)):
        if all(isinstance(x, (int, float)) for x in v):
            return "{ " + ", ".join(fmt_num(x) for x in v) + " }"
        return "{\n" + "".join(pad + "\t" + lua(x, ind + 1) + ",\n" for x in v) + pad + "}"
    if isinstance(v, Ctor):
        return v.ctor + " " + lua(dict(v), ind)
    if isinstance(v, dict):
        items = []
        for k, x in v.items():
            key = k if k.isidentifier() else "[" + lua_str(k) + "]"
            items.append(pad + "\t" + key + " = " + lua(x, ind + 1) + ",\n")
        return "{\n" + "".join(items) + pad + "}"
    raise TypeError(type(v))


def ctor(name, body, ind):
    return Raw(name + " " + lua(body, ind))


def Inp(value=None, expr=None, src=None, out="Output"):
    d = Ctor("Input")
    if value is not None:
        d["Value"] = value
    if src is not None:
        d["SourceOp"] = src
        d["Source"] = out
    if expr is not None:
        d["Expression"] = expr
    return d


def fuid(s):
    return Raw("FuID { " + lua_str(s) + " }")


def polyline(points):
    """Punti px (y verso il basso, relativi al Center) -> Polyline Fusion normalizzata."""
    n = len(points)
    pts = []
    for i, (x, y) in enumerate(points):
        X, Y = x / W, -y / H
        px, py = points[i - 1]
        nx, ny = points[(i + 1) % n]
        pts.append(Raw("{ Linear = true, X = %s, Y = %s, LX = %s, LY = %s, RX = %s, RY = %s }" % (
            fmt_num(X), fmt_num(Y),
            fmt_num((px - x) / W / 3), fmt_num(-(py - y) / H / 3),
            fmt_num((nx - x) / W / 3), fmt_num(-(ny - y) / H / 3))))
    return Raw("Polyline {\n\t\t\t\t\t\tClosed = true,\n\t\t\t\t\t\tPoints = {\n"
               + "".join("\t\t\t\t\t\t\t" + p + ",\n" for p in pts)
               + "\t\t\t\t\t\t}\n\t\t\t\t\t}")


# ----------------------------------------------------------------- espressioni Lua

LUA_TIME = (
    'local fps, t0 = 30, 0 '
    'pcall(function() local r = comp:GetPrefs("Comp.FrameFormat.Rate") if r and r > 0 then fps = r end '
    't0 = comp.RenderStart or 0 end) '
    'local T = (time - t0) / fps '
    'local function cl(x) if x < 0 then return 0 elseif x > 1 then return 1 end return x end '
    'local function pr(a, b) return cl((T - a) / (b - a)) end '
    'local function lerp(a, b, u) return a + (b - a) * u end '
    'local function oback(u) local s = 1.70158 u = u - 1 return 1 + (s + 1) * u * u * u + s * u * u end '
    'local function ocub(u) return 1 - (1 - u) ^ 3 end '
    'local function icub(u) return u * u * u end '
    'local function iocub(u) if u < 0.5 then return 4 * u * u * u end return 1 - (-2 * u + 2) ^ 3 / 2 end '
    'local function bump(u) return math.sin(math.pi * cl(u)) end '
    'local function press(tc) local u = pr(tc, tc + %(PRESS)s) if u > 0 and u < 1 then return 1 - 0.07 * bump(u) end return 1 end '
    'local function appear(a, b) local u = pr(a, b) local s = 0.55 if u > 0 then s = lerp(0.55, 1, oback(u)) end '
    'return s, ocub(pr(a, a + (b - a) * 0.55)) end '
    'local function outro() local u = pr(%(OUT0)s, %(OUT1)s) return lerp(1, 0.65, icub(u)), 1 - u * u end '
) % dict(PRESS=R.PRESS_DUR, OUT0=R.T_OUT[0], OUT1=R.T_OUT[1])

LUA_LAYOUT = (
    'local function tw(tl, fb) local ok, w = pcall(function() local o = tl.Output[0] local d = o.DataWindow '
    'return (d[3] - d[1]) * 1920 / o.Width end) '
    'if ok and type(w) == "number" and w > 1 and w < 1900 then return w end return fb end '
    'local TL, TS, TD = tw(LK_Txt, %(FL).3f), tw(SB_Txt1, %(FS).3f), tw(SB_Txt2, %(FD).3f) '
    'local LW = math.max(330, %(LPAD)s + TL) '
    'local SW = math.max(420, %(SPAD)s + TS, %(DPAD)s + TD) '
    'local left = 960 - (LW + 32 + SW) / 2 '
    'local LCX = left + LW / 2 '
    'local SCX = left + LW + 32 + SW / 2 '
    'local ICX = -(%(IG)s + TL) / 2 + %(IH)s '
    'local BCX = -(%(BG)s + TD) / 2 + %(BH)s '
) % dict(FL=FB_LIKE, FS=FB_SUB, FD=FB_SUBBED,
         LPAD=2 * PAD + ICON + ICON_GAP, SPAD=2 * PAD, DPAD=2 * PAD + BELL + ICON_GAP,
         IG=ICON + ICON_GAP, IH=ICON / 2, BG=BELL + ICON_GAP, BH=BELL / 2)

LUA_CURSOR = (
    'local function cursor() '
    'local sx, sy = 960 + 600, 540 + 340 '
    'local lx, ly = LCX + 1, 540 + 45 '
    'local bx, by = SCX + 49, 540 + 45 '
    'local ex, ey = 960 + 660, 540 + 400 '
    'if T < %(CI0)s then return sx, sy, 0 end '
    'local a = ocub(pr(%(CF0)s, %(CF1)s)) local x, y '
    'if T < %(CS0)s then local u = iocub(pr(%(CI0)s, %(CI1)s)) x, y = lerp(sx, lx, u), lerp(sy, ly, u) '
    'elseif T < %(CO0)s then local u = iocub(pr(%(CS0)s, %(CS1)s)) x, y = lerp(lx, bx, u), lerp(ly, by, u) '
    'else local e = icub(pr(%(CO0)s, %(CO1)s)) x, y = lerp(bx, ex, e), lerp(by, ey, e) '
    'a = a * (1 - ocub(pr(%(CO0)s + 0.15, %(CO1)s))) end '
    'return x, y, a end '
) % dict(CI0=R.T_CUR_IN[0], CI1=R.T_CUR_IN[1], CF0=R.T_CUR_FADE[0], CF1=R.T_CUR_FADE[1],
         CS0=R.T_CUR_TO_SUB[0], CS1=R.T_CUR_TO_SUB[1], CO0=R.T_CUR_OUT[0], CO1=R.T_CUR_OUT[1])


def E(body, layout=False, cursor=False):
    code = LUA_TIME + (LUA_LAYOUT if layout else "") + (LUA_CURSOR if cursor else "") + body
    return ":" + code


LIKE_STATE = ('local ls, la = appear(%s, %s) local so, ao = outro() ls = ls * press(%s) * so la = la * ao '
              % (R.T_LIKE_IN[0], R.T_LIKE_IN[1], R.T_CLICK_LIKE))
SUB_STATE = ('local ss, sa = appear(%s, %s) local so, ao = outro() ss = ss * press(%s) * so sa = sa * ao '
             % (R.T_SUB_IN[0], R.T_SUB_IN[1], R.T_CLICK_SUB))
SWAP = 'local k = iocub(pr(%s, %s)) ' % R.T_SWAP
THUMB = 'local ut = pr(%s, %s) ' % R.T_THUMB
BELL_ANGLE = (
    'local function bell() local u = pr(%(B0)s, %(B1)s) if u <= 0 or u >= 1 then return 0 end '
    'local c = 3.5 local up = 1 / (4 * c) return 26 / ((1 - up) ^ 2) * (1 - u) ^ 2 * math.sin(2 * math.pi * c * u) end '
) % dict(B0=R.T_BELL[0], B1=R.T_BELL[1])
BURST = (
    'local ub = pr(%(T0)s, %(T0)s + %(D)s) local eb = ocub(ub) local ab = 0 '
    'if ub > 0 and ub < 1 then ab = 1 - ub * ub end local rb = lerp(34, 92, eb) - 7 '
) % dict(T0=R.T_THUMB[0], D=R.BURST_DUR)
RING = (
    'local tc, px, py = %(CL)s, LCX + 1, 585 if T >= %(MID)s then tc, px, py = %(CS)s, SCX + 49, 585 end '
    'local ur = pr(tc, tc + %(RD)s) local active = ur > 0 and ur < 1 '
    'local rr = lerp(12, 52, ocub(ur)) local rw = lerp(4, 1.5, ur) '
) % dict(CL=R.T_CLICK_LIKE, CS=R.T_CLICK_SUB, MID=(R.T_CLICK_LIKE + R.T_CLICK_SUB) / 2 + 0.5, RD=R.RING_DUR)


# ----------------------------------------------------------------- costruzione grafo


class Graph:
    def __init__(self):
        self.tools = []      # (name, regid, dict)
        self.col = 0

    def add(self, name, regid, inputs, pos=None, extra=None):
        body = {}
        if extra:
            body.update(extra)
        body["Inputs"] = inputs
        if pos is not None:
            body["ViewInfo"] = Raw("OperatorInfo { Pos = { %s, %s } }" % (fmt_num(pos[0]), fmt_num(pos[1])))
        self.tools.append((name, regid, body))
        return name


GEN = dict(GlobalIn=Inp(-1000), GlobalOut=Inp(20000), Width=Inp(1920), Height=Inp(1080),
           UseFrameFormatSettings=Inp(1))
MASK = dict(MaskWidth=Inp(1920), MaskHeight=Inp(1080), PixelAspect=Inp([1, 1]),
            UseFrameFormatSettings=Inp(1), ClippingMode=Inp(fuid("None")))


def background(g, name, rgb, alpha=1.0, mask=None, pos=None, color_expr=None):
    inp = dict(GEN)
    names = ("TopLeftRed", "TopLeftGreen", "TopLeftBlue")
    for i, n in enumerate(names):
        inp[n] = Inp(rgb[i], expr=(color_expr[i] if color_expr else None))
    inp["TopLeftAlpha"] = Inp(alpha)
    if mask:
        inp["EffectMask"] = Inp(src=mask, out="Mask")
    return g.add(name, "Background", inp, pos)


def merge(g, name, bg, fg, pos=None, **kw):
    inp = dict(Background=Inp(src=bg), Foreground=Inp(src=fg), PerformDepthMerge=Inp(0))
    for k, v in kw.items():
        inp[k] = v
    return g.add(name, "Merge", inp, pos)


def poly_chain(g, prefix, classified, pos, center=(0.5, 0.5), center_expr=None, soft=0.0):
    """Catena di PolylineMask: contorni pieni in Maximum, fori in Subtract. Ritorna l'ultima."""
    prev = None
    for i, (poly, hole) in enumerate(classified):
        nm = f"{prefix}{i + 1}"
        inp = dict(MASK)
        inp["Center"] = Inp(list(center), expr=center_expr)
        inp["Polyline"] = Inp(polyline(poly))
        inp["Polyline2"] = Inp(Raw("Polyline { }"))
        if soft:
            inp["SoftEdge"] = Inp(soft)
        if prev:
            inp["EffectMask"] = Inp(src=prev, out="Mask")
            inp["PaintMode"] = Inp(fuid("Subtract" if hole else "Maximum"))
        g.add(nm, "PolylineMask", inp, (pos[0] + 0, pos[1] - 33 * (len(classified) - i)))
        prev = nm
    return prev


def textplus(g, name, text, style, center, pos, color_expr=None):
    inp = dict(GEN)
    inp.update(dict(
        StyledText=Inp(Raw("StyledText { Value = %s }" % lua_str(text))),
        Font=Inp("Roboto"), Style=Inp(style), Size=Inp(TEXT_SIZE),
        Center=Inp(list(center)),
        VerticalJustificationNew=Inp(3), HorizontalJustificationNew=Inp(3),
        Red1=Inp(1.0, expr=(color_expr[0] if color_expr else None)),
        Green1=Inp(1.0, expr=(color_expr[1] if color_expr else None)),
        Blue1=Inp(1.0, expr=(color_expr[2] if color_expr else None)),
    ))
    return g.add(name, "TextPlus", inp, pos)


TEXT_LINK = ("LK_Txt.Red1", "LK_Txt.Green1", "LK_Txt.Blue1")


def build_graph(shapes):
    g = Graph()
    pill_h = 100.0 / H
    soft = 1.18 * 22 / W     # blur CSS 22 px

    g.add("Base", "Background", dict(GEN, TopLeftRed=Inp(0), TopLeftGreen=Inp(0), TopLeftBlue=Inp(0),
                                     TopLeftAlpha=Inp(0)), (0, 0))

    # ---------------- pillola Mi piace (costruita al centro del frame)
    x = 110
    g.add("LK_SM", "RectangleMask", dict(MASK, Center=Inp([0.5, 0.5 - 10 / H]),
                                         Width=Inp(330 / W, expr=E("return LW / 1920", layout=True)),
                                         Height=Inp(pill_h), CornerRadius=Inp(1), SoftEdge=Inp(soft)), (x, -66))
    background(g, "LK_Shadow", (0, 0, 0), 0.35, "LK_SM", (x, -33))
    g.add("LK_M", "RectangleMask", dict(MASK, Center=Inp([0.5, 0.5]),
                                        Width=Inp(330 / W, expr=E("return LW / 1920", layout=True)),
                                        Height=Inp(pill_h), CornerRadius=Inp(1)), (x + 110, -66))
    background(g, "LK_BG", COL_LIKE, 1.0, "LK_M", (x + 110, -33))
    textplus(g, "LK_Txt", "Mi piace", "Medium", (0.5 + (ICON + ICON_GAP) / 2 / W, 0.5), (x + 220, -33))
    # pollice: contorno -> pieno con Dissolve
    tho = poly_chain(g, "TH_O", shapes["thumb_outline"], (x + 330, -33))
    background(g, "TH_OBG", COL_TEXT, 1.0, tho, (x + 330, 0), color_expr=TEXT_LINK)
    thf = poly_chain(g, "TH_F", shapes["thumb_fill"], (x + 440, -33))
    background(g, "TH_FBG", COL_TEXT, 1.0, thf, (x + 440, 0), color_expr=TEXT_LINK)
    g.add("TH_Dis", "Dissolve", dict(Background=Inp(src="TH_OBG"), Foreground=Inp(src="TH_FBG"),
                                     Mix=Inp(0.0, expr=E("return ocub(pr(%s, %s))" % (
                                         R.T_THUMB[0], R.T_THUMB[0] + R.THUMB_FILL_DUR)))), (x + 440, 33))
    merge(g, "LK_C1", "Base", "LK_Shadow", (x, 66))
    merge(g, "LK_C2", "LK_C1", "LK_BG", (x + 110, 66))
    merge(g, "LK_C3", "LK_C2", "LK_Txt", (x + 220, 66))
    merge(g, "LK_C4", "LK_C3", "TH_Dis", (x + 440, 66),
          Center=Inp([0.5 + (-(ICON + ICON_GAP + FB_LIKE) / 2 + ICON / 2) / W, 0.5],
                     expr=E("return Point(0.5 + ICX / 1920, 0.5)", layout=True)),
          Size=Inp(1.0, expr=E(THUMB + "return 1 + 0.5 * bump(ut)")),
          Angle=Inp(0.0, expr=E(THUMB + "return 22 * bump(ut)")))

    # ---------------- pillola Iscriviti / Iscritto
    y = 230
    g.add("SB_SM", "RectangleMask", dict(MASK, Center=Inp([0.5, 0.5 - 10 / H]),
                                         Width=Inp(420 / W, expr=E("return SW / 1920", layout=True)),
                                         Height=Inp(pill_h), CornerRadius=Inp(1), SoftEdge=Inp(soft)), (x, y - 66))
    background(g, "SB_Shadow", (0, 0, 0), 0.35, "SB_SM", (x, y - 33))
    g.add("SB_M", "RectangleMask", dict(MASK, Center=Inp([0.5, 0.5]),
                                        Width=Inp(420 / W, expr=E("return SW / 1920", layout=True)),
                                        Height=Inp(pill_h), CornerRadius=Inp(1)), (x + 110, y - 99))
    background(g, "SB_RedBG", COL_SUB, 1.0, "SB_M", (x + 110, y - 66))
    background(g, "SB_GreyBG", COL_SUBBED, 1.0, "SB_M", (x + 220, y - 66))
    g.add("SB_Dis", "Dissolve", dict(Background=Inp(src="SB_RedBG"), Foreground=Inp(src="SB_GreyBG"),
                                     Mix=Inp(0.0, expr=E(SWAP + "return k"))), (x + 220, y - 33))
    textplus(g, "SB_Txt1", "Iscriviti", "Bold", (0.5, 0.5), (x + 330, y - 66), color_expr=TEXT_LINK)
    textplus(g, "SB_Txt2", "Iscritto", "Medium", (0.5 + (BELL + ICON_GAP) / 2 / W, 0.5), (x + 440, y - 99),
             color_expr=TEXT_LINK)
    blc = poly_chain(g, "BL_", shapes["bell"], (x + 550, y - 99))
    background(g, "BL_BG", COL_TEXT, 1.0, blc, (x + 550, y - 66), color_expr=TEXT_LINK)
    g.add("BL_Xf", "Transform", dict(
        Input=Inp(src="BL_BG"),
        Pivot=Inp([0.5, 0.5 + (BELL / 2 - 2 * BELL / 24) / H]),
        Center=Inp([0.5 + (-(BELL + ICON_GAP + FB_SUBBED) / 2 + BELL / 2) / W, 0.5],
                   expr=E("return Point(0.5 + BCX / 1920, 0.5)", layout=True)),
        Angle=Inp(0.0, expr=E(BELL_ANGLE + "return -bell()"))), (x + 550, y - 33))
    merge(g, "SB_New", "SB_Txt2", "BL_Xf", (x + 440, y - 33))
    merge(g, "SB_C1", "Base", "SB_Shadow", (x, y))
    merge(g, "SB_C2", "SB_C1", "SB_Dis", (x + 220, y))
    merge(g, "SB_C3", "SB_C2", "SB_Txt1", (x + 330, y),
          Blend=Inp(1.0, expr=E(SWAP + "return 1 - cl(k / 0.6)")))
    merge(g, "SB_C4", "SB_C3", "SB_New", (x + 440, y),
          Blend=Inp(0.0, expr=E(SWAP + "return cl((k - 0.4) / 0.6)")))

    # ---------------- lineette (scena)
    z = 420
    white_chain, blue_chain = None, None
    for k in range(6):
        nm = f"BU_{k}"
        ang = math.radians(-90 + k * 60)
        cx_expr = E(LIKE_STATE + BURST + (
            "local tx = LCX + ICX * ls return Point((tx + math.cos(%r) * rb) / 1920, 1 - (540 + math.sin(%r) * rb) / 1080)"
            % (ang, ang)), layout=True)
        inp = dict(MASK)
        inp["Center"] = Inp([0.5, 0.5], expr=cx_expr)
        (poly, _), = shapes[f"burst{k}"]
        inp["Polyline"] = Inp(polyline(poly))
        inp["Polyline2"] = Inp(Raw("Polyline { }"))
        prev = white_chain if k % 2 == 0 else blue_chain
        if prev:
            inp["EffectMask"] = Inp(src=prev, out="Mask")
            inp["PaintMode"] = Inp(fuid("Maximum"))
        g.add(nm, "PolylineMask", inp, (x + 55 * k, z - 66))
        if k % 2 == 0:
            white_chain = nm
        else:
            blue_chain = nm
    background(g, "BU_WBG", COL_TEXT, 1.0, white_chain, (x + 330, z - 33), color_expr=TEXT_LINK)
    background(g, "BU_ABG", COL_ACCENT, 1.0, blue_chain, (x + 385, z - 33))

    # ---------------- anello del clic (scena)
    ring_c = E(RING + "return Point(px / 1920, 1 - py / 1080)", layout=True)
    g.add("RI_O", "EllipseMask", dict(MASK, Center=Inp([0.5, 0.5], expr=ring_c),
                                      Width=Inp(0.0, expr=E(RING + "return 2 * (rr + rw / 2) / 1920", layout=True)),
                                      Height=Inp(0.0, expr=E(RING + "return 2 * (rr + rw / 2) / 1920", layout=True))),
          (x + 495, z - 66))
    g.add("RI_I", "EllipseMask", dict(MASK, Center=Inp([0.5, 0.5], expr=ring_c),
                                      Width=Inp(0.0, expr=E(RING + "return 2 * math.max(rr - rw / 2, 0) / 1920", layout=True)),
                                      Height=Inp(0.0, expr=E(RING + "return 2 * math.max(rr - rw / 2, 0) / 1920", layout=True)),
                                      EffectMask=Inp(src="RI_O", out="Mask"), PaintMode=Inp(fuid("Subtract"))),
          (x + 550, z - 66))
    background(g, "RI_BG", COL_TEXT, 1.0, "RI_I", (x + 550, z - 33))

    # ---------------- cursore (punta al centro del frame)
    cu_sh = poly_chain(g, "CU_S", shapes["cursor_shadow"], (x + 660, z - 33),
                       center=(0.5 + 2.4 / W, 0.5 - 4.0 / H), soft=1.18 * 8 / W)
    background(g, "CU_SBG", (0, 0, 0), 0.45, cu_sh, (x + 660, z))
    cu_b = poly_chain(g, "CU_B", shapes["cursor_black"], (x + 770, z - 33))
    background(g, "CU_BBG", (0, 0, 0), 1.0, cu_b, (x + 770, z))
    cu_w = poly_chain(g, "CU_W", shapes["cursor_white"], (x + 880, z - 33))
    background(g, "CU_WBG", (1, 1, 1), 1.0, cu_w, (x + 880, z))
    merge(g, "CU_C1", "CU_SBG", "CU_BBG", (x + 770, z + 33))
    merge(g, "CU_C2", "CU_C1", "CU_WBG", (x + 880, z + 33))

    # ---------------- scena
    s = 600
    merge(g, "SC_Like", "Base", "LK_C4", (x, s),
          Center=Inp([734 / W, 0.5], expr=E("return Point(LCX / 1920, 0.5)", layout=True)),
          Size=Inp(1.0, expr=E(LIKE_STATE + "return ls")),
          Blend=Inp(0.0, expr=E(LIKE_STATE + "return la")))
    merge(g, "SC_Sub", "SC_Like", "SB_C4", (x + 110, s),
          Center=Inp([1141 / W, 0.5], expr=E("return Point(SCX / 1920, 0.5)", layout=True)),
          Size=Inp(1.0, expr=E(SUB_STATE + "return ss")),
          Blend=Inp(0.0, expr=E(SUB_STATE + "return sa")))
    merge(g, "SC_BurstW", "SC_Sub", "BU_WBG", (x + 220, s), Blend=Inp(0.0, expr=E(BURST + "return ab")))
    merge(g, "SC_BurstA", "SC_BurstW", "BU_ABG", (x + 330, s), Blend=Inp(0.0, expr=E(BURST + "return ab")))
    merge(g, "SC_Ring", "SC_BurstA", "RI_BG", (x + 440, s),
          Blend=Inp(0.0, expr=E(RING + "if not active then return 0 end return 0.95 * (1 - ur) ^ 1.5", layout=True)))
    merge(g, "SC_Cursor", "SC_Ring", "CU_C2", (x + 550, s),
          Center=Inp([0.5, 0.5], expr=E("local x, y = cursor() return Point(x / 1920, 1 - y / 1080)",
                                        layout=True, cursor=True)),
          Size=Inp(1.0, expr=E("local p = math.min(press(%s), press(%s)) if p < 1 then return 1 + 1.3 * (p - 1) end return 1"
                                % (R.T_CLICK_LIKE, R.T_CLICK_SUB))),
          Blend=Inp(0.0, expr=E("local x, y, a = cursor() return a", layout=True, cursor=True)))
    g.add("GL_Xf", "Transform", dict(Input=Inp(src="SC_Cursor"), Center=Inp([0.5, 0.5]), Size=Inp(1.0)),
          (x + 660, s))
    return g


PUBLISHED = [
    ("LK_Txt", "StyledText", dict(Name="Testo Mi piace")),
    ("SB_Txt1", "StyledText", dict(Name="Testo Iscriviti")),
    ("SB_Txt2", "StyledText", dict(Name="Testo Iscritto")),
    ("color", "LK_BG", "Colore Mi piace", COL_LIKE),
    ("color", "SB_RedBG", "Colore Iscriviti", COL_SUB),
    ("color", "SB_GreyBG", "Colore Iscritto", COL_SUBBED),
    ("tcolor", "LK_Txt", "Colore testo e icone", COL_TEXT),
    ("color", "BU_ABG", "Colore lineette", COL_ACCENT),
    ("GL_Xf", "Center", dict(Name="Posizione", DefaultX=0.5, DefaultY=0.5)),
    ("GL_Xf", "Size", dict(Name="Dimensione", Default=1, MinScale=0.2, MaxScale=2)),
]


def macro_text(g):
    inputs = {}
    n, cg = 1, 10
    for entry in PUBLISHED:
        if entry[0] in ("color", "tcolor"):
            kind, tool, label, rgb = entry
            names = ("TopLeftRed", "TopLeftGreen", "TopLeftBlue") if kind == "color" else \
                ("Red1Clone", "Green1Clone", "Blue1Clone")
            for i, src in enumerate(names):
                d = dict(SourceOp=tool, Source=src, ControlGroup=cg, Default=round(rgb[i], 6))
                if i == 0:
                    d["Name"] = label
                inputs[f"Input{n}"] = Ctor("InstanceInput", d)
                n += 1
            cg += 1
        else:
            tool, src, extra = entry
            d = dict(SourceOp=tool, Source=src)
            d.update(extra)
            inputs[f"Input{n}"] = Ctor("InstanceInput", d)
            n += 1

    tools_txt = ""
    for name, regid, body in g.tools:
        tools_txt += "\t\t\t\t%s = %s %s,\n" % (name, regid, lua(body, 4))

    inputs_txt = "".join("\t\t\t\t%s = %s,\n" % (k, lua(v, 4)) for k, v in inputs.items())
    return (
        "{\n"
        "\tTools = ordered() {\n"
        f"\t\t{MACRO} = MacroOperator {{\n"
        "\t\t\tCtrlWZoom = false,\n"
        "\t\t\tInputs = ordered() {\n" + inputs_txt + "\t\t\t},\n"
        "\t\t\tOutputs = {\n"
        "\t\t\t\tMainOutput1 = InstanceOutput { SourceOp = \"GL_Xf\", Source = \"Output\", },\n"
        "\t\t\t},\n"
        "\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },\n"
        "\t\t\tTools = ordered() {\n" + tools_txt + "\t\t\t},\n"
        "\t\t},\n"
        "\t},\n"
        f"\tActiveTool = \"{MACRO}\"\n"
        "}\n"
    )


# ----------------------------------------------------------------- icona e pacchetto


def make_icon(path):
    """Icona 104x58 dal renderer di riferimento (frame con Iscritto)."""
    from PIL import Image
    c = R.Config(type("A", (), dict(like_text="Mi piace", subscribe_text="Iscriviti",
                                    subscribed_text="Iscritto", x=CX, y=CY))())
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(int(W), int(H), skia.kRGBA_8888_ColorType,
                                                       skia.kPremul_AlphaType))
    arr = R.frame_rgba(surf, surf.getCanvas(), 2.30, c)
    im = Image.fromarray(arr, "RGBA").crop((545, 465, 1375, 625))
    bg = Image.new("RGBA", im.size, (24, 24, 28, 255))
    out = Image.alpha_composite(bg, im).convert("RGB")
    out.thumbnail((104, 58), Image.LANCZOS)
    canvas = Image.new("RGB", (104, 58), (24, 24, 28))
    canvas.paste(out, ((104 - out.width) // 2, (58 - out.height) // 2))
    canvas.save(path)


def build(out_dir=HERE):
    shapes = build_shapes()
    g = build_graph(shapes)
    text = macro_text(g)
    setting = os.path.join(out_dir, NAME + ".setting")
    with open(setting, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    icon = os.path.join(out_dir, NAME + ".png")
    make_icon(icon)
    drfx = os.path.join(out_dir, NAME + ".drfx")
    with zipfile.ZipFile(drfx, "w", zipfile.ZIP_DEFLATED) as z:
        for src in (setting, icon):
            info = zipfile.ZipInfo("Edit/Titles/Like e Iscriviti/" + os.path.basename(src), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(src, "rb") as fh:
                z.writestr(info, fh.read())
    return setting, icon, drfx, shapes, g


if __name__ == "__main__":
    setting, icon, drfx, shapes, g = build()
    print("scritto", setting, f"({os.path.getsize(setting) // 1024} KB, {len(g.tools)} nodi)")
    print("scritto", icon)
    print("scritto", drfx)
    if "--check" in sys.argv:
        import check_template
        sys.exit(check_template.run(setting, shapes))
