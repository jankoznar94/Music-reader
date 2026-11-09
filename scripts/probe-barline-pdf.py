#!/usr/bin/env python3
"""Probe detekce čar na SKUTEČNÉM PDF (stránka not), přesně jako v appce.

Vezme PDF, vyrendruje pás stránky přes `renderPageRegion` (stejná cesta jako
klepnutí na systém), zavolá `detectBarlines` a vypíše, co našel: kandidáty,
jejich hlasy a výsledné čáry. Volitelně vypíše i sloupcový profil inkoustu
jednotlivých osnov (proč kterou čáru vzal/nevzal).

Předpoklad: `npx vite --port 5173`, Chrome na 9222, PDF ve scripts/fixtures/ (vite ho servíruje z /scripts/fixtures/).

Použití:
  python3 scripts/probe-barline-pdf.py --pdf /scripts/fixtures/ave.pdf --page 1 \
      --band 260 --ypt 200,300,400 --krok 4
"""
import argparse
import asyncio
import json
import urllib.request

import websockets

JS = """(async () => {
  const { renderPageRegion } = await import('/src/pdf.js');
  const { detectBarlines } = await import('/src/barLines.js');
  const blob = await (await fetch(%(pdf)s)).blob();
  const song = { data: blob, id: 'probe', name: 'probe' };
  const dim = await (await import('/src/pdf.js')).getPageWidthHeight(song, %(page)s);
  const out = [];
  for (const ypt of %(ypts)s) {
    const pdftop = %(pdftop)s;
    const bandH = %(band)s;
    const cropY = Math.max(0, Math.min(ypt - bandH / 2, dim.height - bandH));
    const crop = { x: 0, y: cropY, w: dim.width, h: bandH };
    const cv = document.createElement('canvas');
    const PPT = %(ppt)s, dpr = window.devicePixelRatio || 1;
    await renderPageRegion(song, %(page)s, cv, crop, dim.width * PPT / dpr, bandH * PPT / dpr);
    const pxPerPt = cv.width / crop.w;
    const det = detectBarlines(cv, pxPerPt, { krok: %(krok)s, ypt: ypt, offsetY: crop.y });
    out.push({ ypt, crop, w: cv.width, h: cv.height, pxPerPt, det });
  }
  return { dim, out };
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
    ap.add_argument("--pdf", default="/scripts/fixtures/ave.pdf")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--band", type=float, default=260)
    ap.add_argument("--ppt", type=float, default=6)
    ap.add_argument("--krok", type=int, default=4)
    ap.add_argument("--ypt", default="200,300,400")
    a = ap.parse_args()
    ypts = [float(v) for v in a.ypt.split(",")]

    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
    page = [t for t in tabs if t["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                                  "params": {"url": "http://127.0.0.1:5173/"}}))
        await asyncio.sleep(2.5)
        expr = JS % {"pdf": json.dumps(a.pdf), "page": a.page, "ypts": json.dumps(ypts),
                     "band": a.band, "ppt": a.ppt, "krok": a.krok, "pdftop": 0}
        r = await ev(ws, 10, expr)
        if r.get("result", {}).get("exceptionDetails"):
            print(json.dumps(r["result"]["exceptionDetails"])[:1200])
            return
        out = r["result"]["result"]["value"]
        print("stránka:", out["dim"])
        for o in out["out"]:
            d = o["det"]
            print(f"\n--- ypt={o['ypt']} crop y={o['crop']['y']} plátno {o['w']}x{o['h']} "
                  f"px/pt={o['pxPerPt']:.3f}")
            print(f"  ok={d['ok']} bars={d['bars']} staves={d['staves']} need={d.get('need')} thr={d.get('thr')}")
            print(f"  lines={[round(v,1) for v in d['lines']]}")
            if d.get("reason"):
                print(f"  reason={d['reason']}")
            print(f"  cands={d.get('cands')}")


asyncio.run(main())
