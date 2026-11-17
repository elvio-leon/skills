"""Titoli Moviola (Edit/Titles): si mettono su una traccia sopra la clip."""
from __future__ import annotations

from base import *  # noqa: F401,F403
from base import BASE, BG_OPTS, GLIDE, OUT  # noqa: F401

UTF8 = "local function chars(s) local t={} for c in string.gmatch(s,'[%z\\1-\\127\\194-\\244][\\128-\\191]*') do table.insert(t,c) end return t end\n"


def ex_out(d=18):
    """Avanzamento dell'uscita (0 → 1 negli ultimi d fotogrammi)."""
    return f"(1-{clamp01(f'{R}/{F(d)}')})"


# ============================================================== APERTURA
def t_apertura():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "Frame": checkbox("Cornice di registro", 1),
         "TSize": slider("Dimensione titolo (px)", 230, 80, 400), "Grain": slider("Grana pellicola", 0.35, 0, 1),
         "Drift": slider("Spinta lenta di camera", 0.04, 0, 0.15)}
    two = "((Riga2.StyledText.Value or '')~='')"
    ts = "Ctrl.TSize"
    # centro verticale di ciascuna riga (px, y in basso)
    y1 = f"(({two}) and 540-{ts}*0.52 or 520)"
    y2 = f"(540+{ts}*0.5)"
    bottom = f"(({two}) and 540+{ts}*1.02 or 520+{ts}*0.5)"
    xo = ex_out(20)
    tools = ground_tools()
    fr, fl = reg_frame("Cornice", 60, 60, 1860, 1020, f"{eo(st(0, 28))}*(1-{xo})", alpha=0.45)
    tools += fr
    k_occ = eo(st(6, 30))
    tools += [
        text("Occhiello", "UNA STORIA DEL CALCIO ITALIANO", INTER, 26, CARTA, 960, f"{y1}-{ts}*0.5-44", align=0,
             track=f"1.75-0.3*{k_occ}", alpha=0.85),
        rect("RigaMask1", 960, y1, 1900, f"{ts}*1.02"),
        rect("RigaMask2", 960, y2, 1900, f"{ts}*1.02"),
    ]
    for i, (yy, d) in enumerate(((y1, 14), (y2, 18)), 1):
        k = eo(st(d, 30))
        tools.append(text(f"Riga{i}", "IL GRANDE" if i == 1 else "TORINO", ANTON, ts, CARTA, 960,
                          f"{yy}+(1-{k})*{ts}*1.05-{eio(xo)}*{ts}*1.05", align=0, track=f"1.08-0.08*{k}",
                          extra={"EffectMask": Conn(f"RigaMask{i}", "Mask")}))
    tools += [
        Tool("Titolo", "Merge", {"Background": Conn("Riga1"), "Foreground": Conn("Riga2"), "PerformDepthMerge": 0}),
        Tool("TitoloAlfa", "BitmapMask", {"Image": Conn("Titolo"), "Channel": FuID("Alpha"), "Low": 0, "High": 1}),
        rect("RiflessoMask", f"-500+2900*{eio(st(50, 36))}", 540, 300, 1500, angle=-20, soft=0.06,
             prev="TitoloAlfa", mode="Minimum"),
        solid("Riflesso", (1, 0.99, 0.94), "RiflessoMask", alpha=0.85),
        rect("FiloMask", 960, f"{bottom}+34", f"840*{eo(st(28, 26))}*(1-{xo})", 6),
        solid("Filo", ROSSO, "FiloMask"),
        text("Sotto", "1943 — 1949", INTER, 38, CARTA, 960, f"{bottom}+92+(1-{eo(st(36, 22))})*16", align=0, track=1.55),
        grain(),
    ]
    layers = ground_layers() + [(fl[0][0], f"Ctrl.Frame*{fl[0][1]}"), (fl[1][0], f"Ctrl.Frame*{fl[1][1]}"),
                                ("Occhiello", f"{k_occ}*(1-{xo})"), ("Titolo", None), ("Riflesso", None), ("Filo", None),
                                ("Sotto", f"{eo(st(36, 22))}*(1-{xo})"), grain_layer()]
    mt, last = stack(layers)
    return title("MOV_Apertura", tools + mt, c,
                 [texp("Occhiello", "Occhiello"), texp("Riga1", "Titolo riga 1"), texp("Riga2", "Titolo riga 2 (vuota = una riga)"),
                  texp("Sotto", "Sottotitolo"), *color_exposed("Filo", "Colore filo", 1)],
                 last, size=f"1+Ctrl.Drift*{GLIDE}")


