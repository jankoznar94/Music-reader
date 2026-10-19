#!/usr/bin/env python3
"""Sonda: aktualizace JEN na tlačítko (to stávající vpravo nahoře v knihovně).
1) na serveru je nová verze → appka se sama NEreloaduje,
2) tlačítko v topbaru ji načte,
3) žádné druhé tlačítko „Aktualizovat“ v appce není."""
import asyncio
import importlib.util
import os
import re
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
    if '__buildTag' in s:
        s = re.sub(r"window\.__buildTag = '[^']*';", f"window.__buildTag = '{tag}';", s)
    else:
        s = s.replace("import { checkForUpdate } from './update';",
                      "import { checkForUpdate } from './update';\nwindow.__buildTag = '%s';" % tag)
    open(p, 'w').write(s)
    subprocess.run(['npm', 'run', 'build'], cwd=_HERE, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def main():
    chk = Check()
    build('t1')
    async with Harness(URL) as h:
        await h.open()
        await asyncio.sleep(3)
        tag = await h.ev('window.__buildTag')
        print('úvodní verze:', tag, await h.ev('window.__updateState'))
        chk('běží první verze', tag == 't1', str(tag))
        chk('v appce není druhé plovoucí tlačítko',
            await h.ev("!document.querySelector('.update-pill')"), 'update-pill')

        await h.ev('window.__noReloadMark = 12345')
        build('t2')
        await asyncio.sleep(1.5)
        await h.ev('window.__checkUpdate()', await_promise=True)
        await asyncio.sleep(1.0)
        state = await h.ev('window.__updateState')
        mark = await h.ev('window.__noReloadMark')
        print('po nasazení:', state, 'značka:', mark)
        chk('appka se sama neobnovila', mark == 12345, str(mark))
        chk('zjistila novou verzi', str(state).startswith('available:'), str(state))

        await h.ev("document.querySelector('.update-btn').click()")
        # toast žije jen 2,5 s → čteme ho hned, jak se appka po reloadu nahodí
        toast = ''
        for _ in range(24):
            await asyncio.sleep(0.25)
            t = await h.ev("(document.body.innerText.match(/Aktualizace proběhla[^\\n]*/)||[''])[0]")
            if t:
                toast = t
                break
        await asyncio.sleep(0.5)
        tag = await h.ev('window.__buildTag')
        print('po kliknutí na tlačítko:', tag, '| toast:', toast)
        chk('tlačítko v topbaru načetlo novou verzi', tag == 't2', str(tag))
        chk('po aktualizaci se ukázalo potvrzení', 'Aktualizace' in toast, toast)
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
