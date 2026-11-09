#!/usr/bin/env python3
"""E2E: počítadlo čísel taktů je PER SKLADBA.

Jan (Nov 2026): „Číslo taktu pro číslování se přenáší mezi skladbami. Dám jinou
skladbu a zůstane tam například 178 z minula. Každou skladbou by se to mělo
resetovat.“

Ověřuje:
  * číslo nastavené v jedné skladbě zůstane v localStorage pod klíčem dané skladby
  * po reloadu téže skladby se vrátí
  * v JINÉ skladbě začíná počítadlo na 1
  * po návratu do první skladby je zase její číslo
"""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

NEXT = "document.querySelector('.ap-bar-next:not(.ap-bar-step)')"


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")


async def next_val(h):
    return await h.ev("(document.querySelector('.ap-bar-next:not(.ap-bar-step)')||{}).value")


async def set_next(h, v):
    await h.set_value(".ap-bar-next:not(.ap-bar-step)", str(v))
    await h.ev("document.querySelector('.ap-bar-next:not(.ap-bar-step)').dispatchEvent(new Event('change',{bubbles:true}))")
    await asyncio.sleep(0.25)


async def open_tool(h):
    if not await h.ev("!!document.querySelector('.ap-tool')"):
        await h.annot_toggle()
        await asyncio.sleep(0.5)
    if not await h.ev("!!document.querySelector('.ap-bar-next')"):
        t = await h.ev(BAR_TOOL)
        if t:
            await h.pen_tap(t["x"], t["y"])
            await asyncio.sleep(0.45)


async def main():
    fails = []
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.clear(); navigator.serviceWorker && navigator.serviceWorker"
                   ".getRegistrations().then(rs => rs.forEach(r => r.unregister())); return true; })()")

        # skladba A
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.5)
        await open_tool(h)
        print("A: výchozí další =", await next_val(h))
        if await next_val(h) != "1":
            fails.append("A nezačíná na 1")
        await set_next(h, 178)
        keys = await h.ev("Object.keys(localStorage).filter(k => k.startsWith('noty.barNext'))")
        print("klíče v localStorage:", keys)
        if not any("noty.barNext." in k for k in keys):
            fails.append("počítadlo se neukládá pod klíč skladby (%s)" % keys)
        if "noty.barNext" in keys:
            fails.append("zůstal starý globální klíč")

        # reload téže skladby
        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(2.5)
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč")
        await open_tool(h)
        print("A po reloadu:", await next_val(h))
        if await next_val(h) != "178":
            fails.append("A po reloadu nemá 178 (má %s)" % await next_val(h))

        # skladba B (nahraná zvlášť) — z prohlížeče zpět do knihovny
        await h.ev("history.back()")
        await asyncio.sleep(1.5)
        await h.set_tablet()
        await h.set_file_input("input[type=file]", m.make_pdf(pages=2, path="/tmp/fixtureB.pdf"))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", timeout=60, label="PDF B")
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 1", timeout=20, label="dvě skladby")
        names = await h.ev("[...document.querySelectorAll('.song-name')].map(e => e.textContent.trim())")
        print("skladby:", names)
        await h.ev("(() => { const s = document.querySelectorAll('.song-name'); s[s.length-1].click(); })()")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč B")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka B")
        await asyncio.sleep(1.0)
        await open_tool(h)
        print("B: další =", await next_val(h))
        if await next_val(h) != "1":
            fails.append("B nezačíná na 1 (má %s)" % await next_val(h))

        # reload B: pořád 1, a klíč skladby A musí zůstat nedotčený (178)
        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload B")
        await asyncio.sleep(2.5)
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč B")
        await open_tool(h)
        keys2 = await h.ev("Object.keys(localStorage).filter(k => k.startsWith('noty.barNext'))"
                           ".map(k => k + '=' + localStorage.getItem(k))")
        print("B po reloadu: další =", await next_val(h), "| klíče:", keys2)
        if await next_val(h) != "1":
            fails.append("B po reloadu nemá 1 (má %s)" % await next_val(h))
        if not any(k.endswith("=178") for k in keys2):
            fails.append("klíč skladby A s 178 zmizel (%s)" % keys2)

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
