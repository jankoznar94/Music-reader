#!/usr/bin/env python3
"""Sonda menu Zobrazení: jedno tlačítko, tři skupiny, každá s vlastním košem."""
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
  const groups = [...document.querySelectorAll('.prefs-group')].map(g => ({
    head: g.querySelector('.prefs-group-head span')?.textContent.trim(),
    state: g.querySelector('.prefs-state')?.textContent.trim(),
    trashDisabled: g.querySelector('.zp-btn.danger')?.disabled,
  }));
  const c = document.querySelector('canvas.pdf-canvas').getBoundingClientRect();
  return {open: !!document.querySelector('.prefs-panel'),
          panelOpenCount: document.querySelectorAll('.zoom-panel').length,
          groups, cw: Math.round(c.width),
          vb: document.querySelector('.annot-layer').getAttribute('viewBox')};
})()
"""


async def click_text(h, text):
    return await h.ev("(() => { const b=[...document.querySelectorAll('.prefs-panel button,.tb-btn')]"
                      ".find(x=>x.textContent.trim()==%s); if(!b) return 'chybi'; b.click(); return 'ok'; })()" % repr(text))


async def click_trash(h, idx):
    return await h.ev("(() => { const b=document.querySelectorAll('.prefs-panel .zp-btn.danger')[%d];"
                      " if(!b) return 'chybi'; b.click(); return 'ok'; })()" % idx)


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song()
        s = await h.ev(STATE)
        chk('menu zavřené', not s['open'])
        chk('bez starých tlačítek na liště', s['open'] is False)

        # otevřít tlačítkem Vycentrovat
        r = await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));if(!b)return 'chybi';b.click();return 'ok'})()")
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        print('menu:', s)
        chk('tlačítko otevřelo menu', r == 'ok' and s['open'])
        chk('tři skupiny', len(s['groups']) == 3, str([g['head'] for g in s['groups']]))
        chk('pojmenování skupin', [g['head'] for g in s['groups']] ==
            ['Tato stránka', 'Celá skladba', 'Rám — ořez okrajů'], str([g['head'] for g in s['groups']]))
        chk('všechny koše neaktivní', all(g['trashDisabled'] for g in s['groups']))

        # Rám
        print('rám:', await click_text(h, 'Rám'))
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('po rámu:', s['groups'], 'vb', s['vb'])
        chk('rám zapnutý', not s['vb'].startswith('0 0'))
        chk('rám: koš aktivní', s['groups'][2]['trashDisabled'] is False)
        chk('rám: stav zapnutý', s['groups'][2]['state'] == 'zapnutý')

        # uložit stránku
        print('uložit stránku:', await click_text(h, 'Uložit'))
        await asyncio.sleep(1.2)
        s = await h.ev(STATE)
        print('po uložení stránky:', s['groups'])
        chk('stránka uložena', s['groups'][0]['state'] == 'uloženo')

        # smazat stránku → zmizí i rám (byl součástí)
        print('koš stránky:', await click_trash(h, 0))
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('po smazání stránky:', s['groups'], 'vb', s['vb'])
        chk('stránka smazána', s['groups'][0]['state'] == 'neuloženo')
        chk('rám zrušen se stránkou', s['vb'].startswith('0 0'), s['vb'])

        # globál
        r = await h.ev("(()=>{const g=document.querySelectorAll('.prefs-group')[1];const b=[...g.querySelectorAll('button')].find(x=>x.textContent.trim()==='Uložit');b&&b.click();return 'ok'})()")
        await asyncio.sleep(1.2)
        s = await h.ev(STATE)
        chk('skladba uložena', s['groups'][1]['state'] == 'uloženo')
        print('koš skladby:', await click_trash(h, 1))
        await asyncio.sleep(1.5)
        s = await h.ev(STATE)
        chk('skladba smazána', s['groups'][1]['state'] == 'neuloženo')
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
