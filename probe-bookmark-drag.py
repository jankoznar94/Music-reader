#!/usr/bin/env python3
"""Ověření řazení záložek tažením (drag & drop) na dev serveru.

Co se měří (skutečné dotykové eventy přes CDP, ne syntetické PointerEventy):
  1. při tažení existuje právě JEDEN duch (.bm-ghost) a JEDEN prázdný slot
     (.jp-gap) a slot je na místě, kam položka opravdu spadne;
  2. po puštění je pořadí v DOM i v IndexedDB stejné jako slot, který uživatel
     viděl;
  3. po puštění Nezůstane duch, slot, ani .dragging („označený řádek“);
  4. tap na táhlo bez pohybu nic nepřesune a nic nezanechá.
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
    r.onerror = () => resolve(null);
  };
  q.onerror = () => resolve(null);
})
"""

SEED = r"""
((songId) => new Promise((resolve) => {
  const items = [
    { id: 'bm-a', page: 0, label: 'A' },
    { id: 'bm-b', page: 1, label: 'B' },
    { id: 'bm-c', page: 2, label: 'C' },
    { id: 'bm-d', page: 3, label: 'D' },
  ];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: true });
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => resolve(false);
  };
  q.onerror = () => resolve(false);
}))(%s)
"""

DB_ORDER = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('bookmarks', 'readonly').objectStore('bookmarks').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].items.map(i => i.id) : null);
  };
  q.onerror = () => resolve(null);
})
"""

ROWS = r"""
(() => [...document.querySelectorAll('.jp-list .jp-item')].map(el => {
  const r = el.getBoundingClientRect();
  const h = el.querySelector('.jp-drag').getBoundingClientRect();
  return { id: (el.textContent || '').trim(), top: r.top, bottom: r.bottom, h: r.height,
           hx: h.left + h.width / 2, hy: h.top + h.height / 2 };
}))()
"""

STATE = r"""
(() => ({
  ghosts: document.querySelectorAll('.bm-ghost').length,
  gaps: document.querySelectorAll('.jp-gap').length,
  dragging: document.querySelectorAll('.jp-item.dragging').length,
  ids: [...document.querySelectorAll('.jp-list .jp-item .jp-item-label')].map(e => e.textContent.trim()),
}))()
"""


def label_of(text):
    return text.split('·')[-1].strip() if '·' in text else text.strip()


async def drag(h, x, y0, y1, steps=14):
    """Skutečné prstové tažení: touchStart na táhle, plynulé pohyby, touchEnd."""
    await h.touch("touchStart", [(x, y0, 12)])
    await asyncio.sleep(0.05)
    for i in range(1, steps + 1):
        await h.touch("touchMove", [(x, y0 + (y1 - y0) * i / steps, 12)])
        await asyncio.sleep(0.03)
    await asyncio.sleep(0.05)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.6)


class P:
    """Adaptér: `c(podmínka, detail)` -> Check s číslovaným štítkem."""

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
        await h.open()                     # nejdřív navigace, jinak je IndexedDB zakázaná
        await h.open_song(pdf=make_pdf(8), pages=8)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačetl se song"
        assert await h.ev(SEED % json.dumps(song), await_promise=True), "seed selhal"

        await h.open()                     # reload, ať se záložky načtou z DB
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.0)

        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Přidat záložku')); b && b.click(); return !!b; })()")
        await h.wait_for("document.querySelectorAll('.jp-list .jp-item').length === 4", 10, "panel záložek")
        await asyncio.sleep(0.3)

        rows = await h.ev(ROWS)
        c(len(rows) == 4, f"4 řádky v seznamu (je {len(rows)})")
        st = await h.ev(STATE)
        c(st["ghosts"] == 0 and st["gaps"] == 0 and st["dragging"] == 0, f"čistý start: {st}")

        # --- 1) táhnout A dolů na pozici C (dva sloty) -----------------------
        a, b, cc, d = rows
        x = a["hx"]
        await drag(h, x, a["hy"], cc["bottom"] - 4)

        mid = await h.ev(STATE)
        db = await h.ev(DB_ORDER, await_promise=True)
        dom = [label_of(t) for t in mid["ids"]]
        c(mid["ghosts"] == 0, f"po puštění nezůstal duch ({mid['ghosts']})")
        c(mid["gaps"] == 0, f"po puštění nezůstal slot ({mid['gaps']})")
        c(mid["dragging"] == 0, f"po puštění nezůstalo označení ({mid['dragging']})")
        c(dom == ["B", "C", "A", "D"], f"DOM po přesunu A dolů: {dom}")
        c(db == ["bm-b", "bm-c", "bm-a", "bm-d"], f"IndexedDB po přesunu A dolů: {db}")

        # --- 2) táhnout D nahoru na začátek ---------------------------------
        rows2 = await h.ev(ROWS)
        d2, a2 = rows2[3], rows2[0]
        await drag(h, d2["hx"], d2["hy"], a2["top"] + 4)
        mid = await h.ev(STATE)
        db = await h.ev(DB_ORDER, await_promise=True)
        dom = [label_of(t) for t in mid["ids"]]
        c(dom == ["D", "B", "C", "A"], f"DOM po přesunu D nahoru: {dom}")
        c(db == ["bm-d", "bm-b", "bm-c", "bm-a"], f"IndexedDB po přesunu D nahoru: {db}")
        c(mid["ghosts"] == 0 and mid["gaps"] == 0 and mid["dragging"] == 0,
             f"po druhém přesunu čisto: {mid}")

        # --- 3) tap na táhlo = žádná změna ----------------------------------
        rows3 = await h.ev(ROWS)
        await h.finger_tap(rows3[1]["hx"], rows3[1]["hy"])
        st3 = await h.ev(STATE)
        db3 = await h.ev(DB_ORDER, await_promise=True)
        c([label_of(t) for t in st3["ids"]] == ["D", "B", "C", "A"], f"tap nic nepřesunul: {st3['ids']}")
        c(db3 == ["bm-d", "bm-b", "bm-c", "bm-a"], f"tap nezapsal: {db3}")
        c(st3["ghosts"] == 0 and st3["gaps"] == 0 and st3["dragging"] == 0, f"tap nechal čisto: {st3}")

        # --- 4) slot musí ukazovat cílové místo UPROSTŘED tažení ------------
        rows4 = await h.ev(ROWS)
        top = rows4[0]
        y_end = rows4[3]["bottom"] - 4      # až za střed posledního řádku
        await h.touch("touchStart", [(top["hx"], top["hy"], 12)])
        await asyncio.sleep(0.05)
        for i in range(1, 13):
            await h.touch("touchMove", [(top["hx"], top["hy"] + (y_end - top["hy"]) * i / 12, 12)])
            await asyncio.sleep(0.03)
        await asyncio.sleep(0.2)
        live = await h.ev(STATE)
        gap_geo = await h.ev(
            "(() => { const g = document.querySelector('.jp-gap'); if (!g) return null;"
            " const r = g.getBoundingClientRect(); const gs = document.querySelector('.bm-ghost');"
            " const gr = gs ? gs.getBoundingClientRect() : null;"
            " return {gapTop: r.top, gapH: r.height,"
            "  ghostExists: !!gs, ghostTop: gr ? gr.top : null,"
            "  ghostH: gr ? gr.height : null}; })()")
        c(live["ghosts"] == 1, f"během tažení je právě jeden duch ({live['ghosts']})")
        c(live["gaps"] == 1, f"během tažení je právě jeden slot ({live['gaps']})")
        c(not live["dragging"], f"tažený řádek není v seznamu dvakrát ({live})")
        c(gap_geo is not None, "slot existuje")
        if gap_geo:
            c(abs(gap_geo["gapH"] - gap_geo["ghostH"]) < 1.5,
                 f"slot má stejnou výšku jako duch ({gap_geo['gapH']} vs {gap_geo['ghostH']})")
            c(gap_geo["ghostTop"] is not None and gap_geo["ghostTop"] > rows4[0]["top"] + rows4[0]["h"],
                 f"duch je pod prstem, ne na startu ({gap_geo['ghostTop']} vs {rows4[0]['top']})")
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st5 = await h.ev(STATE)
        c(st5["ghosts"] == 0 and st5["gaps"] == 0 and st5["dragging"] == 0, f"po puštění čisto: {st5}")
        dom5 = [label_of(t) for t in st5["ids"]]
        c(dom5 == ["B", "C", "A", "D"], f"DOM po přesunu prvního řádku na konec: {dom5}")

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
