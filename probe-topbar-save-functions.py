#!/usr/bin/env python3
"""Dělají tři vytažená tlačítka na liště SVOJÍ funkci?

Přesun do lišty je jen polovina práce — Jan: „když ho teď sdílí dvě různé
funkce“ (stránka vs. celá skladba). Ověřuje se proto, že každé tlačítko zapíše
to, co má, a že se to uživatel dozví potvrzením:
  * Uložit stav TÉTO stránky  → hláška „Výchozí zobrazení stránky N uloženo“
  * Uložit pro CELOU skladbu  → hláška „Výchozí zobrazení skladby uloženo“
  * Vycentrovat               → zoom zpět na 100 % a posun na 0
  * a hlášky se NESMÍ zaměnit (to je jádro Janovy stížnosti na sdílení)
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

STATE = r"""
(() => {
  const s = document.querySelector('.stage');
  const m = new DOMMatrix(getComputedStyle(s).transform);
  const t = document.querySelector('.viewer-toast');
  const on = [...document.querySelectorAll('.top-bar .tb-btn.on')].map(b=>b.title);
  return { zoomFit: +Math.hypot(m.a, m.b).toFixed(3), panX:+m.e.toFixed(1), panY:+m.f.toFixed(1),
           toast: t ? t.textContent.trim() : '', savedOn: on };
})()
"""


async def click(h, title_part):
    n = await h.ev(
        "(() => { const b=[...document.querySelectorAll('.top-bar .tb-btn')]"
        ".find(x=>(x.title||'').startsWith(%s)); if(!b) return 0; b.click(); return 1; })()"
        % json.dumps(title_part))
    await asyncio.sleep(0.9)
    return n == 1


async def run():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open_song(pages=6)
        await asyncio.sleep(0.8)

        # --- 0) Vycentrovat BEZ uloženého zobrazení → zpět na 100 % ---
        # ⚠️ Musí být PRVNÍ: Vycentrovat vrací ULOŽENÉ výchozí zobrazení, takže
        # po uložení 150 % by (správně!) vrátilo 150 % — a test by hlásil
        # falešný FAIL, že vycentrování nefunguje. Ověřeno: přesně takhle
        # napoprvé selhal. Pořadí kroků je součástí správného testu.
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Zvětšení a posun'); b.click(); return true; })()")
        await asyncio.sleep(0.4)
        for _ in range(10):
            await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                       ".find(x=>x.title==='Přiblížit'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(0.05)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Zvětšení a posun'); b.click(); return true; })()")
        await asyncio.sleep(0.5)
        z0 = await h.ev(STATE)
        ok("zoom nastaven nad výchozí", z0["zoomFit"] > 1.2, f"zoomFit={z0['zoomFit']}")
        ok("tlačítko „Vycentrovat“ na liště kliknuto", await click(h, "Vycentrovat"))
        await asyncio.sleep(0.8)
        z1 = await h.ev(STATE)
        print(f"  vycentrování bez uloženého zobrazení: {z0['zoomFit']} -> {z1['zoomFit']}")
        ok("Vycentrovat bez uloženého zobrazení vrátí 100 %",
           abs(z1["zoomFit"] - 1.0) < 0.02, f"{z0['zoomFit']} -> {z1['zoomFit']}")

        # --- nastav známý stav (zoom 150 %) ať má co ukládat ---
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Zvětšení a posun'); b.click(); return true; })()")
        await asyncio.sleep(0.4)
        for _ in range(10):
            await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                       ".find(x=>x.title==='Přiblížit'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(0.05)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Zvětšení a posun'); b.click(); return true; })()")
        await asyncio.sleep(0.5)
        st = await h.ev(STATE)
        print(f"  stav před ukládáním: {json.dumps(st)}")
        ok("zoom se podařilo nastavit nad výchozí (je co ukládat)",
           st["zoomFit"] > 1.2, f"zoomFit={st['zoomFit']}")

        # --- 1) uložit stav této stránky ---
        ok("tlačítko „Uložit stav této stránky“ na liště kliknuto",
           await click(h, "Uložit jako výchozí jen pro tuto stránku"))
        st = await h.ev(STATE)
        print(f"  po uložení stránky:  toast=\"{st['toast']}\"  svítí={st['savedOn']}")
        ok("hláška je o STRÁNCE (ne o skladbě)", "stránky" in st["toast"], st["toast"])
        ok("hláška obsahuje číslo stránky", " 1 " in st["toast"] or "stránky 1" in st["toast"],
           st["toast"])
        ok("tlačítko stránky se vybarvilo",
           any("jen pro tuto stránku" in (t or "") for t in st["savedOn"]), str(st["savedOn"]))

        # --- 2) uložit pro celou skladbu (hláška se NESMÍ zaměnit) ---
        await asyncio.sleep(2.4)   # ať předchozí hláška zmizí
        ok("tlačítko „Uložit pro celou skladbu“ na liště kliknuto",
           await click(h, "Uložit jako výchozí pro celou skladbu"))
        st = await h.ev(STATE)
        print(f"  po uložení skladby:  toast=\"{st['toast']}\"  svítí={st['savedOn']}")
        ok("hláška je o SKLADBĚ (ne o stránce)",
           "skladby" in st["toast"] and "stránky" not in st["toast"], st["toast"])
        ok("tlačítko skladby se vybarvilo",
           any("pro celou skladbu" in (t or "") for t in st["savedOn"]), str(st["savedOn"]))

        # --- 3) Vycentrovat po uložení vrátí ULOŽENÉ zobrazení (ne 100 %) ---
        # Tohle je druhá polovina správného chování a Janův požadavek: co si
        # uložil jako výchozí, to mu vycentrování vrátí. (Test na 100 % je
        # v kroku 0, ještě než bylo něco uložené.)
        await asyncio.sleep(2.4)
        before = await h.ev(STATE)
        ok("před vycentrováním je zoom stále zvětšený", before["zoomFit"] > 1.2,
           f"zoomFit={before['zoomFit']}")
        ok("tlačítko „Vycentrovat“ na liště kliknuto", await click(h, "Vycentrovat"))
        await asyncio.sleep(0.8)
        after = await h.ev(STATE)
        print(f"  po vycentrování:     {json.dumps(after)}")
        ok("Vycentrovat vrátí ULOŽENÉ výchozí zobrazení stránky (150 %)",
           abs(after["zoomFit"] - 1.5) < 0.02, f"{before['zoomFit']} -> {after['zoomFit']}")
        ok("Vycentrovat vrátilo posun na 0",
           abs(after["panX"]) < 0.5 and abs(after["panY"]) < 0.5,
           f"pan {after['panX']},{after['panY']}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
