#!/usr/bin/env python3
"""ORÁKUL osnov: najde řádky linek osnov s mírným prahem a vypíše je.

Pro každou stránku vypíše podezřelé řádky (podíl inkoustu, nejdelší tah)
a z nich složené osnovy (skupiny 4–5 řádků s pravidelným krokem).
Slouží k porovnání s tím, co najde appka — bez dohadování.
"""
import numpy as np
import fitz

PDFS = {
    "moz": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf",
    "cher": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/native-inputs/743ae0e1e381675e93d3d8669ef6a9293afe9b4b41996ffdaf284a6d012bfa39/doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf",
}
CASES = [("moz", 5), ("moz", 6), ("cher", 3), ("cher", 5), ("cher", 10)]
DPI = 200


def rows_of(key, page):
    d = fitz.open(PDFS[key])
    pix = d[page - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    s = DPI / 72.0
    h, w = a.shape
    thr = 205
    mask = a < thr
    frac = mask.mean(axis=1)
    # nejdelší vodorovný tah v řádku
    longest = np.zeros(h, dtype=np.int32)
    for y in range(h):
        m = mask[y]
        if not m.any():
            continue
        idx = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(np.int8), [0]))))
        longest[y] = (idx[1::2] - idx[0::2]).max() if len(idx) else 0
    on = (frac >= 0.20) | (longest >= 0.25 * w)
    # slij sousední řádky
    groups = []
    y = 0
    while y < h:
        if on[y]:
            y0 = y
            while y < h and on[y]:
                y += 1
            groups.append((y0, y - 1))
        else:
            y += 1
    return a, s, groups, frac, longest


for key, page in CASES:
    a, s, groups, frac, longest = rows_of(key, page)
    h, w = a.shape
    print("=" * 18, key, page, "w", w, "h", h)
    # řádky = centrované skupiny, kde nejdelší tah je delší než 15 % šířky
    lines = [g for g in groups if longest[(g[0] + g[1]) // 2] >= 0.15 * w]
    print("  řádky (max tah >= 15%% šířky), výška skupiny <= 6 px:")
    for g in lines:
        yc = (g[0] + g[1]) / 2
        print("    y%6.1f  frac %.2f longest %.2f h=%d" % (yc / s, frac[int(yc)], longest[int(yc)] / w, g[1] - g[0] + 1))
    # osnovy: 4-5 řádků s krokem ~ 4 px body
    staves = []
    for i in range(len(lines) - 3):
        g = lines[i:i + 5]
        if len(g) < 4:
            continue
        ys = [(x[0] + x[1]) / 2 for x in g]
        gaps = np.diff(ys)
        med = np.median(gaps)
        if med < 2 * s * 0.8:
            continue
        if np.all(np.abs(gaps - med) <= 0.35 * med) and len(g) >= 4:
            staves.append((ys[0] / s, ys[-1] / s, len(g)))
    print("  osnovy:", [(round(t, 1), round(b, 1), n) for t, b, n in staves])
