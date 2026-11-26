/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export type SearchSelectRecord = Record<string, any>;

export interface SearchSelectOverflowResult {
  visibleIndices: number[];
  hiddenIndices: number[];
}

export interface HighlightSegment {
  text: string;
  matched: boolean;
}

export function formatSearchChipText(
  item: SearchSelectRecord,
  options: { displayKey: string; explainCode: string; splitCode: string },
): string {
  const { displayKey, explainCode, splitCode } = options;
  const name = String(item?.[displayKey] ?? '');
  const values = Array.isArray(item?.values) ? item.values : [];
  if (!values.length) return name;
  const condition = item.condition?.[displayKey] ? String(item.condition[displayKey]) : '';
  return (
    name +
    explainCode +
    condition +
    values.map((value: SearchSelectRecord) => String(value?.[displayKey] ?? '')).join(splitCode)
  );
}

/**
 * Compute visible & hidden chip indices when blurred in single-line shrink mode.
 *
 * Rules matching V2 search-select UX:
 * - 0 chips -> nothing hidden
 * - 1 chip -> always visible (CSS ellipsis truncates single oversized chip cleanly; never shows lone "+1")
 * - All chips fit -> all visible, nothing hidden
 * - Overflow with >= 2 chips:
 *   1. Prefer leading chips 0..k-1 that fit alongside the "+N" badge.
 *   2. If chip 0 alone exceeds the budget (e.g. a very long multi-value first chip followed by a shorter recent chip),
 *      try fitting trailing chip(s) from the end so the recent chip stays readable next to "+N".
 *   3. Fallback if every individual chip exceeds the budget: keep chip 0 (CSS ellipsis) + "+N".
 */
export function computeSearchSelectOverflow(params: {
  chipWidths: number[];
  availableWidth: number;
  chipGap?: number;
  badgeWidth?: number;
}): SearchSelectOverflowResult {
  const { chipWidths, availableWidth, chipGap = 6, badgeWidth = 36 } = params;
  const count = chipWidths.length;
  if (count === 0) {
    return { visibleIndices: [], hiddenIndices: [] };
  }
  if (count === 1 || availableWidth <= 0) {
    return {
      visibleIndices: Array.from({ length: count }, (_, idx) => idx),
      hiddenIndices: [],
    };
  }

  let totalWidth = 0;
  for (let i = 0; i < count; i += 1) {
    totalWidth += chipWidths[i] + (i > 0 ? chipGap : 0);
  }
  if (totalWidth <= availableWidth) {
    return {
      visibleIndices: Array.from({ length: count }, (_, idx) => idx),
      hiddenIndices: [],
    };
  }

  const budgetWithBadge = Math.max(0, availableWidth - badgeWidth - chipGap);

  // 1. Try leading chips
  const leadingVisible: number[] = [];
  let usedWidth = 0;
  for (let i = 0; i < count - 1; i += 1) {
    const nextUsed = usedWidth + (leadingVisible.length > 0 ? chipGap : 0) + chipWidths[i];
    if (nextUsed <= budgetWithBadge) {
      leadingVisible.push(i);
      usedWidth = nextUsed;
    } else {
      break;
    }
  }
  if (leadingVisible.length > 0) {
    const visibleSet = new Set(leadingVisible);
    const hiddenIndices = Array.from({ length: count }, (_, idx) => idx).filter(idx => !visibleSet.has(idx));
    return { visibleIndices: leadingVisible, hiddenIndices };
  }

  // 2. Chip 0 is wider than budgetWithBadge — check if trailing chip(s) fit cleanly
  const trailingVisible: number[] = [];
  let tailUsed = 0;
  for (let i = count - 1; i >= 1; i -= 1) {
    const nextUsed = tailUsed + (trailingVisible.length > 0 ? chipGap : 0) + chipWidths[i];
    if (nextUsed <= budgetWithBadge) {
      trailingVisible.unshift(i);
      tailUsed = nextUsed;
    } else {
      break;
    }
  }
  if (trailingVisible.length > 0) {
    const visibleSet = new Set(trailingVisible);
    const hiddenIndices = Array.from({ length: count }, (_, idx) => idx).filter(idx => !visibleSet.has(idx));
    return { visibleIndices: trailingVisible, hiddenIndices };
  }

  // 3. Fallback: keep first chip truncated with ellipsis + remaining count
  return {
    visibleIndices: [0],
    hiddenIndices: Array.from({ length: count - 1 }, (_, idx) => idx + 1),
  };
}

