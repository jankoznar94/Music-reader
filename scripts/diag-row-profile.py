#!/usr/bin/env python3
"""Detailní rozbor řádků jedné stránky: které řádky vypadají jako linka osnovy
a jak z nich vycházejí osnovy. Pomáhá najít, proč appka osnovu ztratí."""
import sys
import numpy as np
import fitz

PDFS = {
    "moz": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf",
    "cher": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/native-inputs/743ae0e1e381675e93d3d8669ef6a9293afe9b4b41996ffdaf284a6d012bfa39/doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf",
}
DPI = 200
key = sys.argv[1] if len(sys.argv) > 1 else "cher"
page = int(sys.argv[2]) if len(sys.argv) > 2 else 5
y0pt = float(sys.argv[3]) if len(sys.argv) > 3 else 0
y1pt = float(sys.argv[4]) if len(sys.argv) > 4 else 9999

d = fitz.open(PDFS[key])
pix = d[page - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
s = DPI / 72.0
h, w = a.shape
mask = a < 205

print(f"{key} str.{page}: {w}x{h} px, {1/s:.3f} b/px")
rows = []
for y in range(h):
    m = mask[y]
    frac = m.mean()
    idx = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(np.int8), [0]))))
    longest = (idx[1::2] - idx[0::2]).max() / w if len(idx) else 0
    if y / s < y0pt or y / s > y1pt:
        continue
    if frac >= 0.15 or longest >= 0.16:
        rows.append((y / s, frac, longest))
# slij sousední řádky (jedna linka = víc pixelů)
groups = []
for r in rows:
    if groups and r[0] - groups[-1][-1][0] < 1.2:
        groups[-1].append(r)
    else:
        groups.append([r])
print("skupiny řádků (y, frac, longest):")
for g in groups:
    best = max(g, key=lambda r: r[2])
    print("  y%7.2f  frac %.2f  longest %.2f  h=%d" % (best[0], best[1], best[2], len(g)))
