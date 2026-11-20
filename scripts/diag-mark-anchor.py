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
    text: 'A', size: 40, color: '#0b6bff', opacity: 1, border: false,
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
  // Rámeček značky (rect s třídou text-border) — má být modrý a STŘEDEM na bodu.
  const r = document.querySelector('.annot-layer rect.text-border');
  const rb = r ? r.getBBox() : null;
  const cs = r ? getComputedStyle(r) : null;
  return {
    attrs: { x: t.getAttribute('x'), y: t.getAttribute('y'),
             anchor: t.getAttribute('text-anchor'), size: s },
    bbox: { x: bb.x, y: bb.y, w: bb.width, h: bb.height,
            left: bb.x, right: bb.x + bb.width,
            centerX: bb.x + bb.width / 2, centerY: bb.y + bb.height / 2 },
    frame: rb ? {
      x: rb.x, y: rb.y, w: rb.width, h: rb.height,
      centerX: rb.x + rb.width / 2, centerY: rb.y + rb.height / 2,
      stroke: cs.stroke, strokeWidth: cs.strokeWidth,
    } : null,
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
        # panel je potřeba kvůli tlačítkům velikosti; zároveň díky němu platí
        # „s otevřeným oknem jsou značky vidět"
        await h.ev("document.querySelector('.tb-mark').click()")
        await h.wait_for("!!document.querySelector('.marks-panel')", 10, "panel Značky")
        await asyncio.sleep(0.5)
        info = await h.ev(INFO)
        print(json.dumps(info, indent=1, ensure_ascii=False))
        # měřítko vrstvy: šířka viewBoxu vs šířka stránky v bodech
        bb = info["bbox"]
        dx = bb["centerX"] - 300
        dy = bb["centerY"] - 400
        print(f"střed otisku vůči bodu ťuknutí: dx={dx:.1f} px, dy={dy:.1f} px (velikost 40)")
        print("PASS střed na bodu" if abs(dx) <= 4 and abs(dy) <= 4
              else "FAIL text není vycentrovaný na bod")

        fr = info.get("frame")
        if not fr:
            print("FAIL chybí rámeček značky")
        else:
            fdx, fdy = fr["centerX"] - 300, fr["centerY"] - 400
            print(f"rámeček: {fr['w']:.1f}×{fr['h']:.1f}, stroke={fr['stroke']}, "
                  f"střed dx={fdx:.1f} dy={fdy:.1f}")
            covers = fr["w"] >= bb["w"] + 2 and fr["h"] >= bb["h"] + 2
            print(f"písmeno {bb['w']:.1f}×{bb['h']:.1f}, rámeček {fr['w']:.1f}×{fr['h']:.1f}")
            print("PASS rámeček je čtverec, obepíná písmeno a sedí středem na bodu"
                  if abs(fdx) <= 4 and abs(fdy) <= 4 and abs(fr["w"] - fr["h"]) <= 1.5 and covers
                  else "FAIL rámeček nesedí")

        # velikost písma značek: tlačítko L v panelu musí změnit i vykreslení
        b = json.loads(await h.ev(
            "(() => { const b = [...document.querySelectorAll('.marks-panel .jp-btn')]"
            ".find(x => (x.textContent || '').trim() === 'L'); if (!b) return 'null';"
            " const r = b.getBoundingClientRect();"
            " return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}); })()"))
        await h.finger_tap(b["x"], b["y"])
        await asyncio.sleep(0.8)
        after = await h.ev(INFO)
        print("velikost po L:", after["attrs"]["size"], "| rámeček:",
              None if not after.get("frame") else round(after["frame"]["w"], 1))
        ok_size = float(after["attrs"]["size"]) == 26
        ok_frame = bool(after.get("frame")) and abs(after["frame"]["w"] - fr["w"]) > 3
        print("PASS velikost se změnila i s rámečkem" if ok_size and ok_frame
              else "FAIL velikost se nepropsala")
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
