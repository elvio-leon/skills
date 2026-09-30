"""Linea di Fondo — brand pack built on the channel's visual identity.

Identity rules applied here (from the brand guide):
* palette: verde profondo #183A2F (dominant), avorio #F5EFE6 (contrast),
  terracotta #B5323C (only for lines, routes, points, dates), ardesia #1E1E1E;
* Optima for titles and information (the brand fonts SangBleu / Inter are
  not installed on the editing machine);
* "la linea" is the proprietary element: it appears, extends, becomes a
  route, a timeline, an underline, a pitch line;
* motion is slow, precise, geometric: eases without overshoot, no glitch,
  no aggressive zooms, no glow, no heavy grain, no filters forced on photos.
"""

from __future__ import annotations

from fusion import LEN, R, T, Conn, Expr, Exposed, FuID, Macro, Tool, anim_curves, checkbox, clamp01, combo, slider
from templates import FRAME, canvas, ctrl_values, ease_in, ease_io, ease_out, solid

PACK = "Linea di Fondo"
PREFIX = "LDF"

VERDE = (0.094, 0.227, 0.184)      # #183A2F
AVORIO = (0.961, 0.937, 0.902)     # #F5EFE6
TERRA = (0.710, 0.196, 0.235)      # #B5323C
ARDESIA = (0.118, 0.118, 0.118)    # #1E1E1E

# Optima for everything: it ships with macOS and is available in Resolve without
# installing anything. Titles use Regular, labels and names use Bold.
SERIF, SERIF_STYLE = "Optima", "Regular"
SANS = "Optima"

OW = "Ctrl.Background.OriginalWidth"
OH = "Ctrl.Background.OriginalHeight"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def st(a, d):
    """Progress 0..1 of an animation stage starting at frame a lasting d frames
    (both multiplied by the 'Durata animazioni' control)."""
    return clamp01(f"({T}-({a})*Ctrl.Speed)/max(({d})*Ctrl.Speed,1)")


OUT = clamp01(f"{R}/max(Ctrl.OutDur,1)")

BASE_CONTROLS = {
    "Speed": slider("Durata animazioni (1 = normale, 2 = più lenta)", 1, 0.3, 3, allowed=(0.05, 20)),
    "OutDur": slider("Durata uscita (frame)", 15, 1, 60, integer=True, allowed=(1, 600)),
}


def tx(name, value, font=SANS, style="Regular", size=0.02, rgb=AVORIO, pos=(0.5, 0.5),
       track=1.0, left=True, center_expr=None, extra=None):
    i = {**FRAME, "StyledText": value, "Font": font, "Style": style, "Size": size,
         "VerticalJustificationNew": 3, "HorizontalJustificationNew": 3,
         "Center": center_expr if center_expr is not None else pos,
         "Red1": rgb[0], "Green1": rgb[1], "Blue1": rgb[2], "ElementShape1": 0,
         "CharacterSpacing": track}
    if left:
        i["HorizontalLeftCenterRight"] = -1
    i.update(extra or {})
    return Tool(name, "TextPlus", i)


def rise(x, y, stage, dist=0.012):
    """Centre that rises gently into place (no overshoot)."""
    return Expr(f"Point({x}, {y}-(1-{ease_out(stage)})*{dist})")


def hline(name, x0, y, length, thick_px, rgb, prog, from_center=False):
    """Horizontal line that draws itself from x0 (or from its centre)."""
    if from_center:
        center = Expr(f"Point({x0}, {y})")
    else:
        center = Expr(f"Point({x0}+({length})*({prog})/2, {y})")
    mask = Tool(name + "Mask", "RectangleMask", {
        "Center": center, "Width": Expr(f"({length})*({prog})"),
        "Height": Expr(f"({thick_px})/{OH}"), "SoftEdge": 0.0003})
    return [mask, solid(name, rgb, {"EffectMask": Conn(name + "Mask", "Mask")})]


def vline(name, x, y0, length, thick_px, rgb, prog):
    mask = Tool(name + "Mask", "RectangleMask", {
        "Center": Expr(f"Point({x}, {y0}+({length})*({prog})/2)"),
        "Width": Expr(f"({thick_px})/{OW}"), "Height": Expr(f"({length})*({prog})"),
        "SoftEdge": 0.0003})
    return [mask, solid(name, rgb, {"EffectMask": Conn(name + "Mask", "Mask")})]


def dot(name, center, diam_px, rgb, scale="1"):
    mask = Tool(name + "Mask", "EllipseMask", {
        "Center": center if not isinstance(center, str) else Expr(center),
        "Width": Expr(f"({diam_px})*({scale})/{OW}"),
        "Height": Expr(f"({diam_px})*({scale})/{OH}"), "SoftEdge": 0.0006})
    return [mask, solid(name, rgb, {"EffectMask": Conn(name + "Mask", "Mask")})]


def stack(layers, base="Canvas", prefix="Livello"):
    """Merge a list of (tool, blend_expr_or_None) over ``base``; returns tools, last name."""
    tools, prev = [], base
    for i, (src, blend) in enumerate(layers, 1):
        inputs = {"Background": Conn(prev), "Foreground": Conn(src), "PerformDepthMerge": 0}
        if blend is not None:
            inputs["Blend"] = blend
        tools.append(Tool(f"{prefix}{i}", "Merge", inputs))
        prev = f"{prefix}{i}"
    return tools, prev


def green_bg_layer():
    """Optional full-frame brand green under a title (for title cards)."""
    return solid("SfondoVerde", VERDE), ("SfondoVerde", Expr("Ctrl.GreenBg"))


GREEN_BG_CTRL = {"GreenBg": checkbox("Sfondo verde pieno (per schermate titolo)", 0)}


def title_macro(name, tools, controls, exposed, center=(0.5, 0.5), last="Livello"):
    ctrl = Tool("Ctrl", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn(last),
                                  "Center": center, "PerformDepthMerge": 0,
                                  "Blend": Expr(OUT), **ctrl_values(controls)}, controls=controls)
    return Macro(name, [canvas(), *tools, ctrl], "Ctrl",
                 exposed + [Exposed("Ctrl", "Center", "Posizione")] + [Exposed("Ctrl", k) for k in controls])


def texp(tool, label, size=None, font=True):
    e = [Exposed(tool, "StyledText", label)]
    if font:
        e += [Exposed(tool, "Font", f"Font {label.lower()}"), Exposed(tool, "Style", f"Stile {label.lower()}")]
    if size is not None:
        e.append(Exposed(tool, "Size", f"Dimensione {label.lower()}", size))
    return e


