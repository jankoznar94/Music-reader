#!/usr/bin/env python3
"""DIAGNOSTIKA: tloušťka NOŽIČKY noty na stránce — měřeno z pixelů.

Jan: „Nešla by nožička noty udělat o trochu tlustší?“

Font NotyDyn (Bravura) kreslí nožičku 0,030 em (0,12 notové mezery — doporučení
SMuFL). V aplikaci se to ztlušťuje `stroke-width` u <text> noty (paint-order:
stroke), protože tloušťku jednoho tahu uvnitř glyfu jinak měnit nelze.

Sonda změří, jak tlustá je nožička NA OBRAZOVCE (sken řádků nad hlavičkou),
a to pro zadané hodnoty stroke-width, takže se dá ověřit i to, co má aplikace.

    bash scripts/run-probe-fresh.sh scripts/diag-note-stem-thickness.py
    bash scripts/run-probe-fresh.sh scripts/diag-note-stem-thickness.py 0 1 2
"""
import asyncio
import base64
import importlib.util
import io
import json
import os
import sys

import numpy as np
from PIL import Image

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_m.CDP_HTTP = CDP
Harness = _m.Harness

STEM_EM = 0.030        # tloušťka nožičky v glyfu (změřeno z obrysu Bravura)
WANT = [float(a) for a in sys.argv[1:]] or None


async def note_box(h):
    """Obrazový rámeček OTISKU noty v px (ne em box!).

    ⚠️ `getBBox()` u <text> vrací EM BOX (u NotyDyn 4,024 em = 120 px při 30 px),
    ne otisk — se starým měřením sonda „měřila“ prázdno nad notou. Otisk se
    dopočítá z metrik glyfu (`ctvrt_h`: šířka 0,332 em, nad účařím 0,875 em,
    pod účařím 0,141 em) a ukotvení se čte z atributů `x`/`y` prvku.
    """
    return await h.ev("""(() => {
      const t = [...document.querySelectorAll('.annot-layer text')].pop();
      if (!t) return null;
      const m = t.getScreenCTM();
      const a = new DOMPoint(parseFloat(t.getAttribute('x')),
                             parseFloat(t.getAttribute('y'))).matrixTransform(m);
      const size = parseFloat(getComputedStyle(t).fontSize);
      const s = Math.abs(m.a);
      const adv = 0.332, up = 0.875, dn = 0.141;      // ctvrt_h: metriky glyfu
      return { x: a.x - adv / 2 * size * s, y: a.y - up * size * s,
               w: adv * size * s, h: (up + dn) * size * s,
               size: size, sw: parseFloat(getComputedStyle(t).strokeWidth) || 0,
               scale: s, anchor: [a.x, a.y] };
    })()""")


async def stem_px(h, box, dsf):
    """Šířka nožičky v px = NEJUŽŠÍ souvislý běh přes celý otisk noty.

    Hlavička je ~9 px široká, nožička jednotky px — minimum přes řádky je tedy
    nožička. Práh je nízký (40), aby se počítaly i antialiasované okraje: uživatel
    vidí právě je, ne jen plnou barvu.
    """
    pad = 2
    x0 = int((box["x"] - pad) * dsf); y0 = int((box["y"] - pad) * dsf)
    w = int((box["w"] + 2 * pad) * dsf); hh = int((box["h"] + 2 * pad) * dsf)
    shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
    crop = np.asarray(img.crop((x0, y0, x0 + w, y0 + hh))).astype(int)
    edge = np.concatenate([crop[:2].reshape(-1, 3), crop[-2:].reshape(-1, 3)])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    bg = vals[counts.argmax()]
    mask = np.abs(crop - bg).sum(axis=2) > 40
    runs = []
    for row in mask:
        xs = np.nonzero(row)[0]
        if len(xs) == 0:
            continue
        cuts = np.split(xs, np.nonzero(np.diff(xs) > 2)[0] + 1)
        for c in cuts:
            if len(c) >= 1:
                runs.append(len(c))
    if not runs:
        return None
    runs = np.array(runs)
    return {"min": int(runs.min()), "median": float(np.median(runs)), "max": int(runs.max()),
            "n": int(len(runs))}


