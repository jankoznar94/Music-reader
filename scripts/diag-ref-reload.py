#!/usr/bin/env python3
"""Diag: co je v knihovně po reloadu s jinou šířkou."""
import asyncio
import importlib.util
import json
import os

CDP = "http://127.0.0.1:9223"
spec = importlib.util.spec_from_file_location("h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = CDP
Harness = m.Harness

INFO = """(() => {
  const songs = [...document.querySelectorAll('li.song')];
  return JSON.stringify({
    groups: document.querySelectorAll('.author-group').length,
    songs: songs.length,
    names: songs.map(s => (s.querySelector('.song-name') || {}).textContent),
    bodyStart: document.body.innerText.slice(0, 300),
  });
})()"""


async def main():
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(m.make_pdf(4))
        await h.annot_toggle()
        await asyncio.sleep(0.5)
        f = await h.free_point()
        x, y = f["x"], f["y"]
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')].find(x => (x.title||'').startsWith('Zvýraznění')); if (b) b.click(); })()")
        await h.pen_tap(x - 70, y + 14)
        await h.pen_tap(x - 70, y - 14)
        await h.pen_tap(x + 70, y)
        await asyncio.sleep(1.0)
        print("annot:", await h.ev("JSON.stringify(window.__navdbg().annotCount)"))
        print("db ref:", await h.ev(
            "new Promise(r => { const q = indexedDB.open('noty-app'); q.onsuccess = () => {"
            " const db = q.result; const t = db.transaction('annotations','readonly');"
            " const g = t.objectStore('annotations').getAll(); g.onsuccess = () => {"
            " r(JSON.stringify(g.result.map(x => ({song: x.songId, ref: x.ref, n: x.items.length})))); }; }; })"
        ))
        await h.set_tablet(560, 1280, 2)
        await asyncio.sleep(1.2)
        await h.open()
        await asyncio.sleep(2.0)
        print("after reload:", await h.ev(INFO))
        await h.ev(h.expand_authors_js())
        await asyncio.sleep(0.5)
        await h.ev("(() => { const s = document.querySelector('.song-name'); if (s) s.click(); })()")
        await asyncio.sleep(3.0)
        print("viewer:", await h.ev("!!document.querySelector('.tb-page')"), "loading:", await h.ev("!!document.querySelector('.viewer-loading')"))
        print("ref:", await h.ev("JSON.stringify(window.__navdbg && window.__navdbg())") if await h.ev("!!window.__navdbg") else "none")
        print("db ref2:", await h.ev(
            "new Promise(r => { const q = indexedDB.open('noty-app'); q.onsuccess = () => {"
            " const db = q.result; const t = db.transaction('annotations','readonly');"
            " const g = t.objectStore('annotations').getAll(); g.onsuccess = () => {"
            " r(JSON.stringify(g.result.map(x => ({song: x.songId, ref: x.ref, n: x.items.length, d: (x.items[0]||{}).poly ? (x.items[0].poly[0].x + ',' + x.items[0].poly[0].y) : null})))); }; }; })"
        ))


asyncio.run(main())