# --------------------------------------------------------------------------- #
# TITLES
# --------------------------------------------------------------------------- #
def t_linea():
    c = {**BASE_CONTROLS,
         "Length": slider("Lunghezza linea", 0.25, 0.02, 0.5),
         "Thick": slider("Spessore (pixel)", 4, 1, 20),
         "StartDot": checkbox("Punto iniziale", 1),
         "EndDot": checkbox("Punto finale", 0)}
    p = ease_io(st(8, 32))
    tools = [
        *dot("PuntoA", (0.5, 0.5), "Ctrl.Thick*3.2", TERRA, ease_out(st(0, 10))),
        *hline("Linea", 0.5, 0.5, "Ctrl.Length", "Ctrl.Thick", TERRA, p),
        *dot("PuntoB", Expr("Point(0.5+Ctrl.Length, 0.5)"), "Ctrl.Thick*3.2", TERRA, ease_out(st(38, 10))),
    ]
    mt, last = stack([("PuntoA", Expr("Ctrl.StartDot")), ("Linea", None), ("PuntoB", Expr("Ctrl.EndDot"))])
    m = title_macro("LDF_Linea", tools + mt, c, [
        Exposed("Ctrl", "Angle", "Rotazione (90 = verticale)"),
        Exposed("Linea", "TopLeftRed", "Colore", group=1), Exposed("Linea", "TopLeftGreen", group=1),
        Exposed("Linea", "TopLeftBlue", group=1)], center=(0.3, 0.5), last=last)
    # Dots share the line colour.
    for d in ("PuntoA", "PuntoB"):
        tool = next(t for t in m.tools if t.name == d)
        tool.inputs.update({"TopLeftRed": Expr("Linea.TopLeftRed"), "TopLeftGreen": Expr("Linea.TopLeftGreen"),
                            "TopLeftBlue": Expr("Linea.TopLeftBlue")})
    return m


def t_titolo():
    c = {**BASE_CONTROLS, **GREEN_BG_CTRL}
    x = 0.08
    tools = [
        green_bg_layer()[0],
        tx("Sopra", "CAPITOLO 01", SANS, "Regular", 0.016, TERRA, track=1.35,
           center_expr=rise(x, 0.64, st(0, 16))),
        tx("Titolo", "IL CALCIO IN COREA DEL NORD", SERIF, SERIF_STYLE, 0.062, AVORIO,
           center_expr=rise(x, 0.545, st(6, 26), 0.018)),
        *hline("Linea", x, 0.46, 0.055, 4, TERRA, ease_io(st(20, 24))),
        tx("Sotto", "STORIE DI CALCIO NEL MONDO", SANS, "Regular", 0.018, AVORIO, track=1.35,
           center_expr=rise(x, 0.41, st(32, 20))),
    ]
    mt, last = stack([green_bg_layer()[1], ("Sopra", Expr(ease_out(st(0, 16)))),
                      ("Titolo", Expr(ease_out(st(6, 26)))), ("Linea", None),
                      ("Sotto", Expr(ease_out(st(32, 20))))])
    return title_macro("LDF_TitoloEditoriale", tools + mt, c,
                       texp("Sopra", "Sopratitolo", 0.016) + texp("Titolo", "Titolo", 0.062)
                       + texp("Sotto", "Sottotitolo", 0.018), last=last)


def t_coordinate():
    c = {**BASE_CONTROLS,
         "Panel": checkbox("Pannello verde", 1),
         "DateCol": checkbox("Mostra colonna data", 1)}
    tools = [
        Tool("PannelloMask", "RectangleMask", {"Center": (0.5, 0.5), "Width": 0.3, "Height": 0.3}),
        solid("Pannello", VERDE, {"EffectMask": Conn("PannelloMask", "Mask"), "TopLeftAlpha": 0.94}),
        tx("Luogo", "KABUL", SANS, "Bold", 0.04, AVORIO, track=1.05,
           center_expr=rise(0.375, 0.58, st(4, 20))),
        tx("Coord", "34.5553° N\n69.2075° E", SANS, "Regular", 0.02, AVORIO, pos=(0.375, 0.46),
           track=1.15, extra={"End": Expr(ease_io(st(18, 30))), "LineSpacing": 1.3}),
        *hline("LineaA", 0.375, 0.385, 0.028, 3, TERRA, ease_io(st(40, 16))),
        *vline("Divisore", 0.535, 0.37, 0.26, 2, AVORIO, ease_io(st(10, 26))),
        tx("Data", "12 MAR 1973", SANS, "Regular", 0.02, AVORIO, pos=(0.565, 0.58), track=1.15),
        *hline("LineaB", 0.565, 0.535, 0.075, 3, TERRA, ease_io(st(30, 20))),
        tx("Info", "AFG\nASIA", SANS, "Regular", 0.016, AVORIO, pos=(0.565, 0.46), track=1.3,
           extra={"LineSpacing": 1.3}),
    ]
    data_fade = f"Ctrl.DateCol*{ease_out(st(24, 18))}"
    mt, last = stack([
        ("Pannello", Expr(f"Ctrl.Panel*{ease_out(st(0, 14))}")),
        ("Luogo", Expr(ease_out(st(4, 20)))), ("Coord", None), ("LineaA", None),
        ("Divisore", Expr(f"Ctrl.DateCol*0.45")), ("Data", Expr(data_fade)),
        ("LineaB", Expr("Ctrl.DateCol")), ("Info", Expr(data_fade))])
    return title_macro("LDF_Coordinate", tools + mt, c,
                       [Exposed("Luogo", "StyledText", "Luogo"), Exposed("Coord", "StyledText", "Coordinate"),
                        Exposed("Data", "StyledText", "Data"), Exposed("Info", "StyledText", "Info (paese, continente)"),
                        Exposed("Luogo", "Font", "Font"), Exposed("Pannello", "TopLeftAlpha", "Opacità pannello", 0.94)],
                       center=(0.24, 0.24), last=last)


def scheda(name, lines, underline_after, underline_len=0.05):
    """Left-aligned stacked text card: [(tool, text, font, style, size, rgb, track, y)]."""
    c = {**BASE_CONTROLS, "Shadow": checkbox("Ombra morbida per leggibilità su foto", 0)}
    x, tools, layers = 0.08, [], []
    for i, (tool, text, font, style, size, rgb, track, y) in enumerate(lines):
        stage = st(i * 10, 22)
        t = tx(tool, text, font, style, size, rgb, track=track, center_expr=rise(x, y, stage),
               extra={"Enabled3": Expr("Ctrl.Shadow"), "ElementShape3": 0, "Red3": 0, "Green3": 0,
                      "Blue3": 0, "Alpha3": 0.6, "Offset3": (0.0, -0.004), "Softness3": 1,
                      "SoftnessX3": 12, "SoftnessY3": 12, "PriorityBack3": 5, "PriorityBack1": 10})
        tools.append(t)
        layers.append((tool, Expr(ease_out(stage))))
        if tool == underline_after:
            ly = y - 0.045
            tools += hline("Linea", x, ly, underline_len, 4, TERRA, ease_io(st(i * 10 + 12, 24)))
            layers.append(("Linea", None))
    mt, last = stack(layers)
    exposed = []
    for tool, *_rest in lines:
        exposed += [Exposed(tool, "StyledText", tool)]
    exposed += [Exposed(lines[0][0], "Font", "Font nome"), Exposed(lines[0][0], "Size", "Dimensione nome", lines[0][4]),
                Exposed(lines[1][0], "Font", "Font testi")]
    return title_macro(name, tools + mt, c, exposed, center=(0.5, 0.5), last=last)


