"""Costruisce il pack Moviola per DaVinci Resolve.

    python3 build.py

Per ogni template: genera il .setting, controlla che si legga come Lua,
che ogni collegamento punti a un nodo esistente e che ogni espressione giri
senza errori su più fotogrammi (simulatore sim.py), poi disegna l'icona da un
fotogramma reale dell'animazione. Produce:
    dist/Moviola.drfx, dist/Moviola-60fps.drfx, dist/Moviola-completo.zip
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import lupa
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import fusion  # noqa: E402
import sfx  # noqa: E402
from fusion import Conn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PACK = "Moviola"


def check_lua(lua, text, name):
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
    assert err is None, f"{name}: errore Lua: {err}"


def check_links(m):
    names = {t.name for t in m.tools}
    assert m.output in names, f"{m.name}: uscita mancante"
    for t in m.tools:
        for k, v in t.inputs.items():
            if isinstance(v, Conn):
                assert v.tool in names, f"{m.name}: {t.name}.{k} -> {v.tool} non esiste"
    for e in m.exposed:
        assert e.tool in names, f"{m.name}: controllo su {e.tool} che non esiste"
    for tool, src, _ in m.main_inputs:
        assert tool in names, f"{m.name}: ingresso {tool} mancante"


def render_icon(item, lua, path):
    import preview
    from sim import Sim, to_pil
    cat, label, builder, desc, opts = item
    m = builder()
    W, H = 416, 234
    foto = preview.load(preview.HERE / "sample_foto.jpg", W, H)
    rit = preview.load(preview.HERE / "sample_ritratto.jpg", W, H)
    imgs = {"_default": rit if "Scheda" in label else foto, "Clip in uscita": foto,
            "Clip in entrata": rit * np.array([0.7, 0.9, 1.0, 1.0], np.float32)}
    length = opts.get("len", 120)
    sim = Sim(m, lua, W, H, rend=length, images=imgs)
    fr = opts.get("icon", 0.55 if cat != "Transitions" else 0.42)
    errs = []
    for f in (0, int(length * 0.3), int(length * fr), length - 1):   # le espressioni devono girare ovunque
        img = sim.frame(f)
    img = sim.frame(int(length * fr))
    if cat == "Titles":
        base = foto.copy()
        base[..., :3] *= 0.8
        img = img + base * (1 - img[..., 3:4])
    to_pil(img).resize((208, 116), Image.LANCZOS).save(path)
    return errs


def write_templates(lua, out, fps60=False):
    import catalog
    fusion.K = 60 / 25 if fps60 else 1.0
    folder_name = PACK + (" 60fps" if fps60 else "")
    count = {}
    try:
        for item in catalog.ALL:
            cat, label, builder, desc, opts = item
            m = builder()
            fusion.scale_frame_controls(m)
            if fps60:
                label += " 60fps"
                m.name += "_60fps"
            check_links(m)
            text = m.render()
            check_lua(lua, text, label)
            d = out / cat / folder_name
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{label}.setting").write_text(text, encoding="utf-8")
            render_icon(item, lua, d / f"{label}.png")
            count[cat] = count.get(cat, 0) + 1
    finally:
        fusion.K = 1.0
    return count


def drfx(path, tdir):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(tdir.rglob("*")):
            if f.is_file():
                z.write(f, Path("Edit") / f.relative_to(tdir))
    print("DRFX", path.name, path.stat().st_size // 1024, "KB")


SOUNDS = [
    ("Transizioni", "whoosh", lambda: sfx.whoosh(), "Passaggio d'aria: sotto transizioni, barre e titoli che entrano"),
    ("Transizioni", "whoosh_lento", sfx.whoosh_slow, "Per Luce calda, Ken Burns e titoli lenti"),
    ("Impatti", "impatto", sfx.impact, "Il colpo dei titoli e di Impatto Trailer"),
    ("Impatti", "riser", lambda: sfx.riser(1.5), "Tensione che sale prima della prima battuta"),
    ("Archivio", "macchina_da_scrivere", lambda: sfx.typewriter_loop(4.0), "Sotto Macchina da Scrivere (taglialo alla lunghezza del testo)"),
    ("Archivio", "campanello_carrello", sfx.typewriter_ding, "A fine riga della macchina da scrivere"),
    ("Archivio", "otturatore", sfx.shutter, "Con Flash Magnesio e Foto sul Tavolo"),
    ("Archivio", "disturbo_vhs", lambda: sfx.glitch(0.9), "Con Disturbo VHS e Videocassetta"),
    ("Dati", "pop", sfx.pop, "Su ogni gol del Tabellino, sulle righe della Classifica"),
    ("Dati", "click", sfx.click, "Sui numeri che contano"),
]


def main():
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    tpl = ROOT / "Templates" / "Edit"
    if tpl.parent.exists():
        shutil.rmtree(tpl.parent)
    print("Template 25 fps:", write_templates(lua, tpl))
    drfx(DIST / "Moviola.drfx", tpl)
    with tempfile.TemporaryDirectory() as tmp:
        t60 = Path(tmp) / "Edit"
        print("Template 60 fps:", write_templates(lua, t60, fps60=True))
        drfx(DIST / "Moviola-60fps.drfx", t60)
    sdir = ROOT / "SFX"
    if sdir.exists():
        shutil.rmtree(sdir)
    for cat, name, fn, _ in SOUNDS:
        (sdir / cat).mkdir(parents=True, exist_ok=True)
        sfx.write_wav(sdir / cat / f"{name}.wav", fn())
    full = DIST / "Moviola-completo.zip"
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED) as z:
        for f in [DIST / "Moviola.drfx", DIST / "Moviola-60fps.drfx"]:
            z.write(f, Path("Moviola") / f.name)
        for sub in ("Font", "SFX", "Templates"):
            for f in sorted((ROOT / sub).rglob("*")):
                if f.is_file():
                    z.write(f, Path("Moviola") / f.relative_to(ROOT))
        for extra in ("LEGGIMI.md", "Installa Moviola.command"):
            p = ROOT / extra
            if p.exists():
                info = zipfile.ZipInfo(str(Path("Moviola") / extra))
                info.external_attr = (0o100755 << 16) if extra.endswith(".command") else (0o100644 << 16)
                z.writestr(info, p.read_bytes())
    print("ZIP", full.name, full.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
