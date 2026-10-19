#!/usr/bin/env python3
"""Sonda rámu: po ořezu se stránka MUSÍ vejít do čtecí plochy (i když byla
předtím přiblížená) a obsah musí zůstat uvnitř canvasu. Navíc hlídá nový
design menu Zobrazení: řada ikon (stránka / hvězda / ořez / střed), doleva."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

# Strana 595x842, osnovy v okrajích 50..545 x 110..750 — je co ořezat.
CONTENT = []
for s in range(11):
    y = 110 + s * 58
    for i in range(5):
        CONTENT.append(f"0.6 w 50 {y + i * 4} m 545 {y + i * 4} l S")
# Úzký svislý sloupec — výřez je vysoký a fit-na-šířku by přetekl displej.
NARROW = []
for s in range(11):
    y = 110 + s * 58
    for i in range(5):
        NARROW.append(f"0.6 w 150 {y + i * 4} m 400 {y + i * 4} l S")

STATE = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  const cr = c.getBoundingClientRect();
  const v = document.querySelector('.viewer').getBoundingClientRect();
  const bar = document.querySelector('.top-bar').getBoundingClientRect();
  const svg = document.querySelector('.annot-layer');
  const ctx = c.getContext('2d');
  const W = c.width, H = c.height;
  const d = ctx.getImageData(0, 0, W, H).data;
  let x0 = W, x1 = -1, y0 = H, y1 = -1;
  for (let y = 0; y < H; y += 2) {
    for (let x = 0; x < W; x += 2) {
      const i = (y * W + x) * 4;
      if (d[i] < 240 || d[i+1] < 240 || d[i+2] < 240) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  }
  return {
    cw: Math.round(cr.width), ch: Math.round(cr.height),
    cleft: Math.round(cr.left), ctop: Math.round(cr.top),
    vw: Math.round(v.width), vh: Math.round(v.height),
    barBottom: Math.round(bar.bottom),
    vb: svg.getAttribute('viewBox'),
    ink: {x0, x1, y0, y1, W, H},
    win: {w: innerWidth, h: innerHeight},
    scale: getComputedStyle(document.querySelector('.stage')).transform,
  };
})()
"""

DESIGN = r"""
(() => {
  const p = document.querySelector('.prefs-panel');
  if (!p) return null;
  const rows = [...p.querySelectorAll('.prefs-row')];
  const btns = [...p.querySelectorAll('.prefs-row .zp-btn.prefs-icon')];
  const pr = p.getBoundingClientRect();
  return {
    rows: rows.length,
    icons: btns.map(b => ({title: b.title, hasSvg: !!b.querySelector('svg'),
                           left: Math.round(b.getBoundingClientRect().left)})),
    textUlozit: p.textContent.includes('Uložit'),
    panelLeft: Math.round(pr.left), panelRight: Math.round(pr.right),
  };
})()
"""


def make_music_pdf(path="/tmp/noty-music-fixture.pdf", lines=None):
    stream = "\n".join(CONTENT if lines is None else lines)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Contents 4 0 R /Resources << >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"]
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


async def click_title(h, scope, prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll(%s)]"
        ".find(x => (x.title||'').startsWith(%s));"
        "if (!b) return 'chybi'; b.click(); return 'ok'; })()"
        % (repr(scope), repr(prefix)))


