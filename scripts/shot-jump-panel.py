#!/usr/bin/env python3
"""Screenshot okna Skoků (vzhled + cíl na cílové stránce) pro vizuální kontrolu.

    scripts/run-probe-fresh.sh scripts/shot-jump-panel.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
OUT = os.environ.get("SHOT_OUT", "/tmp/noty-jump-panel.png")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness = m.Harness
JS = "window.__barDev"


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(reset=os.environ.get("NOTY_RESET_DB") == "1")
        await h.set_tablet(820, 1180, 2)

        # Dva skoky: VIDE (červený, velký) a Da Capo (modrý, střední) + cíle
        await h.ev(f"""(() => {{
          const d = {JS};
          d.jumps.value = [
            {{ id: 'a', fromPage: 0, toPage: 1, label: 'VIDE', color: '#c0392b', size: 'l',
               place: null, toMark: {{ page: 1, x: 240, y: 420 }} }},
            {{ id: 'b', fromPage: 0, toPage: 2, label: 'Da Capo', color: '#1f6fd0', size: 'm',
               place: null, toMark: null }},
          ];
          d.toggleJumpMode();
          return 1; }})()""")
        await asyncio.sleep(0.8)
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        import base64
        with open(OUT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("panel:", OUT)

        # cíl na cílové stránce (rámeček)
        await h.ev(f"(() => {{ {JS}.gotoPage(1); return 1; }})()")
        await asyncio.sleep(1.0)
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        out2 = OUT.replace(".png", "-target.png")
        with open(out2, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("cíl:", out2)


if __name__ == "__main__":
    asyncio.run(main())
