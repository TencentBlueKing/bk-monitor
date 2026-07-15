/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { reactive } from 'vue';

import StaticUtil from './static.util';

export type PageHighlightAccuracy = 'exactly' | 'partially';

export interface PageHighlightKeyword {
  text: string;
  className: string;
  backgroundColor: string;
  color: string;
  textReg: RegExp;
}

export interface PageHighlightState {
  keywords: PageHighlightKeyword[];
  caseSensitive: boolean;
  regExpMark: boolean;
  accuracy: PageHighlightAccuracy;
  colors: string[][];
  version: number;
}

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

export const pageHighlightState = reactive<PageHighlightState>({
  keywords: [],
  caseSensitive: false,
  regExpMark: false,
  accuracy: 'partially',
  colors: [],
  version: 0,
});

export const getPageHighlightOptions = () => ({
  caseSensitive: pageHighlightState.caseSensitive,
  regExpMark: pageHighlightState.regExpMark,
  accuracy: pageHighlightState.accuracy,
});

export const buildPageHighlightKeyword = (
  keyword: string,
  index: number,
  colors: string[][],
  options = getPageHighlightOptions(),
): PageHighlightKeyword | null => {
  if (!keyword) {
    return null;
  }

  try {
    const colorPair = colors[index % colors.length];
    const formatRegStr = !options.regExpMark;
    return {
      text: keyword,
      className: `highlight-${index}`,
      backgroundColor: colorPair[0],
      color: colorPair[1],
      textReg: StaticUtil.getRegExp(
        keyword,
        options.caseSensitive ? 'g' : 'gi',
        options.accuracy === 'exactly',
        formatRegStr,
      ),
    };
  } catch (error) {
    console.error(`Invalid highlight keyword: ${keyword}`, error);
    return null;
  }
};

export const setPageHighlightOptions = (options: Partial<Omit<PageHighlightState, 'keywords' | 'version' | 'colors'>>) => {
  let changed = false;
  if (typeof options.caseSensitive === 'boolean' && pageHighlightState.caseSensitive !== options.caseSensitive) {
    pageHighlightState.caseSensitive = options.caseSensitive;
    changed = true;
  }
  if (typeof options.regExpMark === 'boolean' && pageHighlightState.regExpMark !== options.regExpMark) {
    pageHighlightState.regExpMark = options.regExpMark;
    changed = true;
  }
  if (options.accuracy && pageHighlightState.accuracy !== options.accuracy) {
    pageHighlightState.accuracy = options.accuracy;
    changed = true;
  }

  if (changed) {
    pageHighlightState.version += 1;
  }
};

export const setPageHighlightKeywords = (keywords: PageHighlightKeyword[], colors?: string[][]) => {
  pageHighlightState.keywords = keywords;
  if (colors) {
    pageHighlightState.colors = colors;
  }
  pageHighlightState.version += 1;
};

export const clearPageHighlightKeywords = () => {
  if (!pageHighlightState.keywords.length) {
    return;
  }

  pageHighlightState.keywords = [];
  pageHighlightState.version += 1;
};

const cloneGlobalRegExp = (regExp: RegExp) => {
  const flags = regExp.flags.includes('g') ? regExp.flags : `${regExp.flags}g`;
  return new RegExp(regExp.source, flags);
};

export const collectPageHighlightRanges = (text: string, keywords = pageHighlightState.keywords): HighlightRange[] => {
  if (!text || !keywords.length) {
    return [];
  }

  const ranges: HighlightRange[] = [];
  keywords.forEach((keyword, keywordIndex) => {
    const regExp = cloneGlobalRegExp(keyword.textReg);
    let match = regExp.exec(text);

    while (match) {
      const matchText = match[0] ?? '';
      const matchLength = matchText.length;
      if (matchLength > 0) {
        ranges.push({
          start: match.index,
          end: match.index + matchLength,
          keywordIndex,
        });
      }
      regExp.lastIndex = matchLength === 0 ? match.index + 1 : regExp.lastIndex;
      match = regExp.exec(text);
    }
  });

  return ranges
    .filter(range => range.end > range.start)
    .sort((a, b) => a.start - b.start || b.end - a.end || (a.keywordIndex ?? 0) - (b.keywordIndex ?? 0));
};

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

/**
 * 在分词拼接后的完整文本上匹配页面高亮，再映射回每个分词的局部范围。
 * 用于跨分词连续划选（如 mirrors.tencent.com/tgingame）保持同一关键词的完整高亮，含中间标点。
 * 拼接文本需与渲染文本一致（空串展示为 ""）。
 */