async def main():
    async with Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.reset_db()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.annot_toggle()
        dsf = await h.ev("window.devicePixelRatio") or 2

        # vložíme jednu čtvrťovou notu (nožička nahoru) a necháme ji na stránce
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Vkládání not'));"
                   " if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        p = await h.free_point()
        await h.pen_stroke(p["x"], p["y"], p["x"] + 2, p["y"] + 2)
        await asyncio.sleep(0.8)
        tpt = await h.ev("""(() => {
          const card = document.querySelector('.text-input-card');
          if (!card) return null;
          for (const b of card.querySelectorAll('.mark-sec .dyn-btn')) {
            if (b.title === 'čtvrťová nota') {
              const r = b.getBoundingClientRect();
              return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
            }
          }
          return null; })()""")
        if not tpt:
            print("FAIL: dlaždice „čtvrťová nota“ nenalezena")
            return 1
        await h.pen_tap(tpt[0], tpt[1])
        await asyncio.sleep(1.0)

        box = await note_box(h)
        if not box:
            print("FAIL: nota na stránce není")
            return 1
        print(f"nota na obrazovce: otisk {box['w']:.1f}×{box['h']:.1f} px, "
              f"velikost {box['size']:.1f}, měřítko vrstvy {box['scale']:.3f}, "
              f"stroke-width {box['sw']}")
        print(f"→ nožička v glyfu má {STEM_EM} em = {STEM_EM * box['size'] * box['scale']:.2f} px "
              f"na obrazovce")
        print()

        # 1) co má aplikace TEĎ (nic neměnit) — tohle je ta hodnota, kterou Jan uvidí
        cur = await h.ev("""(() => {
          const t = [...document.querySelectorAll('.annot-layer text')].pop();
          const cs = getComputedStyle(t);
          return { stroke: t.getAttribute('stroke'), sw: t.getAttribute('stroke-width'),
                   paint: t.getAttribute('paint-order') };
        })()""")
        r0 = await stem_px(h, box, dsf)
        ok_app = bool(cur and cur["stroke"] and float(cur["sw"] or 0) > 0)
        print(f"V APLIKACI:  stroke={cur['stroke']!r}, stroke-width={cur['sw']!r}, "
              f"paint-order={cur['paint']!r}")
        if r0:
            print(f"             nožička na obrazovce: min {r0['min']} / medián {r0['median']:.1f} px "
                  f"({'ztluštěná' if ok_app else 'BEZ ztluštění — chyba!'})")
        print()
        print("A/B: jak se nožička mění s jinou hodnotou stroke-width")
        vals = WANT or [0.0, 0.5, 0.75, 0.9, 1.4]
        for sw in vals:
            await h.ev("""(() => {
              const t = [...document.querySelectorAll('.annot-layer text')].pop();
              if (!t) return false;
              // Bez barvy tahu (`stroke`) by se šířka vůbec neprojevila —
              // v aplikaci se váže na barvu noty (:stroke="it.color").
              if (%s > 0) {
                t.setAttribute('stroke', getComputedStyle(t).fill);
                t.setAttribute('stroke-width', %s);
                t.setAttribute('paint-order', 'stroke');
              } else {
                t.removeAttribute('stroke'); t.setAttribute('stroke-width', 0);
              }
              return true; })()""" % (json.dumps(sw), json.dumps(sw)))
            await asyncio.sleep(0.35)
            r = await stem_px(h, box, dsf)
            if not r:
                print(f"stroke-width {sw:>5}:   (nožička se nenašla)")
                continue
            # nožička v glyfu (em × velikost) + přírůstek tahu (v jednotkách vrstvy)
            pred = (STEM_EM * box["size"] + sw) * box["scale"]
            print(f"stroke-width {sw:>5}:   naměřeno min {r['min']} / medián {r['median']:.1f} / "
                  f"max {r['max']} px  (z {r['n']} běhů)   "
                  f"předpověď {pred:.2f} px  (+{sw * box['scale']:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
