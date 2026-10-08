#!/usr/bin/env python3
"""Živý web: rámeček textu VYCENTROVANÝ + volitelná šířka a styl (Jan, Oct 2026).

Ověřuje totéž co dev sonda, ale proti https://harlequin-music-reader.web.app —
tedy verzi, kterou uživatel opravdu dostane. Nejdřív odregistruje starý service
worker a smaže CacheStorage/IndexedDB, jinak prohlížeč servíruje starou verzi
a sonda hlásí falešný FAIL.

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/probe-live-text-border-center.py
"""
import asyncio
import importlib.util
import json
import os

LIVE = os.environ.get("NOTY_TARGET", "https://harlequin-music-reader.web.app/")


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("h", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")
Harness, Check = _m.Harness, _m.Check

JS_INK = """
const ink = (text, size) => {
  const c = document.createElement('canvas').getContext('2d');
  c.font = size + 'px system-ui, sans-serif';
  const m = c.measureText(text || 'H');
  return { asc: m.actualBoundingBoxAscent, desc: m.actualBoundingBoxDescent };
};
"""


async def tap_el(h, sel):
    pt = await h.ev("""(() => {
      const el = document.querySelector(%s); if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(%s) === el))) return [x+0.5, y+0.5];
        }
      return null; })()""" % (json.dumps(sel), json.dumps(sel)))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(0.06)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.45)
    return True


async def tap_text(h, sel, label):
    pt = await h.ev("""(() => {
      const el = [...document.querySelectorAll(%s)].find(b => (b.textContent||'').trim() === %s);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2)
          if (document.elementFromPoint(x, y) === el) return [x+0.5, y+0.5];
      return null; })()""" % (json.dumps(sel), json.dumps(label)))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(0.06)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.45)
    return True


async def geometry(h, text):
    raw = await h.ev("(() => {" + JS_INK + """return (() => {
      const want = %s;
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const layerTop = svg.getBoundingClientRect().top;
      for (const g of svg.querySelectorAll('g')) {
        const t = g.querySelector(':scope > text');
        if (!t || (t.textContent || '') !== want) continue;
        const rects = [...g.querySelectorAll(':scope > rect.text-border')];
        if (!rects.length) return JSON.stringify({ hasRect: false });
        const r = rects.reduce((a, b) => {
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          return (rb.width * rb.height > ra.width * ra.height) ? b : a; });
        const tb = t.getBoundingClientRect(), rb = r.getBoundingClientRect();
        const size = Number(t.getAttribute('font-size')) || 20;
        const k = ink(want, size);
        const baseline = layerTop + (Number(t.getAttribute('y')) || 0);
        const inkTop = baseline - k.asc, inkBot = baseline + k.desc;
        return JSON.stringify({
          hasRect: true, rects: rects.length,
          dx: (tb.left + tb.width / 2) - (rb.left + rb.width / 2),
          dy: ((inkTop + inkBot) / 2) - (rb.top + rb.height / 2),
          gapL: tb.left - rb.left, gapR: (rb.left + rb.width) - (tb.left + tb.width),
          gapT: inkTop - rb.top, gapB: (rb.top + rb.height) - inkBot,
          rw: rb.width, rh: rb.height, dash: rects[0].getAttribute('stroke-dasharray'),
          stroke: rects[0].getAttribute('stroke'),
        });
      }
      return null; })()""" % json.dumps(text) + "})()")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


async def saved_texts(h):
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const n = (dbs.map(d=>d.name)||[]).find(x=>/noty|music|reader/i.test(x)); if (!n) return '[]';
      const db = await new Promise((res,rej)=>{const r=indexedDB.open(n);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(String(r.error));});
      const all = s => new Promise(res => { if (!db.objectStoreNames.contains(s)) return res(null);
        const r = db.transaction(s,'readonly').objectStore(s).getAll(); r.onsuccess=()=>res(r.result); r.onerror=()=>res(null); });
      const out = [];
      for (const s of [...db.objectStoreNames]) { const rows = await all(s); if (!Array.isArray(rows)) continue;
        for (const row of rows) for (const i of ((row&&row.items)||[]))
          if (i && i.tool === 'text') out.push({text:i.text,size:i.size,borderWidth:i.borderWidth,
            borderStyle:i.borderStyle,color:i.color}); }
      db.close(); return JSON.stringify(out); })()""", await_promise=True)
    return json.loads(raw) if raw else []


async def free_xy(h):
    p = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')].map(e=>e.getBoundingClientRect());
      const near = (x,y) => boxes.some(r => r.width>0 && x>r.left-34 && x<r.right+34 && y>r.top-34 && y<r.bottom+34);
      for (const fy of [0.30,0.38,0.46,0.54,0.62]) for (const fx of [0.60,0.52,0.44,0.36,0.68,0.28]) {
        const x = v.left + v.width*fx, y = v.top + v.height*fy;
        if (document.elementFromPoint(x,y) === svg && !near(x,y)) return {x,y}; }
      return null; })()""")
    return (p["x"], p["y"]) if p else None


