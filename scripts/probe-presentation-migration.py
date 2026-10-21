#!/usr/bin/env python3
"""Migrace vzhledu (rev 2): skladba uložená s rámem se po startu otevře BEZ rámu.

Jan (Oct 2026): „nesmí se žádná naše aktualizace takhle radikálně projevit
automaticky" — noty, které měl dřív v pohodě, se otevíraly oříznuté a zvětšené,
protože příznak `frame` zůstal z vývoje zapnutý (na skladbě i v uložených
zobrazeních). Migrace ho jednou vypne a označí se revizí; druhý start už do dat
nesahá (uživatel si mezitím mohl rám zapnout sám).
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

SONGS_JS = """(() => new Promise(r => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const db = q.result;
    const t = db.transaction('songs', 'readonly');
    const g = t.objectStore('songs').getAll();
    g.onsuccess = () => r(JSON.stringify(g.result.map(s =>
      ({id: s.id, frame: s.frame == null ? null : s.frame}))));
    g.onerror = () => r('ERR');
  };
  q.onerror = () => r('OPEN_ERR');
}))()"""

SET_FRAME_JS = """(() => new Promise(r => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const db = q.result;
    const t = db.transaction('songs', 'readwrite');
    const st = t.objectStore('songs');
    const all = st.getAll();
    all.onsuccess = () => {
      const rows = all.result;
      for (const s of rows) { s.frame = 1; st.put(s); }
      t.oncomplete = () => r('ok:' + rows.length);
    };
  };
}))()"""

# Uložená zobrazení (skladba + stránka) s příznakem rámu, jak je zapisoval vývoj.
SEED_VIEWS_JS = """(() => new Promise(r => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const db = q.result;
    const t = db.transaction('songs', 'readonly');
    const g = t.objectStore('songs').getAll();
    g.onsuccess = () => {
      const s = g.result[0];
      const w = db.transaction('meta', 'readwrite');
      const st = w.objectStore('meta');
      st.put({ songId: s.id, zoom: 1, panX: 0, panY: 0, rot: 0, frame: 1 }, 'view:' + s.id);
      st.put({ songId: s.id, page: 0, zoom: 1, panX: 0, panY: 0, rot: 0, frame: 1 },
             'pview:' + s.id + ':0');
      w.oncomplete = () => r('views-ok');
    };
  };
}))()"""

VIEWS_JS = """(() => new Promise(r => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const db = q.result;
    const t = db.transaction('songs', 'readonly');
    const g = t.objectStore('songs').getAll();
    g.onsuccess = () => {
      const s = g.result[0];
      const rd = db.transaction('meta', 'readonly').objectStore('meta');
      const a = rd.get('view:' + s.id);
      const b2 = rd.get('pview:' + s.id + ':0');
      let out = {};
      a.onsuccess = () => { out.view = a.result ? a.result.frame : null; };
      b2.onsuccess = () => { out.page = b2.result ? b2.result.frame : null; };
      setTimeout(() => r(JSON.stringify(out)), 150);
    };
  };
}))()"""


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.ev("localStorage.removeItem('noty.presentationRev')")
        await h.open_song(m.make_pdf(3))

        songs = json.loads(await h.ev(SONGS_JS, await_promise=True))
        ok("skladba vznikla", len(songs) >= 1, str(songs))
        print("frame po importu:", songs[0]["frame"])

        # simulace stavu po vývoji: rám zapnutý na skladbě i v uložených zobrazeních
        print("set:", await h.ev(SET_FRAME_JS, await_promise=True))
        print("views:", await h.ev(SEED_VIEWS_JS, await_promise=True))
        await h.ev("localStorage.removeItem('noty.presentationRev')")

        await h.open()                      # restart appky = start migrace
        await asyncio.sleep(2.5)
        rev = await h.ev("localStorage.getItem('noty.presentationRev')")
        songs2 = json.loads(await h.ev(SONGS_JS, await_promise=True))
        views2 = json.loads(await h.ev(VIEWS_JS, await_promise=True))
        ok("migrace se označila jako hotová", rev == "2", str(rev))
        ok("rám na skladbě je vypnutý", songs2[0]["frame"] == 0, str(songs2))
        ok("rám v uloženém zobrazení skladby je vypnutý", views2.get("view") == 0, str(views2))
        ok("rám v uloženém zobrazení stránky je vypnutý", views2.get("page") == 0, str(views2))

        # a podruhé už nic nemění (idempotence — uživatel si mohl rám zapnout sám)
        print("set znovu:", await h.ev(SET_FRAME_JS, await_promise=True))
        await h.open()
        await asyncio.sleep(2.0)
        songs3 = json.loads(await h.ev(SONGS_JS, await_promise=True))
        ok("druhý start už do dat nezasahuje", songs3[0]["frame"] == 1, str(songs3))
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
