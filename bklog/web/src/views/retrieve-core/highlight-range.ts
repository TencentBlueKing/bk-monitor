/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

// 高亮范围的纯计算部分，不依赖 vue / DOM，可在 Worker 内直接使用。
// page-highlight.ts 持有 reactive 的页面高亮状态，Worker 侧不可引入。

export interface HighlightRange {
  start: number;
  end: number;
  keywordIndex?: number;
}

export interface HighlightSegment {
  text: string;
  resultHighlighted?: boolean;
  pageHighlighted?: boolean;
  pageHighlightIndex?: number;
}

/**
 * 将全局字符范围映射到各分词局部坐标。
 * @param normalizeEmptyAsQuotes 与渲染层一致：空串按 "" 计入拼接偏移（页面划词高亮用）
 */
export const mapGlobalRangesToSegments = (
  segments: Array<{ text?: string } | string>,
  globalRanges: HighlightRange[],
  normalizeEmptyAsQuotes = false,
): HighlightRange[][] => {
  const texts = segments.map((segment) => {
    const text = typeof segment === 'string' ? segment : String(segment?.text ?? '');
    return normalizeEmptyAsQuotes && !text.length ? '""' : text;
  });

  if (!texts.length) {
    return [];
  }

  if (!globalRanges.length) {
    return texts.map(() => []);
  }

  const perSegmentRanges: HighlightRange[][] = texts.map(() => []);
  let offset = 0;

  texts.forEach((text, index) => {
    const start = offset;
    const end = offset + text.length;
    globalRanges.forEach((range) => {
      if (range.end > start && range.start < end) {
        perSegmentRanges[index].push({
          start: Math.max(0, range.start - start),
          end: Math.min(text.length, range.end - start),
          keywordIndex: range.keywordIndex,
        });
      }
    });
    offset = end;
  });

  return perSegmentRanges;
};

export const parseResultMarkedText = (value: unknown) => {
  const source = String(value ?? '');
  const markRanges: HighlightRange[] = [];
  let plainText = '';
  let cursor = 0;
  const markReg = /<mark(?:\s[^>]*)?>([\s\S]*?)<\/mark>/gi;
  let match = markReg.exec(source);

  while (match) {
    plainText += source.slice(cursor, match.index);
    const start = plainText.length;
    plainText += match[1];
    markRanges.push({ start, end: plainText.length });
    cursor = match.index + match[0].length;
    match = markReg.exec(source);
  }

  plainText += source.slice(cursor);
  return { plainText, markRanges };
};

export const escapeHtml = (value: unknown) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');
