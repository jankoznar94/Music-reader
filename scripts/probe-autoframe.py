#!/usr/bin/env python3
"""Sonda automatického rámu: obsah musí být vycentrovaný a mimo okrajové pruhy."""
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
OUT = "/tmp/autoframe-shot.png"

GEO = r"""
(() => {
  const v = document.querySelector('.viewer').getBoundingClientRect();
  const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
  const svg = document.querySelector('.annot-layer');
  const stage = document.querySelector('.stage').getBoundingClientRect();
  const cs = getComputedStyle(document.querySelector('.viewer'));
  const edgeW = parseFloat(cs.getPropertyValue('--edge-w')) || 0;
  // obálka skutečného inkoustu na canvasu
  const cv = document.querySelector('canvas.pdf-canvas');
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < cv.height; y += 2) {
    for (let x = 0; x < cv.width; x += 2) {
      const p = (y * cv.width + x) * 4;
      if (d[p] + d[p+1] + d[p+2] < 480) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  }
  return {
    viewer: {x: v.left, y: v.top, w: v.width, h: v.height},
    canvas: {x: c.left, y: c.top, w: c.width, h: c.height},
    stage: {x: stage.left, y: stage.top, w: stage.width, h: stage.height},
    edgeW,
    viewBox: svg ? svg.getAttribute('viewBox') : null,
    ink: {x0, y0, x1, y1, cw: cv.width, ch: cv.height},
    pageText: document.querySelector('.tb-page').textContent.trim(),
  };
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()          # musí být na origin aplikace, jinak IndexedDB odmítne
        await h.open_song(pdf=PDF)
        g = await h.ev(GEO)
        print(json.dumps({k: v for k, v in g.items() if k != 'ink'}, indent=1))
        print('ink', g['ink'])
        cw, ch = g['ink']['cw'], g['ink']['ch']
        sx = g['canvas']['w'] / cw
        sy = g['canvas']['h'] / ch
        left_ink = g['canvas']['x'] + g['ink']['x0'] * sx
        right_ink = g['canvas']['x'] + g['ink']['x1'] * sx
        top_ink = g['canvas']['y'] + g['ink']['y0'] * sy
        bot_ink = g['canvas']['y'] + g['ink']['y1'] * sy
        left_band = g['viewer']['x'] + g['edgeW']
        right_band = g['viewer']['x'] + g['viewer']['w'] - g['edgeW']
        print(f"ink L={left_ink:.1f} R={right_ink:.1f}  band L={left_band:.1f} R={right_band:.1f}")
        print(f"ink T={top_ink:.1f} B={bot_ink:.1f}  viewer T={g['viewer']['y']:.1f} "
              f"B={g['viewer']['y']+g['viewer']['h']:.1f}")
        chk('obsah vlevo mimo pruh', left_ink >= left_band - 1, f"{left_ink:.1f} >= {left_band:.1f}")
        chk('obsah vpravo mimo pruh', right_ink <= right_band + 1, f"{right_ink:.1f} <= {right_band:.1f}")
        lgap = left_ink - left_band
        rgap = right_band - right_ink
        chk('vodorovně vycentrováno', abs(lgap - rgap) <= 3, f"L{lgap:.1f} vs R{rgap:.1f}")
        chk('vyplňuje šířku (safe zónu)', abs(g['canvas']['w'] - (g['viewer']['w'] - 12 - 2 * (g['edgeW'] + 4))) <= 4,
            f"canvas {g['canvas']['w']:.0f}")
        tgap = top_ink - (g['viewer']['y'] + 0)
        bgap = (g['viewer']['y'] + g['viewer']['h']) - bot_ink
        print(f"vertical gaps T={tgap:.1f} B={bgap:.1f}")
        shot = await h.cdp('Page.captureScreenshot', {'format': 'png'})
        import base64
        open(OUT, 'wb').write(base64.b64decode(shot['data']))
        print('screenshot', OUT)
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
