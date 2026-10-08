#!/usr/bin/env python3
"""Živý web: rámeček + barva textu + krok velikosti (verze, kterou dostal Jan).

Ověřuje TOTÉŽ co dev sonda, ale proti https://harlequin-music-reader.web.app.
Nejdřív odregistruje starý SW a smaže CacheStorage/IndexedDB, jinak by prohlížeč
servíroval starou verzi a sonda by hlásila falešný FAIL.
"""
import asyncio, importlib.util, json, os

LIVE = os.environ.get("NOTY_TARGET", "https://harlequin-music-reader.web.app/")

def _load():
    for c in (os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),):
        if os.path.exists(c):
            s = importlib.util.spec_from_file_location("h", c)
            m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
    raise SystemExit("chybi harness")

_m = _load()
_m.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")
Harness, Check = _m.Harness, _m.Check

async def point_of(h, sel):
    return await h.ev("""(() => {
      const el = document.querySelector(%s); if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(%s) === el))) return [x+0.5, y+0.5];
        }
      return null; })()""" % (json.dumps(sel), json.dumps(sel)))

async def tap(h, sel):
    pt = await point_of(h, sel)
    if not pt: return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)]); await asyncio.sleep(0.06)
    await h.touch("touchEnd", []); await asyncio.sleep(0.45)
    return True

async def tap_idx(h, sel, idx):
    pt = await h.ev("""(() => { const el = document.querySelectorAll(%s)[%d]; if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2)
          if (document.elementFromPoint(x,y) === el) return [x+0.5, y+0.5];
      return null; })()""" % (json.dumps(sel), idx))
    if not pt: return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)]); await asyncio.sleep(0.06)
    await h.touch("touchEnd", []); await asyncio.sleep(0.45)
    return True

async def state(h):
    raw = await h.ev("""(() => { const q = s => document.querySelector(s);
      const cols = [...document.querySelectorAll('.ti-color')];
      return JSON.stringify({ open: !!q('.text-input-overlay'), colors: cols.length,
        sel: cols.findIndex(c => c.classList.contains('on')),
        toggle: q('.ti-toggle') ? q('.ti-toggle').textContent.trim() : null,
        val: q('.ti-size-val') ? Number(q('.ti-size-val').textContent.trim()) : null }); })()""")
    return json.loads(raw) if raw else {}

async def saved(h):
    raw = await h.ev("""(async () => { const dbs = await indexedDB.databases();
      const n = (dbs.map(d=>d.name)||[]).find(x=>/noty|music|reader/i.test(x)); if (!n) return '[]';
      const db = await new Promise((res,rej)=>{const r=indexedDB.open(n);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(String(r.error));});
      const all = s => new Promise(res => { if (!db.objectStoreNames.contains(s)) return res(null);
        const r = db.transaction(s,'readonly').objectStore(s).getAll(); r.onsuccess=()=>res(r.result); r.onerror=()=>res(null); });
      const out = [];
      for (const s of [...db.objectStoreNames]) { const rows = await all(s); if (!Array.isArray(rows)) continue;
        for (const row of rows) for (const i of ((row&&row.items)||[]))
          if (i && i.tool === 'text') out.push({text:i.text,size:i.size,color:i.color,border:i.border===true}); }
      db.close(); return JSON.stringify(out); })()""", await_promise=True)
    return json.loads(raw) if raw else []

async def geo(h, text):
    raw = await h.ev("""(() => { const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      for (const g of svg.querySelectorAll('g')) { const t = g.querySelector(':scope > text');
        if (!t || (t.textContent||'') !== %s) continue;
        const r = g.querySelector(':scope > rect.text-border');
        if (!r) return JSON.stringify({hasRect:false, fill:t.getAttribute('fill')});
        const rb = r.getBoundingClientRect();
        return JSON.stringify({hasRect:true, w:rb.width, h:rb.height, stroke:r.getAttribute('stroke'),
          fill:t.getAttribute('fill')}); }
      return null; })()""" % json.dumps(text))
    return json.loads(raw) if raw else None

async def free_xy(h):
    p = await h.ev("""(() => { const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')].map(e=>e.getBoundingClientRect());
      const near = (x,y) => boxes.some(r => r.width>0 && x>r.left-26 && x<r.right+26 && y>r.top-26 && y<r.bottom+26);
      for (const fy of [0.30,0.38,0.46,0.54]) for (const fx of [0.62,0.54,0.46,0.38,0.70,0.30]) {
        const x = v.left + v.width*fx, y = v.top + v.height*fy;
        if (document.elementFromPoint(x,y) === svg && !near(x,y)) return {x,y}; }
      return null; })()""")
    return (p["x"], p["y"]) if p else None

async def use_text(h):
    await h.ev("(() => { const b=[...document.querySelectorAll('.ap-tool')].find(x=>(x.title||'').startsWith('Text')); if(b) b.click(); })()")
    await asyncio.sleep(0.4)

async def main():
    ok = Check()
    async with Harness(LIVE) as h:
        await h.cdp("Page.navigate", {"url": LIVE})
        await h.wait_for("document.readyState === 'complete'", label="live load")
        # odregistrovat starý SW + smazat cache, ať se měří opravdu nasazená verze
        await h.ev("""(async () => { if (navigator.serviceWorker) {
          const rs = await navigator.serviceWorker.getRegistrations();
          for (const r of rs) await r.unregister(); }
          if (window.caches) { const ks = await caches.keys(); for (const k of ks) await caches.delete(k); }
          return true; })()""", await_promise=True)
        await asyncio.sleep(0.5)
        await h.open()                      # čistý load bez SW
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await use_text(h)

        xy = await free_xy(h)
        await h.pen_tap(xy[0], xy[1]); await asyncio.sleep(0.9)
        st = await state(h)
        ok("L1) živý web: dialog má paletu barev i přepínač rámečku",
           st.get("open") and st.get("colors") == 9 and st.get("toggle") == "Vypnutý",
           json.dumps(st, ensure_ascii=False))
        seq = []
        for _ in range(5):
            await tap(h, ".ti-size-btn:last-of-type"); seq.append((await state(h)).get("val"))
        d = [seq[i+1]-seq[i] for i in range(len(seq)-1)]
        ok("L2) živý web: krok velikosti je VŽDY 3", all(x == 3 for x in d), f"{seq} kroky={d}")
        await tap_idx(h, ".ti-color", 1)
        await tap(h, ".ti-toggle")
        st2 = await state(h)
        ok("L3) živý web: barva i rámeček se v dialogu nastaví",
           st2.get("sel") == 1 and st2.get("toggle") == "Zapnutý", json.dumps(st2, ensure_ascii=False))
        await h.set_value(".ti-input", "live ram")
        await tap(h, ".jp-btn.primary"); await asyncio.sleep(1.2)
        mine = [t for t in await saved(h) if t.get("text") == "live ram"]
        ok("L4) živý web: uložený text má barvu i rámeček",
           bool(mine) and mine[0].get("border") is True and mine[0].get("color") == "#c0392b",
           f"{mine}")
        g = await geo(h, "live ram")
        ok("L5) živý web: rámeček je ČTVEREC stejné barvy jako text",
           g and g.get("hasRect") and abs(g["w"]-g["h"]) <= 1.5 and g.get("stroke") == g.get("fill") == "#c0392b",
           json.dumps(g, ensure_ascii=False))
    return ok.report()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
