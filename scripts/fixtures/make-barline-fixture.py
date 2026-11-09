#!/usr/bin/env python3
"""Syntetická SAZBA pro test detekce taktových čar (barLines.js).

PROČ: detekci čar nelze ověřit na fixtures/notes-fixture.pdf (jsou tam jen
pomlčky). Tenhle generátor vykreslí realistický SKEN dvouosnového systému:
dvě osnovy, svorka na začátku, úvodní taktová čára v ose začátku osnov,
tři vnitřní taktové čáry, koncová tlustá čára, noty s nožičkami (i akordy,
jejichž nožička přeroste celou osnovu), pomocné linky, trámce, klíč, číslo
taktu nad systémem a šum skenu.

Výstup: PNG 6 px/pt + JSON s PRAVDOU (kde čáry jsou), aby se dalo měřit
kolik čar detekce našla a o kolik se sekla.

Použití:  python3 scripts/fixtures/make-barline-fixture.py [--out DIR]
"""
import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

PPT = 6                     # px na PDF bod
W_PT, H_PT = 595, 260
SPACE = 4.0                 # mezera osnovy v bodech (běžná sazba)
PX = lambda pt: pt * PPT
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


def barline(d, x, y0, y1, over=0.3 * SPACE, thick=0.9):
    """Taktová čára: svislý tah, mírně přes osnovu (over = přesah v bodech)."""
    t = thick * PPT
    d.rectangle([PX(x) - t / 2, PX(y0 - over), PX(x) + t / 2, PX(y1 + over)], fill=95)


def staff(d, x0, x1, ytop):
    for i in range(5):
        y = ytop + i * SPACE
        d.rectangle([PX(x0), PX(y) - 1.6, PX(x1), PX(y) + 1.6], fill=105)


def notehead(d, x, y, half=True):
    """Plná nota (elipsa 1,2 mezery široká, 0,66 mezery vysoká)."""
    w, h = PX(1.2 * SPACE / 2), PX(0.66 * SPACE / 2)
    d.ellipse([PX(x) - w, PX(y) - h, PX(x) + w, PX(y) + h], fill=40)


def stem(d, x, y_from, direction, length=3.5 * SPACE):
    t = 0.45 * PPT
    y_to = y_from + (length if direction == "down" else -length)
    d.rectangle([PX(x) - t / 2, PX(min(y_from, y_to)), PX(x) + t / 2,
                 PX(max(y_from, y_to))], fill=45)


def ledger(d, x, y):
    d.rectangle([PX(x) - PX(0.9), PX(y) - 1.4, PX(x) + PX(0.9), PX(y) + 1.4], fill=105)


def chord(d, x, y_low, y_high, direction):
    """Akord: jedna nožička přes celý rozsah — přesně to, co detekce dřív
    pletla s taktovou čarou (přesáhne celou osnovu)."""
    notehead(d, x, y_low); notehead(d, x, y_high)
    stem(d, x + PX(0.55), y_low if direction == "up" else y_high, direction,
         length=abs(y_high - y_low) + 3.0 * SPACE)


def beam(d, x0, x1, y):
    d.rectangle([PX(x0), PX(y) - PX(0.28), PX(x1), PX(y) + PX(0.28)], fill=45)


def clef(d, x, ytop):
    """Hrubý tvar houslového klíče: svislá tlustá křivka přes osnovu."""
    for i in range(10):
        yy = ytop - 0.4 * SPACE + i * (4.0 * SPACE / 9)
        w = PX(0.55 if i % 2 else 0.35)
        d.ellipse([PX(x) - w, PX(yy) - PX(0.25), PX(x) + w, PX(yy) + PX(0.25)], fill=45)