def t_persona():
    return scheda("LDF_Persona", [
        ("Nome", "GEORGE WEAH", SERIF, SERIF_STYLE, 0.05, AVORIO, 1.0, 0.25),
        ("Descrizione", "DALLA LIBERIA AL MONDO", SANS, "Regular", 0.016, AVORIO, 1.35, 0.185),
        ("Periodo", "1966  —  1995", SANS, "Regular", 0.016, AVORIO, 1.2, 0.145),
    ], underline_after="Periodo", underline_len=0.07)


def t_club():
    return scheda("LDF_Club", [
        ("Club", "AL AHLY", SERIF, SERIF_STYLE, 0.062, AVORIO, 1.0, 0.3),
        ("Payoff", "IL CLUB DEL POPOLO", SERIF, SERIF_STYLE, 0.024, AVORIO, 1.05, 0.225),
        ("Citta", "IL CAIRO, EGITTO", SANS, "Regular", 0.015, AVORIO, 1.35, 0.17),
        ("Fondazione", "EST. 1907", SANS, "Regular", 0.015, TERRA, 1.35, 0.135),
    ], underline_after="Payoff", underline_len=0.05)


def t_evento():
    c = {**BASE_CONTROLS, **GREEN_BG_CTRL,
         "Year": slider("Anno", 1986, 1850, 2030, integer=True, allowed=(0, 3000)),
         "Count": checkbox("L'anno scorre fino alla data (passaggio del tempo)", 0),
         "CountFrom": slider("Anni di scorrimento", 30, 5, 100, integer=True, allowed=(1, 1000))}
    x = 0.08
    year = (f":local y=Ctrl.Year\n"
            f"if Ctrl.Count>0.5 then y=Ctrl.Year-Ctrl.CountFrom*(1-{ease_out(st(0, 40))}) end\n"
            f"return Text(string.format('%d', floor(y+0.5)))")
    tools = [
        green_bg_layer()[0],
        tx("Anno", "1986", SERIF, SERIF_STYLE, 0.13, AVORIO, center_expr=rise(x, 0.58, st(0, 26), 0.02),
           extra={"StyledText": Expr(year)}),
        *hline("Linea", x, 0.47, 0.12, 4, TERRA, ease_io(st(16, 26))),
        tx("Evento", "UN MONDIALE\nDUE MONDI", SERIF, SERIF_STYLE, 0.034, AVORIO,
           center_expr=rise(x, 0.39, st(28, 22)), extra={"LineSpacing": 1.05}),
    ]
    mt, last = stack([green_bg_layer()[1], ("Anno", Expr(ease_out(st(0, 20)))), ("Linea", None),
                      ("Evento", Expr(ease_out(st(28, 22))))])
    return title_macro("LDF_Evento", tools + mt, c,
                       [Exposed("Evento", "StyledText", "Titolo evento"), Exposed("Anno", "Font", "Font"),
                        Exposed("Anno", "Size", "Dimensione anno", 0.13),
                        Exposed("Anno", "Red1", "Colore anno", group=1), Exposed("Anno", "Green1", group=1),
                        Exposed("Anno", "Blue1", group=1)], last=last)


def t_archivio():
    c = {**BASE_CONTROLS, "Paper": checkbox("Cartoncino avorio dietro al testo", 1)}
    tools = [
        Tool("CartaMask", "RectangleMask", {"Center": (0.5, 0.5), "Width": 0.3, "Height": 0.2}),
        solid("Carta", AVORIO, {"EffectMask": Conn("CartaMask", "Mask")}),
        Tool("Grana", "FastNoise", {**FRAME, "Detail": 6, "XScale": 60, "Contrast": 1.2,
                                    "EffectMask": Conn("CartaMask", "Mask")}),
        Tool("CartaGrana", "Merge", {"Background": Conn("Carta"), "Foreground": Conn("Grana"),
                                     "ApplyMode": FuID("Multiply"), "Blend": 0.06, "PerformDepthMerge": 0}),
        tx("Anno", "1970", SERIF, SERIF_STYLE, 0.058, TERRA, pos=(0.375, 0.5)),
        tx("Didascalia", "Una squadra\nun paese\nun cambiamento", SERIF, SERIF_STYLE, 0.019, ARDESIA,
           pos=(0.5, 0.5), extra={"LineSpacing": 1.0}),
    ]
    mt, last = stack([("CartaGrana", Expr(f"Ctrl.Paper*{ease_out(st(0, 16))}")),
                      ("Anno", Expr(ease_out(st(8, 20)))), ("Didascalia", Expr(ease_out(st(18, 22))))])
    rise_t = Tool("Sale", "Transform", {"Input": Conn(last),
                                        "Center": Expr(f"Point(0.5, 0.5-(1-{ease_out(st(0, 26))})*0.01)")})
    return title_macro("LDF_Archivio", tools + mt + [rise_t], c, [
        Exposed("Anno", "StyledText", "Anno"), Exposed("Didascalia", "StyledText", "Didascalia"),
        Exposed("Anno", "Font", "Font"),
        Exposed("Didascalia", "Center", "Posizione didascalia"), Exposed("Anno", "Center", "Posizione anno"),
        Exposed("CartaMask", "Width", "Larghezza cartoncino"), Exposed("CartaMask", "Height", "Altezza cartoncino"),
        Exposed("Didascalia", "Red1", "Colore testo", group=1), Exposed("Didascalia", "Green1", group=1),
        Exposed("Didascalia", "Blue1", group=1)], center=(0.26, 0.2), last="Sale")


def t_timeline():
    n_max = 6
    years = ["1950", "1970", "1990", "2010", "2020", "2030"]
    c = {**BASE_CONTROLS, "Count": slider("Numero di punti", 4, 2, 6, integer=True, allowed=(2, 6)),
         "DrawDur": slider("Durata tracciamento (frame)", 60, 10, 200, integer=True, allowed=(1, 2000))}
    x0, x1, y = 0.12, 0.88, 0.5
    prog = ease_io(clamp01(f"({T}-6*Ctrl.Speed)/max(Ctrl.DrawDur*Ctrl.Speed,1)"))
    tools = hline("Linea", x0, y, x1 - x0, 3, TERRA, prog)
    layers = [("Linea", None)]
    for i in range(n_max):
        xi = f"({x0}+0.04+({x1 - x0 - 0.08})*{i}/max(Ctrl.Count-1,1))"
        reach = f"(({xi}-{x0})/{x1 - x0})"
        # progress at which the drawn line reaches this point -> local 0..1 after that
        after = clamp01(f"(({prog})-{reach})*8")
        vis = f"iif({i}<Ctrl.Count,1,0)"
        tools += dot(f"Punto{i + 1}", f"Point({xi}, {y})", 13, TERRA, f"{vis}*{ease_out(after)}")
        tools.append(tx(f"Anno{i + 1}", years[i], SANS, "Regular", 0.016, AVORIO, track=1.2, left=False,
                        center_expr=Expr(f"Point({xi}, {y}+0.045-(1-{ease_out(after)})*0.01)")))
        layers += [(f"Punto{i + 1}", None), (f"Anno{i + 1}", Expr(f"{vis}*{ease_out(after)}"))]
    mt, last = stack(layers)
    exposed = [Exposed(f"Anno{i + 1}", "StyledText", f"Punto {i + 1}") for i in range(n_max)]
    exposed += [Exposed("Linea", "TopLeftRed", "Colore linea", group=1),
                Exposed("Linea", "TopLeftGreen", group=1), Exposed("Linea", "TopLeftBlue", group=1)]
    m = title_macro("LDF_Timeline", tools + mt, c, exposed, center=(0.5, 0.5), last=last)
    for t in m.tools:
        if t.name.startswith("Punto") and t.kind == "Background":
            t.inputs.update({"TopLeftRed": Expr("Linea.TopLeftRed"), "TopLeftGreen": Expr("Linea.TopLeftGreen"),
                             "TopLeftBlue": Expr("Linea.TopLeftBlue")})
    return m


