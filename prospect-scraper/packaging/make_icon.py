"""Genera l'icona dell'app (PNG 1024×1024): quadrato arrotondato blu con lente d'ingrandimento."""

import sys

from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# Sfondo con leggero gradiente verticale, margini come le icone macOS (824 px utili).
m, r = 100, 185
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line([(0, y), (S, y)], fill=(int(64 - 30 * t), int(110 - 40 * t), int(200 - 50 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([m, m, S - m, S - m], radius=r, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
white = (255, 255, 255, 255)
# Lente
cx, cy, rad, w = 450, 440, 190, 58
d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=white, width=w)
# Manico
d.line([(cx + 140, cy + 140), (cx + 330, cy + 330)], fill=white, width=100)
d.ellipse([cx + 280, cy + 280, cx + 380, cy + 380], fill=white)

img.save(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
