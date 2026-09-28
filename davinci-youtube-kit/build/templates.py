"""Definitions of every Fusion template in the YouTube Kit.

Conventions
-----------
* Each template has a controller tool named ``Ctrl`` that owns the custom
  sliders (UserControls). Expressions read them as ``Ctrl.<Id>``; inside
  ``Ctrl`` itself they are referenced by their bare id. Write ``C.`` in the
  expression source and :func:`X` resolves it.
* Titles/effects/generators time their animations in frames using
  ``comp.RenderStart``/``comp.RenderEnd`` so intros and outros keep the same
  speed whatever the clip length.
* Transitions use the Anim Curves modifier (0..1 over the transition length),
  exactly as Blackmagic recommends, stored on ``Ctrl.Mix``.
"""

from __future__ import annotations

from fusion import (LEN, R, T, Conn, Expr, Exposed, FuID, Macro, Tool,
                    anim_curves, checkbox, clamp01, combo, slider)

# Width/height ratio of the frame, read from the controller Merge's background.
ASPECT_WH = "(Ctrl.Background.OriginalWidth/max(Ctrl.Background.OriginalHeight,1))"


def X(code: str, in_ctrl: bool = False) -> Expr:
    return Expr(code.replace("C.", "" if in_ctrl else "Ctrl."))


# Easing snippets (Lua). ``x`` must already be clamped to 0..1. ------------- #
def ease_out(x):
    return f"(1-(1-{x})^3)"


def ease_in(x):
    return f"(({x})^3)"


def ease_io(x):
    return f"(({x})<0.5 and 4*({x})^3 or 1-((-2*({x})+2)^3)/2)"


def back_out(x, k=1.70158):
    return f"(1+{k + 1}*(({x})-1)^3+{k}*(({x})-1)^2)"


IN = clamp01(f"{T}/max(C.InDur,1)")
OUT = clamp01(f"{R}/max(C.OutDur,1)")

# --------------------------------------------------------------------------- #
# Shared building blocks
# --------------------------------------------------------------------------- #
FRAME = {"Width": 1920, "Height": 1080, "UseFrameFormatSettings": 1}


def canvas(name="Canvas"):
    """Fully transparent frame-sized background."""
    return Tool(name, "Background", {
        **FRAME, "TopLeftRed": 0, "TopLeftGreen": 0, "TopLeftBlue": 0, "TopLeftAlpha": 0,
    })


def solid(name, rgb, extra=None):
    r, g, b = rgb
    return Tool(name, "Background", {
        **FRAME, "TopLeftRed": r, "TopLeftGreen": g, "TopLeftBlue": b, "TopLeftAlpha": 1,
        **(extra or {}),
    })


def text(name, value, font="Arial Black", style="Regular", size=0.08, rgb=(1, 1, 1),
         outline=None, shadow=True, box=None, center=(0.5, 0.5), extra=None):
    i = {
        **FRAME,
        "StyledText": value, "Font": font, "Style": style, "Size": size,
        "VerticalJustificationNew": 3, "HorizontalJustificationNew": 3,
        "Center": center,
        "Red1": rgb[0], "Green1": rgb[1], "Blue1": rgb[2],
        "ElementShape1": 0, "PriorityBack1": 10,
    }
    if outline:
        thick, orgb = outline
        i.update({"Enabled2": 1, "ElementShape2": 1, "OutsideOnly2": 1, "Thickness2": thick,
                  "Red2": orgb[0], "Green2": orgb[1], "Blue2": orgb[2], "PriorityBack2": 9})
    if shadow:
        i.update({"Enabled3": 1, "ElementShape3": 0, "Red3": 0, "Green3": 0, "Blue3": 0,
                  "Alpha3": 0.55, "Offset3": (0.012, -0.018), "Softness3": 1,
                  "SoftnessX3": 6, "SoftnessY3": 6, "PriorityBack3": 5})
    if box:
        brgb, ext_h, ext_v, rnd = box
        i.update({"Enabled4": 1, "ElementShape4": 2, "Level4": 0,
                  "Red4": brgb[0], "Green4": brgb[1], "Blue4": brgb[2], "Alpha4": 1,
                  "ExtendHorizontal4": ext_h, "ExtendVertical4": ext_v, "Round4": rnd,
                  "PriorityBack4": 3})
    i.update(extra or {})
    return Tool(name, "TextPlus", i)


def text_exposed(tool="Testo", label="Testo", color=True, size_default=None):
    e = [
        Exposed(tool, "StyledText", label),
        Exposed(tool, "Font", "Font"),
        Exposed(tool, "Style", "Stile"),
    ]
    if size_default is not None:
        e.append(Exposed(tool, "Size", "Dimensione testo", size_default))
    if color:
        e += [Exposed(tool, "Red1", "Colore testo", group=1),
              Exposed(tool, "Green1", group=1),
              Exposed(tool, "Blue1", group=1)]
    return e


def outline_exposed(tool="Testo"):
    return [Exposed(tool, "Thickness2", "Spessore contorno"),
            Exposed(tool, "Red2", "Colore contorno", group=2),
            Exposed(tool, "Green2", group=2),
            Exposed(tool, "Blue2", group=2)]


def ctrl_merge(fg, bg="Canvas", center=(0.5, 0.5), size=None, blend=None, angle=None,
               controls=None, extra=None):
    i = {"Background": Conn(bg), "Foreground": Conn(fg), "Center": center,
         "PerformDepthMerge": 0}
    if size is not None:
        i["Size"] = size
    if blend is not None:
        i["Blend"] = blend
    if angle is not None:
        i["Angle"] = angle
    i.update(extra or {})
    return Tool("Ctrl", "Merge", i, controls=controls or {})


IN_OUT = {
    "InDur": slider("Durata entrata (frame)", 10, 1, 60, integer=True, allowed=(0, 600)),
    "OutDur": slider("Durata uscita (frame)", 8, 1, 60, integer=True, allowed=(0, 600)),
}


def ctrl_values(controls):
    return {k: v["INP_Default"] for k, v in controls.items() if "INP_Default" in v}


def controls_exposed(controls):
    return [Exposed("Ctrl", k) for k in controls]


