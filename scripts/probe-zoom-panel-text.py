#!/usr/bin/env python3
"""Diagnostika panelu ZVĚTŠENÍ A POSUNU — jak velký je text tlačítek.

Jan: „V tomto stejném menu jsou i další tlačítka s čísly a procenty.
Tam je zase hrozně velký text."

Sonda otevře kus, otevře panel zoomu, vyfotí ho a vypíše skutečné
(computed) velikosti písma a rozměry každého tlačítka — aby se ladilo
podle změřeného stavu, ne podle dojmu.

    scripts/run-probe-fresh.sh scripts/probe-zoom-panel-text.py
"""
import asyncio
import base64
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
OUT = "/tmp/zoom-panel"


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

# Každý prvek panelu: text, computed font-size, vnější rozměry, box.
DUMP = r"""
(() => {
  const p = document.querySelector('.zoom-panel');
  if (!p) return null;
  const pr = p.getBoundingClientRect();
  const items = [...p.children].map(el => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName.toLowerCase(),
      cls: el.className,
      text: (el.textContent || '').trim().slice(0, 24),
      title: el.title || '',
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      w: Math.round(r.width), h: Math.round(r.height),
      x: Math.round(r.left), y: Math.round(r.top),
      lines: (() => { const rg = document.createRange(); rg.selectNodeContents(el);
                      return rg.getClientRects().length; })(),
      overflow: el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1,
    };
  });
  return {panel: {w: Math.round(pr.width), h: Math.round(pr.height),
                  x: Math.round(pr.left), y: Math.round(pr.top)},
          items};
})()
"""


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def shot(h, path):
    res = await h.cdp("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(res["data"]))
    print("   vyfoceno:", path)


async def main():
    c = Check()
    h = await fresh_harness()
    async with h:
        await h.open()
        await h.open_song(pages=6, reset=True)
        await h.set_tablet(800, 1280)
        await asyncio.sleep(0.6)

        print("--- otvírám panel zoomu ---")
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Zvětšení')); if (b) b.click(); })()")
        await h.wait_for("!!document.querySelector('.zoom-panel')", 8, "zoom panel")
        await asyncio.sleep(0.5)

        await shot(h, OUT + "-pred.png")

        d = await h.ev(DUMP)
        print("panel: %dx%d na x=%d y=%d" % (d["panel"]["w"], d["panel"]["h"],
                                             d["panel"]["x"], d["panel"]["y"]))
        print("\n%-8s %-8s %-8s %-6s %-6s %-5s %-6s %s" % (
            "text", "font", "váha", "w", "h", "řádků", "přetéká", "třída"))
        for it in d["items"]:
            print("%-8s %-8s %-8s %-6s %-6s %-5s %-6s %s" % (
                repr(it["text"]), it["fontSize"], it["fontWeight"],
                it["w"], it["h"], it["lines"], "ANO" if it["overflow"] else "ne",
                it["cls"]))

        # výřez jen panelu, ať je na fotce vidět detail
        pr = d["panel"]
        res = await h.cdp("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": max(0, pr["x"] - 8), "y": max(0, pr["y"] - 8),
                     "width": pr["w"] + 16, "height": pr["h"] + 16, "scale": 3}})
        with open(OUT + "-detail.png", "wb") as fh:
            fh.write(base64.b64decode(res["data"]))
        print("\n   detail panelu (3x):", OUT + "-detail.png")

        c("panel zoomu se otevřel", True)
    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
