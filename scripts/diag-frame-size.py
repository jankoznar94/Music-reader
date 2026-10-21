#!/usr/bin/env python3
"""O kolik se stránka zvětší, když je zapnutý rám — důkaz pro Jana."""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
spec = importlib.util.spec_from_file_location("h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = CDP
Harness = m.Harness

GEOM = """(() => {
  const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
  const a = document.querySelector('.page-area').getBoundingClientRect();
  const v = document.querySelector('.viewer').getBoundingClientRect();
  return JSON.stringify({canvas: {w: Math.round(c.width), h: Math.round(c.height)},
    pageArea: {w: Math.round(a.width), h: Math.round(a.height)},
    viewer: {w: Math.round(v.width), h: Math.round(v.height)},
    gapL: Math.round(c.left - a.left), gapR: Math.round(a.right - c.right),
    gapT: Math.round(c.top - a.top), gapB: Math.round(a.bottom - c.bottom)});
})()"""


async def frame(h, on):
    await h.ev("(() => new Promise(r => { const q = indexedDB.open('noty-app');"
               " q.onsuccess = () => { const db = q.result; const t = db.transaction('songs','readwrite');"
               " const st = t.objectStore('songs'); const all = st.getAll(); all.onsuccess = () => {"
               " for (const s of all.result) { s.frame = %d; st.put(s); } t.oncomplete = () => r(1); }; }; }))()"
               % (1 if on else 0), await_promise=True)
    await h.open()
    await asyncio.sleep(2.0)
    await h.ev(h.expand_authors_js())
    await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=30, label="library")
    await h.click(".song-name")
    await h.wait_for("!!document.querySelector('canvas.pdf-canvas')", timeout=40, label="canvas")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="page")
    await asyncio.sleep(1.5)


async def main():
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(m.make_pdf(3))
        await frame(h, False)
        g0 = json.loads(await h.ev(GEOM))
        print("BEZ rámu:", g0)
        await frame(h, True)
        g1 = json.loads(await h.ev(GEOM))
        print("S rámem:", g1)
        print("změna výšky: %d px -> %d px (%.0f %%)" % (
            g0["canvas"]["h"], g1["canvas"]["h"],
            100 * (g1["canvas"]["h"] / max(1, g0["canvas"]["h"]) - 1)))
        # úklid pro další sondy
        await frame(h, False)


asyncio.run(main())
