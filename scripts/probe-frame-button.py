#!/usr/bin/env python3
"""Sonda RUČNÍHO rámu: tlačítko na hlavní liště, platí pro JEDNU stránku,
uloží se a po znovuotevření skladby drží. Žádný automatický režim."""
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
  const svg = document.querySelector('.annot-layer');
  const btn = [...document.querySelectorAll('.tb-btn')]
      .find(x => (x.title || '').startsWith('Rám:'));
  return {cw: Math.round(c.width), vw: Math.round(v.width),
          vb: svg.getAttribute('viewBox'),
          btn: !!btn, on: btn ? btn.classList.contains('on') : null,
          page: document.querySelector('.tb-page').textContent.trim()};
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.ev("localStorage.removeItem('noty-auto-frame-v2')")
        await h.open_song()                     # fixture 6 stran
        s = await h.ev(STATE)
        print('1 výchozí        ', s)
        chk('tlačítko Rám na liště', s['btn'])
        chk('výchozí celá stránka', s['vb'].startswith('0 0') and abs(s['cw'] - (s['vw'] - 12)) <= 3)
        chk('tlačítko není aktivní', s['on'] is False)

        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Rám:'));b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('2 rám na str. 1  ', s)
        chk('stránka 1 oříznutá', not s['vb'].startswith('0 0') and s['cw'] < s['vw'] - 50)
        chk('tlačítko aktivní', s['on'] is True)

        # stránka 2 musí zůstat celá (rám je ruční, per page)
        await h.goto(2)
        s = await h.ev(STATE)
        print('3 stránka 2      ', s)
        chk('stránka 2 neoríznutá', s['vb'].startswith('0 0') and s['on'] is False, s['vb'])

        # zpět na 1 a vypnout rám
        await h.goto(1)
        s = await h.ev(STATE)
        chk('stránka 1 po návratu drží rám', s['on'] is True, s['vb'])
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Rám:'));b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('4 rám zrušen     ', s)
        chk('rám zrušen = celá stránka', s['vb'].startswith('0 0'), s['vb'])

        # znovu zapnout a přežít znovuotevření skladby
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Rám:'));b&&b.click()})()")
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        vb_on = s['vb']
        await h.cdp('Page.reload')
        await h.wait_for("document.readyState==='complete'", label='reload')
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label='viewer po reloadu')
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label='první stránka')
        await asyncio.sleep(2.0)
        s = await h.ev(STATE)
        print('5 po znovuotevření', s)
        chk('uložený rám přežil reload', s['vb'] == vb_on and s['on'] is True, f"{s['vb']} vs {vb_on}")
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
