#!/usr/bin/env python3
"""OVĚŘENÍ dvou úprav čtečky not (Jan, Oct 2026):

  1) GESTO ZAPNE SVŮJ REŽIM SÁMO
     „Když použiji gesto třemi prsty, tak se automaticky zapne rotační mód.
      Když použiji gesto dvěma prsty, tak se automaticky zapne zoom/pozice režim.“
     → po třech prstech musí být `.rot-grid` (mřížka) V DOM a `rotPanelOpen` on;
       po dvou prstech musí být `.zoom-panel` v DOM a mřížka pryč.

  2) OKRAJOVÉ PRUHY ZŮSTÁVAJÍ I V ANOTAČNÍM REŽIMU
     „Když zapnu anotační režim, tak zmizí postranní podbarvené oblasti pro
      přepínání mezi stránkami. To bych ponechal i při anotačním módu.“
     → `.edge-hint` musí být v DOM v režimu čtení I v anotaci (jen při
       umisťování skoku na stránku se schová).

Prostředí: dev server na :5173 + headless Chrome s CDP na :9222
(`/tmp/start-chrome-noty.sh`). Dotyky se posílají POUZE přes
`Input.dispatchTouchEvent` — `Emulation.setTouchEmulationEnabled` doručování
dotyků ZABIJE (viz komentář v probe-pinch-robustness.py).
"""
import asyncio
import importlib.util
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = "http://127.0.0.1:9222"


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


def fresh_harness():
    """Harness na NOVĚ otevřeném tabu (čerstvý renderer doručuje dotyky)."""
    import json
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(_mod.APP_URL)
    h._fresh_target = info.get("id")
    return h


# Co je zrovna otevřené — čte se z DOM, ne z interního stavu Vue.
PANELS = r"""
(() => ({
  rotGrid: !!document.querySelector('.rot-grid'),
  zoomPanel: !!document.querySelector('.zoom-panel'),
  rotPanel: !!document.querySelector('.rot-panel'),
  edgeHints: document.querySelectorAll('.edge-hint').length,
  annotOn: !!document.querySelector('.annot-panel'),
  deg: (() => {
    const r = document.querySelector('.rotor'); if (!r) return null;
    const m = new DOMMatrix(getComputedStyle(r).transform);
    return +(Math.atan2(m.b, m.a) * 180 / Math.PI).toFixed(2);
  })(),
}))()
"""

CLOSE_PANELS = r"""
(() => {
  const btn = [...document.querySelectorAll('.tb-btn')]
    .filter(b => /Zvětšení|Rotace/.test(b.title || ''))
    .filter(b => b.classList.contains('on'));
  btn.forEach(b => b.click());
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
  if (!a) return false;
  a.click();
  return true;
})()
"""


async def open_viewer(h, pages=6):
    await h.open()
    await h.set_tablet(800, 1280, 2)
    await asyncio.sleep(1.0)
    existing = await h.ev("document.querySelectorAll('li.song').length")
    if not existing:
        await h.set_file_input("input[type=file]", _mod.make_pdf(pages))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="PDF upload")
    await h.ev(_mod.Harness.expand_authors_js())
    await h.wait_for("document.querySelectorAll('li.song').length > 0",
                     timeout=10, label="expand authors")
    await h.click(".song-name")
    await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="open viewer")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="first page")
    await asyncio.sleep(1.0)


def three_points(cx, cy, r=170, spread=300):
    return [(cx - r, cy, 12), (cx + r, cy, 12), (cx, cy + spread, 12)]


def two_points(cx, cy, r=100):
    return [(cx - r, cy, 12), (cx + r, cy, 12)]


