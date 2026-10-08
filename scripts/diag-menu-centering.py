#!/usr/bin/env python3
"""DIAGNOSTIKA: vycentrování čísel/glyfů v anotačním menu — MĚŘENO Z PIXELŮ.

Jan: „V anotačním menu nejsou čísla a znaky vycentrovaný uprostřed tlačítek.
Konkrétně velikost tužky, značka dynamiky atd.“

Proč z pixelů: metrický výpočet (canvas measureText) dá jen to, jak je znak široký
a vysoký, ale NE to, kde ho prohlížeč v řádku posadí. Rozdíl mezi „flex vycentroval
řádek“ a „oko vidí znak uprostřed“ je právě v tom posazení. Proto se udělá snímek
obrazovky a změří se STŘED SKUTEČNÝCH NEPOZADÍOVÝCH PIXELŮ uvnitř výřezu tlačítka.

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/diag-menu-centering.py
"""
import asyncio
import base64
import importlib.util
import json
import os

import numpy as np
from PIL import Image

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness = _m.Harness


def ink_center(img, box, btn_box, tol=44, margin=6):
    """Střed OTISKU uvnitř výřezu tlačítka.

    ⚠️ Bere se STŘED OHRANIČUJÍCÍHO BOXU otisku, ne těžiště pixelů: u antialiasovaného
    znaku je těžiště zašuměné (naměřeno ±0,6 px, takže se na něm nedá ladit posun
    o 1 px) a oko stejně hodnotí hranice znaku, ne rozložení odstínů.
    """
    x, y, w, h = [int(round(v)) for v in box]
    if w < 8 or h < 8:
        return None
    crop = np.asarray(img.crop((x, y, x + w, y + h)).convert("RGB")).astype(int)
    # Pozadí z vnitřní části (rámeček tlačítka pryč) — jinak by se za „znak“ počal i obrys.
    m2 = margin
    inner = crop[m2:-m2, m2:-m2]
    if inner.size == 0:
        return None
    edge = np.concatenate([inner[:2].reshape(-1, 3), inner[-2:].reshape(-1, 3),
                           inner[:, :2].reshape(-1, 3), inner[:, -2:].reshape(-1, 3)])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    bg = vals[counts.argmax()]
    dist_bg = np.abs(inner - bg).sum(axis=2)
    mask = dist_bg > tol
    if mask.sum() < 6:
        return None
    ys, xs = np.nonzero(mask)
    return {
        "cx": x + m2 + (xs.min() + xs.max()) / 2,
        "cy": y + m2 + (ys.min() + ys.max()) / 2,
        "w_ink": int(xs.max() - xs.min() + 1), "h_ink": int(ys.max() - ys.min() + 1),
        "n": int(mask.sum()), "btn": btn_box,
    }


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.8)

        # rects všech tlačítek, která mají nést znak
        raw = await h.ev("""(() => {
          const out = [];
          const sel = '.annot-panel .ap-size, .annot-panel .ap-tool';
          document.querySelectorAll(sel).forEach((el, i) => {
            const btn = el.classList.contains('dyn-ico') ? el.closest('button') : el;
            if (!btn) return;
            const b = btn.getBoundingClientRect();
            const inner = el.getBoundingClientRect();
            const txt = (el.textContent || '').trim();
            out.push({ i, txt: txt || '(glyf)', cls: btn.className,
                       btn: [b.left, b.top, b.width, b.height],
                       inner: [inner.left, inner.top, inner.width, inner.height],
                       dsf: devicePixelRatio });
          });
          return JSON.stringify(out); })()""")
        items = json.loads(raw) if isinstance(raw, str) else raw

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        img = Image.open(__import__("io").BytesIO(base64.b64decode(shot["data"])))
        # snímek je ve fyzických pixelech (dsf) — přepočítat souřadnice
        dsf = items[0]["dsf"] if items else 1
        print(f"snímek {img.size[0]}×{img.size[1]}, devicePixelRatio={dsf}")

        print(f"\n{'znak':>7} {'tlačítko':>9} {'střed znaku':>18} {'odchylka od tlačítka':>22}")
        worst = []
        for it in items:
            btn = it["btn"]
            # výřez vnitřku tlačítka (bez rámečku), ve fyzických px
            pad = 4
            box = [(btn[0] + pad) * dsf, (btn[1] + pad) * dsf,
                   (btn[2] - 2 * pad) * dsf, (btn[3] - 2 * pad) * dsf]
            c = ink_center(img, box, btn)
            if not c:
                print(f"{it['txt'][:7]:>7} {'':>9}   (nic nenalezeno)")
                continue
            bcx = btn[0] + btn[2] / 2
            bcy = btn[1] + btn[3] / 2
            dx = c["cx"] / dsf - bcx
            dy = c["cy"] / dsf - bcy
            print(f"{it['txt'][:7]:>7} {str(int(btn[2]))+'x'+str(int(btn[3])):>9} "
                  f"{c['cx']/dsf:>8.1f},{c['cy']/dsf:<8.1f} "
                  f"dx={dx:>+6.2f} dy={dy:>+6.2f}  (px otisku={c['n']})")
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                worst.append((it["txt"], round(dx, 2), round(dy, 2)))

        print("\n=== NEVYCENTROVANÉ (|odchylka| > 0,5 px) ===")
        if not worst:
            print("žádné — všechno je vycentrované")
        for w in worst:
            print(f"   „{w[0]}“  dx={w[1]:+.2f}  dy={w[2]:+.2f}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