def t_rotta():
    """A route drawn from point A to point B along a gentle arc."""
    c = {**BASE_CONTROLS,
         "DrawDur": slider("Durata tracciamento (frame)", 50, 10, 200, integer=True, allowed=(1, 2000)),
         "Bulge": slider("Curvatura", 0.22, 0.05, 0.8),
         "Down": checkbox("Curva verso il basso", 0),
         "Thick": slider("Spessore rotta (pixel)", 4, 1, 16)}
    A, B = "PuntoAMask.Center", "PuntoBMask.Center"
    dx, dy = f"(({B}.X-{A}.X)*{OW})", f"(({B}.Y-{A}.Y)*{OH})"
    scale = f"(math.sqrt({dx}^2+{dy}^2)/(0.4*{OW}))"
    draw = ease_io(clamp01(f"({T}-10*Ctrl.Speed)/max(Ctrl.DrawDur*Ctrl.Speed,1)"))
    # Canonical arc: chord from x=0.3 to 0.7 at y=0.5 in a frame-sized image, built as the
    # top part of an elliptical ring (outer minus inner ellipse), revealed by a wipe.
    a_px = f"(0.3*{OW})"
    b_px = f"(Ctrl.Bulge*0.4*{OW}/0.2546)"
    t_px = f"(Ctrl.Thick/max({scale},0.05))"
    cy = f"(0.5-({b_px})*0.7454/{OH})"
    tools = [
        *dot("PuntoA", (0.25, 0.4), 16, AVORIO, ease_out(st(0, 10))),
        *dot("PuntoB", (0.75, 0.6), 16, AVORIO, ease_out(clamp01(
            f"({T}-(10*Ctrl.Speed+Ctrl.DrawDur*Ctrl.Speed))/max(10*Ctrl.Speed,1)"))),
        Tool("ArcoEsterno", "EllipseMask", {"Center": Expr(f"Point(0.5, {cy})"),
                                            "Width": Expr(f"2*({a_px}+{t_px}/2)/{OW}"),
                                            "Height": Expr(f"2*({b_px}+{t_px}/2)/{OH}")}),
        Tool("ArcoInterno", "EllipseMask", {"EffectMask": Conn("ArcoEsterno", "Mask"),
                                            "PaintMode": FuID("Subtract"),
                                            "Center": Expr(f"Point(0.5, {cy})"),
                                            "Width": Expr(f"2*({a_px}-{t_px}/2)/{OW}"),
                                            "Height": Expr(f"2*({b_px}-{t_px}/2)/{OH}")}),
        Tool("Traccia", "RectangleMask", {"EffectMask": Conn("ArcoInterno", "Mask"),
                                          "PaintMode": FuID("Minimum"),
                                          "Center": Expr(f"Point(0.29+(0.42*{draw})/2, 0.75)"),
                                          "Width": Expr(f"0.42*{draw}"), "Height": 0.5}),
        solid("Arco", TERRA, {"EffectMask": Conn("Traccia", "Mask")}),
        Tool("Rotta", "Transform", {"Input": Conn("Arco"),
                                    "Center": Expr(f"Point(({A}.X+{B}.X)/2, ({A}.Y+{B}.Y)/2)"),
                                    "Angle": Expr(f"math.atan2({dy},{dx})*180/pi"),
                                    "Size": Expr(scale), "FlipVert": Expr("Ctrl.Down")}),
    ]
    labels = []
    for p, name, coord, delay in (("A", "DAKAR", "14.7167° N  17.4677° W", "0"),
                                  ("B", "RIO DE JANEIRO", "22.9068° S  43.1729° W", "(10+Ctrl.DrawDur)")):
        stage = clamp01(f"({T}-({delay}+8)*Ctrl.Speed)/max(18*Ctrl.Speed,1)")
        pc = f"Punto{p}Mask.Center"
        tools.append(tx(f"Nome{p}", name, SANS, "Bold", 0.015, AVORIO, track=1.25,
                        center_expr=Expr(f"Point({pc}.X+0.012, {pc}.Y+0.032)")))
        tools.append(tx(f"Coord{p}", coord, SANS, "Regular", 0.012, AVORIO, track=1.15,
                        center_expr=Expr(f"Point({pc}.X+0.012, {pc}.Y+0.006)")))
        labels += [(f"Nome{p}", Expr(ease_out(stage))), (f"Coord{p}", Expr(ease_out(stage)))]
    mt, last = stack([("Rotta", None), ("PuntoA", None), ("PuntoB", None), *labels])
    ctrl = Tool("Ctrl", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn(last),
                                  "PerformDepthMerge": 0, "Blend": Expr(OUT), **ctrl_values(c)}, controls=c)
    return Macro("LDF_Rotta", [canvas(), *tools, *mt, ctrl], "Ctrl", [
        Exposed("PuntoAMask", "Center", "Punto di partenza"), Exposed("PuntoBMask", "Center", "Punto di arrivo"),
        Exposed("NomeA", "StyledText", "Luogo partenza"), Exposed("CoordA", "StyledText", "Coordinate partenza"),
        Exposed("NomeB", "StyledText", "Luogo arrivo"), Exposed("CoordB", "StyledText", "Coordinate arrivo"),
    ] + [Exposed("Ctrl", k) for k in c])


