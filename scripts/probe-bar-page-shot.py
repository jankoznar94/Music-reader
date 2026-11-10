#!/usr/bin/env python3
"""Snímek dočíslování CELÉ STRÁNKY — vizuální kontrola, kde čísla sedí.

Nahraje noty, otevře okno Číslování taktů, nechá dočíslovat zadanou stránku
(NOTY_PAGE, default 2), potvrdí „Vložit“ a uloží PNG celé stránky
(NOTY_OUT, default /tmp/barnum-page.png). Čísla musí být NAD horní osnovou
každého systému, ne v notách a ne nad klávesou.
"""
import asyncio
import base64
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get(
    "NOTY_PDF",
    "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
    "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
PAGE = int(os.environ.get("NOTY_PAGE", "2"))
OUT = os.environ.get("NOTY_OUT", "/tmp/barnum-page.png")


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(PAGE)
        # Panel číslování: tlačítko v liště je PŘEPÍNAČ — klikat, dokud nejsou
        # zapnuté oba režimy (barnum + anotace) a panel v DOM.
        for _ in range(4):
            st = json.loads(await h.ev("""(() => { const d=window.__barDev;
                return JSON.stringify({b:d.barnumMode.value, a:d.annotMode.value,
                  panel: !!document.querySelector('.barnum-panel')}); })()"""))
            if st["b"] and st["a"] and st["panel"]:
                break
            await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
            await asyncio.sleep(0.5)
        # ⚠️ `.bn-page` = dočíslovat celou STRÁNKU, `.bn-fill` = jen SYSTÉM.
        # Záměna dala 4 čísla místo 11 a vypadalo to jako rozbitá stránka.
        await h.ev("(() => { const b=document.querySelector('.bn-page'); if (b) b.click(); })()")
        for _ in range(12):
            if await h.ev("!!document.querySelector('.bn-page.on')"):
                break
            await asyncio.sleep(0.2)
        # bod, který je opravdu anotační vrstva (ne panel)
        pt = json.loads(await h.ev("""(() => {
            const v = document.querySelector('.viewer').getBoundingClientRect();
            for (const fy of [0.55, 0.7, 0.85, 0.45]) {
              for (const fx of [0.3, 0.5, 0.7, 0.4, 0.6]) {
                const x = v.left + v.width * fx, y = v.top + v.height * fy;
                const el = document.elementFromPoint(x, y);
                if (el && el.closest && el.closest('.annot-layer'))
                  return JSON.stringify({x: Math.round(x), y: Math.round(y)});
              }
            }
            return 'null'; })()"""))
        if pt in (None, "null"):
            print("CHYBA: nenašel jsem bod v anotační vrstvě")
            return
        await h.finger_tap(pt["x"], pt["y"])
        for _ in range(40):
            pn = await h.ev("(() => { const p=window.__barDev.barFillPreview.value;"
                            "return p ? (p.items||[]).length : -1; })()")
            if pn and pn > 0:
                break
            await asyncio.sleep(0.25)
        toast = await h.ev("window.__barDev.toast.value")
        await h.ev("(() => { const b=document.querySelector('.bn-fill-ok'); if (b) b.click(); })()")
        await asyncio.sleep(2.0)
        cnt = await h.ev("window.__barDev.annotations.value.items.filter(i=>i.barNum && i.page===%d).length"
                         % (PAGE - 1))
        pos = await h.ev("""(async () => {
            const d = window.__barDev;
            const s = await d.layerScale(d.currentPage.value);
            return JSON.stringify(d.annotations.value.items.filter(i => i.barNum && i.page === %d)
              .map(i => [i.text, Math.round(i.x / s), Math.round(i.y / s)])); })()"""
                        % (PAGE - 1), await_promise=True)
        # sbalit panely, ať je vidět celá stránka
        await h.ev("(() => { const c=document.querySelector('.bn-close'); if (c) c.click(); })()")
        await asyncio.sleep(0.8)
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(OUT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("toast:", toast)
        print("čísel na stránce:", cnt)
        print("pozice (PDF b):", pos)
        print("snímek:", OUT)


asyncio.run(main())
