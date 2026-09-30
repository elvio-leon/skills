"""Linea di Fondo Ritmo — the channel's pack for the intense moments.

The main Linea di Fondo pack is deliberately slow. This one keeps the same
identity (verde / avorio / terracotta, la linea, Optima) but moves fast:
social-style zooms that are fully adjustable, punchy transitions, focus and
flash hits, and titles that land with a snap.

All text uses Optima (Regular / Bold / Italic), available on the editing
machine without installing anything.
"""

from __future__ import annotations

from fusion import R, T, Conn, Expr, Exposed, FuID, Macro, Tool, anim_curves, checkbox, clamp01, combo, slider
from ldf import AVORIO, OH, OW, TERRA, VERDE, hline, st, vline
from templates import FRAME, canvas, ctrl_values, ease_in, ease_out, solid

PACK = "Linea di Fondo Ritmo"
PREFIX = "LDF"
FONT = "Optima"


def own(code: str) -> Expr:
    """Expression that lives on Ctrl itself: its controls are read by bare name."""
    return Expr(code.replace("Ctrl.", ""))


def snap(x):
    """Quartic ease-out: fast start, clean landing (the 'social' feel)."""
    return f"(1-(1-{x})^4)"


def back(x, k=1.2):
    return f"(1+{k + 1}*(({x})-1)^3+{k}*(({x})-1)^2)"


# --------------------------------------------------------------------------- #
# ZOOM SOCIAL — one engine, several presets, every parameter adjustable
# --------------------------------------------------------------------------- #
ZOOM_MODES = ["Zoom e resta", "Zoom e ritorno a fine clip", "Colpo: entra e torna",
              "Parte zoomato e si allarga", "Zoom a scalini", "Battito a ritmo"]
CURVES = ["Scatto (parte veloce)", "Morbida", "Accelera (parte lenta)", "Lineare", "Con rimbalzo"]

# Lua prelude shared by every input of the zoom. ``Ctrl.`` is stripped on Ctrl.
ZOOM_LUA = """local function cv(x)
  x=min(max(x,0),1)
  local m=Ctrl.Curve
  if m<0.5 then return 1-(1-x)^4 end
  if m<1.5 then if x<0.5 then return 4*x^3 end return 1-((-2*x+2)^3)/2 end
  if m<2.5 then return x^3 end
  if m<3.5 then return x end
  local k=Ctrl.Bounce
  return 1+(k+1)*(x-1)^3+k*(x-1)^2
end
local function st(f,a,d)
  if d<1 then if f>=a then return 1 end return 0 end
  return min(max((f-a)/d,0),1)
end
local function val(f)
  local M=Ctrl.Mode
  local a=Ctrl.Start
  local d=Ctrl.Dur
  if M<0.5 then return cv(st(f,a,d)) end
  if M<1.5 then return min(cv(st(f,a,d)),cv(st(comp.RenderEnd-comp.RenderStart-f,0,Ctrl.Back))) end
  if M<2.5 then return max(cv(st(f,a,d))-cv(st(f,a+d+Ctrl.Hold,Ctrl.Back)),0) end
  if M<3.5 then return 1-cv(st(f,a,d)) end
  if M<4.5 then
    local n=max(floor(Ctrl.Steps+0.5),1)
    local s=0
    for i=0,n-1 do s=s+cv(st(f,a+i*Ctrl.Every,d)) end
    return s/n
  end
  if f<a then return 0 end
  local ph=(f-a)%max(Ctrl.Every,1)
  return max(cv(st(ph,0,d))-cv(st(ph,d+Ctrl.Hold,Ctrl.Back)),0)
end
local function zoom(f) return max((Ctrl.From+(Ctrl.To-Ctrl.From)*val(f))/100,0.01) end
local function arrivo(f)
  local M=Ctrl.Mode
  local a=Ctrl.Start
  local d=Ctrl.Dur
  local e=max(Ctrl.Every,1)
  if M>3.5 and M<4.5 then
    local k=min(floor((f-a-d)/e),max(floor(Ctrl.Steps+0.5),1)-1)
    return a+max(k,0)*e+d
  end
  if M>4.5 then return a+max(floor((f-a)/e),0)*e+d end
  return a+d
end
"""


def zoom_controls(**d):
    g = {"Mode": 0, "From": 100, "To": 130, "Start": 0, "Dur": 8, "Curve": 0, "Bounce": 1.5,
         "Hold": 10, "Back": 8, "Steps": 3, "Every": 15, "Tilt": 0, "Shake": 0, "ZBlur": 0.6, **d}
    return {
        "Mode": combo("Andamento", ZOOM_MODES, g["Mode"]),
        "From": slider("Zoom normale (%)", g["From"], 50, 200, allowed=(1, 2000)),
        "To": slider("Zoom massimo (%)", g["To"], 100, 300, allowed=(1, 2000)),
        "Start": slider("Inizia dopo (frame)", g["Start"], 0, 60, integer=True, allowed=(0, 100000)),
        "Dur": slider("Durata zoom (frame, 0 = istantaneo)", g["Dur"], 0, 60, integer=True, allowed=(0, 10000)),
        "Curve": combo("Curva", CURVES, g["Curve"]),
        "Bounce": slider("Quantità rimbalzo (curva Con rimbalzo)", g["Bounce"], 0, 4),
        "Hold": slider("Tenuta prima del ritorno (frame)", g["Hold"], 0, 60, integer=True, allowed=(0, 10000)),
        "Back": slider("Durata ritorno (frame)", g["Back"], 1, 60, integer=True, allowed=(1, 10000)),
        "Steps": slider("Numero di scalini", g["Steps"], 1, 8, integer=True, allowed=(1, 50)),
        "Every": slider("Frame tra scalini / battiti", g["Every"], 2, 60, integer=True, allowed=(1, 10000)),
        "Tilt": slider("Inclinazione durante lo zoom (gradi)", g["Tilt"], -10, 10),
        "Shake": slider("Scossa all'arrivo", g["Shake"], 0, 2),
        "ZBlur": slider("Sfocatura di movimento", g["ZBlur"], 0, 2),
    }