def t_punto():
    c = {**BASE_CONTROLS, "Pulse": checkbox("Anello che pulsa lentamente", 1)}
    P = "PuntoMask.Center"
    ring_t = f"(({T}%60)/60)"
    ring_r = f"(10+50*{ease_out(ring_t)})"
    tools = [
        *dot("Punto", (0.5, 0.5), 14, TERRA, ease_out(st(0, 12))),
        Tool("AnelloEst", "EllipseMask", {"Center": Expr(P), "Width": Expr(f"2*({ring_r}+1.5)/{OW}"),
                                          "Height": Expr(f"2*({ring_r}+1.5)/{OH}")}),
        Tool("AnelloInt", "EllipseMask", {"EffectMask": Conn("AnelloEst", "Mask"), "PaintMode": FuID("Subtract"),
                                          "Center": Expr(P), "Width": Expr(f"2*({ring_r}-1.5)/{OW}"),
                                          "Height": Expr(f"2*({ring_r}-1.5)/{OH}")}),
        solid("Anello", TERRA, {"EffectMask": Conn("AnelloInt", "Mask")}),
        tx("Nome", "SEOUL", SANS, "Bold", 0.02, AVORIO, track=1.2,
           center_expr=Expr(f"Point({P}.X+0.018, {P}.Y+0.012)")),
        tx("Coord", "37.5665° N  126.9780° E", SANS, "Regular", 0.013, AVORIO, track=1.15,
           center_expr=Expr(f"Point({P}.X+0.018, {P}.Y-0.018)")),
    ]
    mt, last = stack([("Anello", Expr(f"Ctrl.Pulse*(1-{ring_t})*0.8*{st(12, 10)}")), ("Punto", None),
                      ("Nome", Expr(ease_out(st(8, 18)))), ("Coord", Expr(ease_out(st(16, 18))))])
    ctrl = Tool("Ctrl", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn(last),
                                  "PerformDepthMerge": 0, "Blend": Expr(OUT), **ctrl_values(c)}, controls=c)
    return Macro("LDF_PuntoLuogo", [canvas(), *tools, *mt, ctrl], "Ctrl", [
        Exposed("PuntoMask", "Center", "Posizione punto"),
        Exposed("Nome", "StyledText", "Luogo"), Exposed("Coord", "StyledText", "Coordinate"),
    ] + [Exposed("Ctrl", k) for k in c])


def t_campo():
    """The line becomes a football pitch (motion identity step 7)."""
    c = {**BASE_CONTROLS, **GREEN_BG_CTRL, "PitchW": slider("Larghezza campo", 0.5, 0.2, 0.9)}
    # Pitch geometry in metres (105 x 68), converted to frame-relative units.
    pw = "(Ctrl.PitchW)"                                   # width, frame-width relative
    m2x = f"({pw}/105)"                                    # metres -> width units
    m2y = f"({pw}*{OW}/105/{OH})"                          # metres -> height units
    t = 2.5                                                # line thickness in px
    tx_ = f"({t}/{OW})"
    ty_ = f"({t}/{OH})"
    reveal = ease_io(st(34, 40))
    rects = []  # (name, cx_m, cy_m, w_m, h_m) in metres from pitch centre; lines have 0 size -> thickness

    def r(name, cx, cy, w, h):
        rects.append((name, cx, cy, w, h))

    r("Fondo1", -52.5, 0, 0, 68); r("Fondo2", 52.5, 0, 0, 68)
    r("Lato1", 0, 34, 105, 0); r("Lato2", 0, -34, 105, 0)
    r("Meta", 0, 0, 0, 68)
    for s, sign in (("S", -1), ("D", 1)):
        r(f"Area{s}1", sign * (52.5 - 16.5), 0, 0, 40.32)
        r(f"Area{s}2", sign * (52.5 - 8.25), 20.16, 16.5, 0)
        r(f"Area{s}3", sign * (52.5 - 8.25), -20.16, 16.5, 0)
        r(f"Porta{s}1", sign * (52.5 - 5.5), 0, 0, 18.32)
        r(f"Porta{s}2", sign * (52.5 - 2.75), 9.16, 5.5, 0)
        r(f"Porta{s}3", sign * (52.5 - 2.75), -9.16, 5.5, 0)
    tools = [
        green_bg_layer()[0],
        Tool("CerchioEst", "EllipseMask", {"Center": (0.5, 0.5),
                                           "Width": Expr(f"2*9.15*{m2x}+{tx_}"), "Height": Expr(f"2*9.15*{m2y}+{ty_}")}),
        Tool("CerchioInt", "EllipseMask", {"EffectMask": Conn("CerchioEst", "Mask"), "PaintMode": FuID("Subtract"),
                                           "Center": (0.5, 0.5),
                                           "Width": Expr(f"2*9.15*{m2x}-{tx_}"), "Height": Expr(f"2*9.15*{m2y}-{ty_}")}),
    ]
    prev = "CerchioInt"
    for name, cx, cy, w, h in rects:
        tools.append(Tool(name, "RectangleMask", {
            "EffectMask": Conn(prev, "Mask"),
            "Center": Expr(f"Point(0.5+({cx})*{m2x}, 0.5+({cy})*{m2y})"),
            "Width": Expr(f"({w})*{m2x}+{tx_}"), "Height": Expr(f"({h})*{m2y}+{ty_}")}))
        prev = name
    tools += [
        Tool("Svela", "RectangleMask", {"EffectMask": Conn(prev, "Mask"), "PaintMode": FuID("Minimum"),
                                        "Center": (0.5, 0.5), "Width": Expr(f"({pw}+0.02)*{reveal}"), "Height": 1.2}),
        solid("Campo", AVORIO, {"EffectMask": Conn("Svela", "Mask")}),
        *hline("Linea", 0.5, 0.5, f"({pw}+0.06)", 4, TERRA, ease_io(st(8, 30)), from_center=True),
        *dot("Centro", (0.5, 0.5), 12, TERRA, ease_out(st(0, 12))),
    ]
    mt, last = stack([green_bg_layer()[1], ("Campo", Expr(f"0.85*{ease_out(st(34, 20))}")),
                      ("Linea", None), ("Centro", None)])
    return title_macro("LDF_Campo", tools + mt, c, [], center=(0.5, 0.5), last=last)


# --------------------------------------------------------------------------- #
# TRANSITIONS — slow and sober
# --------------------------------------------------------------------------- #
P = "Ctrl.Mix"
IW = "ClipA.Input.OriginalWidth"
IH = "ClipA.Input.OriginalHeight"


def progress(controls):
    return [Tool("Ctrl", "Dissolve", {"Mix": Conn("CtrlCurve", "Value"), **ctrl_values(controls)},
                 controls=controls), *anim_curves("CtrlCurve")]


def clip_inputs():
    return [Tool("ClipA", "Transform", {}), Tool("ClipB", "Transform", {})]


MAINS = [("ClipA", "Input", "Clip in uscita"), ("ClipB", "Input", "Clip in entrata")]


def tr_dip_verde():
    c = {"Line": checkbox("Linea terracotta al centro", 1),
         "Hold": slider("Tenuta sul verde", 0.3, 0, 0.8)}
    amt = clamp01(f"(1-abs(2*{P}-1))/max(1-Ctrl.Hold,0.05)")
    lp = ease_io(clamp01(f"({P}-0.2)/0.45"))
    tools = [
        *clip_inputs(),
        Tool("Taglio", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                    "Mix": Expr(f"iif({P}<0.5,0,1)")}),
        solid("Verde", VERDE),
        Tool("LineaMask", "RectangleMask", {"Center": (0.5, 0.5), "Width": Expr(f"0.3*{lp}"),
                                            "Height": Expr(f"4/{IH}")}),
        solid("Linea", TERRA, {"EffectMask": Conn("LineaMask", "Mask")}),
        Tool("VerdeLinea", "Merge", {"Background": Conn("Verde"), "Foreground": Conn("Linea"),
                                     "Blend": Expr("Ctrl.Line"), "PerformDepthMerge": 0}),
        Tool("Uscita", "Merge", {"Background": Conn("Taglio"), "Foreground": Conn("VerdeLinea"),
                                 "Blend": Expr(ease_io(amt)), "PerformDepthMerge": 0}),
        *progress(c),
    ]
    return Macro("LDF_DipVerde", tools, "Uscita", [Exposed("Ctrl", k) for k in c], MAINS)


