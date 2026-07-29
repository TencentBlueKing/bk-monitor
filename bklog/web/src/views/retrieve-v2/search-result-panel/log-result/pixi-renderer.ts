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
const TEXT_COLOR = '#313238';
const MAX_SAFE_CANVAS_HEIGHT = 32000;
const MAX_HIGHLIGHT_MATCHES = 2000;

type PixiDisplayRow = {
  isMark: boolean;
  start: number;
  text: string;
};

const splitTextForPixi = (text: string, startIndex: number, maxCharsPerLine: number, isMark: boolean): PixiDisplayRow[] => {
  const output: PixiDisplayRow[] = [];
  let lineStart = 0;

  while (lineStart <= text.length) {
    const newlineIndex = text.indexOf('\n', lineStart);
    const lineEnd = newlineIndex === -1 ? text.length : newlineIndex;

    if (lineEnd === lineStart) {
      output.push({ text: '', start: startIndex + lineStart, isMark });
    } else {
      for (let partStart = lineStart; partStart < lineEnd; partStart += maxCharsPerLine) {
        output.push({
          text: text.slice(partStart, Math.min(partStart + maxCharsPerLine, lineEnd)),
          start: startIndex + partStart,
          isMark,
        });
      }
    }

    if (newlineIndex === -1) break;
    lineStart = newlineIndex + 1;
    if (lineStart === text.length) {
      output.push({ text: '', start: startIndex + lineStart, isMark });
      break;
    }
  }

  return output;
};

const fillRect = (PIXI: any, color: number, x: number, y: number, width: number, height: number) => {
  const rect = new PIXI.Graphics();
  if (typeof rect.rect === 'function' && typeof rect.fill === 'function') {
    rect.rect(x, y, width, height).fill({ color, alpha: 1 });
  } else {
    rect.beginFill(color, 1);
    rect.drawRect(x, y, width, height);
    rect.endFill();
  }

  return rect;
};

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
  const width = Math.floor(canvas.parentElement?.clientWidth || canvas.offsetWidth || 960);
  const maxCharsPerLine = Math.max(40, Math.floor((width - 24) / charWidth));
  const fullText = rows.map(r => r.text).join('');
  const displayRows: PixiDisplayRow[] = [];
  let globalIdx = 0;

  for (const row of rows) {
    displayRows.push(...splitTextForPixi(row.text, globalIdx, maxCharsPerLine, row.isMark));
    globalIdx += row.text.length;
  }
  const contentHeight = displayRows.length * lineHeight + 16;
  if (contentHeight > MAX_SAFE_CANVAS_HEIGHT) {
    throw new Error(`Pixi canvas height ${contentHeight}px exceeds safe limit`);
  }
  const height = Math.max(480, contentHeight);
  const resolution = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));

  const app = new PIXI.Application();
  await app.init({
    canvas,
    view: canvas,
    width,
    height,
    backgroundColor: 0xf5f7fa,
    antialias: true,
    resolution,
    autoDensity: true,
  });
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  if (app.renderer) {
    app.renderer.roundPixels = true;
  }

  const container = new PIXI.Container();
  app.stage.addChild(container);

  // Build lowercase kw list for fast scan
  const kwsLC = highlightKeywords.map(k => k.toLowerCase());
  const matches: Array<{ start: number; end: number }> = [];
  const fullTextLC = fullText.toLowerCase();
  for (const kw of kwsLC) {
    if (!kw) continue;
    let pos = 0;
    while (matches.length < MAX_HIGHLIGHT_MATCHES && (pos = fullTextLC.indexOf(kw, pos)) !== -1) {
      matches.push({ start: pos, end: pos + kw.length });
      pos += kw.length;
    }
  }

  // Flatten lines into PIXI graphics + text sprites
  const GUTTER_X = 12;
  const GUTTER_Y = 8;
  let yCursor = GUTTER_Y;
  const style = new PIXI.TextStyle({
    fontSize,
    fontFamily: 'Menlo, Monaco, Consolas, "Courier New", monospace',
    fill: TEXT_COLOR,
    wordWrap: false,
  });

  for (const row of displayRows) {
    const lineLenPx = row.text.length * charWidth;
    if (yCursor + lineHeight > app.screen.height) {
      // Auto-grow viewport
      app.renderer.resize(app.screen.width, app.screen.height + lineHeight * 2);
    }

    if (row.isMark) {
      const bg = fillRect(PIXI, 0xfff3b8, GUTTER_X - 2, yCursor - 1, lineLenPx + 4, lineHeight + 2);
      container.addChild(bg);
    }

    // Highlight individual matches overlapping this line
    const lineStart = row.start;
    const lineEnd = row.start + row.text.length;
    const lineMatches = matches.filter(m => m.start < lineEnd && m.end > lineStart);
    for (const m of lineMatches) {
      const hlStart = Math.max(0, m.start - lineStart);
      const hlEnd = Math.min(row.text.length, m.end - lineStart);
      const hlBg = fillRect(
        PIXI,
        0xff9c01,
        GUTTER_X + hlStart * charWidth,
        yCursor,
        (hlEnd - hlStart) * charWidth,
        lineHeight,
      );
      container.addChild(hlBg);
    }

    const pixiTxt = new PIXI.Text({ text: row.text, style });
    pixiTxt.position.set(GUTTER_X, yCursor);
    container.addChild(pixiTxt);

    yCursor += lineHeight;
  }

  return { app, container };
}

/** Destroy PIXI app cleanly */
export function destroyPixiApp(app: any) {
  app?.stage?.removeChildren();
  app?.destroy(true, { children: true, texture: true });
}