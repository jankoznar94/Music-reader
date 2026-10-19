#!/usr/bin/env python3
"""Sonda menu Zobrazení: ikony (stránka / hvězda / ořez / střed) doleva,
koše jako IKONY v rozích, rám = globální pro celou skladbu,
priorita: preference stránky > preference skladby > rám."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

LINES = []
for s in range(11):
    y = 110 + s * 58
    for i in range(5):
        LINES.append(f"0.6 w 50 {y + i * 4} m 545 {y + i * 4} l S")


def make_pdf(path, pages=3):
    stream = "\n".join(LINES)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Count {pages} /Kids [{' '.join(f'{3+i} 0 R' for i in range(pages))}] >>"]
    for i in range(pages):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Contents {3 + pages + i} 0 R /Resources << >> >>")
    for _ in range(pages):
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    with open(path, "w", encoding="latin-1") as fh:
        fh.write(out)
    return path


STATE = r"""
(() => {
  const p = document.querySelector('.prefs-panel');
  if (!p) return {open: false};
  const icon = (prefix) => {
    const b = [...p.querySelectorAll('.prefs-icon')].find(x => (x.title || '').startsWith(prefix));
    return b ? b.classList.contains('on') : null;
  };
  const badges = [...p.querySelectorAll('.prefs-trash-badge')].map(b => b.title);
  const texts = [...p.querySelectorAll('.prefs-row *')]
    .filter(e => e.children.length === 0 && e.textContent.trim())
    .map(e => e.textContent.trim()).filter(t => t !== '⠿');
  return {
    open: true,
    page: icon('Uložit zobrazení této stránky'),
    song: icon('Uložit zobrazení celé skladby'),
    frame: icon('Oříznout okraje'),
    badges, texts,
    vb: document.querySelector('.annot-layer').getAttribute('viewBox'),
    pageNo: document.querySelector('.tb-page').textContent.trim(),
  };
})()
"""


async def click(h, scope, prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll(%s)]"
        ".find(x => (x.title||'').startsWith(%s));"
        "if (!b) return 'chybi'; b.click(); return 'ok'; })()"
        % (repr(scope), repr(prefix)))


async def menu(h):
    if not await h.ev("!!document.querySelector('.prefs-panel')"):
        await click(h, '.tb-btn', 'Vycentrovat a preference')
        await asyncio.sleep(0.4)


async def close_menu(h):
    if await h.ev("!!document.querySelector('.prefs-panel')"):
        await click(h, '.tb-btn', 'Vycentrovat a preference')
        await asyncio.sleep(0.3)


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=make_pdf('/tmp/noty-prefs-3p.pdf', 3), pages=3)

        await menu(h)
        s = await h.ev(STATE)
        print('START:', s)
        chk('menu otevřené', s['open'])
        chk('bez uložených preferencí nejsou koše', s['badges'] == [], str(s['badges']))
        chk('v panelu žádný text (jen ikony)', s['texts'] == [], str(s['texts']))

        # 1) rám je GLOBÁLNÍ: zapnout na 1. stránce a ověřit na 2.
        await click(h, '.prefs-panel .prefs-icon', 'Oříznout okraje')
        await asyncio.sleep(2.2)
        s = await h.ev(STATE)
        print('PO RÁMU (str. 1):', s['vb'], s['pageNo'])
        chk('str. 1: rám zapnutý', not s['vb'].startswith('0 0'), s['vb'])
        chk('rám se neukládá jako stránková preference', s['badges'] == [], str(s['badges']))

        await close_menu(h)
        await h.goto(2)
        await asyncio.sleep(1.6)
        vb2 = await h.ev("document.querySelector('.annot-layer').getAttribute('viewBox')")
        print('str. 2 viewBox:', vb2)
        chk('str. 2: rám platí taky (globální)', not vb2.startswith('0 0'), vb2)

        # 2) priorita: stránková preference (bez rámu) přebije globální rám.
        # Nejdřív rám vypnout (na 2. stránce), teprve pak uložit její zobrazení —
        # preference si pamatuje stav v okamžiku uložení.
        await menu(h)
        await click(h, '.prefs-panel .prefs-icon', 'Oříznout okraje')   # vypnout
        await asyncio.sleep(1.8)
        await click(h, '.prefs-panel .prefs-icon', 'Uložit zobrazení této stránky')
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('str. 2: koš stránky je ikona s popisem',
            s['badges'] == ['Smazat uložené zobrazení této stránky'], str(s['badges']))

        # rám zapnout z 1. stránky → str. 2 má vlastní preferenci (bez rámu)
        await close_menu(h)
        await h.goto(1)
        await asyncio.sleep(1.4)
        await menu(h)
        await click(h, '.prefs-panel .prefs-icon', 'Oříznout okraje')   # zapnout
        await asyncio.sleep(2.2)
        await close_menu(h)
        await h.goto(2)
        await asyncio.sleep(1.6)
        vb2 = await h.ev("document.querySelector('.annot-layer').getAttribute('viewBox')")
        print('str. 2 po globálním rámu:', vb2)
        chk('str. 2: stránková preference má přednost (bez rámu)',
            vb2.startswith('0 0'), vb2)

        # 3) smazání stránkové preference → vrátí se globální rám
        await menu(h)
        await click(h, '.prefs-panel .prefs-trash-badge', 'Smazat uložené zobrazení této stránky')
        await asyncio.sleep(2.0)
        s = await h.ev(STATE)
        print('po smazání stránkové preference:', s['vb'], s['badges'])
        chk('str. 2: po smazání preference platí globální rám',
            not s['vb'].startswith('0 0'), s['vb'])
        chk('koš zmizel', s['badges'] == [], str(s['badges']))

        # 4) globální preference + koš
        await click(h, '.prefs-panel .prefs-icon', 'Uložit zobrazení celé skladby')
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('skladba: ikona svítí a má koš',
            s['song'] and s['badges'] == ['Smazat výchozí zobrazení celé skladby'],
            str(s['badges']))
        await click(h, '.prefs-panel .prefs-trash-badge', 'Smazat výchozí zobrazení celé skladby')
        await asyncio.sleep(1.2)
        s = await h.ev(STATE)
        chk('skladba: smazáno', not s['song'] and s['badges'] == [], str(s))

        # 5) rám zůstává zapnutý i po smazání preference skladby
        chk('rám zůstal zapnutý', not s['vb'].startswith('0 0'), s['vb'])
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