async def main():
    ok = Check()
    async with Harness(LIVE) as h:
        await h.cdp("Page.navigate", {"url": LIVE})
        await h.wait_for("document.readyState === 'complete'", label="live load")
        # Odregistrovat starý SW + smazat cache: jinak by se měřila STARÁ verze
        # (přesně to je past, na kterou u PWA narazíš).
        await h.ev("""(async () => { if (navigator.serviceWorker) {
          const rs = await navigator.serviceWorker.getRegistrations();
          for (const r of rs) await r.unregister(); }
          if (window.caches) { const ks = await caches.keys(); for (const k of ks) await caches.delete(k); }
          return true; })()""", await_promise=True)
        await asyncio.sleep(0.5)
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await h.ev("(() => { const b=[...document.querySelectorAll('.ap-tool')].find(x=>(x.title||'').startsWith('Text')); if(b) b.click(); })()")
        await asyncio.sleep(0.4)

        # --- vycentrování na živém webu, dva různé texty -----------------------
        for txt, size in [("live ram", 20), ("live dlouhy text na noty", 32)]:
            xy = await free_xy(h)
            await h.pen_tap(xy[0], xy[1]); await asyncio.sleep(0.9)
            await h.set_value(".ti-input", txt)
            for _ in range(40):
                cur = await h.ev("Number((document.querySelector('.ti-size-val')||{}).textContent)")
                if cur == size:
                    break
                await tap_el(h, ".ti-size-btn:last-of-type" if cur < size else ".ti-size-btn")
            for _ in range(3):
                if await h.ev("!!document.querySelector('.ti-toggle.on')") is True:
                    break
                await tap_el(h, ".ti-toggle")
            await asyncio.sleep(0.3)
            await tap_text(h, ".ti-chip", "8")
               
            await tap_el(h, ".jp-btn.primary")
            await asyncio.sleep(1.3)
            g = await geometry(h, txt)
            ok(f"L1) živý web: text „{txt}“ (vel. {size}) je VYCENTROVANÝ (≤ 1,5 px)",
               g and g.get("hasRect") and abs(g["dx"]) <= 1.5 and abs(g["dy"]) <= 1.5,
               json.dumps(g, ensure_ascii=False))
            ok(f"L2) živý web: šířka rámu 8 se projevila a rám je ČTVEREC",
               g and min(g["gapL"], g["gapR"], g["gapT"], g["gapB"]) >= 7
               and abs(g["rw"] - g["rh"]) <= 1.5,
               f"mezery={[round(g[k],1) for k in ('gapL','gapR','gapT','gapB')]} rám={g['rw']:.1f}x{g['rh']:.1f}")

        # --- styl rámu na živém webu ------------------------------------------
        xy = await free_xy(h)
        await h.pen_tap(xy[0], xy[1]); await asyncio.sleep(0.9)
        await h.set_value(".ti-input", "live teckovany")
        if await h.ev("!!document.querySelector('.ti-toggle.on')") is not True:
            await tap_el(h, ".ti-toggle")
        await asyncio.sleep(0.3)
        await tap_text(h, ".ti-chip", "Tečky")
        await tap_el(h, ".jp-btn.primary"); await asyncio.sleep(1.3)
        g3 = await geometry(h, "live teckovany")
        ok("L3) živý web: tečkovaný rám má správný vzor čáry",
           g3 and g3.get("dash") == "1.5 4", json.dumps(g3, ensure_ascii=False))
        ok("L4) živý web: tečkovaný rám je vycentrovaný a čtvercový",
           g3 and abs(g3["dx"]) <= 1.5 and abs(g3["dy"]) <= 1.5 and abs(g3["rw"] - g3["rh"]) <= 1.5,
           f"dx={g3['dx']:.2f} dy={g3['dy']:.2f} {g3['rw']:.1f}x{g3['rh']:.1f}")
        saved = [t for t in await saved_texts(h) if t.get("text") == "live teckovany"]
        # Šířka se u tohoto textu needitovala záměrně — zdědila se z předchozího
        # vložení (8), což je správné chování (volba se pamatuje).
        ok("L5) živý web: volby šířky a stylu se uložily do anotace",
           bool(saved) and saved[0].get("borderWidth") == 8 and saved[0].get("borderStyle") == "dotted",
           f"ulozeno={saved}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
