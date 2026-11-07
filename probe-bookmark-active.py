#!/usr/bin/env python3
"""Dolní lišta záložek: aktivní záložka svítí po CELOU část skladby.

Záložky: Intro str. 3 (idx 2), Sloka str. 5 (idx 4), Refrén str. 7 (idx 6)
z 8stránkového PDF. Očekávané zvýraznění podle aktuální stránky (1-based):

  str. 1–2  → nic (před první záložkou)
  str. 3–4  → Intro
  str. 5–6  → Sloka
  str. 7–8  → Refrén

Navíc se kontroluje, že zvýraznění je OPRAVDU vidět (zlatý podklad + tmavý
text), ne jen třída `.on`.
"""
import asyncio
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check, make_pdf = m.Harness, m.Check, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")
SHOT = os.environ.get("OUT", "/tmp/noty-bookmark-active.png")

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
    { id: 'bm-1', page: 2, label: 'Intro' },
    { id: 'bm-2', page: 4, label: 'Sloka' },
    { id: 'bm-3', page: 6, label: 'Refrén' },
  ];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: false });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""

STRIP = r"""
(() => {
  const btns = [...document.querySelectorAll('.bookmark-strip .bookmark-btn')];
  if (!btns.length) return { count: 0, on: [], style: null };
  const on = btns.filter(b => b.classList.contains('on'));
  const st = on.length ? getComputedStyle(on[0]) : null;
  const num = on.length ? getComputedStyle(on[0].querySelector('.bk-num')) : null;
  return {
    count: btns.length,
    on: on.map(b => (b.querySelector('.bk-label') || b).textContent.trim()),
    bg: st ? st.backgroundColor : null,
    fg: st ? st.color : null,
    numBg: num ? num.backgroundColor : null,
    page: (document.querySelector('.tb-page') || {}).textContent || '',
  };
})()
"""


class P:
    def __init__(self):
        self.inner = Check()
        self.n = 0

    def __call__(self, ok, detail=""):
        self.n += 1
        self.inner(f"check {self.n}: {detail[:56]}", ok, detail="")

    def report(self):
        return self.inner.report()


async def show_bars(h):
    """Lišta záložek je schovaná spolu s horní lištou — klepnutím doprostřed
    not ji ukážeme (stejné gesto jako v aplikaci)."""
    for _ in range(3):
        cls = await h.ev("(document.querySelector('.top-bar')||{}).className || ''")
        if "hidden" not in cls:
            return True
        g = await h.geo()
        await h.finger_tap(g["left"] + g["w"] / 2, g["top"] + g["h"] / 2)
        await asyncio.sleep(0.8)
    return False


async def main():
    c = P()
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.open_song(pdf=make_pdf(8), pages=8)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačtený song"
        assert await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True), "seed selhal"
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        c(await show_bars(h), "lišty se podařilo zobrazit")
        await h.wait_for("document.querySelectorAll('.bookmark-strip .bookmark-btn').length === 3",
                         15, "lišta záložek")
        await asyncio.sleep(0.6)

        expect = {1: None, 2: None, 3: "Intro", 4: "Intro", 5: "Sloka",
                  6: "Sloka", 7: "Refrén", 8: "Refrén"}
        seen = {}
        for page, want in expect.items():
            await h.goto(page)
            await asyncio.sleep(0.4)
            st = await h.ev(STRIP)
            got = st["on"][0] if len(st["on"]) == 1 else (st["on"] or None)
            ok = (want is None and not st["on"]) or (want is not None and st["on"] == [want])
            c(ok, f"str. {page}: očekáváno {want!r}, zvýrazněno {st['on']!r} (lišta: {st['page'].strip()!r})")
            c(len(st["on"]) <= 1, f"str. {page}: svítí nejvýš jedna záložka ({len(st['on'])})")
            seen[page] = st

        # zvýraznění musí být vidět, ne jen třída
        a = seen[4]
        c(a["bg"] == "rgb(201, 168, 124)", f"aktivní má zlatý podklad ({a['bg']})")
        c(a["fg"] == "rgb(23, 19, 15)", f"aktivní má tmavý text ({a['fg']})")
        c(a["numBg"] == "rgb(23, 19, 15)", f"odznak s číslem je obrácený ({a['numBg']})")
        idle = await h.ev(
            "(() => { const b = document.querySelector('.bookmark-strip .bookmark-btn:not(.on)');"
            " return b ? getComputedStyle(b).backgroundColor : null; })()")
        c(idle != a["bg"], f"neaktivní záložka vypadá jinak ({idle})")

        # screenshot pro vizuální kontrolu (str. 5 = Sloka)
        import base64
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(SHOT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("screenshot:", SHOT)

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
