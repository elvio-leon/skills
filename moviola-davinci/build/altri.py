"""Titoli dati, transizioni ed effetti Moviola."""
from __future__ import annotations

from base import *  # noqa: F401,F403
from base import BASE, BG_OPTS, GLIDE, OUT  # noqa: F401
from titoli import ex_out, scrim, SCRIM_C

PROG = "Ctrl.Mix"


# ============================================================== NUMERO GIGANTE
def t_numero():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "CountDur": slider("Durata conteggio (fotogrammi)", 55, 5, 250, integer=True),
         "Grain": slider("Grana pellicola", 0.3, 0, 1)}
    xo = ex_out(18)
    k = f"min(max(({T}-{F(6)}*Ctrl.Speed)/max(Ctrl.CountDur*Ctrl.Speed,1),0),1)"
    num = (":" + lua_split() + f"local s=NumeroSrc.StyledText.Value or '0'\nlocal v=num(s)\nlocal k={k}\nk=1-(1-k)^5\n"
           "return Text((Prefisso.StyledText.Value or '')..fmt(v*k,dec(s))..(Suffisso.StyledText.Value or ''))")
    lp = eo(st(60, 22))
    tools = ground_tools() + [
        text("NumeroSrc", "1.257", ANTON, 10, CARTA, 960, -400), text("Prefisso", "", ANTON, 10, CARTA, 960, -400),
        text("Suffisso", "", ANTON, 10, CARTA, 960, -400),
        text("Numero", "", ANTON, 380, CARTA, 960, 430, align=0, extra={"StyledText": Expr(num)}),
        rect("FiloMask", 960, 655, f"320*{lp}", 6), solid("Filo", ROSSO, "FiloMask"),
        text("Etichetta", "GIORNI SENZA SCONFITTE IN CASA", INTER_B, 44, CARTA, 960, f"725+(1-{eo(st(62, 18))})*12", align=0, track=1.25),
        text("Nota", "Stadio Filadelfia, 17 gennaio 1943 – 30 aprile 1949", INTER, 28, CARTA, 960, 785, align=0, alpha=0.7),
        grain(),
    ]
    layers = ground_layers() + [("Numero", f"{clamp01(f'{st(0, 6)}')}*(1-{xo})"), ("Filo", f"1-{xo}"),
                                ("Etichetta", f"{eo(st(62, 18))}*(1-{xo})"), ("Nota", f"{eo(st(74, 20))}*(1-{xo})"), grain_layer()]
    mt, last = stack(layers)
    return title("MOV_NumeroGigante", tools + mt, c,
                 [texp("NumeroSrc", "Numero (es. 1.257 o 0,61)"), texp("Prefisso", "Prefisso"), texp("Suffisso", "Suffisso"),
                  texp("Etichetta", "Etichetta"), texp("Nota", "Nota"), *color_exposed("Filo", "Colore accento", 1)],
                 last, size=f"1+0.03*{GLIDE}")


# ============================================================== TABELLINO
def t_tabellino():
    c = {**BASE, "Step": slider("Fotogrammi tra un gol e l'altro", 15, 3, 75, integer=True),
         "First": slider("Primo gol al fotogramma", 45, 0, 300, integer=True), "Paper": checkbox("Stile cartoncino d'archivio", 0)}
    xo = ex_out(16)
    goals = (f"local function parse(fld,team,G) local s=fld.StyledText.Value or '' for l0 in string.gmatch(s..'\\n','([^\\n]*)\\n') do local l=string.gsub(l0,'^%s+','') if l~='' then local m=tonumber(string.match(l,'(%d+)')) or 0 table.insert(G,{{m=m,t=team,s=l}}) end end end\n"
             "local G={} parse(MarcCasa,1,G) parse(MarcOspiti,2,G)\n"
             "table.sort(G,function(a,b) return a.m<b.m end)\n"
             f"local f=({T})-Ctrl.First*Ctrl.Speed\nlocal shown=(f<0) and 0 or (floor(f/(Ctrl.Step*Ctrl.Speed))+1)\nif shown>#G then shown=#G end\n")
    score = ":" + goals + "local a,b=0,0 for i=1,shown do if G[i].t==1 then a=a+1 else b=b+1 end end return Text(a..' – '..b)"

    def lst(team):
        return ":" + goals + f"local o={{}} for i=1,shown do if G[i].t=={team} then table.insert(o,G[i].s) end end return Text(table.concat(o,'\\n'))"
    bump = ":" + goals + f"if shown<1 then return 190/{W} end local d=f-(shown-1)*Ctrl.Step*Ctrl.Speed return 190/{W}*(1+0.25*max(1-d/{F(8)},0))"
    k = eo(st(0, 16))
    paper = torn_rect_pts(1500, 600, amp=3, step=10, seed=31)
    shield = [(-46, -54), (46, -54), (46, 10), (30, 40), (0, 64), (-30, 40), (-46, 10)]
    tools = [
        rect("PannelloMask", f"210+1500*{k}/2", 550, f"1500*{k}", 600),
        solid("Pannello", VERDE_SCURO, "PannelloMask", alpha=0.92),
        rect("FiloMask", f"210+1500*{eo(st(4, 18))}/2", 252, f"1500*{eo(st(4, 18))}", 6), solid("Filo", ROSSO, "FiloMask"),
        poly("CartaMask", 960, 550, paper, extra={"Angle": -0.7}), solid("CartaS", CARTA, "CartaMask"),
        Tool("CartaFibra", "FastNoise", {**FRAME, "Detail": 4, "XScale": 7, "Contrast": 0.7, "Color1Red": 0.83, "Color1Green": 0.77,
                                         "Color1Blue": 0.67, "EffectMask": Conn("CartaMask", "Mask")}),
        text("Info", "SERIE A 1945/46 · STADIO FILADELFIA", INTER_B, 24, CARTA, 960, 316, align=0, track=1.4, alpha=0.8),
        poly("StemmaCasaMask", 360, 460, shield), solid("StemmaCasa", (0.48, 0.12, 0.17), "StemmaCasaMask"),
        poly("StemmaOspMask", 1560, 460, shield), solid("StemmaOsp", (0.78, 0.47, 0.17), "StemmaOspMask"),
        text("Casa", "TORINO", ANTON, 88, CARTA, 450, 470), text("Ospiti", "ROMA", ANTON, 88, CARTA, 1470, 470, align=1),
        text("IniCasa", "", ANTON, 60, CARTA, 360, 462, align=0, extra={"StyledText": Expr("Text(string.sub(Casa.StyledText.Value or '',1,1))")}),
        text("IniOsp", "", ANTON, 60, CARTA, 1560, 462, align=0, extra={"StyledText": Expr("Text(string.sub(Ospiti.StyledText.Value or '',1,1))")}),
        text("Punteggio", "", ANTON, 190, CARTA, 960, 470, align=0, extra={"StyledText": Expr(score), "Size": Expr(bump)}),
        rect("SepMask", 960, 572, 1340, 2), solid("Sep", CARTA, "SepMask", alpha=0.25),
        text("MarcCasa", "Gabetto 3'\nMazzola 15'\nOssola 32'\nLoik 51'\nMazzola 63'\nGabetto 70'", INTER, 30, CARTA, 300, -500),
        text("MarcOspiti", "Amadei 40'", INTER, 30, CARTA, 300, -500),
        text("ListaCasa", "", INTER, 30, CARTA, 300, 700, extra={"StyledText": Expr(lst(1)), "LineSpacing": 1.05}),
        text("ListaOsp", "", INTER, 30, CARTA, 1620, 700, align=1, extra={"StyledText": Expr(lst(2)), "LineSpacing": 1.05}),
    ]
    for n in ("Info", "Casa", "Ospiti", "Punteggio", "ListaCasa", "ListaOsp"):
        t = next(x for x in tools if x.name == n)
        for i, ch in enumerate(("Red1", "Green1", "Blue1")):
            t.inputs[ch] = Expr(f"Ctrl.Paper>0.5 and {INCHIOSTRO[i]} or {CARTA[i]}")
    layers = [("Pannello", "1-Ctrl.Paper"), ("Filo", "1-Ctrl.Paper"), ("CartaS", f"Ctrl.Paper*{k}"), ("CartaFibra", "Ctrl.Paper*0.4", "Multiply"),
              ("Info", eo(st(10, 16))), ("StemmaCasa", eo(st(12, 14))), ("StemmaOsp", eo(st(14, 14))), ("IniCasa", eo(st(12, 14))),
              ("IniOsp", eo(st(14, 14))), ("Casa", eo(st(16, 16))), ("Ospiti", eo(st(18, 16))), ("Punteggio", eo(st(20, 16))),
              ("Sep", eo(st(20, 16))), ("ListaCasa", None), ("ListaOsp", None)]
    mt, last = stack(layers)
    return title("MOV_Tabellino", tools + mt, c,
                 [texp("Casa", "Squadra di casa"), texp("Ospiti", "Squadra ospite"), texp("Info", "Competizione e stadio"),
                  texp("MarcCasa", "Marcatori casa (uno per riga, con minuto)"), texp("MarcOspiti", "Marcatori ospiti"),
                  *color_exposed("StemmaCasa", "Colore casa", 1), *color_exposed("StemmaOsp", "Colore ospiti", 2)], last)


