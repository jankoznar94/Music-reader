#!/usr/bin/env python3
"""Proč zmizelo tlačítko „mazání nastavení stránky“ z panelu zoomu? (Jan, Oct 2026)

Jan: „Tlačítko pro reset nastavení stránky zmizelo úplně.“

Tlačítko má `v-if="hasSavedPageView || hasSavedZoom"`. Sonda projde CELÝ
životní cyklus a u každého kroku vypíše, jestli tlačítko v panelu JE:

  1) čerstvě otevřená skladba          → co ukazuje hasSavedPageView/Zoom
  2) po uložení zobrazení STRÁNKY      (tlačítko diskety v liště)
  3) po uložení zobrazení SKLADBY      (tlačítko hvězdy v liště)
  4) po smazání (klepnutí na koš)      → má zmizet

    scripts/run-probe-fresh.sh scripts/probe-clear-page-view.py
"""
import asyncio
import base64
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check

STATE = r"""
(() => {
  const p = document.querySelector('.zoom-panel');
  const kids = p ? [...p.children] : [];
  return {
    panel: !!p,
    children: kids.length,
    trash: kids.filter(e => (e.title || '').startsWith('Smazat uložené')).length,
    seps: kids.filter(e => e.classList && e.classList.contains('zp-sep')).length,
    lastChild: kids.length ? (kids[kids.length - 1].className || kids[kids.length - 1].tagName) : null,
    titles: kids.map(e => e.title || (e.textContent || '').trim().slice(0, 12)),
    savedPage: document.querySelector('.tb-btn[title^="Uložit jako výchozí jen pro tuto"]')
                 ? document.querySelector('.tb-btn[title^="Uložit jako výchozí jen pro tuto"]')
                     .classList.contains('on') : null,
    savedSong: document.querySelector('.tb-btn[title^="Uložit jako výchozí pro celou"]')
                 ? document.querySelector('.tb-btn[title^="Uložit jako výchozí pro celou"]')
                     .classList.contains('on') : null,
  };
})()
"""

TOPBAR_PAGE = 'Uložit jako výchozí jen pro tuto stránku'
TOPBAR_SONG = 'Uložit jako výchozí pro celou skladbu'
ZOOM_BTN = 'Zvětšení a posun'


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def open_panel(h):
    if not await h.ev("!!document.querySelector('.zoom-panel')"):
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
                   % json.dumps(ZOOM_BTN))
        await asyncio.sleep(0.5)
    return await h.ev(STATE)


async def close_panel(h):
    await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
               % json.dumps(ZOOM_BTN))
    await asyncio.sleep(0.4)


async def tb_click(h, title):
    return await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                      ".find(x => (x.title || '').startsWith(%s));"
                      " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                      % json.dumps(title))


