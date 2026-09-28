"""Build the whole YouTube Kit.

    python3 build_all.py

Outputs (next to this folder):
    Templates/Edit/...          Fusion templates (.setting + icon .png)
    LUT/*.cube                  colour looks for the Color page
    SFX/<categoria>/*.wav       sound effects
    dist/YouTubeKit.drfx        one-file installer for DaVinci Resolve

Every template is validated before packaging: the .setting must parse as Lua,
every connection must point at an existing tool, and every expression is
executed at several frames inside a mock of Fusion's expression environment.
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

import luts  # noqa: E402
import sfx  # noqa: E402
from fusion import Conn, Expr  # noqa: E402
from templates import CATALOG, LOOKS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PACK = "YouTube Kit"
TEMPLATES = ROOT / "Templates" / "Edit"
CATEGORY_COLORS = {"Titles": (230, 57, 70), "Transitions": (69, 123, 157),
                   "Effects": (42, 157, 143), "Generators": (244, 162, 97)}


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
MOCK_ENV = r"""
local M = {}
function M.run(code, tools, t, rstart, rend)
  local function Point(x, y) return {X = x, Y = y, _point = true} end
  local function Text(s) return {Value = s, _text = true} end
  local env = {
    time = t, comp = {RenderStart = rstart, RenderEnd = rend, CurrentTime = t},
    min = math.min, max = math.max, sin = math.sin, cos = math.cos, abs = math.abs,
    floor = math.floor, ceil = math.ceil, exp = math.exp, sqrt = math.sqrt, pi = math.pi,
    random = math.random, randomseed = math.randomseed, math = math, string = string,
    table = table, tostring = tostring, tonumber = tonumber,
    Point = Point, Text = Text,
    iif = function(c, a, b) if c and c ~= 0 then return a else return b end end,
  }
  for name, inputs in pairs(tools) do env[name] = inputs end
  setmetatable(env, {__index = function(_, k) error("undefined name: " .. tostring(k)) end})
  local body = code
  if string.sub(body, 1, 1) == ":" then body = string.sub(body, 2)
  else body = "return " .. body end
  local f, err = load(body, "expr", "t", env)
  if not f then error("syntax: " .. err) end
  return f()
