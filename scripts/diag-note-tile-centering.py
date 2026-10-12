#!/usr/bin/env python3
"""DIAGNOSTIKA: vycentrování OBRÁZKŮ NOT v dlaždicích nabídky — měřeno z pixelů.

Jan: „V nabídce not jsou obrázky not zarovnané na střed podle bříška. Měly by být
zarovnané na střed celé. Nožičky jsou teď mimo tlačítka.“

CSS (flex) vycentruje ÚČAŘÍ, ale otisk noty visí nad ním — u noty s nožičkou
o (y0+y1)/2 em. Sonda měří STŘED SKUTEČNÉHO OTISKU v každé dlaždici (z pixelů,
výřez uvnitř rámečku, aby se nepletl okraj a zaoblené rohy) a porovnává ho se
středem dlaždice. Očekává se do ~1,5 px.

    bash scripts/run-probe-fresh.sh scripts/diag-note-tile-centering.py
"""
import asyncio
import base64
import importlib.util
import io
import json
import os

import numpy as np
from PIL import Image

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.CDP_HTTP = CDP
Harness = _m.Harness

TOL = 1.5   # px
# Když se měří ŽIVÝ web, musí se nejdřív odregistrovat service worker a smazat
# cache — jinak se změří stará nasazená verze a centrování „nevyjde“.
TARGET = os.environ.get("NOTY_TARGET", "") or None


async def tiles(h):
    return await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      return [...card.querySelectorAll('.mark-sec .dyn-btn')].map(b => {
        const r = b.getBoundingClientRect();
        const g = b.querySelector('.nota-glyf');
        const gr = g ? g.getBoundingClientRect() : null;
        return { title: b.title, x: r.left, y: r.top, w: r.width, h: r.height,
                 span: gr ? { x: gr.left, y: gr.top, w: gr.width, h: gr.height } : null };
      });
    })()""")


async def ink_center(img, t, dsf, margin=6):
    x = int((t["x"] + margin) * dsf); y = int((t["y"] + margin) * dsf)
    w = int((t["w"] - 2 * margin) * dsf); hh = int((t["h"] - 2 * margin) * dsf)
    crop = np.asarray(img.crop((x, y, x + w, y + hh))).astype(int)
    edge = np.concatenate([crop[:2].reshape(-1, 3), crop[-2:].reshape(-1, 3),
                           crop[:, :2].reshape(-1, 3), crop[:, -2:].reshape(-1, 3)])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    bg = vals[counts.argmax()]
    mask = np.abs(crop - bg).sum(axis=2) > 60
    ys, xs = np.nonzero(mask)
    if len(xs) < 6:
        return None
    return {"cx": (x + (xs.min() + xs.max() + 1) / 2) / dsf,
            "cy": (y + (ys.min() + ys.max() + 1) / 2) / dsf,
            "w": (xs.max() + 1 - xs.min()) / dsf, "h": (ys.max() + 1 - ys.min()) / dsf,
            "tile": t}


async def main():
    async with Harness(url=TARGET or _m.APP_URL) as h:
        await h.open()
        if TARGET:
            print("měřím živý web:", TARGET)
            await h.ev("(async () => {"
                       " const rs = await navigator.serviceWorker.getRegistrations();"
                       " for (const r of rs) await r.unregister();"
                       " for (const k of await caches.keys()) await caches.delete(k);"
                       " return true; })()", await_promise=True)
            await h.ev("indexedDB.deleteDatabase('noty-app')")
            await h.cdp("Page.reload", {"ignoreCache": True})
            await h.wait_for("document.readyState === 'complete'", label="reload")
            await asyncio.sleep(2.0)
        await h.set_tablet()
        await h.reset_db()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.annot_toggle()
        dsf = await h.ev("window.devicePixelRatio") or 2

        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Vkládání not'));"
                   " if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        p = await h.free_point()
        if not p:
            print("FAIL: nenašel se bod na vrstvě")
            return 1
        await h.pen_stroke(p["x"], p["y"], p["x"] + 2, p["y"] + 2)
        await asyncio.sleep(0.9)
        if not await h.ev("!!document.querySelector('.text-input-card')"):
            print("FAIL: dialog noty se neotevřel")
            return 1

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")

        bad = 0
        print(f"{'dlaždice':>24} {'dx':>7} {'dy':>7} {'otisk':>13}  posun v CSS")
        for t in (await tiles(h) or []):
            ink = await ink_center(img, t, dsf)
            if not ink:
                print(f"{t['title']:>24}   (otisk nenalezen)")
                bad += 1
                continue
            cx = t["x"] + t["w"] / 2
            cy = t["y"] + t["h"] / 2
            dx = ink["cx"] - cx
            dy = ink["cy"] - cy
            nudge = await h.ev("(() => { const c = document.querySelector('.text-input-card');"
                               " const b = [...c.querySelectorAll('.mark-sec .dyn-btn')]"
                               ".find(x => x.title === %s); const g = b && b.querySelector('.nota-glyf');"
                               " return g ? getComputedStyle(g).transform : 'none'; })()"
                               % json.dumps(t["title"]))
            over = (abs(dx) > TOL or abs(dy) > TOL)
            bad += 1 if over else 0
            print(f"{t['title']:>24} {dx:>+7.2f} {dy:>+7.2f} "
                  f"{ink['w']:>5.1f}×{ink['h']:<6.1f} {nudge}  {'' if not over else '<-- MIMO TOLERANCI'}")
            # otisk se nesmí dotýkat okraje dlaždice
            if ink["h"] > t["h"] - 2 or ink["w"] > t["w"] - 2:
                print(f"{'':>24}   POZOR: otisk je větší než dlaždice "
                      f"({ink['w']:.1f}×{ink['h']:.1f} vs {t['w']:.0f}×{t['h']:.0f})")

        print()
        print("VERDICT:", "OK — všechny otisky jsou vycentrované" if bad == 0
              else f"{bad} dlaždic mimo toleranci ±{TOL} px")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