# ============================================================== CAPITOLO
def t_capitolo():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "Fill": checkbox("Riempimento del numero", 1),
         "NSize": slider("Dimensione numero (px)", 520, 200, 800), "Grain": slider("Grana pellicola", 0.35, 0, 1)}
    xo = ex_out(20)
    ns = "Ctrl.NSize"
    tools = ground_tools()
    tools += [
        # contorno rivelato dall'alto, poi riempimento che sale dal basso
        rect("ContornoMask", 520, f"540-{ns}*0.5+{ns}*1.1*{eio(st(4, 40))}/2", 1000, f"{ns}*1.1*{eio(st(4, 40))}"),
        text("NumeroContorno", "IV", ANTON, ns, CARTA, 520, f"540+{eio(xo)}*60", align=0, alpha=0,
             extra={"Enabled2": 1, "ElementShape2": 1, "OutsideOnly2": 0, "Thickness2": 0.0018, "Red2": CARTA[0],
                    "Green2": CARTA[1], "Blue2": CARTA[2], "Alpha2": 1, "PriorityBack2": 9,
                    "StyledText": Expr("Text(Numero.StyledText.Value)"), "EffectMask": Conn("ContornoMask", "Mask")}),
        rect("RiempiMask", 520, f"540+{ns}*0.5-{ns}*1.04*{eo(st(26, 34))}/2", 1000, f"{ns}*1.04*{eo(st(26, 34))}"),
        text("Numero", "IV", ANTON, ns, ROSSO, 520, f"540+{eio(xo)}*60", align=0,
             extra={"EffectMask": Conn("RiempiMask", "Mask")}),
        rect("FiloVMask", 1060, 540, 2, f"460*{eo(st(12, 28))}"),
        solid("FiloV", CARTA, "FiloVMask", alpha=0.55),
        text("EtichettaSrc", "CAPITOLO", INTER, 26, ROSSO, 1130, 400),
        text("Etichetta", "CAPITOLO IV", INTER_B, 26, ROSSO, f"1130-(1-{eo(st(22, 20))})*12", 405, track=1.75,
             extra={"StyledText": Expr("Text(string.upper((EtichettaSrc.StyledText.Value or '')..' '..(Numero.StyledText.Value or '')))")}),
        text("Titolo", "La nebbia\nsu Superga", SERIF_I, 92, CARTA, 1130, f"530+(1-{eo(st(32, 30))})*26",
             extra={"LineSpacing": 1.0}),
        Tool("TitoloBlur", "Blur", {"Input": Conn("Titolo"), "XBlurSize": Expr(f"(1-{eo(st(32, 30))})*14")}),
        text("Data", "4 MAGGIO 1949", INTER, 28, CARTA, 1130, 680, track=1.5, alpha=0.8),
        grain(),
    ]
    layers = ground_layers() + [("NumeroContorno", f"1-{xo}"), ("Numero", f"Ctrl.Fill*(1-{xo})"),
                                ("FiloV", f"1-{xo}"), ("Etichetta", f"{eo(st(22, 20))}*(1-{xo})"),
                                ("TitoloBlur", f"{eo(st(32, 30))}*(1-{xo})"), ("Data", f"{eo(st(48, 20))}*(1-{xo})"),
                                grain_layer()]
    mt, last = stack(layers)
    m = title("MOV_Capitolo", tools + mt, c,
              [texp("Numero", "Numero"), texp("EtichettaSrc", "Etichetta"), texp("Titolo", "Titolo"),
               texp("Data", "Data o periodo"), *text_color_exposed("Numero", "Colore riempimento", 1)],
              last, size=f"1+0.03*{GLIDE}")
    return m


