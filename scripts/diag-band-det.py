#!/usr/bin/env python3
"""Offline A/B detekce jednoho systému: nakrmí `detectBarlines` výřezem stránky
(PNG z reálného PDF, 6 px/bod) a vypíše, co z něj vyleze.

Proč: regresní sonda `probe-bar-fill-system.py` nahrává 11MB sken a běží minuty,
takže ladění okraje/koncové čáry přes ni je pomalé. Tenhle skript dělá totéž
rozhodnutí jako appka (`detectBarlines` s pásem a `ypt`), ale na PNG — iterace
jsou sekundy. PNG se dělá `/usr/bin/python3` + fitz, tenhle skript chce
`websockets` (tedy `python3`).

Použití:
  python3 scripts/diag-band-det.py  # konfigurace v CONFIG níž
"""
import asyncio
import base64
import json
import os
import urllib.request

import websockets

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
APP = os.environ.get("NOTY_APP", "http://localhost:5173/")
SCR = os.path.expanduser("~/.hermes/profiles/cfsb-agent/cache/scratch")

# (png, pxPerPt, ypt v pásu, offsetY, krok)
CONFIG = [
    ("band-p6-y300-h520.png", 6.0, 300, 40.0, 4),
    ("band-p10-y740-h520.png", 6.0, 740, 321.7, 4),
    ("band-p2-y190-h520.png", 6.0, 190, 0.0, 4),
    ("band-p2-y640-h520.png", 6.0, 640, 321.7, 4),
]

JS = """(async () => {
  const mod = await import('/src/barLines.js?' + Date.now());
  const img = new Image();
  img.src = %(url)s;
  await img.decode();
  const cv = document.createElement('canvas');
  cv.width = img.width; cv.height = img.height;
  cv.getContext('2d', { willReadFrequently: true }).drawImage(img, 0, 0);
  const res = mod.detectBarlines(cv, %(ppt)s, { krok: %(krok)s, ypt: %(ypt)s, offsetY: %(off)s });
  return { res };
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
    tabs = json.load(urllib.request.urlopen(CDP + "/json/list"))
    page = [t for t in tabs if t["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=128 << 20) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                                  "params": {"url": APP}}))
        await asyncio.sleep(3.0)
        i = 10
        for (png, ppt, ypt, off, krok) in CONFIG:
            p = os.path.join(SCR, png)
            with open(p, "rb") as fh:
                url = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
            r = await ev(ws, i, JS % {"url": json.dumps(url), "ppt": ppt, "krok": krok,
                                      "ypt": ypt, "off": off})
            i += 1
            if r.get("result", {}).get("exceptionDetails"):
                print("CHYBA:", json.dumps(r["result"]["exceptionDetails"])[:500])
                continue
            d = (r["result"]["result"].get("value") or {}).get("res", {})
            print(f"\n=== {png} ypt={ypt:.1f} off={off:.1f}")
            print(f"  ok={d.get('ok')} bars={d.get('bars')} staves={d.get('staves')} "
                  f"lines={[round(v, 1) for v in d.get('lines', [])]}")
            print(f"  opening={d.get('opening')} closing={d.get('closing')} "
                  f"staffLeftPt={d.get('staffLeftPt')}")
            print(f"  diag={d.get('diag')}")
            print(f"  dbg={d.get('dbg')}")
            print(f"  cands={[c for c in (d.get('cands') or [])]}")


asyncio.run(main())
