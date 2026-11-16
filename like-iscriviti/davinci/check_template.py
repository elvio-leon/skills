#!/usr/bin/env python3
"""
Verifica offline del template Fusion (non sostituisce una prova in DaVinci Resolve):

1. il .setting si carica come tabella Lua (stessa grammatica che legge Fusion);
2. ogni Expression compila ed esegue in un ambiente che imita quello di Fusion
   (time, comp, Point, nodi referenziati per nome) per tutti i frame, a 30 e 25 fps;
3. i valori animati coincidono con il renderer di riferimento (render.py);
4. le forme poligonali vengono ridisegnate in un'immagine di controllo.
"""

import math
import os
import sys

from lupa.luajit21 import LuaRuntime  # Fusion esegue le espressioni con LuaJIT

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import render as R  # noqa: E402

W, H = 1920.0, 1080.0

STUB = r"""
local function ctor(name)
  return function(t) if type(t) ~= "table" then t = { t } end t.__ctor = name return t end
end
ordered = function() return function(t) return t end end
setmetatable(_G, { __index = function(_, k) return ctor(k) end })
"""


def load_setting(lua, path):
    text = open(path, encoding="utf-8").read()
    fn = lua.execute("return function(src) return load('return ' .. src, 'setting', 't') end")
    res = fn(text)
    chunk, err = (res if isinstance(res, tuple) else (res, None))
    if chunk is None:
        raise SyntaxError(str(err))
    return chunk()


def walk_expressions(tbl):
    """Ritorna {(tool, input): expression} dal MacroOperator."""
    macro = None
    for k, v in tbl["Tools"].items():
        if v["__ctor"] == "MacroOperator":
            macro = v
    out, tools = {}, {}
    for tname, tool in macro["Tools"].items():
        tools[tname] = tool
        inputs = tool["Inputs"]
        if inputs is None:
            continue
        for iname, inp in inputs.items():
            if inp["Expression"] is not None:
                out[(tname, iname)] = inp["Expression"]
    return macro, tools, out


ENV_FACTORY = r"""
return function(code, fps, widths, strict)
  local env = {}
  local fn, err
  if code:sub(1, 1) == ":" then
    fn, err = load(code:sub(2), "expr", "t", env)
  else
    fn, err = load("return " .. code, "expr", "t", env)
  end
  if not fn then return nil, err end
  local function txt(w)
    if w == nil then return {} end
    return { Output = { [0] = { DataWindow = { 100, 400, 100 + w, 460 }, Width = 1920 } } }
  end
  local base = {
    math = math, pcall = pcall, type = type, tostring = tostring,
    Point = function(x, y) return { X = x, Y = y } end,
    comp = { RenderStart = 0, GetPrefs = function(self, k) if k == "Comp.FrameFormat.Rate" then return fps end end },
    LK_Txt = txt(widths[1]), SB_Txt1 = txt(widths[2]), SB_Txt2 = txt(widths[3]),
  }
  base.LK_Txt.Red1, base.LK_Txt.Green1, base.LK_Txt.Blue1 = 1, 1, 1
  setmetatable(env, { __index = function(_, k)
    if k == "time" then return env.__time end
    local v = base[k]
    if v == nil and strict then error("nome sconosciuto nell'espressione: " .. tostring(k)) end
    return v
  end })
  return function(t) env.__time = t return fn() end
end
"""


