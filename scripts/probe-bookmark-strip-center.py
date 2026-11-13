#!/usr/bin/env python3
"""Aktivní záložka v liště je na STŘEDU i poté, co se lišta schová a zase ukáže.

Jan, Nov 2026: „Když je lišta se záložkami schovaná, tak se při listování
stránek nescrolluje jak má. Aktivní záložka by měla být na středu, pokud je to
možné. Když je lišta zobrazená, tak to funguje jak má.“

Sonda:
1. nahrát 24stránkové PDF, otevřít skladbu, nasypat 20 záložek do IndexedDB
   (lišta se musí přetéct, jinak není co centrovat), reload.
2. SE SCHOVANOU lištou listovat přes pravý okraj not (skutečné ťukání, ne
   nastavení currentPage) na stránku daleko za polovinou záložek → lišta se
   ukáže → aktivní záložka musí být na středu (±6 px), nebo na dorazu scrollu.
3. S VIDITELNOU lištou listovat dál → aktivní záložka se plynule docentruje.
4. Schovat/ukázat BEZ listování → scroll pozice lišty se nesmí ztratit.
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

PAGES = 24
# Dvě záložky na každou stránku → lišta výrazně přeteče (24 stránek × 2 = 48
# položek ≈ 1700 px na 766 px široké liště), takže je co centrovat i uprostřed.
BM_ITEMS = [{"id": f"bm-{p}-{k}", "page": p, "label": ""}
            for p in range(PAGES) for k in (1, 2)]

SEED = """(async () => {
  const songId = location.pathname.split('/').pop();
  const items = %s;
  const rec = { songId, items, manualOrder: false };
  await new Promise((res, rej) => {
    const rq = indexedDB.open('noty-app');
    rq.onerror = () => rej(rq.error);
    rq.onsuccess = () => {
      const db = rq.result;
      if (!db.objectStoreNames.contains('bookmarks')) { db.close(); return res('no-store'); }
      const tx = db.transaction('bookmarks', 'readwrite');
      tx.objectStore('bookmarks').put(rec);
      tx.oncomplete = () => { db.close(); res('ok'); };
      tx.onerror = () => { db.close(); rej(tx.error); };
    };
  });
  return songId;
})()""" % json.dumps(BM_ITEMS)

MEASURE = """(() => {
  const strip = document.querySelector('.bookmark-strip');
  if (!strip) return JSON.stringify({ strip: false });
  const btns = [...strip.querySelectorAll('.bookmark-btn')];
  const on = strip.querySelector('.bookmark-btn.on');
  const s = strip.getBoundingClientRect();
  const r = on ? on.getBoundingClientRect() : null;
  return JSON.stringify({
    strip: true,
    n: btns.length,
    scrollLeft: Math.round(strip.scrollLeft),
    clientW: Math.round(strip.clientWidth),
    scrollW: Math.round(strip.scrollWidth),
    max: Math.round(strip.scrollWidth - strip.clientWidth),
    onIdx: on ? btns.indexOf(on) : -1,
    onText: on ? on.textContent.trim() : null,
    // je aktivní záložka vůbec vidět v okně lišty?
    onVisible: r ? (r.left >= s.left - 1 && r.right <= s.right + 1) : false,
    // kladné = aktivní záložka je vpravo od středu lišty
    centerDelta: r ? Math.round((r.left + r.width / 2) - (s.left + strip.clientWidth / 2)) : null,
  });
})()"""

PAGE = "document.querySelector('.tb-page').textContent.trim()"


def mid(x):
    return round(x, 1)


async def page_no(h):
    t = await h.ev(PAGE)
    return t.replace(" ", "")


async def geo(h):
    return json.loads(await h.ev(
        "(() => { const r = document.querySelector('.viewer').getBoundingClientRect();"
        " return JSON.stringify({cx: r.x + r.width/2, cy: r.y + r.height/2,"
        " rx: r.x + r.width * 0.93, lx: r.x + r.width * 0.07}); })()"))


async def measure(h):
    return json.loads(await h.ev(MEASURE))


def centered(m, tol=6):
    if not m.get("strip") or m["onIdx"] < 0:
        return False
    if m["max"] <= 0:
        return True                     # vše se vejde → není co centrovat
    at_start, at_end = m["scrollLeft"] <= 1, m["scrollLeft"] >= m["max"] - 1
    if at_start or at_end:
        # na dorazu se centrovat nedá — aktivní záložka tam ale MUSÍ být vidět
        # (jinak je to právě ta chyba: lišta zůstala na začátku a aktivní je pryč)
        return bool(m["onVisible"])
    return abs(m["centerDelta"]) <= tol


async def main():
    ok = Check()
    pdf = m.make_pdf(PAGES)
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(pdf, reset=True)
        await h.ev(SEED)
        # reload, ať se záložky načtou z IndexedDB jako po restartu appky
        await h.cdp("Page.reload")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer po reloadu")
        await h.wait_for("!document.querySelector('.viewer-loading')", 40, "stránka")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", 15, "lišta záložek")
        await asyncio.sleep(1.2)

        g = await geo(h)
        cx, cy, rx = mid(g["cx"]), mid(g["cy"]), mid(g["rx"])

        mm = await measure(h)
        print("start:", mm)
        ok("lišta přetéká (je co centrovat)", mm["scrollW"] > mm["clientW"] + 20, str(mm))
        # dvě záložky na str. 1 → aktivní je ta druhá z nich (index 1)
        ok("na začátku je aktivní 1. záložka a lišta na dorazu",
           mm["onIdx"] <= 1 and mm["scrollLeft"] <= 2, str(mm))

        # --- 1) se SCHOVANOU lištou listovat daleko za střed ----------------
        await h.finger_tap(cx, cy)          # schovat horní i dolní lištu
        await asyncio.sleep(0.5)
        mm = await measure(h)
        ok("tap na střed schová lištu záložek", mm.get("strip") is False, str(mm))

        before = await page_no(h)
        for _ in range(16):
            await h.finger_tap(rx, cy)
            await asyncio.sleep(0.22)
        await asyncio.sleep(0.6)
        after = await page_no(h)
        print("listování se schovanou lištou:", before, "->", after)

        await h.finger_tap(cx, cy)          # ukázat lištu
        await asyncio.sleep(0.7)
        mm = await measure(h)
        print("po zobrazení lišty:", mm)
        ok("lišta se po listování vrátí", mm.get("strip") is True, str(mm))
        ok("aktivní záložka odpovídá stránce (ne 1.)", mm["onIdx"] > 6, str(mm))
        ok("PO ZOBRAZENÍ je aktivní záložka na STŘEDU", centered(mm), str(mm))

        # --- 2) s VIDITELNOU lištou listovat dál ---------------------------
        for _ in range(3):
            await h.finger_tap(rx, cy)
            await asyncio.sleep(0.75)       # smooth scroll má čas dojet
            mm = await measure(h)
            print("viditelná lišta po dalším listování:", mm)
            ok(f"viditelná lišta drží aktivní záložku na středu (str. {await page_no(h)})",
               centered(mm), str(mm))

        # --- 3) schovat/ukázat BEZ listování → pozice se nesmí ztratit -----
        m1 = await measure(h)
        await h.finger_tap(cx, cy)
        await asyncio.sleep(0.5)
        await h.finger_tap(cx, cy)
        await asyncio.sleep(0.7)
        m2 = await measure(h)
        print("bez listování:", m1, "->", m2)
        ok("hide/show bez listování nemění scroll pozici lišty",
           abs(m2["scrollLeft"] - m1["scrollLeft"]) <= 3, f"{m1} -> {m2}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
