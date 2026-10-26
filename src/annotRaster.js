// src/annotRaster.js — vykreslení anotační vrstvy do canvasu (pro vypálení do PDF)
//
// Anotace jsou uložené ve "ref px" — ve stejné soustavě, v jaké je kreslí SVG
// vrstva v Prohlížeči. Aby vypálený výsledek vypadal PŘESNĚ jako na obrazovce,
// kreslí se stejnými pravidly (kotvy, tloušťky, průhlednosti) jen jiným
// vykreslovačem. Vzory (glyfy dynamiky/not/značek, rámečky textu) dodává
// Prohlížeč přes callbacky — mapování klíč → glyf tak zůstává na jednom místě.

// Kolik rastrových px připadá na 1 ref px. 3× odpovídá ~300 dpi při tisku A4.
// (Víc = ostřejší vypálení, ale výrazně větší PDF; 3× je kompromis.)
export const ANNOT_SCALE = 3;

// Průhlednost zvýrazňovače je v aplikaci daná CSS (`.annot-layer .hl`), ne
// atributem — vypálení musí dopadnout stejně, proto stejná konstanta.
const HL_ALPHA = 0.9;

function roundRect(ctx, r) {
  ctx.beginPath();
  ctx.rect(r.x, r.y, r.width, r.height);
  ctx.stroke();
}

/**
 * Vykreslí anotace jedné stránky do canvasu.
 *
 * @param {HTMLCanvasElement} canvas cílový canvas (velikost se nastaví)
 * @param {Array} items anotace stránky (souřadnice v ref px)
 * @param {Object} opts
 *   w, h          rozměry ref soustavy (refW/refH)
 *   scale         rastrové px na ref px (default ANNOT_SCALE)
 *   displayText   (it) => znak glyfu pro dynamiku/značku/notu
 *   borderRects   (it) => [{x,y,width,height,dash}] rámečky textové anotace
 *   noteStroke    (it) => tloušťka tahu noty
 */
export function renderAnnotationLayer(canvas, items, opts) {
  const w = Math.max(1, Math.round(opts.w));
  const h = Math.max(1, Math.round(opts.h));
  const scale = opts.scale || ANNOT_SCALE;
  const displayText = opts.displayText || ((it) => it.text || '');
  const borderRects = opts.borderRects || (() => []);
  const noteStroke = opts.noteStroke || (() => 0);
  // Zrcadlení noty ve svislé ose NENÍ jen geometrie: u not, které mají
  // v fontu obrácenou variantu (NOTE_DIR_SWAP), je směr už v glyfu a flipY
  // se geometricky neprojeví. Rozhoduje o tom Prohlížeč → callback.
  const noteFlipY = opts.noteFlipY || ((it) => !!it.flipY);

  canvas.width = Math.max(1, Math.round(w * scale));
  canvas.height = Math.max(1, Math.round(h * scale));
  const ctx = canvas.getContext('2d');
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, w, h);

  for (const it of items || []) {
    if (!it) continue;
    const alpha = it.opacity != null ? it.opacity : 1;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (it.tool === 'pencil') {
      // Tah perem: body jako lomená čára; jediný bod = tečka o průměru tahu.
      const pts = it.points || [];
      ctx.strokeStyle = it.color;
      ctx.fillStyle = it.color;
      ctx.lineWidth = it.width || 2;
      if (pts.length === 1) {
        const r = Math.max(1.5, (it.width || 2) / 2);
        ctx.beginPath();
        ctx.arc(pts[0].x, pts[0].y, r, 0, Math.PI * 2);
        ctx.fill();
      } else if (pts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
        ctx.stroke();
      }
    } else if (it.tool === 'highlighter') {
      // Zvýrazňovač = multiply, aby noty pod ním zůstaly čitelné (jako v SVG).
      ctx.globalCompositeOperation = 'multiply';
      ctx.globalAlpha = alpha * HL_ALPHA;
      ctx.fillStyle = it.color;
      if (Array.isArray(it.poly) && it.poly.length >= 3) {
        ctx.beginPath();
        ctx.moveTo(it.poly[0].x, it.poly[0].y);
        for (let i = 1; i < it.poly.length; i++) ctx.lineTo(it.poly[i].x, it.poly[i].y);
        ctx.closePath();
        ctx.fill();
      } else if (it.x1 != null && it.x2 != null) {
        ctx.fillRect(Math.min(it.x1, it.x2), Math.min(it.y1, it.y2),
          Math.abs(it.x2 - it.x1), Math.abs(it.y2 - it.y1));
      }
    } else if (it.tool === 'text') {
      // Rámeček (volitelný) pak text; účaří je v it.y, stejně jako v SVG.
      ctx.strokeStyle = it.color;
      ctx.lineWidth = 1.5;
      if (it.border) {
        for (const r of borderRects(it)) {
          ctx.setLineDash(r.dash ? [6, 4] : []);
          roundRect(ctx, r);
        }
        ctx.setLineDash([]);
      }
      ctx.fillStyle = it.color;
      ctx.font = `${it.size || 20}px system-ui, sans-serif`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(it.text || '', it.x, it.y);
    } else if (it.tool === 'dynamic' || it.tool === 'mark' || it.tool === 'note') {
      const ch = displayText(it);
      if (!ch) { ctx.restore(); continue; }
      ctx.fillStyle = it.color;
      ctx.strokeStyle = it.color;
      ctx.font = `${it.size || 20}px 'NotyDyn', serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      if (it.tool === 'note' && (it.flipX || noteFlipY(it))) {
        // Zrcadlení noty se dělá kolem jejího ukotvení (střed/účaří).
        const sx = it.flipX ? -1 : 1;
        const sy = noteFlipY(it) ? -1 : 1;
        ctx.translate(it.x, it.y);
        ctx.scale(sx, sy);
        ctx.translate(-it.x, -it.y);
      }
      if (it.tool === 'note') {
        // Nota se kreslí TAHEM pod výplní (v SVG paint-order: stroke) — stejný
        // vzhled nožičky, jen silnější obrys.
        const sw = noteStroke(it);
        if (sw > 0) {
          ctx.lineWidth = sw;
          ctx.strokeText(ch, it.x, it.y);
        }
      }
      ctx.fillText(ch, it.x, it.y);
    } else if (it.tool === 'crescendo' || it.tool === 'decrescendo') {
      ctx.strokeStyle = it.color;
      ctx.lineWidth = it.width || 2;
      ctx.beginPath();
      ctx.moveTo(it.x2, it.y2);
      ctx.lineTo(it.x1, it.y1);
      ctx.lineTo(it.x3, it.y3);
      ctx.stroke();
    }

    ctx.restore();
  }
  return canvas;
}

/**
 * Počká, až bude notační font opravdu načtený — bez toho by se glyfy not
 * vypálily prázdné (canvas kreslí fallback fontem, který SMuFL znaky nemá).
 */
export async function ensureNotationFont(sizePx = 64) {
  if (!document.fonts || !document.fonts.load) return;
  try {
    await document.fonts.load(`${sizePx}px 'NotyDyn'`);
    await document.fonts.ready;
  } catch { /* font nemusí být potřeba (žádné noty) */ }
}