def tr_linea_apre():
    c = {"Thick": slider("Spessore linea (pixel)", 4, 1, 16)}
    draw = ease_io(clamp01(f"{P}/0.4"))
    open_ = ease_io(clamp01(f"({P}-0.4)/0.6"))
    tools = [
        *clip_inputs(),
        Tool("Banda", "RectangleMask", {"Center": (0.5, 0.5), "Width": 1.2, "Height": Expr(f"1.02*{open_}")}),
        Tool("Apertura", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                   "EffectMask": Conn("Banda", "Mask"), "PerformDepthMerge": 0}),
        Tool("LineaMask", "RectangleMask", {"Center": Expr(f"Point({draw}/2, 0.5)"), "Width": Expr(draw),
                                            "Height": Expr(f"Ctrl.Thick/{IH}")}),
        solid("Linea", TERRA, {"EffectMask": Conn("LineaMask", "Mask")}),
        Tool("Uscita", "Merge", {"Background": Conn("Apertura"), "Foreground": Conn("Linea"),
                                 "Blend": Expr(f"1-{clamp01(f'({P}-0.55)/0.35')}"), "PerformDepthMerge": 0}),
        *progress(c),
    ]
    return Macro("LDF_LineaApre", tools, "Uscita", [Exposed("Ctrl", k) for k in c], MAINS)


def tr_scorrimento():
    c = {"Rev": checkbox("Inverti direzione", 0),
         "Thick": slider("Spessore linea (pixel)", 4, 0, 16)}
    e = ease_io(P)
    s = "iif(Ctrl.Rev>0.5,-1,1)"
    tools = [
        Tool("ClipA", "Transform", {"Center": Expr(f"Point(0.5-{s}*{e}, 0.5)"), "Edges": 0}),
        Tool("ClipB", "Transform", {"Center": Expr(f"Point(0.5+{s}*(1-{e}), 0.5)"), "Edges": 0}),
        Tool("Spinta", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"), "PerformDepthMerge": 0}),
        Tool("LineaMask", "RectangleMask", {"Center": Expr(f"Point(0.5+{s}*(0.5-{e}), 0.5)"),
                                            "Width": Expr(f"Ctrl.Thick/{IW}"), "Height": 1.1}),
        solid("Linea", TERRA, {"EffectMask": Conn("LineaMask", "Mask")}),
        Tool("Uscita", "Merge", {"Background": Conn("Spinta"), "Foreground": Conn("Linea"),
                                 "Blend": Expr(f"iif({P}>0.001 and {P}<0.999,1,0)"), "PerformDepthMerge": 0}),
        *progress(c),
    ]
    return Macro("LDF_ScorrimentoLinea", tools, "Uscita", [Exposed("Ctrl", k) for k in c], MAINS)


def tr_tendina():
    c = {"Rev": checkbox("Inverti direzione", 0),
         "Thick": slider("Spessore linea (pixel)", 4, 0, 16)}
    e = ease_io(P)
    x = f"iif(Ctrl.Rev>0.5, 1-{e}, {e})"
    tools = [
        *clip_inputs(),
        Tool("Area", "RectangleMask", {"Center": Expr(f"Point(iif(Ctrl.Rev>0.5, 1-{e}/2, {e}/2), 0.5)"),
                                       "Width": Expr(e), "Height": 1.1}),
        Tool("Tendina", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                  "EffectMask": Conn("Area", "Mask"), "PerformDepthMerge": 0}),
        Tool("LineaMask", "RectangleMask", {"Center": Expr(f"Point({x}, 0.5)"),
                                            "Width": Expr(f"Ctrl.Thick/{IW}"), "Height": 1.1}),
        solid("Linea", TERRA, {"EffectMask": Conn("LineaMask", "Mask")}),
        Tool("Uscita", "Merge", {"Background": Conn("Tendina"), "Foreground": Conn("Linea"),
                                 "Blend": Expr(f"iif({P}>0.001 and {P}<0.999,1,0)"), "PerformDepthMerge": 0}),
        *progress(c),
    ]
    return Macro("LDF_TendinaLinea", tools, "Uscita", [Exposed("Ctrl", k) for k in c], MAINS)


def tr_morbida():
    c = {"Push": slider("Leggero avvicinamento", 0.03, 0, 0.1)}
    tools = [
        Tool("ClipA", "Transform", {"Size": Expr(f"1+Ctrl.Push*{P}")}),
        Tool("ClipB", "Transform", {"Size": Expr(f"1+Ctrl.Push*(1-{P})")}),
        Tool("Dissolvenza", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                         "Mix": Expr(ease_io(P))}),
        *progress(c),
    ]
    return Macro("LDF_DissolvenzaMorbida", tools, "Dissolvenza", [Exposed("Ctrl", k) for k in c], MAINS)


# --------------------------------------------------------------------------- #
# EFFECTS
# --------------------------------------------------------------------------- #
def fx_foto_archivio():
    c = {"Scale": slider("Dimensione foto", 0.7, 0.3, 1),
         "Tilt": slider("Rotazione (gradi)", -1.5, -8, 8),
         "Border": slider("Bordo carta (pixel)", 14, 0, 60),
         "Drift": slider("Movimento lento", 0.04, 0, 0.15),
         "GreenBg": checkbox("Sfondo verde (altrimenti trasparente)", 1)}
    iw, ih = "Foto.Input.OriginalWidth", "Foto.Input.OriginalHeight"
    p = ease_io(clamp01(f"{T}/{LEN}"))
    tools = [
        Tool("Foto", "Transform", {"Size": Expr("Ctrl.Scale"), "Angle": Expr("Ctrl.Tilt"), "Center": (0.5, 0.5)}),
        solid("Verde", VERDE, {"TopLeftAlpha": Expr("Ctrl.GreenBg"), "TopLeftRed": Expr(f"{VERDE[0]}*Ctrl.GreenBg"),
                               "TopLeftGreen": Expr(f"{VERDE[1]}*Ctrl.GreenBg"),
                               "TopLeftBlue": Expr(f"{VERDE[2]}*Ctrl.GreenBg")}),
        Tool("BordoMask", "RectangleMask", {"Center": Expr("Foto.Center"), "Angle": Expr("Ctrl.Tilt"),
                                            "Width": Expr(f"Ctrl.Scale+2*Ctrl.Border/{iw}"),
                                            "Height": Expr(f"Ctrl.Scale+2*Ctrl.Border/{ih}")}),
        solid("Bordo", AVORIO, {"EffectMask": Conn("BordoMask", "Mask")}),
        Tool("ConBordo", "Merge", {"Background": Conn("Verde"), "Foreground": Conn("Bordo"), "PerformDepthMerge": 0}),
        Tool("ConFoto", "Merge", {"Background": Conn("ConBordo"), "Foreground": Conn("Foto"), "PerformDepthMerge": 0}),
        Tool("Ctrl", "Transform", {"Input": Conn("ConFoto"), "Size": Expr(f"1+Drift*{p}"),
                                   "Center": Expr(f"Point(0.5-Drift*0.25*{p}, 0.5)"), **ctrl_values(c)},
             controls=c),
    ]
    return Macro("LDF_FotoArchivio", tools, "Ctrl",
                 [Exposed("Foto", "Center", "Posizione foto")] + [Exposed("Ctrl", k) for k in c]
                 + [Exposed("Bordo", "TopLeftRed", "Colore bordo", group=1),
                    Exposed("Bordo", "TopLeftGreen", group=1), Exposed("Bordo", "TopLeftBlue", group=1)],
                 [("Foto", "Input", "Input")])