# ============================================================== CLASSIFICA
def t_classifica():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "Hi": slider("Riga in evidenza (0 = nessuna)", 1, 0, 8, integer=True),
         "Grain": slider("Grana pellicola", 0.25, 0, 1)}
    xo = ex_out(16)
    X, Wd, top, rh = 420, 1080, 330, 86
    hk = eo(st(50, 18))
    tools = ground_tools() + [
        text("Righe", "Torino|65\nMilan|49\nJuventus|49\nTriestina|49\nAtalanta|48\nModena|48", INTER, 10, CARTA, 0, -400),
        text("Titolo", "SERIE A 1947/48", ANTON, 92, CARTA, X, f"210+(1-{eo(st(0, 18))})*90", extra={"EffectMask": Conn("TitMask", "Mask")}),
        rect("TitMask", 960, 210, 1920, 112),
        text("Nota", "Classifica finale · 2 punti a vittoria", INTER, 26, CARTA, X + Wd, 228, align=1, alpha=0.7),
        rect("FiloMask", f"{X}+{Wd}*{eo(st(6, 20))}/2", 262, f"{Wd}*{eo(st(6, 20))}", 4), solid("Filo", ROSSO, "FiloMask"),
    ]
    layers = ground_layers() + [("Titolo", None), ("Nota", eo(st(10, 14))), ("Filo", None)]
    for r in range(8):
        y = top + r * rh + rh / 2
        kk = eo(st(16 + r * 3, 18))
        get = ":" + lua_lines("Righe") + lua_split() + f"local a=split(L[{r + 1}] or '') "
        hi = f"(Ctrl.Hi=={r + 1})"
        dim = f"((Ctrl.Hi>0 and not {hi}) and (1-0.45*{hk}) or 1)"
        on = f"({hk}>0.5 and {hi})"
        col = lambda i, base: Expr(f"({on}) and {CARTA[i]} or {base[i]}")  # noqa: E731
        tools += [
            rect(f"Evid{r}Mask", f"{X - 20}+({Wd + 40})*{hk}/2", y, f"({Wd + 40})*{hk}", rh - 10), solid(f"Evid{r}", ROSSO, f"Evid{r}Mask"),
            rect(f"Riga{r}Mask", X + Wd / 2, y + rh / 2 - 2, Wd, 1), solid(f"Linea{r}", CARTA, f"Riga{r}Mask", alpha=0.14),
            text(f"Pos{r}", "", ANTON, 46, CARTA, f"{X + 10}+(1-{kk})*260", y,
                 extra={"StyledText": Expr(get + f"if (L[{r + 1}] or '')=='' then return Text('') end return Text(string.format('%02d',{r + 1}))"),
                        "Red1": col(0, CARTA), "Green1": col(1, CARTA), "Blue1": col(2, CARTA), "Alpha1": Expr(f"({on}) and 1 or 0.6")}),
            text(f"Squadra{r}", "", INTER_B, 32, CARTA, f"{X + 120}+(1-{kk})*260", y, track=1.12,
                 extra={"StyledText": Expr(get + "return Text(string.upper(a[1] or ''))")}),
            text(f"Punti{r}", "", ANTON, 46, CARTA, f"{X + Wd - 10}+(1-{kk})*260", y, align=1,
                 extra={"StyledText": Expr(get + "return Text(a[2] or '')")}),
        ]
        ex_ = ":" + lua_lines("Righe") + f"return ((L[{r + 1}] or '')~='') and 1 or 0"
        tools.append(Tool(f"Esiste{r}", "Transform", {"Size": Expr(ex_)}))
        layers += [(f"Evid{r}", f"{hi} and Esiste{r}.Size or 0"), (f"Linea{r}", f"{kk}*Esiste{r}.Size*((Ctrl.Hi=={r + 1}) and 0 or 1)"),
                   (f"Pos{r}", f"{kk}*{dim}"), (f"Squadra{r}", f"{kk}*{dim}"), (f"Punti{r}", f"{kk}*{dim}")]
    layers.append(grain_layer())
    tools.append(grain())
    mt, last = stack(layers)
    return title("MOV_Classifica", tools + mt, c,
                 [texp("Titolo", "Titolo"), texp("Nota", "Nota"), texp("Righe", "Righe (Squadra|punti, max 8)"),
                  *color_exposed("Filo", "Colore accento", 1)], last)


# ============================================================== TESTA A TESTA
def t_confronto():
    c = {**BASE, "Bg": combo("Sfondo", BG_OPTS, 1), "Grain": slider("Grana pellicola", 0.25, 0, 1)}
    hk = eo(st(4, 20))
    tools = ground_tools() + [
        text("Righe", "Presenze in A|195|239\nGol in A|118|197\nScudetti|5|3\nMedia gol|0,61|0,82", INTER, 10, CARTA, 0, -400),
        rect("SxMask", 480, 220, 920, 150), rect("DxMask", 1440, 220, 920, 150),
        text("Nome1", "VALENTINO MAZZOLA", ANTON, 84, ROSSO, f"880-(1-{hk})*200", 215, align=1, extra={"EffectMask": Conn("SxMask", "Mask")}),
        text("Nome2", "GIUSEPPE MEAZZA", ANTON, 84, CARTA, f"1040+(1-{hk})*200", 215, extra={"EffectMask": Conn("DxMask", "Mask")}),
        text("VS", "VS", ANTON, 40, CARTA, 960, 215, align=0, alpha=0.5),
        text("Sotto1", "Torino 1942–49", INTER, 26, CARTA, 880, 280, align=1, alpha=0.7),
        text("Sotto2", "Inter 1927–40", INTER, 26, CARTA, 1040, 280, alpha=0.7),
    ]
    layers = ground_layers() + [("Nome1", None), ("Nome2", None), ("VS", eo(st(10, 14))), ("Sotto1", eo(st(12, 14))), ("Sotto2", eo(st(12, 14)))]
    top, rh, maxL = 380, 150, 720
    for r in range(5):
        y = top + r * rh
        g = f"min(max(({T}-{F(24 + r * 9)}*Ctrl.Speed)/max({F(30)}*Ctrl.Speed,1),0),1)"
        pre = ":" + lua_lines("Righe") + lua_split() + f"local a=split(L[{r + 1}] or '') local va,vb=num(a[2]),num(a[3]) local mx=math.max(va,vb,1e-9) local k={g} k=1-(1-k)^3\n"
        la = f"{pre}return {maxL}*va/mx*k"
        lb = f"{pre}return {maxL}*vb/mx*k"
        tools += [
            text(f"Lab{r}", "", INTER_B, 24, CARTA, 960, y, align=0, track=1.35, alpha=0.75,
                 extra={"StyledText": Expr(pre + "return Text(string.upper(a[1] or ''))")}),
            rect(f"Trk{r}A", 960 - 10 - maxL / 2, y + 36, maxL, 26), rect(f"Trk{r}B", 960 + 10 + maxL / 2, y + 36, maxL, 26, prev=f"Trk{r}A"),
            solid(f"Binario{r}", CARTA, f"Trk{r}B", alpha=0.08),
            rect(f"BarA{r}Mask", f"950-({la[1:] if False else 'BarA' + str(r) + 'Len.Value'})/2", y + 36, f"BarA{r}Len.Value", 26),
        ]
        # le lunghezze vivono su due nodi di appoggio per non ripetere il calcolo
        tools.pop()
        tools += [
            Tool(f"LenA{r}", "Transform", {"Size": Expr(la)}), Tool(f"LenB{r}", "Transform", {"Size": Expr(lb)}),
            rect(f"BarA{r}Mask", f"950-LenA{r}.Size/2", y + 36, f"LenA{r}.Size", 26),
            rect(f"BarB{r}Mask", f"970+LenB{r}.Size/2", y + 36, f"LenB{r}.Size", 26),
            Tool(f"BarA{r}", "Background", {**FRAME, "TopLeftAlpha": 1, "EffectMask": Conn(f"BarA{r}Mask", "Mask"),
                                            "TopLeftRed": Expr(f"{pre}return va>=vb and Colore.TopLeftRed or 0.55"),
                                            "TopLeftGreen": Expr(f"{pre}return va>=vb and Colore.TopLeftGreen or 0.55"),
                                            "TopLeftBlue": Expr(f"{pre}return va>=vb and Colore.TopLeftBlue or 0.53")}),
            Tool(f"BarB{r}", "Background", {**FRAME, "TopLeftAlpha": 1, "EffectMask": Conn(f"BarB{r}Mask", "Mask"),
                                            "TopLeftRed": Expr(f"{pre}return vb>=va and {CARTA[0]} or 0.45"),
                                            "TopLeftGreen": Expr(f"{pre}return vb>=va and {CARTA[1]} or 0.47"),
                                            "TopLeftBlue": Expr(f"{pre}return vb>=va and {CARTA[2]} or 0.46")}),
            text(f"ValA{r}", "", ANTON, 52, CARTA, f"936-LenA{r}.Size", y + 36, align=1,
                 extra={"StyledText": Expr(pre + "return Text(fmt(va*k,dec(a[2])))")}),
            text(f"ValB{r}", "", ANTON, 52, CARTA, f"984+LenB{r}.Size", y + 36,
                 extra={"StyledText": Expr(pre + "return Text(fmt(vb*k,dec(a[3])))")}),
        ]
        vis = f"{pre}return ((L[{r + 1}] or '')~='') and 1 or 0"
        layers += [(f"Lab{r}", vis), (f"Binario{r}", vis), (f"BarA{r}", vis), (f"BarB{r}", vis), (f"ValA{r}", vis), (f"ValB{r}", vis)]
    tools.append(solid("Colore", ROSSO, alpha=0))
    tools.append(grain())
    layers.append(grain_layer())
    mt, last = stack(layers)
    return title("MOV_TestaATesta", tools + mt, c,
                 [texp("Nome1", "Lato sinistro"), texp("Sotto1", "Sottotitolo sinistro"), texp("Nome2", "Lato destro"),
                  texp("Sotto2", "Sottotitolo destro"), texp("Righe", "Righe (Statistica|sinistra|destra, max 5)"),
                  *color_exposed("Colore", "Colore lato sinistro", 1)], last)


