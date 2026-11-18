#!/usr/bin/env python3
"""Skoky: listování s otevřeným oknem + vzhled tlačítka + cíl na cílové stránce.

Jan, 18. 11. 2026:
  * „Listování stránek když je zapnuté okno pro vytváření skoků nefunguje.“
  * „Rozšířit možnosti jak zobrazíme tlačítko pro daný skok — změna textu,
    barvy, atd.“
  * „Na stránce, na kterou skáčeme, by to chtělo vložit značku na místo, kam
    chce uživatel konkrétně skočit.“

Co sonda ověřuje:
1. s otevřeným oknem Skoků ťuknutí na okraj LISTUJE (obě strany) a okno zůstane,
2. Start/Konec na různých stránkách jde nastavit (to je smysl listování),
3. cíl skoku (jedno ťuknutí na cílové stránce) se uloží a kreslí se rámečkem,
4. barva a velikost tlačítka se uloží a opravdu se propíšou do stylu tlačítka,
5. skok na cíl rozsvítí cíl (flash) a okno úprav načte existující skok.

    scripts/run-probe-fresh.sh scripts/probe-jump-panel-nav.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
RESET_DB = os.environ.get("NOTY_RESET_DB") == "1"


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

JS = "window.__barDev"


async def page(h):
    return (await h.page_text()).split("/")[0].strip()


async def panel_open(h):
    return bool(await h.ev("!!document.querySelector('[data-panel=\"jump\"]')"))


async def free_edge(h, side, fy=0.88):
    """Bod v okrajové zóně, který NENÍ pod plovoucím panelem (jinak tap spolkne panel)."""
    return await h.ev(f"""(() => {{
      const v = document.querySelector('.viewer').getBoundingClientRect();
      const x = {'v.left + 10' if side == 'left' else 'v.right - 10'};
      for (const f of [0.88, 0.8, 0.7, 0.55, 0.42, 0.3]) {{
        const y = v.top + v.height * f;
        const el = document.elementFromPoint(x, y);
        if (!el) continue;
        if (el.closest('.jump-panel, .top-bar, .jump-strip, button')) continue;
        return {{x, y}};
      }}
      return null;
    }})()""")


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(reset=RESET_DB)
        await h.set_tablet(800, 1280, 2)

        # --- 1. Okno Skoků otevřené, listování okrajem musí fungovat ---------
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Vytvořit skok'));"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.5)
        ok("okno Skoků se otevřelo", await panel_open(h))

        p0 = await page(h)
        e = await free_edge(h, "right")
        ok("volný bod v pravém okraji (mimo panel)", bool(e), json.dumps(e))
        await h.finger_tap(e["x"], e["y"])
        p1 = await page(h)
        ok("tap na pravý okraj s otevřeným oknem Skoků listuje", p1 != p0, f"{p0} -> {p1}")
        ok("okno Skoků po listování zůstalo otevřené", await panel_open(h))

        e = await free_edge(h, "left")
        await h.finger_tap(e["x"], e["y"])
        p2 = await page(h)
        ok("tap na levý okraj listuje zpět", p2 != p1, f"{p1} -> {p2}")

        # --- 2. Start a Konec na různých stránkách ----------------------------
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.trim() === 'Start'); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.4)
        start_page = await page(h)
        e = await free_edge(h, "right")
        await h.finger_tap(e["x"], e["y"])
        await asyncio.sleep(0.8)
        end_page = await page(h)
        ok("s otevřeným oknem se dá přelistovat na cílovou stránku",
           end_page != start_page, f"{start_page} -> {end_page}")
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.startsWith('Konec')); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.4)
        st = json.loads(await h.ev(f"(() => JSON.stringify({{s: {JS}.jumpStart.value, e: {JS}.jumpEnd.value}}))()"))
        ok("Start i Konec jsou nastavené a různé",
           st["s"] is not None and st["e"] is not None and st["s"] != st["e"], json.dumps(st))

        # --- 3. Cíl skoku na cílové stránce ----------------------------------
        await h.ev(f"(() => {{ {JS}.jumpLabel.value = 'VIDE'; return 1; }})()")
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.trim() === 'Označit cíl na stránce'); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.5)
        ok("panel se při označování cíle schová",
           not await panel_open(h))
        ok("nápověda cíle je vidět", bool(await h.ev("!!document.querySelector('.jp-place-hint')")))

        pt = await h.free_point(0.35, 0.65)
        await h.finger_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.4)
        tm = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumpToMark.value))()"))
        ok("cíl se uložil na cílovou stránku",
           bool(tm) and tm.get("page") == st["e"], json.dumps(tm))
        ok("cíl se hned kreslí rámečkem (náhled)",
           bool(await h.ev("!!document.querySelector('.jump-target-mark.preview')")))

        # --- 4. Barva + velikost ---------------------------------------------
        await h.ev("""(() => { const sw = document.querySelectorAll('[data-panel="jump"] .jp-sw');
            sw[1].click(); return sw.length; })()""")   # 2. barva = červená
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn.sm')]
            .find(x => x.textContent.trim() === 'Velké'); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.3)
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.trim() === 'Uložit skok'); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.8)

        j = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value))()"))
        ok("skok se uložil", len(j) == 1, json.dumps(j)[:220])
        if j:
            ok("uložená barva je zvolená (červená)", j[0].get("color") == "#c0392b", str(j[0].get("color")))
            ok("uložená velikost je Velké", j[0].get("size") == "l", str(j[0].get("size")))
            ok("uložený cíl má stránku i souřadnice",
               bool(j[0].get("toMark")) and j[0]["toMark"].get("page") == st["e"])

        # trvalý rámeček cíle na cílové stránce (jsme na ní)
        ok("na cílové stránce je rámeček cíle",
           bool(await h.ev("!!document.querySelector('.jump-target-mark:not(.preview)')")))

        # --- 5. Skok na cíl: přepne stránku a rozsvítí cíl --------------------
        await h.ev(f"(() => {{ {JS}.gotoPage({st['s']}); return 1; }})()")
        await asyncio.sleep(0.8)
        btn = await h.ev("""(() => { const b = document.querySelector('.jump-strip .jump-btn');
            if (!b) return null; const r = b.getBoundingClientRect();
            return JSON.stringify({x: r.left + r.width / 2, y: r.top + r.height / 2,
              bg: getComputedStyle(b).backgroundColor, fs: getComputedStyle(b).fontSize}); })()""")
        ok("tlačítko skoku je na okraji displeje", bool(btn), str(btn))
        if btn:
            b = json.loads(btn)
            ok("tlačítko má zvolenou barvu", b["bg"] == "rgb(192, 57, 43)", b["bg"])
            await h.finger_tap(b["x"], b["y"])
            await asyncio.sleep(0.9)
            ok("skok přepnul na cílovou stránku", await page(h) == end_page, await page(h))
            ok("cíl se po skoku rozsvítil (flash)",
               bool(await h.ev("!!document.querySelector('.jump-target-mark.flash')")))

        # --- 6. Úprava existujícího skoku ------------------------------------
        await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title || '').startsWith('Vytvořit skok')); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.5)
        await h.ev("""(() => { const b = document.querySelector('[data-panel="jump"] .jp-item .jp-del');
            if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.5)
        ok("okno úprav načetlo skok", bool(await h.ev(
            "(() => { const t = document.querySelector('[data-panel=\"jump\"] .jp-title');"
            " return t && t.textContent.includes('Úprava'); })()")))
        ok("do pole se načetl text skoku",
           (await h.ev("document.querySelector('[data-panel=\"jump\"] .jp-input').value")) == "VIDE")
        await h.ev(f"(() => {{ {JS}.jumpLabel.value = 'Da Capo'; return 1; }})()")
        await asyncio.sleep(0.2)
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.trim() === 'Uložit změny'); if (b) b.click(); return 1; })()""")
        await asyncio.sleep(0.8)
        j2 = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value))()"))
        ok("úprava přepsala text a NEpřidala druhý skok",
           len(j2) == 1 and j2[0]["label"] == "Da Capo", json.dumps(j2)[:200])
        ok("po úpravě zůstal cíl", bool(j2 and j2[0].get("toMark")))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
