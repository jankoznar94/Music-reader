#!/usr/bin/env python3
"""Diagnostika vzhledu textu značky v seznamu — proč je první písmeno
zkosené/oříznuté (Jan, 20. 11. 2026).

Vypíše computed style textu i řádku (font, line-height, overflow, transform,
letter-spacing, šířky) a uloží ZOOMovaný screenshot prvního řádku do
/tmp/marks-row.png, ať je vidět, co se v prohlížeči opravdu vykreslilo.
"""
import asyncio
import base64
import importlib.util
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
APP = os.environ.get("APP_URL") or "http://localhost:5173/"
OUT = os.environ.get("OUT", "/tmp/marks-row.png")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    m.CDP_HTTP = CDP  # type: ignore[attr-defined]
    return m


m = _load()

SEED = """(() => {
  const d = window.__barDev;
  const mk = (page, text, y) => ({
    id: 'diag-' + text, page, tool: 'text', mk: true, hidden: true,
    text, size: 12, color: '#0b6bff', opacity: 1, border: false, x: 300, y,
  });
  d.annotations.value.items = [mk(0, 'Část 1', 300), mk(2, 'Řada', 420),
                               mk(4, '12', 380), mk(5, 'Špička', 500)];
  d.currentPage.value = 0;
  return d.annotations.value.items.length;
})()"""

INFO = r"""(() => {
  const row = document.querySelector('.marks-panel .jp-list .jp-item');
  if (!row) return null;
  const lab = row.querySelector('.mk-label');
  const txt = row.querySelector('.marks-text');
  const pg = row.querySelector('.jp-item-pages');
  const pick = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      cls: el.className, tag: el.tagName,
      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      font: cs.fontFamily.slice(0, 60), size: cs.fontSize, lh: cs.lineHeight,
      weight: cs.fontWeight, style: cs.fontStyle, spacing: cs.letterSpacing,
      transform: cs.transform, overflow: cs.overflow, textOverflow: cs.textOverflow,
      whiteSpace: cs.whiteSpace, pad: cs.padding, margin: cs.margin,
      display: cs.display, align: cs.alignItems, justify: cs.justifyContent,
      flex: cs.flex, minW: cs.minWidth, w: cs.width, h: cs.height,
      scrollW: el.scrollWidth, clientW: el.clientWidth,
    };
  };
  return { row: pick(row), label: pick(lab), text: pick(txt), page: pick(pg) };
})()"""


async def main():
    async with m.Harness(url=APP) as h:
        await h.set_tablet(390, 844, 3)
        await h.open()
        await h.open_song(m.make_pdf(8), reset=False)
        await asyncio.sleep(1.0)
        print("items:", await h.ev(SEED))
        await asyncio.sleep(0.6)
        if await h.ev("(() => !!document.querySelector('.marks-panel'))()") is False:
            await h.ev("document.querySelector('.tb-mark').click()")
        await asyncio.sleep(0.8)
        info = await h.ev(INFO)
        for k, v in (info or {}).items():
            print(k, "=", v)
        rect = await h.ev(
            "(() => { const r = document.querySelector('.marks-panel .jp-list .jp-item').getBoundingClientRect();"
            " return [r.x - 4, r.y - 4, r.width + 8, r.height + 8]; })()")
        raw = await h.cdp("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3], "scale": 6},
        })
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(raw["data"]))
        print("saved", OUT)


asyncio.run(main())
