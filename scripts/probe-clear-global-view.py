#!/usr/bin/env python3
"""Sonda vynulování GLOBÁLNÍ preference: uloží se zobrazení skladby a koš
v panelu zoomu ho musí smazat (dřív mazal jen stránku)."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

STATE = r"""
(() => {
  const st = [...document.querySelectorAll('.tb-btn')]
      .find(x => (x.title || '').startsWith('Uložit jako výchozí pro celou'));
  return {saved: !!st && st.classList.contains('on'),
          zoom: document.querySelector('.zoom-btn') ? document.querySelector('.zoom-btn').textContent.trim() : null,
          trash: !!document.querySelector('.zoom-panel .zp-btn[title^="Vynulovat"]')};
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song()
        # panel zoomu
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Zvětšení'));b&&b.click()})()")
        await asyncio.sleep(0.5)
        # přiblížit, aby bylo co resetovat
        for _ in range(3):
            await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                       ".find(x=>x.textContent.trim()==='+');b&&b.click()})()")
        await asyncio.sleep(0.4)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Uložit jako výchozí pro celou skladbu'));b&&b.click()})()")
        await asyncio.sleep(1.0)
        s = await h.ev(STATE)
        print('po uložení globálu', s)
        chk('skladba má uložené zobrazení', s['saved'] is True)
        chk('zoom není 100 %', s['zoom'] not in ('100%', '100 %'), str(s['zoom']))

        # koš v panelu zoomu → vynulovat globál
        await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vynulovat'));b&&b.click()})()")
        await asyncio.sleep(2.0)
        s = await h.ev(STATE)
        print('po vynulování     ', s)
        chk('globál smazán', s['saved'] is False, str(s['saved']))
        chk('zoom zpět na 100 %', s['zoom'] in ('100%', '100 %'), str(s['zoom']))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
