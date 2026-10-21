#!/usr/bin/env python3
"""Debug: co se stane s dotykem v režimu Ruka (evLog + pozice čtyřúhelníku)."""
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

TOOL_JS = ("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
           ".find(x => (x.title || '').startsWith(%s)); if (b) { b.click(); return 'ok'; }"
           " return 'missing'; })()")


async def dbg(h):
    raw = await h.ev("JSON.stringify(window.__navdbg())")
    return json.loads(raw)


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(m.make_pdf(4))
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        f = await h.free_point()
        x, y = f["x"], f["y"]
        await h.ev(TOOL_JS % json.dumps("Zvýraznění"))
        await h.pen_tap(x - 70, y + 14)
        await h.pen_tap(x - 70, y - 14)
        await h.pen_tap(x + 70, y)
        await h.ev(TOOL_JS % json.dumps("Upravit"))
        await asyncio.sleep(1.5)

        d0 = await h.ev("document.querySelector('.annot-layer path.hl').getAttribute('d')")
        print("d0:", d0)
        await h.palm_tap(x, y)
        await asyncio.sleep(0.5)
        await h.finger_tap(x, y)
        await asyncio.sleep(0.5)
        print("before:", json.dumps(await dbg(h), ensure_ascii=False)[:400])

        await h.touch("touchStart", [(x, y, 12)])
        await asyncio.sleep(0.15)
        print("after start:", json.dumps(await dbg(h), ensure_ascii=False)[:800])
        for i in range(1, 13):
            await h.touch("touchMove", [(x + 5 * i, y + 2 * i, 12)])
            await asyncio.sleep(0.03)
        print("after moves:", json.dumps(await dbg(h), ensure_ascii=False)[:1200])
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        print("after end:", json.dumps(await dbg(h), ensure_ascii=False)[:1200])
        print("d1:", await h.ev("document.querySelector('.annot-layer path.hl').getAttribute('d')"))


asyncio.run(main())
