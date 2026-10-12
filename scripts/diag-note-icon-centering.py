#!/usr/bin/env python3
"""DIAGNOSTIKA: vycentrování IKONY NÁSTROJE „Vkládání not" — měřeno z pixelů.

Proč vlastní měření, když na to je `calibrate-menu-glyphs.py`: ta kreslí výřez
tlačítka s odsazením 4 px a okrajem 6 px, takže z 40px tlačítka zbude ~26 px.
Nota je ale na výšku skoro celá (0,141 + 0,875 em ≈ 24 px při 1,5rem), takže se
ve výřezu OŘEZÁVÁ — naměřený střed se pak s posunem hýbe jen asi poloviční
rychlostí a kalibrace vyjde nesmyslně (vyšlo jí ≈ +10 px místo ≈ +5 px).

Tady se měří jednou, s výřezem přes CELÉ tlačítko: posun je čistý překlad,
takže hledaná hodnota je rovnou −naměřená odchylka. Druhé měření ji ověří.

    bash scripts/run-probe-fresh.sh scripts/diag-note-icon-centering.py
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

SEL = ".ap-tool[title^='Vkládání not'] .dyn-ico"


async def measure(h, dsf):
    """Odchylka středu OTISKU ikony od středu tlačítka (CSS px, kladná = níž)."""
    rect = await h.ev("""(() => {
      const el = document.querySelector(%s);
      if (!el) return null;
      const b = el.closest('button') || el;
      const r = b.getBoundingClientRect();
      return { l: r.left, t: r.top, w: r.width, h: r.height };
    })()""" % json.dumps(SEL))
    if not rect:
        return None
    shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
    # výřez = CELÉ tlačítko (jen 2 px na jeho rámeček), nic se neořezává
    pad = 2
    x = int((rect["l"] + pad) * dsf); y = int((rect["t"] + pad) * dsf)
    w = int((rect["w"] - 2 * pad) * dsf); hh = int((rect["h"] - 2 * pad) * dsf)
    crop = np.asarray(img.crop((x, y, x + w, y + hh))).astype(int)
    # pozadí = nejčastější barva v pásu u okrajů (tlačítko je jednolitá plocha)
    edge = np.concatenate([crop[:3].reshape(-1, 3), crop[-3:].reshape(-1, 3),
                           crop[:, :3].reshape(-1, 3), crop[:, -3:].reshape(-1, 3)])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    bg = vals[counts.argmax()]
    mask = np.abs(crop - bg).sum(axis=2) > 60
    ys, xs = np.nonzero(mask)
    if len(xs) < 6:
        return None
    cx = (x + (xs.min() + xs.max() + 1) / 2) / dsf
    cy = (y + (ys.min() + ys.max() + 1) / 2) / dsf
    return {"dx": cx - (rect["l"] + rect["w"] / 2),
            "dy": cy - (rect["t"] + rect["h"] / 2),
            "ink_h": (ys.max() + 1 - ys.min()) / dsf,
            "touches_edge": bool(xs.min() <= 1 or ys.min() <= 1
                                 or xs.max() >= w - 2 or ys.max() >= hh - 2)}


async def set_nudge(h, v):
    await h.ev("""(() => {
      let s = document.getElementById('calib');
      if (!s) { s = document.createElement('style'); s.id = 'calib';
                document.head.appendChild(s); }
      s.textContent = %s;
      return true;
    })()""" % json.dumps("%s { --glyph-nudge: %spx !important; }" % (SEL, v)))


async def main():
    async with Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.annot_toggle()
        await asyncio.sleep(0.9)
        dsf = await h.ev("window.devicePixelRatio") or 2

        force = os.environ.get("NOTY_NUDGE", "")
        if force:
            await set_nudge(h, force)
            await asyncio.sleep(0.3)
            print(f"posun vynucen na {force} px (mimo CSS aplikace)")
        else:
            print("měřím posun, který má aplikace v CSS")
        m = await measure(h, dsf)
        print("naměřeno:", m)
        if not m:
            print("FAIL: ikona se nenašla")
            return 1
        if m["touches_edge"]:
            print("POZOR: otisk se dotýká okraje tlačítka — posun je moc velký/malý")
        if not force:
            print(f"→ potřeba posunout o {round(-m['dy'], 2):+} px "
                  f"(tlačítko 40 px, otisk {m['ink_h']:.1f} px)")
        good = abs(m["dy"]) <= 0.6
        await h.ev("(() => { const s = document.getElementById('calib');"
                   " if (s) s.textContent = ''; return true; })()")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
