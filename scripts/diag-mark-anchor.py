#!/usr/bin/env python3
"""Kam přesně se značka položí vůči bodu ťuknutí (Jan, 20. 11. 2026).

Značka se ukládá jako anotace s `x, y` = bod ťuknutí v souřadnicích PDF.
Když je zapnuté zobrazení v notách, kreslí se jako text — otázka je, jestli
je na tom bodě STŘEDEM, nebo LEVOU HRANOU (a jak je to s účařím).

Sonda změří skutečně vykreslený element ve vrstvě:
  - uložené x,y (PDF souřadnice) a přepočet do vrstvy (× měřítko),
  - atributy <text> (x, y, text-anchor, font-size),
  - jeho getBBox() → levý okraj, střed, účaří.
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "..", "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
Harness = m.Harness

APP = os.environ.get("APP_URL", "http://localhost:5173/")

SEED = """(() => {
  const d = window.__barDev;
  d.annotations.value.items = [{
    id: 'anchor-1', page: 0, tool: 'text', mk: true, hidden: true,
    text: 'A', size: 40, color: '#000000', opacity: 1, border: false,
    x: 300, y: 400,
  }];
  d.mkVisible.value = true;
  d.currentPage.value = 0;
  return 1;
})()"""

INFO = r"""(() => {
  const layer = document.querySelector('.annot-layer');
  const t = [...document.querySelectorAll('.annot-layer text')]
    .find(e => (e.textContent || '').trim() === 'A');
  if (!t) return { error: 'text nenalezen' };
  const bb = t.getBBox();
  const vb = layer.viewBox.baseVal;
  const s = t.getAttribute('font-size');
  return {
    attrs: { x: t.getAttribute('x'), y: t.getAttribute('y'),
             anchor: t.getAttribute('text-anchor'), size: s },
    bbox: { x: bb.x, y: bb.y, w: bb.width, h: bb.height,
            left: bb.x, right: bb.x + bb.width,
            centerX: bb.x + bb.width / 2, centerY: bb.y + bb.height / 2 },
    viewBox: [vb.x, vb.y, vb.width, vb.height],
    layerScale: layer.getAttribute('data-scale') || null,
  };
})()"""


async def main():
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.open_song(pdf=m.make_pdf(8), pages=8)
        await asyncio.sleep(1.0)
        await h.ev(SEED)
        await asyncio.sleep(0.8)
        info = await h.ev(INFO)
        print(json.dumps(info, indent=1, ensure_ascii=False))
        # měřítko vrstvy: šířka viewBoxu vs šířka stránky v bodech
        bb = info["bbox"]
        dx = bb["centerX"] - 300
        dy = bb["centerY"] - 400
        print(f"střed otisku vůči bodu ťuknutí: dx={dx:.1f} px, dy={dy:.1f} px (velikost 40)")
        print("PASS střed na bodu" if abs(dx) <= 4 and abs(dy) <= 4
              else "FAIL text není vycentrovaný na bod")
        # náhled: výřez kolem značky + křížek v místě ťuknutí (jen do screenshotu)
        box = await h.ev(
            "(() => { const l = document.querySelector('.annot-layer');"
            " const t = [...document.querySelectorAll('.annot-layer text')]"
            "  .find(e => (e.textContent || '').trim() === 'A');"
            " const b = t.getBBox();"
            " const r = l.getBoundingClientRect();"
            " const vb = l.viewBox.baseVal;"
            " const k = r.width / vb.width;"
            " return [r.x + (b.x - vb.x) * k - 40, r.y + (b.y - vb.y) * k - 40,"
            "         (b.width) * k + 80, (b.height) * k + 80]; })()")
        raw = await h.cdp("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": box[0], "y": box[1], "width": box[2], "height": box[3], "scale": 4},
        })
        import base64
        with open("/tmp/marks-centered.png", "wb") as f:
            f.write(base64.b64decode(raw["data"]))
        print("saved /tmp/marks-centered.png")


asyncio.run(main())
