/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

export interface RetrieveTextSegment {
  text: string;
  isMark: boolean;
  isCursorText: boolean;
  isBlobWord?: boolean;
  isNotParticiple?: boolean;
}

export interface RetrieveRowRenderMeta {
  hasTruncatedField: boolean;
  truncatedFields: string[];
  fieldSegments: Record<string, RetrieveTextSegment[]>;
  /** 大字段表格 CELL 渲染覆盖值：仅保存超 32KB 字段的截断文本，避免存储 row-shaped 副本 */
  truncatedTextByField?: Record<string, string>;
}

interface RetrieveRowRenderMetaOptions {
  highlightField?: string;
  precomputeSegments?: boolean;
  /** 仅为即将渲染/复制/高亮使用的字段预计算，避免为整行所有字段生成重复派生数据 */
  fieldNames?: string[];
}

// 表格 CELL 默认展示上限：32KB，超出部分通过「全量」侧栏查看
export const LARGE_FIELD_TEXT_LENGTH = 32 * 1024;
export const DEFAULT_HIGHLIGHT_FIELD = '__highlight';
const SEGMENT_MAX_TOKENS = 500;
const SEGMENT_CHUNK_SIZE = 200;
const LARGE_FIELD_PREVIEW_SUFFIX = '...';
const textEncoder = typeof TextEncoder !== 'undefined' ? new TextEncoder() : null;

export const stripMark = (value: string) =>
  String(value)
    .replace(/<mark>/gi, '')
    .replace(/<\/mark>/gi, '');

const stringifyValue = (value: any) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

/** 估算字符串字节数（UTF-8）。Blob 不可用时降级为 length * 3（UTF-16 保守估计）。 */
const estimateTextBytes = (text: string): number => {
  if (textEncoder) {
    return textEncoder.encode(text).length;
  }
  if (typeof Blob !== 'undefined') {
    try {
      return new Blob([text]).size;
    } catch {
      // ignore
    }
  }
  return text.length * 3;
};

