#!/usr/bin/env python3
"""Co překáží klepnutí do pásu horní lišty (pás lišty úprav)?

Vypíše pro daný bod CELÝ zásobník `elementsFromPoint` s třídami a z-indexy —
aby se dalo určit, který prvek klepnutí spolkne, místo hádání.
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    cand = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    spec = importlib.util.spec_from_file_location("h", cand)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness = _m.Harness

STACK = """(() => {
  const pts = %s;
  const out = [];
  for (const [x, y] of pts) {
    const st = document.elementsFromPoint(x, y).slice(0, 6).map(e => ({
      tag: e.tagName,
      cls: (e.className && e.className.baseVal !== undefined ? e.className.baseVal : (e.className || '')),
      z: getComputedStyle(e).zIndex,
      pos: getComputedStyle(e).position,
      pe: getComputedStyle(e).pointerEvents,
    }));
    const el = document.elementFromPoint(x, y);
    out.push({x, y, top: el ? (el.tagName + '.' + ((el.className && el.className.baseVal !== undefined) ? el.className.baseVal : el.className)) : null, stack: st});
  }
  return JSON.stringify(out);
})()"""


async def main():
    async with Harness() as h:
        # připoj se k běžící stránce (nesahat na načtený stav)
        await h.open()
        info = await h.ev("""(() => JSON.stringify({
          annotMode: !!document.querySelector('.annot-layer.active'),
          bar: !!document.querySelector('.edit-bar'),
          ap: (() => { const p = document.querySelector('.ap-panel, .annot-panel, .ap-collapse');
            return p ? {cls: p.className, r: p.getBoundingClientRect().toJSON()} : null; })(),
          topbar: (() => { const b = document.querySelector('.top-bar');
            return b ? b.getBoundingClientRect().toJSON() : null; })(),
          layer: (() => { const l = document.querySelector('.annot-layer');
            return l ? l.getBoundingClientRect().toJSON() : null; })(),
        }))()""")
        print("stav:", info)
        pts = [[547, 80], [547, 90], [547, 100], [400, 90], [700, 90], [547, 140], [547, 200]]
        print("zásobník v bodech:")
        raw = await h.ev(STACK % json.dumps(pts))
        for row in json.loads(raw):
            print(f"\n  ({row['x']},{row['y']}) top={row['top']}")
            for e in row["stack"]:
                print(f"      {e['tag']:10s} z={e['z']:>5s} {e['pos']:8s} pe={e['pe']:6s} {e['cls']}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
