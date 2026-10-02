#!/usr/bin/env python3
"""ŽIVÝ WEB: ověření dvou úprav čtečky not (Jan, Oct 2026) na PRODUKCI.

  1) tři prsty → rotační mód (mřížka) se zapne SÁM; dva prsty → panel zoomu
  2) okrajové pruhy (`.edge-hint`) zůstávají i v anotačním režimu

Proč samostatná sonda pro živý web: `devtoolsRawSetupState` v minifikovaném
buildu NEEXISTUJE, takže se stav čte z DOM (transformace, přítomnost prvků).
A hlavně: prohlížeč má z dřívějška nainstalovaný SW z produkce a ten drží app
shell v CacheStorage → sonda by viděla STARÉ chování a hlásila falešné FAILy.
Před měřením se proto odregistruje SW, smažou cache i IndexedDB.
"""
import asyncio
import importlib.util
import json
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = "http://127.0.0.1:9222"
LIVE = "https://harlequin-music-reader.web.app/"


def _load_harness():
    for cand in (
        os.path.join(_HERE, "cdp-e2e-harness.py"),
        os.path.expanduser(
            "~/.hermes/profiles/cfsb-agent/skills/software-development/"
            "pwa-pdf-viewer/scripts/cdp-e2e-harness.py"),
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_mod = _load_harness()
Harness, Check = _mod.Harness, _mod.Check


def fresh_harness(url=LIVE):
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(url)
    h._fresh_target = info.get("id")
    return h


CLEAN = r"""
(async () => {
  const rs = await navigator.serviceWorker.getRegistrations();
  for (const r of rs) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  indexedDB.deleteDatabase('noty-app');
  return { unregistered: rs.length, caches: (await caches.keys()).length };
})()
"""

PANELS = r"""
(() => ({
  rotGrid: !!document.querySelector('.rot-grid'),
  zoomPanel: !!document.querySelector('.zoom-panel:not(.rot-panel)'),
  edgeHints: document.querySelectorAll('.edge-hint').length,
  annotOn: !!document.querySelector('.annot-panel'),
  sw: navigator.serviceWorker.controller ? 'active' : 'none',
  deg: (() => {
    const r = document.querySelector('.rotor'); if (!r) return null;
    const m = new DOMMatrix(getComputedStyle(r).transform);
    return +(Math.atan2(m.b, m.a) * 180 / Math.PI).toFixed(2);
  })(),
}))()
"""

CLOSE_PANELS = r"""
(() => {
  [...document.querySelectorAll('.tb-btn')]
    .filter(b => /Zvětšení|Rotace/.test(b.title || ''))
    .filter(b => b.classList.contains('on')).forEach(b => b.click());
  const a = [...document.querySelectorAll('.tb-btn')]
    .find(b => (b.title || '').startsWith('Anotace'));
  if (a && a.classList.contains('on')) a.click();
  return true;
})()
"""

TOGGLE_ANNOT = r"""
(() => {
  const a = [...document.querySelectorAll('.tb-btn')]
    .find(b => (b.title || '').startsWith('Anotace'));
  if (!a) return false; a.click(); return true;
})()
"""


def three_points(cx, cy, r=170, spread=300):
    return [(cx - r, cy, 12), (cx + r, cy, 12), (cx, cy + spread, 12)]


def two_points(cx, cy, r=100):
    return [(cx - r, cy, 12), (cx + r, cy, 12)]


def rotate_pts(pts, cx, cy, deg):
    import math
    a = math.radians(deg)
    out = []
    for (x, y, rr) in pts:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * math.cos(a) - dy * math.sin(a),
                    cy + dx * math.sin(a) + dy * math.cos(a), rr))
    return out


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await h.open()
        # vyčisti starý SW/cache/DB a teprve pak navaž spojení s novým buildem.
        # POZOR: `h.goto()` v harnessu je skok NA STRÁNKU skladby, ne navigace
        # URL — naviguje se přes `Page.navigate` (jako v `Harness.open`).
        try:
            print("   úklid:", await h.ev(CLEAN, await_promise=True))
        except Exception as e:
            print("   úklid přeskočen:", e)
        await h.cdp("Page.navigate", {"url": LIVE + "?cb=" + str(int(time.time()))})
        await h.wait_for("document.readyState === 'complete'", timeout=30, label="reload")
        await asyncio.sleep(3.0)
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.5)

        # fixture nahrajeme přes skutečný input[type=file]
        await h.set_file_input("input[type=file]", _mod.make_pdf(6))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=90, label="PDF upload (live)")
        await h.ev(_mod.Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0",
                         timeout=15, label="expand authors")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=60, label="open viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=60, label="first page")
        await asyncio.sleep(1.5)

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        # preflight doručování dotyků
        await h.ev("(() => { window.__pre=[];"
                   " document.addEventListener('touchstart', e => window.__pre.push(e.touches.length),"
                   " { capture: true, passive: true }); return true; })()")
        await h.touch("touchStart", two_points(cx, cy))
        await asyncio.sleep(0.1)
        await h.touch("touchEnd", [])
        pre = await h.ev("JSON.stringify(window.__pre)")
        ok("preflight: dotyky se na živém webu doručí", bool(pre) and "2" in pre, f"{pre}")
        if not (pre and "2" in pre):
            print("\nPREFLIGHT FAILED — prostředí nedoručuje dotyky. Konec.")
            return ok.report()
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.5)

        base = await h.ev(PANELS)
        print("   stav:", base)
        ok("výchozí: mřížka ani panely nejsou otevřené",
           not base["rotGrid"] and not base["zoomPanel"], str(base))

        # 1) TŘI PRSTY → ROTAČNÍ MÓD SÁM
        pts = three_points(cx, cy)
        await h.touch("touchStart", pts)
        await asyncio.sleep(0.2)
        during = await h.ev(PANELS)
        ok("LIVE 1) tři prsty zapnou rotační mód (mřížka je vidět)",
           during["rotGrid"], str(during))
        for i in range(1, 9):
            await h.touch("touchMove", rotate_pts(pts, cx, cy, 40 * i / 8))
            await asyncio.sleep(0.03)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        after = await h.ev(PANELS)
        ok("LIVE 1) rotace proběhla (~40°)",
           after["deg"] is not None and abs(after["deg"] - base["deg"]) > 25,
           f"{base['deg']} -> {after['deg']}")
        ok("LIVE 1) mřížka po gestu zůstává", after["rotGrid"], str(after))

        # 2) DVA PRSTY → ZOOM MÓD SÁM, mřížka pryč
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.5)
        p2 = two_points(cx, cy)
        await h.touch("touchStart", p2)
        await asyncio.sleep(0.2)
        d2 = await h.ev(PANELS)
        ok("LIVE 2) dva prsty zapnou panel zvětšení a posunu",
           d2["zoomPanel"] and not d2["rotGrid"], str(d2))
        for i in range(1, 9):
            await h.touch("touchMove", two_points(cx, cy, 100 + 100 * i / 8))
            await asyncio.sleep(0.03)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        a2 = await h.ev(PANELS)
        ok("LIVE 2) po gestu zůstává otevřený panel zoomu", a2["zoomPanel"], str(a2))

        # 3) OKRAJOVÉ PRUHY V ANOTACI
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.5)
        r0 = await h.ev(PANELS)
        ok("LIVE 3) ve čtení jsou oba pruhy vidět", r0["edgeHints"] == 2,
           f"pruhů {r0['edgeHints']}")
        await h.ev(TOGGLE_ANNOT)
        await asyncio.sleep(0.6)
        an = await h.ev(PANELS)
        ok("LIVE 3) anotační režim se zapnul", an["annotOn"], str(an))
        ok("LIVE 3) V ANOTACI pruhy ZŮSTÁVAJÍ", an["edgeHints"] == 2,
           f"pruhů {an['edgeHints']}")

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