# ============================================================== CORNICE D'ARCHIVIO / MIRINO (titoli sovrapposti)
def t_cornice():
    c = {**BASE, "Bars": checkbox("Bande cinema 2,39:1", 0)}
    bh = (1080 - 1920 / 2.39) / 2
    fr, fl = reg_frame("Cornice", 60, 60, 1860, 1020, eo(st(0, 30)), alpha=0.55)
    bk = eo(st(0, 24))
    tools = fr + [
        rect("BandaSu", 960, f"{bh}*{bk}/2", 1920, f"{bh}*{bk}"), rect("BandaGiu", 960, f"1080-{bh}*{bk}/2", 1920, f"{bh}*{bk}", prev="BandaSu"),
        solid("Bande", (0, 0, 0), "BandaGiu"),
        rect("QuadMask", 107, f"Ctrl.Bars>0.5 and {bh + 52} or 108", 14, 14), solid("Quad", ROSSO, "QuadMask"),
        text("Etichetta", "MATERIALE D'ARCHIVIO", INTER_B, 22, CARTA, 128, f"Ctrl.Bars>0.5 and {bh + 52} or 108", track=1.55, extra=shadow(0.5, 8)),
        text("Fonte", "Fonte: Archivio Storico Luce", INTER, 22, CARTA, 1820, f"Ctrl.Bars>0.5 and {1080 - bh - 40} or 990", align=1, alpha=0.85, extra=shadow(0.5, 8)),
        text("Anno", "1949", ANTON, 72, CARTA, 1820, f"Ctrl.Bars>0.5 and {bh + 80} or 140", align=1, alpha=0.9, extra=shadow(0.5, 8)),
    ]
    layers = [("Bande", "Ctrl.Bars")] + [(fl[0][0], fl[0][1]), (fl[1][0], fl[1][1])] + [
        ("Quad", eo(st(12, 14))), ("Etichetta", eo(st(12, 14))), ("Fonte", eo(st(16, 14))), ("Anno", eo(st(16, 14)))]
    mt, last = stack(layers)
    return title("MOV_CorniceArchivio", tools + mt, c,
                 [texp("Etichetta", "Etichetta"), texp("Fonte", "Fonte"), texp("Anno", "Anno (vuoto = nessuno)"),
                  *color_exposed("Quad", "Colore accento", 1)], last)


def t_mirino():
    c = {**BASE, "TCStart": slider("Timecode iniziale (secondi)", 872, 0, 86000, integer=True), "Fps": slider("Fotogrammi al secondo del timecode", 25, 24, 60, integer=True)}
    tools, prev = [], None
    m, L = 90, 90
    for i, (x, y, sx, sy) in enumerate(((m, m, 1, 1), (1920 - m, m, -1, 1), (m, 1080 - m, 1, -1), (1920 - m, 1080 - m, -1, -1))):
        tools.append(rect(f"AH{i}", x + sx * L / 2, y, L, 4, prev=prev))
        tools.append(rect(f"AV{i}", x, y + sy * L / 2, 4, L, prev=f"AH{i}"))
        prev = f"AV{i}"
    fk = eback(st(4, 16))
    sz = f"(260-100*{fk})"
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        tools.append(rect(f"FH{i}", f"960+({sx})*({sz}/2-13)", f"540+({sy})*{sz}/2", 26, 3, prev=prev))
        tools.append(rect(f"FV{i}", f"960+({sx})*{sz}/2", f"540+({sy})*({sz}/2-13)", 3, 26, prev=f"FH{i}"))
        prev = f"FV{i}"
    tools += [rect("CH", 960, 540, 24, 2, prev=prev), rect("CV", 960, 540, 2, 24, prev="CH"),
              rect("Batt", 166, 974, 70, 32, extra={"Solid": 0, "BorderWidth": 0.0016}, prev="CV"),
              rect("BattIn", 160, 974, 44, 20, prev="Batt"), rect("BattPolo", 205, 974, 6, 12, prev="BattIn"),
              solid("Linee", CARTA, "BattPolo"),
              ellipse("RecMask", 160, 164, 30, 30), solid("Rec", ROSSO, "RecMask"),
              text("RecTxt", "REC", INTER_B, 42, CARTA, 190, 164, extra=shadow(0.5, 6)),
              text("TC", "", VIDEO, 44, CARTA, 1800, 164, align=1, extra={"StyledText": Expr(
                  f":local fr=Ctrl.TCStart*Ctrl.Fps+floor({T}*Ctrl.Fps/{F(25)})\nlocal f=fr%Ctrl.Fps local s=floor(fr/Ctrl.Fps)\n"
                  "return Text(string.format('TC %02d:%02d:%02d:%02d',floor(s/3600)%24,floor(s/60)%60,s%60,f))"), **shadow(0.5, 6)}),
              text("Info", "ISO 800   1/50   F2.8   4K 25P", INTER, 30, CARTA, 960, 950, align=0, track=1.15, extra=shadow(0.5, 6))]
    mt, last = stack([("Linee", None), ("Rec", f"floor({T}/{F(16)})%2==0 and 1 or 0"), ("RecTxt", None), ("TC", None), ("Info", None)])
    return title("MOV_MirinoREC", tools + mt, c, [texp("Info", "Parametri"), texp("RecTxt", "Scritta REC")], last)


# ============================================================== TRANSIZIONI
def progress(controls):
    return [Tool("Ctrl", "Dissolve", {"Mix": Conn("CtrlCurve", "Value"), **ctrl_values(controls)}, controls=controls),
            *anim_curves("CtrlCurve")]


def cut(width=0.04, at=0.5):
    return Expr(clamp01(f"({PROG}-{at}+{width / 2})/{width}"))


def transition(name, tools, out, c, extra_exposed=None, a=("Taglio", "Background"), b=("Taglio", "Foreground")):
    return Macro(name, tools + progress(c), out, [Exposed("Ctrl", k) for k in c] + (extra_exposed or []),
                 [(a[0], a[1], "Clip in uscita"), (b[0], b[1], "Clip in entrata")])


def tr_pellicola():
    c = {"Heat": slider("Intensità", 1, 0.3, 1.5)}
    p = f"(({PROG})<0.5 and ({PROG}*2)^2 or 1-(({PROG}-0.5)*2)^0.55)"
    th = f"(1.25-{p}*1.55)"
    tools = [
        Tool("Taglio", "Dissolve", {"Mix": cut(0.06)}),
        Tool("Campo", "FastNoise", {**FRAME, "Detail": 5, "XScale": 2.2, "Contrast": 1.3, "SeetheRate": 0.25}),
        rect("Lato", 1920, 540, 2600, 2400, soft=0.45),
        Tool("Fiamma", "Merge", {"Background": Conn("Campo"), "Foreground": Conn("LatoSolido"), "ApplyMode": FuID("Screen"), "PerformDepthMerge": 0,
                                 "Blend": 0.55}),
        solid("LatoSolido", (1, 1, 1), "Lato"),
        Tool("Bianco", "BitmapMask", {"Image": Conn("Fiamma"), "Channel": FuID("Luminance"), "Low": Expr(f"{th}+0.16"), "High": Expr(f"{th}+0.26")}),
        Tool("Arancio", "BitmapMask", {"Image": Conn("Fiamma"), "Channel": FuID("Luminance"), "Low": Expr(f"{th}+0.03"), "High": Expr(f"{th}+0.13")}),
        Tool("Rosso", "BitmapMask", {"Image": Conn("Fiamma"), "Channel": FuID("Luminance"), "Low": Expr(f"{th}-0.08"), "High": Expr(f"{th}+0.02")}),
        solid("StratoRosso", (0.75, 0.2, 0.04), "Rosso"), solid("StratoArancio", (1, 0.6, 0.15), "Arancio"), solid("StratoBianco", (1, 0.97, 0.88), "Bianco"),
        Tool("M1", "Merge", {"Background": Conn("Taglio"), "Foreground": Conn("StratoRosso"), "PerformDepthMerge": 0, "Blend": Expr("Ctrl.Heat*0.9")}),
        Tool("M2", "Merge", {"Background": Conn("M1"), "Foreground": Conn("StratoArancio"), "PerformDepthMerge": 0, "Blend": Expr("min(Ctrl.Heat,1)")}),
        Tool("M3", "Merge", {"Background": Conn("M2"), "Foreground": Conn("StratoBianco"), "PerformDepthMerge": 0}),
        Tool("Bagliore", "Blur", {"Input": Conn("M3"), "XBlurSize": 4}),
    ]
    return transition("MOV_BruciaturaPellicola", tools, "Bagliore", c)