def fx_zoom(name, **defaults):
    c = zoom_controls(**defaults)
    pre = ":" + ZOOM_LUA
    shake = (f"local e={T}-arrivo({T})\n"
             "if e<0 or Ctrl.Shake<=0 then return {zero} end\n"
             "local a=Ctrl.Shake*0.01*exp(-e/4)\n")
    tools = [
        Tool("Ctrl", "Transform", {
            "Size": own(pre + f"return zoom({T})"),
            "Angle": own(pre + f"return Ctrl.Tilt*val({T})"),
            "Edges": 3, **ctrl_values(c)}, controls=c),
        Tool("Scossa", "Transform", {
            "Input": Conn("Ctrl"), "Edges": 3,
            "Center": Expr(pre + shake.format(zero="Point(0.5,0.5)")
                           + "return Point(0.5+a*sin(e*2.9+1), 0.5+a*cos(e*3.7))"),
            "Angle": Expr(pre + shake.format(zero="0") + "return a*60*sin(e*2.1)"),
        }),
        Tool("Mosso", "DirectionalBlur", {
            "Input": Conn("Scossa"), "Type": 3,
            "Center": Expr("Point(Ctrl.Pivot.X+Ctrl.Center.X-0.5, Ctrl.Pivot.Y+Ctrl.Center.Y-0.5)"),
            "Length": Expr(pre + f"return min(Ctrl.ZBlur*abs(zoom({T})-zoom({T}-1))/zoom({T})*1.5,0.25)"),
        }),
    ]
    return Macro(name, tools, "Mosso",
                 [Exposed("Ctrl", "Pivot", "Punto di zoom (trascinalo sul soggetto)"),
                  Exposed("Ctrl", "Center", "Sposta inquadratura")] + [Exposed("Ctrl", k) for k in c],
                 [("Ctrl", "Input", "Input")])


# --------------------------------------------------------------------------- #
# EFFECTS
# --------------------------------------------------------------------------- #
def env_start(start="Ctrl.Start", dur="Ctrl.Dur"):
    """1 at the hit, falling to 0 over ``dur`` frames (0 before the hit)."""
    return (f":local f={T}-{start}\n"
            f"if f<0 then return 0 end\n"
            f"return (1-min(f/max({dur},1),1))^2")


def fx_scossa():
    c = {"Strength": slider("Intensità", 0.6, 0, 2), "Speed": slider("Velocità", 0.7, 0, 1),
         "Start": slider("Inizia dopo (frame)", 0, 0, 60, integer=True, allowed=(0, 100000)),
         "Dur": slider("Durata (frame, 0 = tutta la clip)", 12, 0, 120, integer=True, allowed=(0, 100000)),
         "Zoom": slider("Zoom anti-bordi (%)", 106, 100, 130, allowed=(100, 400))}
    strength = (f":local f={T}-Ctrl.Start\n"
                "if f<0 then return 0 end\n"
                "if Ctrl.Dur<1 then return 1 end\n"
                "return (1-min(f/Ctrl.Dur,1))^2")
    tools = [
        Tool("Tremolio", "CameraShake", {"XDeviation": Expr("0.02*Ctrl.Strength"),
                                         "YDeviation": Expr("0.02*Ctrl.Strength"),
                                         "RotationDeviation": Expr("0.4*Ctrl.Strength"),
                                         "Speed": Expr("Ctrl.Speed"), "Randomness": 0.9,
                                         "OverallStrength": Expr(strength), "Edges": 3}),
        Tool("Ctrl", "Transform", {"Input": Conn("Tremolio"), "Size": own("Ctrl.Zoom/100"), **ctrl_values(c)},
             controls=c),
    ]
    return Macro("LDF_Scossa", tools, "Ctrl", [Exposed("Ctrl", k) for k in c], [("Tremolio", "Input", "Input")])


def fx_flash():
    c = {"Start": slider("Inizia dopo (frame)", 0, 0, 60, integer=True, allowed=(0, 100000)),
         "Dur": slider("Durata lampo (frame)", 8, 1, 40, integer=True, allowed=(1, 1000)),
         "Amount": slider("Intensità lampo", 0.8, 0, 1),
         "Expo": slider("Sovraesposizione", 0.5, 0, 2)}
    env = env_start()
    tools = [
        Tool("Espo", "BrightnessContrast", {"Gain": Expr(env.replace("return (1-", "return 1+Ctrl.Expo*(1-"))}),
        solid("Luce", AVORIO),
        Tool("Ctrl", "Merge", {"Background": Conn("Espo"), "Foreground": Conn("Luce"), "PerformDepthMerge": 0,
                               "Blend": own(env.replace("return (1-", "return Ctrl.Amount*(1-")),
                               **ctrl_values(c)}, controls=c),
    ]
    return Macro("LDF_FlashColpo", tools, "Ctrl", [Exposed("Ctrl", k) for k in c] + [
        Exposed("Luce", "TopLeftRed", "Colore lampo", group=1), Exposed("Luce", "TopLeftGreen", group=1),
        Exposed("Luce", "TopLeftBlue", group=1)], [("Espo", "Input", "Input")])


def fx_fuoco():
    c = {"Blur": slider("Sfocatura iniziale", 25, 0, 100),
         "Start": slider("Inizia dopo (frame)", 0, 0, 60, integer=True, allowed=(0, 100000)),
         "Dur": slider("Durata messa a fuoco (frame)", 10, 1, 60, integer=True, allowed=(1, 10000)),
         "Zoom": slider("Assestamento zoom (%)", 6, 0, 20),
         "OutToo": checkbox("Sfoca anche alla fine della clip", 0),
         "OutDur": slider("Durata sfocatura finale (frame)", 10, 1, 60, integer=True, allowed=(1, 10000))}
    amt = (f":local a=1-{snap(clamp01(f'({T}-Ctrl.Start)/max(Ctrl.Dur,1)'))}\n"
           f"if Ctrl.OutToo>0.5 then a=max(a,1-{ease_out(clamp01(f'{R}/max(Ctrl.OutDur,1)'))}) end\n")
    tools = [
        Tool("Sfoca", "Blur", {"XBlurSize": Expr(amt + "return Ctrl.Blur*a")}),
        Tool("Ctrl", "Transform", {"Input": Conn("Sfoca"), "Edges": 3, "Size": own(amt + "return 1+Ctrl.Zoom/100*a"),
                                   **ctrl_values(c)}, controls=c),
    ]
    return Macro("LDF_FuocoRapido", tools, "Ctrl", [Exposed("Ctrl", k) for k in c]
                 + [Exposed("Ctrl", "Pivot", "Punto di zoom")], [("Sfoca", "Input", "Input")])