# --------------------------------------------------------------------------- #
# TITLES
# --------------------------------------------------------------------------- #
def t_typewriter():
    c = {
        "TypeDur": slider("Durata scrittura (frame)", 45, 5, 240, integer=True, allowed=(1, 3000)),
        "EraseOut": checkbox("Cancella lettera per lettera alla fine", 0),
        "OutDur": slider("Durata uscita (frame)", 12, 1, 60, integer=True, allowed=(1, 600)),
    }
    write = (f":local a={clamp01(f'{T}/max(Ctrl.TypeDur,1)')}\n"
             f"local b=1\n"
             f"if Ctrl.EraseOut>0.5 then b={clamp01(f'{R}/max(Ctrl.OutDur,1)')} end\n"
             f"return min(a,b)")
    tools = [
        canvas(),
        text("Testo", "Scrivi qui il tuo testo", font="Courier New", style="Bold", size=0.06,
             extra={"End": Expr(write)}),
        ctrl_merge("Testo", center=(0.5, 0.5),
                   blend=X(f"iif(C.EraseOut>0.5, 1, {OUT})", True),
                   controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_MacchinaDaScrivere", tools, "Ctrl",
                 text_exposed(size_default=0.06) + [Exposed("Ctrl", "Center", "Posizione")]
                 + controls_exposed(c))


def t_pop():
    c = {**IN_OUT, "Overshoot": slider("Rimbalzo", 1.7, 0, 4)}
    size = X(f":local a={IN}\nlocal b={OUT}\n"
             f"local s=1+(C.Overshoot+1)*(a-1)^3+C.Overshoot*(a-1)^2\n"
             f"return max(s,0)*{ease_out('b')}", True)
    tools = [
        canvas(),
        text("Testo", "TESTO POP!", size=0.09, outline=(0.08, (0, 0, 0))),
        ctrl_merge("Testo", center=(0.5, 0.5), size=size, controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_TestoPop", tools, "Ctrl",
                 text_exposed(size_default=0.09) + outline_exposed()
                 + [Exposed("Ctrl", "Center", "Posizione")] + controls_exposed(c))


def t_words():
    c = {
        "WordDur": slider("Frame per parola", 8, 2, 30, integer=True, allowed=(1, 600)),
        "OneWord": checkbox("Mostra solo la parola corrente (stile Shorts)", 1),
        "Pop": slider("Rimbalzo parola", 1, 0, 1),
    }
    words = (":local s=Sorgente.StyledText.Value or ''\n"
             "local w={}\n"
             "for x in string.gmatch(s,'%S+') do w[#w+1]=x end\n"
             f"local k=floor({T}/max(Ctrl.WordDur,1))+1\n"
             "if k>#w then k=#w end\n"
             "if k<1 then return Text('') end\n"
             "if Ctrl.OneWord>0.5 then return Text(w[k]) end\n"
             "return Text(table.concat(w,' ',1,k))")
    size = X(f":local f=({T}%max(C.WordDur,1))\n"
             f"local a={clamp01('f/3')}\n"
             f"local s={back_out('a', 2.2)}\n"
             f"if C.OneWord<0.5 then s=1 end\n"
             f"return 1+(max(s,0)-1)*C.Pop", True)
    tools = [
        canvas(),
        text("Sorgente", "Scrivi qui la frase che vuoi far apparire parola per parola",
             size=0.09, outline=(0.08, (0, 0, 0))),
        text("Testo", "", size=0.09, outline=(0.08, (0, 0, 0)), rgb=(1, 0.86, 0.1),
             extra={"StyledText": Expr(words)}),
        ctrl_merge("Testo", center=(0.5, 0.3), size=size,
                   blend=Expr(clamp01(f"{R}/3")), controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_ParolaPerParola", tools, "Ctrl",
                 [Exposed("Sorgente", "StyledText", "Frase")] + text_exposed(size_default=0.09)[1:]
                 + outline_exposed()
                 + [Exposed("Ctrl", "Center", "Posizione")] + controls_exposed(c))


def t_box():
    c = {**IN_OUT}
    size = X(f":local a={IN}\nlocal b={OUT}\n"
             f"return max({back_out('a')},0)*{ease_out('b')}", True)
    tools = [
        canvas(),
        text("Testo", "PAROLA CHIAVE", size=0.07, rgb=(0.05, 0.05, 0.05), shadow=False,
             box=((1, 0.85, 0.05), 0.25, 0.2, 0.25)),
        ctrl_merge("Testo", center=(0.5, 0.5), size=size, controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_BoxEvidenziato", tools, "Ctrl",
                 text_exposed(size_default=0.07)
                 + [Exposed("Testo", "Red4", "Colore box", group=4),
                    Exposed("Testo", "Green4", group=4), Exposed("Testo", "Blue4", group=4),
                    Exposed("Testo", "ExtendHorizontal4", "Margine orizzontale box"),
                    Exposed("Testo", "ExtendVertical4", "Margine verticale box"),
                    Exposed("Testo", "Round4", "Arrotondamento box"),
                    Exposed("Ctrl", "Center", "Posizione")] + controls_exposed(c))


def t_lower_third():
    c = {"InDur": slider("Durata entrata (frame)", 14, 1, 60, integer=True, allowed=(0, 600)),
         "OutDur": slider("Durata uscita (frame)", 12, 1, 60, integer=True, allowed=(0, 600))}

    def slide(y, delay):
        a = clamp01(f"({T}-{delay})/max(Ctrl.InDur,1)")
        b = clamp01(f"({R}-{delay})/max(Ctrl.OutDur,1)")
        return Expr(f":local a={a}\nlocal b={b}\nlocal e=min({ease_out('a')},{ease_out('b')})\n"
                    f"return Point(0.5-(1-e)*0.8, {y})")

    tools = [
        canvas(),
        text("Nome", "Mario Rossi", font="Arial", style="Bold", size=0.055,
             rgb=(0.05, 0.05, 0.05), shadow=False, box=((1, 0.8, 0.05), 0.3, 0.25, 0.1),
             extra={"Center": slide(0.535, 0)}),
        text("Ruolo", "Fondatore @ Il Mio Canale", font="Arial", style="Regular", size=0.035,
             shadow=False, box=((0.08, 0.08, 0.1), 0.35, 0.3, 0.1),
             extra={"Center": slide(0.455, 4)}),
        Tool("Blocco", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("Nome"),
                                 "PerformDepthMerge": 0}),
        Tool("Blocco2", "Merge", {"Background": Conn("Blocco"), "Foreground": Conn("Ruolo"),
                                  "PerformDepthMerge": 0}),
        ctrl_merge("Blocco2", center=(0.27, 0.16), controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_LowerThird", tools, "Ctrl", [
        Exposed("Nome", "StyledText", "Nome"),
        Exposed("Ruolo", "StyledText", "Ruolo / descrizione"),
        Exposed("Nome", "Font", "Font"), Exposed("Nome", "Style", "Stile"),
        Exposed("Nome", "Red4", "Colore accento", group=1),
        Exposed("Nome", "Green4", group=1), Exposed("Nome", "Blue4", group=1),
        Exposed("Nome", "Size", "Dimensione nome", 0.055),
        Exposed("Ruolo", "Size", "Dimensione ruolo", 0.035),
        Exposed("Ctrl", "Center", "Posizione"),
    ] + controls_exposed(c))


def t_subscribe():
    c = {
        **IN_OUT,
        "ClickAt": slider("Click dopo (frame)", 40, 0, 150, integer=True, allowed=(0, 3000)),
        "Testo1": {"LINKS_Name": "Testo prima del click", "LINKID_DataType": "Text",
                   "INPID_InputControl": "TextEditControl", "TEC_Lines": 1,
                   "ICS_ControlPage": "Controls"},
        "Testo2": {"LINKS_Name": "Testo dopo il click", "LINKID_DataType": "Text",
                   "INPID_InputControl": "TextEditControl", "TEC_Lines": 1,
                   "ICS_ControlPage": "Controls"},
    }
    clicked = f"({T}>=Ctrl.ClickAt)"
    size = X(f":local a={IN}\nlocal b={OUT}\n"
             f"local s=max({back_out('a')},0)*{ease_out('b')}\n"
             f"local d={T}-C.ClickAt\n"
             f"if d>=0 and d<6 then s=s*(1-0.12*sin(pi*d/6)) end\n"
             f"return s", True)
    tools = [
        canvas(),
        Tool("BtnMask", "RectangleMask", {"Center": (0.5, 0.5), "Width": 0.2, "Height": 0.1,
                                          "CornerRadius": 0.35, "SoftEdge": 0.0005}),
        solid("Bottone", (0.9, 0.05, 0.05), {
            "EffectMask": Conn("BtnMask", "Mask"),
            "TopLeftRed": Expr(f"iif({clicked}, 0.35, Ctrl.Red)"),
            "TopLeftGreen": Expr(f"iif({clicked}, 0.35, Ctrl.Green)"),
            "TopLeftBlue": Expr(f"iif({clicked}, 0.35, Ctrl.Blue)"),
        }),
        text("Etichetta", "ISCRIVITI", font="Arial", style="Bold", size=0.05, shadow=False,
             extra={"StyledText": Expr(f":if {clicked} then return Ctrl.Testo2 end\nreturn Ctrl.Testo1")}),
        Tool("Pulsante", "Merge", {"Background": Conn("Bottone"), "Foreground": Conn("Etichetta"),
                                   "PerformDepthMerge": 0}),
        ctrl_merge("Pulsante", center=(0.5, 0.18), size=size, controls={
            **c,
            "Red": {"LINKS_Name": "Colore pulsante", "LINKID_DataType": "Number",
                    "INPID_InputControl": "ColorControl", "INP_Default": 0.9,
                    "IC_ControlGroup": 1, "IC_ControlID": 0, "ICS_ControlPage": "Controls"},
            "Green": {"LINKID_DataType": "Number", "INPID_InputControl": "ColorControl",
                      "INP_Default": 0.05, "IC_ControlGroup": 1, "IC_ControlID": 1,
                      "ICS_ControlPage": "Controls"},
            "Blue": {"LINKID_DataType": "Number", "INPID_InputControl": "ColorControl",
                     "INP_Default": 0.05, "IC_ControlGroup": 1, "IC_ControlID": 2,
                     "ICS_ControlPage": "Controls"},
        }, extra={**ctrl_values(c), "Testo1": "ISCRIVITI", "Testo2": "ISCRITTO",
                  "Red": 0.9, "Green": 0.05, "Blue": 0.05}),
    ]
    return Macro("YTK_Iscriviti", tools, "Ctrl", [
        Exposed("Ctrl", "Testo1"), Exposed("Ctrl", "Testo2"),
        Exposed("Ctrl", "Red", group=1), Exposed("Ctrl", "Green", group=1),
        Exposed("Ctrl", "Blue", group=1),
        Exposed("Etichetta", "Font", "Font"), Exposed("Etichetta", "Style", "Stile"),
        Exposed("Ctrl", "Center", "Posizione"),
        Exposed("Ctrl", "InDur"), Exposed("Ctrl", "OutDur"), Exposed("Ctrl", "ClickAt"),
    ])


def t_cinematic():
    c = {"InDur": slider("Durata entrata (frame)", 24, 1, 90, integer=True, allowed=(0, 600)),
         "OutDur": slider("Durata uscita (frame)", 20, 1, 90, integer=True, allowed=(0, 600)),
         "Spread": slider("Allargamento lettere", 0.35, 0, 1.5)}
    tools = [
        canvas(),
        text("Testo", "IL TITOLO DEL TUO VIDEO", font="Arial", style="Regular", size=0.065,
             extra={"CharacterSpacing": Expr(f"1+Ctrl.Spread*({T}/{LEN})")}),
        Tool("SfocaIn", "Blur", {"Input": Conn("Testo"),
                                 "XBlurSize": X(f"12*((1-{ease_out(IN)})+(1-{ease_out(OUT)}))")}),
        ctrl_merge("SfocaIn", center=(0.5, 0.5),
                   blend=X(f"min({ease_out(IN)},{ease_out(OUT)})", True),
                   controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_TitoloCinematico", tools, "Ctrl",
                 text_exposed(size_default=0.065) + [Exposed("Ctrl", "Center", "Posizione")]
                 + controls_exposed(c))


def t_glitch():
    c = {**IN_OUT,
         "Amount": slider("Intensità glitch", 1, 0, 3),
         "Random": slider("Glitch casuali durante il testo", 0.08, 0, 0.5)}
    c["InDur"] = slider("Durata glitch in entrata (frame)", 12, 1, 60, integer=True, allowed=(0, 600))
    c["OutDur"] = slider("Durata glitch in uscita (frame)", 10, 1, 60, integer=True, allowed=(0, 600))
    g = (f"local g=max(1-{T}/max(Ctrl.InDur,1),1-{R}/max(Ctrl.OutDur,1),0)\n"
         f"randomseed(floor(time)*13+7)\n"
         f"if random()<Ctrl.Random then g=max(g,0.6) end\n")
    off = lambda seed, sign: Expr(  # noqa: E731
        f":{g}randomseed(floor(time)*31+{seed})\n"
        f"return Point(0.5{sign}g*Ctrl.Amount*(0.004+0.02*random()), 0.5+g*Ctrl.Amount*0.006*(random()-0.5))")
    tools = [
        canvas(),
        text("Testo", "GLITCH", size=0.12, outline=None),
        Tool("SoloR", "ColorGain", {"Input": Conn("Testo"), "LockRGB": 0, "GainGreen": 0, "GainBlue": 0}),
        Tool("SoloG", "ColorGain", {"Input": Conn("Testo"), "LockRGB": 0, "GainRed": 0, "GainBlue": 0}),
        Tool("SoloB", "ColorGain", {"Input": Conn("Testo"), "LockRGB": 0, "GainRed": 0, "GainGreen": 0}),
        Tool("SpostaR", "Transform", {"Input": Conn("SoloR"), "Center": off(3, "+")}),
        Tool("SpostaB", "Transform", {"Input": Conn("SoloB"), "Center": off(5, "-")}),
        Tool("UnisciR", "Merge", {"Background": Conn("SoloG"), "Foreground": Conn("SpostaR"),
                                  "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        Tool("UnisciB", "Merge", {"Background": Conn("UnisciR"), "Foreground": Conn("SpostaB"),
                                  "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        ctrl_merge("UnisciB", center=(0.5, 0.5),
                   blend=Expr(f":{g}randomseed(floor(time)*17+1)\n"
                              f"if g>0.5 and random()<0.35 then return 0 end\n"
                              f"return min({clamp01(f'{T}/2')},{clamp01(f'{R}/2')})"),
                   controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_TitoloGlitch", tools, "Ctrl",
                 text_exposed(size_default=0.12) + [Exposed("Ctrl", "Center", "Posizione")]
                 + controls_exposed(c))


def t_counter():
    c = {
        "From": slider("Da", 0, 0, 1000, allowed=(-1e9, 1e12)),
        "To": slider("A", 1000, 0, 100000, allowed=(-1e9, 1e12)),
        "CountDur": slider("Durata conteggio (frame)", 60, 5, 300, integer=True, allowed=(1, 5000)),
        "Sep": checkbox("Separatore migliaia (1.000)", 1),
    }
    num = (f":local p={clamp01(f'{T}/max(Ctrl.CountDur,1)')}\n"
           f"local v=Ctrl.From+(Ctrl.To-Ctrl.From)*{ease_out('p')}\n"
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
    tools = [
        canvas(),
        text("Prefisso", "", size=0.1),
        text("Suffisso", " iscritti", size=0.1),
        text("Testo", "0", size=0.1, outline=(0.06, (0, 0, 0)),
             extra={"StyledText": Expr(num)}),
        ctrl_merge("Testo", center=(0.5, 0.5),
                   size=X(f"max({back_out(IN)},0)*{ease_out(OUT)}", True),
                   controls={**c, **IN_OUT}, extra={**ctrl_values(c), **ctrl_values(IN_OUT)}),
    ]
    return Macro("YTK_Contatore", tools, "Ctrl", [
        Exposed("Ctrl", "From"), Exposed("Ctrl", "To"), Exposed("Ctrl", "CountDur"),
        Exposed("Ctrl", "Sep"),
        Exposed("Prefisso", "StyledText", "Prefisso (es. €)"),
        Exposed("Suffisso", "StyledText", "Suffisso (es. iscritti)"),
    ] + text_exposed(size_default=0.1)[1:] + [
        Exposed("Ctrl", "Center", "Posizione"), Exposed("Ctrl", "InDur"), Exposed("Ctrl", "OutDur"),
    ])


def t_circle():
    c = {**IN_OUT, "Pulse": slider("Pulsazione", 0.04, 0, 0.2)}
    tools = [
        canvas(),
        Tool("Anello", "EllipseMask", {"Center": (0.5, 0.5), "Width": 0.22,
                                       "Height": Expr(f"Width*{ASPECT_WH}"),
                                       "Solid": 0, "BorderWidth": 0.008, "SoftEdge": 0.0008}),
        solid("Colore", (1, 0.1, 0.1), {"EffectMask": Conn("Anello", "Mask")}),
        ctrl_merge("Colore", center=(0.5, 0.5),
                   size=X(f"max({back_out(IN, 2.5)},0)*{ease_out(OUT)}*(1+C.Pulse*sin({T}*0.25))", True),
                   controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_CerchioEvidenzia", tools, "Ctrl", [
        Exposed("Ctrl", "Center", "Posizione"),
        Exposed("Anello", "Width", "Dimensione", 0.22),
        Exposed("Anello", "BorderWidth", "Spessore"),
        Exposed("Colore", "TopLeftRed", "Colore", group=1),
        Exposed("Colore", "TopLeftGreen", group=1), Exposed("Colore", "TopLeftBlue", group=1),
    ] + controls_exposed(c))


def t_arrow():
    c = {**IN_OUT, "Bounce": slider("Oscillazione", 0.02, 0, 0.1),
         "Scale": slider("Dimensione", 1, 0.2, 3)}
    # Arrow pointing right, drawn with three rectangle masks (shaft + two arms).
    # Mask sizes are relative to frame width (X) and height (Y) respectively.
    thick = 0.035
    tools = [
        canvas(),
        Tool("Asta", "RectangleMask", {"Center": (0.4773, 0.5), "Width": 0.135, "Height": thick}),
        Tool("PuntaSu", "RectangleMask", {"EffectMask": Conn("Asta", "Mask"), "Center": (0.5323, 0.5315),
                                          "Width": 0.07, "Height": thick, "Angle": -45}),
        Tool("PuntaGiu", "RectangleMask", {"EffectMask": Conn("PuntaSu", "Mask"), "Center": (0.5323, 0.4685),
                                           "Width": 0.07, "Height": thick, "Angle": 45}),
        solid("Colore", (1, 0.85, 0.05), {"EffectMask": Conn("PuntaGiu", "Mask")}),
        Tool("Oscilla", "Transform", {"Input": Conn("Colore"),
                                      "Center": Expr(f"Point(0.5-Ctrl.Bounce*(0.5+0.5*sin({T}*0.35)), 0.5)")}),
        ctrl_merge("Oscilla", center=(0.4, 0.5), angle=0,
                   size=X(f"C.Scale*max({back_out(IN)},0)*{ease_out(OUT)}", True),
                   controls=c, extra=ctrl_values(c)),
    ]
    return Macro("YTK_Freccia", tools, "Ctrl", [
        Exposed("Ctrl", "Center", "Posizione"), Exposed("Ctrl", "Angle", "Rotazione"),
        Exposed("Colore", "TopLeftRed", "Colore", group=1), Exposed("Colore", "TopLeftGreen", group=1),
        Exposed("Colore", "TopLeftBlue", group=1),
    ] + controls_exposed(c))


# --------------------------------------------------------------------------- #
# TRANSITIONS  (MainInput1 = outgoing clip, MainInput2 = incoming clip)
# --------------------------------------------------------------------------- #
P = "Ctrl.Mix"  # 0..1 progress from Anim Curves


def progress(controls):
    return [Tool("Ctrl", "Dissolve", {"Mix": Conn("CtrlCurve", "Value"), **ctrl_values(controls)},
                 controls=controls), *anim_curves("CtrlCurve")]


def cut_mix(width=0.08):
    return Expr(clamp01(f"({P}-0.5+{width / 2})/{width}"))


def tr_zoom(zoom_in=True):
    c = {"Zoom": slider("Intensità zoom", 1.5, 0.2, 4), "Blur": slider("Sfocatura zoom", 0.25, 0, 1)}
    if zoom_in:
        a = f"1+Ctrl.Zoom*{ease_in(clamp01(f'{P}*2'))}"
        b = f"1/(1+Ctrl.Zoom*(1-{ease_out(clamp01(f'{P}*2-1'))}))"
        name = "YTK_ZoomIn"
    else:
        a = f"1/(1+Ctrl.Zoom*{ease_in(clamp01(f'{P}*2'))})"
        b = f"1+Ctrl.Zoom*(1-{ease_out(clamp01(f'{P}*2-1'))})"
        name = "YTK_ZoomOut"
    tools = [
        Tool("ClipA", "Transform", {"Size": Expr(a), "Edges": 3}),
        Tool("ClipB", "Transform", {"Size": Expr(b), "Edges": 3}),
        Tool("Taglio", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                    "Mix": cut_mix()}),
        Tool("ZoomBlur", "DirectionalBlur", {"Input": Conn("Taglio"), "Type": 3, "Center": (0.5, 0.5),
                                             "Length": Expr(f"Ctrl.Blur*0.6*sin(pi*{P})^2")}),
        *progress(c),
    ]
    return Macro(name, tools, "ZoomBlur", controls_exposed(c),
                 [("ClipA", "Input", "Clip in uscita"), ("ClipB", "Input", "Clip in entrata")])


def tr_whip(direction):
    c = {"Blur": slider("Mosso (motion blur)", 1, 0, 2)}
    dx, dy, ang = {"sinistra": (-1, 0, 0), "destra": (1, 0, 0), "su": (0, 1, 90), "giu": (0, -1, 90)}[direction]
    e = ease_io(P)
    ca = f"Point(0.5+({dx})*{e}, 0.5+({dy})*{e})"
    cb = f"Point(0.5-({dx})*(1-{e}), 0.5-({dy})*(1-{e}))"
    tools = [
        Tool("ClipA", "Transform", {"Center": Expr(ca), "Edges": 0}),
        Tool("ClipB", "Transform", {"Center": Expr(cb), "Edges": 0}),
        Tool("Unisci", "Merge", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                 "PerformDepthMerge": 0}),
        Tool("Mosso", "DirectionalBlur", {"Input": Conn("Unisci"), "Type": 0, "Angle": ang,
                                          "Length": Expr(f"Ctrl.Blur*0.25*sin(pi*{P})^2")}),
        *progress(c),
    ]
    return Macro(f"YTK_Whip_{direction.capitalize()}", tools, "Mosso", controls_exposed(c),
                 [("ClipA", "Input", "Clip in uscita"), ("ClipB", "Input", "Clip in entrata")])


def tr_flash():
    c = {"Peak": slider("Intensità flash", 1, 0, 1)}
    tools = [
        Tool("Taglio", "Dissolve", {"Mix": cut_mix(0.04)}),
        solid("Bianco", (1, 1, 1)),
        Tool("Flash", "Merge", {"Background": Conn("Taglio"), "Foreground": Conn("Bianco"),
                                "PerformDepthMerge": 0,
                                "Blend": Expr(f"Ctrl.Peak*(1-abs(2*{P}-1))^1.5")}),
        *progress(c),
    ]
    return Macro("YTK_FlashBianco", tools, "Flash",
                 controls_exposed(c) + [Exposed("Bianco", "TopLeftRed", "Colore flash", group=1),
                                        Exposed("Bianco", "TopLeftGreen", group=1),
                                        Exposed("Bianco", "TopLeftBlue", group=1)],
                 [("Taglio", "Background", "Clip in uscita"), ("Taglio", "Foreground", "Clip in entrata")])


def tr_blur():
    c = {"Blur": slider("Sfocatura massima", 40, 0, 150)}
    tools = [
        Tool("SfocaA", "Blur", {"XBlurSize": Expr(f"Ctrl.Blur*{ease_in(clamp01(f'{P}*1.6'))}")}),
        Tool("SfocaB", "Blur", {"XBlurSize": Expr(f"Ctrl.Blur*{ease_out(clamp01(f'1.6-{P}*1.6'))}")}),
        Tool("Dissolvenza", "Dissolve", {"Background": Conn("SfocaA"), "Foreground": Conn("SfocaB"),
                                         "Mix": Expr(ease_io(P))}),
        *progress(c),
    ]
    return Macro("YTK_DissolvenzaSfocata", tools, "Dissolvenza", controls_exposed(c),
                 [("SfocaA", "Input", "Clip in uscita"), ("SfocaB", "Input", "Clip in entrata")])


def tr_glitch():
    c = {"Amount": slider("Intensità glitch", 1, 0, 3)}
    g = f"local g=sin(pi*{P})^0.7*Ctrl.Amount\n"
    mix = Expr(f":local p={P}\nif p<0.35 then return 0 end\nif p>0.65 then return 1 end\n"
               f"randomseed(floor(time)*7+3)\nreturn iif(random()>0.5,1,0)")

    def off(seed, sign):
        return Expr(f":{g}randomseed(floor(time)*29+{seed})\n"
                    f"return Point(0.5{sign}g*(0.006+0.03*random()), 0.5)")

    jitter = Expr(f":{g}randomseed(floor(time)*11+5)\n"
                  f"if random()<0.5 then return Point(0.5,0.5) end\n"
                  f"return Point(0.5+g*0.08*(random()-0.5), 0.5+g*0.02*(random()-0.5))")
    tools = [
        Tool("Taglio", "Dissolve", {"Mix": mix}),
        Tool("SoloR", "ColorGain", {"Input": Conn("Taglio"), "LockRGB": 0, "GainGreen": 0, "GainBlue": 0}),
        Tool("SoloG", "ColorGain", {"Input": Conn("Taglio"), "LockRGB": 0, "GainRed": 0, "GainBlue": 0}),
        Tool("SoloB", "ColorGain", {"Input": Conn("Taglio"), "LockRGB": 0, "GainRed": 0, "GainGreen": 0}),
        Tool("SpostaR", "Transform", {"Input": Conn("SoloR"), "Center": off(3, "+"), "Edges": 2}),
        Tool("SpostaB", "Transform", {"Input": Conn("SoloB"), "Center": off(9, "-"), "Edges": 2}),
        Tool("UnisciR", "Merge", {"Background": Conn("SoloG"), "Foreground": Conn("SpostaR"),
                                  "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        Tool("UnisciB", "Merge", {"Background": Conn("UnisciR"), "Foreground": Conn("SpostaB"),
                                  "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        Tool("Scatto", "Transform", {"Input": Conn("UnisciB"), "Center": jitter, "Edges": 1}),
        *progress(c),
    ]
    return Macro("YTK_Glitch", tools, "Scatto", controls_exposed(c),
                 [("Taglio", "Background", "Clip in uscita"), ("Taglio", "Foreground", "Clip in entrata")])


def tr_spin():
    c = {"Turns": slider("Rotazione (gradi)", 180, 45, 720), "Zoom": slider("Zoom", 0.4, 0, 2)}
    a1 = ease_in(clamp01(f"{P}*2"))
    b1 = f"(1-{ease_out(clamp01(f'{P}*2-1'))})"
    tools = [
        Tool("ClipA", "Transform", {"Angle": Expr(f"-Ctrl.Turns/2*{a1}"),
                                    "Size": Expr(f"1+Ctrl.Zoom*{a1}"), "Edges": 3,
                                    "MotionBlur": 1, "Quality": 8, "ShutterAngle": 180}),
        Tool("ClipB", "Transform", {"Angle": Expr(f"Ctrl.Turns/2*{b1}"),
                                    "Size": Expr(f"1+Ctrl.Zoom*{b1}"), "Edges": 3,
                                    "MotionBlur": 1, "Quality": 8, "ShutterAngle": 180}),
        Tool("Taglio", "Dissolve", {"Background": Conn("ClipA"), "Foreground": Conn("ClipB"),
                                    "Mix": cut_mix()}),
        *progress(c),
    ]
    return Macro("YTK_Spin", tools, "Taglio", controls_exposed(c),
                 [("ClipA", "Input", "Clip in uscita"), ("ClipB", "Input", "Clip in entrata")])


def tr_light_leak():
    c = {"Amount": slider("Intensità luce", 1, 0, 1.5)}
    tools = [
        Tool("Dissolvenza", "Dissolve", {"Mix": Expr(ease_io(P))}),
        Tool("Luce", "FastNoise", {**FRAME, "Detail": 2, "XScale": 1.2, "Contrast": 1.6,
                                   "Brightness": 0.1, "SeetheRate": 0.3, "Seethe": Expr(f"{P}*2"),
                                   "Center": Expr(f"Point(-0.3+{P}*1.2, 0.5)")}),
        Tool("Tinta", "ColorGain", {"Input": Conn("Luce"), "LockRGB": 0,
                                    "GainRed": 1.25, "GainGreen": 0.62, "GainBlue": 0.22}),
        Tool("Bruciatura", "Merge", {"Background": Conn("Dissolvenza"), "Foreground": Conn("Tinta"),
                                     "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0,
                                     "Blend": Expr(f"Ctrl.Amount*sin(pi*{P})")}),
        *progress(c),
    ]
    return Macro("YTK_LightLeak", tools, "Bruciatura",
                 controls_exposed(c) + [Exposed("Tinta", "GainRed", "Tinta rosso"),
                                        Exposed("Tinta", "GainGreen", "Tinta verde"),
                                        Exposed("Tinta", "GainBlue", "Tinta blu")],
                 [("Dissolvenza", "Background", "Clip in uscita"),
                  ("Dissolvenza", "Foreground", "Clip in entrata")])


# --------------------------------------------------------------------------- #
# EFFECTS (drag onto a clip) — MainInput1 = the clip
# --------------------------------------------------------------------------- #
def fx_shake():
    c = {"Strength": slider("Intensità", 0.5, 0, 2), "Speed": slider("Velocità", 0.6, 0, 1),
         "Zoom": slider("Zoom anti-bordi", 1.06, 1, 1.5)}
    tools = [
        Tool("Tremolio", "CameraShake", {"XDeviation": Expr("0.02*Ctrl.Strength"),
                                         "YDeviation": Expr("0.02*Ctrl.Strength"),
                                         "RotationDeviation": Expr("0.3*Ctrl.Strength"),
                                         "Speed": Expr("Ctrl.Speed"), "Randomness": 0.9,
                                         "OverallStrength": 1, "Edges": 3}),
        Tool("Ctrl", "Transform", {"Input": Conn("Tremolio"), "Size": Expr("Zoom"),
                                   **ctrl_values(c)}, controls=c),
    ]
    return Macro("YTK_CameraShake", tools, "Ctrl", controls_exposed(c),
                 [("Tremolio", "Input", "Input")])


def fx_punch_in():
    c = {"Zoom": slider("Zoom", 1.25, 1, 3),
         "InDur": slider("Durata animazione (frame, 0 = istantaneo)", 0, 0, 30, integer=True, allowed=(0, 600))}
    size = Expr(f":if InDur<1 then return Zoom end\n"
                f"local a={clamp01(f'{T}/InDur')}\n"
                f"return 1+(Zoom-1)*{ease_out('a')}")
    tools = [Tool("Ctrl", "Transform", {"Size": size, "Center": (0.5, 0.5), "Edges": 3,
                                        **ctrl_values(c)}, controls=c)]
    return Macro("YTK_ZoomPunchIn", tools, "Ctrl",
                 controls_exposed(c) + [Exposed("Ctrl", "Center", "Centro zoom"),
                                        Exposed("Ctrl", "Pivot", "Punto di zoom")],
                 [("Ctrl", "Input", "Input")])


def fx_ken_burns():
    c = {"From": slider("Zoom iniziale", 1.0, 1, 2), "To": slider("Zoom finale", 1.15, 1, 2),
         "Smooth": checkbox("Movimento morbido (ease)", 1)}
    size = Expr(f":local p={clamp01(f'{T}/{LEN}')}\n"
                f"if Smooth>0.5 then p={ease_io('p')} end\n"
                f"return From+(To-From)*p")
    tools = [Tool("Ctrl", "Transform", {"Size": size, "Edges": 3, **ctrl_values(c)}, controls=c)]
    return Macro("YTK_ZoomLento", tools, "Ctrl",
                 controls_exposed(c) + [Exposed("Ctrl", "Pivot", "Punto di zoom")],
                 [("Ctrl", "Input", "Input")])


def fx_impact():
    c = {"Strength": slider("Intensità", 1, 0, 3)}
    size = Expr(f":local t={T}\n"
                f"local s=1+0.18*Strength*{clamp01('t/3')}\n"
                f"if t>3 then s=1+Strength*(0.1+0.08*exp(-(t-3)/5)) end\n"
                f"return s")
    center = Expr(f":local t={T}\n"
                  f"local a=0.012*Strength*exp(-t/6)\n"
                  f"return Point(0.5+a*sin(t*2.3), 0.5+a*cos(t*3.1))")
    tools = [Tool("Ctrl", "Transform", {"Size": size, "Center": center, "Edges": 3,
                                        "MotionBlur": 1, "Quality": 5, **ctrl_values(c)}, controls=c)]
    return Macro("YTK_ZoomImpatto", tools, "Ctrl", controls_exposed(c), [("Ctrl", "Input", "Input")])


def fx_rgb_split():
    c = {"Amount": slider("Spostamento", 0.006, 0, 0.05),
         "Flicker": checkbox("Tremolio casuale", 1)}
    off = lambda sign, seed: Expr(  # noqa: E731
        f":local a=Ctrl.Amount\n"
        f"if Ctrl.Flicker>0.5 then randomseed(floor(time)*19+{seed}) a=a*(0.4+1.2*random()) end\n"
        f"return Point(0.5{sign}a, 0.5)")
    tools = [
        Tool("Ingresso", "Transform", {}),
        Tool("SoloR", "ColorGain", {"Input": Conn("Ingresso"), "LockRGB": 0, "GainGreen": 0, "GainBlue": 0}),
        Tool("SoloG", "ColorGain", {"Input": Conn("Ingresso"), "LockRGB": 0, "GainRed": 0, "GainBlue": 0}),
        Tool("SoloB", "ColorGain", {"Input": Conn("Ingresso"), "LockRGB": 0, "GainRed": 0, "GainGreen": 0}),
        Tool("SpostaR", "Transform", {"Input": Conn("SoloR"), "Center": off("+", 1), "Edges": 2}),
        Tool("SpostaB", "Transform", {"Input": Conn("SoloB"), "Center": off("-", 2), "Edges": 2}),
        Tool("UnisciR", "Merge", {"Background": Conn("SoloG"), "Foreground": Conn("SpostaR"),
                                  "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        Tool("Ctrl", "Merge", {"Background": Conn("UnisciR"), "Foreground": Conn("SpostaB"),
                               "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0, **ctrl_values(c)},
             controls=c),
    ]
    return Macro("YTK_RGBSplit", tools, "Ctrl", controls_exposed(c) + [Exposed("Ctrl", "Blend", "Mix")],
                 [("Ingresso", "Input", "Input")])


def fx_vhs():
    c = {"Amount": slider("Intensità", 1, 0, 2)}
    tools = [
        Tool("Morbido", "Blur", {"XBlurSize": Expr("1.5*Ctrl.Amount")}),
        Tool("SoloR", "ColorGain", {"Input": Conn("Morbido"), "LockRGB": 0, "GainGreen": 0, "GainBlue": 0}),
        Tool("SoloGB", "ColorGain", {"Input": Conn("Morbido"), "LockRGB": 0, "GainRed": 0}),
        Tool("SpostaR", "Transform", {"Input": Conn("SoloR"), "Edges": 2,
                                      "Center": Expr("Point(0.5+0.004*Ctrl.Amount, 0.5)")}),
        Tool("Colori", "Merge", {"Background": Conn("SoloGB"), "Foreground": Conn("SpostaR"),
                                 "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0}),
        Tool("Sbiadito", "BrightnessContrast", {"Input": Conn("Colori"), "Saturation": 0.78,
                                                "Contrast": -0.08, "Lift": 0.04, "Gamma": 1.05}),
        Tool("Righe", "FastNoise", {**FRAME, "LockXY": 0, "XScale": 0.6, "YScale": 90,
                                    "Detail": 3, "Contrast": 1.4, "SeetheRate": 1.5,
                                    "Center": Expr("Point(0, time*0.013)")}),
        Tool("Interferenze", "Merge", {"Background": Conn("Sbiadito"), "Foreground": Conn("Righe"),
                                       "ApplyMode": FuID("Overlay"), "PerformDepthMerge": 0,
                                       "Blend": Expr("0.18*Ctrl.Amount")}),
        Tool("Grana", "FilmGrain", {"Input": Conn("Interferenze"), "MasterStrength": 0.05}),
        Tool("Ctrl", "Transform", {"Input": Conn("Grana"), "Edges": 2, **ctrl_values(c),
                                   "Center": Expr(":randomseed(floor(time)*3+1)\n"
                                                  "local j=0\n"
                                                  "if random()<0.12 then j=(random()-0.5)*0.006*Amount end\n"
                                                  "return Point(0.5+j, 0.5)")},
             controls=c),
    ]
    return Macro("YTK_VHS", tools, "Ctrl", controls_exposed(c), [("Morbido", "Input", "Input")])


def fx_vignette():
    c = {}
    tools = [
        Tool("Forma", "EllipseMask", {"Center": (0.5, 0.5), "Width": 1.25,
                                      "Height": Expr("Forma.Width"),
                                      "SoftEdge": 0.35, "Invert": 1}),
        solid("Nero", (0, 0, 0), {"EffectMask": Conn("Forma", "Mask")}),
        Tool("Ctrl", "Merge", {"Foreground": Conn("Nero"), "PerformDepthMerge": 0, "Blend": 0.7}),
    ]
    return Macro("YTK_Vignetta", tools, "Ctrl", [
        Exposed("Ctrl", "Blend", "Intensità", 0.7),
        Exposed("Forma", "SoftEdge", "Morbidezza", 0.35),
        Exposed("Forma", "Width", "Ampiezza", 1.25),
    ], [("Ctrl", "Background", "Input")])


def fx_letterbox():
    c = {"Ratio": slider("Formato (2.39 = cinema)", 2.39, 1.5, 3),
         "InDur": slider("Entrata animata (frame, 0 = fisse)", 0, 0, 60, integer=True, allowed=(0, 600))}
    h = Expr(f":local r=Ctrl.Ratio\nlocal a=1\n"
             f"if Ctrl.InDur>=1 then a={ease_out(clamp01(f'{T}/Ctrl.InDur'))} end\n"
             f"local v=min({ASPECT_WH}/max(r,0.1),1)\n"
             f"return 1+(v-1)*a")
    tools = [
        Tool("Fascia", "RectangleMask", {"Center": (0.5, 0.5), "Width": 1.2, "Height": h, "Invert": 1}),
        solid("Nero", (0, 0, 0), {"EffectMask": Conn("Fascia", "Mask")}),
        Tool("Ctrl", "Merge", {"Foreground": Conn("Nero"), "PerformDepthMerge": 0, **ctrl_values(c)},
             controls=c),
    ]
    return Macro("YTK_BandeCinema", tools, "Ctrl", controls_exposed(c), [("Ctrl", "Background", "Input")])


def fx_censor():
    tools = [
        Tool("Area", "RectangleMask", {"Center": (0.5, 0.5), "Width": 0.2, "Height": 0.12,
                                       "CornerRadius": 0.3, "SoftEdge": 0.004}),
        Tool("Ctrl", "Blur", {"XBlurSize": 60, "EffectMask": Conn("Area", "Mask")}),
    ]
    return Macro("YTK_SfocaturaCensura", tools, "Ctrl", [
        Exposed("Area", "Center", "Posizione area"),
        Exposed("Area", "Width", "Larghezza area"), Exposed("Area", "Height", "Altezza area"),
        Exposed("Area", "CornerRadius", "Arrotondamento"),
        Exposed("Ctrl", "XBlurSize", "Sfocatura", 60),
    ], [("Ctrl", "Input", "Input")])


def fx_glow():
    tools = [Tool("Ctrl", "SoftGlow", {"Threshold": 0.55, "Gain": 0.9, "XGlowSize": 40})]
    return Macro("YTK_GlowSogno", tools, "Ctrl", [
        Exposed("Ctrl", "Threshold", "Soglia", 0.55), Exposed("Ctrl", "Gain", "Intensità", 0.9),
        Exposed("Ctrl", "XGlowSize", "Ampiezza bagliore", 40), Exposed("Ctrl", "Blend", "Mix"),
    ], [("Ctrl", "Input", "Input")])


def fx_grain():
    tools = [Tool("Ctrl", "FilmGrain", {"MasterStrength": 0.06, "MasterXSize": 0.8, "Monochrome": 1})]
    return Macro("YTK_GranaPellicola", tools, "Ctrl", [
        Exposed("Ctrl", "MasterStrength", "Intensità", 0.06),
        Exposed("Ctrl", "MasterXSize", "Dimensione grana", 0.8),
        Exposed("Ctrl", "Monochrome", "Monocromatica", 1),
    ], [("Ctrl", "Input", "Input")])


def fx_bw():
    tools = [Tool("Ctrl", "BrightnessContrast", {"Saturation": 0, "Contrast": 0.25, "Gamma": 0.95})]
    return Macro("YTK_BiancoNero", tools, "Ctrl", [
        Exposed("Ctrl", "Contrast", "Contrasto", 0.25), Exposed("Ctrl", "Gamma", "Gamma", 0.95),
        Exposed("Ctrl", "Blend", "Mix"),
    ], [("Ctrl", "Input", "Input")])


def fx_pip():
    c = {"Scale": slider("Dimensione", 0.33, 0.1, 1), "Border": slider("Spessore bordo", 0.006, 0, 0.03),
         "Radius": slider("Arrotondamento angoli", 0.08, 0, 0.5)}
    asp = ASPECT_WH
    tools = [
        canvas("Vuoto"),
        Tool("Riduci", "Transform", {"Size": Expr("Ctrl.Scale"), "Center": Expr("Posizione.Center")}),
        # Holds the on-screen position control only (not part of the image chain).
        Tool("Posizione", "Merge", {"Background": Conn("Vuoto"), "Center": (0.72, 0.7),
                                    "PerformDepthMerge": 0}),
        Tool("MaskBordo", "RectangleMask", {
            "Center": Expr("Posizione.Center"),
            "Width": Expr("Ctrl.Scale+2*Ctrl.Border"),
            "Height": Expr(f"Ctrl.Scale+2*Ctrl.Border*{asp}"),
            "CornerRadius": Expr("Ctrl.Radius"), "SoftEdge": 0.0005}),
        solid("Bordo", (1, 1, 1), {"EffectMask": Conn("MaskBordo", "Mask")}),
        Tool("MaskClip", "RectangleMask", {
            "Center": Expr("Posizione.Center"),
            "Width": Expr("Ctrl.Scale"), "Height": Expr("Ctrl.Scale"),
            "CornerRadius": Expr("Ctrl.Radius"), "SoftEdge": 0.0005}),
        Tool("ConBordo", "Merge", {"Background": Conn("Vuoto"), "Foreground": Conn("Bordo"),
                                   "PerformDepthMerge": 0}),
        Tool("Ctrl", "Merge", {"Background": Conn("ConBordo"), "Foreground": Conn("Riduci"),
                               "EffectMask": Conn("MaskClip", "Mask"), "PerformDepthMerge": 0,
                               **ctrl_values(c)}, controls=c),
    ]
    return Macro("YTK_PictureInPicture", tools, "Ctrl", [
        Exposed("Posizione", "Center", "Posizione"),
    ] + controls_exposed(c) + [
        Exposed("Bordo", "TopLeftRed", "Colore bordo", group=1),
        Exposed("Bordo", "TopLeftGreen", group=1), Exposed("Bordo", "TopLeftBlue", group=1),
    ], [("Riduci", "Input", "Input")])


def fx_look(key, label):
    tools = [Tool("Ctrl", "FileLUT", {"LUTFile": f"Setting:YTK_{key}.cube", "Blend": 1})]
    return Macro(f"YTK_Look_{key}", tools, "Ctrl",
                 [Exposed("Ctrl", "Blend", "Intensità look", 1)], [("Ctrl", "Input", "Input")])


# --------------------------------------------------------------------------- #
# GENERATORS (place on a track above your video)
# --------------------------------------------------------------------------- #
def g_progress():
    c = {"Thick": slider("Spessore barra", 0.02, 0.004, 0.08),
         "Top": checkbox("Barra in alto", 0)}
    y = "iif(Ctrl.Top>0.5, 1-Ctrl.Thick*0.5, Ctrl.Thick*0.5)"
    p = clamp01(f"{T}/{LEN}")
    tools = [
        canvas(),
        Tool("FondoMask", "RectangleMask", {"Center": Expr(f"Point(0.5, {y})"), "Width": 1,
                                            "Height": Expr("Ctrl.Thick")}),
        solid("Fondo", (0, 0, 0), {"TopLeftAlpha": 0.45, "EffectMask": Conn("FondoMask", "Mask")}),
        Tool("BarraMask", "RectangleMask", {"Center": Expr(f"Point({p}/2, {y})"),
                                            "Width": Expr(p), "Height": Expr("Ctrl.Thick")}),
        solid("Barra", (1, 0.1, 0.1), {"EffectMask": Conn("BarraMask", "Mask")}),
        Tool("Unisci", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("Fondo"),
                                 "PerformDepthMerge": 0}),
        Tool("Ctrl", "Merge", {"Background": Conn("Unisci"), "Foreground": Conn("Barra"),
                               "PerformDepthMerge": 0, **ctrl_values(c)}, controls=c),
    ]
    return Macro("YTK_BarraProgresso", tools, "Ctrl", controls_exposed(c) + [
        Exposed("Barra", "TopLeftRed", "Colore barra", group=1),
        Exposed("Barra", "TopLeftGreen", group=1), Exposed("Barra", "TopLeftBlue", group=1),
        Exposed("Fondo", "TopLeftAlpha", "Opacità sfondo barra", 0.45),
    ])


def g_letterbox():
    c = {"Ratio": slider("Formato (2.39 = cinema)", 2.39, 1.5, 3),
         "InDur": slider("Entrata animata (frame, 0 = fisse)", 12, 0, 60, integer=True, allowed=(0, 600))}
    h = Expr(f":local r=Ctrl.Ratio\nlocal a=1\n"
             f"if Ctrl.InDur>=1 then a={ease_out(clamp01(f'{T}/Ctrl.InDur'))} end\n"
             f"local v=min({ASPECT_WH}/max(r,0.1),1)\n"
             f"return 1+(v-1)*a")
    tools = [
        canvas(),
        Tool("Fascia", "RectangleMask", {"Center": (0.5, 0.5), "Width": 1.2, "Height": h, "Invert": 1}),
        solid("Nero", (0, 0, 0), {"EffectMask": Conn("Fascia", "Mask")}),
        Tool("Ctrl", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("Nero"),
                               "PerformDepthMerge": 0, **ctrl_values(c)}, controls=c),
    ]
    return Macro("YTK_BandeCinemaGeneratore", tools, "Ctrl", controls_exposed(c))


def g_gradient():
    tools = [
        Tool("Ctrl", "FastNoise", {**FRAME, "Detail": 1.5, "XScale": 0.8, "Contrast": 1.3,
                                   "SeetheRate": 0.05, "Type": 0,
                                   "Color1Red": 0.36, "Color1Green": 0.1, "Color1Blue": 0.85, "Color1Alpha": 1,
                                   "Color2Red": 0.95, "Color2Green": 0.25, "Color2Blue": 0.45, "Color2Alpha": 1,
                                   "Center": Expr("Point(time*0.002, time*0.001)")}),
    ]
    return Macro("YTK_SfondoAnimato", tools, "Ctrl", [
        Exposed("Ctrl", "Color1Red", "Colore 1", group=1), Exposed("Ctrl", "Color1Green", group=1),
        Exposed("Ctrl", "Color1Blue", group=1),
        Exposed("Ctrl", "Color2Red", "Colore 2", group=2), Exposed("Ctrl", "Color2Green", group=2),
        Exposed("Ctrl", "Color2Blue", group=2),
        Exposed("Ctrl", "SeetheRate", "Velocità movimento", 0.05),
        Exposed("Ctrl", "XScale", "Scala", 0.8),
    ])


# --------------------------------------------------------------------------- #
# Catalogue: (category, file name, builder, short description)
# --------------------------------------------------------------------------- #
LOOKS = [
    ("TealOrange", "Look Teal & Orange", "Il classico look cinematografico: ombre verde-acqua, pelle calda"),
    ("CaldoCinema", "Look Caldo Cinematico", "Toni dorati da tramonto, contrasto morbido"),
    ("FreddoModerno", "Look Freddo Moderno", "Look pulito e freddo stile tech/review"),
    ("Vintage", "Look Vintage Pellicola", "Neri sbiaditi, colori desaturati, calore pellicola"),
    ("Moody", "Look Moody Scuro", "Scuro e desaturato stile vlog cinematico"),
    ("VivaceYT", "Look Vivace YouTube", "Colori saturi e brillanti che risaltano nel feed"),
    ("BiancoNeroFilm", "Look B&N Pellicola", "Bianco e nero ad alto contrasto"),
    ("Pastello", "Look Pastello", "Colori tenui e luminosi stile lifestyle"),
]

CATALOG = [
    ("Titles", "YTK Macchina da Scrivere", t_typewriter, "Il testo appare lettera per lettera"),
    ("Titles", "YTK Testo Pop", t_pop, "Testo grande con contorno che rimbalza (stile MrBeast)"),
    ("Titles", "YTK Parola per Parola", t_words, "Sottotitoli dinamici una parola alla volta (Shorts/Reels)"),
    ("Titles", "YTK Box Evidenziato", t_box, "Parola chiave su riquadro colorato"),
    ("Titles", "YTK Lower Third", t_lower_third, "Nome e ruolo che scorrono da sinistra"),
    ("Titles", "YTK Iscriviti", t_subscribe, "Pulsante iscriviti con animazione del click"),
    ("Titles", "YTK Titolo Cinematico", t_cinematic, "Titolo elegante con lettere che si allargano"),
    ("Titles", "YTK Titolo Glitch", t_glitch, "Testo con effetto glitch RGB"),
    ("Titles", "YTK Contatore", t_counter, "Numero che conta (iscritti, soldi, views)"),
    ("Titles", "YTK Cerchio Evidenzia", t_circle, "Cerchio per evidenziare un dettaglio"),
    ("Titles", "YTK Freccia", t_arrow, "Freccia animata che indica qualcosa"),
    ("Transitions", "YTK Zoom In", lambda: tr_zoom(True), "Zoom veloce in avanti con sfocatura"),
    ("Transitions", "YTK Zoom Out", lambda: tr_zoom(False), "Zoom veloce all'indietro con sfocatura"),
    ("Transitions", "YTK Whip Sinistra", lambda: tr_whip("sinistra"), "Panoramica a frusta verso sinistra"),
    ("Transitions", "YTK Whip Destra", lambda: tr_whip("destra"), "Panoramica a frusta verso destra"),
    ("Transitions", "YTK Whip Su", lambda: tr_whip("su"), "Panoramica a frusta verso l'alto"),
    ("Transitions", "YTK Whip Giu", lambda: tr_whip("giu"), "Panoramica a frusta verso il basso"),
    ("Transitions", "YTK Flash Bianco", tr_flash, "Lampo bianco sul taglio"),
    ("Transitions", "YTK Dissolvenza Sfocata", tr_blur, "Dissolvenza morbida con sfocatura"),
    ("Transitions", "YTK Glitch", tr_glitch, "Transizione glitch digitale"),
    ("Transitions", "YTK Spin", tr_spin, "Rotazione con motion blur"),
    ("Transitions", "YTK Light Leak", tr_light_leak, "Bruciatura di luce calda stile pellicola"),
    ("Effects", "YTK Camera Shake", fx_shake, "Tremolio della camera"),
    ("Effects", "YTK Zoom Punch-In", fx_punch_in, "Zoom sul viso per enfasi / jump cut"),
    ("Effects", "YTK Zoom Lento", fx_ken_burns, "Zoom lento continuo (Ken Burns)"),
    ("Effects", "YTK Zoom Impatto", fx_impact, "Zoom di colpo con scossa (momenti WOW)"),
    ("Effects", "YTK RGB Split", fx_rgb_split, "Aberrazione cromatica / separazione RGB"),
    ("Effects", "YTK VHS Retro", fx_vhs, "Look videocassetta anni '90"),
    ("Effects", "YTK Vignetta", fx_vignette, "Bordi scuri per concentrare lo sguardo"),
    ("Effects", "YTK Bande Cinema", fx_letterbox, "Bande nere cinematografiche 2.39:1"),
    ("Effects", "YTK Sfocatura Censura", fx_censor, "Sfoca un'area (targhe, volti, dati)"),
    ("Effects", "YTK Glow Sogno", fx_glow, "Bagliore morbido sulle luci"),
    ("Effects", "YTK Grana Pellicola", fx_grain, "Grana da pellicola"),
    ("Effects", "YTK Bianco e Nero", fx_bw, "Bianco e nero contrastato"),
    ("Effects", "YTK Picture in Picture", fx_pip, "Riquadro facecam con bordo arrotondato"),
    *[("Effects", f"YTK {label}", (lambda k=k, l=label: fx_look(k, l)), desc) for k, label, desc in LOOKS],
    ("Generators", "YTK Barra Progresso", g_progress, "Barra che si riempie per tutta la durata"),
    ("Generators", "YTK Bande Cinema", g_letterbox, "Bande cinema su traccia separata"),
    ("Generators", "YTK Sfondo Animato", g_gradient, "Sfondo colorato in movimento"),
]
