"""Naměří, kde jsou VYTISKNUTÁ čísla taktů na str. 16 skenu (Mozart).

Cíl: rozhodnout, jestli klepnutí `pdf 14,487` bylo na čísle, nebo o kus vedle.
Souřadnice v bodech PDF, y od shora. Digitální komponenty se hledají stejnými
prahy jako v aplikaci (výška 3–12 b, šířka 0,7–12 b).
"""
import sys
import pymupdf as fitz
import numpy as np
from scipy import ndimage

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
PAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 15   # 0-based → str. 16
ZOOM = 4

doc = fitz.open(PDF)
page = doc[PAGE]
print("page rect:", page.rect, "rotation:", page.rotation)
pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), colorspace=fitz.csGRAY)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
ppt = ZOOM
thr = 150
mask = img < thr
lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
objs = ndimage.find_objects(lab)
comps = []
for i, sl in enumerate(objs):
    if sl is None:
        continue
    h = (sl[0].stop - sl[0].start) / ppt
    w = (sl[1].stop - sl[1].start) / ppt
    area = (lab[sl] == i + 1).sum()
    if 3 <= h <= 12 and 0.7 <= w <= 12 and w / h <= 6 and area >= 12:
        comps.append({"x0": sl[1].start / ppt, "y0": sl[0].start / ppt,
                      "x1": sl[1].stop / ppt, "y1": sl[0].stop / ppt,
                      "h": h, "w": w})
# jen levý okraj (kde bývají čísla taktů)
left = [c for c in comps if c["x1"] < 130]
left.sort(key=lambda c: (round(c["y0"] / 6), c["x0"]))
print("\ndigitálních komponent u levého okraje: %d" % len(left))
for c in left:
    print("  x %6.1f–%6.1f  y %6.1f–%6.1f  (h %.1f w %.1f)"
          % (c["x0"], c["x1"], c["y0"], c["y1"], c["h"], c["w"]))

# co je poblíž klepnutí pdf (14, 487)
print("\nkomponenty do 40 b od bodu (14, 487):")
for c in comps:
    cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
    if abs(cx - 14) < 40 and abs(cy - 487) < 40:
        print("  x %6.1f–%6.1f  y %6.1f–%6.1f  (h %.1f w %.1f)"
              % (c["x0"], c["x1"], c["y0"], c["y1"], c["h"], c["w"]))
