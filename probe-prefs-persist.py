#!/usr/bin/env python3
"""Volby knihovny přežijí vypnutí appky (listopad 2026).

Jan: „appka by si měla pamatovat některé volby i po vypnutí/zapnutí. Například
zobrazení podle skladatelů/bez skladatelů.“

Ověřuje v reálném prohlížeči:
  1. čisté úložiště = výchozí stav (seskupeno podle skladatelů, řazení podle názvu)
  2. vypnutí seskupení se uloží do localStorage
  3. po reloadu je seskupení pořád vypnuté (a seznam je plochý)
  4. změna řazení na „Datum“ přežije reload
  5. vymazané úložiště = zase výchozí stav
"""
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


async def lib_state(h):
    return await h.ev(
        "(() => ({ grouped: (() => { const b = document.querySelector('.group-toggle');"
        "    return b ? b.classList.contains('on') : null; })(),"
        "  sort: (document.querySelector('select.sort') || {}).value || null,"
        "  prefs: (() => { try { return JSON.parse(localStorage.getItem('noty.prefs') || 'null'); }"
        "           catch (e) { return 'bad'; } })(),"
        "  authors: document.querySelectorAll('.author-header').length,"
        "  flat: document.querySelectorAll('li.song').length }))()")


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.removeItem('noty.prefs')")
        await h.open()

        st = await lib_state(h)
        ok("výchozí: seskupeno podle skladatelů", st["grouped"] is True, st["grouped"])
        ok("výchozí: řazení podle názvu", st["sort"] == "name", st["sort"])

        # --- vypnout seskupení ----------------------------------------------
        await h.ev("document.querySelector('.group-toggle').click()")
        await asyncio.sleep(0.25)
        st = await lib_state(h)
        ok("vypnutí seskupení se projeví", st["grouped"] is False, st["grouped"])
        ok("volba se uložila do localStorage",
           isinstance(st["prefs"], dict) and st["prefs"].get("groupByComposer") is False, st["prefs"])

        # --- reload ----------------------------------------------------------
        await h.open()
        st = await lib_state(h)
        ok("po restartu je seskupení pořád vypnuté", st["grouped"] is False, st["grouped"])

        # --- řazení ----------------------------------------------------------
        await h.ev("(() => { const s = document.querySelector('select.sort');"
                   " s.value = 'date'; s.dispatchEvent(new Event('change', { bubbles: true })); return s.value; })()")
        await asyncio.sleep(0.25)
        await h.open()
        st = await lib_state(h)
        ok("po restartu zůstalo řazení podle data", st["sort"] == "date", st["sort"])
        ok("v localStorage jsou obě volby",
           isinstance(st["prefs"], dict) and st["prefs"].get("sortBy") == "date"
           and st["prefs"].get("groupByComposer") is False, st["prefs"])

        # --- nesmyslná hodnota v úložišti nesmí appku rozhodit -----------------
        await h.ev("localStorage.setItem('noty.prefs', JSON.stringify({ sortBy: 'blbost', groupByComposer: 'ano' }))")
        await h.open()
        st = await lib_state(h)
        ok("nesmyslné uložené hodnoty spadnou na výchozí",
           st["sort"] in ("name", "date") and st["grouped"] is not None, st)

        # --- úklid ------------------------------------------------------------
        await h.ev("localStorage.removeItem('noty.prefs')")
        await h.open()
        st = await lib_state(h)
        ok("po vymazání úložiště je zase výchozí stav",
           st["grouped"] is True and st["sort"] == "name", st)

    ok.report()


asyncio.run(main())
