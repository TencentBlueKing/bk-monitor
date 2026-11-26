/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export interface NormalizedTagOption {
  id: string;
  name: string;
  tooltip: string;
  raw: Record<string, unknown>;
}

export function normalizeTagOption(
  item: unknown,
  saveKey = 'id',
  displayKey = 'name',
  tooltipKey = '',
): NormalizedTagOption | null {
  if (item === null || item === undefined) return null;
  if (typeof item === 'string' || typeof item === 'number') {
    const text = String(item);
    return {
      id: text,
      name: text,
      tooltip: text,
      raw: { [saveKey]: text, [displayKey]: text },
    };
  }
  if (typeof item === 'object') {
    const record = item as Record<string, unknown>;
    const rawId = record[saveKey] ?? record.id ?? record[displayKey] ?? record.name;
    if (rawId === null || rawId === undefined) return null;
    const id = String(rawId);
    const rawName = record[displayKey] ?? record.name ?? rawId;
    const name = String(rawName);
    const rawTooltip = tooltipKey ? record[tooltipKey] : undefined;
    const tooltip = rawTooltip !== null && rawTooltip !== undefined ? String(rawTooltip) : name;
    return { id, name, tooltip, raw: record };
  }
  return null;
}

export function normalizeTagOptions(
  list: unknown[] | undefined,
  saveKey = 'id',
  displayKey = 'name',
  tooltipKey = '',
): NormalizedTagOption[] {
  if (!Array.isArray(list) || list.length === 0) return [];
  const seen = new Set<string>();
  const result: NormalizedTagOption[] = [];
  for (const item of list) {
    const normalized = normalizeTagOption(item, saveKey, displayKey, tooltipKey);
    if (!normalized || seen.has(normalized.id)) continue;
    seen.add(normalized.id);
    result.push(normalized);
  }
  return result;
}

export function filterTagOptions(params: {
  options: NormalizedTagOption[];
  selected: string[];
  keyword: string;
  searchKey?: string | string[];
}): NormalizedTagOption[] {
  const { options, selected, keyword, searchKey = 'name' } = params;
  if (!options.length) return [];

  const selectedSet = new Set(selected.map(item => String(item)));
  const normalizedKeyword = String(keyword ?? '').trim().toLowerCase();
  const keys = Array.isArray(searchKey) ? searchKey : [searchKey];

  return options.filter(option => {
    if (selectedSet.has(option.id)) return false;
    if (!normalizedKeyword) return true;
    if (option.name.toLowerCase().includes(normalizedKeyword)) return true;
    if (option.id.toLowerCase().includes(normalizedKeyword)) return true;
    return keys.some(key => {
      const value = option.raw[key];
      return value !== null && value !== undefined && String(value).toLowerCase().includes(normalizedKeyword);
    });
  });
}

/**
 * Compute how many leading tags fit in a single line alongside a `+N` badge.
 * Returns `0` when no collapsing is needed (all tags fit or fewer than 2 tags).
 */
export function computeCollapsedVisibleCount(params: {
  tagWidths: number[];
  availableWidth: number;
  gap?: number;
  moreBadgeWidth?: number;
}): number {
  const { tagWidths, availableWidth, gap = 4, moreBadgeWidth = 36 } = params;
  if (tagWidths.length <= 1 || availableWidth <= 0) return 0;

  let totalWidth = 0;
  for (let i = 0; i < tagWidths.length; i += 1) {
    totalWidth += tagWidths[i] + (i > 0 ? gap : 0);
  }
  if (totalWidth <= availableWidth) return 0;

  let usedWidth = 0;
  let visibleCount = 1;
  for (let i = 0; i < tagWidths.length - 1; i += 1) {
    const nextUsed = usedWidth + (i > 0 ? gap : 0) + tagWidths[i];
    if (nextUsed + gap + moreBadgeWidth <= availableWidth) {
      usedWidth = nextUsed;
      visibleCount = i + 1;
    } else {
      break;
    }
  }
  return Math.max(1, Math.min(visibleCount, tagWidths.length - 1));
}

export function resolveTagAddition(params: {
  currentTags: string[];
  candidate: string;
  allowCreate: boolean;
  options: NormalizedTagOption[];
  max?: number;
}): string[] | null {
  const { currentTags, candidate, allowCreate, options, max } = params;
  const trimmed = String(candidate ?? '').trim();
  if (!trimmed) return null;
  if (max !== undefined && Number.isFinite(max) && currentTags.length >= max) return null;

  let resolvedValue: string | null = trimmed;
  if (!allowCreate) {
    const matched = options.find(
      option =>
        option.id === trimmed ||
        option.name === trimmed ||
        option.id.toLowerCase() === trimmed.toLowerCase() ||
        option.name.toLowerCase() === trimmed.toLowerCase(),
    );
    resolvedValue = matched ? matched.id : null;
  }

  if (!resolvedValue || currentTags.includes(resolvedValue)) return null;
  return [...currentTags, resolvedValue];
}

export function parsePastedTags(params: {
  currentTags: string[];
  pasteValue: string;
  pasteFn?: (value: string) => unknown;
  separator?: string;
  max?: number;
}): string[] | null {
  const { currentTags, pasteValue, pasteFn, separator, max } = params;
  const limit = max !== undefined && Number.isFinite(max) ? max : undefined;

  if (pasteFn) {
    const returned = pasteFn(pasteValue);
    if (!Array.isArray(returned) || returned.length === 0) return null;
    const merged = [...currentTags];
    for (const item of returned) {
      const text = String(item).trim();
      if (!text || merged.includes(text)) continue;
      if (limit !== undefined && merged.length >= limit) break;
      merged.push(text);
    }
    return merged.length !== currentTags.length ? merged : null;
  }

  if (!separator) return null;
  const splitSep = separator === '\\n' ? /\r?\n/ : separator;
  const parts = String(pasteValue || '')
    .split(splitSep)
    .map(item => item.trim())
    .filter(Boolean);
  if (!parts.length) return null;

  const merged = [...currentTags];
  for (const item of parts) {
    if (merged.includes(item)) continue;
    if (limit !== undefined && merged.length >= limit) break;
    merged.push(item);
  }
  return merged.length !== currentTags.length ? merged : null;
}
