#!/usr/bin/env python3
"""Sonda automatického rámu (lokální dev): vypnuto = plná šířka jako dřív,
zapnuto = ořez + obsah mimo okrajové pruhy, Vycentrovat = rám zase vypne."""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

PDF = "/home/martin_fabian/skladby/out/HLAS_TENOR_1.pdf"

GEO = r"""
(() => {
  const v = document.querySelector('.viewer').getBoundingClientRect();
  const cvEl = document.querySelector('canvas.pdf-canvas');
  const c = cvEl.getBoundingClientRect();
  const svg = document.querySelector('.annot-layer');
  const cs = getComputedStyle(document.querySelector('.viewer'));
  const edgeW = parseFloat(cs.getPropertyValue('--edge-w')) || 0;
  const ctx = cvEl.getContext('2d');
  const d = ctx.getImageData(0, 0, cvEl.width, cvEl.height).data;
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < cvEl.height; y += 2)
    for (let x = 0; x < cvEl.width; x += 2) {
      const p = (y * cvEl.width + x) * 4;
      if (d[p] + d[p+1] + d[p+2] < 480) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  return {viewer: {x: v.left, w: v.width, h: v.height}, canvas: {x: c.left, y: c.top, w: c.width, h: c.height},
          edgeW, viewBox: svg.getAttribute('viewBox'), stored: localStorage.getItem('noty-auto-frame'),
          ink: {x0, y0, x1, y1, cw: cvEl.width, ch: cvEl.height}};
})()
"""


def analyze(g):
    sx = g['canvas']['w'] / g['ink']['cw']
    sy = g['canvas']['h'] / g['ink']['ch']
    L = g['canvas']['x'] + g['ink']['x0'] * sx
    R = g['canvas']['x'] + g['ink']['x1'] * sx
    T = g['canvas']['y'] + g['ink']['y0'] * sy
    B = g['canvas']['y'] + g['ink']['y1'] * sy
    vb = [float(x) for x in g['viewBox'].split()]
    return L, R, T, B, vb


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.ev("localStorage.removeItem('noty-auto-frame')")
        await h.open_song(pdf=PDF)
        g = await h.ev(GEO)
        L, R, T, B, vb = analyze(g)
        fullW = g['viewer']['w'] - 12
        print('VYPNUTO  viewBox', g['viewBox'], 'canvas w', round(g['canvas']['w']), 'full', fullW,
              'ink', round(L), round(R))
        chk('vypnuto: celá stránka', vb[0] == 0 and vb[1] == 0 and vb[2] > 700)
        chk('vypnuto: plná šířka', abs(g['canvas']['w'] - fullW) <= 3, f"{g['canvas']['w']:.0f} vs {fullW:.0f}")

        # zapnout Rám
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Zvětšení')); b && b.click(); })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='Rám'); b && b.click(); })()")
        await asyncio.sleep(2.5)
        g = await h.ev(GEO)
        L, R, T, B, vb = analyze(g)
        band = g['edgeW'] + 4
        left_band = g['viewer']['x'] + band
        right_band = g['viewer']['x'] + g['viewer']['w'] - band
        print('ZAPNUTO  viewBox', g['viewBox'], 'canvas w', round(g['canvas']['w']),
              f"ink L{ L:.0f} R{R:.0f} band L{left_band:.0f} R{right_band:.0f}")
        chk('zapnuto: oříznuto', vb[2] < 770 and vb[3] < 700, f"{vb[2]:.0f}x{vb[3]:.0f}")
        chk('zapnuto: vlevo mimo pruh', L >= left_band - 1, f"{L:.0f}")
        chk('zapnuto: vpravo mimo pruh', R <= right_band + 1, f"{R:.0f}")
        chk('zapnuto: vycentrováno', abs((L - left_band) - (right_band - R)) <= 4,
            f"{(L-left_band):.0f} vs {(right_band-R):.0f}")
        chk('zapnuto: uloženo', g['stored'] == '1')

        # Vycentrovat = manuální override
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat')); b && b.click(); })()")
        await asyncio.sleep(2.5)
        g = await h.ev(GEO)
        L, R, T, B, vb = analyze(g)
        print('VYCENTROVAT viewBox', g['viewBox'], 'canvas w', round(g['canvas']['w']), 'stored', g['stored'])
        chk('vycentrovat vypne rám', g['stored'] == '0' and vb[0] == 0 and abs(g['canvas']['w'] - fullW) <= 3)
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