def fx_movimento():
    c = {"Mode": combo("Movimento", ["Avvicina", "Allontana", "Verso destra", "Verso sinistra", "Verso l'alto",
                                     "Verso il basso"], 0),
         "Amount": slider("Ampiezza", 0.06, 0, 0.3)}
    p = ease_io(clamp01(f"{T}/{LEN}"))
    size = Expr(f":local p={p}\nlocal a=Amount\n"
                f"if Mode==0 then return 1+a*p end\n"
                f"if Mode==1 then return 1+a*(1-p) end\n"
                f"return 1+a")
    center = Expr(f":local p={p}\nlocal a=Amount/2\n"
                  f"if Mode==2 then return Point(0.5+a-2*a*p, 0.5) end\n"
                  f"if Mode==3 then return Point(0.5-a+2*a*p, 0.5) end\n"
                  f"if Mode==4 then return Point(0.5, 0.5+a-2*a*p) end\n"
                  f"if Mode==5 then return Point(0.5, 0.5-a+2*a*p) end\n"
                  f"return Point(0.5, 0.5)")
    tools = [Tool("Ctrl", "Transform", {"Size": size, "Center": center, "Edges": 3, **ctrl_values(c)}, controls=c)]
    return Macro("LDF_MovimentoDocumentario", tools, "Ctrl", [Exposed("Ctrl", k) for k in c]
                 + [Exposed("Ctrl", "Pivot", "Punto di zoom")], [("Ctrl", "Input", "Input")])


def fx_texture():
    tools = [
        Tool("Fine", "FastNoise", {**FRAME, "Detail": 8, "XScale": 90, "Contrast": 1.4}),
        Tool("Ampia", "FastNoise", {**FRAME, "Detail": 2, "XScale": 1.5, "Contrast": 0.8}),
        Tool("Grana", "Merge", {"Foreground": Conn("Fine"), "ApplyMode": FuID("Multiply"),
                                "Blend": 0.05, "PerformDepthMerge": 0}),
        Tool("Ctrl", "Merge", {"Background": Conn("Grana"), "Foreground": Conn("Ampia"),
                               "ApplyMode": FuID("Overlay"), "Blend": 0.04, "PerformDepthMerge": 0}),
    ]
    return Macro("LDF_TextureCarta", tools, "Ctrl", [
        Exposed("Grana", "Blend", "Micro-grana carta", 0.05),
        Exposed("Ctrl", "Blend", "Variazioni di tono", 0.04),
    ], [("Grana", "Background", "Input")])


def fx_look(key):
    tools = [Tool("Ctrl", "FileLUT", {"LUTFile": f"Setting:{PREFIX}_{key}.cube", "Blend": 0.7})]
    return Macro(f"{PREFIX}_Look_{key}", tools, "Ctrl",
                 [Exposed("Ctrl", "Blend", "Intensità look", 0.7)], [("Ctrl", "Input", "Input")])


# --------------------------------------------------------------------------- #
# GENERATORS
# --------------------------------------------------------------------------- #
def g_sfondo(name, rgb, grain):
    tools = [
        solid("Colore", rgb),
        Tool("Fine", "FastNoise", {**FRAME, "Detail": 8, "XScale": 90, "Contrast": 1.4}),
        Tool("Ctrl", "Merge", {"Background": Conn("Colore"), "Foreground": Conn("Fine"),
                               "ApplyMode": FuID("Multiply"), "Blend": grain, "PerformDepthMerge": 0}),
    ]
    return Macro(name, tools, "Ctrl", [
        Exposed("Colore", "TopLeftRed", "Colore", group=1), Exposed("Colore", "TopLeftGreen", group=1),
        Exposed("Colore", "TopLeftBlue", group=1), Exposed("Ctrl", "Blend", "Texture carta", grain)])


# --------------------------------------------------------------------------- #
LOOKS = [
    ("Editoriale", "Look Editoriale", "Neri ardesia e bianchi avorio: armonizza senza cambiare la foto"),
    ("ArchivioBN", "Look Archivio B&N", "Per materiale in bianco e nero: neutro, neri morbidi, niente seppia"),
]

CATALOG = [
    ("Titles", "LDF Linea", t_linea, "La linea appare e si estende (sottolineature, divisori, verticale ruotandola)"),
    ("Titles", "LDF Titolo Editoriale", t_titolo, "Sopratitolo, titolo serif, linea che si disegna, sottotitolo"),
    ("Titles", "LDF Coordinate", t_coordinate, "Luogo, coordinate, data e paese in pannello verde"),
    ("Titles", "LDF Persona", t_persona, "Nome, descrizione e periodo con linea terracotta"),
    ("Titles", "LDF Club", t_club, "Nome del club, payoff, città e anno di fondazione"),
    ("Titles", "LDF Evento", t_evento, "Anno dominante (con scorrimento opzionale) e titolo dell'evento"),
    ("Titles", "LDF Archivio", t_archivio, "Didascalia per foto d'archivio: anno terracotta su cartoncino avorio"),
    ("Titles", "LDF Timeline", t_timeline, "La linea diventa un asse temporale con 2-6 date"),
    ("Titles", "LDF Rotta", t_rotta, "La linea diventa una rotta tra due luoghi, con coordinate"),
    ("Titles", "LDF Punto Luogo", t_punto, "Punto sulla mappa con nome e coordinate"),
    ("Titles", "LDF Campo", t_campo, "La linea si trasforma nel campo da calcio"),
    ("Transitions", "LDF Dip Verde", tr_dip_verde, "Passaggio sul verde profondo con la linea al centro"),
    ("Transitions", "LDF Linea Apre", tr_linea_apre, "La linea attraversa l'immagine e si apre sulla scena nuova"),
    ("Transitions", "LDF Scorrimento Linea", tr_scorrimento, "Scorrimento orizzontale lento con linea di confine"),
    ("Transitions", "LDF Tendina Linea", tr_tendina, "Tendina guidata da una linea verticale"),
    ("Transitions", "LDF Dissolvenza Morbida", tr_morbida, "Dissolvenza con leggerissimo avvicinamento"),
    ("Effects", "LDF Foto Archivio", fx_foto_archivio, "Foto con bordo carta, lieve rotazione e movimento lento"),
    ("Effects", "LDF Movimento Documentario", fx_movimento, "Movimento lento su foto/filmati (zoom o panoramica)"),
    ("Effects", "LDF Texture Carta", fx_texture, "Texture carta discreta (micro-grana, niente vintage)"),
    *[("Effects", f"LDF {label}", (lambda k=k: fx_look(k)), desc) for k, label, desc in LOOKS],
    ("Generators", "LDF Sfondo Verde", lambda: g_sfondo("LDF_SfondoVerde", VERDE, 0.03),
     "Verde profondo con texture carta minima"),
    ("Generators", "LDF Sfondo Carta", lambda: g_sfondo("LDF_SfondoCarta", AVORIO, 0.06),
     "Avorio carta con micro-grana"),
]


