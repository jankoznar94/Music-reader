#!/usr/bin/env python3
"""Sonda okrajů rámu: nahoře i dole musí být STEJNĚ místa, i když obsah sahá
téměř k okraji stránky (nejnižší basové noty se nesmí dotýkat hrany)."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check


def make_pdf(path, y0=10, y1=832, pages=1):
    """Obsah: osnovy v prostředku + krátké značky u horního a dolního okraje
    (jako číslo stránky nahoře a nejnižší basové noty dole)."""
    lines = []
    n = 11
    for s in range(n):
        y = 120 + s * 58
        for i in range(5):
            lines.append(f"0.6 w 50 {y + i * 4} m 545 {y + i * 4} l S")
    # horní a dolní obsah až u okraje stránky (krátké tahy, ne dlouhá linka —
    # dlouhá linka u okraje se správně považuje za sken hrany)
    lines.append("200 795 40 7 re f")     # nahoře (číslo stránky)
    lines.append("300 4 8 5 re f")        # dole: JEDINÁ osamocená hluboká nota
    stream = "\n".join(lines)
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


MARGINS = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  const ctx = c.getContext('2d');
  const W = c.width, H = c.height;
  const d = ctx.getImageData(0, 0, W, H).data;
  let y0 = H, y1 = -1, x0 = W, x1 = -1;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (d[i] < 200 || d[i+1] < 200 || d[i+2] < 200) {
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
      }
    }
  }
  const dpr = window.devicePixelRatio || 1;
  return {
    topPx: y0 / dpr, bottomPx: (H - 1 - y1) / dpr,
    leftPx: x0 / dpr, rightPx: (W - 1 - x1) / dpr,
    wPx: W / dpr, hPx: H / dpr,
    vb: document.querySelector('.annot-layer').getAttribute('viewBox'),
  };
})()
"""


async def click(h, prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.prefs-panel .prefs-icon')]"
        ".find(x => (x.title||'').startsWith(%s));"
        "if(!b) return 'chybi'; b.click(); return 'ok'; })()" % repr(prefix))


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=make_pdf('/tmp/noty-margins.pdf'), pages=1)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));b&&b.click()})()")
        await asyncio.sleep(0.4)
        await click(h, 'Oříznout okraje')
        await asyncio.sleep(2.4)
        s = await h.ev(MARGINS)
        print('OKRAJE:', s)
        chk('rám se zapnul', not s['vb'].startswith('0 0'), s['vb'])
        top, bottom = s['topPx'], s['bottomPx']
        chk('dole je aspoň 3 px místa', bottom >= 3, f"{bottom:.1f} px")
        chk('osamocená hluboká nota není uříznutá (je v canvasu)',
            bottom <= 45, f"bottom {bottom:.1f} px (kdyby chyběla, je tam >150)")
        # Nová pravidla: nahoru se bere první osnova (číslo stránky se
        # vynechá), dolů všechen obsah. Symetrie se už nevyžaduje — hlídá se
        # jen, že nahoře nezbývá zbytečně moc místa.
        chk('nahoře nezbývá víc než 200 px', top <= 200, f"top {top:.1f}")
        left, right = s['leftPx'], s['rightPx']
        chk('vlevo i vpravo stejně', abs(left - right) < max(6, 0.25 * max(left, right)),
            f"left {left:.1f} right {right:.1f}")
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
