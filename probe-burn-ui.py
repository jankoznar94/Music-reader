#!/usr/bin/env python3
"""E2E: klikne na 'Vypálit PDF' v reálné aplikaci a zjistí, co se stane.

Sleduje: stahování (Browser download), toast hlášku, console.error, promise
rejection a jestli tlačítko zůstalo zakázané (exporting zaseknutý).
"""
import asyncio
import importlib.util
import json
import os
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

LIVE = os.environ.get("APP_URL", "https://harlequin-music-reader.web.app/")
DL = "/tmp/dl-burn"

PATCH = """
window.__log = [];
const oe = console.error;
console.error = (...a) => { window.__log.push('console.error: ' + a.map(x => (x && x.message) ? x.message : String(x)).join(' | ')); oe(...a); };
window.addEventListener('unhandledrejection', (e) => window.__log.push('rejection: ' + ((e.reason && e.reason.message) ? e.reason.message : String(e.reason))));
window.addEventListener('error', (e) => window.__log.push('error: ' + e.message));
"""

FIND_BTN = """
() => {
  const btns = [...document.querySelectorAll('.ap-share-btn')];
  const b = btns.find(x => x.textContent.includes('Vypálit'));
  if (!b) return { found: false, count: btns.length };
  b.scrollIntoView({ block: 'center' });
  const r = b.getBoundingClientRect();
  const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
  const el = document.elementFromPoint(cx, cy);
  return {
    found: true, x: cx, y: cy, disabled: b.disabled,
    rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
    hit: el ? (el.tagName + '.' + (el.className || '')) : null,
    onTop: !!el && (el === b || b.contains(el)),
  };
}
"""


async def main():
    if os.path.isdir(DL):
        shutil.rmtree(DL)
    os.makedirs(DL, exist_ok=True)
    async with m.Harness(url=LIVE) as h:
        await h.cdp("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": DL})
        await h.open_song(pages=6)
        await h.ev(PATCH)
        print("song open, canvas count:", await h.canvas_len())
        await h.annot_toggle()
        await asyncio.sleep(0.8)
        pt = await h.free_point()
        print("free point:", pt)
        # jeden tah perem, aby bylo co vypalovat
        await h.pen_stroke(pt["x"] - 40, pt["y"], pt["x"] + 40, pt["y"] + 30)
        await asyncio.sleep(0.6)
        info = await h.ev("(" + FIND_BTN + ")()")
        print("burn button:", info)
        if not info.get("found"):
            print("NENALEZENO")
            return
        await h.pen_tap(info["x"], info["y"])
        # sleduj 45 s
        for i in range(45):
            await asyncio.sleep(1)
            files = os.listdir(DL)
            toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent || ''")
            disabled = await h.ev("(document.querySelectorAll('.ap-share-btn')[0]||{}).disabled")
            if files or (toast and 'Vypálené' in toast) or i in (5, 15, 30):
                print(f"t={i+1}s files={files} toast={toast!r} disabled={disabled}")
            if files and not disabled:
                break
        print("DL:", [(f, os.path.getsize(os.path.join(DL, f))) for f in os.listdir(DL)])
        print("log:", json.dumps(await h.ev("window.__log"), ensure_ascii=False)[:3000])
        print("toast final:", await h.ev("(document.querySelector('.viewer-toast')||{}).textContent || ''"))


asyncio.run(main())
