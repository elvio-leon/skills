"""Simulatore minimo dei nodi Fusion usati da Moviola, per vedere i template senza Resolve.

Interpreta il grafo di una Macro (fusion.py): valuta le espressioni Lua con lupa
fotogramma per fotogramma e disegna con numpy/PIL i nodi Background, Merge,
Transform, Dissolve, maschere (rettangolo, ellisse, poligono, bitmap), Text+,
FastNoise, Blur, correzioni colore. Serve a controllare impaginazione e tempi:
non è una copia esatta del motore di Resolve.

Convenzioni Fusion rispettate: coordinate normalizzate 0..1 con y verso l'alto,
punti dei poligoni normalizzati sulla larghezza (Y * W/H), Text+ Size relativo
alla larghezza del fotogramma, write-on dei poligoni = segmento centrato su
WritePosition lungo WriteLength.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from fusion import Conn, Expr, Raw

FONT_DIR = Path(__file__).resolve().parent.parent / "Font"
FONTS = {
    ("Anton", "Regular"): "Anton-400.ttf", ("Inter", "Regular"): "Inter-400.ttf", ("Inter", "Bold"): "Inter-700.ttf",
    ("Permanent Marker", "Regular"): "PermanentMarker-400.ttf", ("Playfair Display", "Italic"): "PlayfairDisplay-400i.ttf",
    ("Playfair Display", "Bold"): "PlayfairDisplay-700.ttf", ("Playfair Display", "Bold Italic"): "PlayfairDisplay-700i.ttf",
    ("Shadows Into Light Two", "Regular"): "ShadowsIntoLightTwo-400.ttf", ("Special Elite", "Regular"): "SpecialElite-400.ttf",
    ("UnifrakturMaguntia", "Book"): "UnifrakturMaguntia-400.ttf", ("VT323", "Regular"): "VT323-400.ttf",
}

LUA_PRELUDE = r"""
local M = {}
if math.atan2 == nil then math.atan2 = function(y, x) return math.atan(y, x) end end
function M.mkproxy(cb, name)
  return setmetatable({}, {__index = function(_, k) return cb(name, k) end})
end
function M.Point(x, y) return {X = x, Y = y, _point = true} end
function M.Text(s) return {Value = s, _text = true} end
function M.run(body, resolve, t, rs, re)
  local env = {
    time = t, comp = {RenderStart = rs, RenderEnd = re, CurrentTime = t},
    min = math.min, max = math.max, sin = math.sin, cos = math.cos, tan = math.tan, abs = math.abs,
    floor = math.floor, ceil = math.ceil, exp = math.exp, sqrt = math.sqrt, pi = math.pi, log = math.log,
    random = math.random, randomseed = math.randomseed, math = math, string = string, table = table,
    tostring = tostring, tonumber = tonumber, pairs = pairs, ipairs = ipairs, type = type,
    Point = M.Point, Text = M.Text, atan2 = function(y, x) return math.atan(y, x) end,
    iif = function(c, a, b) if c and c ~= 0 then return a else return b end end,
  }
  setmetatable(env, {__index = function(_, k) return resolve(k) end})
  local f, err = load(body, "expr", "t", env)
  if not f then error("syntax: " .. err) end
  return f()