async def shot(h, path):
    res = await h.cdp("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(res["data"]))


async def main():
    c = Check()
    h = await fresh_harness()
    async with h:
        await h.open()
        await h.open_song(pages=6, reset=True)
        await h.set_tablet(800, 1280)
        await asyncio.sleep(0.6)

        print("\n--- 1) čerstvá skladba, otevírám panel zoomu ---")
        s = await open_panel(h)
        print("   děti panelu:", s["children"], "| košů:", s["trash"], "| oddělovačů:", s["seps"])
        print("   poslední prvek:", s["lastChild"])
        print("   titulky:", s["titles"])
        print("   disketa(stránka) svítí:", s["savedPage"], "| hvězda(skladba) svítí:", s["savedSong"])
        c("1) na čerstvé stránce koš není (není co mazat)", s["trash"] == 0, str(s["trash"]))
        c("1) bez uloženého stavu nezůstává osamocený oddělovač (1)",
          s["seps"] == 1, str(s["seps"]))
        c("1) panel končí tlačítkem +10 (žádný visící pruh)",
          s["lastChild"] == 'zp-btn num', str(s["lastChild"]))
        await close_panel(h)

        print("\n--- 2) ukládám zobrazení STRÁNKY (disketa) ---")
        print("   tlačítko:", await tb_click(h, TOPBAR_PAGE))
        await asyncio.sleep(1.2)
        s = await open_panel(h)
        print("   děti panelu:", s["children"], "| košů:", s["trash"], "| oddělovačů:", s["seps"])
        print("   disketa svítí:", s["savedPage"], "| hvězda svítí:", s["savedSong"])
        print("   titulky:", s["titles"])
        c("2) po uložení stránky se koš OBJEVÍ", s["trash"] == 1, str(s["trash"]))
        c("2) s košem je i jeho oddělovač (2)", s["seps"] == 2, str(s["seps"]))
        await shot(h, "/tmp/panel-po-ulozeni-stranky.png")

        if s["trash"] == 1:
            print("\n--- 3) klepnutí na koš ---")
            r = await h.ev("(() => { const p = document.querySelector('.zoom-panel');"
                           " const b = [...p.children].find(e => (e.title || '')"
                           ".startsWith('Smazat uložené')); if (!b) return 'missing';"
                           " b.click(); return 'ok'; })()")
            print("   klik:", r)
            await asyncio.sleep(1.0)
            s2 = await h.ev(STATE)
            print("   košů po smazání:", s2["trash"], "| oddělovačů:", s2["seps"],
                  "| disketa svítí:", s2["savedPage"])
            c("3) po smazání koš zmizí", s2["trash"] == 0, str(s2["trash"]))
            c("3) po smazání zmizí i oddělovač (1)", s2["seps"] == 1, str(s2["seps"]))
        await close_panel(h)

        print("\n--- 4) ukládám zobrazení CELÉ SKLADBY (hvězda) ---")
        print("   tlačítko:", await tb_click(h, TOPBAR_SONG))
        await asyncio.sleep(1.2)
        s = await open_panel(h)
        print("   děti panelu:", s["children"], "| košů:", s["trash"], "| oddělovačů:", s["seps"])
        print("   hvězda svítí:", s["savedSong"])
        c("4) po uložení skladby se koš OBJEVÍ", s["trash"] == 1, str(s["trash"]))
        await shot(h, "/tmp/panel-po-ulozeni-skladby.png")

        print("\n--- 5) ZNOVUOTEVRENÍ skladby (reload + otevřít tytéž noty) ---")
        await close_panel(h)
        # Uklidit hvězdu (zobrazení celé skladby), ať je na stránce jen
        # uložené zobrazení STRÁNKY — testujeme právě jeho načtení z DB.
        await h.ev(
            "(() => { const b = document.querySelector("
            "'.tb-btn[title^=\"Uložit jako výchozí pro celou\"]');"
            " if (b && b.classList.contains('on')) b.click(); return true; })()")
        await asyncio.sleep(0.6)
        # Znovu uložit zobrazení stránky 1, ať je jistota, že existuje.
        await tb_click(h, TOPBAR_PAGE)
        await asyncio.sleep(1.0)
        pre = await h.ev("JSON.stringify([...document.querySelectorAll('.tb-btn')]"
                         ".filter(b => b.classList.contains('on')).map(b => b.title))")
        print("   před reloadem svítí:", pre)

        print("   reload stránky…")
        await h.open()
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=30, label="knihovna po reloadu")
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 10, "seznam skladeb")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "otevření skladby")
        await h.wait_for("!document.querySelector('.viewer-loading')", 40, "první stránka")
        await asyncio.sleep(1.2)
        post = await h.ev("JSON.stringify([...document.querySelectorAll('.tb-btn')]"
                          ".filter(b => b.classList.contains('on')).map(b => b.title))")
        print("   po reloadu svítí:", post)
        s = await open_panel(h)
        print("   děti panelu:", s["children"], "| košů:", s["trash"], "| oddělovačů:", s["seps"])
        print("   titulky:", s["titles"])
        c("5) po znovuotevření skladby je koš ZPĚT (stav se načetl)", s["trash"] == 1, str(s["trash"]))
        c("5) i s ním jeho oddělovač (2)", s["seps"] == 2, str(s["seps"]))
        await shot(h, "/tmp/panel-po-reloadu.png")
        await close_panel(h)

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
