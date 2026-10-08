#!/usr/bin/env python3
"""DIAGNOSTIKA: proč sonda A nenašla volný bod na plátně?

Sonda A skončila „nešlo změřit 12“ — `free_xy` nevracel bod ani jednou, zatímco
v části B (stejná funkce) fungoval. Vypíše se stav: který nástroj je vybraný,
jestli je panel sbalený, co vrací elementFromPoint na mřížce bodů, a co je
v zásobníku nad vrstvou.

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/diag-free-point.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness = _m.Harness


async def dump(h, label):
    raw = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer');
      const panel = document.querySelector('.annot-panel');
      const tools = [...document.querySelectorAll('.ap-tool')]
        .filter(b => b.classList.contains('on')).map(b => b.title);
      const items = svg ? svg.querySelectorAll('g > text, g > path, g > rect, g > line').length : -1;
      let scan = [];
      if (svg) {
        const v = svg.getBoundingClientRect();
        for (const fx of [0.3, 0.5, 0.7]) {
          const x = v.left + v.width * fx, y = v.top + v.height * 0.5;
          const el = document.elementFromPoint(x, y);
          scan.push({ fx, el: el ? (el.tagName + '.' + (el.getAttribute('class') || '')) : null });
        }
      }
      return JSON.stringify({
        layer: !!svg,
        layerW: svg ? Math.round(svg.getBoundingClientRect().width) : null,
        panel: panel ? (panel.querySelector('.ap-cat') ? 'rozbaleny' : 'sbaleny') : 'zadny',
        toolsOn: tools,
        panelOpen: !!document.querySelector('.annot-panel .ap-cat'),
        dialog: !!document.querySelector('.text-input-overlay'),
        items, scan,
        annot: (() => { const b = [...document.querySelectorAll('.tb-btn')]
          .find(x => (x.title || '').startsWith('Anotace'));
          return b ? b.classList.contains('on') : null; })(),
      }); })()""")
    print(f"[{label}] {raw}")


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8))
        await h.set_tablet()
        await dump(h, "1. po otevreni skladby")

        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Anotace')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        await dump(h, "2. anotace zapnuta")

        # sbalit panel
        await h.ev("""(() => { const b = document.querySelector('.ap-collapse');
          if (!b) return 'no-toggle';
          const open = document.querySelector('.annot-panel .ap-cat');
          if (open) b.click();
          return 'ok'; })()""")
        await asyncio.sleep(0.5)
        await dump(h, "3. panel sbali")

        # vybrat nastroj Text (po sbaleni nemusi byt v DOM!)
        r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
          .find(x => (x.title || '').startsWith('Text'));
          if (!b) return 'NENALEZEN (panel je sbaleny!)';
          b.click(); return 'kliknuto'; })()""")
        await asyncio.sleep(0.5)
        print("   vyber nastroje Text:", r)
        await dump(h, "4. po vyberu Text")

        # co dela free_xy
        raw = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer'); if (!svg) return 'no-svg';
          const v = svg.getBoundingClientRect();
          const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
            .map(e => e.getBoundingClientRect());
          const near = (x, y, d) => boxes.some(r => r.width > 0 &&
            x > r.left - d && x < r.right + d && y > r.top - d && y < r.bottom + d);
          const hits = [];
          for (let y = v.top + 40; y < v.bottom - 40; y += 60) {
            for (let x = v.left + 24; x < v.right - 24; x += 60) {
              const el = document.elementFromPoint(x, y);
              if (el === svg) hits.push([Math.round(x), Math.round(y), near(x, y, 30)]);
            }
          }
          return JSON.stringify({ total: hits.length,
            volnych: hits.filter(t => !t[2]).length, vzorek: hits.slice(0, 5) });
        })()""")
        print("   free_xy scan:", raw)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
