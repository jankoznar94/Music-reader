#!/usr/bin/env python3
"""Hustota inkoustu v mezerách mezi osnovami (nezávisle na appce).

Cíl: najít signál, který odliší mezeru UVNITŘ systému (sbor -> klavír, kde
bývá text písně) od mezery MEZI systémy (téměř prázdno).
Vypíše pro každou mezeru: velikost v bodech, podíl inkoustu v mezeře.
"""
import sys
import numpy as np
import fitz

DPI = 200

CASES = {
    ("moz", 5): [(52.5, 67.2), (89.7, 104.8), (123.2, 138.7), (157.7, 173.5), (208.2, 225.4),
                 (250.9, 268.1), (309.1, 324.9), (343.9, 360), (371.3, 386.6), (398, 413.8),
                 (425.4, 441.3), (463.8, 480.6), (502.6, 519.4), (556.6, 572.1), (595.2, 610.9),
                 (630.8, 646.3), (665.1, 680.8), (699.8, 715.3), (738.2, 754.8), (775.6, 792.4)],
    ("moz", 6): [(52.3, 67.4), (89.5, 105), (127.3, 143), (169.2, 185.1), (207.6, 223.1),
                 (250.3, 267.1), (296.7, 313.4), (354.1, 369.8), (400.1, 416.2), (442, 458.1),
                 (484.7, 500), (526.8, 542.3), (568.4, 585.4), (615.2, 631.8), (672, 687.1),
                 (725.4, 742.3), (771.1, 787.7)],
    ("cher", 3): [(41.4, 54.4), (71.4, 84.4), (136.4, 148.8), (171.6, 188.2), (211.2, 227.6),
                  (257.2, 270.2), (288, 300.8), (322.4, 335.2), (353, 365.8), (388.4, 404.8),
                  (431.8, 448.4), (480.4, 492.8), (508.4, 520.8), (539.6, 552.2), (567.6, 580),
                  (602.8, 618.8), (644.8, 661.2)],
    ("cher", 5): [(45.2, 58.4), (75.2, 88.4), (108.8, 121.8), (138.2, 150.8), (176, 192.6),
                  (215.2, 231.6), (263.8, 276.6), (293.2, 306), (322.6, 335.2), (355.6, 368.2),
                  (393.2, 409.8), (432.2, 444.6), (546.6, 556.2), (578.8, 588.2)],
    ("cher", 10): [(37.4, 50.8), (70.2, 83.4), (102, 115), (134.2, 147.2), (174.2, 190.8),
                   (220.8, 237.6), (275, 288), (303.6, 316.6), (332, 344.8), (364.6, 377.6),
                   (400, 421), (441, 457.4), (622, 634.4), (659, 671.4)],
}
PDFS = {
    "moz": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf",
    "cher": "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/native-inputs/743ae0e1e381675e93d3d8669ef6a9293afe9b4b41996ffdaf284a6d012bfa39/doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf",
}


def gray(key, page):
    d = fitz.open(PDFS[key])
    pix = d[page - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


for (key, page), rows in CASES.items():
    a = gray(key, page)
    s = DPI / 72.0
    print("=" * 20, key, page)
    for i in range(len(rows) - 1):
        y0 = int(rows[i][1] * s) + 2
        y1 = int(rows[i + 1][0] * s) - 2
        if y1 <= y0:
            continue
        gap = rows[i + 1][0] - rows[i][1]
        band = a[y0:y1, :]
        ink = (band < 190).mean()
        # bez okrajů: 8 % z každé strany
        w = band.shape[1]
        inner = band[:, int(0.08 * w):int(0.92 * w)]
        ink2 = (inner < 190).mean()
        print(f"  mezera y{rows[i][1]:.0f}->{rows[i+1][0]:.0f} ({gap:5.1f} b): ink {ink:.3f} / střed {ink2:.3f}")
