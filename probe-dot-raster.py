import asyncio, importlib.util, json, os
_HERE = "/home/martin_fabian/noty-app"
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)

JS = r"""
(async () => {
  const mod = await import('/src/annotRaster.js');
  // stejná pravidla, jaká používá Prohlížec při vypalování
  const NOTE = {
    ctvrt_h: { cp: 0xE1D5, adv: 0.332, box: [0, 0.332, -0.141, 0.875], dotAt: [0.37, 0] },
    poml_pul: { cp: 0xE4E4, adv: 0.283, box: [0, 0.282, -0.002, 0.142], dotAt: [0.34, 0.267] },
  };
  const key = (it) => it.text;
  const displayText = (it) => String.fromCodePoint(NOTE[key(it)].cp);
  const noteDot = (it) => {
    if (!it.dot) return null;
    const n = NOTE[key(it)];
    const dx = it.x + n.dotAt[0] * it.size, dy = it.y - n.dotAt[1] * it.size;
    const sx = it.flipX ? 2 * it.x - dx : dx;
    // zrcadlení svisle u pomlky — v canvasu ho dělá transform, tady ho napodobíme
    return { cx: sx, cy: dy, r: 0.1 * it.size };
  };
  const canvas = document.createElement('canvas');
  const items = [
    { id: 'a', tool: 'note', text: 'ctvrt_h', x: 120, y: 120, size: 60, color: '#000000',
      dot: true, flipX: false, flipY: false },
    { id: 'b', tool: 'note', text: 'ctvrt_h', x: 120, y: 260, size: 60, color: '#000000',
      dot: false, flipX: false, flipY: false },
    { id: 'c', tool: 'note', text: 'poml_pul', x: 320, y: 120, size: 60, color: '#000000',
      dot: true, flipX: false, flipY: false },
  ];
  await mod.ensureNotationFont(60);
  mod.renderAnnotationLayer(canvas, items, {
    w: 500, h: 400, scale: 1,
    displayText, noteStroke: () => 0, noteFlipY: () => false, noteDot,
  });
  const ctx = canvas.getContext('2d');
  // kde je tmavý inkoust: sloupce a řádky
  const darkCols = [], darkRows = [];
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const hit = (x, y) => img[(y * canvas.width + x) * 4 + 3] > 60;
  let count = 0;
  for (let x = 0; x < canvas.width; x++) for (let y = 0; y < canvas.height; y++) if (hit(x, y)) count++;
  // tečka noty A: očekáváme kolem x = 120 + 0.37*60 = 142, y = 120
  const boxDark = (x0, y0, x1, y1) => {
    let n = 0;
    for (let x = x0; x < x1; x++) for (let y = y0; y < y1; y++) if (hit(x, y)) n++;
    return n;
  };
  return {
    total: count,
    dotA: boxDark(135, 112, 152, 129),      // tečka u čtvrťové noty s tečkou
    noDotB: boxDark(135, 252, 152, 269),    // stejné místo u noty BEZ tečky
    dotC: boxDark(335, 95, 352, 112),       // tečka nad pomlkou (dy 0.267*60 = 16 px nahoru)
    png: canvas.toDataURL().length,
  };
})()
"""

async def main():
    async with m.Harness() as h:
        print(await h.ev(JS, await_promise=True))

asyncio.run(main())
