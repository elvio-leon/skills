"""Genera l'icona dell'app (PNG 1024×1024): quadrato arrotondato rosso con freccia di download."""

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
    gd.line([(0, y), (S, y)], fill=(int(255 - 40 * t), int(70 - 40 * t), int(70 - 35 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([m, m, S - m, S - m], radius=r, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
white = (255, 255, 255, 255)
cx = S // 2
# Freccia verso il basso
d.rectangle([cx - 62, 270, cx + 62, 560], fill=white)
d.polygon([(cx - 190, 520), (cx + 190, 520), (cx, 720)], fill=white)
# Vassoio
d.rounded_rectangle([cx - 250, 760, cx + 250, 820], radius=30, fill=white)

img.save(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