end
return M
"""


def lua_value_for(lua, v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, tuple):
        return lua.table(X=v[0], Y=v[1])
    if isinstance(v, str):
        return lua.table(Value=v)
    return 0


def validate(macro, lua, runner):
    names = {t.name for t in macro.tools}
    assert macro.output in names, f"{macro.name}: output {macro.output} missing"
    for tool, src, _ in macro.main_inputs:
        assert tool in names, f"{macro.name}: main input tool {tool} missing"
    for e in macro.exposed:
        assert e.tool in names, f"{macro.name}: exposed tool {e.tool} missing"
        tool = next(t for t in macro.tools if t.name == e.tool)
        known = set(tool.inputs) | set(tool.controls)
        if e.source not in known and tool.kind in ("Merge", "Transform", "Dissolve", "Background"):
            # Standard inputs we rely on without setting a value explicitly.
            assert e.source in {"Center", "Blend", "Angle", "Pivot", "Size"}, \
                f"{macro.name}: {e.tool}.{e.source} not defined"
    exprs = []
    for t in macro.tools:
        for k, v in t.inputs.items():
            if isinstance(v, Conn):
                assert v.tool in names, f"{macro.name}: {t.name}.{k} -> missing {v.tool}"
            if isinstance(v, Expr):
                exprs.append((t, k, v.code))

    # Build the mock tool table: every input's static value, Anim Curves = linear 0..1.
    def build_tools(t_now, rend):
        tbl = lua.table()
        for t in macro.tools:
            it = lua.table()
            for k, v in t.inputs.items():
                if isinstance(v, Conn):
                    if v.output == "Value":
                        it[k] = t_now / max(rend, 1)
                    else:
                        it[k] = lua.table(OriginalWidth=1920, OriginalHeight=1080)
                elif not isinstance(v, Expr):
                    it[k] = lua_value_for(lua, v)
            for k in ("Center", "Pivot"):
                if k not in t.inputs:
                    it[k] = lua.table(X=0.5, Y=0.5)
            for k in ("Width", "Height", "Size", "Angle", "Blend", "Mix"):
                if k not in t.inputs:
                    it[k] = 1
            for k in ("Background", "Input", "Foreground"):
                if k not in t.inputs:
                    it[k] = lua.table(OriginalWidth=1920, OriginalHeight=1080)
            if t.kind == "TextPlus":
                it["StyledText"] = lua.table(Value=t.inputs.get("StyledText", "")
                                             if isinstance(t.inputs.get("StyledText"), str) else "")
            tbl[t.name] = it
        return tbl

    for rend in (29, 119):
        for frame in range(0, rend + 1, 3):
            tools = build_tools(frame, rend)
            for t, k, code in exprs:
                # Inside a tool, bare names refer to its own inputs.
                own = tools[t.name]
                ltools = lua.table()
                for kk, vv in tools.items():
                    ltools[kk] = vv
                for kk, vv in own.items():
                    if kk not in ltools:
                        ltools[kk] = vv
                try:
                    res = runner.run(code, ltools, frame, 0, rend)
                except Exception as ex:  # noqa: BLE001
                    raise AssertionError(f"{macro.name}: {t.name}.{k} @f{frame}: {ex}\n{code}") from ex
                if k in ("StyledText",):
                    assert res is not None and "Value" in list(res.keys()), \
                        f"{macro.name}: {t.name}.{k} must return Text()"
                elif k in ("Center", "Pivot"):
                    assert res is not None and res["X"] is not None, f"{macro.name}: {t.name}.{k} not a Point"
                    assert res["X"] == res["X"] and res["Y"] == res["Y"], f"{macro.name}: NaN point"
                else:
                    assert isinstance(res, (int, float)), f"{macro.name}: {t.name}.{k} returned {res!r}"
                    assert res == res and abs(res) < 1e7, f"{macro.name}: {t.name}.{k} = {res}"


def validate_lua_syntax(lua, text, name):
    stub = lua.eval("""function(src)
        local mt = {__index = function(_, k)
            if k == 'ordered' then return function() return function(t) return t end end end
            return function(t) return t end
        end}
        local env = setmetatable({}, mt)
        local f, err = load('return ' .. src, 'setting', 't', env)
        if not f then return err end
        local ok, res = pcall(f)
        if not ok then return res end
        if type(res) ~= 'table' or type(res.Tools) ~= 'table' then return 'no Tools table' end
        return nil
    end""")
    err = stub(text)
    assert err is None, f"{name}: Lua parse error: {err}"


# --------------------------------------------------------------------------- #
# Icons
# --------------------------------------------------------------------------- #
def font(size, bold=True):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_icon(path, label, category):
    w, h = 208, 116
    img = Image.new("RGB", (w, h), (24, 24, 28))
    d = ImageDraw.Draw(img)
    col = CATEGORY_COLORS[category]
    d.rectangle([0, 0, w, 10], fill=col)
    d.text((8, 16), "YTK", font=font(14), fill=col)
    words, lines, cur = label.split(), [], ""
    for wd in words:
        if len(cur + " " + wd) > 14 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    y = 40 if len(lines) < 3 else 34
    for ln in lines[:3]:
        d.text((8, y), ln, font=font(20), fill=(245, 245, 245))
        y += 25
    img.save(path)


# --------------------------------------------------------------------------- #
WHERE = {
    "Titles": ("Titoli", "Effects Library → Toolbox → Titles → Fusion Titles",
               "Trascinalo su una traccia video **sopra** la clip (es. V2)."),
    "Transitions": ("Transizioni", "Effects Library → Toolbox → Video Transitions → Fusion Transitions",
                    "Trascinala sul **punto di taglio** tra due clip."),
    "Effects": ("Effetti", "Effects Library → Toolbox → Effects",
                "Trascinalo **sopra la clip** (o su un Adjustment Clip per applicarlo a più clip)."),
    "Generators": ("Generatori", "Effects Library → Toolbox → Generators → Fusion Generators",
                   "Trascinalo su una traccia video sopra il resto."),
}


def write_catalog():
    L = ["# Catalogo YouTube Kit", "",
         "_File generato automaticamente da `build/build_all.py`._", ""]
    for cat, (it, where, how) in WHERE.items():
        L += [f"## {it}", "", f"**Dove lo trovi:** {where}  ", f"**Come si usa:** {how}", "",
              "| Nome | Cosa fa |", "|---|---|"]
        L += [f"| {label} | {desc} |" for c, label, _, desc in CATALOG if c == cat]
        L.append("")
    L += ["## Effetti sonori (cartella `SFX/`)", "",
          "Trascina il file `.wav` dal Media Pool su una traccia audio (A2, A3...).", "",
          "| File | Categoria | Quando usarlo |", "|---|---|---|"]
    L += [f"| `{cat}/{name}.wav` | {cat} | {desc} |" for cat, name, _, desc in sfx.SOUNDS]
    L += ["", "## LUT colore (cartella `LUT/`)", "",
          "Gli stessi look sono disponibili anche come **effetti trascinabili** (`YTK Look ...`).", "",
          "| File | Look |", "|---|---|"]
    L += [f"| `YTK_{k}.cube` | {label}: {desc} |" for k, label, desc in LOOKS]
    (ROOT / "CATALOGO.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    import lupa

    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    runner = lua.execute(MOCK_ENV)

    if TEMPLATES.exists():
        shutil.rmtree(TEMPLATES)
    for d in ("LUT", "SFX", "dist"):
        if (ROOT / d).exists():
            shutil.rmtree(ROOT / d)

    # LUTs -----------------------------------------------------------------
    (ROOT / "LUT").mkdir(parents=True)
    fx_dir = TEMPLATES / "Effects" / PACK
    fx_dir.mkdir(parents=True)
    for key, label, _ in LOOKS:
        text = luts.cube_text(key, label)
        (ROOT / "LUT" / f"YTK_{key}.cube").write_text(text)
        (fx_dir / f"YTK_{key}.cube").write_text(text)
    print(f"LUT: {len(LOOKS)}")

    # Fusion templates ------------------------------------------------------
    count = {}
    for category, label, builder, _desc in CATALOG:
        macro = builder()
        validate(macro, lua, runner)
        text = macro.render()
        validate_lua_syntax(lua, text, label)
        folder = TEMPLATES / category / PACK
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{label}.setting").write_text(text, encoding="utf-8")
        make_icon(folder / f"{label}.png", label.replace("YTK ", ""), category)
        count[category] = count.get(category, 0) + 1
    print("Template:", count)

    # SFX -------------------------------------------------------------------
    n = 0
    for cat, name, fn, _desc in sfx.SOUNDS:
        folder = ROOT / "SFX" / cat
        folder.mkdir(parents=True, exist_ok=True)
        sfx.write_wav(folder / f"{name}.wav", fn())
        n += 1
    print(f"SFX: {n}")

    write_catalog()

    # DRFX bundle -----------------------------------------------------------
    (ROOT / "dist").mkdir()
    drfx = ROOT / "dist" / "YouTubeKit.drfx"
    with zipfile.ZipFile(drfx, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(TEMPLATES.rglob("*")):
            if f.is_file():
                z.write(f, Path("Edit") / f.relative_to(TEMPLATES))
    print(f"DRFX: {drfx.relative_to(ROOT)} ({drfx.stat().st_size // 1024} KB)")

    # Everything in one zip for easy download ------------------------------
    full = ROOT / "dist" / "YouTubeKit-completo.zip"
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("Templates", "LUT", "SFX"):
            for f in sorted((ROOT / sub).rglob("*")):
                if f.is_file():
                    z.write(f, Path("YouTubeKit") / f.relative_to(ROOT))
        for name in ("README.md", "CATALOGO.md", "installa_windows.bat", "installa_mac.command"):
            if (ROOT / name).exists():
                z.write(ROOT / name, Path("YouTubeKit") / name)
        z.write(drfx, Path("YouTubeKit") / drfx.name)
    print(f"ZIP: {full.relative_to(ROOT)} ({full.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