# --------------------------------------------------------------------------- #
# LUTs
# --------------------------------------------------------------------------- #
def lut_editoriale(c):
    import luts
    black = __import__("numpy").array([0.118, 0.118, 0.118]) * 0.35
    white = __import__("numpy").array([0.985, 0.972, 0.95])
    c = luts.contrast(c, 1.04)
    return black + c * (white - black)


def lut_archivio_bn(c):
    import luts
    import numpy as np
    y = (c[..., 0] * 0.3 + c[..., 1] * 0.59 + c[..., 2] * 0.11)[..., None].repeat(3, -1)
    y = luts.contrast(y, 1.08)
    black = np.array([0.118, 0.118, 0.118]) * 0.6
    white = np.array([0.965, 0.945, 0.915])
    return black + y * (white - black)


LOOK_FUNCS = {"Editoriale": lut_editoriale, "ArchivioBN": lut_archivio_bn}


# --------------------------------------------------------------------------- #
# SOUNDS — sober, documentary
# --------------------------------------------------------------------------- #
def _sounds():
    import numpy as np
    import sfx
    from sfx import SR, bandpass, bell, env_ad, highpass, lowpass, noise, pan, place, sweep_bandpass, t_axis

    def linea(dur):
        x = sweep_bandpass(noise(dur), 900, 3200, 2000, q=3.5, peak_at=0.7)
        t = t_axis(dur)
        e = np.clip(t / (dur * 0.7), 0, 1) ** 1.5 * np.clip((dur - t) / (dur * 0.3), 0, 1)
        tone = np.sin(2 * np.pi * np.cumsum(440 + 220 * t / dur) / SR) * 0.05
        return pan((x + tone) * e, np.linspace(-0.5, 0.5, len(t)))

    def punto():
        tap = 0.3 * bandpass(noise(0.01), 2000, 8000) * env_ad(int(0.01 * SR), 0.0002, 10)
        return place(0.6, [(0, bell(1320, 0.6, partials=((1, 1), (2.0, 0.25), (3.0, 0.08)), decay=9)),
                           (0, tap)])

    def tick():
        return bandpass(noise(0.03), 1800, 6000) * env_ad(int(0.03 * SR), 0.0003, 12) + \
            0.4 * np.sin(2 * np.pi * 900 * t_axis(0.03)) * env_ad(int(0.03 * SR), 0.0005, 14)

    def carta(dur=0.9):
        x = bandpass(noise(dur), 1500, 9000)
        crackle = (np.random.default_rng(3).random(len(x)) > 0.997) * np.random.default_rng(4).standard_normal(len(x))
        t = t_axis(dur)
        return (x * 0.5 + highpass(crackle, 2000) * 2) * np.sin(np.pi * t / dur) ** 1.5

    def pagina(dur=0.8):
        x = sweep_bandpass(noise(dur), 800, 5000, 2500, q=1.5, peak_at=0.4)
        crackle = highpass((np.random.default_rng(9).random(len(x)) > 0.995) * 1.0, 3000)
        t = t_axis(dur)
        return (x + crackle) * np.sin(np.pi * t / dur) ** 2

    def timbro():
        thud = np.sin(2 * np.pi * 95 * t_axis(0.25)) * env_ad(int(0.25 * SR), 0.002, 14)
        slap = lowpass(noise(0.05), 2500) * env_ad(int(0.05 * SR), 0.0005, 9)
        return place(0.5, [(0, thud), (0, slap * 0.8)])

    def colpo(dur=3.5):
        t = t_axis(dur)
        low = np.sin(2 * np.pi * np.cumsum(60 - 18 * t / dur) / SR) * np.exp(-1.6 * t)
        body = lowpass(noise(dur), 400) * np.exp(-4 * t) * 0.8
        tail = lowpass(noise(dur), 1200) * np.exp(-1.2 * t) * 0.05
        return np.tanh(1.2 * (low + body)) + tail

    def morbida(dur=1.6):
        x = sweep_bandpass(noise(dur), 200, 1100, 300, q=1.2, peak_at=0.5)
        t = t_axis(dur)
        return pan(x * np.sin(np.pi * t / dur) ** 2, np.linspace(-0.4, 0.4, len(t)))

    def tappeto(dur=8.0):
        t = t_axis(dur)
        rng = np.random.default_rng(11)
        y = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * a
                for f, a in ((65.4, 0.5), (98.0, 0.35), (130.8, 0.2), (196.0, 0.08)))
        y *= 1 + 0.15 * np.sin(2 * np.pi * 0.08 * t)
        y *= np.clip(t / 2.5, 0, 1) * np.clip((dur - t) / 2.0, 0, 1)
        air = lowpass(noise(dur), 900) * 0.06 * np.clip(t / 3, 0, 1)
        return pan(y + air, 0.25 * np.sin(2 * np.pi * 0.05 * t))

    def macchina():
        rng = np.random.default_rng(21)
        parts, t = [], 0.05
        while t < 3.8:
            parts.append((t, sfx.key_stroke(rng.random()) * (0.5 + 0.3 * rng.random())))
            t += rng.uniform(0.12, 0.28)
        return lowpass(place(4.0, parts), 6000)

    return [
        ("Linea", "linea_traccia", lambda: linea(1.4), "Da sincronizzare con la linea che si disegna"),
        ("Linea", "linea_breve", lambda: linea(0.6), "Sottolineature e divisori brevi"),
        ("Mappa", "punto_mappa", punto, "Comparsa di un punto o di un luogo"),
        ("Mappa", "tick_timeline", tick, "Ogni data della timeline"),
        ("Archivio", "carta_foglio", carta, "Foto o documento che entra in scena"),
        ("Archivio", "pagina", pagina, "Cambio di documento / pagina"),
        ("Archivio", "timbro", timbro, "Data o didascalia che si fissa"),
        ("Archivio", "macchina_da_scrivere_archivio", macchina, "Coordinate e testi tecnici"),
        ("Racconto", "colpo_documentario", colpo, "Momento chiave, titolo capitolo (sobrio)"),
        ("Racconto", "transizione_morbida", morbida, "Transizioni lente (Dip Verde, Scorrimento)"),
        ("Racconto", "tappeto_documentario", tappeto, "Tappeto di tensione sotto la voce"),
    ]


SOUNDS = _sounds()