def tr_carta():
    c = {"Tint": combo("Carta", ["Avorio", "Giornale", "Kraft"], 0)}
    e1 = eio(clamp01(f"{PROG}*2.1"))
    e2 = ei(clamp01(f"({PROG}-0.5)*2"))
    edge = [(0, y) for y in range(-620, 640, 40)]
    import random as _r
    rr = _r.Random(5)
    vt = [((rr.random() - 0.5) * 34 + 14 * __import__('math').sin(y * 0.01), y) for _, y in edge]
    vpts = vt + [(2600, 640), (2600, -620)]
    ht = tear_line_pts(-1100, 1100, amp=30, seed=9)
    top = ht + [(1100, -900), (-1100, -900)]
    bot = ht + [(1100, 900), (-1100, 900)]
    tint = "({0} and {1} or ({2} and {3} or {4}))"
    tools = [
        Tool("Taglio", "Dissolve", {"Mix": cut(0.02)}),
        poly("FoglioMask", f"2000-2060*{e1}", 540, vpts),
        poly("SopraMask", f"960-{e2}*120", f"540-{e2}*900", top, extra={"Angle": Expr(f"{e2}*7")}),
        poly("SottoMask", f"960+{e2}*140", f"540+{e2}*930", bot, extra={"Angle": Expr(f"-{e2}*6")}),
        poly("FibraSopra", f"960-{e2}*120", f"540-{e2}*900", ht, closed=False, stroke=9, extra={"Angle": Expr(f"{e2}*7")}),
        poly("FibraSotto", f"960+{e2}*140", f"540+{e2}*930", ht, closed=False, stroke=9, prev="FibraSopra", extra={"Angle": Expr(f"-{e2}*6")}),
    ]
    for nm, mk in (("Foglio", "FoglioMask"), ("Sopra", "SopraMask"), ("Sotto", "SottoMask")):
        tools.append(Tool(nm, "Background", {**FRAME, "TopLeftAlpha": 1, "EffectMask": Conn(mk, "Mask"),
                                             "TopLeftRed": Expr("Ctrl.Tint==2 and 0.77 or (Ctrl.Tint==1 and 0.9 or 0.961)"),
                                             "TopLeftGreen": Expr("Ctrl.Tint==2 and 0.63 or (Ctrl.Tint==1 and 0.86 or 0.937)"),
                                             "TopLeftBlue": Expr("Ctrl.Tint==2 and 0.44 or (Ctrl.Tint==1 and 0.78 or 0.902)")}))
        tools.append(solid(nm + "OmbraS", (0, 0, 0), mk, alpha=0.6))
        tools.append(Tool(nm + "Ombra", "Blur", {"Input": Conn(nm + "OmbraS"), "XBlurSize": 30}))
    tools += [solid("Fibre", (1, 1, 0.99), "FibraSotto"),
              Tool("Grana", "FastNoise", {**FRAME, "Detail": 4, "XScale": 7, "Contrast": 0.7, "Color1Red": 0.83, "Color1Green": 0.77, "Color1Blue": 0.67})]
    first = f"({PROG}<0.5 and 1 or 0)"
    second = f"({PROG}>=0.5 and 1 or 0)"
    layers = [("FoglioOmbra", first), ("Foglio", first), ("SopraOmbra", second), ("SottoOmbra", second), ("Sopra", second), ("Sotto", second),
              ("Fibre", second)]
    mt, last = stack(layers, base="Taglio", prefix="S")
    return transition("MOV_StrappoDiCarta", tools + mt, last, c)


def tr_luce():
    c = {"Amount": slider("Intensità", 0.9, 0.2, 1.5), "Tint": combo("Tinta", ["Ambra", "Rosso", "Freddo"], 0)}
    pk = f"(1-abs(2*{PROG}-1))"
    cols = {0: [(1, 0.67, 0.24), (1, 0.35, 0.12), (1, 0.9, 0.67)], 1: [(1, 0.27, 0.2), (0.75, 0.12, 0.16), (1, 0.7, 0.55)], 2: [(0.47, 0.75, 1), (0.31, 0.47, 1), (0.86, 0.94, 1)]}
    tools = [Tool("Taglio", "Dissolve", {"Mix": cut(0.12)})]
    layers = []
    import random as _r
    rr = _r.Random(5)
    for i in range(5):
        x0, y0, sz = rr.random() * 0.4 - 0.3, 0.2 + rr.random() * 0.6, 900 + rr.random() * 900
        sp = 1.2 + rr.random() * 0.8
        tools.append(ellipse(f"Bolla{i}Mask", f"(-600+{sp}*2700*{PROG}+{x0}*1000)", y0 * 1080, sz, sz * 0.8, soft=0.35))
        tools.append(Tool(f"Bolla{i}", "Background", {**FRAME, "TopLeftAlpha": 1, "EffectMask": Conn(f"Bolla{i}Mask", "Mask"),
                                                      **{f"TopLeft{ch}": Expr(f"Ctrl.Tint==0 and {cols[0][i % 3][j]} or (Ctrl.Tint==1 and {cols[1][i % 3][j]} or {cols[2][i % 3][j]})")
                                                         for j, ch in enumerate(("Red", "Green", "Blue"))}}))
        layers.append((f"Bolla{i}", f"0.6*Ctrl.Amount*{pk}", "Screen"))
    tools.append(solid("Picco", (1, 0.96, 0.88)))
    layers.append(("Picco", f"Ctrl.Amount*0.85*max(1-abs({PROG}-0.5)/0.09,0)", "Screen"))
    mt, last = stack(layers, base="Taglio", prefix="S")
    return transition("MOV_LuceCalda", tools + mt, last, c)


def tr_flash():
    c = {"Peak": slider("Intensità", 1, 0, 1), "Smoke": checkbox("Fumo del magnesio", 1)}
    f = f"({PROG}<0.08 and ({PROG}/0.08)^2 or (1-({PROG}-0.08)/0.92)^3)"
    tools = [Tool("Taglio", "Dissolve", {"Mix": cut(0.02, 0.08)}), solid("Bianco", (1, 1, 1)),
             ellipse("CaldoMask", 1060, 450, 2400, 1800, soft=0.3), solid("Caldo", (1, 0.86, 0.63), "CaldoMask"),
             Tool("Fumo", "FastNoise", {**FRAME, "Detail": 3, "XScale": 2.5, "Contrast": 1.1, "SeetheRate": 0.6,
                                        "Center": Expr(f"Point(0.5, 0.5+{PROG}*0.25)")})]
    mt, last = stack([("Bianco", f"Ctrl.Peak*({f})^1.6"), ("Caldo", f"Ctrl.Peak*0.5*{f}", "Screen"),
                      ("Fumo", f"Ctrl.Smoke*0.25*min({PROG}*8,1)*(1-{PROG})", "Screen")], base="Taglio", prefix="S")
    return transition("MOV_FlashMagnesio", tools + mt, last, c)