def rotate_pts(pts, cx, cy, deg):
    import math
    out = []
    a = math.radians(deg)
    for (x, y, rr) in pts:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * math.cos(a) - dy * math.sin(a),
                    cy + dx * math.sin(a) + dy * math.cos(a), rr))
    return out


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await open_viewer(h)
        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        # ---- PREFLIGHT: bez doručovaných dotyků je měření nesmysl ----
        await h.ev("(() => { window.__pre=[];"
                   " document.addEventListener('touchstart', e => window.__pre.push(e.touches.length),"
                   " { capture: true, passive: true }); return true; })()")
        await h.touch("touchStart", two_points(cx, cy))
        await asyncio.sleep(0.1)
        await h.touch("touchEnd", [])
        pre = await h.ev("JSON.stringify(window.__pre)")
        ok("preflight: dvouprstý dotyk se doručí", bool(pre) and "2" in pre,
           f"touchstarty: {pre}")
        if not (pre and "2" in pre):
            print("\nPREFLIGHT FAILED — prostředí nedoručuje dotyky. Konec.")
            return ok.report()
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.4)

        # ================= 1) TŘI PRSTY → ROTAČNÍ MÓD SÁM =================
        base = await h.ev(PANELS)
        ok("1) výchozí stav: mřížka NENÍ a ani jeden režim není otevřený",
           (not base["rotGrid"]) and (not base["rotPanel"]) and (not base["zoomPanel"]),
           str(base))

        pts = three_points(cx, cy)
        await h.touch("touchStart", pts)
        await asyncio.sleep(0.15)
        during = await h.ev(PANELS)
        ok("1) třemi prsty se rotační mód zapne SÁM (mřížka je vidět)",
           during["rotGrid"] and during["rotPanel"], str(during))
        # otočíme trojici o 40° — mřížka musí zůstat, rotace proběhnout
        for i in range(1, 9):
            await h.touch("touchMove", rotate_pts(pts, cx, cy, 40 * i / 8))
            await asyncio.sleep(0.02)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        after = await h.ev(PANELS)
        ok("1) rotace skutečně proběhla (~40°)",
           after["deg"] is not None and abs(after["deg"] - base["deg"]) > 25,
           f"{base['deg']} -> {after['deg']}")
        ok("1) po gestu zůstává rotační mód otevřený (mřížka svítí)",
           after["rotGrid"], str(after))

        # ================= 2) DVA PRSTY → ZOOM MÓD SÁM =================
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.4)
        base2 = await h.ev(PANELS)
        p2 = two_points(cx, cy)
        await h.touch("touchStart", p2)
        await asyncio.sleep(0.15)
        during2 = await h.ev(PANELS)
        ok("2) dvěma prsty se zapne režim zvětšení a posunu (panel je vidět)",
           during2["zoomPanel"] and not during2["rotPanel"], str(during2))
        ok("2) při zoomu se mřížka NEZOBRAZUJE",
           not during2["rotGrid"], str(during2))
        for i in range(1, 9):
            r = 100 + 100 * i / 8
            await h.touch("touchMove", two_points(cx, cy, r))
            await asyncio.sleep(0.02)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        after2 = await h.ev(PANELS)
        ok("2) po dvouprstém gestu zůstává otevřený panel zoomu",
           after2["zoomPanel"], str(after2))

        # ================= 3) OKRAJOVÉ PRUHY V ANOTACI =================
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.4)
        read_hints = await h.ev(PANELS)
        ok("3) v režimu čtení jsou oba okrajové pruhy vidět",
           read_hints["edgeHints"] == 2, f"pruhů: {read_hints['edgeHints']}")
        await h.ev(TOGGLE_ANNOT)
        await asyncio.sleep(0.5)
        annot = await h.ev(PANELS)
        ok("3) anotační režim se skutečně zapnul",
           annot["annotOn"] and not annot["zoomPanel"] and not annot["rotPanel"],
           str(annot))
        ok("3) V ANOTACI okrajové pruhy ZŮSTÁVAJÍ (Jan: „ponechal i při anotačním módu“)",
           annot["edgeHints"] == 2, f"pruhů: {annot['edgeHints']}")
        ok("3) mřížka se v anotaci neobjevila sama",
           not annot["rotGrid"], str(annot))
        await h.ev(TOGGLE_ANNOT)
        await asyncio.sleep(0.4)

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