# ============================================================== CITAZIONE
def t_citazione():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "Under": checkbox("Sottolineatura a pennarello", 1),
         "ULen": slider("Lunghezza sottolineatura (px)", 330, 40, 1400), "UAt": slider("Sottolineatura al fotogramma", 70, 0, 400, integer=True),
         "Grain": slider("Grana pellicola", 0.3, 0, 1)}
    xo = ex_out(22)
    k = eo(st(14, 36))
    u = eio(clamp01(f"({T}-Ctrl.UAt*Ctrl.Speed)/max({F(14)}*Ctrl.Speed,1)"))
    tools = ground_tools()
    tools += [
        text("Virgolette", "“", SERIF_B, f"300*{eback(st(4, 22))}", ROSSO, 960, 330, align=0),
        text("Testo", "Il calcio è la cosa più importante\ndelle cose meno importanti.", SERIF_I, 72, CARTA, 960,
             f"560+(1-{k})*22", align=0, extra={"LineSpacing": 1.05}),
        Tool("TestoBlur", "Blur", {"Input": Conn("Testo"), "XBlurSize": Expr(f"(1-{k})*16+{xo}*10")}),
        # sottolineatura: due passate leggermente storte, tipo pennarello
        rect("SottMask", f"Sott.Center.X*{W}-Ctrl.ULen/2+Ctrl.ULen*{u}/2", f"(1-Sott.Center.Y)*{H}", f"Ctrl.ULen*{u}", 9, angle=-0.8),
        rect("SottMask2", f"Sott.Center.X*{W}-Ctrl.ULen/2+Ctrl.ULen*{u}/2+6", f"(1-Sott.Center.Y)*{H}+5", f"Ctrl.ULen*{u}*0.96", 5,
             angle=0.6, prev="SottMask"),
        Tool("Sott", "Background", {**FRAME, "TopLeftRed": ROSSO[0], "TopLeftGreen": ROSSO[1], "TopLeftBlue": ROSSO[2],
                                    "TopLeftAlpha": 1, "EffectMask": Conn("SottMask2", "Mask"), "Center": P(1300, 556)}),
        text("AutoreSrc", "Arrigo Sacchi", INTER, 28, CARTA, 960, 760),
        rect("AutLineaMask", 960, 744, f"80*{eo(st(60, 20))}", 3),
        solid("AutLinea", ROSSO, "AutLineaMask"),
        text("Autore", "", INTER_B, 28, CARTA, 960, 800, align=0, track=1.6, alpha=0.9,
             extra={"StyledText": Expr("Text('— '..string.upper(AutoreSrc.StyledText.Value or ''))")}),
        grain(),
    ]
    layers = ground_layers() + [("Virgolette", f"{clamp01(f'{st(4, 22)}*3')}*(1-{xo})"), ("TestoBlur", f"{k}*(1-{xo})"),
                                ("Sott", f"Ctrl.Under*(1-{xo})"), ("AutLinea", f"1-{xo}"),
                                ("Autore", f"{eo(st(62, 20))}*(1-{xo})"), grain_layer()]
    mt, last = stack(layers)
    return title("MOV_Citazione", tools + mt, c,
                 [texp("Testo", "Citazione (a capo dove vuoi)"), texp("AutoreSrc", "Autore"),
                  Exposed("Sott", "Center", "Posizione sottolineatura"), Exposed("Testo", "Font", "Font citazione"),
                  Exposed("Testo", "Size", "Dimensione citazione", round(72 / W, 5)),
                  *text_color_exposed("Virgolette", "Colore accento", 1)],
                 last, size=f"1+0.035*{GLIDE}")