def build(overshoot=0.3, with_final=True):
    img = Image.new("L", (PX(W_PT), PX(H_PT)), 250)
    d = ImageDraw.Draw(img)
    t1, t2 = 78.0, 118.0                      # horní linka 1. a 2. osnovy
    x0, x1 = 58.0, 470.0
    staff(d, x0, x1, t1)
    staff(d, x0, x1, t2)
    # svorka na začátku systému (tlustá svislá čára přes obě osnovy)
    d.rectangle([PX(x0) - 4, PX(t1 - 1), PX(x0) + PX(0.55), PX(t2 + 4 * SPACE + 1)], fill=35)
    # úvodní taktová čára v ose začátku osnov — tu appka NESMÍ počítat
    barline(d, x0, t1, t1 + 4 * SPACE, over=overshoot)
    barline(d, x0, t2, t2 + 4 * SPACE, over=overshoot)
    # vnitřní taktové čáry (3) → systém má 4 takty
    inner = [148.0, 250.0, 352.0]
    for x in inner:
        for ty in (t1, t2):
            barline(d, x, ty, ty + 4 * SPACE, over=overshoot)
    # koncová čára (tenká + tlustá)
    if with_final:
        for ty in (t1, t2):
            yb = ty + 4 * SPACE
            d.rectangle([PX(x1) - PX(0.45), PX(ty - overshoot), PX(x1) - PX(0.15), PX(yb + overshoot)], fill=95)
            d.rectangle([PX(x1) + PX(0.10), PX(ty - overshoot), PX(x1) + PX(0.65), PX(yb + overshoot)], fill=45)
    # klíče + noty: akordy, pomocné linky, trámce
    clef(d, 66.0, t1)
    clef(d, 66.0, t2)
    # akord přes celou osnovu (nožička = plná výška osnovy) – past na detekci
    chord(d, 74.0, t1 + 3 * SPACE, t1 + 0.5 * SPACE, "down")
    chord(d, 74.0, t2 + 3 * SPACE, t2 + 0.5 * SPACE, "down")
    # běžné noty s nožičkami uvnitř osnov
    for x in (90.0, 106.0, 122.0, 134.0):
        notehead(d, x, t1 + 2 * SPACE); stem(d, x + PX(0.55), t1 + 2 * SPACE, "up")
        notehead(d, x, t2 + 1 * SPACE); stem(d, x + PX(0.55), t2 + 1 * SPACE, "down")
    # noty nad osnovou na pomocných linkách + nožička dolů
    for x, y in ((162.0, t1 - 1 * SPACE), (172.0, t1 - 2 * SPACE)):
        ledger(d, x, y); notehead(d, x, y); stem(d, x + PX(0.55), y, "down")
    # nota pod osnovou, nožička nahoru
    for x, y in ((196.0, t2 + 5 * SPACE), (206.0, t2 + 6 * SPACE)):
        ledger(d, x, y); notehead(d, x, y); stem(d, x + PX(0.55), y, "up")
    # trámcová skupina
    for x in (226.0, 234.0, 242.0):
        notehead(d, x, t1 + 3 * SPACE); stem(d, x + PX(0.55), t1 + 3 * SPACE, "up")
    beam(d, 226.5, 243.0, t1 + 3 * SPACE - 3.5 * SPACE)
    # číslo taktu nad systémem (vytištěné číslo prvního taktu systému)
    f = ImageFont.truetype(FONT, int(PX(7.0)))
    d.text((PX(x0) + 2, PX(t1) - PX(13.0)), "24", font=f, fill=40)
    # dynamika / obloučky jako smetí
    f2 = ImageFont.truetype(FONT, int(PX(6.0)))
    for x in (300.0, 380.0):
        d.text((PX(x), PX(t1) + PX(17.0)), "p", font=f2, fill=50)
    # šum skenu
    rnd = random.Random(7)
    px = img.load()
    for _ in range(int(W_PT * H_PT * PPT * PPT * 0.004)):
        x = rnd.randrange(img.width); y = rnd.randrange(img.height)
        v = max(0, min(255, px[x, y] + rnd.randint(-26, 26)))
        px[x, y] = v
    img = img.filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(0.6))
    truth = {
        "ppt": PPT, "space": SPACE, "staffs": [[t1, t1 + 4 * SPACE], [t2, t2 + 4 * SPACE]],
        "opening": x0, "inner": inner, "final": x1, "bars": 4,
    }
    return img, truth


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    os.makedirs(out, exist_ok=True)
    for name, kw in (("barline-scan.png", {}), ("barline-scan-flush.png", {"overshoot": 0.0})):
        img, truth = build(**kw)
        img.save(os.path.join(out, name))
        with open(os.path.join(out, name.replace(".png", ".json")), "w") as fh:
            json.dump(truth, fh, indent=1)
        print(os.path.join(out, name))


if __name__ == "__main__":
    main()
