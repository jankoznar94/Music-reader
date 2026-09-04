#!/usr/bin/env python3
"""Vygeneruje PWA ikony pro Noty App (192, 512) + favicon SVG."""
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'public', 'assets')
os.makedirs(OUT, exist_ok=True)

BG = (28, 25, 23, 255)          # teplá tmavě hnědá (--bg)
ACCENT = (201, 168, 124, 255)   # desaturovaná zlatá (--accent)


def draw_note_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Kulaté plátno, tmavé pozadí
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=BG)

    s = size / 256.0
    # Hlava noty (elipsa)
    ebox = [62 * s, 108 * s, 150 * s, 196 * s]
    d.ellipse(ebox, fill=ACCENT)

    # Stonka
    d.rounded_rectangle(
        [128 * s, 52 * s, 152 * s, 140 * s], radius=int(10 * s), fill=ACCENT
    )

    # Praporek (oblouk / vlaječka) — dva oblouky pro notu osminovou
    d.arc([120 * s, 30 * s, 260 * s, 120 * s], start=140, end=300, fill=ACCENT, width=int(12 * s))
    return img


for name, size in [('noty-app-logo-192.png', 192), ('noty-app-logo-512.png', 512)]:
    draw_note_icon(size).save(os.path.join(OUT, name))
    print(f'Generated {name} ({size}x{size})')

# Favicon SVG
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect x="0" y="0" width="256" height="256" rx="56" fill="{hex(BG[0])[2:]}{hex(BG[1])[2:]}{hex(BG[2])[2:]}"/>
  <ellipse cx="106" cy="152" rx="44" ry="44" fill="{hex(ACCENT[0])[2:]}{hex(ACCENT[1])[2:]}{hex(ACCENT[2])[2:]}"/>
  <rect x="128" y="52" width="24" height="88" rx="10" fill="{hex(ACCENT[0])[2:]}{hex(ACCENT[1])[2:]}{hex(ACCENT[2])[2:]}"/>
  <path d="M140 52 q 120 -10 100 60 q -8 24 -30 28" fill="none" stroke="{hex(ACCENT[0])[2:]}{hex(ACCENT[1])[2:]}{hex(ACCENT[2])[2:]}" stroke-width="12"/>
</svg>'''
with open(os.path.join(OUT, 'noty-icon.svg'), 'w') as f:
    f.write(svg)
print('Generated noty-icon.svg')
