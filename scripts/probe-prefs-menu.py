#!/usr/bin/env python3
"""Sonda menu Zobrazení: řada ikon (stránka / hvězda / ořez / střed) doleva,
ukládání i mazání každé preference přes vlastní koš."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

_s2 = importlib.util.spec_from_file_location(
    "pg", os.path.join(_HERE, "scripts", "probe-frame-geometry.py"))
pg = importlib.util.module_from_spec(_s2)
_s2.loader.exec_module(pg)

STATE = r"""
(() => {
  const p = document.querySelector('.prefs-panel');
  if (!p) return {open: false};
  const icon = (prefix) => {
    const b = [...p.querySelectorAll('.prefs-icon')].find(x => (x.title || '').startsWith(prefix));
    return b ? {on: b.classList.contains('on'), fill: b.querySelector('svg').getAttribute('fill')} : null;
  };
  return {
    open: true,
    page: icon('Uložit zobrazení této stránky'),
    song: icon('Uložit zobrazení celé skladby'),
    frame: icon('Oříznout'),
    trash: [...p.querySelectorAll('.prefs-trash-btn span')].map(s => s.textContent.trim()),
    vb: document.querySelector('.annot-layer').getAttribute('viewBox'),
  };
})()
"""


async def click(h, scope, prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll(%s)]"
        ".find(x => (x.title||'').startsWith(%s));"
        "if (!b) return 'chybi'; b.click(); return 'ok'; })()"
        % (repr(scope), repr(prefix)))


async def open_menu(h):
    await click(h, '.tb-btn', 'Vycentrovat a preference')
    await asyncio.sleep(0.4)


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=pg.make_music_pdf("/tmp/noty-prefs.pdf"), pages=1)
        await open_menu(h)
        s = await h.ev(STATE)
        print('START:', s)
        chk('menu otevřené', s['open'])
        chk('start: nic není uložené',
            not s['page']['on'] and not s['song']['on'] and not s['trash'])

        # stránka
        await click(h, '.prefs-panel .prefs-icon', 'Uložit zobrazení této stránky')
        await asyncio.sleep(0.6)
        s = await h.ev(STATE)
        chk('stránka: ikona svítí', s['page']['on'], str(s['page']))
        chk('stránka: koš přibyl', s['trash'] == ['stránka'], str(s['trash']))

        # skladba
        await click(h, '.prefs-panel .prefs-icon', 'Uložit zobrazení celé skladby')
        await asyncio.sleep(0.6)
        s = await h.ev(STATE)
        chk('skladba: ikona svítí', s['song']['on'], str(s['song']))
        chk('skladba: koš přibyl', s['trash'] == ['stránka', 'skladba'], str(s['trash']))

        # rám
        await click(h, '.prefs-panel .prefs-icon', 'Oříznout')
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('PO RÁMU:', s)
        chk('rám: ikona svítí', s['frame']['on'], str(s['frame']))
        chk('rám: viewBox není celá stránka', not s['vb'].startswith('0 0'), s['vb'])
        chk('rám: koš přibyl', 'rám' in s['trash'], str(s['trash']))

        # mazání: rám
        await click(h, '.prefs-panel .prefs-trash-btn', 'Zrušit rám')
        await asyncio.sleep(2.0)
        s = await h.ev(STATE)
        print('PO SMAZÁNÍ RÁMU:', s)
        chk('rám smazán: viewBox celá stránka', s['vb'].startswith('0 0'), s['vb'])
        chk('rám smazán: koš zmizel', 'rám' not in s['trash'], str(s['trash']))

        # mazání: stránka, skladba
        await click(h, '.prefs-panel .prefs-trash-btn', 'Smazat uložené zobrazení této stránky')
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('stránka smazána', not s['page']['on'] and 'stránka' not in s['trash'], str(s))
        await click(h, '.prefs-panel .prefs-trash-btn', 'Smazat výchozí zobrazení celé skladby')
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('skladba smazána', not s['song']['on'] and s['trash'] == [], str(s))

        # střed = vycentrování (nesmí otevřít/zavřít nic jiného)
        r = await click(h, '.prefs-panel .prefs-icon', 'Vycentrovat na uložené zobrazení')
        await asyncio.sleep(0.8)
        chk('tlačítko středu funguje', r == 'ok' and (await h.ev(STATE))['open'])
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
