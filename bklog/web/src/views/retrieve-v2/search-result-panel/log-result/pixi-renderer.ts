/**
 * Pixi.js renderer for Full Row Viewer.
 *
 * Progressive enhancement:
 * 1. Static fallback renders immediately (native browser)
 * 2. When PIXI is ready, upgrade to GPU-accelerated rendering
 */


/** Lazy-load PIXI, returns { Application, Container, Text, Graphics, TextStyle, FederatedPointerEvent } or throws */
export async function lazyLoadPixi(): Promise<any> {
  const PIXI = await import(
    /* webpackChunkName: "retrieve-pixi-renderer" */
    'pixi.js'
  );
  return PIXI;
}

/** Estimate character-pixel widths cheaply without creating PIXI App */
export function measureTextPixelWidth(text: string, pixelPerChar: number = 8): number {
  return text.length * pixelPerChar;
}

export interface PixiRowRenderOptions {
  canvas: HTMLCanvasElement;
  rows: Array<{ text: string; isMark: boolean }>;
  highlightKeywords?: string[];
  fontSize?: number;
  lineHeight?: number;
  charWidth?: number;
  onHighlightClick?(charIndex: number, text: string): void;
}

const CHAR_WIDTH = 8.5;
const LINE_HEIGHT = 22;
const MARK_COLOR = '#FF9C01'; // orange – same as full-row-search-mark.active
const NORMAL_BG = '#F5F7FA';
const TEXT_COLOR = '#313238';
const MARK_BG = '#FFF3B8';

/** Build PIXI app synchronously – caller ensures PIXI is loaded */
export async function buildPixiApp(canvas: HTMLCanvasElement, options: PixiRowRenderOptions) {
  const PIXI = await lazyLoadPixi();
  const {
    rows,
    highlightKeywords = [],
    fontSize = 12,
    lineHeight = LINE_HEIGHT,
    charWidth = CHAR_WIDTH,
  } = options;

  const app = new PIXI.Application();
  await app.init({
    view: canvas,
    width: canvas.offsetWidth || canvas.parentElement?.clientWidth || 960,
    height: Math.max(480, rows.length * lineHeight + 16),
    backgroundColor: 0xf5f7fa,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });

  const container = new PIXI.Container();
  app.stage.addChild(container);

  // Build lowercase kw list for fast scan
  const kwsLC = highlightKeywords.map(k => k.toLowerCase());

  const fullText = rows.map(r => r.text).join('');
  const matches: Array<{ start: number; end: number }> = [];
  let globalIdx = 0;
  for (const row of rows) {
    const start = globalIdx;
    const end = globalIdx + row.text.length;
    globalIdx = end;

    if (kwsLC.length === 0) continue;
    const txtLC = row.text.toLowerCase();
    for (const kw of kwsLC) {
      let pos = 0;
      while ((pos = txtLC.indexOf(kw, pos)) !== -1) {
        matches.push({ start: start + pos, end: start + pos + kw.length });
        pos += kw.length;
      }
    }
  }

  // Flatten lines into PIXI graphics + text sprites
  const GUTTER_X = 12;
  const GUTTER_Y = 8;
  let yCursor = GUTTER_Y;
  globalIdx = 0;

  for (const row of rows) {
    const lineLenPx = row.text.length * charWidth;
    if (yCursor + lineHeight > app.screen.height) {
      // Auto-grow viewport
      app.renderer.resize(app.screen.width, app.screen.height + lineHeight * 2);
    }

    if (row.isMark) {
      const bg = new PIXI.Graphics();
      bg.beginFill(0xfff3b8, 1);
      bg.drawRect(GUTTER_X - 2, yCursor - 1, lineLenPx + 4, lineHeight + 2);
      bg.endFill();
      container.addChild(bg);
    }

    // Highlight individual matches overlapping this line
    const lineStart = globalIdx;
    const lineEnd = globalIdx + row.text.length;
    const lineMatches = matches.filter(m => m.start < lineEnd && m.end > lineStart);
    for (const m of lineMatches) {
      const hlStart = Math.max(0, m.start - lineStart);
      const hlEnd = Math.min(row.text.length, m.end - lineStart);
      const hlBg = new PIXI.Graphics();
      hlBg.beginFill(0xff9c01, 1);
      hlBg.drawRect(
        GUTTER_X + hlStart * charWidth,
        yCursor,
        (hlEnd - hlStart) * charWidth,
        lineHeight,
      );
      hlBg.endFill();
      container.addChild(hlBg);
    }

    const style = new PIXI.TextStyle({
      fontSize,
      fontFamily: "'Menlo','Monaco','Consolas',monospace",
      fill: TEXT_COLOR,
      wordWrap: false,
    });
    const pixiTxt = new PIXI.Text({ text: row.text, style });
    pixiTxt.position.set(GUTTER_X, yCursor);
    container.addChild(pixiTxt);

    globalIdx = lineEnd;
    yCursor += lineHeight;
  }

  return { app, container };
}

/** Destroy PIXI app cleanly */
export function destroyPixiApp(app: any) {
  app?.stage?.removeChildren();
  app?.destroy(true, { children: true, texture: true });
}