async def scenario(h, chk, pdf, label):
    await h.open()
    await h.open_song(pdf=pdf, pages=1)
    await asyncio.sleep(0.5)
    print(f'--- {label} --- bez rámu:', await h.ev(STATE))

    # menu Zobrazení
    await click_title(h, '.tb-btn', 'Vycentrovat a preference')
    await asyncio.sleep(0.5)
    d = await h.ev(DESIGN)
    print('DESIGN:', d)
    chk(f'{label}: menu se otevřelo', bool(d))
    chk(f'{label}: jedna řada se čtyřmi ikonami', d and d['rows'] >= 1 and len(d['icons']) == 4,
        str(d and d['icons']))
    chk(f'{label}: ikony mají SVG a správné popisky',
        d and all(i['hasSvg'] for i in d['icons']) and
        [i['title'] for i in d['icons']] == [
            'Uložit zobrazení této stránky', 'Uložit zobrazení celé skladby',
            'Oříznout okraje (rám)', 'Vycentrovat na uložené zobrazení'],
        str(d and [i['title'] for i in d['icons']]))
    chk(f'{label}: žádné textové „Uložit“', d and not d['textUlozit'])
    chk(f'{label}: ikony jsou v jedné řadě zarovnané doleva',
        d and min(i['left'] for i in d['icons']) - d['panelLeft'] < 75,
        str(d and [(i['left'], d['panelLeft']) for i in d['icons']]))

    # přiblížit na 120 % — ořez to musí srovnat na fit
    await click_title(h, '.tb-btn', 'Zvětšení a posun')
    await asyncio.sleep(0.3)
    for _ in range(2):
        await h.ev("(()=>{const b=[...document.querySelectorAll('.zoom-panel button')]"
                   ".find(x=>x.textContent.trim()==='+10');b&&b.click()})()")
        await asyncio.sleep(0.25)
    await click_title(h, '.tb-btn', 'Zvětšení a posun')
    print('zoom před rámem:', await h.ev(
        "[...document.querySelectorAll('.tb-btn')].find(x=>x.title==='Zvětšení a posun')"
        ".textContent.trim()"))

    # otevřít menu znovu a oříznout
    await click_title(h, '.tb-btn', 'Vycentrovat a preference')
    await asyncio.sleep(0.3)
    r = await click_title(h, '.prefs-panel .prefs-icon', 'Oříznout')
    print('klik ořez:', r)
    await asyncio.sleep(2.5)
    s = await h.ev(STATE)
    print('S RÁMEM:', s)
    print('zoom po rámu:', await h.ev(
        "[...document.querySelectorAll('.tb-btn')].find(x=>x.title==='Zvětšení a posun')"
        ".textContent.trim()"))

    chk(f'{label}: rám se zapnul', not s['vb'].startswith('0 0'), s['vb'])
    chk(f'{label}: canvas není širší než čtecí plocha', s['cw'] <= s['vw'],
        f"canvas {s['cw']} vs viewer {s['vw']}")
    chk(f'{label}: canvas nezačíná nad lištou', s['ctop'] >= s['barBottom'] - 1,
        f"top {s['ctop']} vs bar {s['barBottom']}")
    chk(f'{label}: canvas se vejde na výšku', s['ctop'] + s['ch'] <= s['win']['h'] + 1,
        f"bottom {s['ctop'] + s['ch']} vs win {s['win']['h']}")
    chk(f'{label}: canvas se vejde na šířku (vlevo)', s['cleft'] >= -1, str(s['cleft']))
    chk(f'{label}: canvas se vejde na šířku (vpravo)',
        s['cleft'] + s['cw'] <= s['win']['w'] + 1,
        f"right {s['cleft'] + s['cw']} vs win {s['win']['w']}")
    chk(f'{label}: žádné přeškálování stage',
        s['scale'] in ('none', 'matrix(1, 0, 0, 1, 0, 0)'), s['scale'])
    ink = s['ink']
    chk(f'{label}: obsah není odstřižený',
        ink['x0'] > 2 and ink['x1'] < ink['W'] - 3 and
        ink['y0'] > 2 and ink['y1'] < ink['H'] - 3, str(ink))
    dl, dr = ink['x0'] / ink['W'], 1 - ink['x1'] / ink['W']
    chk(f'{label}: obsah je v canvasu vodorovně vycentrovaný', abs(dl - dr) < 0.06,
        f"levý {dl:.3f} pravý {dr:.3f}")


async def main():
    chk = Check()
    async with Harness() as h:
        await scenario(h, chk, make_music_pdf("/tmp/noty-wide.pdf", CONTENT), 'široký obsah')
        await scenario(h, chk, make_music_pdf("/tmp/noty-narrow.pdf", NARROW), 'úzký obsah')
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