def run(setting_path, shapes=None):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUB)
    tbl = load_setting(lua, setting_path)
    macro, tools, exprs = walk_expressions(tbl)
    print(f"[ok] sintassi Lua: {len(tools)} nodi, {len(exprs)} espressioni, "
          f"{len(list(macro['Inputs'].items()))} controlli pubblicati")

    # costruttori: ogni input e' Input { }, ogni controllo pubblicato InstanceInput { }
    known = {"Background", "RectangleMask", "EllipseMask", "PolylineMask", "TextPlus", "Merge",
             "Dissolve", "Transform"}
    bad = [(t, tool["__ctor"]) for t, tool in tools.items() if tool["__ctor"] not in known]
    bad += [(t, i) for t, tool in tools.items() for i, inp in (tool["Inputs"] or {}).items()
            if inp["__ctor"] != "Input"]
    bad += [("macro", k) for k, inp in macro["Inputs"].items() if inp["__ctor"] != "InstanceInput"]
    if bad:
        print("[ERRORE] costruttori errati:", bad[:10])
        return 1
    print("[ok] costruttori: nodi noti, Input { } e InstanceInput { } ovunque")

    # riferimenti tra nodi: ogni SourceOp deve esistere
    missing = []
    for tname, tool in tools.items():
        for iname, inp in (tool["Inputs"] or {}).items():
            if hasattr(inp, "__getitem__") and not isinstance(inp, (int, float, str)):
                try:
                    so = inp["SourceOp"]
                except Exception:
                    so = None
                if so is not None and so not in tools:
                    missing.append((tname, iname, so))
    for k, inp in macro["Inputs"].items():
        if inp["SourceOp"] not in tools:
            missing.append(("macro", k, inp["SourceOp"]))
    if missing:
        print("[ERRORE] riferimenti mancanti:", missing)
        return 1
    print("[ok] tutti i SourceOp puntano a nodi esistenti")

    factory = lua.execute(ENV_FACTORY)
    cfg = R.Config(type("A", (), dict(like_text="Mi piace", subscribe_text="Iscriviti",
                                      subscribed_text="Iscritto", x=960.0, y=540.0))())
    widths = lua.table(cfg.f_medium.measureText("Mi piace"), cfg.f_bold.measureText("Iscriviti"),
                       cfg.f_medium.measureText("Iscritto"))

    errors = 0

    def evaluator(key, fps=30, w=widths, strict=True):
        res = factory(exprs[key], fps, w, strict)
        f, err = (res if isinstance(res, tuple) else (res, None))
        if f is None:
            raise SyntaxError(f"{key}: {err}")
        return f

    # 1) tutte le espressioni compilano e girano su tutti i frame (30 e 25 fps)
    for fps in (30, 25):
        for key in exprs:
            f = evaluator(key, fps)
            for fr in range(int(5 * fps) + 10):
                v = f(fr)
                if v is None:
                    print("[ERRORE] nil da", key, "frame", fr)
                    errors += 1
                    break
    print(f"[ok] espressioni eseguite su tutti i frame a 30 e 25 fps" if not errors else "[ERRORE] espressioni")

    # 2) confronto con il renderer di riferimento (30 fps)
    def num(key, fr, **kw):
        v = evaluator(key, **kw)(fr)
        return v if isinstance(v, (int, float)) else (v["X"], v["Y"])

    def close(a, b, tol, label):
        nonlocal errors
        if abs(a - b) > tol:
            print(f"[ERRORE] {label}: template {a:.5f} vs riferimento {b:.5f}")
            errors += 1
            return False
        return True

    worst = {}

    def track(label, a, b):
        worst[label] = max(worst.get(label, 0.0), abs(a - b))

    for fr in range(150):
        t = fr / 30
        # pillole
        ls, la = R.appear(t, *R.T_LIKE_IN)
        so, ao = R.disappear(t)
        ls *= R.press(t, R.T_CLICK_LIKE) * so
        la *= ao
        ss, sa = R.appear(t, *R.T_SUB_IN)
        ss *= R.press(t, R.T_CLICK_SUB) * so
        sa *= ao
        track("scala Mi piace", num(("SC_Like", "Size"), fr), ls)
        track("opacita' Mi piace", num(("SC_Like", "Blend"), fr), la)
        track("scala Iscriviti", num(("SC_Sub", "Size"), fr), ss)
        track("opacita' Iscriviti", num(("SC_Sub", "Blend"), fr), sa)
        # posizioni pillole
        cx, cy = num(("SC_Like", "Center"), fr)
        track("centro Mi piace (px)", cx * W, cfg.like_cx)
        cx, cy = num(("SC_Sub", "Center"), fr)
        track("centro Iscriviti (px)", cx * W, cfg.sub_cx)
        track("larghezza Mi piace (px)", num(("LK_M", "Width"), fr) * W, cfg.like_w)
        track("larghezza Iscriviti (px)", num(("SB_M", "Width"), fr) * W, cfg.sub_w)
        # cursore
        (px, py), pa = R.cursor_state(t, cfg)
        cx, cy = num(("SC_Cursor", "Center"), fr)
        track("cursore x (px)", cx * W, px)
        track("cursore y (px)", (1 - cy) * H, py)
        track("cursore opacita'", num(("SC_Cursor", "Blend"), fr), pa)
        # pollice
        ut = R.prog(t, *R.T_THUMB)
        track("pollice rotazione (gradi)", num(("LK_C4", "Angle"), fr), 22.0 * R.bump(ut))
        track("pollice scala", num(("LK_C4", "Size"), fr), 1 + 0.5 * R.bump(ut))
        track("pollice riempimento", num(("TH_Dis", "Mix"), fr),
              R.ease_out_cubic(R.prog(t, R.T_THUMB[0], R.T_THUMB[0] + R.THUMB_FILL_DUR)))
        # campanella e crossfade
        track("campanella (gradi)", num(("BL_Xf", "Angle"), fr), -R.bell_angle(t))
        k = R.ease_in_out_cubic(R.prog(t, *R.T_SWAP))
        track("crossfade colore", num(("SB_Dis", "Mix"), fr), k)
        # anello
        for tc, tgt in ((R.T_CLICK_LIKE, cfg.cur_like), (R.T_CLICK_SUB, cfg.cur_sub)):
            u = R.prog(t, tc, tc + R.RING_DUR)
            if 0 < u < 1:
                r = R.lerp(12, 52, R.ease_out_cubic(u))
                w = R.lerp(4.0, 1.5, u)
                track("anello raggio esterno (px)", num(("RI_O", "Width"), fr) * W / 2, r + w / 2)
                cx, cy = num(("RI_O", "Center"), fr)
                track("anello centro (px)", math.hypot(cx * W - tgt[0], (1 - cy) * H - tgt[1]), 0)
                track("anello opacita'", num(("SC_Ring", "Blend"), fr), 0.95 * (1 - u) ** 1.5)

    tol = {"(px)": 0.6, "(gradi)": 0.05}
    for label, d in worst.items():
        lim = next((v for s, v in tol.items() if s in label), 2e-3)
        status = "ok" if d <= lim else "ERRORE"
        if d > lim:
            errors += 1
        print(f"[{status}] {label}: scarto massimo {d:.4g}")

    # 3) layout con testi diversi: le pillole si allargano e restano centrate
    wide = lua.table(400.0, 120.0, 330.0)
    LW = num(("LK_M", "Width"), 60, w=wide) * W
    SW = num(("SB_M", "Width"), 60, w=wide) * W
    lc = num(("SC_Like", "Center"), 60, w=wide)[0] * W
    sc = num(("SC_Sub", "Center"), 60, w=wide)[0] * W
    ok = close(LW, 146 + 400, 0.01, "larghezza auto Mi piace") & close(SW, 150 + 330, 0.01, "larghezza auto Iscritto")
    ok &= close((lc - LW / 2 + sc + SW / 2) / 2, 960, 0.01, "gruppo centrato")
    print("[ok] testi lunghi: pillole allargate e gruppo centrato" if ok else "[ERRORE] layout testi lunghi")

    # 4) a 25 fps i tempi in secondi restano uguali
    f25 = evaluator(("SC_Like", "Blend"), 25)
    ok = close(f25(int(0.5 * 25)), R.appear(0.5, *R.T_LIKE_IN)[1], 1e-6, "tempo a 25 fps")
    print("[ok] a 25 fps l'animazione segue i secondi" if ok else "[ERRORE] 25 fps")

    # 5) senza DataWindow (fallback) il layout resta quello di design
    nowidth = lua.table()
    lw = num(("LK_M", "Width"), 60, w=nowidth) * W
    ok = close(lw, 330, 0.01, "fallback larghezza")
    print("[ok] se il DataWindow non e' leggibile si usano le larghezze di design" if ok else "[ERRORE] fallback")

    if shapes:
        draw_shapes(shapes, os.path.join(HERE, "check-forme.png"))

    print("VERIFICA SUPERATA" if errors == 0 else f"VERIFICA FALLITA: {errors} errori")
    return 0 if errors == 0 else 1


