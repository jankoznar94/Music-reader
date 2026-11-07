#!/usr/bin/env python3
"""Screenshot UPROSTŘED tažení záložky — kontrola, že duch i slot vypadají správně."""
import asyncio
import base64
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, make_pdf = m.Harness, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")
OUT = os.environ.get("OUT", "/tmp/noty-drag-mid.png")

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
    { id: 'bm-a', page: 0, label: 'Intro' },
    { id: 'bm-b', page: 2, label: 'Sloka 1' },
    { id: 'bm-c', page: 4, label: 'Refrén' },
    { id: 'bm-d', page: 6, label: 'Coda' },
  ];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: true });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""

ROWS = r"""
(() => [...document.querySelectorAll('.jp-list .jp-item')].map(el => {
  const r = el.getBoundingClientRect();
  const h = el.querySelector('.jp-drag').getBoundingClientRect();
  return { top: r.top, bottom: r.bottom, h: r.height,
           hx: h.left + h.width / 2, hy: h.top + h.height / 2 };
}))()
"""


async def main():
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.open_song(pdf=make_pdf(8), pages=8)
        song = await h.ev(GET_SONG, await_promise=True)
        await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True)
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.0)
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Přidat záložku')); b && b.click(); })()")
        await h.wait_for("document.querySelectorAll('.jp-list .jp-item').length === 4", 10, "panel")
        await asyncio.sleep(0.3)

        rows = await h.ev(ROWS)
        y_end = rows[2]["top"] + 10           # slot mezi 2. a 3. řádkem
        await h.touch("touchStart", [(rows[0]["hx"], rows[0]["hy"], 12)])
        await asyncio.sleep(0.05)
        for i in range(1, 11):
            await h.touch("touchMove", [(rows[0]["hx"], rows[0]["hy"] +
                                         (y_end - rows[0]["hy"]) * i / 10, 12)])
            await asyncio.sleep(0.03)
        await asyncio.sleep(0.3)
        shot = await h.cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        with open(OUT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("saved", OUT)
        await h.touch("touchEnd", [])


if __name__ == "__main__":
    asyncio.run(main())
