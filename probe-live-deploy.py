#!/usr/bin/env python3
"""Ověření, že nové funkce jsou na ŽIVÉM webu (harlequin-music-reader.web.app).

Ne jen že deploy proběhl — čte se skutečný stav stránky: je v toolbaru
přepínač seskupení a je v dialogu pole pro první stránku?
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

LIVE = "https://harlequin-music-reader.web.app/"


async def main():
    async with m.Harness(url=LIVE) as h:
        await h.cdp("Page.navigate", {"url": LIVE})
        await h.wait_for("document.readyState === 'complete'", timeout=40, label="live load")
        await asyncio.sleep(3)
        print("URL:", await h.ev("location.href"))
        print("přepínač seskupení v toolbaru:", await h.ev(
            "!!document.querySelector('.group-toggle')"))
        print("verze ze service workeru:", await h.ev(
            "(() => { const s = [...document.querySelectorAll('script')].map(x=>x.src).join(' ');"
            " return s.slice(0, 180); })()"))


asyncio.run(main())
