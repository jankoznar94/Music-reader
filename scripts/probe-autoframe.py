#!/usr/bin/env python3
"""Sonda rámu: default vypnuto, plná šířka bez rámu, a ULOŽENÁ PREFERENCE
(stránka/skladba) má vždy přednost před rámem — v obou směrech."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

PDF = "/home/martin_fabian/skladby/out/HLAS_TENOR_1.pdf"

STATE = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
  const v = document.querySelector('.viewer').getBoundingClientRect();
  const svg = document.querySelector('.annot-layer');
  return {cw: Math.round(c.width), vw: Math.round(v.width),
          vb: svg.getAttribute('viewBox'), st: localStorage.getItem('noty-auto-frame-v2')};
})()
"""


async def click_title(h, prefix):
    return await h.ev("(() => { const b=[...document.querySelectorAll('button')]"
                      ".find(x=>(x.title||'').startsWith(%s)); if(!b) return 'chybi';"
                      " b.click(); return 'ok'; })()" % repr(prefix))


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.ev("localStorage.removeItem('noty-auto-frame-v2');"
                   "localStorage.removeItem('noty-auto-frame')")
        await h.open_song(pdf=PDF)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Zvětšení'));b&&b.click()})()")
        await asyncio.sleep(0.5)

        s = await h.ev(STATE)
        print('1 default      ', s)
        chk('default: vypnuto', s['st'] is None)
        chk('default: plná šířka', abs(s['cw'] - (s['vw'] - 12)) <= 3, str(s['cw']))

        # Rám ON
        await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='Rám');b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('2 rám on       ', s)
        chk('rám: oříznuto + safe šířka', s['cw'] < s['vw'] - 100, str(s['cw']))
        vb_on = [float(x) for x in s['vb'].split()]

        # Uložit preference stránky (rám ON)
        print('  save page:', await click_title(h, 'Uložit jako výchozí jen'))
        await asyncio.sleep(1.0)

        # Rám OFF → preference (frame=1) musí držet ořez
        await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='Rám');b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('3 rám off, uložená stránka s rámem', s)
        vb3 = [float(x) for x in s['vb'].split()]
        chk('preference s rámem drží ořez', abs(vb3[2] - vb_on[2]) < 2, f"{vb3[2]:.0f} vs {vb_on[2]:.0f}")

        # Smazat uloženou stránku → rám (vypnutý) = celá stránka
        print('  clear page:', await click_title(h, 'Smazat uložené nastavení této stránky'))
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('4 po smazání preference', s)
        chk('po smazání: plná stránka', s['vb'].startswith('0 0'), s['vb'])

        # Uložit preferenci BEZ rámu, pak Rám ON → preference musí vyhrát (plná stránka)
        print('  save page(no frame):', await click_title(h, 'Uložit jako výchozí jen'))
        await asyncio.sleep(1.0)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='Rám');b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('5 rám on, uložená stránka bez rámu', s)
        chk('preference bez rámu vyhraje', s['vb'].startswith('0 0'), s['vb'])
        chk('uloženo jako zapnuto', s['st'] == '1', str(s['st']))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