def tr_barre():
    c = {"Pal": combo("Colori", ["Canale", "Granata", "Azzurro", "Bianco e nero"], 0)}
    pals = [[CARTA, ROSSO, INCHIOSTRO, VERDE], [CARTA, (0.71, 0.23, 0.23), (0.36, 0.08, 0.13), (0.23, 0.05, 0.09)],
            [(1, 1, 1), (0.23, 0.48, 0.84), (0.12, 0.25, 0.55), (0.05, 0.12, 0.27)], [(1, 1, 1), (0.54, 0.54, 0.54), (0.16, 0.16, 0.16), (0.04, 0.04, 0.04)]]
    sk = 390
    tools = [Tool("Taglio", "Dissolve", {"Mix": cut(0.02)})]
    layers = []
    for i in range(4):
        a = eio(clamp01(f"({PROG}-{i * 0.05})/(0.5-{(3 - i) * 0.025}-{i * 0.05})"))
        b = eio(clamp01(f"({PROG}-0.5-{i * 0.04})/(0.5-{(3 - i) * 0.02}-{i * 0.04})"))
        x0 = f"(-{sk}-40+({1920 + 2 * sk})*{b})"
        x1 = f"(-{sk}-40+({1920 + 2 * sk + 40})*{a})"
        w = f"max({x1}-{x0},0)"
        tools.append(poly(f"Barra{i}Mask", 960, 540, [(-sk / 2 - 10, -560), (sk / 2 + 10, -560), (-sk / 2 + 10, 560), (-sk / 2 - 30, 560)], extra={"Size": 0}))
        tools.pop()
        tools.append(rect(f"Barra{i}Mask", f"({x0}+{x1})/2", 540, w, 1400, angle=-20))
        tools.append(Tool(f"Barra{i}", "Background", {**FRAME, "TopLeftAlpha": 1, "EffectMask": Conn(f"Barra{i}Mask", "Mask"),
                                                      **{f"TopLeft{ch}": Expr(" or ".join(f"(Ctrl.Pal=={p} and {pals[p][i][j]})" for p in range(4)) + " or 0")
                                                         for j, ch in enumerate(("Red", "Green", "Blue"))}}))
        layers.append((f"Barra{i}", None))
    tools.append(text("Scritta", "CAPITOLO II", ANTON, 170, CARTA, 960, 540, align=0,
                      extra={"Size": Expr(f"170/{W}*(1+({PROG}-0.5)*0.4)")}))
    layers.append(("Scritta", f"max(1-abs({PROG}-0.5)/0.17,0)"))
    mt, last = stack(layers, base="Taglio", prefix="S")
    return transition("MOV_BarreDelCanale", tools + mt, last, c, [texp("Scritta", "Scritta sul taglio (vuota = nessuna)")])


def tr_vhs():
    c = {"Amount": slider("Intensità", 1, 0.2, 1.5)}
    a = f"(max(1-abs({PROG}-0.5)*2,0)^1.4)"
    tools = [Tool("Taglio", "Dissolve", {"Mix": cut(0.06)}),
             Tool("Sposta", "Transform", {"Input": Conn("Taglio"), "Center": Expr(f":randomseed(floor(time)*13) return Point(0.5+(random()-0.5)*0.06*{a}*Ctrl.Amount, 0.5)"), "Edges": 3}),
             Tool("Neve", "FastNoise", {**FRAME, "Detail": 1, "XScale": 260, "Contrast": 2.5, "SeetheRate": 8}),
             Tool("Righe", "FastNoise", {**FRAME, "LockXY": 0, "XScale": 0.4, "YScale": 60, "Contrast": 3, "SeetheRate": 6}),
             Tool("Bande", "BitmapMask", {"Image": Conn("Righe"), "Channel": FuID("Luminance"), "Low": Expr(f"0.75-{a}*0.4"), "High": Expr(f"0.8-{a}*0.4")}),
             solid("Ciano", (0.16, 0.86, 1), "Bande"), solid("Magenta", (1, 0.16, 0.24), "Bande")]
    tools[-2].inputs["Center"] = (0.506, 0.5)
    tools[-1].inputs["Center"] = (0.494, 0.5)
    mt, last = stack([("Neve", f"Ctrl.Amount*({a}>0.8 and 1 or {a}*0.5)"), ("Ciano", f"0.35*{a}*Ctrl.Amount", "Screen"),
                      ("Magenta", f"0.35*{a}*Ctrl.Amount", "Screen")], base="Sposta", prefix="S")
    return transition("MOV_DisturboVHS", tools + mt, last, c)


# ============================================================== EFFETTI (sulla clip)
def effect(name, tools, out, c, exposed=None, inp=("Ctrl", "Input")):
    return Macro(name, tools, out, [Exposed("Ctrl", k) for k in c] + (exposed or []), [(inp[0], inp[1], "Input")])


TONE = combo("Tono", ["Originale", "Bianco e nero", "Seppia", "Duotono verde"], 1)


def tone_tools(src, prefix="Tono"):
    """Tono sulla clip: B/N, seppia o duotono verde (Ctrl.Tone)."""
    return [Tool(prefix, "BrightnessContrast", {"Input": Conn(src), "Saturation": Expr("Ctrl.Tone>0 and 0 or 1"),
                                                "Contrast": Expr("Ctrl.Tone>0 and 0.12 or 0")}),
            Tool(prefix + "Tinta", "ColorGain", {"Input": Conn(prefix),
                                                 "GainRed": Expr("Ctrl.Tone==2 and 1.08 or (Ctrl.Tone==3 and 0.78 or 1)"),
                                                 "GainGreen": Expr("Ctrl.Tone==2 and 0.98 or (Ctrl.Tone==3 and 1.0 or 1)"),
                                                 "GainBlue": Expr("Ctrl.Tone==2 and 0.82 or (Ctrl.Tone==3 and 0.86 or 1)")})]


def look_tools(src):
    return [ellipse("VignMask", 960, 540, 2300, 1500, soft=0.25, extra={"Invert": 1}), solid("Vign", (0, 0, 0), "VignMask"),
            grain("GranaFx", 120, 1.4),
            Tool("Look1", "Merge", {"Background": Conn(src), "Foreground": Conn("Vign"), "PerformDepthMerge": 0, "Blend": Expr("Ctrl.Vign*0.6")}),
            Tool("Look2", "Merge", {"Background": Conn("Look1"), "Foreground": Conn("GranaFx"), "ApplyMode": FuID("Overlay"), "PerformDepthMerge": 0,
                                    "Blend": Expr("Ctrl.Grain*0.3")})]


LOOK_C = {"Vign": slider("Vignetta", 0.45, 0, 1), "Grain": slider("Grana pellicola", 0.35, 0, 1)}


def fx_pellicola():
    c = {"Grain": slider("Grana", 0.55, 0, 1), "Dust": slider("Polvere e graffi", 1, 0, 2), "Flicker": slider("Sfarfallio", 0.35, 0, 1),
         "Vign": slider("Vignetta", 0.55, 0, 1), "Burn": checkbox("Bordi bruciati", 1), "Tone": TONE}
    tools = [
        Tool("Ctrl", "BrightnessContrast", {"Gain": Expr(":randomseed(floor(time/2)*7) return 1+(random()-0.5)*0.12*Flicker"), **ctrl_values(c)}, controls=c),
        *tone_tools("Ctrl"),
    ]
    prev = None
    for i in range(7):
        e = f":randomseed(floor(time/2)*31+{i}*7) local on=random()<0.35+0.3*Ctrl.Dust return Point(random(), random())"
        sz = f":randomseed(floor(time/2)*31+{i}*7) random() random() random() return ({i % 3 + 1})*(2+6*random())*Ctrl.Dust/1920"
        tools.append(Tool(f"Granello{i}", "EllipseMask", {"Center": Expr(e), "Width": Expr(sz), "Height": Expr(sz.replace("/1920", "/1080*0.8")), "SoftEdge": 0.0008,
                                                         **({"EffectMask": Conn(prev, "Mask")} if prev else {})}))
        prev = f"Granello{i}"
    tools.append(solid("Sporco", (0.05, 0.04, 0.03), prev))
    prev = None
    for i in range(2):
        x = f":randomseed(floor(time/6)*17+{i}*5) return Point(random()+0.003*sin(time*0.9), 0.5)"
        tools.append(Tool(f"Graffio{i}", "RectangleMask", {"Center": Expr(x), "Width": 0.0008, "Height": Expr(f":randomseed(floor(time/6)*17+{i}*5) random() return (random()<0.5+0.25*Ctrl.Dust) and 1.2 or 0"),
                                                          **({"EffectMask": Conn(prev, "Mask")} if prev else {})}))
        prev = f"Graffio{i}"
    tools.append(solid("Righe", (1, 0.97, 0.92), prev))
    tools += [
        rect("BruciaSx", 0, 540, 560, 1300, soft=0.12), rect("BruciaDx", 1920, 540, 560, 1300, soft=0.12, prev="BruciaSx"),
        solid("Bruciato", (0.42, 0.18, 0.05), "BruciaDx"),
    ]
    tools += look_tools("TonoTinta")
    mt, last = stack([("Sporco", "min(Ctrl.Dust,1)*0.75"), ("Righe", "Ctrl.Dust*0.35"), ("Bruciato", "Ctrl.Burn*0.45*(0.8+0.2*sin(time*0.7))", "Multiply")],
                     base="Look2", prefix="P")
    return effect("MOV_PellicolaEpoca", tools + mt, last, c)


