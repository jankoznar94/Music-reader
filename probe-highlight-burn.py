#!/usr/bin/env python3
"""Zvýrazňovač ve vypáleném PDF: noty pod ním musí zůstat čitelné.

Vypálí stránku se zvýrazňovačem přes černé linky/noty, výsledek vyrenderuje
PyMuPDF a změří jas pixelů. Zvýrazňovač se v PDF kreslí jako samostatná vrstva
s blend mode /Multiply (jako `mix-blend-mode: multiply` na obrazovce), takže
černé noty zůstanou černé a papír se jen zabarví.

Referenční hodnoty ze starého kódu (bez multiply), ať je vidět rozdíl:
  tlustá nota pod zvýrazněním: rgb(230,203,68) jas 196  -> nečitelná
  linka osnovy:                rgb(243,216,81) jas 209  -> nečitelná
Nový kód: nota jas 0, linka jas ~117, papír jas ~219.

Pozor: pás zvýraznění je v "ref px" (y roste dolů), PDF má počátek vlevo dole
— proto se vzorky zadávají v PDF souřadnicích (page y = 842 - ref y).
"""
import asyncio
import base64
import importlib.util
import json
import os

import fitz

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

APP = os.environ.get("APP_URL", "http://localhost:5199/")

JS = r"""
async (b64, mod) => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const share = await import(mod);
  // Pás zvýrazňovače přes noty (ref y 645..760 -> PDF y 82..197) + tah perem.
  const items = [
    { page: 0, tool: 'highlighter', color: '#ffe14d', opacity: 1,
      poly: [{x: 40, y: 645}, {x: 560, y: 645}, {x: 560, y: 760}, {x: 40, y: 760}] },
    { page: 0, tool: 'pencil', color: '#ff0000', width: 3, opacity: 1,
      points: [{x: 60, y: 800}, {x: 400, y: 800}] },
  ];
  const payload = share.buildOverlayPayload({
    song: { name: 'hl', composer: '', pages: 1, hiddenPages: [], frame: false },
    annotations: { ref: { w: 595, h: 842 }, items: items },
    jumps: [], bookmarks: [], bmManualOrder: false,
  });
  const out = await share.exportBurnedPdf(bytes, {
    items: items, ref: { w: 595, h: 842 },
    helpers: { displayText: () => '', borderRects: () => [], noteStroke: () => 0, noteFlipY: () => false },
    payload: payload,
  });
  let s = '';
  for (let i = 0; i < out.length; i++) s += String.fromCharCode(out[i]);
  return btoa(s);
}
"""


def sample(path):
    doc = fitz.open(path)
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    scale = 150 / 72.0

    def px(x, y):
        # PDF počátek vlevo dole, pixmapa vlevo nahoře
        return pix.pixel(int(x * scale), int((page.rect.height - y) * scale))

    return {
        'nota_pod_zvyraznenim': px(100, 159),   # tlustý černý pruh
        'linka_pod_zvyraznenim': px(300, 116),  # linka osnovy
        'papir_pod_zvyraznenim': px(450, 88),   # papír bez linek
        'papir_mimo': px(300, 500),             # bez zvýraznění
        'tah_perem': px(200, 42),
    }


def lum(rgb):
    r, g, b = rgb[:3]
    return round(0.299 * r + 0.587 * g + 0.114 * b)


async def main():
    fixture = open(os.path.join(_HERE, 'scripts/fixtures/notes-fixture.pdf'), 'rb').read()
    async with m.Harness(url=APP) as h:
        await h.set_tablet()
        await h.open()
        await asyncio.sleep(2)
        mod = os.environ.get('MOD', '/src/share.js')
        expr = f"({JS})({json.dumps(base64.b64encode(fixture).decode())}, {json.dumps(mod)})"
        data = base64.b64decode(await h.ev(expr, await_promise=True))

    out = '/tmp/hl-burn.pdf'
    open(out, 'wb').write(data)
    s = sample(out)
    print(f'vypálené PDF: {len(data)} B -> {out}')
    for k, v in s.items():
        print(f'  {k:26s} RGB={tuple(v[:3])}  jas={lum(v)}')

    nota, linka, papir = lum(s['nota_pod_zvyraznenim']), lum(s['linka_pod_zvyraznenim']), lum(s['papir_pod_zvyraznenim'])
    mimo = lum(s['papir_mimo'])
    r, g, b = s['papir_pod_zvyraznenim'][:3]
    checks = [
        ('nota pod zvýrazněním zůstala ČERNÁ (jas < 40)', nota < 40),
        ('linka osnovy je tmavší než papír aspoň o 60', papir - linka > 60),
        ('papír pod zvýrazněním je zabarvený (žlutý)', b < g < r and papir > 150),
        ('mimo zvýraznění zůstal papír bílý', mimo > 245),
    ]
    print()
    for label, ok in checks:
        print(f"{'OK  ' if ok else 'FAIL'} {label}")
    raise SystemExit(0 if all(ok for _, ok in checks) else 1)


asyncio.run(main())
