#!/usr/bin/env python3
"""Ověření ŽIVÉHO nasazení: tlačítko Rám existuje, default je vypnuto, po
zapnutí se stránka ořízne (viewBox se zmenší) a obsah zůstane uvnitř pruhů."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

URL = "https://harlequin-music-reader.web.app/"


async def main():
    chk = Check()
    async with Harness(url=URL) as h:
        await h.open()
        await h.open_song()          # fixture 6 stran
        # otevřít panel „Zvětšení a posun“ (tlačítko Rám je až v něm)
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Zvětšení')); b && b.click(); })()")
        await asyncio.sleep(0.6)
        state = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          const btns = [...document.querySelectorAll('.zoom-panel .zp-btn')].map(b => b.textContent.trim());
          return {viewBox: svg.getAttribute('viewBox'),
                  hasRam: btns.includes('Rám'),
                  stored: localStorage.getItem('noty-auto-frame'),
                  canvas: document.querySelector('canvas.pdf-canvas').style.width};
        })()""")
        print('před zapnutím:', state)
        chk('tlačítko Rám existuje', state['hasRam'])
        chk('default vypnuto', state['stored'] is None, str(state['stored']))
        vb0 = [float(x) for x in state['viewBox'].split()]
        chk('bez rámu = celá stránka', vb0[0] == 0 and vb0[1] == 0, state['viewBox'])

        # zapnout Rám
        await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='Rám'); b && b.click(); })()")
        await asyncio.sleep(2.5)
        st2 = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
          return {viewBox: svg.getAttribute('viewBox'), stored: localStorage.getItem('noty-auto-frame'),
                  canvas: {w: c.width, h: c.height}, err: window.__err || null};
        })()""")
        print('po zapnutí:', st2)
        vb1 = [float(x) for x in st2['viewBox'].split()]
        chk('uloženo zapnuto', st2['stored'] == '1')
        chk('stránka oříznutá', vb1[2] < vb0[2] and vb1[3] < vb0[3],
            f"{vb0[2]:.0f}x{vb0[3]:.0f} -> {vb1[2]:.0f}x{vb1[3]:.0f}")
        chk('žádná chyba', st2['err'] is None)
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
