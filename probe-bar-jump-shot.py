#!/usr/bin/env python3
"""Screenshot: dialog stránky s řádkem „Skoč na takt“ + očíslované takty."""
import asyncio
import base64
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")


async def main():
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.clear(); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.4)
        # dvě čísla obdélníkem, ať je v notách vidět
        for y in (900, 1030):
            await h.pen_down(470, y)
            await h.pen_move(600, y + 30)
            await h.pen_move(700, y + 60)
            await h.pen_up(700, y + 60)
            await asyncio.sleep(0.4)
        await h.ev("document.querySelector('.tb-page').click()")
        await h.wait_for("!!document.querySelector('.pg-bar-go')", timeout=8, label="dialog")
        await h.set_value(".pg-bar-go", "7")
        await asyncio.sleep(0.3)
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        open("/tmp/bar-jump-dialog.png", "wb").write(base64.b64decode(shot["data"]))
        print("hotovo")


asyncio.run(main())
