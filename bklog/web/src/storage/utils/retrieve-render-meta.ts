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
  /** 表格 CELL 渲染用的截断行，大字段已在入库阶段截到 32KB */
  displayRow?: Record<string, any>;
}

interface RetrieveRowRenderMetaOptions {
  highlightField?: string;
}

// 表格 CELL 默认展示上限：32KB，超出部分通过「全量」侧栏查看
export const LARGE_FIELD_TEXT_LENGTH = 32 * 1024;
export const DEFAULT_HIGHLIGHT_FIELD = '__highlight';
const SEGMENT_MAX_TOKENS = 500;
const SEGMENT_CHUNK_SIZE = 200;
const LARGE_FIELD_PREVIEW_SUFFIX = '...';

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
  let bytes = 0;
  let output = '';

  for (const char of text) {
    const charBytes = estimateTextBytes(char);
    if (bytes + charBytes > maxBytes) break;
    bytes += charBytes;
    output += char;
  }

  return `${output}${LARGE_FIELD_PREVIEW_SUFFIX}`;
};

const hasMark = (value: any) => typeof value === 'string' && /<\/?mark>/i.test(value);

const isPlainObject = (value: any) => Object.prototype.toString.call(value) === '[object Object]';

const setDisplayFieldValue = (row: Record<string, any>, fieldName: string, value: any) => {
  if (!fieldName.includes('.') || Object.hasOwn(row, fieldName)) {
    row[fieldName] = value;
    return row;
  }

  const path = fieldName.split('.');
  const rootKey = path[0];
  if (!isPlainObject(row[rootKey])) {
    row[fieldName] = value;
    return row;
  }

  row[rootKey] = { ...row[rootKey] };
  let current = row[rootKey];
  for (let index = 1; index < path.length - 1; index += 1) {
    const key = path[index];
    if (!isPlainObject(current[key])) {
      current[path.slice(index).join('.')] = value;
      return row;
    }
    current[key] = { ...current[key] };
    current = current[key];
  }

  current[path[path.length - 1]] = value;
  return row;
};

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

    const parts = cleanText.split(/([\s:\.,\-_\[\]\{\}\(\)"'=\/\\]+)/).filter(Boolean);
    for (const part of parts) {
      if (count >= SEGMENT_MAX_TOKENS) {
        output.push({ text: part, isMark: false, isCursorText: false, isBlobWord: true });
        continue;
      }

      output.push({
        text: part,
        isMark: false,
        isCursorText: !/^[\s:\.,\-_\[\]\{\}\(\)"'=\/\\]+$/.test(part),
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
  const truncatedFields: string[] = [];
  const fieldSegments: Record<string, RetrieveTextSegment[]> = {};
  const sourceRow = renderRow || rawRow;
  const displayRow = isPlainObject(sourceRow) ? { ...sourceRow } : sourceRow;
  const markedFields = {
    ...collectMarkedFields(sourceRow, '', {}, highlightField),
    ...collectHighlightFields(rawRow, highlightField),
    ...collectHighlightFields(renderRow, highlightField),
  };
  const fieldNames = new Set([
    ...Object.keys(rawRow ?? {}).filter(fieldName => fieldName !== highlightField),
    ...Object.keys(sourceRow ?? {}).filter(fieldName => fieldName !== highlightField),
    ...Object.keys(markedFields),
  ]);

  fieldNames.forEach(fieldName => {
    const value = Object.hasOwn(markedFields, fieldName)
      ? markedFields[fieldName]
      : (getValueByPath(sourceRow, fieldName) ?? getValueByPath(rawRow, fieldName));
    if (value === null || value === undefined) return;

    const rawValue = getValueByPath(rawRow, fieldName);
    const rawText = stringifyValue(rawValue);
    const renderText = stringifyValue(value);
    const plainRenderText = stripMark(renderText);
    const rawBytes = estimateTextBytes(rawText);
    const exceedsLargeFieldLimit = rawBytes > LARGE_FIELD_TEXT_LENGTH;
    if (exceedsLargeFieldLimit) {
      truncatedFields.push(fieldName);
    }

    const truncatedRenderText = exceedsLargeFieldLimit
      ? truncateTextByBytes(plainRenderText, LARGE_FIELD_TEXT_LENGTH)
      : renderText;

    if (isPlainObject(displayRow) && exceedsLargeFieldLimit) {
      setDisplayFieldValue(displayRow, fieldName, truncatedRenderText);
    }

    // Store the pre-tokenized render value for every field that may be rendered.
    fieldSegments[fieldName] = splitRenderText(truncatedRenderText);
  });

  return {
    hasTruncatedField: truncatedFields.length > 0,
    truncatedFields,
    fieldSegments,
    displayRow: isPlainObject(displayRow) ? displayRow : undefined,
  };
};