def fx_vhs():
    c = {"Amount": slider("Intensità", 0.6, 0, 1), "Osd": checkbox("Scritte a schermo", 1),
         "TStart": slider("Ora di partenza (secondi dalla mezzanotte)", 73867, 0, 86399, integer=True)}
    tools = [
        Tool("Ctrl", "BrightnessContrast", {"Saturation": Expr("1-0.25*Amount"), "Contrast": Expr("0.08*Amount"), **ctrl_values(c)}, controls=c),
        Tool("Mosso", "Blur", {"Input": Conn("Ctrl"), "XBlurSize": Expr("2*Ctrl.Amount"), "YBlurSize": 0}),
        Tool("Linee", "FastNoise", {**FRAME, "LockXY": 0, "XScale": 0.01, "YScale": 270, "Contrast": 4}),
        Tool("Banda", "FastNoise", {**FRAME, "LockXY": 0, "XScale": 0.5, "YScale": 4, "Contrast": 1.5, "Center": Expr("Point(0.5, (time*0.004)%1)")}),
        Tool("Neve", "FastNoise", {**FRAME, "Detail": 1, "XScale": 200, "Contrast": 2, "SeetheRate": 8}),
        rect("TestinaMask", 960, 1062, 1920, 36), solid("Testina", (0.8, 0.8, 0.8), "TestinaMask"),
        text("Play", "PLAY ▶", VIDEO, 64, (0.96, 0.96, 0.94), 120, 150, extra=shadow(0.6, 3)),
        text("Data", "MAG. 25 1994", VIDEO, 64, (0.96, 0.96, 0.94), 120, 960, extra=shadow(0.6, 3)),
        text("Ora", "", VIDEO, 64, (0.96, 0.96, 0.94), 1800, 960, align=1, extra={"StyledText": Expr(
            f":local s=Ctrl.TStart+floor({T}/{F(25)})\nlocal h=floor(s/3600)%24\nlocal ap=h>=12 and 'PM' or 'AM'\nlocal hh=h%12 if hh==0 then hh=12 end\n"
            "return Text(string.format('%s %2d:%02d:%02d',ap,hh,floor(s/60)%60,s%60))"), **shadow(0.6, 3)}),
    ]
    mt, last = stack([("Linee", "Ctrl.Amount*0.18", "Multiply"), ("Banda", "Ctrl.Amount*0.1", "Screen"), ("Neve", "Ctrl.Amount*0.08", "Overlay"),
                      ("Testina", "Ctrl.Amount*0.5"), ("Play", f"Ctrl.Osd*(({T}>{F(60)} or floor({T}/{F(12)})%2==0) and 1 or 0)"),
                      ("Data", "Ctrl.Osd"), ("Ora", "Ctrl.Osd")], base="Mosso", prefix="V")
    return effect("MOV_Videocassetta", tools + mt, last, c, [texp("Data", "Data"), texp("Play", "Scritta in alto")])


def cam_ctrl(c, size, center="Point(0.5,0.5)", pivot=None, angle=None):
    i = {"Size": Expr(size.replace("Ctrl.", "")), "Center": Expr(center.replace("Ctrl.", "")), "Edges": 3, **ctrl_values(c)}
    if angle:
        i["Angle"] = Expr(angle.replace("Ctrl.", ""))
    return Tool("Ctrl", "Transform", i, controls=c)


def fx_dettaglio():
    c = {"Zoom": slider("Ingrandimento", 2.4, 1, 5), "ZStart": slider("Zoom parte al fotogramma", 12, 0, 300, integer=True),
         "ZDur": slider("Durata zoom (fotogrammi)", 60, 1, 300, integer=True), "Mark": combo("Segno", ["Cerchio a mano", "Riflettore", "Nessuno"], 0),
         "Radius": slider("Dimensione segno (px)", 170, 40, 500), "Dark": slider("Scurisci il resto", 0.6, 0, 1), "Tone": TONE, **LOOK_C}
    z = f"(1+(Zoom-1)*{eio(clamp01(f'({T}-ZStart)/max(ZDur,1)'))})"
    # Il punto si sceglie con il controllo "Punto" (Pivot di Fuoco): sposta l'immagine perché il punto vada verso il centro
    pre = f"local z={z}\nlocal px,py=Fuoco.Pivot.X,Fuoco.Pivot.Y\n"
    center = f":{pre}local cx=0.5-(px-0.5)*z local cy=0.5-(py-0.5)*z\nlocal lim=(z-1)/2 cx=min(max(cx,0.5-lim),0.5+lim) cy=min(max(cy,0.5-lim),0.5+lim)\nreturn Point(cx,cy)"
    scr = (f":local z={z.replace('Zoom', 'Ctrl.Zoom').replace('ZStart', 'Ctrl.ZStart').replace('ZDur', 'Ctrl.ZDur')}\n"
           "local c=Ctrl.Center\nreturn Point((Fuoco.Pivot.X-0.5)*z+c.X, (Fuoco.Pivot.Y-0.5)*z+c.Y)")
    mk_t = f"(({T}-Ctrl.ZStart-Ctrl.ZDur*0.8)/{F(18)})"
    cp = eio(clamp01(mk_t))
    tools = [cam_ctrl(c, z, center), Tool("Fuoco", "Transform", {"Pivot": (0.58, 0.4)}),
             Tool("Schermo", "Transform", {"Center": Expr(scr)}),
             *tone_tools("Ctrl"),
             ellipse("BuioMask", "Schermo.Center.X*1920", "(1-Schermo.Center.Y)*1080", "Ctrl.Radius*6.5", "Ctrl.Radius*6.5", soft=0.12,
                     extra={"Invert": 1}),
             solid("Buio", (0, 0, 0), "BuioMask"),
             poly("CerchioMask", 960, 540, hand_ellipse_pts(112, 100, 3), closed=False, stroke=9, write=cp,
                  extra={"Center": Expr("Schermo.Center"), "Size": Expr("Ctrl.Radius/100")}),
             solid("Cerchio", ROSSO, "CerchioMask"),
             text("Nota", "VALENTINO MAZZOLA", MANO, 64, CARTA, 0, 0, extra={
                 "Center": Expr(f":local p=Schermo.Center local r=Ctrl.Radius/1920 local right=p.X<0.58\nreturn Point(p.X+(right and 1 or -1)*(r*1.5+0.03), p.Y+r*1.7)"),
                 "HorizontalLeftCenterRight": Expr("Schermo.Center.X<0.58 and -1 or 1"), **shadow(0.7, 10)}),
             rect("NotaMask", 960, 540, f"1920*2*{eio(clamp01(f'({mk_t}-1)*1.2'))}", 1080 * 2)]
    tools[-2].inputs["EffectMask"] = Conn("NotaMask", "Mask")
    tools[-1].inputs["Center"] = Expr(f":local p=Nota.Center local right=Schermo.Center.X<0.58 local w={eio(clamp01(f'({mk_t}-1)*1.2'))}\nreturn Point(right and p.X-1+w or p.X+1-w, 0.5)")
    tools[-1].inputs["Width"] = 2
    tools += look_tools("TonoTinta")
    dk = eio(clamp01(f"({T}-Ctrl.ZStart-Ctrl.ZDur*0.6)/{F(20)}"))
    mt, last = stack([("Buio", f"(Ctrl.Mark<2 and 1 or 0)*Ctrl.Dark*{dk}*(Ctrl.Mark==1 and 1.35 or 1)"), ("Cerchio", "Ctrl.Mark==0 and 1 or 0"),
                      ("Nota", None)], base="Look2", prefix="D")
    m = effect("MOV_ZoomSulDettaglio", tools + mt, last, c,
               [Exposed("Fuoco", "Pivot", "Punto (trascinalo nel viewer)"), texp("Nota", "Nota scritta a mano (vuota = nessuna)"),
                *color_exposed("Cerchio", "Colore segno", 1)])
    return m


def fx_kenburns():
    c = {"Z0": slider("Zoom iniziale", 1.05, 1, 3), "Z1": slider("Zoom finale", 1.45, 1, 3), "Rot": slider("Rotazione (gradi)", 1, -6, 6),
         "Breath": checkbox("Respiro di camera a mano", 1), "Smooth": combo("Curva", ["Morbida", "Lineare", "Decisa"], 0), "Tone": combo("Tono", ["Originale", "Bianco e nero", "Seppia", "Duotono verde"], 0), **LOOK_C}
    p = f"local p={clamp01(f'{T}/{LEN}')}\nif Smooth==0 then p=p<0.5 and 4*p^3 or 1-((-2*p+2)^3)/2 elseif Smooth==2 then p=p<0.5 and 16*p^5 or 1-((-2*p+2)^5)/2 end\n"
    size = f":{p}return Z0+(Z1-Z0)*p"
    center = (f":{p}local z=Z0+(Z1-Z0)*p\nlocal ax,ay=PuntoA.Pivot.X,PuntoA.Pivot.Y\nlocal bx,by=PuntoB.Pivot.X,PuntoB.Pivot.Y\n"
              "local px,py=ax+(bx-ax)*p,ay+(by-ay)*p\nlocal cx,cy=0.5-(px-0.5)*z,0.5-(py-0.5)*z\nlocal lim=(z-1)/2\n"
              "cx=min(max(cx,0.5-lim),0.5+lim) cy=min(max(cy,0.5-lim),0.5+lim)\n"
              "if Breath>0.5 then cx=cx+0.003*sin(time*0.05) cy=cy+0.003*cos(time*0.043) end\nreturn Point(cx,cy)")
    tools = [Tool("Ctrl", "Transform", {"Size": Expr(size), "Center": Expr(center), "Angle": Expr(f":{p}return Rot*p"), "Edges": 3, **ctrl_values(c)}, controls=c),
             Tool("PuntoA", "Transform", {"Pivot": (0.35, 0.55)}), Tool("PuntoB", "Transform", {"Pivot": (0.62, 0.45)}), *tone_tools("Ctrl"), *look_tools("TonoTinta")]
    return effect("MOV_KenBurns", tools, "Look2", c, [Exposed("PuntoA", "Pivot", "Punto di partenza"), Exposed("PuntoB", "Pivot", "Punto di arrivo")])


