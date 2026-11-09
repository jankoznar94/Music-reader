#!/usr/bin/env python3
"""Probe detekce taktových čar (barLines.js) v reálném prohlížeči.

Nakrmí `detectBarlines` syntetickým skenem (scripts/fixtures/barline-scan*.png)
nebo libovolným reálným obrázkem stránky — měří se samotný algoritmus, ne cesta
přes rendrování PDF.

Předpoklad: `npx vite --port 5173` + headless Chrome s --remote-debugging-port=9222.

Použití:
  python3 scripts/probe-barline-detect.py [--img cesta.png ...] [--krok 4] [--ypt 86]
"""
import argparse
import asyncio
import base64
import json
import os
import urllib.request

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))

JS = """(async () => {
  const { detectBarlines } = await import('/src/barLines.js');
  const img = new Image();
  img.src = %(url)s;
  await img.decode();
  const cv = document.createElement('canvas');
  // Volitelně VÝŘEZ pásu (jako klepnutí na systém): crop v bodech stránky.
  const band = %(band)s, ypt = %(ypt)s, ppt = %(ppt)s;
  let sx = 0, sy = 0, sw = img.width, sh = img.height;
  if (band > 0) {
    sy = Math.max(0, Math.min((ypt - band / 2) * ppt, img.height - band * ppt));
    sh = Math.min(img.height - sy, band * ppt);
  }
  cv.width = sw; cv.height = sh;
  cv.getContext('2d', { willReadFrequently: true })
    .drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);
  const res = detectBarlines(cv, ppt, { krok: %(krok)s, ypt: ypt - sy / ppt, offsetY: sy / ppt });
  return { w: cv.width, h: cv.height, bandTop: sy / ppt, res };
})()"""


async def ev(ws, i, expr):
    await ws.send(json.dumps({"id": i, "method": "Runtime.evaluate",
                              "params": {"expression": expr, "awaitPromise": True,
                                         "returnByValue": True}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == i:
            return msg


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", action="append", default=[])
    ap.add_argument("--krok", type=int, default=4)
    ap.add_argument("--ypt", default="86")
    ap.add_argument("--ppt", type=float, default=6.0)
    ap.add_argument("--band", type=float, default=0)
    a = ap.parse_args()
    imgs = a.img or [os.path.join(HERE, "fixtures", "barline-scan.png")]

    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
    page = [t for t in tabs if t["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                                  "params": {"url": "http://127.0.0.1:5173/"}}))
        await asyncio.sleep(2.5)
        ypts = [float(v) for v in str(a.ypt).split(",")]
        i = 10
        for p in imgs:
            with open(p, "rb") as fh:
                url = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
            for yv in ypts:
                expr = JS % {"url": json.dumps(url), "ppt": a.ppt, "krok": a.krok,
                             "ypt": yv, "band": a.band}
                r = await ev(ws, i, expr)
                i += 1
                if r.get("result", {}).get("exceptionDetails"):
                    print("CHYBA:", json.dumps(r["result"]["exceptionDetails"])[:600])
                    continue
                out = r["result"]["result"].get("value") or {}
                d = out.get("res", {})
                print(f"\n=== {os.path.basename(p)} ypt={yv}  "
                      f"(plátno {out.get('w')}x{out.get('h')}, pás od {out.get('bandTop')})")
                print(f"  ok={d.get('ok')} bars={d.get('bars')} staves={d.get('staves')} "
                      f"need={d.get('need')} thr={d.get('thr')}")
                print(f"  lines={[round(v, 1) for v in d.get('lines', [])]}")
                if d.get("reason"):
                    print(f"  reason={d['reason']}")
                print(f"  dbg={d.get('dbg')}")
                print(f"  diag={d.get('diag')}")
                print(f"  cands={[c for c in (d.get('cands') or []) if c[0] > 100][:14]}")


asyncio.run(main())
