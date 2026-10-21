#!/usr/bin/env python3
"""Anotace musí zůstat NA NOTÁCH i po změně šířky čtecí plochy.

Jan (Oct 2026): po aktualizaci se noty posunuly, poznámky zůstaly na stejném
místě a „odsazení je uprostřed prázdna". Příčina: anotace jsou uložené
v referenčních px celé stránky (šířka = šířka čtecí plochy) a bez razítka se
po změně šířky čtou v jiném měřítku.

Sonda:
  1. nakreslí zvýraznění a zapamatuje jeho POZICI NA STRÁNCE (x / refW)
  2. změní šířku viewportu (jiná čtecí plocha) a znovu načte appku
  3. ověří, že pozice na stránce je stejná (souřadnice se přepočetly)
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check
TOOL_JS = ("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
           ".find(x => (x.title || '').startsWith(%s)); if (b) { b.click(); return 'ok'; }"
           " return 'missing'; })()")
INFO = """(() => {
  const dbg = window.__navdbg();
  const d = document.querySelector('.annot-layer path.hl');
  const p = document.querySelector('.annot-layer');
  const vb = p.viewBox.baseVal;
  return JSON.stringify({refW: dbg.refW, refH: dbg.refH,
    crop: {x: vb.x, y: vb.y, w: vb.width, h: vb.height},
    d: d ? d.getAttribute('d') : null,
    layerW: p.getBoundingClientRect().width});
})()"""


async def info(h):
    return json.loads(await h.ev(INFO))


def page_frac(inf):
    """kde na stránce zvýraznění je: podíl referenční šířky"""
    import re
    nums = [float(v) for v in re.findall(r"-?[0-9.]+", inf["d"])]
    xs = nums[0::2]
    return round((min(xs) + max(xs)) / 2 / inf["refW"], 4)


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(m.make_pdf(4))
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        f = await h.free_point()
        x, y = f["x"], f["y"]
        await h.ev(TOOL_JS % json.dumps("Zvýraznění"))
        await h.pen_tap(x - 70, y + 14)
        await h.pen_tap(x - 70, y - 14)
        await h.pen_tap(x + 70, y)
        await asyncio.sleep(0.8)

        a = await info(h)
        ok("zvýraznění existuje", bool(a["d"]), str(a)[:100])
        fa = page_frac(a)
        print("refW:", a["refW"], "poloha na stránce:", fa)

        # Zapnout RÁM (ořez) — poznámka se nesmí rozejít s notami ani tady
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Vycentrovat a preference'));"
                   " if (b) b.click(); })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { const b = [...document.querySelectorAll('.prefs-panel .zp-btn')]"
                   ".find(x => (x.title || '').includes('Oříznout')); if (b) b.click(); })()")
        await asyncio.sleep(1.8)
        fr = await info(h)
        ff = page_frac(fr)
        print("s rámem: refW:", fr["refW"], "crop:", fr["crop"], "poloha:", ff)
        ok("rám posune noty (crop je aktivní)", fr["crop"]["w"] < a["refW"], str(fr["crop"]))
        ok("rám nemění polohu poznámky na stránce", abs(ff - fa) < 0.005, f"{fa} -> {ff}")

        # Jiná šířka čtecí plochy (jiné zařízení / jiná verze) + reload z DB
        await h.set_tablet(560, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open()          # znovu načte appku z IndexedDB
        await asyncio.sleep(1.0)
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=30, label="library")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="page")
        await asyncio.sleep(1.2)

        b = await info(h)
        fb = page_frac(b)
        print("refW:", b["refW"], "poloha na stránce:", fb)
        ok("šířka soustavy se opravdu změnila", a["refW"] != b["refW"], f"{a['refW']} -> {b['refW']}")
        ok("poznámka zůstala na stejném místě stránky", abs(fa - fb) < 0.01,
           f"{fa} -> {fb}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
