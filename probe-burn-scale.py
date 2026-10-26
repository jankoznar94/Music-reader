#!/usr/bin/env python3
"""Ověření nového vypalování: měřítko z rozměru stránky + timeout na toBlob.

1) Telefonní ref (1200x1900) na 3 stranách -> canvas musí zůstat pod stropem
   a PDF musí být hotové.
2) Simulovaný Android bug: canvas.toBlob NIKDY nezavolá callback -> export
   musí i tak doběhnout (synchronní fallback), ne zůstat viset.
"""
import asyncio
import base64
import importlib.util
import json
import os
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

APP = os.environ.get("APP_URL", "http://localhost:5199/")

JS = r"""
async (b64, pages, refW, refH, hang) => {
  const out = { meta: [], errors: [] };
  if (hang) {
    // Přesně to, co dělá Android Chrome u velkého canvasu: callback nepřijde.
    HTMLCanvasElement.prototype.toBlob = function () { /* mlčí */ };
  }
  try {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const share = await import('/src/share.js');
    const items = [];
    for (let p = 0; p < pages; p++) {
      items.push({ page: p, tool: 'text', text: 'AHOJ ' + (p + 1), x: 60, y: 300 + p * 20, size: 24, color: '#ff0000' });
      items.push({ page: p, tool: 'pencil', points: [{x: 100, y: 600}, {x: 300, y: 640}], color: '#00ff00', width: 2, opacity: 1 });
    }
    const payload = share.buildOverlayPayload({
      song: { name: 'probe', composer: '', pages: pages, hiddenPages: [], frame: false },
      annotations: { ref: { w: refW, h: refH }, items: items },
      jumps: [], bookmarks: [], bmManualOrder: false,
    });
    const t0 = performance.now();
    const res = await Promise.race([
      share.exportBurnedPdf(bytes, {
        items: items, ref: { w: refW, h: refH },
        helpers: { displayText: () => '', borderRects: () => [], noteStroke: () => 0, noteFlipY: () => false },
        payload: payload,
        onProgress: (done, total, meta) => out.meta.push({ done, total, scale: +meta.scale.toFixed(3), page: meta.page }),
      }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('TIMEOUT 60 s - burn nedobehl')), 60000)),
    ]);
    out.ok = true;
    out.bytes = res.length;
    out.ms = Math.round(performance.now() - t0);
    out.px = out.meta.map(x => Math.round(refW * x.scale) + 'x' + Math.round(refH * x.scale));
  } catch (e) {
    out.ok = false;
    out.errors.push((e && e.stack) ? e.stack : String(e));
  }
  return out;
}
"""


async def run(h, pdf, pages, refW, refH, hang=False):
    b64 = base64.b64encode(open(pdf, 'rb').read()).decode()
    expr = f"({JS})({json.dumps(b64)}, {pages}, {refW}, {refH}, {json.dumps(hang)})"
    return await h.ev(expr, await_promise=True)


async def main():
    # fixture s tolika stranami, kolik testujeme
    pdf = m.make_pdf(pages=3, path='/tmp/burn-scale.pdf')
    async with m.Harness(url=APP) as h:
        await h.set_tablet()
        await h.open()
        await asyncio.sleep(2)
        print("== 1) telefonní ref 1200x1900, 3 strany, normální toBlob ==")
        r = await run(h, pdf, 3, 1200, 1900)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2500])
        print("== 2) simulovaný Android bug: toBlob mlčí, 1 strana ==")
        t = time.time()
        r2 = await run(h, pdf, 1, 1200, 1900, hang=True)
        print(f"wall {round(time.time() - t, 1)} s")
        print(json.dumps(r2, ensure_ascii=False, indent=1)[:2500])


asyncio.run(main())