export const buildSegmentPageHighlightRanges = (
  segments: Array<{ text?: string } | string>,
  keywords = pageHighlightState.keywords,
): HighlightRange[][] => {
  const texts = segments.map((segment) => {
    const text = typeof segment === 'string' ? segment : String(segment?.text ?? '');
    return text.length ? text : '""';
  });

  if (!texts.length) {
    return [];
  }

  return mapGlobalRangesToSegments(
    segments,
    collectPageHighlightRanges(texts.join(''), keywords),
    true,
  );
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

export const mergeHighlightSegments = ({
  text,
  resultRanges = [],
  pageRanges = collectPageHighlightRanges(text),
}: {
  text: string;
  resultRanges?: HighlightRange[];
  pageRanges?: HighlightRange[];
}): HighlightSegment[] => {
  if (!text) {
    return [];
  }

  const points = new Set([0, text.length]);
  const addRangePoints = (range: HighlightRange) => {
    const start = Math.max(0, Math.min(text.length, range.start));
    const end = Math.max(0, Math.min(text.length, range.end));
    if (end > start) {
      points.add(start);
      points.add(end);
    }
  };

  resultRanges.forEach(addRangePoints);
  pageRanges.forEach(addRangePoints);

  const sortedPoints = Array.from(points).sort((a, b) => a - b);
  const segments: HighlightSegment[] = [];

  for (let index = 0; index < sortedPoints.length - 1; index += 1) {
    const start = sortedPoints[index];
    const end = sortedPoints[index + 1];
    if (start === end) {
      continue;
    }

    const pageRange = pageRanges.find(range => range.start < end && range.end > start);
    const resultHighlighted = resultRanges.some(range => range.start < end && range.end > start);
    segments.push({
      text: text.slice(start, end),
      resultHighlighted,
      pageHighlighted: Boolean(pageRange),
      pageHighlightIndex: pageRange?.keywordIndex,
    });
  }

  return segments;
};

export const escapeHtml = (value: unknown) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

export const buildHighlightHtml = ({
  text,
  resultRanges = [],
  pageRanges = collectPageHighlightRanges(text),
}: {
  text: string;
  resultRanges?: HighlightRange[];
  pageRanges?: HighlightRange[];
}) => mergeHighlightSegments({ text, resultRanges, pageRanges }).map((segment) => {
  const classes = [];
  const styles: string[] = [];
  if (segment.resultHighlighted) {
    classes.push('result-highlight');
  }
  if (segment.pageHighlighted) {
    classes.push('page-highlight');
    if (typeof segment.pageHighlightIndex === 'number') {
      classes.push(`page-highlight-${segment.pageHighlightIndex}`);
      const keyword = pageHighlightState.keywords[segment.pageHighlightIndex];
      if (keyword?.backgroundColor) {
        styles.push(`background-color:${keyword.backgroundColor}`);
      }
      if (keyword?.color) {
        styles.push(`color:${keyword.color}`);
      }
    }
  }

  const content = escapeHtml(segment.text);
  if (!classes.length) {
    return content;
  }
  const styleAttr = styles.length ? ` style="${styles.join(';')}"` : '';
  return `<mark class="${classes.join(' ')}"${styleAttr}>${content}</mark>`;
}).join('');

export const highlightPlainTextIntoFragment = ({
  text,
  resultHighlighted = false,
  resultRanges: explicitResultRanges,
  pageRanges,
}: {
  text: string;
  resultHighlighted?: boolean;
  resultRanges?: HighlightRange[];
  pageRanges?: HighlightRange[];
}) => {
  const fragment = document.createDocumentFragment();
  const resultRanges = explicitResultRanges
    ?? (resultHighlighted && text ? [{ start: 0, end: text.length }] : []);
  const segments = mergeHighlightSegments({ text, resultRanges, pageRanges });

  segments.forEach((segment) => {
    const tagName = segment.resultHighlighted || segment.pageHighlighted ? 'mark' : 'span';
    const child = document.createElement(tagName);
    child.textContent = segment.text?.length ? segment.text : '""';
    if (segment.resultHighlighted) {
      child.classList.add('result-highlight');
    }
    if (segment.pageHighlighted) {
      child.classList.add('page-highlight');
      if (typeof segment.pageHighlightIndex === 'number') {
        child.classList.add(`page-highlight-${segment.pageHighlightIndex}`);
        const keyword = pageHighlightState.keywords[segment.pageHighlightIndex];
        if (keyword) {
          child.style.backgroundColor = keyword.backgroundColor;
          child.style.color = keyword.color;
        }
      }
    }
    fragment.appendChild(child);
  });

  return fragment;
};
