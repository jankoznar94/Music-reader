#!/usr/bin/env python3
"""Prohlédne reálné noty (Ejhle hospodin přijde) — ořez po stránkách:
změří okraje v canvasu a uloží screenshot stránky pro vizuální kontrolu."""
import asyncio
import base64
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness = _m.Harness

PDF = '/tmp/ejhle.pdf'

MEASURE = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  const r = c.getBoundingClientRect();
  const a = document.querySelector('.page-area').getBoundingClientRect();
  const ctx = c.getContext('2d');
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  let x0 = c.width, x1 = -1, y0 = c.height, y1 = -1;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
    const i = (y * c.width + x) * 4;
    if (d[i] < 200 || d[i + 1] < 200 || d[i + 2] < 200) {
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  const dpr = window.devicePixelRatio || 1;
  return {
    win: [innerWidth, innerHeight],
    canvas: [Math.round(r.width), Math.round(r.height)],
    gapL: Math.round(r.left - a.left),
    gapR: Math.round(a.right - r.right),
    gapT: Math.round(r.top), gapB: Math.round(innerHeight - r.bottom),
    inkL: +(x0 / dpr).toFixed(1), inkR: +((c.width - 1 - x1) / dpr).toFixed(1),
    inkT: +(y0 / dpr).toFixed(1), inkB: +((c.height - 1 - y1) / dpr).toFixed(1),
    vb: (document.querySelector('.annot-layer') || {}).getAttribute
        ? document.querySelector('.annot-layer').getAttribute('viewBox') : '',
  };
})()
"""


async def shot(h, path):
    res = await h.cdp('Page.captureScreenshot', {'format': 'png'})
    with open(path, 'wb') as fh:
        fh.write(base64.b64decode(res['data']))


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=PDF, pages=50)
        await asyncio.sleep(1.5)
        await h.cdp('Emulation.setDeviceMetricsOverride',
                    {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        await asyncio.sleep(1.0)
        # zapnout rám
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));b&&b.click()})()")
        await asyncio.sleep(0.4)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.prefs-panel .prefs-icon')]"
                   ".find(x=>(x.title||'').startsWith('Oříznout'));b&&b.click()})()")
        await asyncio.sleep(3.0)
        for page in (1, 2, 6, 10):
            if page > 1:
                await h.goto(page)
                await asyncio.sleep(2.2)
            s = await h.ev(MEASURE)
            print(f'strana {page}:', s, flush=True)
            if page <= 6: await shot(h, f'/tmp/ejhle-p{page}.png')
        print('screenshoty: /tmp/ejhle-p1..3.png')


if __name__ == '__main__':
    asyncio.run(main())