# ============================================================== MACCHINA DA SCRIVERE
def t_macchina():
    c = {**BASE, "Rate": slider("Lettere al secondo", 16, 4, 40), "Delay": slider("Inizia dopo (fotogrammi)", 10, 0, 200, integer=True),
         "Strip": combo("Supporto", ["Striscia di carta corta", "Striscia di carta media", "Striscia di carta lunga", "Sul video (senza carta)"], 1),
         "Cursor": checkbox("Cursore", 1)}
    xo = ex_out(14)
    typed = (UTF8 + "local s=Sorgente.StyledText.Value or ''\nlocal t=chars(s)\n"
             f"local f=({T}-Ctrl.Delay*Ctrl.Speed)\nlocal n=floor(f*Ctrl.Rate/{F(25)}/Ctrl.Speed)\n"
             "if n<0 then n=0 end\nif n>#t then n=#t end\nlocal out=table.concat(t,'',1,n)\n"
             f"local done = n>=#t\nlocal blink = (floor({T}/{F(7)})%2==0)\n"
             "if Ctrl.Cursor>0.5 and (not done or blink) then out=out..'_' end\nreturn Text(out)")
    strips = [(1000, 190), (1400, 190), (1720, 190)]
    tools = []
    for i, (w, h) in enumerate(strips, 1):
        pts = torn_rect_pts(w, h, amp=5, step=9, seed=11 + i)
        tools += [poly(f"StrisciaMask{i}", 160 + w / 2 - 60, 905, pts, extra={"Angle": -0.4}),
                  solid(f"Striscia{i}", CARTA, f"StrisciaMask{i}"),
                  Tool(f"StrisciaFibra{i}", "FastNoise", {**FRAME, "Detail": 4, "XScale": 7, "Contrast": 0.7,
                                                         "Color1Red": 0.83, "Color1Green": 0.77, "Color1Blue": 0.67,
                                                         "EffectMask": Conn(f"StrisciaMask{i}", "Mask")}),
                  solid(f"StrisciaOmbraS{i}", (0, 0, 0), f"StrisciaMask{i}", alpha=0.55),
                  Tool(f"StrisciaOmbra{i}", "Blur", {"Input": Conn(f"StrisciaOmbraS{i}"), "XBlurSize": 22})]
    tools += [
        text("Sorgente", "TORINO, 4 MAGGIO 1949.\nORE 17:03. NEBBIA FITTA SULLA COLLINA.", MACCHINA, 52, INCHIOSTRO, 200, 905),
        text("Testo", "", MACCHINA, 52, INCHIOSTRO, 200, 905, extra={"StyledText": Expr(":" + typed), "LineSpacing": 1.15}),
    ]
    layers = []
    for i in range(1, 4):
        on = f"(Ctrl.Strip=={i - 1} and 1 or 0)"
        layers += [(f"StrisciaOmbra{i}", f"{on}*0.8*{eo(st(0, 10))}"), (f"Striscia{i}", f"{on}*{eo(st(0, 10))}"),
                   (f"StrisciaFibra{i}", f"{on}*0.45", "Multiply")]
    layers.append(("Testo", None))
    mt, last = stack(layers)
    tools += mt
    # sul video il testo è chiaro e ha l'ombra
    tt = next(t for t in tools if t.name == "Testo")
    tt.inputs.update({"Red1": Expr(f"Ctrl.Strip==3 and {CARTA[0]} or Sorgente.Red1"),
                      "Green1": Expr(f"Ctrl.Strip==3 and {CARTA[1]} or Sorgente.Green1"),
                      "Blue1": Expr(f"Ctrl.Strip==3 and {CARTA[2]} or Sorgente.Blue1"),
                      **shadow(0.0)})
    tt.inputs["Alpha3"] = Expr("Ctrl.Strip==3 and 0.7 or 0")
    tt.inputs["Size"] = Expr("Sorgente.Size")
    return title("MOV_MacchinaDaScrivere", tools, c,
                 [texp("Sorgente", "Testo (a capo dove vuoi)"), Exposed("Sorgente", "Size", "Dimensione testo", round(52 / W, 5)),
                  *text_color_exposed("Sorgente", "Colore inchiostro", 1)],
                 last, fade=True)


