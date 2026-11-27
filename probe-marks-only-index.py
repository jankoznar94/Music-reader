#!/usr/bin/env python3
"""Značky se v notách kreslí jen když jsou „zobrazené“, v okně Značek nebo
u právě upravované značky (Ruka)."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL


async def drawn(h):
    return await h.ev("[...document.querySelectorAll('.annot-layer g[data-id]')].map(g => g.getAttribute('data-id'))")


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        await h.set_tablet(800, 1280, 2)
        await h.ev("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)))")
        await h.ev("(() => { const d = window.__barDev; d.mkVisible.value = false; d.mkPanelOpen.value = false;"
                   " d.annotations.value.items.push({ id: 'mk-a', page: d.currentPage.value, tool: 'text',"
                   "   color: '#0b6bff', opacity: 1, size: 18, x: 300, y: 700, text: 'A', mk: true },"
                   " { id: 'mk-b', page: d.currentPage.value, tool: 'text',"
                   "   color: '#0b6bff', opacity: 1, size: 18, x: 500, y: 720, text: 'B', mk: true });"
                   " return 1 })()")
        await asyncio.sleep(0.4)
        ok("jen index: v notách nic", await drawn(h) == [], await drawn(h))

        # Ruka bez výběru
        await h.ev("(() => { window.__barDev.tool.value = 'edit'; window.__barDev.editingId.value = null; return 1 })()")
        await asyncio.sleep(0.4)
        ok("Ruka bez výběru: značky zůstanou skryté", await drawn(h) == [], await drawn(h))

        # Ruka s vybranou značkou
        await h.ev("(() => { window.__barDev.editingId.value = 'mk-a'; return 1 })()")
        await asyncio.sleep(0.4)
        ok("Ruka s vybranou značkou: vidět jen ta jedna", await drawn(h) == ['mk-a'], await drawn(h))

        # okno Značek
        await h.ev("(() => { window.__barDev.editingId.value = null; window.__barDev.mkPanelOpen.value = true; return 1 })()")
        await asyncio.sleep(0.4)
        ok("okno Značek: vidět všechny", sorted(await drawn(h)) == ['mk-a', 'mk-b'], await drawn(h))

        # explicitní přepínač
        await h.ev("(() => { window.__barDev.mkPanelOpen.value = false; window.__barDev.mkVisible.value = true;"
                   " window.__barDev.tool.value = 'pencil'; return 1 })()")
        await asyncio.sleep(0.4)
        ok("„V notách: zobrazené“: vidět všechny", sorted(await drawn(h)) == ['mk-a', 'mk-b'], await drawn(h))

        await h.ev("(() => { window.__barDev.mkVisible.value = false; return 1 })()")
        await asyncio.sleep(0.4)
        ok("zpět na „jen index“: skryté", await drawn(h) == [], await drawn(h))

        ok("žádné chyby v konzoli", not await h.ev("window.__errs"), await h.ev("window.__errs"))
    ok.report()

asyncio.run(main())
