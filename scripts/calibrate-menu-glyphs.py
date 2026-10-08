#!/usr/bin/env python3
"""KALIBRACE: pro každý znak v menu najdi posun, při kterém je střed otisku
přesně ve středu tlačítka.

Proč takhle: ladit `--glyph-nudge` rebuildem a dalším během sondy je plýtvání —
na jednu hodnotu padne celý cyklus. Tady se v JEDNOM běhu prohlížeče projede řada
posunů, změří se skutečný střed otisku z pixelů a vypíše se hodnota, kde odchylka
přechází nulou. Rebuild pak stačí jeden.

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/calibrate-menu-glyphs.py
"""
import asyncio
import base64
import importlib.util
import io
import json
import os

import numpy as np
from PIL import Image

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness = _m.Harness

# Znaky křivočaré kalibrace: selektor prvku, který má posun nést.
TARGETS = [
    (".ap-tool[title^='Text'] .ap-glyph", "T"),
    (".ap-tool.mus .ap-glyph", "<"),
    (".ap-size span", "číslo"),
    (".ap-tool[title^='Dynamika'] .dyn-ico", "dyn mf"),
    (".ap-tool[title^='Značky'] .dyn-ico", "znacka"),
    (".ap-tool[title^='Tužka'] .ap-glyph", "emoji"),
]

SWEEP = [round(-1.0 + 0.5 * i, 1) for i in range(11)]   # -1.0 .. 4.0


def ink_center(img, box, margin=6, tol=44):
    x, y, w, h = [int(round(v)) for v in box]
    if w < 8 or h < 8:
        return None
    crop = np.asarray(img.crop((x, y, x + w, y + h)).convert("RGB")).astype(int)
    inner = crop[margin:-margin, margin:-margin]
    if inner.size == 0:
        return None
    edge = np.concatenate([inner[:2].reshape(-1, 3), inner[-2:].reshape(-1, 3),
                           inner[:, :2].reshape(-1, 3), inner[:, -2:].reshape(-1, 3)])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    bg = vals[counts.argmax()]
    mask = np.abs(inner - bg).sum(axis=2) > tol
    if mask.sum() < 6:
        return None
    ys, xs = np.nonzero(mask)
    return (x + margin + (xs.min() + xs.max()) / 2,
            y + margin + (ys.min() + ys.max()) / 2)


async def measure(h, dsf, sel):
    """Odchylka středu otisku od středu tlačítka (v CSS px)."""
    rect = await h.ev("""(() => { const el = document.querySelector(%s);
      if (!el) return null; const b = el.closest('button') || el;
      const r = b.getBoundingClientRect();
      return { l: r.left, t: r.top, w: r.width, h: r.height }; })()""" % json.dumps(sel))
    if not rect:
        return None
    shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"])))
    pad = 4
    box = [(rect["l"] + pad) * dsf, (rect["t"] + pad) * dsf,
           (rect["w"] - 2 * pad) * dsf, (rect["h"] - 2 * pad) * dsf]
    c = ink_center(img, box)
    if not c:
        return None
    return ((c[0] / dsf) - (rect["l"] + rect["w"] / 2),
            (c[1] / dsf) - (rect["t"] + rect["h"] / 2))


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.9)
        dsf = await h.ev("devicePixelRatio") or 2

        # Přepis posunu dělej PŘES STYL v <head>, ne rebuildem.
        await h.ev("""(() => { if (!document.getElementById('calib')) {
          const s = document.createElement('style'); s.id = 'calib';
          document.head.appendChild(s); } return true; })()""")

        print(f"{'znak':>9} {'nudge':>6} {'dx':>7} {'dy':>7}")
        results = {}
        for sel, name in TARGETS:
            if not await h.ev("!!document.querySelector(%s)" % json.dumps(sel)):
                print(f"{name:>9}   (prvek nenalezen)")
                continue
            rows = []
            for v in SWEEP:
                css = "%s { --glyph-nudge: %spx !important; }" % (sel, v)
                await h.ev("""(() => { const s = document.getElementById('calib');
                  s.textContent = %s; return true; })()""" % json.dumps(css))
                await asyncio.sleep(0.25)
                m = await measure(h, dsf, sel)
                if m:
                    rows.append((v, m[0], m[1]))
            results[name] = rows
            # najdi nulový přechod v dy (a ukaž i dx, ať je vidět vodorovná složka)
            zero = None
            for i in range(len(rows) - 1):
                (v0, _, y0), (v1, _, y1) = rows[i], rows[i + 1]
                if y0 == 0 or (y0 < 0 < y1) or (y0 > 0 > y1):
                    if y1 != y0:
                        zero = v0 + (v1 - v0) * (0 - y0) / (y1 - y0)
                    break
            for v, dx, dy in rows:
                print(f"{name:>9} {v:>6.1f} {dx:>+7.2f} {dy:>+7.2f}")
            if zero is not None:
                print(f"{'':>9} {'→':>6} nulová odchylka při nudge ≈ {zero:.2f} px")
            print()

        await h.ev("(() => { const s = document.getElementById('calib'); if (s) s.textContent = ''; return true; })()")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
