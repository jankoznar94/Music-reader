#!/usr/bin/env python3
"""Ověří na ŽIVÉM webu, že bílé plátno svítí i v neupraveném stavu.

Pozor na tři pasti živého prostředí (viz references/deploy-verification-and-cache-headers.md):
  1) starý service worker servíruje staré stránky → odregistrovat + smazat cache
  2) IndexedDB si pamatuje stav → deleteDatabase před měřením
  3) devtoolsRawSetupState v produkci neexistuje → měř z DOM

Nahrává fixture přes skutečný input[type=file] (na webu není /tmp-fixture.pdf v appce,
ale my ho podstrčíme z disku — to jde).
"""
import asyncio
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_HERE)
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_APP, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness = _mod.Harness

LIVE = "https://harlequin-music-reader.web.app/"

M = r"""
(() => {
  const el = document.querySelector('.sheet-backdrop');
  const c  = document.querySelector('.pdf-canvas');
  const st = document.querySelector('.stage');
  const cs = getComputedStyle(document.querySelector('.viewer'));
  return {
    backdrop: !!el,
    backdropRect: el ? (() => { const b = el.getBoundingClientRect();
      return {t:+b.top.toFixed(0), l:+b.left.toFixed(0), w:+b.width.toFixed(0), h:+b.height.toFixed(0)}; })() : null,
    backdropBg: el ? getComputedStyle(el).backgroundColor : null,
    backdropZ: el ? getComputedStyle(el).zIndex : null,
    canvasShadow: c ? getComputedStyle(c).boxShadow : null,
    stageClasses: st ? st.className : null,
    canvasW: c ? +c.getBoundingClientRect().width.toFixed(1) : null,
    viewerBg: cs.backgroundColor,
  };
})()
"""

CLEAN = r"""
(async () => {
  const rs = await navigator.serviceWorker.getRegistrations();
  for (const r of rs) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  indexedDB.deleteDatabase('noty-app');
  return true;
})()
"""

results = {}


def line(tag, m):
    print(f"\n--- {tag} ---")
    for k, v in m.items():
        print(f"  {k}: {v}")
    results[tag] = m


async def run():
    async with Harness(url=LIVE) as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        # past 1+2: čistý SW i IndexedDB
        await h.ev(CLEAN, await_promise=True)
        await asyncio.sleep(1.0)
        await h.cdp("Page.reload", {"ignoreCache": True})
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(3.0)
        sw = await h.ev("navigator.serviceWorker.getRegistrations().then(r => r.length)",
                        await_promise=True)
        print(f"service workerů po reloadu: {sw}")

        # nahraj fixture a otevři skladbu
        pdf = _mod.make_pdf(6)
        await h.set_file_input("input[type=file]", pdf)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=90, label="PDF upload")
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0",
                         timeout=15, label="expand authors")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=60, label="viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=60, label="first page")
        await asyncio.sleep(2.0)

        m0 = await h.ev(M)
        line("NEUPRAVENY STAV (zoom 100 %, bez rotace)", m0)

        # zoom +5 %, pak rotace — ověř, že plátno svítí dál
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Zvětšení')); if(b) b.click(); })()")
        await asyncio.sleep(0.6)
        await h.ev("(() => { const b=[...document.querySelectorAll('.zp-btn')]"
                   ".find(x=>x.title==='Přiblížit'); if(b) b.click(); })()")
        await asyncio.sleep(1.2)
        m1 = await h.ev(M)
        line("PO ZOOMU (+5 %)", m1)

    # vyhodnocení
    print("\n=== VYHODNOCENI ===")
    a = results["NEUPRAVENY STAV (zoom 100 %, bez rotace)"]
    b = results["PO ZOOMU (+5 %)"]
    checks = [
        ("plátno existuje v NEUPRAVENÉM stavu", a["backdrop"] is True),
        ("plátno je bílé", a["backdropBg"] == "rgb(255, 255, 255)"),
        ("plátno kryje čtecí plochu od lišty dolů",
         a["backdropRect"] and a["backdropRect"]["l"] == 0 and a["backdropRect"]["w"] == 800),
        ("plátno je POD papírem (z-index 0, stage 1)",
         a["backdropZ"] == "0" and "backdrop" in (a["stageClasses"] or "")),
        ("stín papíru je vypnutý i v neupraveném stavu", a["canvasShadow"] == "none"),
        ("plátno svítí i po zoomu", b["backdrop"] is True),
        ("stín vypnutý i po zoomu", b["canvasShadow"] == "none"),
    ]
    fails = 0
    for label, okk in checks:
        print(f"{'OK  ' if okk else 'FAIL'} {label}")
        fails += 0 if okk else 1
    print("\n" + ("ALL CHECKS PASSED" if not fails else f"{fails} FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
