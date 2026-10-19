#!/usr/bin/env python3
"""Sonda: aktualizace JEN na tlačítko.
1) appka běží na staré verzi — nic se samo nenačítá,
2) na serveru je nová verze — po otevření se appka NEreloaduje, jen se objeví
   tlačítko „Aktualizovat“,
3) kliknutí tlačítka načte novou verzi."""
import asyncio
import importlib.util
import os
import subprocess

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

URL = 'http://localhost:4173/'


def build(tag):
    p = os.path.join(_HERE, 'src/main.js')
    s = open(p).read()
    import re
    s = re.sub(r"window\.__buildTag = '[^']*';", f"window.__buildTag = '{tag}';", s)
    open(p, 'w').write(s)
    subprocess.run(['npm', 'run', 'build'], cwd=_HERE, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def main():
    chk = Check()
    async with Harness(URL) as h:
        await h.open()
        await asyncio.sleep(3)
        tag = await h.ev('window.__buildTag')
        state = await h.ev('window.__updateState')
        print('úvodní verze:', tag, state)
        chk('běží první verze', tag == 't1', str(tag))

        # Nová verze na serveru (jako po deployi), stránka se nesmí sama obnovit.
        await h.ev('window.__noReloadMark = 12345')
        build('t2')
        await asyncio.sleep(1.5)
        await h.ev('window.__checkUpdate()', await_promise=True)
        await asyncio.sleep(1.0)
        state = await h.ev('window.__updateState')
        pill = await h.ev("!!document.querySelector('.update-pill')")
        mark = await h.ev('window.__noReloadMark')
        tag = await h.ev('window.__buildTag')
        print('po nasazení nové verze:', state, 'tlačítko:', pill, 'značka:', mark)
        chk('appka se sama neobnovila', mark == 12345 and tag == 't1', f"{mark} {tag}")
        chk('zjistila novou verzi', str(state).startswith('available:'), str(state))
        chk('objevilo se tlačítko Aktualizovat', pill is True, str(pill))

        # Klik na tlačítko → nová verze
        await h.ev("document.querySelector('.update-pill').click()")
        await asyncio.sleep(4.0)
        tag = await h.ev('window.__buildTag')
        pill = await h.ev("!!document.querySelector('.update-pill')")
        print('po kliknutí:', tag, 'tlačítko:', pill)
        chk('tlačítko načetlo novou verzi', tag == 't2', str(tag))
        chk('tlačítko po aktualizaci zmizelo', pill is False, str(pill))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
