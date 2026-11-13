#!/usr/bin/env python3
"""Screenshot panelu Značky (pro Jana) — CDP, tablet 820×1180 @2x.

Značky se do stránky vloží přímo (dev `__barDev.annotations`) — jde jen o to,
jak panel vypadá; funkčnost ověřuje `probe-marks-jump.py`.
Záložky se pro tuto skladbu vynulují (jinak se panel zužuje na jednu část).
"""
import asyncio
import base64
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
APP = os.environ.get("APP_URL") or "http://localhost:5173/"
OUT = os.environ.get("OUT", "/tmp/marks-panel.png")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    m.CDP_HTTP = CDP  # type: ignore[attr-defined]
    return m


m = _load()

CLEAR_BM = """(async () => {
  const songId = location.pathname.split('/').pop();
  const db = await new Promise((res, rej) => {
    const r = indexedDB.open('noty-app');
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  });
  await new Promise((res, rej) => {
    const tx = db.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items: [], manualOrder: false });
    tx.oncomplete = () => res(1); tx.onerror = () => rej(tx.error);
  });
  db.close();
  return songId;
})()"""

SEED = """(() => {
  const d = window.__barDev;
  const mk = (page, text, y) => ({
    id: 'shot-' + text, page, tool: 'text', mk: true, hidden: true,
    text, size: 12, color: '#0b6bff', opacity: 1, border: false,
    x: 300, y,
  });
  // jen samotné značky (žádné zbytky z předchozích běhů)
  d.annotations.value.items = [
    mk(0, 'A', 300), mk(2, 'C', 420), mk(4, '12', 380), mk(5, '7', 500)];
  d.currentPage.value = 0;
  return d.annotations.value.items.length;
})()"""


async def main():
    async with m.Harness(url=APP) as h:
        await h.open()
        await h.open_song(m.make_pdf(8), reset=False)
        await asyncio.sleep(1.0)
        print("song:", await h.ev(CLEAR_BM, await_promise=True))
        await h.cdp("Page.reload")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "znovu prohlížeč")
        await asyncio.sleep(1.5)
        print("items:", await h.ev(SEED))
        await asyncio.sleep(0.6)
        if await h.ev("(() => !!document.querySelector('.marks-panel'))()") is False:
            await h.ev("document.querySelector('.tb-mark').click()")
        await asyncio.sleep(0.8)
        print("hint:", await h.ev("document.querySelector('.marks-panel .jp-hint').textContent.trim()"))
        print("panel:", await h.ev(
            "(() => [...document.querySelectorAll('.marks-panel .marks-item .marks-text')]"
            ".map(e => e.textContent.trim()).join(', '))()"))
        await h.cdp("Emulation.setDeviceMetricsOverride",
                    {"width": 820, "height": 1180, "deviceScaleFactor": 2, "mobile": False})
        await asyncio.sleep(0.8)
        raw = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(raw["data"]))
        print("saved", OUT)


asyncio.run(main())
