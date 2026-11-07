#!/usr/bin/env python3
"""Listování tapem podle záložek (koncertní pořadí).

9stránkový sešit, záložky NA STRÁNKÁCH 1, 4, 7 (`str.` = 1-based):
  A = str. 1, B = str. 4, C = str. 7
V liště ale jsou v KONCERTNÍM pořadí C, A, B (přetažené).

Očekávané listování tapem dopředu (od str. 7):
  7 → 8 → 9 → (konec C) 1 → 2 → 3 → (konec A) 4 → 5 → 6 → (konec B) ZŮSTANE 6

Zpět od str. 6:
  6 → 5 → 4 → (začátek B) 3 → 2 → 1 → (začátek A) 9 → 8 → 7 → (začátek C) ZŮSTANE 7

Tedy C → A → B místo 1..9.
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
  const items = [
    { id: 'bm-c', page: 6, label: 'C' },   // koncertní pořadí: C, A, B
    { id: 'bm-a', page: 0, label: 'A' },
    { id: 'bm-b', page: 3, label: 'B' },
  ];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: true });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""


SEED_PAGED = r"""
((songId) => new Promise((resolve) => {
  const items = [
    { id: 'bm-p', page: 0, label: 'P' },
    { id: 'bm-q', page: 3, label: 'Q' },
    { id: 'bm-r', page: 6, label: 'R' },
  ];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: false });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
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


async def page_no(h):
    t = await h.ev("(document.querySelector('.tb-page')||{}).textContent || ''")
    return int(t.split('/')[0].strip())


async def tap(h, side):
    g = await h.geo()
    y = g["top"] + g["h"] / 2
    x = g["left"] + (16 if side == "prev" else g["w"] - 16)
    await h.finger_tap(x, y)
    await asyncio.sleep(0.45)
    return await page_no(h)


async def main():
    c = P()
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        # IndexedDB se z předchozího běhu drží otevřená → deleteDatabase() v
        # reset_db() je blokovaný a upload pak „zamrzne“. Vyčistíme přes CDP.
        await h.cdp("Storage.clearDataForOrigin",
                    {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open_song(pdf=make_pdf(9), pages=9)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačtený song"
        assert await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True), "seed selhal"
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.0)

        # kontrola, že seed i lišta sedí
        bm = await h.ev("""new Promise((resolve) => {
          const q = indexedDB.open('noty-app');
          q.onsuccess = () => { const r = q.result.transaction('bookmarks','readonly')
            .objectStore('bookmarks').getAll();
            r.onsuccess = () => resolve(r.result[0].items.map(i => i.label + '@' + (i.page + 1))); };
        })""", await_promise=True)
        c(bm == ['C@7', 'A@1', 'B@4'], f"lišta v koncertním pořadí: {bm}")

        await h.goto(7)
        await asyncio.sleep(0.4)
        c(await page_no(h) == 7, "start na str. 7")

        seq = []
        for _ in range(9):
            seq.append(await tap(h, "next"))
        c(seq == [8, 9, 1, 2, 3, 4, 5, 6, 6],
          f"vpřed C→A→B: {seq} (čekáno [8, 9, 1, 2, 3, 4, 5, 6, 6])")

        seq2 = []
        for _ in range(9):
            seq2.append(await tap(h, "prev"))
        c(seq2 == [5, 4, 3, 2, 1, 9, 8, 7, 7],
          f"zpět B→A→C: {seq2} (čekáno [5, 4, 3, 2, 1, 9, 8, 7, 7])")

        # uvnitř části se listuje po stránkách, ne skokem
        await h.goto(2)
        await asyncio.sleep(0.3)
        c(await tap(h, "next") == 3, "uvnitř části A: 2 → 3 (stránka, ne skok)")

        # --- regrese: záložky v pořadí stránek = listování jako dřív ---------
        assert await h.ev(SEED_PAGED.replace("__SONG__", json.dumps(song)),
                          await_promise=True), "seed 2 selhal"
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand 2")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer 2")
        await asyncio.sleep(1.0)
        await h.goto(1)
        await asyncio.sleep(0.3)
        plain = [await tap(h, "next") for _ in range(9)]
        c(plain == [2, 3, 4, 5, 6, 7, 8, 9, 9],
          f"pořadí stránek = běžné listování: {plain} (čekáno [2,3,4,5,6,7,8,9,9])")

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
