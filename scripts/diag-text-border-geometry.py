#!/usr/bin/env python3
"""DIAGNOSTIKA: co je uvnitř textBorderBox — vypiš VŠECHNA vstupní čísla.

Sonda na centrování naměřila rám 312 px u 20bodového dvouznakového textu, což
neodpovídá výpočtu (max(šířka, výška) + 2×okraj ≈ 33 px). Někde je jiné číslo,
než si kód myslí. Tohle vypíše měření, extents i atributy vykresleného rectu,
aby se dalo hádat PŘESNĚ, ne odhadovat.
"""
import asyncio, importlib.util, json, os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")

def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

_m = _load(); _m.CDP_HTTP = CDP
Harness = _m.Harness

async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await h.ev("(() => { const b=[...document.querySelectorAll('.ap-tool')].find(x=>(x.title||'').startsWith('Text')); if(b) b.click(); })()")
        await asyncio.sleep(0.4)
        p = await h.ev("""(() => { const svg=document.querySelector('.annot-layer'); const v=svg.getBoundingClientRect();
          for (const fy of [0.4,0.5,0.3]) for (const fx of [0.5,0.6,0.4]) {
            const x=v.left+v.width*fx, y=v.top+v.height*fy;
            if (document.elementFromPoint(x,y)===svg) return {x,y}; }
          return null; })()""")
        await h.pen_tap(p["x"], p["y"]); await asyncio.sleep(0.9)
        await h.set_value(".ti-input", "ca")
        if not await h.ev("!!document.querySelector('.ti-toggle.on')"):
            await h.ev("document.querySelector('.ti-toggle').click()")
            await asyncio.sleep(0.3)
        await h.ev("document.querySelector('.jp-btn.primary').click()")
        await asyncio.sleep(1.3)

        dump = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          const layerRect = svg.getBoundingClientRect();
          const svgAttrs = { w: svg.getAttribute('width'), h: svg.getAttribute('height'),
                             vb: svg.getAttribute('viewBox'),
                             styleW: svg.style.width, styleH: svg.style.height,
                             cssW: getComputedStyle(svg).width, cssH: getComputedStyle(svg).height };
          const out = { layerRect: [layerRect.left, layerRect.top, layerRect.width, layerRect.height],
                        svgAttrs, texts: [], probes: [], ctm: null };
          // měřítko vrstvy: 1 user unit = kolik CSS px?
          try { const m = svg.getScreenCTM(); out.ctm = [m.a, m.d, m.e, m.f]; } catch (e) {}
          for (const g of svg.querySelectorAll('g')) {
            const t = g.querySelector(':scope > text');
            if (!t || !(t.textContent||'').trim()) continue;
            const r = g.querySelector(':scope > rect.text-border');
            const tb = t.getBoundingClientRect();
            out.texts.push({
              text: t.textContent, fontSize: t.getAttribute('font-size'),
              tBox: [tb.left, tb.top, tb.width, tb.height],
              textLen: (() => { try { return t.getComputedTextLength(); } catch (e) { return null; } })(),
              rect: r ? { x: r.getAttribute('x'), y: r.getAttribute('y'),
                          w: r.getAttribute('width'), h: r.getAttribute('height'),
                          box: (() => { const b = r.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; })() } : null,
            });
          }
          for (const t of svg.querySelectorAll('text.text-measure')) {
            const b = t.getBoundingClientRect();
            out.probes.push({ id: t.id, text: t.textContent, fontSize: t.getAttribute('font-size'),
              len: (() => { try { return t.getComputedTextLength(); } catch (e) { return null; } })(),
              box: [b.left, b.top, b.width, b.height] });
          }
          return JSON.stringify(out); })()""")
        print(json.dumps(json.loads(dump), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