# ============================================================== IMPATTO
def t_impatto():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 2), "Beat": slider("Fotogrammi per battuta", 24, 6, 75, integer=True),
         "Start": slider("Prima battuta al fotogramma", 14, 0, 200, integer=True), "TSize": slider("Dimensione testo (px)", 300, 100, 500),
         "LastRed": checkbox("Ultima battuta in colore accento", 1), "Grain": slider("Grana pellicola", 0.4, 0, 1)}
    pre = (lua_lines("Battute") + f"local n=#L\nlocal b=Ctrl.Beat*Ctrl.Speed\nlocal f={T}-Ctrl.Start*Ctrl.Speed\n"
           "local i=floor(f/b)\nif i>n-1 then i=n-1 end\n")
    tools = ground_tools() + [text("Battute", "UNA SQUADRA.\nUNA CITTÀ.\nUNA LEGGENDA.", ANTON, 10, CARTA, 960, -400)]
    for s in range(4):
        k = f"((f-{s}*b)/{F(5)})"
        vis = f"(f>={s}*b and i=={s}) and 1 or 0"
        size = f":{pre}local k=min(max({k},0),1)\nlocal last=(i==n-1)\nlocal creep=1+0.05*min(max((f-{s}*b)/b,0),3)\nreturn Ctrl.TSize/{W}*(1+0.45*(1-(k>=1 and 1 or 1-2^(-10*k))))*creep"
        tools.append(text(f"Battuta{s}", "", ANTON, 10, CARTA, 960, 540, align=0, track=1.02,
                          extra={"StyledText": Expr(f":{pre}return Text(L[{s + 1}] or '')"), "Size": Expr(size),
                                 "Red1": Expr(f":{pre}if Ctrl.LastRed>0.5 and {s}==n-1 then return {ROSSO[0]} end return {CARTA[0]}"),
                                 "Green1": Expr(f":{pre}if Ctrl.LastRed>0.5 and {s}==n-1 then return {ROSSO[1]} end return {CARTA[1]}"),
                                 "Blue1": Expr(f":{pre}if Ctrl.LastRed>0.5 and {s}==n-1 then return {ROSSO[2]} end return {CARTA[2]}")}))
    tools += [
        Tool("Colpi0", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("Battuta0"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f":{pre}return (f>=0 and i==0) and 1 or 0")}),
        Tool("Colpi1", "Merge", {"Background": Conn("Colpi0"), "Foreground": Conn("Battuta1"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f":{pre}return i==1 and 1 or 0")}),
        Tool("Colpi2", "Merge", {"Background": Conn("Colpi1"), "Foreground": Conn("Battuta2"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f":{pre}return i==2 and 1 or 0")}),
        Tool("Colpi3", "Merge", {"Background": Conn("Colpi2"), "Foreground": Conn("Battuta3"), "PerformDepthMerge": 0,
                                 "Blend": Expr(f":{pre}return i==3 and 1 or 0")}),
        Tool("Scia", "DirectionalBlur", {"Input": Conn("Colpi3"), "Type": 3, "Center": (0.5, 0.5),
                                         "Length": Expr(f":{pre}local k=(f-i*b)/{F(5)} if f<0 then return 0 end return 0.18*max(1-k,0)")}),
        solid("Lampo", (1, 0.98, 0.94)), grain(),
    ]
    visible = f":{pre}if f<0 then return 0 end local k=(f-i*b) return (i==0 and 1 or 1)*(k>=0 and 1 or 0)"
    layers = ground_layers() + [("Scia", visible), ("Lampo", f":{pre}if f<0 then return 0 end local k=(f-i*b)/{F(3)} return 0.35*max(1-k,0)"),
                                grain_layer()]
    mt, last = stack(layers)
    shake = (f":{pre}local k=(f-i*b) if f<0 then return Point(0.5,0.5) end local a=0.012*max(1-k/{F(9)},0)^2\n"
             "return Point(0.5+a*sin(time*2.7), 0.5+a*cos(time*3.3))")
    m = title("MOV_ImpattoTrailer", tools + mt, c, [texp("Battute", "Battute (una per riga, max 4)")], last)
    m.tools[-1].inputs["Center"] = Expr(shake)
    m.exposed = [e for e in m.exposed if not (e.tool == "Ctrl" and e.source == "Center")]
    return m


# ============================================================== SOTTOPANCIA
def scrim(name, x, y, w, h, alpha=0.6):
    return [ellipse(name + "Mask", x, y, w, h, soft=0.18), solid(name, (0, 0, 0), name + "Mask", alpha=alpha)]


SCRIM_C = {"Scrim": checkbox("Ombra di leggibilità", 1)}


