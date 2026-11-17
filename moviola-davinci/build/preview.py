"""Anteprima dei template con il simulatore: python3 preview.py nome1,nome2 [uscita.jpg]

Per ogni template disegna alcuni fotogrammi (sopra una foto di prova) e li mette
in un foglio di provini. Serve solo al controllo durante lo sviluppo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import lupa
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import catalog  # noqa: E402
from sim import Sim, checker, to_pil  # noqa: E402

HERE = Path(__file__).parent
PW, PH = 640, 360


def load(path, w=PW, h=PH):
    im = Image.open(path).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s + 1), int(im.height * s + 1)))
    l, t = (im.width - w) // 2, (im.height - h) // 2
    a = np.asarray(im.crop((l, t, l + w, t + h)), np.float32) / 255
    return np.concatenate([a, np.ones((h, w, 1), np.float32)], -1)


def frames_for(item):
    cat, label, builder, desc, *rest = item
    opts = rest[0] if rest else {}
    return opts.get("frames", [0.15, 0.4, 0.7, 0.95]), opts.get("len", 150)


def render_item(item, lua, cols=4):
    cat, label, builder, desc, *rest = item
    m = builder()
    fr, length = frames_for(item)
    foto, rit = load(HERE / "sample_foto.jpg"), load(HERE / "sample_ritratto.jpg")
    b = foto.copy()
    b[..., :3] = b[..., :3] * 0.85
    imgs = {"_default": foto, "Clip in uscita": foto, "Clip in entrata": load(HERE / "sample_ritratto.jpg") * [0.7, 0.9, 1.0, 1.0]}
    if "Ritratto" in label or "Scheda" in label:
        imgs["_default"] = rit
    sim = Sim(m, lua, PW, PH, rend=length, images=imgs)
    tiles = []
    for f in fr:
        frame = int(round(f * length))
        img = sim.frame(frame)
        if cat == "Titles":
            base = b
            out = img + base * (1 - img[..., 3:4])
            pil = to_pil(out)
        else:
            pil = to_pil(img)
        d = ImageDraw.Draw(pil)
        d.rectangle([0, 0, 150, 16], fill=(0, 0, 0))
        d.text((4, 2), f"{label} f{frame}", fill=(255, 255, 0))
        tiles.append(pil)
    return tiles


def main():
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/preview.jpg"
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    items = [it for it in catalog.ALL if not names or any(n.lower() in it[1].lower() for n in names)]
    rows = []
    for it in items:
        try:
            rows.append(render_item(it, lua))
        except Exception as ex:  # noqa: BLE001
            print("ERRORE", it[1], ex)
            raise
    cols = max(len(r) for r in rows)
    sheet = Image.new("RGB", (cols * PW, len(rows) * PH), (20, 20, 20))
    for y, r in enumerate(rows):
        for x, t in enumerate(r):
            sheet.paste(t, (x * PW, y * PH))
    sheet.save(out, quality=85)
    print("ok", out, len(rows))


if __name__ == "__main__":
    main()
