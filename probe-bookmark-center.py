#!/usr/bin/env python3
"""Dolní lišta: aktivní záložka se drží na STŘEDU, na krajích u dorazu.

14stránkový sešit, 10 záložek (str. 1..10) se širokými popisky → lišta se
musí scrollovat. Ověřuje se:
  * prostřední záložka je po přechodu vycentrovaná (±8 px),
  * první záložka drží scrollLeft ≈ 0, poslední ≈ max (dál to nejde),
  * po návratu doprostřed je zase na středu.
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check, make_pdf = m.Harness, m.Check, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")

GET_SONG = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].id : null);
  };
})
"""

SEED = r"""
((songId) => new Promise((resolve) => {
  const items = [];
  for (let i = 0; i < 10; i++) {
    items.push({ id: 'bm-' + i, page: i, label: 'Skladba ' + (i + 1) });
  }
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: false });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""

GEO = r"""
(() => {
  const strip = document.querySelector('.bookmark-strip');
  if (!strip) return null;
  const on = strip.querySelector('.bookmark-btn.on');
  const s = strip.getBoundingClientRect();
  const r = on ? on.getBoundingClientRect() : null;
  return {
    scrollLeft: strip.scrollLeft,
    max: strip.scrollWidth - strip.clientWidth,
    center: s.left + s.width / 2,
    chipCenter: r ? r.left + r.width / 2 : null,
    label: on ? on.textContent.trim() : null,
    count: strip.querySelectorAll('.bookmark-btn').length,
  };
})()
"""


class P:
    def __init__(self):
        self.inner = Check()
        self.n = 0

    def __call__(self, ok, detail=""):
        self.n += 1
        self.inner(f"check {self.n}: {detail[:60]}", ok, detail="")

    def report(self):
        return self.inner.report()


async def main():
    c = P()
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.cdp("Storage.clearDataForOrigin",
                    {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open_song(pdf=make_pdf(14), pages=14)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačtený song"
        assert await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True), "seed"
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.0)
        # lišty musí být vidět
        for _ in range(3):
            cls = await h.ev("(document.querySelector('.top-bar')||{}).className || ''")
            if "hidden" not in cls:
                break
            g = await h.geo()
            await h.finger_tap(g["left"] + g["w"] / 2, g["top"] + g["h"] / 2)
            await asyncio.sleep(0.8)
        await h.wait_for("document.querySelectorAll('.bookmark-strip .bookmark-btn').length === 10",
                         15, "lišta")
        await asyncio.sleep(0.5)

        g0 = await h.ev(GEO)
        c(g0 is not None and g0["max"] > 40, f"lišta přetéká, scroll je potřeba (max {g0 and g0['max']})")

        await h.goto(6)          # Skladba 6 = prostředek programu
        await asyncio.sleep(1.6)  # doběhne smooth scroll
        g = await h.ev(GEO)
        c(g["label"] and "Skladba 6" in g["label"], f"aktivní je Skladba 6 ({g['label']})")
        c(g["chipCenter"] is not None and abs(g["chipCenter"] - g["center"]) <= 8,
          f"prostřední záložka je na středu (odchylka {None if g['chipCenter'] is None else round(g['chipCenter'] - g['center'], 1)} px)")

        await h.goto(1)
        await asyncio.sleep(1.6)
        g = await h.ev(GEO)
        c("Skladba 1" in (g["label"] or ""), f"aktivní je Skladba 1 ({g['label']})")
        c(g["scrollLeft"] <= 1, f"u první záložky doraz vlevo (scrollLeft {g['scrollLeft']})")

        await h.goto(10)
        await asyncio.sleep(1.6)
        g = await h.ev(GEO)
        c("Skladba 10" in (g["label"] or ""), f"aktivní je Skladba 10 ({g['label']})")
        c(g["scrollLeft"] >= g["max"] - 1, f"u poslední doraz vpravo ({g['scrollLeft']} / {g['max']})")

        await h.goto(7)
        await asyncio.sleep(1.6)
        g = await h.ev(GEO)
        c(g["chipCenter"] is not None and abs(g["chipCenter"] - g["center"]) <= 8,
          f"po návratu doprostřed zase na středu (odchylka {None if g['chipCenter'] is None else round(g['chipCenter'] - g['center'], 1)} px)")

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