def t_sott_cinema():
    c = {**BASE, **SCRIM_C}
    xo = ex_out(16)
    kn, kr = eo(st(5, 20)), eo(st(10, 20))
    tools = scrim("Ombra", 520, 840, 1500, 520) + [
        rect("BarraMask", 154, f"770+150*{eo(st(0, 12))}*(1-{xo})/2", 8, f"150*{eo(st(0, 12))}*(1-{xo})"),
        solid("Barra", ROSSO, "BarraMask"),
        rect("NomeMask", 1040, 812, 1740, 110),
        text("Nome", "VALENTINO MAZZOLA", ANTON, 76, CARTA, f"184-(1-{kn})*900-{eio(xo)}*900", 812,
             extra={"EffectMask": Conn("NomeMask", "Mask"), **shadow(0.35, 8)}),
        rect("RuoloMask", 1040, 880, 1740, 54),
        text("Ruolo", "CAPITANO DEL GRANDE TORINO · 1942–1949", INTER, 28, CARTA, f"184-(1-{kr})*900-{eio(xo)}*900", 880,
             track=1.35, alpha=0.9, extra={"EffectMask": Conn("RuoloMask", "Mask"), **shadow(0.35, 8)}),
    ]
    layers = [("Ombra", f"Ctrl.Scrim*{eo(st(0, 14))}*(1-{xo})"), ("Barra", None), ("Nome", None), ("Ruolo", None)]
    mt, last = stack(layers)
    return title("MOV_SottopanciaCinema", tools + mt, c,
                 [texp("Nome", "Nome"), texp("Ruolo", "Ruolo"), *color_exposed("Barra", "Colore barra", 1)], last, fade=False)


def t_sott_archivio():
    c = {**BASE, "TagW": slider("Larghezza cartellino (px)", 720, 300, 1400)}
    xo = ex_out(16)
    k = eo(st(0, 16))
    tag = torn_rect_pts(720, 200, amp=3, step=9, seed=21)
    wn = clamp01(f"({T}-{F(12)}*Ctrl.Speed)/max({F(26)}*Ctrl.Speed,1)")
    wr = clamp01(f"({T}-{F(36)}*Ctrl.Speed)/max({F(22)}*Ctrl.Speed,1)")
    tools = [
        poly("TagMask", 520, 830, tag, extra={"Angle": -2, "Size": Expr("Ctrl.TagW/720")}),
        solid("TagOmbraS", (0, 0, 0), "TagMask", alpha=0.55),
        Tool("TagOmbra", "Blur", {"Input": Conn("TagOmbraS"), "XBlurSize": 24}),
        solid("Tag", CARTA, "TagMask"),
        Tool("TagFibra", "FastNoise", {**FRAME, "Detail": 4, "XScale": 7, "Contrast": 0.7, "Color1Red": 0.83,
                                       "Color1Green": 0.77, "Color1Blue": 0.67, "EffectMask": Conn("TagMask", "Mask")}),
        rect("NastroMask", 540, 728, 130, 34, angle=4),
        solid("Nastro", (0.94, 0.91, 0.82), "NastroMask", alpha=0.6),
        rect("ScriviNome", f"180+1300*{wn}/2", 800, f"1300*{wn}", 110),
        text("Nome", "VALENTINO MAZZOLA", MANO, 70, INCHIOSTRO, 200, 800, extra={"EffectMask": Conn("ScriviNome", "Mask")}),
        poly("SottMask", 200 + 180, 840, [(-180 + i * 18, (i % 3 - 1) * 1.2) for i in range(21)], closed=False, stroke=4,
             write=eio(st(30, 10))),
        solid("Sott", ROSSO, "SottMask", alpha=0.9),
        rect("ScriviRuolo", f"180+1300*{wr}/2", 878, f"1300*{wr}", 70),
        text("Ruolo", "CAPITANO DEL GRANDE TORINO", MANO, 38, INCHIOSTRO, 200, 878, extra={"EffectMask": Conn("ScriviRuolo", "Mask")}),
    ]
    layers = [("TagOmbra", 0.9), ("Tag", None), ("TagFibra", 0.4, "Multiply"), ("Nastro", None), ("Nome", None),
              ("Sott", None), ("Ruolo", None)]
    mt, last = stack(layers, prefix="Carta")
    tools += mt
    tools.append(Tool("Cartellino", "Transform", {"Input": Conn(last), "Center": Expr(f"Point(0.5-(1-{k})*0.03-{eio(xo)}*0.04, 0.5-(1-{k})*0.03)"),
                                                  "Angle": Expr(f"-(1-{k})*4"), "Pivot": P(520, 830)}))
    mt2, last2 = stack([("Cartellino", f"{clamp01(f'{st(0, 16)}*3')}*(1-{xo})")], prefix="Fin")
    return title("MOV_SottopanciaArchivio", tools + mt2, c,
                 [texp("Nome", "Nome"), texp("Ruolo", "Ruolo"), Exposed("Nome", "Font", "Font scrittura"),
                  *color_exposed("Sott", "Colore sottolineatura", 1)], last2, fade=False)


