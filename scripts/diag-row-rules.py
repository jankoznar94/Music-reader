#!/usr/bin/env python3
"""Simulace prahů staffGroups offline: vypíše řádky s frac/longest a to, které
verze pravidla je pustí, plus výsledné skupiny (centra)."""
import sys
import numpy as np
import fitz

PDFS = {
    "moz": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf",
    "cher": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/native-inputs/743ae0e1e381675e93d3d8669ef6a9293afe9b4b41996ffdaf284a6d012bfa39/doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf",
}
DPI = 200
key, page = sys.argv[1], int(sys.argv[2])
y0pt, y1pt = float(sys.argv[3]), float(sys.argv[4])

d = fitz.open(PDFS[key])
pix = d[page - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
s = DPI / 72.0
h, w = a.shape
mask = a < 205

frac = mask.mean(axis=1)
longest = np.zeros(h)
for y in range(h):
    m = mask[y]
    idx = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(np.int8), [0]))))
    longest[y] = (idx[1::2] - idx[0::2]).max() / w if len(idx) else 0


def groups(on):
    out = []
    start = -1
    for y in range(h + 1):
        o = on[y] if y < h else False
        if o and start < 0:
            start = y
        if not o and start >= 0:
            out.append(((start + y - 1) / 2, start, y - 1))
            start = -1
    return out


y0, y1 = int(y0pt * s), int(y1pt * s)
print("y(b)   frac  longest   A(0.30/0.45)  B(+0.16&0.15)  C(long>=0.16)")
for y in range(y0, y1):
    A = frac[y] >= 0.30 or longest[y] >= 0.45
    B = A or (longest[y] >= 0.16 and frac[y] >= 0.15)
    C = A or longest[y] >= 0.16
    if A or B or C or longest[y] >= 0.10:
        print("%7.2f %.2f  %.2f      %s            %s            %s"
              % (y / s, frac[y], longest[y], "x" if A else ".", "x" if B else ".", "x" if C else "."))
for name, on in (("A", [(frac[y] >= 0.30 or longest[y] >= 0.45) for y in range(h)]),
                 ("B", [(frac[y] >= 0.30 or longest[y] >= 0.45 or (longest[y] >= 0.16 and frac[y] >= 0.15)) for y in range(h)]),
                 ("C", [(frac[y] >= 0.30 or longest[y] >= 0.45 or longest[y] >= 0.16) for y in range(h)])):
    gs = [g for g in groups(on) if y0 <= g[1] and g[2] <= y1]
    print(name, "centra:", [round(c / s, 1) for c, _, _ in gs])