end
return M
"""


class Sim:
    def __init__(self, macro, lua, W=960, H=540, rend=100, images=None):
        self.m, self.lua, self.W, self.H, self.rend = macro, lua, W, H, rend
        self.tools = {t.name: t for t in macro.tools}
        self.L = lua.execute(LUA_PRELUDE)
        self.images = images or {}
        self.main = {(tool, src): label for tool, src, label in macro.main_inputs}
        self.overrides = {}

    # ------------------------------------------------------------------ values
    def set(self, tool, key, value):
        self.overrides[(tool, key)] = value

    def frame(self, f):
        self.f = f
        self.vcache, self.icache, self.mcache = {}, {}, {}
        img = self.render(self.m.output)
        return img

    def to_lua(self, v):
        if isinstance(v, tuple) and len(v) == 2:
            return self.lua.table(X=v[0], Y=v[1])
        if isinstance(v, str):
            return self.lua.table(Value=v)
        if isinstance(v, dict):
            return self.lua.table(**v)
        return v

    def from_lua(self, r):
        if r is None:
            return 0
        if isinstance(r, (int, float, bool)):
            return float(r)
        try:
            keys = list(r.keys())
        except Exception:  # noqa: BLE001
            return r
        if "X" in keys:
            return (float(r["X"]), float(r["Y"]))
        if "Value" in keys:
            return str(r["Value"])
        return 0

    def get(self, tname, key):
        ck = (tname, key)
        if ck in self.vcache:
            return self.vcache[ck]
        self.vcache[ck] = 0  # guard against cycles
        t = self.tools[tname]
        if ck in self.overrides:
            v = self.overrides[ck]
        elif key in t.inputs:
            v = t.inputs[key]
            if isinstance(v, Expr):
                v = self.eval(t, v.code)
            elif isinstance(v, Conn):
                if v.output == "Value":
                    src = self.tools[v.tool]
                    if src.kind == "LUTLookup":
                        v = min(max(self.f / max(self.rend, 1), 0), 1)
                    else:
                        v = self.get(v.tool, "Value")
                else:
                    v = {"OriginalWidth": 1920, "OriginalHeight": 1080}
            elif isinstance(v, Raw):
                v = v
            elif isinstance(v, bool):
                v = float(v)
        elif key in t.controls:
            v = t.controls[key].get("INP_Default", 0)
        else:
            v = self.default(t, key)
        self.vcache[ck] = v
        return v

    def default(self, t, key):
        if key in ("Center", "Pivot"):
            return (0.5, 0.5)
        if key in ("Background", "Foreground", "Input"):
            return {"OriginalWidth": 1920, "OriginalHeight": 1080}
        d = {"Size": 1, "Blend": 1, "Mix": 0, "Angle": 0, "Width": 0.5 if "Mask" in t.kind else 1920,
             "Height": 0.5 if "Mask" in t.kind else 1080, "Level": 1, "SoftEdge": 0, "Solid": 1, "BorderWidth": 0,
             "Invert": 0, "WriteLength": 1, "WritePosition": 0.5, "Start": 0, "End": 1, "CharacterSpacing": 1,
             "LineSpacing": 1, "Alpha1": 1, "Red1": 1, "Green1": 1, "Blue1": 1, "TopLeftAlpha": 1, "Gain": 1,
             "Saturation": 1, "Contrast": 0, "Brightness": 0, "Gamma": 1, "Lift": 0, "XScale": 10, "Detail": 3,
             "SeetheRate": 0, "Seethe": 0, "XBlurSize": 0, "Length": 0, "CornerRadius": 0, "HorizontalLeftCenterRight": 0,
             "Low": 0, "High": 1, "StyledText": "", "Font": "Inter", "Style": "Regular"}
        return d.get(key, 0)

    def eval(self, t, code):
        body = code[1:] if code.startswith(":") else "return " + code

        def resolve(k):
            if k in t.inputs or k in t.controls:
                return self.to_lua(self.get(t.name, k))
            if k in self.tools:
                return self.L.mkproxy(lambda n, kk: self.to_lua(self.get(n, kk)), k)
            if k in ("Center", "Pivot", "Size", "Angle", "Blend"):
                return self.to_lua(self.get(t.name, k))
            raise KeyError(f"nome non definito nell'espressione di {t.name}: {k}")
        try:
            r = self.L.run(body, resolve, self.f, 0, self.rend)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"{self.m.name}: {t.name} @f{self.f}: {ex}\n{code}") from ex
        return self.from_lua(r)

    def num(self, t, k):
        v = self.get(t, k)
        return float(v) if isinstance(v, (int, float)) else 0.0

    def pt(self, t, k):
        v = self.get(t, k)
        return v if isinstance(v, tuple) else (0.5, 0.5)

    # ------------------------------------------------------------------ images
    def blank(self):
        return np.zeros((self.H, self.W, 4), np.float32)

    def input_img(self, t, key):
        v = t.inputs.get(key)
        if isinstance(v, Conn) and v.output != "Value" and v.tool in self.tools and self.tools[v.tool].kind not in ("LUTLookup",):
            return self.render(v.tool)
        if (t.name, key) in self.main:
            lab = self.main[(t.name, key)]
            if lab in self.images:
                return self.images[lab]
            return self.images.get("_default", self.blank())
        return None

    def mask_of(self, t):
        v = t.inputs.get("EffectMask")
        if isinstance(v, Conn):
            return self.mask(v.tool)
        return None

    def render(self, name):
        if name in self.icache:
            return self.icache[name]
        t = self.tools[name]
        k = t.kind
        fn = getattr(self, "r_" + k, None)
        if fn is None:
            img = self.input_img(t, "Input")
            img = img if img is not None else self.blank()
        else:
            img = fn(t)
        self.icache[name] = img
        return img

    # --- generators
    def r_Background(self, t):
        c = [self.num(t.name, k) for k in ("TopLeftRed", "TopLeftGreen", "TopLeftBlue", "TopLeftAlpha")]
        a = c[3]
        img = np.empty((self.H, self.W, 4), np.float32)
        img[...] = (c[0] * a, c[1] * a, c[2] * a, a)
        m = self.mask_of(t)
        if m is not None:
            img *= m[..., None]
        return img

    def r_FastNoise(self, t):
        sc = max(self.num(t.name, "XScale"), 0.01)
        det = int(max(1, min(8, round(self.num(t.name, "Detail") or 3))))
        con = self.num(t.name, "Contrast") or 1
        bri = self.num(t.name, "Brightness")
        seethe = self.num(t.name, "Seethe") + self.num(t.name, "SeetheRate") * self.f
        cx, cy = self.pt(t.name, "Center")
        lock = t.inputs.get("LockXY", 1)
        ysc = self.num(t.name, "YScale") if not lock and "YScale" in t.inputs else sc
        h, w = self.H, self.W
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        u = (xs / w - cx) * sc * 1.2
        v = ((h - ys) / w - (cy - 0.5) * h / w) * ysc * 1.2
        acc, amp, tot = np.zeros((h, w), np.float32), 1.0, 0.0
        for o in range(det):
            acc += amp * _vnoise(u * 2 ** o + o * 17.3, v * 2 ** o + o * 5.1, seethe * (1 + o * .3))
            tot += amp
            amp *= 0.5
        n = acc / tot
        n = np.clip((n - 0.5) * con * 2.2 + 0.5 + bri, 0, 1)
        c1 = [self.num(t.name, k) if k in t.inputs else d for k, d in zip(("Color1Red", "Color1Green", "Color1Blue", "Color1Alpha"), (0, 0, 0, 1))]
        c2 = [self.num(t.name, k) if k in t.inputs else d for k, d in zip(("Color2Red", "Color2Green", "Color2Blue", "Color2Alpha"), (1, 1, 1, 1))]
        img = np.empty((h, w, 4), np.float32)
        for i in range(4):
            img[..., i] = c1[i] + (c2[i] - c1[i]) * n
        img[..., :3] *= img[..., 3:4]
        m = self.mask_of(t)
        if m is not None:
            img *= m[..., None]
        return img

    def r_TextPlus(self, t):
        txt = str(self.get(t.name, "StyledText") or "")
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if txt:
            fam, sty = str(self.get(t.name, "Font")), str(self.get(t.name, "Style"))
            path = FONT_DIR / FONTS.get((fam, sty), FONTS.get((fam, "Regular"), "Inter-400.ttf"))
            px = max(2, int(round(self.num(t.name, "Size") * self.W)))
            font = ImageFont.truetype(str(path), px)
            cs = self.num(t.name, "CharacterSpacing") or 1
            ls = self.num(t.name, "LineSpacing") or 1
            asc, desc = font.getmetrics()
            lh = (asc + desc) * ls
            lines = txt.split("\n")
            n = len(txt.replace("\n", ""))
            s0, s1 = self.num(t.name, "Start"), self.num(t.name, "End")
            vis0, vis1 = int(round(s0 * n)), int(round(s1 * n))
            col = tuple(int(255 * min(max(self.num(t.name, k), 0), 1)) for k in ("Red1", "Green1", "Blue1")) + (int(255 * self.num(t.name, "Alpha1")),)
            d = ImageDraw.Draw(img)
            cx, cy = self.pt(t.name, "Center")
            hal = self.num(t.name, "HorizontalLeftCenterRight")
            widths = [sum(font.getlength(ch) * cs for ch in ln) for ln in lines]
            blockh = lh * len(lines)
            y0 = (1 - cy) * self.H - blockh / 2
            idx = 0
            outline = t.inputs.get("Enabled2") and self.num(t.name, "Thickness2") > 0
            ow = self.num(t.name, "Thickness2") * self.W * 0.5 if outline else 0
            ocol = tuple(int(255 * min(max(self.num(t.name, k), 0), 1)) for k in ("Red2", "Green2", "Blue2")) + (255,)
            for li, ln in enumerate(lines):
                wln = widths[li]
                x = cx * self.W - (0 if hal < -0.5 else (wln if hal > 0.5 else wln / 2))
                for ch in ln:
                    if vis0 <= idx < vis1:
                        if outline:
                            d.text((x, y0 + li * lh), ch, font=font, fill=(0, 0, 0, 0), stroke_width=max(1, int(ow)), stroke_fill=ocol)
                        if col[3] > 0:
                            d.text((x, y0 + li * lh), ch, font=font, fill=col)
                    x += font.getlength(ch) * cs
                    idx += 1
        a = np.asarray(img, np.float32) / 255
        a[..., :3] *= a[..., 3:4]
        if t.inputs.get("Enabled3"):
            sh = a[..., 3]
            soft = self.num(t.name, "SoftnessX3") or 6
            sp = Image.fromarray((sh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(soft * self.W / 1920))
            off = self.get(t.name, "Offset3")
            ox, oy = (off if isinstance(off, tuple) else (0, 0))
            sp = np.roll(np.asarray(sp, np.float32) / 255, (int(-oy * self.H), int(ox * self.W)), (0, 1)) * self.num(t.name, "Alpha3")
            shadow = np.zeros_like(a)
            shadow[..., 3] = sp
            a = a + shadow * (1 - a[..., 3:4])
        m = self.mask_of(t)
        if m is not None:
            a *= m[..., None]
        return a

    # --- compositing
    def xform(self, img, cx, cy, size, ang, pivot=(0.5, 0.5), edges=0):
        if img is None:
            return self.blank()
        if abs(size - 1) < 1e-6 and abs(ang) < 1e-6 and abs(cx - 0.5) < 1e-6 and abs(cy - 0.5) < 1e-6:
            return img
        W, H = self.W, self.H
        px, py = pivot[0] * W, (1 - pivot[1]) * H
        tx, ty = (cx - 0.5) * W, -(cy - 0.5) * H
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        # output -> input inverse map: p_in = R^-1 (p_out - t - pivot)/s + pivot (y down: rotation sign flips)
        s = max(size, 1e-4)
        A = ca / s
        B = -sa / s
        D = sa / s
        E = ca / s
        ox, oy = px + tx, py + ty
        coeffs = (A, B, px - A * ox - B * oy, D, E, py - D * ox - E * oy)
        out = np.empty_like(img)
        for i in range(4):
            ch = Image.fromarray(img[..., i])
            out[..., i] = np.asarray(ch.transform((W, H), Image.AFFINE, coeffs, resample=Image.BILINEAR, fillcolor=0))
        if edges in (2, 3):
            yy, xx = np.mgrid[0:H, 0:W]
            sx = A * xx + B * yy + coeffs[2]
            sy = D * xx + E * yy + coeffs[5]
            if edges == 3:
                sx = np.abs(((sx % (2 * W)) + 2 * W) % (2 * W))
                sx = np.where(sx >= W, 2 * W - sx - 1, sx)
                sy = np.abs(((sy % (2 * H)) + 2 * H) % (2 * H))
                sy = np.where(sy >= H, 2 * H - sy - 1, sy)
            sx = np.clip(sx, 0, W - 1).astype(int)
            sy = np.clip(sy, 0, H - 1).astype(int)
            out = img[sy, sx]
        return out

    def r_Transform(self, t):
        src = self.input_img(t, "Input")
        if src is None:
            src = self.blank()
        cx, cy = self.pt(t.name, "Center")
        out = self.xform(src, cx, cy, self.num(t.name, "Size") or 1, self.num(t.name, "Angle"), self.pt(t.name, "Pivot"),
                         int(t.inputs.get("Edges", 0) if not isinstance(t.inputs.get("Edges"), Expr) else 0))
        if t.inputs.get("FlipVert"):
            out = out[::-1]
        m = self.mask_of(t)
        if m is not None:
            out = src + (out - src) * m[..., None]
        return out

    def r_Merge(self, t):
        bg = self.input_img(t, "Background")
        fg = self.input_img(t, "Foreground")
        bg = bg if bg is not None else self.blank()
        if fg is None:
            return bg
        cx, cy = self.pt(t.name, "Center")
        fg = self.xform(fg, cx, cy, self.num(t.name, "Size") or 1, self.num(t.name, "Angle"))
        blend = self.num(t.name, "Blend") if "Blend" in t.inputs else 1.0
        mode = t.inputs.get("ApplyMode")
        mode = mode.code.split('"')[1] if isinstance(mode, Raw) else "Normal"
        fa = fg[..., 3:4]
        if mode == "Screen":
            rgb = 1 - (1 - bg[..., :3]) * (1 - fg[..., :3])
            out = np.concatenate([rgb, np.maximum(bg[..., 3:4], fa)], -1)
        elif mode == "Multiply":
            rgb = bg[..., :3] * (fg[..., :3] + (1 - fa))
            out = np.concatenate([rgb, bg[..., 3:4]], -1)
        elif mode == "Overlay":
            b = bg[..., :3]
            f = fg[..., :3]
            o = np.where(b < 0.5, 2 * b * f, 1 - 2 * (1 - b) * (1 - f))
            rgb = b + (o - b) * fa
            out = np.concatenate([rgb, bg[..., 3:4]], -1)
        elif mode == "Add":
            out = np.concatenate([np.minimum(bg[..., :3] + fg[..., :3], 1), np.maximum(bg[..., 3:4], fa)], -1)
        else:
            out = fg + bg * (1 - fa)
        out = bg + (out - bg) * blend
        m = self.mask_of(t)
        if m is not None:
            out = bg + (out - bg) * m[..., None]
        return out

    def r_Dissolve(self, t):
        a = self.input_img(t, "Background")
        b = self.input_img(t, "Foreground")
        a = a if a is not None else self.blank()
        b = b if b is not None else self.blank()
        mix = min(max(self.num(t.name, "Mix"), 0), 1)
        return a + (b - a) * mix

    def _blur(self, img, sigma):
        if sigma < 0.3:
            return img
        from scipy.ndimage import gaussian_filter
        return gaussian_filter(img, (sigma, sigma, 0))

    def r_Blur(self, t):
        src = self.input_img(t, "Input")
        src = src if src is not None else self.blank()
        out = self._blur(src, self.num(t.name, "XBlurSize") * self.W / 1920 * 0.6)
        m = self.mask_of(t)
        return out if m is None else src + (out - src) * m[..., None]

    def r_DirectionalBlur(self, t):
        src = self.input_img(t, "Input")
        src = src if src is not None else self.blank()
        L = self.num(t.name, "Length")
        if L < 0.002:
            return src
        typ = int(t.inputs.get("Type", 0)) if not isinstance(t.inputs.get("Type"), Expr) else 0
        acc = np.zeros_like(src)
        n = 7
        for i in range(n):
            k = (i / (n - 1) - 0.5) * L
            if typ == 3:
                acc += self.xform(src, 0.5, 0.5, 1 + k, 0)
            else:
                ang = math.radians(self.num(t.name, "Angle"))
                acc += np.roll(src, (int(-math.sin(ang) * k * self.W), int(math.cos(ang) * k * self.W)), (0, 1))
        return acc / n

    def _cc(self, t, src, gain=1, lift=0, gamma=1, con=0, bri=0, sat=1, rgbgain=(1, 1, 1)):
        a = np.clip(src[..., 3:4], 1e-5, None)
        rgb = src[..., :3] / a
        rgb = rgb * gain * np.array(rgbgain, np.float32) + lift + bri
        rgb = (rgb - 0.5) * (1 + con) + 0.5
        rgb = np.clip(rgb, 0, None) ** (1 / max(gamma, 0.01))
        luma = (rgb * [0.299, 0.587, 0.114]).sum(-1, keepdims=True)
        rgb = luma + (rgb - luma) * sat
        out = np.concatenate([np.clip(rgb, 0, 4) * src[..., 3:4], src[..., 3:4]], -1)
        m = self.mask_of(t)
        return out if m is None else src + (out - src) * m[..., None]

    def r_BrightnessContrast(self, t):
        src = self.input_img(t, "Input")
        src = src if src is not None else self.blank()
        g = lambda k, d: self.num(t.name, k) if k in t.inputs else d  # noqa: E731
        return self._cc(t, src, g("Gain", 1), g("Lift", 0), g("Gamma", 1), g("Contrast", 0), g("Brightness", 0), g("Saturation", 1))

    def r_ColorGain(self, t):
        src = self.input_img(t, "Input")
        src = src if src is not None else self.blank()
        g = lambda k, d: self.num(t.name, k) if k in t.inputs else d  # noqa: E731
        return self._cc(t, src, g("MasterRGBGain", 1), 0, 1, 0, 0, g("MasterSaturation", 1) if "MasterSaturation" in t.inputs else 1,
                        (g("GainRed", 1), g("GainGreen", 1), g("GainBlue", 1)))

    def r_FilmGrain(self, t):
        src = self.input_img(t, "Input")
        src = src if src is not None else self.blank()
        s = self.num(t.name, "MasterStrength") or 0.05
        rng = np.random.default_rng(self.f)
        n = rng.standard_normal((self.H, self.W, 1)).astype(np.float32) * s
        out = src.copy()
        out[..., :3] = np.clip(src[..., :3] + n * src[..., 3:4], 0, None)
        return out

    # --- masks
    def mask(self, name):
        if name in self.mcache:
            return self.mcache[name]
        t = self.tools[name]
        W, H = self.W, self.H
        k = t.kind
        if k == "BitmapMask":
            src = self.input_img(t, "Image")
            src = src if src is not None else self.blank()
            lum = (src[..., :3] * [0.299, 0.587, 0.114]).sum(-1)
            lo, hi = self.num(name, "Low"), (self.num(name, "High") if "High" in t.inputs else 1)
            m = np.clip((lum - lo) / max(hi - lo, 1e-4), 0, 1).astype(np.float32)
        else:
            ss = 2
            im = Image.new("L", (W * ss, H * ss), 0)
            d = ImageDraw.Draw(im)
            cx, cy = self.pt(name, "Center")
            pcx, pcy = cx * W * ss, (1 - cy) * H * ss
            solid = self.num(name, "Solid") if "Solid" in t.inputs else 1
            bw = self.num(name, "BorderWidth") * W * ss
            ang = self.num(name, "Angle") if "Angle" in t.inputs else 0
            if k in ("RectangleMask", "EllipseMask"):
                w = abs(self.num(name, "Width") if "Width" in t.inputs else 0.5) * W * ss
                h = abs(self.num(name, "Height") if "Height" in t.inputs else 0.5) * H * ss
                if k == "RectangleMask":
                    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
                else:
                    pts = [(w / 2 * math.cos(a), h / 2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 120, endpoint=False)]
                a = math.radians(ang)
                P = [(pcx + x * math.cos(a) + y * math.sin(a), pcy - x * math.sin(a) + y * math.cos(a)) for x, y in pts]
                if solid >= 0.5:
                    d.polygon(P, fill=255)
                    if bw > 0:
                        d.line(P + [P[0]], fill=255, width=int(max(1, bw)))
                else:
                    d.line(P + [P[0]], fill=255, width=int(max(1, bw)), joint="curve")
            elif k == "PolylineMask":
                pl = t.inputs.get("Polyline")
                pts, closed = _parse_poly(pl.code if isinstance(pl, Raw) else "")
                a = math.radians(ang)
                P = []
                for x, y in pts:
                    xr, yr = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
                    P.append((pcx + xr * W * ss, pcy - yr * W * ss))
                wl = self.num(name, "WriteLength") if "WriteLength" in t.inputs else 1
                wp = self.num(name, "WritePosition") if "WritePosition" in t.inputs else 0.5
                if wl < 0.999 and len(P) > 1:
                    P = _subpath(P + ([P[0]] if closed else []), wp - wl / 2, wp + wl / 2)
                    closed = False
                if len(P) > 1:
                    if solid >= 0.5 and closed:
                        d.polygon(P, fill=255)
                    else:
                        d.line(P + ([P[0]] if closed else []), fill=255, width=int(max(1, bw)), joint="curve")
            soft = self.num(name, "SoftEdge") * W * ss
            if soft > 0.5:
                im = im.filter(ImageFilter.GaussianBlur(soft * 0.6))
            im = im.resize((W, H), Image.BILINEAR)
            m = np.asarray(im, np.float32) / 255
        m = m * (self.num(name, "Level") if "Level" in t.inputs else 1)
        if t.inputs.get("Invert"):
            m = 1 - m
        prev = t.inputs.get("EffectMask")
        if isinstance(prev, Conn):
            pm = self.mask(prev.tool)
            mode = t.inputs.get("PaintMode")
            mode = mode.code.split('"')[1] if isinstance(mode, Raw) else "Merge"
            if mode == "Subtract":
                m = np.clip(pm - m, 0, 1)
            elif mode == "Minimum":
                m = np.minimum(pm, m)
            elif mode == "Multiply":
                m = pm * m
            else:
                m = np.maximum(pm, m)
        self.mcache[name] = m
        return m


def _parse_poly(code):
    import re
    closed = "Closed = true" in code
    pts = [(float(a), float(b)) for a, b in re.findall(r"X = (-?[\d.e-]+), Y = (-?[\d.e-]+)", code)]
    return pts, closed


def _subpath(P, a, b):
    a, b = max(0, a), min(1, b)
    seg = [math.dist(P[i], P[i + 1]) for i in range(len(P) - 1)]
    tot = sum(seg) or 1
    out, acc = [], 0
    for i, s in enumerate(seg):
        s0, s1 = acc / tot, (acc + s) / tot
        if s1 >= a and s0 <= b:
            u0 = max(0, (a - s0) / max(s1 - s0, 1e-9))
            u1 = min(1, (b - s0) / max(s1 - s0, 1e-9))
            p0 = (P[i][0] + (P[i + 1][0] - P[i][0]) * u0, P[i][1] + (P[i + 1][1] - P[i][1]) * u0)
            p1 = (P[i][0] + (P[i + 1][0] - P[i][0]) * u1, P[i][1] + (P[i + 1][1] - P[i][1]) * u1)
            if not out:
                out.append(p0)
            out.append(p1)
        acc += s
    return out


_PERM = np.random.default_rng(3).random(4096).astype(np.float32)


def _h(ix, iy, iz):
    return _PERM[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791) & 4095]


def _vnoise(x, y, z=0.0):
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    iz = int(math.floor(z))
    fz = z - iz
    ux, uy, uz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    out = 0
    for dz, wz in ((0, 1 - uz), (1, uz)):
        a, b = _h(ix, iy, iz + dz), _h(ix + 1, iy, iz + dz)
        c, d = _h(ix, iy + 1, iz + dz), _h(ix + 1, iy + 1, iz + dz)
        out = out + wz * ((a + (b - a) * ux) * (1 - uy) + (c + (d - c) * ux) * uy)
    return out


def to_pil(img, bg=(40, 44, 42)):
    a = img[..., 3:4]
    rgb = img[..., :3] + np.array(bg, np.float32)[None, None] / 255 * (1 - a)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def checker(W, H, n=24):
    yy, xx = np.mgrid[0:H, 0:W]
    c = ((xx // n + yy // n) % 2).astype(np.float32)
    g = 0.16 + 0.05 * c
    return np.stack([g, g * 1.04, g * 1.02, np.ones_like(g)], -1).astype(np.float32)