def t_sott_minimale():
    c = {**BASE, **SCRIM_C}
    xo = ex_out(16)
    lp = f"{eo(st(2, 22))}*(1-{xo})"
    tools = scrim("Ombra", 520, 860, 1400, 460, 0.5) + [
        rect("LineaMask", f"150+480*{lp}/2", 848, f"480*{lp}", 2), solid("Linea", CARTA, "LineaMask", alpha=0.7),
        rect("CroceH", 150, 848, 20, 2), rect("CroceV", 150, 848, 2, 20, prev="CroceH"), solid("Croce", CARTA, "CroceV"),
        text("Nome", "Valentino Mazzola", INTER_B, 48, CARTA, 150, f"806+(1-{eo(st(6, 18))})*14", extra=shadow(0.4, 8)),
        text("Ruolo", "Capitano del Grande Torino", INTER, 26, CARTA, 150, f"890+(1-{eo(st(14, 18))})*10", alpha=0.72, extra=shadow(0.4, 8)),
    ]
    layers = [("Ombra", f"Ctrl.Scrim*{eo(st(0, 14))}*(1-{xo})"), ("Linea", None), ("Croce", lp),
              ("Nome", f"{eo(st(6, 18))}*(1-{xo})"), ("Ruolo", f"{eo(st(14, 18))}*(1-{xo})")]
    mt, last = stack(layers)
    return title("MOV_SottopanciaMinimale", tools + mt, c, [texp("Nome", "Nome"), texp("Ruolo", "Ruolo")], last, fade=False)


def t_sott_tv():
    c = {**BASE, "BoxW": slider("Larghezza riquadro nome (px)", 760, 200, 1600), "RoleW": slider("Larghezza riquadro ruolo (px)", 640, 200, 1600)}
    xo = ex_out(14)
    a1 = f"{eo(st(0, 14))}*(1-{eio(clamp01(f'{R}/{F(12)}'))*0}+0)"
    a1 = f"({eo(st(0, 14))}*(1-{xo}))"
    a2 = f"({eo(st(5, 14))}*(1-{ex_out(18)}))"
    sk = 0.18 * 92

    def para(w, h, skew):
        return [(-w / 2 + skew / 2, -h / 2), (w / 2 + skew / 2, -h / 2), (w / 2 - skew / 2, h / 2), (-w / 2 - skew / 2, h / 2)]
    tools = [
        poly("BoxNome", 150 + 800, 800, para(1600, 92, sk)),
        rect("SvelaNome", f"150+Ctrl.BoxW*{a1}/2", 800, f"Ctrl.BoxW*{a1}", 100, prev="BoxNome", mode="Minimum"),
        solid("Nome_Box", CARTA, "SvelaNome"),
        poly("BoxRuolo", 168 + 800, 872, para(1600, 50, sk * 0.54)),
        rect("SvelaRuolo", f"168+Ctrl.RoleW*{a2}/2", 872, f"Ctrl.RoleW*{a2}", 60, prev="BoxRuolo", mode="Minimum"),
        solid("Ruolo_Box", ROSSO, "SvelaRuolo"),
        text("Nome", "VALENTINO MAZZOLA", ANTON, 62, INCHIOSTRO, 186, 800, extra={"EffectMask": Conn("SvelaNome", "Mask")}),
        text("Ruolo", "CAPITANO · GRANDE TORINO", INTER_B, 25, CARTA, 196, 872, track=1.3, extra={"EffectMask": Conn("SvelaRuolo", "Mask")}),
    ]
    mt, last = stack([("Nome_Box", None), ("Ruolo_Box", None), ("Nome", None), ("Ruolo", None)])
    return title("MOV_SottopanciaTelevisivo", tools + mt, c,
                 [texp("Nome", "Nome"), texp("Ruolo", "Ruolo"), *color_exposed("Ruolo_Box", "Colore riquadro ruolo", 1),
                  *color_exposed("Nome_Box", "Colore riquadro nome", 2)], last, fade=False)


