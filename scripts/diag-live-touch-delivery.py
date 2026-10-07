#!/usr/bin/env python3
"""Diag: dorazí na ŽIVÝ web syntetický dvouprstý dotyk? (bez toho je měření slepé)

Živá sonda hlásila, že dvouprstý posun nic neudělá (0,0), zatímco dev totéž
zvládl. Než začnu hledat chybu v appce, musím vyloučit, že dotyk vůbec nedorazil
— přesně na tomhle jsem si jednou spálila běh (viz harness-traps).

Sonda proto:
  1) instalací listeneru zaznamená každý touchstart/move/end a počet dotyků,
  2) udělá dvouprstý dotyk a vypíše, co stránka viděla,
  3) zkontroluje, že gesto otevřelo panel zoomu (auto-open v touchstartu) —
     to je nezávislý důkaz, že dotyk prošel až do appky.
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_HERE)
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_APP, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness = _mod.Harness
_mod.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")

TARGET = os.environ.get("NOTY_TARGET", "https://harlequin-music-reader.web.app/")

LOG_INSTALL = r"""
(() => {
  const v = document.querySelector('.viewer');
  if (!v) return 'no-viewer';
  window.__tlog = [];
  const rec = (e) => window.__tlog.push(e.type.replace('touch','') + ':' + e.touches.length);
  for (const k of ['touchstart','touchmove','touchend','touchcancel'])
    v.addEventListener(k, rec, { capture: true, passive: true });
  return 'ok';
})()
"""


async def main():
    async with Harness(url=TARGET) as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(2.0)
        # otevřít skladbu (na živém webu fixture nenahraju, použiju existující)
        if not await h.ev("document.querySelectorAll('li.song').length"):
            pdf = _mod.make_pdf(6)
            await h.set_file_input("input[type=file]", pdf)
            await h.wait_for("document.querySelectorAll('.author-group').length > 0", 90, "upload")
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "seznam")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 60, "viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", 60, "první stránka")
        await asyncio.sleep(2.0)

        print("cíl:", TARGET)
        print("listener:", await h.ev(LOG_INSTALL))

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2
        print("střed:", round(cx), round(cy))

        # panel zoomu před gestem
        before_panel = await h.ev("!!document.querySelector('.zoom-panel')")

        pts = lambda f, dx=0: [(cx - 70 + dx * f, cy, 12), (cx + 70 + dx * f, cy, 12)]
        await h.touch("touchStart", pts(0))
        await asyncio.sleep(0.1)
        for i in range(1, 7):
            await h.touch("touchMove", pts(i / 6, dx=60))
            await asyncio.sleep(0.03)
        await h.touch("touchEnd", [])
        await asyncio.sleep(1.0)

        log = await h.ev("JSON.stringify(window.__tlog)")
        print("co stránka viděla:", log)
        tr = await h.ev("getComputedStyle(document.querySelector('.stage')).transform")
        print("transform .stage:", tr)
        after_panel = await h.ev("!!document.querySelector('.zoom-panel')")
        print(f"panel zoomu: před={before_panel} po={after_panel}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