def fx_spotlight():
    c = {"W": slider("Larghezza zona", 0.12, 0.02, 0.6),
         "Shape": slider("Forma (1 = cerchio, 2 = ovale verticale)", 1.7, 0.3, 3),
         "Dark": slider("Scurisci il resto", 0.55, 0, 1),
         "Desat": slider("Togli colore al resto", 0.6, 0, 1),
         "Tint": slider("Tinta verde sul resto", 0.3, 0, 1),
         "Ring": slider("Spessore anello (pixel, 0 = nessuno)", 4, 0, 20),
         "Start": slider("Inizia dopo (frame)", 0, 0, 60, integer=True, allowed=(0, 100000)),
         "InDur": slider("Durata entrata (frame)", 10, 1, 60, integer=True, allowed=(1, 10000)),
         "OutDur": slider("Durata uscita (frame)", 8, 1, 60, integer=True, allowed=(1, 10000))}
    a = (f"min({snap(clamp01(f'({T}-Ctrl.Start)/max(Ctrl.InDur,1)'))},"
         f"{clamp01(f'{R}/max(Ctrl.OutDur,1)')})")
    sz = f"(1+1.5*(1-{snap(clamp01(f'({T}-Ctrl.Start)/max(Ctrl.InDur,1)'))}))"
    w = f"(Ctrl.W*{sz})"
    h = f"(Ctrl.W*Ctrl.Shape*{OW}/{OH}*{sz})"
    tools = [
        Tool("Ingresso", "Transform", {}),
        Tool("Scuro", "BrightnessContrast", {"Input": Conn("Ingresso"),
                                             "Gain": Expr(f"1-Ctrl.Dark*{a}"),
                                             "Saturation": Expr(f"1-Ctrl.Desat*{a}")}),
        solid("Verde", VERDE),
        Tool("Tinta", "Merge", {"Background": Conn("Scuro"), "Foreground": Conn("Verde"), "PerformDepthMerge": 0,
                                "Blend": Expr(f"Ctrl.Tint*0.35*{a}")}),
        Tool("Zona", "EllipseMask", {"Center": (0.5, 0.5), "Width": Expr(w), "Height": Expr(h), "SoftEdge": 0.02}),
        Tool("Ctrl", "Merge", {"Background": Conn("Tinta"), "Foreground": Conn("Ingresso"),
                               "EffectMask": Conn("Zona", "Mask"), "PerformDepthMerge": 0, **ctrl_values(c)},
             controls=c),
        Tool("AnelloEst", "EllipseMask", {"Center": Expr("Zona.Center"),
                                          "Width": Expr(f"{w}+2*Ctrl.Ring/{OW}"),
                                          "Height": Expr(f"{h}+2*Ctrl.Ring/{OH}")}),
        Tool("AnelloInt", "EllipseMask", {"EffectMask": Conn("AnelloEst", "Mask"), "PaintMode": FuID("Subtract"),
                                          "Center": Expr("Zona.Center"), "Width": Expr(w), "Height": Expr(h)}),
        solid("Anello", TERRA, {"EffectMask": Conn("AnelloInt", "Mask")}),
        Tool("Uscita", "Merge", {"Background": Conn("Ctrl"), "Foreground": Conn("Anello"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f"iif(Ctrl.Ring>0.01,1,0)*{a}")}),
    ]
    return Macro("LDF_EvidenziaGiocatore", tools, "Uscita",
                 [Exposed("Zona", "Center", "Posizione giocatore (animabile con i keyframe)"),
                  Exposed("Zona", "SoftEdge", "Morbidezza bordo", 0.02)] + [Exposed("Ctrl", k) for k in c]
                 + [Exposed("Anello", "TopLeftRed", "Colore anello", group=1),
                    Exposed("Anello", "TopLeftGreen", group=1), Exposed("Anello", "TopLeftBlue", group=1)],
                 [("Ingresso", "Input", "Input")])


def fx_look(key, blend):
    tools = [Tool("Ctrl", "FileLUT", {"LUTFile": f"Setting:{PREFIX}_{key}.cube", "Blend": blend})]
    return Macro(f"{PREFIX}_Look_{key}", tools, "Ctrl",
                 [Exposed("Ctrl", "Blend", "Intensità look", blend)], [("Ctrl", "Input", "Input")])


# --------------------------------------------------------------------------- #
# TRANSITIONS — fast
# --------------------------------------------------------------------------- #
P = "Ctrl.Mix"
IW = "ClipA.Input.OriginalWidth"
IH = "ClipA.Input.OriginalHeight"
MAINS = [("ClipA", "Input", "Clip in uscita"), ("ClipB", "Input", "Clip in entrata")]


def progress(controls):
    return [Tool("Ctrl", "Dissolve", {"Mix": Conn("CtrlCurve", "Value"), **ctrl_values(controls)},
                 controls=controls), *anim_curves("CtrlCurve")]


def quint_io(x):
    return f"(({x})<0.5 and 16*({x})^5 or 1-((-2*({x})+2)^5)/2)"


def cut(width):
    return Expr(clamp01(f"({P}-0.5+{width / 2})/{width}"))


