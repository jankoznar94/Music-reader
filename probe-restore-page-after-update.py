#!/usr/bin/env python3
"""Po aktualizaci appky se prohlížeč vrátí na stejnou stránku not."""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL
VW, VH = (int(x) for x in os.environ.get("NOTY_VIEWPORT", "800x1280").split("x"))


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(VW, VH, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','button');"
                   "localStorage.removeItem('noty.restoreAfterUpdate');"
                   "localStorage.removeItem('noty.lastPos')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.set_tablet(VW, VH, 2)
        await asyncio.sleep(0.5)

        # 1) obyčejné otevření = první stránka
        ok("bez značky se otevře 1. stránka",
           await h.ev("window.__barDev.currentPage.value") == 0,
           await h.ev("window.__barDev.currentPage.value"))
        ok("bez značky značka nezůstane", await h.ev("localStorage.getItem('noty.restoreAfterUpdate')") is None, None)

        # 2) jdi na 3. stránku → pozice se pamatuje
        await h.ev("window.__barDev.gotoPage(2)")
        await asyncio.sleep(0.7)
        pos = await h.ev("localStorage.getItem('noty.lastPos')")
        ok("pozice se ukládá", pos is not None and json.loads(pos)["page"] == 2, pos)

        # 3) simulace tlačítka „Aktualizovat“ (značka + zamrzlá pozice + reload)
        await h.ev("localStorage.setItem('noty.restoreAfterUpdate', String(Date.now()));"
                   "localStorage.setItem('noty.updatePos', localStorage.getItem('noty.lastPos'))")
        await h.ev("location.reload()")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "reload")
        await asyncio.sleep(1.2)
        page = await h.ev("window.__barDev.currentPage.value")
        ok("po aktualizaci se vrací na 3. stránku", page == 2, page)
        counter = await h.ev("(() => { const e = document.querySelector('.tb-page');"
                             " return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null })()")
        ok("počítadlo ukazuje 3 / 6", counter and counter.startswith("3 / 6"), counter)
        # Značka se NEMAŽE hned — jinak by druhý start těsně po aktualizaci
        # (service worker, pád) spadl na jedničku. Maže ji až listování.
        ok("značka zůstává pro případ druhého startu",
           await h.ev("localStorage.getItem('noty.restoreAfterUpdate')") is not None,
           await h.ev("localStorage.getItem('noty.restoreAfterUpdate')"))

        # 4) listování uživatele značku smaže → další start = 1. stránka
        await h.ev("window.__barDev.nextPage()")
        await asyncio.sleep(0.8)
        ok("listování značku smazalo",
           await h.ev("localStorage.getItem('noty.restoreAfterUpdate')") is None, None)
        await h.ev("location.reload()")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "reload2")
        await asyncio.sleep(1.0)
        page2 = await h.ev("window.__barDev.currentPage.value")
        ok("bez značky (další start) se otevře 1. stránka", page2 == 0, page2)

        ok("žádné chyby v konzoli", not await h.ev("window.__errs || []"), None)
    ok.report()

asyncio.run(main())