def draw_shapes(shapes, path):
    """Ridisegna i poligoni (pieni meno fori) come li comporrebbe la catena di maschere."""
    from PIL import Image, ImageChops, ImageDraw
    S = 4
    names = ["thumb_outline", "thumb_fill", "bell", "cursor_black", "cursor_white"]
    tiles = []
    for n in names:
        size = 90 * S
        mask = Image.new("L", (size, size), 0)
        ox = oy = size / 2
        if n.startswith("cursor"):
            ox, oy = size * 0.3, size * 0.15
        for poly, hole in shapes[n]:
            layer = Image.new("L", (size, size), 0)
            ImageDraw.Draw(layer).polygon([(ox + x * S, oy + y * S) for x, y in poly], fill=255)
            mask = ImageChops.subtract(mask, layer) if hole else ImageChops.lighter(mask, layer)
        bg = Image.new("RGB", (size, size), (39, 39, 39) if n != "cursor_white" else (90, 120, 160))
        fill = Image.new("RGB", (size, size), (0, 0, 0) if n == "cursor_black" else (255, 255, 255))
        if n == "cursor_black":
            bg = Image.new("RGB", (size, size), (200, 200, 200))
        tiles.append(Image.composite(fill, bg, mask).resize((size // 2, size // 2), Image.LANCZOS))
    sheet = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height), (0, 0, 0))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width
    sheet.save(path)
    print("[info] forme ridisegnate in", path)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Mi piace Iscriviti.setting")))
