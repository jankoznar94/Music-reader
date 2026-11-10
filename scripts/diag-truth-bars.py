#!/usr/bin/env python3
"""Nezávislé měření: pro každou osnovu (řádky dodané z detekce) vypíše sloupce
plné přes výšku té osnovy. Skutečná taktová čára je tam, kde se x shoduje ve
VÍC osnovách; nožička jen v jedné."""
import numpy as np
import fitz

PDF = "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf"
DPI = 200

ROWS = {
    5: [(52.5, 67.2), (89.7, 104.8), (123.2, 138.7), (157.7, 173.5), (208.2, 225.4),
        (250.9, 268.1), (309.1, 324.9), (343.9, 360), (371.3, 386.6), (398, 413.8),
        (425.4, 441.3), (463.8, 480.6), (502.6, 519.4), (556.6, 572.1), (595.2, 610.9),
        (630.8, 646.3), (665.1, 680.8), (699.8, 715.3), (738.2, 754.8), (775.6, 792.4)],
    6: [(52.3, 67.4), (89.5, 105), (127.3, 143), (169.2, 185.1), (207.6, 223.1),
        (250.3, 267.1), (296.7, 313.4), (354.1, 369.8), (400.1, 416.2), (442, 458.1),
        (484.7, 500), (526.8, 542.3), (568.4, 585.4), (615.2, 631.8), (672, 687.1),
        (725.4, 742.3), (771.1, 787.7)],
}
SYSTEMS = {5: [(0, 5), (6, 12), (13, 19)], 6: [(0, 6), (7, 12), (13, 16)]}


def render(page):
    d = fitz.open(PDF)
    pix = d[page - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def staff_cols(a, top, bot, s):
    mask = a[int(top * s):int(bot * s) + 1, :] < 190
    cov = mask.mean(axis=0)
    cols = np.where(cov >= 0.95)[0]
    groups = []
    for c in cols:
        if groups and c - groups[-1][-1] <= 2:
            groups[-1].append(c)
        else:
            groups.append([c])
    return [round((g[0] + g[-1]) / 2 / s, 1) for g in groups if g[-1] - g[0] + 1 <= 12]


for page, sysdefs in SYSTEMS.items():
    a = render(page)
    s = DPI / 72.0
    print("=" * 25, "page", page)
    for si, (i0, i1) in enumerate(sysdefs, 1):
        print(f"-- systém {si} (osnovy {i0 + 1}..{i1 + 1})")
        for i in range(i0, i1 + 1):
            t, b = ROWS[page][i]
            print(f"   osnova {i + 1} y{t:.0f}-{b:.0f}: {staff_cols(a, t, b, s)}")