def fx_scatti():
    c = {"Steps": slider("Scatti", 3, 1, 5, integer=True), "Every": slider("Fotogrammi tra gli scatti", 18, 4, 75, integer=True),
         "Zoom": slider("Zoom finale", 2.6, 1.2, 5), "Flash": checkbox("Lampo su ogni scatto", 1), "Tone": TONE, **LOOK_C}
    pre = (f"local f={T}-{F(8)}\nlocal n=Steps\nlocal z=1\nlocal last=-1\n"
           "for i=0,n-1 do local t0=i*Every if f>=t0 then local a,b=Zoom^(i/n),Zoom^((i+1)/n) local k=min((f-t0)/4,1) k=k>=1 and 1 or 1-2^(-10*k) z=a+(b-a)*k last=t0 end end\n"
           "z=z*(1+0.02*max(f,0)/100)\n")
    size = f":{pre}return z"
    center = f":{pre}local px,py=Punto.Pivot.X,Punto.Pivot.Y\nlocal cx,cy=0.5-(px-0.5)*z,0.5-(py-0.5)*z\nlocal lim=(z-1)/2 cx=min(max(cx,0.5-lim),0.5+lim) cy=min(max(cy,0.5-lim),0.5+lim)\nlocal d=f-last local a=(last>=0) and 0.012*max(1-d/8,0)^2 or 0\nreturn Point(cx+a*sin(time*2.5), cy+a*cos(time*3.1))"
    lampo = f":local f={T}-{F(8)}\nlocal last=-1 for i=0,Ctrl.Steps-1 do if f>=i*Ctrl.Every then last=i*Ctrl.Every end end\nif last<0 then return 0 end return Ctrl.Flash*0.45*max(1-(f-last)/{F(3)},0)"
    tools = [Tool("Ctrl", "Transform", {"Size": Expr(size), "Center": Expr(center), "Edges": 3, **ctrl_values(c)}, controls=c),
             Tool("Punto", "Transform", {"Pivot": (0.42, 0.42)}),
             Tool("Mosso", "DirectionalBlur", {"Input": Conn("Ctrl"), "Type": 3, "Center": (0.5, 0.5), "Length": Expr(
                 f":local f={T}-{F(8)}\nlocal last=-1 for i=0,Ctrl.Steps-1 do if f>=i*Ctrl.Every then last=i*Ctrl.Every end end\nif last<0 then return 0 end return 0.15*max(1-(f-last)/4,0)")}),
             *tone_tools("Mosso"), *look_tools("TonoTinta"), solid("Bianco", (1, 1, 1))]
    mt, last = stack([("Bianco", lampo)], base="Look2", prefix="Z")
    return effect("MOV_ZoomAScatti", tools + mt, last, c, [Exposed("Punto", "Pivot", "Punto (trascinalo nel viewer)")])


def fx_isola():
    c = {"Height": slider("Altezza del giocatore (px)", 200, 60, 700), "Dark": slider("Scurisci il resto", 0.62, 0, 1),
         "Push": slider("Avvicinamento", 1.2, 1, 2), "Tone": TONE, **LOOK_C}
    z = f"(1+(Push-1)*{eio(clamp01(f'({T}-{F(5)})/{F(55)}'))})"
    center = f":local z={z}\nlocal px,py=Piedi.Pivot.X,Piedi.Pivot.Y+0.04\nlocal cx,cy=0.5-(px-0.5)*z,0.5-(py-0.5)*z\nlocal lim=(z-1)/2 cx=min(max(cx,0.5-lim),0.5+lim) cy=min(max(cy,0.5-lim),0.5+lim)\nreturn Point(cx,cy)"
    scr = f":local z={z.replace('Push', 'Ctrl.Push')}\nlocal c=Ctrl.Center return Point((Piedi.Pivot.X-0.5)*z+c.X,(Piedi.Pivot.Y-0.5)*z+c.Y)"
    hz = f"Ctrl.Height*({z.replace('Push', 'Ctrl.Push')})"
    rk = eback(st(30, 14))
    lp = eio(st(40, 14))
    tools = [cam_ctrl(c, z, center), Tool("Piedi", "Transform", {"Pivot": (0.47, 0.44)}), Tool("Schermo", "Transform", {"Center": Expr(scr)}),
             *tone_tools("Ctrl"),
             ellipse("LuceMask", "Schermo.Center.X*1920", f"(1-Schermo.Center.Y)*1080-{hz}*0.5", f"{hz}*1.0", f"{hz}*1.7", soft=0.08, extra={"Invert": 1}),
             solid("Buio", (0.02, 0.05, 0.04), "LuceMask"),
             ellipse("AnelloMask", "Schermo.Center.X*1920", "(1-Schermo.Center.Y)*1080", f"{hz}*0.85*{rk}", f"{hz}*0.24*{rk}", ring=5),
             ellipse("Anello2Mask", "Schermo.Center.X*1920", "(1-Schermo.Center.Y)*1080", f"{hz}*1.15*{rk}", f"{hz}*0.33*{rk}", ring=2, prev="AnelloMask"),
             solid("Anello", ROSSO, "Anello2Mask"),
             rect("FiloMask", "Schermo.Center.X*1920", f"(1-Schermo.Center.Y)*1080-{hz}*1.05-120*{lp}", 2, f"240*{lp}"),
             solid("Filo", CARTA, "FiloMask"),
             text("Nome", "LOIK", ANTON, 58, INCHIOSTRO, 0, 0, align=0, extra={"Center": Expr(f"Point(Schermo.Center.X, Schermo.Center.Y+({hz}*1.05+300)/1080)")}),
             text("Ruolo", "8 · MEZZALA DESTRA", INTER_B, 24, CARTA, 0, 0, align=0, track=1.25, extra={"Center": Expr(f"Point(Schermo.Center.X, Schermo.Center.Y+({hz}*1.05+252)/1080)")}),
             rect("CartMask", "Schermo.Center.X*1920", f"(1-Schermo.Center.Y)*1080-{hz}*1.05-300", f"420*{eo(st(48, 14))}", 78),
             solid("Cartellino", CARTA, "CartMask"),
             rect("RuoloMask", "Schermo.Center.X*1920", f"(1-Schermo.Center.Y)*1080-{hz}*1.05-252", f"420*{eo(st(52, 14))}", 42),
             solid("RuoloBox", ROSSO, "RuoloMask"), *look_tools("TonoTinta")]
    mt, last = stack([("Buio", f"Ctrl.Dark*{eio(st(14, 18))}"), ("Anello", None), ("Filo", None), ("Cartellino", None), ("RuoloBox", None),
                      ("Nome", eo(st(52, 10))), ("Ruolo", eo(st(56, 10)))], base="Look2", prefix="I")
    return effect("MOV_IsolaGiocatore", tools + mt, last, c,
                  [Exposed("Piedi", "Pivot", "Piedi del giocatore (trascina nel viewer)"), texp("Nome", "Nome"), texp("Ruolo", "Ruolo"),
                   *color_exposed("Anello", "Colore anello", 1)])


