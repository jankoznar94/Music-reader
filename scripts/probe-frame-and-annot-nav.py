#!/usr/bin/env python3
"""Sonda: rám sahá až do krajů + v anotaci zmizí okrajové zóny a listuje se
dvěma tlačítky."""
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
  const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
  const v = document.querySelector('.viewer').getBoundingClientRect();
  return {cw: Math.round(c.width), ch: Math.round(c.height),
          vw: Math.round(v.width), vh: Math.round(v.height),
          vb: document.querySelector('.annot-layer').getAttribute('viewBox'),
          hints: document.querySelectorAll('.edge-hint').length,
          navBtns: document.querySelectorAll('.annot-nav-btn').length,
          page: document.querySelector('.tb-page').textContent.trim(),
          on: (() => { const b = [...document.querySelectorAll('.tb-btn')]
                 .find(x => (x.title || '').startsWith('Rám:'));
                 return b ? b.classList.contains('on') : null; })()};
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song()                     # fixture 6 stran
        s = await h.ev(STATE)
        print('1 výchozí            ', s)
        chk('výchozí celá šířka', abs(s['cw'] - (s['vw'] - 12)) <= 3)
        chk('výchozí: okrajové pruhy', s['hints'] == 2)
        chk('výchozí: žádná nav tlačítka', s['navBtns'] == 0)

        # Rám na stránce 1 — musí být PŘES CELOU šířku
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Rám:'));b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('2 rám (do krajů)     ', s)
        chk('rám: oříznuto', not s['vb'].startswith('0 0'))
        chk('rám: plná šířka', abs(s['cw'] - (s['vw'] - 12)) <= 3, str(s['cw']))

        # Anotační režim
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Anotace'));b&&b.click()})()")
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        print('3 anotace            ', s)
        chk('anotace: pruhy zmizely', s['hints'] == 0)
        chk('anotace: dvě nav tlačítka', s['navBtns'] == 2)

        # Klepnutí na pravý kraj NESMÍ listovat
        p0 = s['page']
        await h.finger_tap(s['vw'] - 25, s['vh'] * 0.7)
        s = await h.ev(STATE)
        print('4 tap na kraj        ', s['page'])
        chk('anotace: kraj nelistuje', s['page'] == p0, f"{p0} -> {s['page']}")
        chk('anotace: pruhy pořád pryč', s['hints'] == 0)

        # Tlačítko vpravo listuje
        await h.ev("(()=>{const b=document.querySelectorAll('.annot-nav-btn')[1];b&&b.click()})()")
        await asyncio.sleep(1.6)
        s = await h.ev(STATE)
        print('5 nav tlačítko       ', s['page'])
        chk('anotace: tlačítko listuje', s['page'].startswith('2 /'), s['page'])

        # Zpět do čtení → pruhy zpět, tlačítka zmizí
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Anotace'));b&&b.click()})()")
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        print('6 zpět do čtení       ', s)
        chk('čtení: pruhy zpět', s['hints'] == 2)
        chk('čtení: nav tlačítka pryč', s['navBtns'] == 0)
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