const truncateTextByBytes = (text: string, maxBytes: number): string => {
  if (estimateTextBytes(text) <= maxBytes) {
    return text;
  }

  let left = 0;
  let right = text.length;
  let output = '';

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const candidate = text.slice(0, mid);
    if (estimateTextBytes(candidate) <= maxBytes) {
      output = candidate;
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return `${output}${LARGE_FIELD_PREVIEW_SUFFIX}`;
};

const truncateMarkedTextByBytes = (text: string, maxBytes: number): string => {
  if (estimateTextBytes(stripMark(text)) <= maxBytes) {
    return text;
  }

  let output = '';
  let consumedBytes = 0;
  let isInsideMark = false;
  const tokens = text.split(/(<\/?mark>)/gi).filter(Boolean);

  const appendVisibleText = (value: string) => {
    if (!value) return false;
    const remainingBytes = maxBytes - consumedBytes;
    if (remainingBytes <= 0) return true;
    if (estimateTextBytes(value) <= remainingBytes) {
      output += value;
      consumedBytes += estimateTextBytes(value);
      return false;
    }

    output += truncateTextByBytes(value, remainingBytes).slice(0, -LARGE_FIELD_PREVIEW_SUFFIX.length);
    consumedBytes = maxBytes;
    return true;
  };

  for (const token of tokens) {
    if (/^<mark>$/i.test(token)) {
      if (!isInsideMark) {
        output += token;
        isInsideMark = true;
      }
      continue;
    }
    if (/^<\/mark>$/i.test(token)) {
      if (isInsideMark) {
        output += token;
        isInsideMark = false;
      }
      continue;
    }

    if (appendVisibleText(token)) {
      break;
    }
  }

  return output + (isInsideMark ? '</mark>' : '') + LARGE_FIELD_PREVIEW_SUFFIX;
};

const hasMark = (value: any) => typeof value === 'string' && /<\/?mark>/i.test(value);

const isPlainObject = (value: any) => Object.prototype.toString.call(value) === '[object Object]';

export const getValueByPath = (row: Record<string, any> | undefined, path: string) => {
  if (!row || typeof path !== 'string') return undefined;
  if (Object.hasOwn(row, path)) return row[path];

  const parts = path.split('.');
  let current: any = row;
  for (let index = 0; index < parts.length; index++) {
    const part = parts[index];
    if (current === null || current === undefined) return undefined;
    if (!Object.hasOwn(current, part)) {
      const validKey = parts.slice(index).join('.');
      return Object.hasOwn(current, validKey) ? current[validKey] : undefined;
    }
    current = current[part];
  }

  return current;
};

const collectMarkedFields = (
  value: any,
  prefix = '',
  output: Record<string, any> = {},
  highlightField = DEFAULT_HIGHLIGHT_FIELD,
) => {
  if (hasMark(value) && prefix) {
    output[prefix] = value;
    return output;
  }

  if (!isPlainObject(value)) return output;

  Object.keys(value).forEach(key => {
    if (key === highlightField) return;
    const fieldName = prefix ? `${prefix}.${key}` : key;
    collectMarkedFields(value[key], fieldName, output, highlightField);
  });

  return output;
};

const collectHighlightFields = (
  rawRow: Record<string, any> | undefined = {},
  highlightField = DEFAULT_HIGHLIGHT_FIELD,
) => {
  const output: Record<string, any> = {};
  const highlight = rawRow[highlightField];
  if (!isPlainObject(highlight)) return output;

  Object.keys(highlight).forEach(fieldName => {
    const value = Array.isArray(highlight[fieldName]) ? highlight[fieldName][0] : highlight[fieldName];
    if (hasMark(value)) {
      output[fieldName] = value;
    }
  });

  return output;
};

/**
 * Pre-split text once after the API response is available.
 * Rendering code can consume these segments directly and avoid LuceneSegment.split on hot paths.
 */
export const splitRenderText = (value: any): RetrieveTextSegment[] => {
  const text = stringifyValue(value);
  const output: RetrieveTextSegment[] = [];
  const segments = String(text ?? '').split(/(<mark>.*?<\/mark>)/gi);
  let count = 0;

  for (const segment of segments) {
    if (!segment) continue;
    const isMark = /<mark>.*?<\/mark>/i.test(segment);
    const cleanText = stripMark(segment);

    if (isMark) {
      output.push({ text: cleanText, isMark: true, isCursorText: true });
      count += 1;
      continue;
    }

    if (count >= SEGMENT_MAX_TOKENS) {
      for (let i = 0; i < cleanText.length; i += SEGMENT_CHUNK_SIZE) {
        output.push({
          text: cleanText.slice(i, i + SEGMENT_CHUNK_SIZE),
          isMark: false,
          isCursorText: false,
          isBlobWord: true,
        });
      }
      continue;
    }

    const parts = cleanText.split(/([\s:.,_[\]{}()"'=/\\-]+)/).filter(Boolean);
    for (const part of parts) {
      if (count >= SEGMENT_MAX_TOKENS) {
        output.push({ text: part, isMark: false, isCursorText: false, isBlobWord: true });
        continue;
      }

      output.push({
        text: part,
        isMark: false,
        isCursorText: !/^[\s:.,_[\]{}()"'=/\\-]+$/.test(part),
      });
      count += 1;
    }
  }

  return output;
};

export const createRetrieveRowRenderMeta = (
  rawRow: Record<string, any> = {},
  renderRow?: Record<string, any>,
  options: RetrieveRowRenderMetaOptions = {},
): RetrieveRowRenderMeta => {
  const highlightField = options.highlightField || DEFAULT_HIGHLIGHT_FIELD;
  const precomputeSegments = options.precomputeSegments ?? true;
  const truncatedFields: string[] = [];
  const fieldSegments: Record<string, RetrieveTextSegment[]> = {};
  const sourceRow = renderRow || rawRow;
  let truncatedTextByField: Record<string, string> | undefined;
  const markedFields = {
    ...collectMarkedFields(sourceRow, '', {}, highlightField),
    ...collectHighlightFields(rawRow, highlightField),
    ...collectHighlightFields(renderRow, highlightField),
  };
  const candidateFieldNames = [
    ...Object.keys(rawRow ?? {}).filter(fieldName => fieldName !== highlightField),
    ...Object.keys(sourceRow ?? {}).filter(fieldName => fieldName !== highlightField),
    ...Object.keys(markedFields),
  ];
  const scopedFieldNames = Array.from(new Set((options.fieldNames ?? []).filter(Boolean)));
  const fieldNames = new Set(
    scopedFieldNames.length
      ? [...scopedFieldNames, ...Object.keys(markedFields)]
      : candidateFieldNames,
  );

  fieldNames.forEach(fieldName => {
    const value = Object.hasOwn(markedFields, fieldName)
      ? markedFields[fieldName]
      : (getValueByPath(sourceRow, fieldName) ?? getValueByPath(rawRow, fieldName));
    if (value === null || value === undefined) return;

    const rawValue = getValueByPath(rawRow, fieldName);
    const rawText = stringifyValue(rawValue);
    const renderText = stringifyValue(value);
    const rawBytes = estimateTextBytes(rawText);
    const exceedsLargeFieldLimit = rawBytes > LARGE_FIELD_TEXT_LENGTH;
    if (exceedsLargeFieldLimit) {
      truncatedFields.push(fieldName);
    }

    const truncatedRenderText = exceedsLargeFieldLimit
      ? truncateMarkedTextByBytes(renderText, LARGE_FIELD_TEXT_LENGTH)
      : renderText;

    if (exceedsLargeFieldLimit) {
      truncatedTextByField = truncatedTextByField ?? {};
      truncatedTextByField[fieldName] = truncatedRenderText;
    }

    // Store the pre-tokenized render value for every field that may be rendered.
    if (precomputeSegments) {
      fieldSegments[fieldName] = splitRenderText(truncatedRenderText);
    }
  });

  return {
    hasTruncatedField: truncatedFields.length > 0,
    truncatedFields,
    fieldSegments,
    truncatedTextByField,
  };
};