def fx_cartolina():
    c = {**BASE, "Tilt": slider("Inclinazione (gradi)", -1.5, -8, 8), "Bg": checkbox("Tavolo verde con cornice", 1), "Tone": combo("Tono", ["Originale", "Bianco e nero", "Seppia", "Duotono verde"], 0),
         "Grain": slider("Grana pellicola", 0.3, 0, 1)}
    k = clamp01(f"{T}/{F(16)}")
    land = ei(k)
    card = torn_rect_pts(1120, 880, amp=3, step=9, seed=7)
    photo = torn_rect_pts(1048, 640, amp=6, step=12, seed=31)
    wp, wp2 = clamp01(f"({T}-{F(34)})/{F(22)}"), clamp01(f"({T}-{F(56)})/{F(26)}")
    fr, fl = reg_frame("Cornice", 60, 60, 1860, 1020, "1", alpha=0.5)
    tools = [
        Tool("Ctrl", "Transform", {"Size": Expr("1.0"), **ctrl_values(c)}, controls=c),
        *tone_tools("Ctrl"),
        Tool("FotoPos", "Transform", {"Input": Conn("TonoTinta"), "Size": 0.6, "Center": P(960, 456)}),
        poly("FotoMask", 960, 456, photo), Tool("Foto", "Merge", {"Background": Conn("CanvasCart"), "Foreground": Conn("FotoPos"), "PerformDepthMerge": 0,
                                                                   "EffectMask": Conn("FotoMask", "Mask")}),
        canvas("CanvasCart"),
        poly("CartaMask", 960, 540, card), solid("Carta", CARTA, "CartaMask"),
        Tool("Fibra", "FastNoise", {**FRAME, "Detail": 4, "XScale": 7, "Contrast": 0.7, "Color1Red": 0.83, "Color1Green": 0.77, "Color1Blue": 0.67,
                                    "EffectMask": Conn("CartaMask", "Mask")}),
        ellipse("UsuraMask", 960, 456, 1300, 900, soft=0.2, extra={"Invert": 1}, prev="FotoMask", mode="Minimum"), solid("Usura", (0.08, 0.055, 0.02), "UsuraMask"),
        rect("ScriviData", f"440+1000*{wp}/2", 845, f"1000*{wp}", 90),
        text("Data", "10 GIUGNO 1934", MANO, 54, INCHIOSTRO, 464, 845, track=1.04, extra={"EffectMask": Conn("ScriviData", "Mask"), "Angle": 0.6}),
        poly("SottMask", 464 + 180, 878, [(-180 + i * 18, (i % 3 - 1) * 1.2) for i in range(21)], closed=False, stroke=4, write=eio(clamp01(f"({T}-{F(52)})/{F(10)}"))),
        solid("Sott", ROSSO, "SottMask", alpha=0.85),
        rect("ScriviLuogo", f"440+1000*{wp2}/2", 918, f"1000*{wp2}", 70),
        text("Luogo", "STADIO NAZIONALE DEL PNF, ROMA", MANO, 36, INCHIOSTRO, 464, 918, track=1.03, extra={"EffectMask": Conn("ScriviLuogo", "Mask")}),
    ]
    mt, last = stack([("Carta", None), ("Fibra", 0.4, "Multiply"), ("Foto", None), ("Usura", 0.35), ("Data", None), ("Sott", None), ("Luogo", None)],
                     base="CanvasCart", prefix="C")
    tools += mt
    rot = f"(Ctrl.Tilt+(1-{land})*(-9))"
    tools += [Tool("Cartolina", "Transform", {"Input": Conn(last), "Angle": Expr(rot), "Size": Expr(f"(1.32-0.32*{land})*(1+0.05*{GLIDE})")}),
              solid("OmbraS", (0, 0, 0), "CartaMask", alpha=0.5),
              Tool("OmbraT", "Transform", {"Input": Conn("OmbraS"), "Angle": Expr(rot), "Size": Expr(f"(1.32-0.32*{land})*(1+0.05*{GLIDE})"),
                                           "Center": Expr(f"Point(0.5, 0.5-(30+60*(1-{land}))/1080)")}),
              Tool("Ombra", "Blur", {"Input": Conn("OmbraT"), "XBlurSize": Expr(f"40+40*(1-{land})")}),
              *ground_tools("Tavolo"), *fr, grain()]
    ctrl = next(t for t in tools if t.name == "Ctrl")
    ctrl.inputs["Bg"] = 1
    layers = [("TavoloVerde", "Ctrl.Bg"), ("TavoloVign", "Ctrl.Bg"), (fl[0][0], "Ctrl.Bg"), (fl[1][0], "Ctrl.Bg"),
              ("Ombra", f"{clamp01(f'{k}*4')}"), ("Cartolina", f"{clamp01(f'{k}*4')}"), ("Grana", "Ctrl.Grain*0.35*Ctrl.Bg", "Overlay")]
    mt2, last2 = stack(layers, base="CanvasFin", prefix="F")
    tools += [canvas("CanvasFin")] + mt2
    return effect("MOV_FotoSulTavolo", tools, last2, c, [texp("Data", "Data"), texp("Luogo", "Luogo o soggetto"), Exposed("Data", "Font", "Font scrittura")])


def fx_scheda():
    c = {**BASE, "Tone": combo("Tono foto", ["Originale", "Bianco e nero", "Seppia", "Duotono verde"], 3), "Grain": slider("Grana pellicola", 0.3, 0, 1),
         "Zoom": slider("Ingrandimento foto", 1.0, 0.5, 3)}
    xo = ex_out(18)
    fx0, fy0, fw, fh = 190, 150, 600, 780
    rv = eo(st(4, 26))
    tools = [
        Tool("Ctrl", "Transform", {"Size": Expr("Zoom*0.75"), "Center": P(fx0 + fw / 2, fy0 + fh / 2), "Edges": 0, **ctrl_values(c)}, controls=c),
        *tone_tools("Ctrl"),
        rect("FotoMask", fx0 + fw / 2, f"{fy0 + fh}-{fh}*{rv}/2", fw, f"{fh}*{rv}"),
        Tool("Foto", "Merge", {"Background": Conn("Canvas"), "Foreground": Conn("TonoTinta"), "PerformDepthMerge": 0, "EffectMask": Conn("FotoMask", "Mask")}),
        canvas("Canvas"),
        *ground_tools(),
        text("Maglia", "10", ANTON, 1100, CARTA, 1960, 560, align=1, alpha=0,
             extra={"Enabled2": 1, "ElementShape2": 1, "OutsideOnly2": 0, "Thickness2": 0.0016, "Red2": CARTA[0], "Green2": CARTA[1], "Blue2": CARTA[2], "Alpha2": 0.16}),
        rect("QuadMask", 911, 248, 22, 22), solid("Quad", ROSSO, "QuadMask"),
        text("Ruolo", "N. 10  ·  MEZZALA · CAPITANO", INTER_B, 26, CARTA, 940, 248, track=1.35, alpha=0.85),
        text("Nome", "VALENTINO", INTER, 66, CARTA, 900, f"318+(1-{eo(st(20, 20))})*80", track=1.3, extra={"EffectMask": Conn("NomeMask", "Mask")}),
        rect("NomeMask", 1400, 318, 1100, 84),
        text("Cognome", "MAZZOLA", ANTON, 210, CARTA, 900, f"470+(1-{eo(st(24, 22))})*210", extra={"EffectMask": Conn("CognomeMask", "Mask")}),
        rect("CognomeMask", 1400, 470, 1100, 220),
        rect("LineaMask", f"900+820*{eo(st(32, 24))}/2", 598, f"820*{eo(st(32, 24))}", 2), solid("Linea", CARTA, "LineaMask", alpha=0.35),
        text("Nato", "Cassano d'Adda, 26 gennaio 1919", INTER, 28, CARTA, 900, 646, alpha=0.75),
        text("Stat", "Presenze|195\nGol|118\nScudetti|5", INTER, 10, CARTA, 0, -400),
    ]
    rft, rf = reg_frame("Registro", fx0 - 24, fy0 - 24, fx0 + fw + 24, fy0 + fh + 24, eo(st(0, 30)), alpha=0.55, thick=2)
    tools += rft
    layers = ground_layers() + [("Maglia", f"{eo(st(8, 40))}*(1-{xo})"), ("Foto", f"1-{xo}"), (rf[0][0], f"{rf[0][1]}*(1-{xo})"), (rf[1][0], f"{rf[1][1]}*(1-{xo})"), ("Quad", f"{eo(st(16, 10))}*(1-{xo})"), ("Ruolo", f"{eo(st(18, 12))}*(1-{xo})"),
                                ("Nome", f"1-{xo}"), ("Cognome", f"1-{xo}"), ("Linea", f"1-{xo}"), ("Nato", f"{eo(st(38, 18))}*(1-{xo})")]
    # registro: avanzamento corretto
    for t in tools:
        if t.name == "Registro":
            pass
    for i in range(3):
        g = f"min(max(({T}-{F(52 + i * 6)}*Ctrl.Speed)/max({F(38)}*Ctrl.Speed,1),0),1)"
        pre = ":" + lua_lines("Stat") + lua_split() + f"local a=split(L[{i + 1}] or '') local v=num(a[2]) local k={g} k=1-(1-k)^5\n"
        tools += [text(f"Val{i}", "", ANTON, 120, ROSSO if i == 0 else CARTA, 900 + i * 273, 770, extra={"StyledText": Expr(pre + "return Text(fmt(v*k,dec(a[2])))")}),
                  text(f"Lab{i}", "", INTER_B, 22, CARTA, 904 + i * 273, 858, track=1.4, alpha=0.7, extra={"StyledText": Expr(pre + "return Text(string.upper(a[1] or ''))")})]
        layers += [(f"Val{i}", f"{eo(st(50 + i * 6, 10))}*(1-{xo})"), (f"Lab{i}", f"{eo(st(50 + i * 6, 10))}*(1-{xo})")]
    tools.append(grain())
    layers.append(grain_layer())
    ctrl = tools[0]
    ctrl.controls["Bg"] = combo("Sfondo", BG_OPTS, 1)
    ctrl.inputs["Bg"] = 1
    mt, last = stack(layers, base="Canvas")
    return effect("MOV_SchedaGiocatore", tools + mt, last, {**c, "Bg": ctrl.controls["Bg"]},
                  [texp("Nome", "Nome"), texp("Cognome", "Cognome"), texp("Maglia", "Numero di maglia"), texp("Ruolo", "Riga sopra il nome"),
                   texp("Nato", "Nascita"), texp("Stat", "Statistiche (Nome|valore, max 3)"), Exposed("Ctrl", "Center", "Posizione foto nella cornice"),
                   *color_exposed("Quad", "Colore accento", 1)])