export function filterSearchChildOptions(params: {
  children: SearchSelectRecord[];
  keyword: string;
  displayKey: string;
  primaryKey: string;
  hasCheckedItems?: boolean;
}): SearchSelectRecord[] {
  const { children, keyword, displayKey, primaryKey, hasCheckedItems = false } = params;
  if (!Array.isArray(children) || !children.length) return [];
  // In multiable mode, once options are checked their display names populate the input;
  // do not hide unselected options behind the checked summary string.
  if (hasCheckedItems) return children;
  const trimmed = keyword.trim().toLowerCase();
  if (!trimmed) return children;
  return children.filter((item) => {
    const displayText = String(item?.[displayKey] ?? '').toLowerCase();
    const idText = String(item?.[primaryKey] ?? '').toLowerCase();
    return displayText.includes(trimmed) || idText.includes(trimmed);
  });
}

export function buildSearchRecommendItems(params: {
  data: SearchSelectRecord[];
  keyword: string;
  displayKey: string;
  primaryKey: string;
  explainCode: string;
}): SearchSelectRecord[] {
  const { data, keyword, displayKey, primaryKey, explainCode } = params;
  const trimmed = keyword.trim().toLowerCase();
  if (!trimmed) return data || [];

  const list: SearchSelectRecord[] = [];
  (data || []).forEach((item) => {
    const children = Array.isArray(item.children) ? item.children : [];
    const matched = children.filter((child: SearchSelectRecord) => {
      const displayText = String(child?.[displayKey] ?? '').toLowerCase();
      const idText = String(child?.[primaryKey] ?? '').toLowerCase();
      return displayText.includes(trimmed) || idText.includes(trimmed);
    });
    if (matched.length) {
      matched.forEach((child: SearchSelectRecord) => {
        list.push({
          ...item,
          [displayKey]: `${item[displayKey]}${explainCode}${child[displayKey]}`,
          [primaryKey]: `${item[primaryKey]}${explainCode}${child[primaryKey]}`,
          recommendValue: {
            [displayKey]: item[displayKey],
            [primaryKey]: item[primaryKey],
            values: [{ [displayKey]: child[displayKey], [primaryKey]: child[primaryKey] }],
          },
        });
      });
      return;
    }
    const fieldName = String(item?.[displayKey] ?? '').toLowerCase();
    const fieldId = String(item?.[primaryKey] ?? '').toLowerCase();
    if (fieldName.includes(trimmed) || fieldId.includes(trimmed)) {
      list.push(item);
    }
  });
  return list;
}

export function splitHighlightSegments(text: string, keyword: string): HighlightSegment[] {
  const str = String(text ?? '');
  const trimmed = String(keyword ?? '').trim();
  if (!trimmed) return [{ text: str, matched: false }];

  const lowerStr = str.toLowerCase();
  const lowerKey = trimmed.toLowerCase();
  const idx = lowerStr.indexOf(lowerKey);
  if (idx < 0) return [{ text: str, matched: false }];

  const segments: HighlightSegment[] = [];
  if (idx > 0) segments.push({ text: str.slice(0, idx), matched: false });
  segments.push({ text: str.slice(idx, idx + trimmed.length), matched: true });
  if (idx + trimmed.length < str.length) {
    segments.push({ text: str.slice(idx + trimmed.length), matched: false });
  }
  return segments;
}
