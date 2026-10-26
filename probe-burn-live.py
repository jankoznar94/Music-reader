#!/usr/bin/env python3
"""Ověření ŽIVÉHO webu po deployi: spustí vypálení nasazeným chunkem.

Telefonní ref (1200x1900), 3 strany -> měřítko musí být odvozené od stránky
(~1,87) a plocha pod 8 M px. Nic se neklika v UI, volá se reálný nasazený kód.
"""
import asyncio
import base64
import importlib.util
import json
import os
import re
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

LIVE = "https://harlequin-music-reader.web.app/"

JS = r"""
async (b64, pages, refW, refH, mod) => {
  const out = { meta: [], errors: [] };
  try {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const share = await import(mod);
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
      new Promise((_, rej) => setTimeout(() => rej(new Error('TIMEOUT 60 s')), 60000)),
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


async def main():
    html = urllib.request.urlopen(LIVE).read().decode('utf-8', 'replace')
    mainjs = html.split('src="/assets/')[1].split('"')[0]
    js = urllib.request.urlopen(LIVE + 'assets/' + mainjs).read().decode('utf-8', 'replace')
    chunk = '/assets/' + re.search(r'share-[A-Za-z0-9_-]+\.js', js).group(0)
    print("live main:", mainjs, "| share chunk:", chunk)
    pdf = m.make_pdf(pages=3, path='/tmp/burn-live.pdf')
    b64 = base64.b64encode(open(pdf, 'rb').read()).decode()
    async with m.Harness(url=LIVE) as h:
        await h.cdp("Page.navigate", {"url": LIVE})
        await h.wait_for("document.readyState === 'complete'", timeout=40, label="live load")
        await asyncio.sleep(3)
        expr = f"({JS})({json.dumps(b64)}, 3, 1200, 1900, {json.dumps(chunk)})"
        res = await h.ev(expr, await_promise=True)
        print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])


asyncio.run(main())