# ============================================================== LUOGO E DATA
SCR = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#/"


def decode_expr(src, start, per=1.0, spin=8):
    return (":" + UTF8 + f"local t=chars({src}.StyledText.Value or '')\n"
            f"local f=({T})/Ctrl.Speed-{F(start)}\nlocal set='{SCR}'\nlocal o={{}}\n"
            "for i,ch in ipairs(t) do\n"
            f"  local s0=(i-1)*{F(per)}\n"
            "  if ch==' ' or f>=s0+" + F(spin) + " then o[i]=ch\n"
            "  elseif f<s0 then o[i]=' '\n"
            "  else local h=(i*7919+floor(time/2)*104729)%" + str(len(SCR)) + "+1 o[i]=string.sub(set,h,h) end\n"
            "end\nreturn Text(table.concat(o))")


def t_luogo():
    c = {**BASE, **SCRIM_C, "Icon": checkbox("Mirino", 1)}
    xo = ex_out(16)
    X0 = 230
    cp = eo(st(34, 36))
    coord = (":" + f"local s=CoordSrc.StyledText.Value or ''\nlocal k={cp}\n"
             "local o=string.gsub(s,'(%d+)%.(%d+)',function(a,b) local v=tonumber(a..'.'..b) local d=#b return string.format('%.'..d..'f', v*(0.2+0.8*k)) end)\n"
             "return Text(o)")
    tools = scrim("Ombra", 560, 860, 1500, 560, 0.55) + [
        ellipse("AnelloMask", 176, 776, f"44*{eback(st(0, 14))}", f"44*{eback(st(0, 14))}", ring=3),
        rect("MirH", 176, 776, f"64*{eo(st(4, 12))}", 3, prev="AnelloMask"),
        rect("MirV", 176, 776, 3, f"64*{eo(st(4, 12))}", prev="MirH"),
        ellipse("PuntoMask", 176, 776, "10+3*sin(time*0.25)", "10+3*sin(time*0.25)", prev="MirV"),
        solid("Mirino", ROSSO, "PuntoMask"),
        text("LuogoSrc", "SUPERGA, TORINO", ANTON, 84, CARTA, X0, -300),
        text("Luogo", "", ANTON, 84, CARTA, X0, 776, track=1.03, extra={"StyledText": Expr(decode_expr("LuogoSrc", 6)), **shadow(0.4, 10)}),
        rect("FiloMask", f"{X0}+300*{eo(st(12, 20))}/2", 830, f"300*{eo(st(12, 20))}", 4), solid("Filo", ROSSO, "FiloMask"),
        text("Dettaglio", "Basilica di Superga · 669 m s.l.m.", INTER, 30, CARTA, X0, 870, alpha=0.88, extra=shadow(0.4, 8)),
        text("DataSrc", "4 MAGGIO 1949 — ORE 17:03", INTER, 26, CARTA, X0, -300),
        text("Data", "", INTER_B, 26, CARTA, X0, 918, track=1.45, extra={"StyledText": Expr(decode_expr("DataSrc", 28, 0.75, 6)), **shadow(0.4, 8)}),
        text("CoordSrc", "45.0803° N   7.7672° E", VIDEO, 34, CARTA, X0, -300),
        text("Coord", "", VIDEO, 36, CARTA, X0, 962, track=1.1, alpha=0.75, extra={"StyledText": Expr(coord), **shadow(0.4, 6)}),
    ]
    layers = [("Ombra", f"Ctrl.Scrim*{eo(st(0, 14))}"), ("Mirino", "Ctrl.Icon"), ("Luogo", None), ("Filo", None),
              ("Dettaglio", eo(st(22, 16))), ("Data", None), ("Coord", clamp01(f"{st(34, 6)}"))]
    mt, last = stack(layers)
    return title("MOV_LuogoData", tools + mt, c,
                 [texp("LuogoSrc", "Luogo"), texp("Dettaglio", "Dettaglio"), texp("DataSrc", "Data e ora"),
                  texp("CoordSrc", "Coordinate"), *color_exposed("Filo", "Colore accento", 1)], last)