def tr_zoom():
    c = {"Dir": combo("Direzione", ["Zoom in avanti", "Zoom all'indietro"], 0),
         "Zoom": slider("Intensità zoom", 1.2, 0.2, 4),
         "Blur": slider("Sfocatura", 0.6, 0, 1.5),
         "Spin": slider("Rotazione (gradi)", 0, -90, 90),
         "Flash": slider("Lampo avorio sul taglio", 0, 0, 1)}
    a = ease_in(clamp01(f"{P}*2"))
    b = f"(1-{ease_out(clamp01(f'{P}*2-1'))})"
    tools = [
        Tool("ClipA", "Transform", {"Edges": 3, "Angle": Expr(f"Ctrl.Spin*{a}"),
                                    "Size": Expr(f"iif(Ctrl.Dir<0.5, 1+Ctrl.Zoom*{a}, 1/(1+Ctrl.Zoom*{a}))")}),
        Tool("ClipB", "Transform", {"Edges": 3, "Angle": Expr(f"-Ctrl.Spin*{b}"), "Pivot": Expr("ClipA.Pivot"),
                                    "Size": Expr(f"iif(Ctrl.Dir<0.5, 1/(1+Ctrl.Zoom*{b}), 1+Ctrl.Zoom*{b})")}),
        Tool("Taglio", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"), "Mix": cut(0.06)}),
        Tool("ZoomBlur", "DirectionalBlur", {"Input": Conn("Taglio"), "Type": 3, "Center": Expr("ClipA.Pivot"),
                                             "Length": Expr(f"Ctrl.Blur*0.3*sin(pi*{P})^2")}),
        solid("Luce", AVORIO),
        Tool("Lampo", "Merge", {"Background": Conn("ZoomBlur"), "Foreground": Conn("Luce"), "PerformDepthMerge": 0,
                                "Blend": Expr(f"Ctrl.Flash*(1-abs(2*{P}-1))^4")}),
        *progress(c),
    ]
    return Macro("LDF_ZoomPassaggio", tools, "Lampo",
                 [Exposed("Ctrl", k) for k in c] + [Exposed("ClipA", "Pivot", "Punto di zoom")], MAINS)


def tr_frusta():
    c = {"Dir": combo("Direzione", ["Verso sinistra", "Verso destra", "Verso l'alto", "Verso il basso"], 0),
         "Blur": slider("Mosso", 1, 0, 2)}
    e = quint_io(P)
    d = ("local m=Ctrl.Dir\n"
         "local dx=0\nlocal dy=0\n"
         "if m<0.5 then dx=-1 elseif m<1.5 then dx=1 elseif m<2.5 then dy=1 else dy=-1 end\n"
         f"local e={e}\n")
    tools = [
        Tool("ClipA", "Transform", {"Edges": 0, "Center": Expr(f":{d}return Point(0.5+dx*e, 0.5+dy*e)")}),
        Tool("ClipB", "Transform", {"Edges": 0,
                                    "Center": Expr(f":{d}return Point(0.5-dx*(1-e), 0.5-dy*(1-e))")}),
        Tool("Unisci", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"), "PerformDepthMerge": 0}),
        Tool("Mosso", "DirectionalBlur", {"Input": Conn("Unisci"), "Type": 0,
                                          "Angle": Expr("iif(Ctrl.Dir<1.5, 0, 90)"),
                                          "Length": Expr(f"Ctrl.Blur*0.3*sin(pi*{P})^2")}),
        *progress(c),
    ]
    return Macro("LDF_Frusta", tools, "Mosso", [Exposed("Ctrl", k) for k in c], MAINS)


def tr_lampo():
    c = {"Peak": slider("Intensità lampo", 1, 0, 1),
         "Punch": slider("Scatto zoom sulla clip nuova", 0.08, 0, 0.4)}
    tools = [
        Tool("ClipA", "Transform", {}),
        Tool("ClipB", "Transform", {"Edges": 3,
                                    "Size": Expr(f"1+Ctrl.Punch*(1-{snap(clamp01(f'({P}-0.5)*2'))})")}),
        Tool("Taglio", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"), "Mix": cut(0.04)}),
        solid("Luce", AVORIO),
        Tool("Lampo", "Merge", {"Background": Conn("Taglio"), "Foreground": Conn("Luce"), "PerformDepthMerge": 0,
                                "Blend": Expr(f"Ctrl.Peak*(1-abs(2*{P}-1))^2")}),
        *progress(c),
    ]
    return Macro("LDF_LampoAvorio", tools, "Lampo", [Exposed("Ctrl", k) for k in c] + [
        Exposed("Luce", "TopLeftRed", "Colore lampo", group=1), Exposed("Luce", "TopLeftGreen", group=1),
        Exposed("Luce", "TopLeftBlue", group=1)], MAINS)


def tr_linea_veloce():
    c = {"Rev": checkbox("Inverti direzione", 0),
         "Thick": slider("Spessore linea (pixel)", 6, 0, 20),
         "Push": slider("Spinta", 0.06, 0, 0.3)}
    e = quint_io(P)
    s = "iif(Ctrl.Rev>0.5,-1,1)"
    x = f"iif(Ctrl.Rev>0.5, 1-{e}, {e})"
    tools = [
        Tool("ClipA", "Transform", {"Edges": 3, "Center": Expr(f"Point(0.5+{s}*Ctrl.Push*{e}, 0.5)")}),
        Tool("ClipB", "Transform", {"Edges": 3, "Size": Expr(f"1+Ctrl.Push*(1-{e})")}),
        Tool("Area", "RectangleMask", {"Center": Expr(f"Point(iif(Ctrl.Rev>0.5, 1-{e}/2, {e}/2), 0.5)"),
                                       "Width": Expr(e), "Height": 1.1}),
        Tool("Tendina", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                  "EffectMask": Conn("Area", "Mask"), "PerformDepthMerge": 0}),
        Tool("LineaMask", "RectangleMask", {"Center": Expr(f"Point({x}, 0.5)"),
                                            "Width": Expr(f"Ctrl.Thick/{IW}"), "Height": 1.1}),
        solid("Linea", TERRA, {"EffectMask": Conn("LineaMask", "Mask")}),
        Tool("Uscita", "Merge", {"Background": Conn("Tendina"), "Foreground": Conn("Linea"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f"iif({P}>0.001 and {P}<0.999,1,0)")}),
        *progress(c),
    ]
    return Macro("LDF_LineaVeloce", tools, "Uscita", [Exposed("Ctrl", k) for k in c], MAINS)


# --------------------------------------------------------------------------- #
# TITLES — Optima, fast entrances
# --------------------------------------------------------------------------- #
RB = {
    "Speed": slider("Durata animazioni (1 = normale, 0.5 = più scattante, 2 = più lenta)", 1, 0.3, 3,
                    allowed=(0.05, 20)),
    "OutDur": slider("Durata uscita (frame)", 8, 1, 60, integer=True, allowed=(1, 600)),
    "Shadow": checkbox("Ombra per leggibilità su video", 1),
}
GREEN_BG = {"GreenBg": checkbox("Sfondo verde pieno (per schermate titolo)", 0)}
OUT = clamp01(f"{R}/max(Ctrl.OutDur,1)")
SHADOW = {"Enabled3": Expr("Ctrl.Shadow"), "ElementShape3": 0, "Red3": 0, "Green3": 0, "Blue3": 0,
          "Alpha3": 0.55, "Offset3": (0.0, -0.004), "Softness3": 1, "SoftnessX3": 10, "SoftnessY3": 10,
          "PriorityBack3": 5, "PriorityBack1": 10}


def tx(name, value, style="Regular", size=0.04, rgb=AVORIO, pos=(0.5, 0.5), align=0, track=1.0,
       center_expr=None, extra=None):
    """Optima Text+. ``align``: -1 left edge at pos, 0 centred, 1 right edge at pos."""
    i = {**FRAME, "StyledText": value, "Font": FONT, "Style": style, "Size": size,
         "VerticalJustificationNew": 3, "HorizontalJustificationNew": 3,
         "Center": center_expr if center_expr is not None else pos,
         "Red1": rgb[0], "Green1": rgb[1], "Blue1": rgb[2], "ElementShape1": 0,
         "CharacterSpacing": track, **SHADOW}
    if align:
        i["HorizontalLeftCenterRight"] = align
    i.update(extra or {})
    return Tool(name, "TextPlus", i)


def layers(items, base="Canvas"):
    """Merge (source, blend or None, mask or None) layers over ``base``."""
    tools, prev = [], base
    for i, (src, blend, mask) in enumerate(items, 1):
        inputs = {"Background": Conn(prev), "Foreground": Conn(src), "PerformDepthMerge": 0}
        if blend is not None:
            inputs["Blend"] = blend
        if mask:
            inputs["EffectMask"] = Conn(mask, "Mask")
        tools.append(Tool(f"Livello{i}", "Merge", inputs))
        prev = f"Livello{i}"
    return tools, prev


def green_bg():
    return solid("SfondoVerde", VERDE), ("SfondoVerde", Expr("Ctrl.GreenBg"), None)


def title(name, tools, controls, exposed, last, center=(0.5, 0.5), size=None):
    inputs = {"Background": Conn("Canvas"), "Foreground": Conn(last), "Center": center,
              "PerformDepthMerge": 0, "Blend": own(OUT), **ctrl_values(controls)}
    if size is not None:
        inputs["Size"] = own(size)
    ctrl = Tool("Ctrl", "Merge", inputs, controls=controls)
    return Macro(name, [canvas(), *tools, ctrl], "Ctrl",
                 exposed + [Exposed("Ctrl", "Center", "Posizione")] + [Exposed("Ctrl", k) for k in controls])


def texp(tool, label, size=None):
    e = [Exposed(tool, "StyledText", label), Exposed(tool, "Style", f"Stile {label.lower()}")]
    if size is not None:
        e.append(Exposed(tool, "Size", f"Dimensione {label.lower()}", size))
    return e


def t_parola():
    c = {**RB, "Punch": slider("Scala di partenza (%)", 140, 100, 300, allowed=(1, 1000)),
         "Line": checkbox("Linea terracotta sotto", 1),
         "LineLen": slider("Lunghezza linea", 0.16, 0.02, 0.6)}
    a = st(0, 7)
    tools = [
        tx("Testo", "DECISIVO", "Bold", 0.11, track=1.02),
        Tool("Sfoca", "Blur", {"Input": Conn("Testo"), "XBlurSize": Expr(f"8*(1-{snap(a)})")}),
        *hline("Linea", 0.5, 0.435, "Ctrl.LineLen", 5, TERRA, snap(st(5, 8)), from_center=True),
    ]
    mt, last = layers([("Sfoca", Expr(snap(a)), None), ("Linea", Expr("Ctrl.Line"), None)])
    return title("LDF_ParolaChiave", tools + mt, c,
                 texp("Testo", "Parola", 0.11) + [Exposed("Testo", "Red1", "Colore parola", group=1),
                                                  Exposed("Testo", "Green1", group=1),
                                                  Exposed("Testo", "Blue1", group=1)],
                 last, size=f"Ctrl.Punch/100+(1-Ctrl.Punch/100)*{back(a, 0.8)}")


def t_didascalie():
    c = {"WordDur": slider("Frame per parola", 8, 2, 30, integer=True, allowed=(1, 600)),
         "OneWord": checkbox("Una parola alla volta (altrimenti la frase si compone)", 1),
         "Pop": slider("Scatto della parola", 1, 0, 1),
         "Box": checkbox("Riquadro terracotta dietro al testo", 1),
         "Shadow": checkbox("Ombra per leggibilità su video", 1)}
    words = (":local s=Sorgente.StyledText.Value or ''\n"
             "local w={}\n"
             "for x in string.gmatch(s,'%S+') do w[#w+1]=x end\n"
             f"local k=floor({T}/max(Ctrl.WordDur,1))+1\n"
             "if k>#w then k=#w end\n"
             "if k<1 then return Text('') end\n"
             "if Ctrl.OneWord>0.5 then return Text(w[k]) end\n"
             "return Text(table.concat(w,' ',1,k))")
    size = (f":local f=({T}%max(Ctrl.WordDur,1))\n"
            f"local a={clamp01('f/3')}\n"
            f"local s={back('a', 1.6)}\n"
            f"if Ctrl.OneWord<0.5 then s=1 end\n"
            f"return 1+(max(s,0)-1)*Ctrl.Pop")
    box = {"Enabled4": Expr("Ctrl.Box"), "ElementShape4": 2, "Level4": 0, "Red4": TERRA[0],
           "Green4": TERRA[1], "Blue4": TERRA[2], "Alpha4": 1, "ExtendHorizontal4": 0.18,
           "ExtendVertical4": 0.12, "Round4": 0.08, "PriorityBack4": 3}
    tools = [
        canvas(),
        tx("Sorgente", "Scrivi qui la frase che vuoi far apparire parola per parola", "Bold", 0.075),
        tx("Testo", "", "Bold", 0.075, extra={"StyledText": Expr(words), **box}),
        Tool("Ctrl", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("Testo"), "Center": (0.5, 0.25),
                               "PerformDepthMerge": 0, "Size": own(size), "Blend": Expr(clamp01(f"{R}/3")),
                               **ctrl_values(c)}, controls=c),
    ]
    return Macro("LDF_Didascalie", tools, "Ctrl", [
        Exposed("Sorgente", "StyledText", "Frase"), Exposed("Testo", "Style", "Stile"),
        Exposed("Testo", "Size", "Dimensione testo", 0.075),
        Exposed("Testo", "Red1", "Colore testo", group=1), Exposed("Testo", "Green1", group=1),
        Exposed("Testo", "Blue1", group=1),
        Exposed("Testo", "Red4", "Colore riquadro", group=4), Exposed("Testo", "Green4", group=4),
        Exposed("Testo", "Blue4", group=4),
        Exposed("Ctrl", "Center", "Posizione")] + [Exposed("Ctrl", k) for k in c])


def t_numero():
    c = {**RB,
         "From": slider("Da", 0, 0, 1000, allowed=(-1e9, 1e12)),
         "To": slider("A", 100000, 0, 200000, allowed=(-1e9, 1e12)),
         "CountDur": slider("Durata conteggio (frame)", 30, 1, 150, integer=True, allowed=(1, 5000)),
         "Sep": checkbox("Separatore migliaia (100.000)", 1),
         "Punch": slider("Colpo a fine conteggio", 0.08, 0, 0.3)}
    num = (f":local p={clamp01(f'{T}/max(Ctrl.CountDur,1)')}\n"
           f"local v=Ctrl.From+(Ctrl.To-Ctrl.From)*{snap('p')}\n"
           "local n=floor(v+0.5)\n"
           "local neg=n<0\n"
           "local s=string.format('%d',math.abs(n))\n"
           "if Ctrl.Sep>0.5 then\n"
           "  s=string.reverse(s)\n"
           "  s=string.gsub(s,'(%d%d%d)','%1.')\n"
           "  s=string.reverse(s)\n"
           "  if string.sub(s,1,1)=='.' then s=string.sub(s,2) end\n"
           "end\n"
           "if neg then s='-'..s end\n"
           "return Text((Prefisso.StyledText.Value or '')..s..(Suffisso.StyledText.Value or ''))")
    a = st(0, 8)
    size = (f":local d={T}-Ctrl.CountDur\n"
            f"local s=0.92+0.08*{snap(a)}\n"
            "if d>=0 and d<8 then s=s*(1+Ctrl.Punch*sin(pi*d/8)) end\n"
            "return s")
    tools = [
        tx("Prefisso", "", "Bold", 0.13), tx("Suffisso", "", "Bold", 0.13),
        tx("Numero", "0", "Bold", 0.13, pos=(0.5, 0.545), extra={"StyledText": Expr(num)}),
        *hline("Linea", 0.5, 0.455, 0.1, 4, TERRA, snap(st(4, 10)), from_center=True),
        tx("Etichetta", "SPETTATORI AL MARACANÀ", "Regular", 0.024, track=1.3,
           center_expr=Expr(f"Point(0.5, 0.405-(1-{snap(st(6, 10))})*0.015)")),
    ]
    mt, last = layers([("Numero", Expr(snap(a)), None), ("Linea", None, None),
                       ("Etichetta", Expr(snap(st(6, 10))), None)])
    return title("LDF_NumeroImpatto", tools + mt, c, [
        Exposed("Prefisso", "StyledText", "Prefisso (es. €)"), Exposed("Suffisso", "StyledText", "Suffisso (es. %)"),
        Exposed("Etichetta", "StyledText", "Etichetta"), Exposed("Numero", "Style", "Stile numero"),
        Exposed("Numero", "Size", "Dimensione numero", 0.13)], last, size=size)


def t_colpo():
    c = {**RB, **GREEN_BG, "Spread": slider("Lettere che si stringono", 0.8, 0, 2),
         "LineLen": slider("Lunghezza linea", 0.3, 0.02, 0.8)}
    a = st(0, 10)
    tools = [
        green_bg()[0],
        tx("Titolo", "LA NOTTE DI MARSIGLIA", "Bold", 0.085, pos=(0.5, 0.52),
           extra={"CharacterSpacing": Expr(f"1+Ctrl.Spread*(1-{snap(a)})")}),
        Tool("Sfoca", "Blur", {"Input": Conn("Titolo"), "XBlurSize": Expr(f"10*(1-{snap(a)})")}),
        *hline("Linea", 0.5, 0.44, "Ctrl.LineLen", 4, TERRA, snap(st(8, 8)), from_center=True),
        tx("Sotto", "CAPITOLO 03", "Regular", 0.022, track=1.35,
           center_expr=Expr(f"Point(0.5, 0.395-(1-{snap(st(12, 10))})*0.015)")),
    ]
    mt, last = layers([green_bg()[1], ("Sfoca", Expr(snap(a)), None), ("Linea", None, None),
                       ("Sotto", Expr(snap(st(12, 10))), None)])
    return title("LDF_TitoloColpo", tools + mt, c, texp("Titolo", "Titolo", 0.085) + texp("Sotto", "Sottotitolo", 0.022),
                 last, size=f"1.08-0.08*{snap(a)}")


def t_rivelato():
    c = {**RB, **GREEN_BG, "LineLen": slider("Lunghezza linea", 0.4, 0.05, 0.9)}
    up, down = snap(st(6, 10)), snap(st(10, 10))
    tools = [
        green_bg()[0],
        *hline("Linea", 0.5, 0.5, "Ctrl.LineLen", 4, TERRA, snap(st(0, 8)), from_center=True),
        tx("Titolo", "IL GOL CHE CAMBIÒ TUTTO", "Bold", 0.075,
           center_expr=Expr(f"Point(0.5, 0.548-(1-{up})*0.09)")),
        Tool("SopraMask", "RectangleMask", {"Center": (0.5, 0.75), "Width": 1.2, "Height": 0.498}),
        tx("Sotto", "MESSICO, 22 GIUGNO 1986", "Regular", 0.024, track=1.3,
           center_expr=Expr(f"Point(0.5, 0.458+(1-{down})*0.06)")),
        Tool("SottoMask", "RectangleMask", {"Center": (0.5, 0.25), "Width": 1.2, "Height": 0.498}),
    ]
    mt, last = layers([green_bg()[1], ("Linea", None, None), ("Titolo", None, "SopraMask"),
                       ("Sotto", None, "SottoMask")])
    return title("LDF_TestoRivelato", tools + mt, c,
                 texp("Titolo", "Titolo", 0.075) + texp("Sotto", "Sottotitolo", 0.024), last)


def t_citazione():
    c = {**RB, **GREEN_BG,
         "WriteDur": slider("Durata scrittura (frame)", 30, 1, 200, integer=True, allowed=(1, 5000))}
    x = 0.1
    write = clamp01(f"({T}-6*Ctrl.Speed)/max(Ctrl.WriteDur*Ctrl.Speed,1)")
    after = st("(6+Ctrl.WriteDur)", 10)
    tools = [
        green_bg()[0],
        tx("Virgolette", "“", "Bold", 0.2, TERRA, align=-1, center_expr=Expr(
            f"Point({x - 0.012}, 0.64+(1-{snap(st(0, 8))})*0.02)")),
        tx("Testo", "Quando entro in campo\nsono un uomo libero.", "Italic", 0.05, align=-1, pos=(x, 0.52),
           extra={"End": Expr(write), "LineSpacing": 1.1}),
        *hline("Linea", x, 0.385, 0.05, 4, TERRA, snap(after)),
        tx("Autore", "DIEGO ARMANDO MARADONA", "Regular", 0.018, align=-1, track=1.3,
           center_expr=Expr(f"Point({x}, 0.345-(1-{snap(after)})*0.012)")),
    ]
    mt, last = layers([green_bg()[1], ("Virgolette", Expr(snap(st(0, 8))), None), ("Testo", None, None),
                       ("Linea", None, None), ("Autore", Expr(snap(after)), None)])
    return title("LDF_Citazione", tools + mt, c,
                 texp("Testo", "Citazione", 0.05) + texp("Autore", "Autore", 0.018), last)


def t_tabellino():
    c = {**RB, "Panel": checkbox("Pannello verde", 1)}
    e = snap(st(0, 9))
    tools = [
        Tool("PannelloMask", "RectangleMask", {"Center": (0.5, 0.49), "Width": 0.64, "Height": 0.2}),
        solid("Pannello", VERDE, {"EffectMask": Conn("PannelloMask", "Mask"), "TopLeftAlpha": 0.92}),
        tx("SquadraA", "ARGENTINA", "Bold", 0.036, align=1, track=1.1,
           center_expr=Expr(f"Point(0.435-(1-{e})*0.04, 0.515)")),
        tx("Risultato", "2 – 1", "Bold", 0.062, pos=(0.5, 0.515)),
        Tool("Colpo", "Transform", {"Input": Conn("Risultato"), "Center": (0.5, 0.5),
                                    "Pivot": (0.5, 0.515), "Size": Expr(f"max({back(st(4, 8), 2)},0)")}),
        tx("SquadraB", "INGHILTERRA", "Bold", 0.036, align=-1, track=1.1,
           center_expr=Expr(f"Point(0.565+(1-{e})*0.04, 0.515)")),
        *hline("Linea", 0.5, 0.462, 0.34, 3, TERRA, snap(st(8, 10)), from_center=True),
        tx("Info", "MONDIALI 1986  ·  QUARTI DI FINALE", "Regular", 0.017, track=1.3,
           center_expr=Expr(f"Point(0.5, 0.43-(1-{snap(st(12, 10))})*0.012)")),
    ]
    mt, last = layers([("Pannello", Expr(f"Ctrl.Panel*{snap(st(0, 6))}"), None),
                       ("SquadraA", Expr(e), None), ("SquadraB", Expr(e), None), ("Colpo", None, None),
                       ("Linea", None, None), ("Info", Expr(snap(st(12, 10))), None)])
    return title("LDF_Tabellino", tools + mt, c, [
        Exposed("SquadraA", "StyledText", "Squadra casa"), Exposed("Risultato", "StyledText", "Risultato"),
        Exposed("SquadraB", "StyledText", "Squadra ospite"), Exposed("Info", "StyledText", "Info partita"),
        Exposed("Pannello", "TopLeftAlpha", "Opacità pannello", 0.92)], last)


def t_minuto():
    c = {**RB}
    e = snap(st(0, 8))
    tools = [
        tx("Minuto", "51'", "Bold", 0.05, TERRA, align=1,
           center_expr=Expr(f"Point(0.148-(1-{e})*0.03, 0.2)")),
        *vline("Divisore", 0.16, 0.168, 0.068, 2, AVORIO, snap(st(4, 8))),
        tx("Evento", "GOL", "Bold", 0.03, align=-1, track=1.15,
           center_expr=Expr(f"Point(0.172+(1-{snap(st(6, 8))})*0.02, 0.217)")),
        tx("Dettaglio", "DIEGO ARMANDO MARADONA", "Regular", 0.017, align=-1, track=1.3,
           center_expr=Expr(f"Point(0.172+(1-{snap(st(9, 8))})*0.02, 0.18)")),
    ]
    mt, last = layers([("Minuto", Expr(e), None), ("Divisore", Expr("0.6"), None),
                       ("Evento", Expr(snap(st(6, 8))), None), ("Dettaglio", Expr(snap(st(9, 8))), None)])
    return title("LDF_Minuto", tools + mt, c, [
        Exposed("Minuto", "StyledText", "Minuto"), Exposed("Evento", "StyledText", "Evento"),
        Exposed("Dettaglio", "StyledText", "Dettaglio"),
        Exposed("Minuto", "Red1", "Colore minuto", group=1), Exposed("Minuto", "Green1", group=1),
        Exposed("Minuto", "Blue1", group=1)], last)


# --------------------------------------------------------------------------- #
LOOKS = [("Tensione", "Look Tensione",
          "Contrasto deciso, colore trattenuto, ombre verso il verde: per i momenti di pressione")]

ZOOM_DESC = "Tutto regolabile: andamento, zoom %, durata, curva, punto di zoom, scossa, sfocatura"

CATALOG = [
    ("Effects", "LDF Zoom Social", lambda: fx_zoom("LDF_ZoomSocial"),
     "Zoom rapido che resta (base di tutti gli zoom). " + ZOOM_DESC),
    ("Effects", "LDF Zoom Punch-In", lambda: fx_zoom("LDF_ZoomPunchIn", To=118, Dur=2, ZBlur=0.3),
     "Stacco secco sul viso, stile jump cut (2 frame)"),
    ("Effects", "LDF Zoom Colpo", lambda: fx_zoom("LDF_ZoomColpo", Mode=2, To=140, Dur=5, Curve=4, Bounce=1.2,
                                                  Hold=12, Back=8, Shake=0.8, ZBlur=0.8),
     "Entra con rimbalzo e scossa, tiene, torna indietro"),
    ("Effects", "LDF Zoom Scalini", lambda: fx_zoom("LDF_ZoomScalini", Mode=4, To=145, Dur=3, Steps=3, Every=12,
                                                    Shake=0.3),
     "Tre scatti in avanti a tempo (tensione che sale)"),
    ("Effects", "LDF Zoom Battito", lambda: fx_zoom("LDF_ZoomBattito", Mode=5, To=106, Dur=2, Hold=0, Back=10,
                                                    Every=15, ZBlur=0.3),
     "Pulsa a ritmo (musica, battito, cori)"),
    ("Effects", "LDF Zoom Rivelazione", lambda: fx_zoom("LDF_ZoomRivelazione", Mode=3, To=160, Dur=12, ZBlur=0.8),
     "Parte stretto su un dettaglio e si apre sulla scena"),
    ("Effects", "LDF Scossa", fx_scossa, "Scossa di camera che si smorza (impatti, esplosioni di gioia)"),
    ("Effects", "LDF Flash Colpo", fx_flash, "Lampo avorio e sovraesposizione a inizio clip"),
    ("Effects", "LDF Fuoco Rapido", fx_fuoco, "Da sfocato a nitido in pochi frame, con assestamento"),
    ("Effects", "LDF Evidenzia Giocatore", fx_spotlight,
     "Isola un giocatore: resto scuro e desaturato, anello terracotta"),
    *[("Effects", f"LDF {label}", (lambda k=k: fx_look(k, 0.8)), desc) for k, label, desc in LOOKS],
    ("Transitions", "LDF Zoom Passaggio", tr_zoom, "Zoom veloce attraverso il taglio, avanti o indietro"),
    ("Transitions", "LDF Frusta", tr_frusta, "Panoramica a frusta nelle 4 direzioni con mosso"),
    ("Transitions", "LDF Lampo Avorio", tr_lampo, "Lampo avorio sul taglio con scatto sulla clip nuova"),
    ("Transitions", "LDF Linea Veloce", tr_linea_veloce, "La linea terracotta taglia lo schermo e rivela la scena"),
    ("Titles", "LDF Parola Chiave", t_parola, "Una parola grande che arriva di scatto, con linea"),
    ("Titles", "LDF Didascalie", t_didascalie, "Sottotitoli parola per parola stile social, riquadro terracotta"),
    ("Titles", "LDF Numero Impatto", t_numero, "Numero che corre fino al dato e batte il colpo"),
    ("Titles", "LDF Titolo Colpo", t_colpo, "Titolo che si stringe e si mette a fuoco di colpo"),
    ("Titles", "LDF Testo Rivelato", t_rivelato, "Il testo esce dalla linea (sopra e sotto)"),
    ("Titles", "LDF Citazione", t_citazione, "Citazione in corsivo con virgolette terracotta e autore"),
    ("Titles", "LDF Tabellino", t_tabellino, "Risultato della partita: squadre, punteggio, competizione"),
    ("Titles", "LDF Minuto", t_minuto, "Minuto ed evento della partita (51' GOL)"),
]


# --------------------------------------------------------------------------- #
# LUT
# --------------------------------------------------------------------------- #
def lut_tensione(c):
    import luts
    import numpy as np
    o = c
    c = luts.contrast(c, 1.22)
    c = luts.saturation(c, 0.78)
    c = luts.split_tone(c, (-0.02, 0.025, 0.005), (0.02, 0.012, -0.012))
    c = luts.skin_protect(o, c, 0.3)
    return np.clip(0.012 + c * 0.985, 0, 1)


LOOK_FUNCS = {"Tensione": lut_tensione}


# --------------------------------------------------------------------------- #
# SOUNDS — punchy but clean
# --------------------------------------------------------------------------- #
def _sounds():
    import numpy as np
    from sfx import (SR, bandpass, chirp_sine, env_ad, highpass, lowpass, noise, pan, place,
                     sweep_bandpass, t_axis, whoosh)

    def thump(dur=0.5, f0=120, f1=45, decay=9):
        t = t_axis(dur)
        return np.tanh(2 * chirp_sine(dur, f0, f1) * np.exp(-decay * t))

    def click(dur=0.015, lo=2500):
        return highpass(noise(dur), lo) * env_ad(int(dur * SR), 0.0003, 9)

    def punch_in():
        return place(0.5, [(0, thump(0.45, 140, 50, 11)), (0, click() * 0.5)])

    def zoom_colpo():
        up = sweep_bandpass(noise(0.22), 300, 3000, 3500, q=1.5, peak_at=0.95)
        up *= np.linspace(0, 1, len(up)) ** 2
        return place(1.0, [(0, up), (0.2, thump(0.8, 110, 38, 6)),
                           (0.2, click() * 0.7)])

    def battito():
        return thump(0.35, 90, 45, 12)

    def frusta():
        x = sweep_bandpass(noise(0.3), 600, 5000, 1500, q=2.0, peak_at=0.4)
        return pan(x * env_ad(len(x), 0.08, 5), np.linspace(-1, 1, len(x)))

    def lampo():
        t = t_axis(0.9)
        air = bandpass(noise(0.9), 3000, 12000) * np.exp(-6 * t)
        rev = sweep_bandpass(noise(0.3), 800, 8000, 8000, q=1.2, peak_at=0.98) * np.linspace(0, 1, int(0.3 * SR)) ** 3
        return place(1.2, [(0, rev * 0.8), (0.3, air), (0.3, thump(0.6, 100, 40, 8) * 0.6)])

    def riser_breve(dur=1.5):
        t = t_axis(dur)
        n = sweep_bandpass(noise(dur), 300, 7000, 8000, q=1.3, peak_at=0.98)
        tone = chirp_sine(dur, 90, 360) * 0.3
        y = (n + tone) * (t / dur) ** 2.5
        return pan(y, 0.3 * np.sin(2 * np.pi * 1.2 * t))

    def colpo_basso(dur=2.2):
        t = t_axis(dur)
        sub = chirp_sine(dur, 70, 30) * np.exp(-2.5 * t)
        body = lowpass(noise(dur), 500) * np.exp(-10 * t) * 1.5
        return np.tanh(1.6 * (sub + body)) + lowpass(noise(dur), 1500) * np.exp(-3 * t) * 0.05

    def conteggio(dur=1.0):
        parts, k = [], 0
        while k * 0.045 < dur - 0.05:
            f = 1400 + 600 * k * 0.045 / dur
            tick = np.sin(2 * np.pi * f * t_axis(0.025)) * env_ad(int(0.025 * SR), 0.0003, 14)
            parts.append((k * 0.045, tick * (0.5 + 0.5 * k * 0.045 / dur)))
            k += 1
        return place(dur, parts)

    def colpo_testo():
        return place(0.6, [(0, thump(0.5, 160, 60, 10)), (0, click(0.02, 1500) * 0.8)])

    return [
        ("Zoom", "punch_in", punch_in, "Con LDF Zoom Punch-In e gli stacchi sul viso"),
        ("Zoom", "zoom_colpo", zoom_colpo, "Con LDF Zoom Colpo (il colpo cade a 0,2 s)"),
        ("Zoom", "battito_zoom", battito, "Un colpo per ogni battito di LDF Zoom Battito / Scalini"),
        ("Transizioni", "frusta", frusta, "Con LDF Frusta"),
        ("Transizioni", "whoosh_rapido", lambda: whoosh(0.45, 300, 3500, 600, 0.4), "Con LDF Zoom Passaggio"),
        ("Transizioni", "lampo", lampo, "Con LDF Lampo Avorio e LDF Flash Colpo (colpo a 0,3 s)"),
        ("Tensione", "riser_breve", riser_breve, "1,5 s di salita prima di un colpo o di un titolo"),
        ("Tensione", "colpo_basso", colpo_basso, "Colpo profondo per Titolo Colpo, Tabellino, reveal"),
        ("Testo", "conteggio", conteggio, "Con LDF Numero Impatto (1 s)"),
        ("Testo", "colpo_testo", colpo_testo, "Con LDF Parola Chiave e LDF Minuto"),
    ]


SOUNDS = _sounds()
