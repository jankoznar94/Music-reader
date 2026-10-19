#!/usr/bin/env python3
"""Sonda: uložené zobrazení stránky s posunem + zapnutý rám.
Rám = „výřez se vejde na displej“ → starý posun se ignoruje, jinak je výřez
posunutý dolů/doprava a spodek je mimo obrazovku."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

INJECT = r"""
(async () => {
  const db = await new Promise((res, rej) => {
    const r = indexedDB.open('noty-app', 5);
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  });
  const ids = await new Promise((res) => {
    const t = db.transaction('songs', 'readonly').objectStore('songs').getAllKeys();
    t.onsuccess = () => res(t.result);
  });
  const songId = ids[0];
  await new Promise((res) => {
    const t = db.transaction('meta', 'readwrite');
    t.objectStore('meta').put({ songId, page: 0, zoom: 1.4, panX: 140, panY: 220,
                                rot: 0, frame: 1 }, 'pview:' + songId + ':0');
    t.oncomplete = () => res();
  });
  db.close();
  return songId;
})()
"""

STATE = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  const r = c.getBoundingClientRect();
  const ctx = c.getContext('2d');
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  let iy1 = -1, ix0 = c.width;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
    const i = (y * c.width + x) * 4;
    if (d[i] < 200 || d[i+1] < 200 || d[i+2] < 200) { if (y > iy1) iy1 = y; if (x < ix0) ix0 = x; }
  }
  const dpr = window.devicePixelRatio || 1;
  return {top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left),
          right: Math.round(r.right), winH: innerHeight, winW: innerWidth,
          inkBottom: iy1 < 0 ? null : (c.height - 1 - iy1) / dpr,
          inkLeft: ix0 === c.width ? null : ix0 / dpr};
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(390, 844, 2)
        await h.open_song(pdf='/tmp/noty-dense.pdf', pages=1)
        await asyncio.sleep(0.5)
        # zapnout rám (aby preference rámu existovala) a uložit song.frame
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));b&&b.click()})()")
        await asyncio.sleep(0.4)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.prefs-panel .prefs-icon')]"
                   ".find(x=>(x.title||'').startsWith('Oříznout'));b&&b.click()})()")
        await asyncio.sleep(2.2)
        # podstrčit uložené zobrazení stránky s posunem a přiblížením
        await h.ev(INJECT, await_promise=True)
        # reload na route prohlížeče → aplikuje se uložené zobrazení stránky
        await h.ev("location.reload()")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="page")
        await asyncio.sleep(2.0)
        s = await h.ev(STATE)
        print('SE STARÝM POSUNEM:', s)
        chk('canvas se celý vejde na výšku', s['top'] >= 0 and s['bottom'] <= s['winH'] + 1,
            f"{s['top']}..{s['bottom']} z {s['winH']}")
        chk('canvas se celý vejde na šířku', s['left'] >= 0 and s['right'] <= s['winW'] + 1,
            f"{s['left']}..{s['right']} z {s['winW']}")
        chk('spodek výřezu není uříznutý', s['inkBottom'] is not None and s['inkBottom'] >= 3,
            str(s['inkBottom']))
        chk('levý okraj výřezu není uříznutý', s['inkLeft'] is not None and s['inkLeft'] >= 3,
            str(s['inkLeft']))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
