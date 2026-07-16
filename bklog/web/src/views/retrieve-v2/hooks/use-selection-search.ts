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

import { computed, type Ref } from 'vue';

import { getRowFieldValue, isNestedField } from '@/common/util';
import LuceneSegment from '@/hooks/lucene.segment';
import useStore from '@/hooks/use-store';
import { splitRenderText } from '@/storage/utils/retrieve-render-meta';
import { getInputQueryDefaultItem } from '@/views/retrieve-v2/search-bar/utils/const.common';

export const FULLTEXT_FIELD_NAME = '*';
const SELECTION_MAX_TOKENS = 1000;
const STRUCT_FIELD_TYPES = new Set(['object', 'nested']);

/**
 * 划词 Value 默认开启「最小分词补齐」。
 * - true：按渲染分词边界，把划选补齐/拆成最小可检索分词（如 lob → lobby；lobby-178 → [lobby, 17841059990]）
 * - false：Value 直接使用划选原文 selectionText，不做最小分词补齐
 *
 * 入口配置：useSelectionSearch({ enableMinimalTokenCompletion: false })
 */
export const DEFAULT_ENABLE_MINIMAL_TOKEN_COMPLETION = true;

export type SelectionToken = {
  text: string;
  isCursorText: boolean;
  fieldName?: string;
  tokenType?: 'field-name' | 'field-value';
};

export type SelectionSearchTarget = {
  field?: Record<string, any>;
  fieldName: string;
  operator: string;
  depth?: string | number;
  isNestedField?: string;
};

export type SelectionCondition = {
  field: string;
  operator: string;
  value: string[];
  depth?: string | number;
  isNestedField?: string;
};

type HandleAddCondition = (
  field: string,
  operator: string,
  value: string[],
  isLink?: boolean,
  depth?: string | number,
  isNestedField?: string,
) => any;

type UseSelectionSearchOptions = {
  handleAddCondition: HandleAddCondition;
  getObjectValue: (row: Record<string, any>, field: Record<string, any>) => any;
  fullColumns: Ref<Record<string, any>[]>;
  showCtxType: Ref<string>;
  /**
   * 是否开启划词 Value「最小分词补齐」（默认 true）。
   * false 时回退为直接使用完整 selectionText。
   * @see DEFAULT_ENABLE_MINIMAL_TOKEN_COMPLETION
   */
  enableMinimalTokenCompletion?: boolean;
};

export const stripSelectionMarkup = (value: string) => String(value ?? '').replace(/<\/?mark>/gim, '');

export const normalizeArrayFieldPath = (path: string) => path.replace(/\.\d+(?=\.|$)/g, '');

export const isStructField = (field?: Record<string, any> | null) =>
  Boolean(field && (STRUCT_FIELD_TYPES.has(field.field_type) || field.is_virtual_obj_node));

export const isLeafQueryableField = (field?: Record<string, any> | null) =>
  Boolean(field && !isStructField(field) && field.field_type !== '__virtual__');

export const getParentFieldPath = (fieldName: string) => {
  const parts = normalizeArrayFieldPath(fieldName).split('.').filter(Boolean);
  if (parts.length <= 1) {
    return '';
  }
  return parts.slice(0, -1).join('.');
};

export const getFieldPathDepth = (fieldName: string, fallbackDepth?: string | null) => {
  if (fallbackDepth !== undefined && fallbackDepth !== null && fallbackDepth !== '') {
    return fallbackDepth;
  }
  const parts = normalizeArrayFieldPath(fieldName).split('.').filter(Boolean);
  return String(Math.max(parts.length, 1));
};

export default (options: UseSelectionSearchOptions) => {
  const store = useStore();
  const { handleAddCondition, getObjectValue, fullColumns, showCtxType } = options;
  // 划词 Value：默认最小分词补齐；传 false 可关闭并直接使用 selectionText
  const enableMinimalTokenCompletion = options.enableMinimalTokenCompletion
    ?? DEFAULT_ENABLE_MINIMAL_TOKEN_COMPLETION;

  const filteredFieldList = computed(() => store.getters.filteredFieldList ?? []);
  const visibleFields = computed(() => store.getters.visibleFields ?? []);

  const getFieldByName = (fieldName: string) => {
    if (!fieldName) {
      return undefined;
    }

    const normalizedName = normalizeArrayFieldPath(fieldName);
    return filteredFieldList.value.find(item => item.field_name === fieldName || item.field_name === normalizedName)
      ?? visibleFields.value.find(item => item.field_name === fieldName || item.field_name === normalizedName)
      ?? fullColumns.value.find(item => item.field_name === fieldName || item.field_name === normalizedName);
  };

  /**
   * 与字段展示分词保持一致：优先走 splitRenderText（whole-value / analyzed 等），
   * 无字段元信息时退化为 LuceneSegment。
   * @param forceSplit 为 true 时强制 Lucene 切分（忽略 keyword whole-value），用于最小分词补齐
   */
  const tokenizeSelectionText = (
    value: string,
    extra?: Partial<SelectionToken>,
    field?: Record<string, any>,
    forceSplit = false,
  ) => {
    const text = stripSelectionMarkup(value);
    if (!text) {
      return [] as SelectionToken[];
    }

    const splitList = field
      ? splitRenderText(text, field, forceSplit ? { forceSplit: true } : undefined)
      : LuceneSegment.split(text, SELECTION_MAX_TOKENS);

    return splitList.map(item => ({
      text: item.text,
      isCursorText: Boolean(item.isCursorText),
      ...extra,
    }));
  };

  const getFieldPlainText = (row: Record<string, any>, field: Record<string, any>) => {
    const rawValue = getRowFieldValue(row, field);
    if (rawValue === null || rawValue === undefined || rawValue === '') {
      return '--';
    }

    return stripSelectionMarkup(String(rawValue));
  };

  const getFieldSegmentTokens = (row: Record<string, any>, field: Record<string, any>) =>
    tokenizeSelectionText(getFieldPlainText(row, field), {
      fieldName: field.field_name,
      tokenType: 'field-value',
    }, field);

  /**
   * 字段 VALUE 的实际可检索分词（强制 Lucene）。
   * keyword 展示可能是 whole-value，但 JSON/Origin 渲染与检索仍按 - 等边界切开，
   * 最小分词补齐必须用这套边界，例如：
   * 0a2bddc9-5657-4949-be1b-f34541ac66f0 → [0a2bddc9, 5657, 4949, be1b, f34541ac66f0]
   */
  const getFieldLuceneTokens = (row: Record<string, any>, field: Record<string, any>) =>
    tokenizeSelectionText(getFieldPlainText(row, field), {
      fieldName: field.field_name,
      tokenType: 'field-value',
    }, field, true);

  const getOriginSegmentTokens = (row: Record<string, any>) => {
    const tokens: SelectionToken[] = [];
    const fields = visibleFields.value.length ? visibleFields.value : filteredFieldList.value;

    fields.forEach((field, index) => {
      if (index > 0) {
        tokens.push({ text: ' ', isCursorText: false });
      }

      tokens.push({
        text: field.field_name,
        isCursorText: true,
        fieldName: field.field_name,
        tokenType: 'field-name',
      });
      tokens.push({ text: ' ', isCursorText: false });
      tokens.push(...tokenizeSelectionText(getFieldPlainText(row, field), {
        fieldName: field.field_name,
        tokenType: 'field-value',
      }, field));
    });

    return tokens;
  };

  const getSelectionTextByRange = (range: Range) => stripSelectionMarkup(range?.toString?.() ?? '');

  const getSelectionAnchorElement = (range: Range) => {
    const startNode = range?.startContainer as Node | null;
    const endNode = range?.endContainer as Node | null;
    const startElement = startNode instanceof Element ? startNode : startNode?.parentElement;
    const endElement = endNode instanceof Element ? endNode : endNode?.parentElement;

    // 优先取分词叶子路径（Origin 未展开 JSON 时挂在 valid-text 上），
    // 再回退 JSON 树 data-search-field-name / data-field-name。
    // 若不优先 segment，同一次划词会因边界落在不同节点而在根字段/叶子字段之间漂移。
    return (
      startElement?.closest?.('[data-segment-field-name]')
      ?? endElement?.closest?.('[data-segment-field-name]')
      ?? startElement?.closest?.('[data-search-field-name]')
      ?? endElement?.closest?.('[data-search-field-name]')
      ?? startElement?.closest?.('[data-field-name]')
      ?? endElement?.closest?.('[data-field-name]')
    ) as HTMLElement | null;
  };

  const iterateFieldPools = (visitor: (field: Record<string, any>) => void) => {
    const pools = [filteredFieldList.value, visibleFields.value, fullColumns.value];
    const seen = new Set<string>();
    pools.forEach((pool) => {
      (pool ?? []).forEach((field) => {
        const name = field?.field_name;
        if (!name || seen.has(name)) {
          return;
        }
        seen.add(name);
        visitor(field);
      });
    });
  };

  /** Fields 列表中是否声明了 parent.xxx 子字段 */
  const hasMappedChildFields = (parentFieldName: string) => {
    if (!parentFieldName) {
      return false;
    }
    const prefix = `${normalizeArrayFieldPath(parentFieldName)}.`;
    let found = false;
    iterateFieldPools((field) => {
      if (found || !field.field_name.startsWith(prefix) || field.is_virtual_obj_node) {
        return;
      }
      if (!STRUCT_FIELD_TYPES.has(field.field_type)) {
        found = true;
      }
    });
    return found;
  };

  /**
   * 是否 Nested 检索上下文：
   * 1) Fields 列表祖先/自身 field_type === nested
   * 2) 行数据路径上存在数组（ES nested 运行时形态）
   */
  const resolveIsNestedSearchField = (fieldName: string, row: Record<string, any>) => {
    const normalized = normalizeArrayFieldPath(fieldName);
    if (!normalized) {
      return false;
    }

    const parts = normalized.split('.');
    for (let i = 1; i <= parts.length; i++) {
      const ancestor = getFieldByName(parts.slice(0, i).join('.'));
      if (ancestor?.field_type === 'nested') {
        return true;
      }
    }

    return isNestedField(parts, row);
  };

  /**
   * 在 Fields 列表中查找与划选值匹配的叶子子字段（如 __ext.bk_bcs_cluster_id）。
   */
  const findLeafFieldBySelection = (
    row: Record<string, any>,
    parentFieldName: string,
    selectionText: string,
  ) => {
    if (!parentFieldName || !selectionText) {
      return undefined;
    }

    const normalizedParent = normalizeArrayFieldPath(parentFieldName);
    const prefix = `${normalizedParent}.`;
    const candidates: Record<string, any>[] = [];

    iterateFieldPools((field) => {
      if (!field.field_name.startsWith(prefix) || !isLeafQueryableField(field)) {
        return;
      }
      candidates.push(field);
    });

    if (!candidates.length) {
      return undefined;
    }

    const normalizedSelection = stripSelectionMarkup(selectionText);

    // 稳定排序后再取最优命中，避免字段池遍历顺序变化导致同词命中不同 KEY
    const scored = candidates.map((field) => {
      const plainText = getFieldPlainText(row, field);
      if (!plainText || plainText === '--') {
        return { field, score: -1 };
      }
      if (plainText === normalizedSelection) {
        return { field, score: 1000 + plainText.length };
      }
      if (plainText.startsWith(normalizedSelection)) {
        return { field, score: 800 + normalizedSelection.length };
      }
      if (plainText.includes(normalizedSelection)) {
        return { field, score: 400 + normalizedSelection.length };
      }
      return { field, score: -1 };
    }).filter(item => item.score >= 0);

    scored.sort((a, b) => b.score - a.score
      || b.field.field_name.length - a.field.field_name.length
      || a.field.field_name.localeCompare(b.field.field_name));

    return scored[0]?.field;
  };

  /**
   * 定位划选文本在 token 序列中的相交区间 [rangeStart, rangeEnd]。
   */
  const findSelectionTokenRange = (selectionText: string, tokens: SelectionToken[]) => {
    const normalizedSelection = stripSelectionMarkup(selectionText);
    if (!normalizedSelection || !tokens.length) {
      return null;
    }

    const plainText = tokens.map(item => item.text).join('');
    const selectionStart = plainText.indexOf(normalizedSelection);
    if (selectionStart < 0) {
      return null;
    }

    const selectionEnd = selectionStart + normalizedSelection.length;
    let cursor = 0;
    let rangeStart = -1;
    let rangeEnd = -1;
    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];
      const tokenStart = cursor;
      const tokenEnd = tokenStart + token.text.length;
      cursor = tokenEnd;

      if (selectionStart < tokenEnd && selectionEnd > tokenStart) {
        if (rangeStart < 0) {
          rangeStart = i;
        }
        rangeEnd = i;
      }
    }

    if (rangeStart < 0 || rangeEnd < 0) {
      return null;
    }
    return { rangeStart, rangeEnd, normalizedSelection };
  };

  /**
   * 最小分词单位：只返回与划选相交的 isCursorText token（不跨 token 拼接）。
   * 例：lobby-178 → [lobby, 17841059990]；lob → [lobby]
   */
  const extractMinimalIntersectingCursorTokens = (selectionText: string, tokens: SelectionToken[]) => {
    const range = findSelectionTokenRange(selectionText, tokens);
    if (!range) {
      return [] as SelectionToken[];
    }

    const result: SelectionToken[] = [];
    const seen = new Set<string>();
    for (let i = range.rangeStart; i <= range.rangeEnd; i++) {
      const token = tokens[i];
      if (!token.isCursorText || !token.text || token.tokenType === 'field-name') {
        continue;
      }
      const key = [token.fieldName ?? '', token.text].join('__');
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      result.push({
        text: token.text,
        isCursorText: true,
        fieldName: token.fieldName,
        tokenType: token.tokenType ?? 'field-value',
      });
    }
    return result;
  };

  /**
   * 将划选范围补全到完整分词边界（可跨相邻 token 拼接，兼容旧行为）。
   */
  const completeSelectionByTokens = (selectionText: string, tokens: SelectionToken[]) => {
    const range = findSelectionTokenRange(selectionText, tokens);
    if (!range) {
      return [] as SelectionToken[];
    }

    const { rangeStart, rangeEnd } = range;

    const flushGroup = (start: number, end: number, bucket: SelectionToken[], dedupeSet: Set<string>) => {
      let from = start;
      let to = end;
      while (from <= to && !tokens[from].isCursorText) {
        from += 1;
      }
      while (to >= from && !tokens[to].isCursorText) {
        to -= 1;
      }
      if (from > to) {
        return;
      }

      const firstCursor = tokens.slice(from, to + 1).find(item => item.isCursorText);
      if (!firstCursor || firstCursor.tokenType === 'field-name') {
        return;
      }

      const text = tokens.slice(from, to + 1).map(item => item.text).join('');
      if (!text) {
        return;
      }

      const tokenKey = [firstCursor.fieldName ?? '', firstCursor.tokenType ?? '', text].join('__');
      if (dedupeSet.has(tokenKey)) {
        return;
      }
      dedupeSet.add(tokenKey);
      bucket.push({
        text,
        isCursorText: true,
        fieldName: firstCursor.fieldName,
        tokenType: firstCursor.tokenType ?? 'field-value',
      });
    };

    const completedTokens: SelectionToken[] = [];
    const appendedTokenSet = new Set<string>();
    let groupStart = rangeStart;
    for (let i = rangeStart; i <= rangeEnd; i++) {
      if (tokens[i].tokenType === 'field-name') {
        if (i > groupStart) {
          flushGroup(groupStart, i - 1, completedTokens, appendedTokenSet);
        }
        groupStart = i + 1;
      }
    }
    if (groupStart <= rangeEnd) {
      flushGroup(groupStart, rangeEnd, completedTokens, appendedTokenSet);
    }

    return completedTokens;
  };

  /**
   * 划词 Value 解析：
   * - enableMinimalTokenCompletion=true（默认）：相对字段完整 VALUE 的 Lucene 分词边界，
   *   把划选补齐到相交的最小 cursor token。
   *   例：划选 0a2bddc9-5 → [0a2bddc9, 5657]（完整值为 0a2bddc9-5657-...）
   * - false：直接返回 [selectionText]
   *
   * 注意：不能用 keyword 的 whole-value 展示分词（整段 1 token）做补齐判断，
   * 否则会把 0a2bddc9-5 原样当作 Value，无法拆到 0a2bddc9 / 5657。
   */
  const resolveSelectionValues = (
    selectionText: string,
    field?: Record<string, any>,
    row?: Record<string, any>,
  ): string[] => {
    const raw = stripSelectionMarkup(selectionText).trim();
    if (!raw) {
      return [];
    }

    if (!enableMinimalTokenCompletion) {
      return [raw];
    }

    if (field && row) {
      const plain = getFieldPlainText(row, field);
      if (plain === raw) {
        return [plain];
      }

      // 1) 优先：相对完整 VALUE 的 Lucene 分词做相交补齐（与渲染/检索边界一致）
      const luceneTokens = getFieldLuceneTokens(row, field);
      const luceneCursorCount = luceneTokens.filter(token => token.isCursorText && token.text).length;
      if (luceneCursorCount > 1) {
        const minimal = extractMinimalIntersectingCursorTokens(raw, luceneTokens);
        if (minimal.length) {
          return minimal.map(token => token.text);
        }
      }

      // 2) 回退：展示层多分词（analyzed 等）
      const fieldTokens = getFieldSegmentTokens(row, field);
      const displayCursorCount = fieldTokens.filter(token => token.isCursorText && token.text).length;
      if (displayCursorCount > 1) {
        const minimal = extractMinimalIntersectingCursorTokens(raw, fieldTokens);
        if (minimal.length) {
          return minimal.map(token => token.text);
        }
      }

      // 3) 对划选文本自身强制 Lucene 拆分（避免 keyword whole-value 把原文黏成 1 token）
      const selfTokens = tokenizeSelectionText(raw, {
        fieldName: field.field_name,
        tokenType: 'field-value',
      }, field, true).filter(token => token.isCursorText && token.text);
      if (selfTokens.length) {
        return selfTokens.map(token => token.text);
      }
    } else if (field) {
      const selfTokens = tokenizeSelectionText(raw, {
        fieldName: field.field_name,
        tokenType: 'field-value',
      }, field, true).filter(token => token.isCursorText && token.text);
      if (selfTokens.length) {
        return selfTokens.map(token => token.text);
      }
    } else {
      const selfTokens = LuceneSegment.split(raw, SELECTION_MAX_TOKENS)
        .filter(item => item.isCursorText && item.text);
      if (selfTokens.length) {
        return selfTokens.map(item => item.text);
      }
    }

    return [raw];
  };

  /**
   * 划选检索目标解析（以 Fields 列表为权威）：
   * 1) 简单叶子字段整段划选：KEY = VALUE
   * 2) String/JSON String 部分划选：KEY 包含（由上游 string 分支处理分词，此处仅给出字段）
   * 3) Object + Fields 声明 KEY.SubKey：KEY.SubKey = VALUE（可补全）
   * 4) Nested + Fields 声明 KEY.SubKey：KEY.SubKey = VALUE，并透传 isNestedField/depth
   */
  const resolveSelectionSearchTarget = (
    row: Record<string, any>,
    selectionText: string,
    targetElement: HTMLElement | null,
  ): SelectionSearchTarget => {
    const searchFieldName = targetElement?.getAttribute('data-search-field-name') ?? '';
    const domFieldName = targetElement?.getAttribute('data-field-name') ?? '';
    const candidateFieldName = searchFieldName || domFieldName;
    const depthFromDom = targetElement?.closest?.('[data-depth]')?.getAttribute('data-depth');

    const buildTarget = (
      field: Record<string, any> | undefined,
      fieldName: string,
      operator: string,
      nestedFlag?: boolean,
    ): SelectionSearchTarget => {
      const finalName = field?.field_name || fieldName;
      const isNested = nestedFlag ?? resolveIsNestedSearchField(finalName, row);
      return {
        field,
        fieldName: finalName,
        operator,
        depth: getFieldPathDepth(finalName, depthFromDom),
        isNestedField: isNested ? 'true' : 'false',
      };
    };

    if (!candidateFieldName) {
      return buildTarget(undefined, FULLTEXT_FIELD_NAME, 'contains match phrase', false);
    }

    let targetField = getFieldByName(candidateFieldName);

    const shouldResolveLeaf = isStructField(targetField)
      || !targetField
      || hasMappedChildFields(candidateFieldName);

    if (shouldResolveLeaf) {
      const directLeaf = isLeafQueryableField(targetField) ? targetField : undefined;
      const leafFromCandidate = directLeaf
        ?? findLeafFieldBySelection(row, candidateFieldName, selectionText);

      if (leafFromCandidate) {
        targetField = leafFromCandidate;
      } else if (!targetField && candidateFieldName.includes('.')) {
        const parentPath = getParentFieldPath(candidateFieldName);
        if (parentPath && hasMappedChildFields(parentPath)) {
          targetField = findLeafFieldBySelection(row, parentPath, selectionText);
        }
      } else if (isStructField(targetField) && hasMappedChildFields(targetField.field_name)) {
        targetField = findLeafFieldBySelection(row, targetField.field_name, selectionText) ?? targetField;
      }
    }

    if (isLeafQueryableField(targetField)) {
      const plainText = getFieldPlainText(row, targetField);
      const nestedFlag = resolveIsNestedSearchField(targetField.field_name, row);

      // 与点击分词 / resolveFieldSelectionOperator 对齐：完整 VALUE → is，否则 contains。
      // 禁止再对 mapped child 无条件 is，否则同词多次划选会在等于/包含间漂移。
      if (plainText === selectionText) {
        return buildTarget(targetField, targetField.field_name, 'is', nestedFlag);
      }

      return buildTarget(targetField, targetField.field_name, 'contains match phrase', nestedFlag);
    }

    if (isStructField(targetField)) {
      const nestedFlag = targetField.field_type === 'nested'
        || resolveIsNestedSearchField(targetField.field_name, row);
      return buildTarget(targetField, targetField.field_name, 'contains match phrase', nestedFlag);
    }

    return buildTarget(undefined, candidateFieldName || FULLTEXT_FIELD_NAME, 'contains match phrase', false);
  };

  /**
   * 列出 Fields 中声明的可检索叶子子字段。
   */
  const listChildLeafFields = (parentFieldName: string) => {
    if (!parentFieldName) {
      return [] as Record<string, any>[];
    }

    const prefix = `${normalizeArrayFieldPath(parentFieldName)}.`;
    const candidates: Record<string, any>[] = [];
    iterateFieldPools((field) => {
      if (!field.field_name.startsWith(prefix) || !isLeafQueryableField(field)) {
        return;
      }
      candidates.push(field);
    });
    return candidates;
  };

  const buildConditionFromFieldWithRow = (
    field: Record<string, any>,
    value: string,
    row: Record<string, any>,
    operator = 'is',
  ): SelectionCondition => {
    const nestedFlag = resolveIsNestedSearchField(field.field_name, row);
    return {
      field: field.field_name,
      operator,
      value: [value],
      depth: getFieldPathDepth(field.field_name),
      isNestedField: nestedFlag ? 'true' : 'false',
    };
  };

  const dedupeSelectionConditions = (conditions: SelectionCondition[]) => {
    const result: SelectionCondition[] = [];
    const seen = new Set<string>();
    conditions.forEach((item) => {
      const key = [item.field, item.operator, item.value.join('\u0001'), item.isNestedField ?? 'false'].join('__');
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      result.push(item);
    });
    return result;
  };

  /**
   * 收集与划选 Range 相交的检索路径节点（JSON 树 / 字段单元格）。
   */
  const collectIntersectedSearchNodes = (range: Range) => {
    const startNode = range.startContainer as Node;
    const endNode = range.endContainer as Node;
    const startElement = startNode instanceof Element ? startNode : startNode.parentElement;
    const endElement = endNode instanceof Element ? endNode : endNode.parentElement;
    const root = (range.commonAncestorContainer instanceof Element
      ? range.commonAncestorContainer
      : range.commonAncestorContainer.parentElement)
      ?? startElement
      ?? endElement;

    if (!root) {
      return [] as HTMLElement[];
    }

    const container = root.closest?.(
      '.bklog-json-formatter-root, .bklog-column-wrapper, .bklog-json-view-object, .bklog-json-view-child',
    ) ?? root;

    const nodes = Array.from(
      container.querySelectorAll?.('[data-search-field-name], [data-field-name]') ?? [],
    ) as HTMLElement[];

    // 自身也可能带属性
    if (container instanceof HTMLElement
      && (container.hasAttribute('data-search-field-name') || container.hasAttribute('data-field-name'))) {
      nodes.unshift(container);
    }

    return nodes.filter((el) => {
      try {
        return range.intersectsNode(el);
      } catch {
        return false;
      }
    });
  };

  const resolveFieldPathFromElement = (el: HTMLElement) => {
    const segmentPath = el.getAttribute('data-segment-field-name')
      ?? el.closest?.('[data-segment-field-name]')?.getAttribute('data-segment-field-name')
      ?? '';
    const searchPath = el.getAttribute('data-search-field-name')
      ?? el.closest?.('[data-search-field-name]')?.getAttribute('data-search-field-name')
      ?? '';
    const fieldPath = el.getAttribute('data-field-name')
      ?? el.closest?.('[data-field-name]')?.getAttribute('data-field-name')
      ?? '';
    // 分词叶子路径优先，避免未展开 JSON 场景下始终回落到根字段（如 __ext）
    return segmentPath || searchPath || fieldPath;
  };

  /**
   * 将短 KEY（如 io_kubernetes_workload_name）解析为 Fields 中的完整路径。
   */
  const resolveFieldByKeyHint = (keyHint: string, parentHint = '', row?: Record<string, any>, valueHint = '') => {
    if (!keyHint) {
      return undefined;
    }

    const normalizedHint = normalizeArrayFieldPath(keyHint);
    const exact = getFieldByName(normalizedHint);
    if (isLeafQueryableField(exact)) {
      return exact;
    }

    if (parentHint) {
      const prefixed = `${normalizeArrayFieldPath(parentHint)}.${normalizedHint}`;
      const byParent = getFieldByName(prefixed);
      if (isLeafQueryableField(byParent)) {
        return byParent;
      }

      const child = listChildLeafFields(parentHint).find((field) => {
        const name = field.field_name;
        return name === prefixed
          || name.endsWith(`.${normalizedHint}`)
          || name.split('.').pop() === normalizedHint;
      });
      if (child) {
        return child;
      }
    }

    // 跨边界划选时 KEY 往往只有尾部。先按 KEY 相似度筛选，再用 VALUE 片段消歧，避免 dsa-1 误命中所有值为 dsa 的字段。
    const keyText = normalizedHint.toLowerCase().replace(/^_+/, '');
    const candidates: Array<{ field: Record<string, any>; score: number }> = [];
    iterateFieldPools((field) => {
      if (!isLeafQueryableField(field)) return;
      const leaf = field.field_name.split('.').pop()?.toLowerCase() ?? '';
      const keyScore = leaf === keyText ? 1000 : leaf.endsWith(keyText) ? 800 : leaf.includes(keyText) ? 500 : 0;
      if (!keyScore) return;
      const plain = row ? getFieldPlainText(row, field) : '';
      const valueScore = valueHint && plain && plain !== '--'
        ? (plain === valueHint ? 300 : plain.startsWith(valueHint) ? 200 : plain.includes(valueHint) ? 50 : 0)
        : 0;
      candidates.push({ field, score: keyScore + valueScore });
    });
    candidates.sort((a, b) => b.score - a.score || b.field.field_name.length - a.field.field_name.length);
    return candidates[0]?.field;
  };

  /**
   * 清洗划选碎片（去掉引号、冒号、逗号等 JSON 边界符）。
   */
  const sanitizeSelectionFragment = (raw: string) =>
    stripSelectionMarkup(raw)
      .replace(/^["'\s|,:{[\]\\]+/, '')
      .replace(/["'\s|,}\]\\]+$/g, '')
      .trim();

  /**
   * 判断划选文本是否与字段 VALUE 有实质重叠（完整值 / 前后缀截断）。
   * 仅 KEY 擦边不算。
   */
  const hasFieldValueOverlap = (selectionText: string, plainText: string) => {
    if (!plainText || plainText === '--' || !selectionText) {
      return false;
    }
    // 短值是更长 VALUE 的前缀时，不算 VALUE 重叠：
    // `_pod":"dsa-1` 不能把实际值为 `dsa` 的 container_name/labels.app 等字段带入。
    const selectionFragments = selectionText
      .split(/(?:["'\s|,:{}]|\[|\])+/)
      .map(item => item.trim())
      .filter(Boolean);
    if (selectionFragments.some(fragment => fragment.length > plainText.length && fragment.startsWith(plainText))) {
      return false;
    }
    if (selectionText.includes(plainText) || plainText === selectionText) {
      return true;
    }

    const minLen = Math.min(4, plainText.length);
    if (plainText.length < minLen) {
      return false;
    }

    // 提取划选中的候选 value 碎片（去掉 JSON 标点）
    const fragments = selectionText
      .split(/(?:["'\s|,:{}]|\[|\])+/)
      .map(item => item.trim())
      .filter(item => item.length >= minLen);

    return fragments.some((fragment) => {
      if (plainText === fragment || plainText.includes(fragment)) {
        // 碎片是完整值的真子串；过短且更像 KEY 前缀时，交给 KEY 判定过滤
        return fragment.length >= Math.min(8, Math.max(4, Math.floor(plainText.length / 4)))
          || plainText.endsWith(fragment)
          || plainText.startsWith(fragment);
      }
      return false;
    });
  };

  /**
   * 用部分 value（跨字段划选时开头/结尾被截断的片段）回落完整叶子字段。
   * 优先最长后缀命中，避免短碎片误匹配。
   */
  const findLeafFieldByPartialValue = (
    row: Record<string, any>,
    parentHint: string,
    partialValue: string,
  ) => {
    const fragment = sanitizeSelectionFragment(partialValue);
    if (!fragment || fragment.length < 2) {
      return undefined;
    }

    const scopes = parentHint
      ? listChildLeafFields(parentHint)
      : (() => {
        const all: Record<string, any>[] = [];
        iterateFieldPools((field) => {
          if (isLeafQueryableField(field)) {
            all.push(field);
          }
        });
        return all;
      })();

    type ScoreHit = { field: Record<string, any>; score: number };
    const hits: ScoreHit[] = [];

    scopes.forEach((field) => {
      const plain = getFieldPlainText(row, field);
      if (!plain || plain === '--') {
        return;
      }
      if (plain === fragment) {
        hits.push({ field, score: 1000 + plain.length });
        return;
      }
      if (plain.endsWith(fragment)) {
        hits.push({ field, score: 800 + fragment.length });
        return;
      }
      if (plain.startsWith(fragment) && fragment.length >= 4) {
        hits.push({ field, score: 600 + fragment.length });
        return;
      }
      if (plain.includes(fragment) && fragment.length >= Math.min(8, Math.max(4, Math.floor(plain.length / 4)))) {
        hits.push({ field, score: 400 + fragment.length });
      }
    });

    if (!hits.length) {
      return undefined;
    }

    hits.sort((a, b) => b.score - a.score);
    return hits[0].field;
  };

  /**
   * 判断碎片是否是“残缺 KEY”（某字段末级名的真前缀），且不是某个 VALUE 的截断。
   * 例如 container_im → container_image，应丢弃。
   */
  const isDanglingFieldKeyPrefix = (
    row: Record<string, any>,
    parentHint: string,
    fragment: string,
  ) => {
    const cleaned = sanitizeSelectionFragment(fragment);
    if (!cleaned || cleaned.length < 2) {
      return false;
    }

    // 若能当作 VALUE 截断命中，则不是残缺 KEY
    if (findLeafFieldByPartialValue(row, parentHint, cleaned)) {
      return false;
    }

    const scopes = parentHint
      ? listChildLeafFields(parentHint)
      : (() => {
        const all: Record<string, any>[] = [];
        iterateFieldPools((field) => {
          if (isLeafQueryableField(field)) {
            all.push(field);
          }
        });
        return all;
      })();

    return scopes.some((field) => {
      const shortKey = field.field_name.split('.').pop() ?? '';
      return Boolean(shortKey)
        && shortKey !== cleaned
        && shortKey.startsWith(cleaned)
        && cleaned.length < shortKey.length;
    });
  };

  /**
   * 从划选文本中解析 JSON / JSON 树 UI 的 key:value 片段。
   * 兼容：
   * - "key":"value" / "key": 123
   * - key:value（json-view 展开后的纯文本）
   * 注意：残缺 KEY（无冒号/无 value）不会进入结果，由尾部 orphan 逻辑丢弃。
   */
  const parseJsonKvPairsFromText = (selectionText: string) => {
    const pairs: Array<{ key: string; value: string; index: number; end: number }> = [];
    const seenSpans = new Set<string>();

    const pushPair = (key: string, value: string, index: number, end: number) => {
      const spanKey = `${index}:${end}`;
      if (!key || value === undefined || value === null || seenSpans.has(spanKey)) {
        return;
      }
      // value 为空或仍是残缺引号，视为无效 KV
      const normalizedValue = String(value).trim();
      if (!normalizedValue) {
        return;
      }
      seenSpans.add(spanKey);
      pairs.push({ key, value: normalizedValue, index, end });
    };

    const quotedRegex = /"([^"\\]+)"\s*:\s*(?:"((?:\\.|[^"\\])*)"|(-?\d+(?:\.\d+)?|true|false|null))/gi;
    let match = quotedRegex.exec(selectionText);
    while (match) {
      pushPair(
        match[1],
        match[2] !== undefined ? match[2].replace(/\\"/g, '"') : match[3],
        match.index,
        quotedRegex.lastIndex,
      );
      match = quotedRegex.exec(selectionText);
    }

    // 跨边界划选允许 VALUE 尚未选到结束引号，例如选中内容以 "_pod":"dsa-1 结尾。
    const partialQuotedRegex = /"([^"\\]+)"\s*:\s*"((?:\\.|[^"\\])*)$/g;
    match = partialQuotedRegex.exec(selectionText);
    while (match) {
      pushPair(match[1], match[2].replace(/\\"/g, '"'), match.index, partialQuotedRegex.lastIndex);
      match = partialQuotedRegex.exec(selectionText);
    }

    // 选区可能从 KEY 的左引号之后开始：`_pod":"dsa-1`。
    // 注意：这里是正则字面量，空白必须写成 `\s`，不能写成 `\\s`。
    const partialKeyQuotedRegex = /(?:^|[\s|,{[])_?([A-Za-z0-9_.-]+)"?\s*:\s*"((?:\\.|[^"\\])*)$/g;
    match = partialKeyQuotedRegex.exec(selectionText);
    while (match) {
      pushPair(match[1], match[2].replace(/\\"/g, '"'), match.index + match[0].indexOf(match[1]), partialKeyQuotedRegex.lastIndex);
      match = partialKeyQuotedRegex.exec(selectionText);
    }

    // json-view 渲染：key:value（无引号 KEY）
    const plainRegex = /(^|[\s|{[,])([A-Za-z_][\w.-]*)\s*:\s*(?:"((?:\\.|[^"\\])*)"|([^\s,}\]"']+))/g;
    match = plainRegex.exec(selectionText);
    while (match) {
      const key = match[2];
      const value = match[3] !== undefined ? match[3].replace(/\\"/g, '"') : match[4];
      const index = match.index + match[1].length;
      pushPair(key, value, index, plainRegex.lastIndex);
      match = plainRegex.exec(selectionText);
    }

    return pairs.sort((a, b) => a.index - b.index);
  };

  /**
   * 拆出划选中的 leading / trailing orphan 碎片（跨字段边界两侧被截断的部分）。
   */
  const extractBoundaryOrphans = (selectionText: string, kvPairs: Array<{ index: number; end: number }>) => {
    if (kvPairs.length) {
      const leading = sanitizeSelectionFragment(selectionText.slice(0, kvPairs[0].index));
      const trailing = sanitizeSelectionFragment(selectionText.slice(kvPairs[kvPairs.length - 1].end));
      return { leading, trailing };
    }

    // 无完整 KV：按 JSON 边界拆，例如 value碎片","key碎片
    const boundarySplit = selectionText.split(/"\s*,\s*"?|,\s*"/);
    if (boundarySplit.length >= 2) {
      return {
        leading: sanitizeSelectionFragment(boundarySplit[0]),
        trailing: sanitizeSelectionFragment(boundarySplit[boundarySplit.length - 1]),
      };
    }

    return {
      leading: sanitizeSelectionFragment(selectionText),
      trailing: '',
    };
  };

  const inferParentHintFromPaths = (paths: string[]) => {
    const normalized = paths.map(normalizeArrayFieldPath).filter(Boolean);
    if (!normalized.length) {
      return '';
    }

    // 取公共父路径；若只有叶子路径，取其父级
    const splitPaths = normalized.map(path => path.split('.'));
    const minLen = Math.min(...splitPaths.map(parts => parts.length));
    const common: string[] = [];
    for (let i = 0; i < minLen; i++) {
      const part = splitPaths[0][i];
      if (splitPaths.every(parts => parts[i] === part)) {
        common.push(part);
      } else {
        break;
      }
    }

    if (common.length && common.length < Math.max(...splitPaths.map(parts => parts.length))) {
      return common.join('.');
    }

    if (normalized.length === 1 && normalized[0].includes('.')) {
      return getParentFieldPath(normalized[0]);
    }

    // 多数叶子共享同一父级
    const parents = normalized
      .map(getParentFieldPath)
      .filter(Boolean);
    if (parents.length) {
      const counter = new Map<string, number>();
      parents.forEach((parent) => counter.set(parent, (counter.get(parent) ?? 0) + 1));
      return [...counter.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? '';
    }

    return '';
  };

  const isCrossFieldSelectionText = (selectionText: string, pathCount: number, kvCount: number) => {
    if (pathCount >= 2 || kvCount >= 1) {
      return true;
    }
    // value","key / key":"value 等跨字段边界
    return /","|"\s*,\s*"?|":\s*"?|(?:^|[\s|{[,])[A-Za-z_][\w.-]*\s*:/.test(selectionText);
  };

  /**
   * 运行时 VALUE 为 String（含 JSON String）：Fields 无子字段映射。
   */
  const isStringRuntimeValue = (field: Record<string, any> | undefined, row: Record<string, any>) => {
    if (!isLeafQueryableField(field) || hasMappedChildFields(field.field_name)) {
      return false;
    }
    return typeof getRowFieldValue(row, field) === 'string';
  };

  /**
   * 运行时 VALUE 为 Object/Array，或 Fields 声明了结构化子字段。
   * 此类即便 UI 以字符串/JSON 树展示，划词仍允许补全。
   */
  const isObjectRuntimeValue = (field: Record<string, any> | undefined, row: Record<string, any>) => {
    if (!field) {
      return false;
    }
    if (hasMappedChildFields(field.field_name) || isStructField(field)) {
      return true;
    }
    const rawValue = getRowFieldValue(row, field);
    return rawValue !== null && typeof rawValue === 'object';
  };

  const resolveStringFieldContext = (range: Range, row: Record<string, any>) => {
    const targetElement = getSelectionAnchorElement(range);
    const candidatePath = normalizeArrayFieldPath(
      targetElement?.getAttribute('data-segment-field-name')
      ?? targetElement?.getAttribute('data-search-field-name')
      ?? targetElement?.getAttribute('data-field-name')
      ?? '',
    );

    const directField = getFieldByName(candidatePath);
    // JSON String 解析节点：data-search-field-name 已是外层字段，且原始 VALUE 为 string
    if (isStringRuntimeValue(directField, row)) {
      return directField;
    }

    const paths = [...new Set(
      collectIntersectedSearchNodes(range)
        .map(resolveFieldPathFromElement)
        .map(normalizeArrayFieldPath)
        .filter(Boolean),
    )];

    for (const path of paths) {
      const field = getFieldByName(path);
      if (isStringRuntimeValue(field, row)) {
        return field;
      }
      const parentField = getFieldByName(getParentFieldPath(path));
      if (isStringRuntimeValue(parentField, row)) {
        return parentField;
      }
    }

    return undefined;
  };

  /**
   * 仅对划选文本本身分词（与渲染分词一致），不做相对整段 VALUE 的边界补全。
   */
  const tokenizeSelectionTextOnly = (selectionText: string, field: Record<string, any>) =>
    tokenizeSelectionText(selectionText, {
      fieldName: field.field_name,
      tokenType: 'field-value',
    }, field).filter(token => token.isCursorText && token.text);

  /**
   * 字段整段 VALUE 的可检索分词（与渲染分词一致）。
   */
  const getFieldCursorTokens = (row: Record<string, any>, field: Record<string, any>) =>
    getFieldSegmentTokens(row, field).filter(token => token.isCursorText && token.text);

  /**
   * String / JSON String：
   * - 划选整段 VALUE → KEY is VALUE
   * - 部分划选：按 enableMinimalTokenCompletion 决定 Value 是最小分词还是 selectionText 原文
   */
  const resolveStringContainsConditions = (
    range: Range,
    row: Record<string, any>,
    field: Record<string, any>,
  ): SelectionCondition[] => {
    const selectionText = getSelectionTextByRange(range);
    if (!selectionText) {
      return [];
    }

    const plain = getFieldPlainText(row, field);
    const nestedFlag = resolveIsNestedSearchField(field.field_name, row);
    const base = {
      field: field.field_name,
      depth: getFieldPathDepth(field.field_name),
      isNestedField: nestedFlag ? 'true' : 'false',
    };

    // 整段划选 → 等值
    if (plain === selectionText) {
      return [{
        ...base,
        operator: 'is',
        value: [plain],
      }];
    }

    const values = resolveSelectionValues(selectionText, field, row);
    return values.map(token => ({
      ...base,
      operator: 'contains match phrase',
      value: [token],
    }));
  };

  /**
   * 跨字段划选智能解析（仅 Object/Nested，允许补全）：
   * 1) DOM 相交叶子：必须有 VALUE 重叠证据才采纳（仅擦到 KEY 前缀则丢弃）
   * 2) 完整 "key":"value" / key:value → 补齐完整字段值
   * 3) leading VALUE 截断碎片 → 补齐；trailing 残缺 KEY → 丢弃
   * 4) 跨边界场景下，即使只解析出 1 条有效条件也返回（如只补齐 container_id）
   */
  const resolvePartialValueTokens = (field: Record<string, any>, row: Record<string, any>, valueHint: string) => {
    const plain = getFieldPlainText(row, field);
    if (!plain || plain === '--' || !valueHint) return '';
    const fullTokens = getFieldSegmentTokens(row, field).filter(token => token.isCursorText && token.text);
    const selectedTokens = tokenizeSelectionText(valueHint).filter(token => token.isCursorText && token.text);
    if (!fullTokens.length || !selectedTokens.length) return '';
    let matched = -1;
    for (let i = 0; i <= fullTokens.length - selectedTokens.length; i++) {
      if (selectedTokens.every((token, j) => fullTokens[i + j].text.startsWith(token.text))) {
        matched = i + selectedTokens.length - 1;
        break;
      }
    }
    if (matched < 0) return '';
    const endToken = fullTokens[matched].text;
    const end = plain.indexOf(endToken) + endToken.length;
    return endToken && end > endToken.length ? plain.slice(0, end) : endToken;
  };

  const resolveMultiFieldSelectionConditions = (
    range: Range,
    row: Record<string, any>,
  ): SelectionCondition[] => {
    const selectionText = getSelectionTextByRange(range);
    if (!selectionText) {
      return [];
    }

    const intersectedNodes = collectIntersectedSearchNodes(range);
    const pathInfos = intersectedNodes.map((el) => {
      const path = resolveFieldPathFromElement(el);
      return {
        path: normalizeArrayFieldPath(path),
        parsedFromJsonString: el.closest?.('[data-json-string-parsed="true"]') != null
          || el.getAttribute('data-json-string-parsed') === 'true',
      };
    }).filter(item => item.path);

    const uniquePaths = [...new Set(pathInfos.map(item => item.path))];
    const anchorPath = getSelectionAnchorElement(range)?.getAttribute('data-search-field-name') ?? '';
    const anchorField = getFieldByName(anchorPath);
    // 补全仅针对 Object 类型（含 Fields 子字段 / 运行时 object）；String/JSON String 不走此分支
    const objectContextField = [anchorField, ...uniquePaths.map(path => getFieldByName(path))]
      .find(field => isObjectRuntimeValue(field, row));
    if (!objectContextField) {
      return [];
    }

    const parentHint = inferParentHintFromPaths(uniquePaths)
      || getParentFieldPath(anchorPath)
      || (hasMappedChildFields(anchorPath) ? anchorPath : '')
      || objectContextField.field_name
      || '';

    const conditions: SelectionCondition[] = [];
    const appendedFields = new Set<string>();
    // 一旦解析出 KV，KEY 是唯一字段判定依据；禁止再用相交 DOM/value 全局反查，
    // 否则同值字段（如 container_name、labels.app）会被误加进来。
    const kvPairs = parseJsonKvPairsFromText(selectionText);

    /**
     * 根据字段完整 VALUE 与本次命中的 VALUE 计算操作符。
     *
     * 不能仅因为字段最终补全出了完整 VALUE 就使用 is：Object/Nested 的 VALUE
     * 可能被渲染为多个可检索分词，例如 `dsa-17841304550` -> [`dsa`, `17841304550`]。
     * 此时点击/划选其中一个分词，应保留命中的分词并使用 contains match phrase。
     * 只有命中完整 VALUE（例如 `FieldName1: Field Value` 中的完整值）才使用 is。
     */
    const resolveFieldSelectionOperator = (
      field: Record<string, any>,
      selectedValue: string,
    ): { value: string; operator: string } => {
      const plain = getFieldPlainText(row, field);
      const value = stripSelectionMarkup(selectedValue).trim();
      if (!value || value === '--') {
        return { value: '', operator: 'is' };
      }
      if (plain === value) {
        return { value: plain, operator: 'is' };
      }

      const tokenCount = getFieldCursorTokens(row, field).length;
      // 多分词字段：命中单个/部分分词只能表达包含关系，不能表达字段等值。
      if (tokenCount > 1) {
        return { value, operator: 'contains match phrase' };
      }

      // 单分词字段的部分划选也不能误升级为等值。
      return { value, operator: 'contains match phrase' };
    };

    const pushFieldValue = (field?: Record<string, any>, rawValue?: string) => {
      if (!isLeafQueryableField(field)) {
        return;
      }
      const selectedValue = rawValue && rawValue !== '--'
        ? stripSelectionMarkup(rawValue)
        : getFieldPlainText(row, field);
      const values = resolveSelectionValues(selectedValue, field, row);
      values.forEach((tokenValue) => {
        const resolved = resolveFieldSelectionOperator(field, tokenValue);
        if (!resolved.value) {
          return;
        }
        const conditionKey = [field.field_name, resolved.operator, resolved.value].join('__');
        if (appendedFields.has(conditionKey)) {
          return;
        }
        appendedFields.add(conditionKey);
        // 兼容旧逻辑：同一字段仍用 field_name 占位，避免后续 setFieldCondition 漏判
        appendedFields.add(field.field_name);
        conditions.push(buildConditionFromFieldWithRow(field, resolved.value, row, resolved.operator));
      });
    };

    // 同一个字段只能生成一个条件。DOM 命中和文本 KV 解析可能同时命中同一叶子字段，
    // 显式 KV（尤其是部分 VALUE）优先级更高，需要替换此前由 DOM 推断出的条件。
    const setFieldCondition = (field: Record<string, any>, value: string, operator: string) => {
      if (!isLeafQueryableField(field) || !value || value === '--') {
        return;
      }
      const index = conditions.findIndex(item => item.field === field.field_name);
      const condition = buildConditionFromFieldWithRow(field, value, row, operator);
      if (index >= 0) {
        conditions.splice(index, 1, condition);
      } else {
        conditions.push(condition);
      }
      appendedFields.add(field.field_name);
    };

    /**
     * 从 selection 中提取当前 DOM 字段真正命中的 VALUE。
     * 不能直接把整段字段 VALUE 传给 pushFieldValue，否则点击 `dsa` 会被
     * 当成完整值 `dsa-17841304550`，最终错误生成 `is`。
     */
    const getSelectedFieldValue = (field: Record<string, any>) => {
      const plain = getFieldPlainText(row, field);
      if (!plain || plain === '--') return '';
      if (selectionText.includes(plain)) return plain;

      const selectedTokens = getFieldCursorTokens(row, field)
        .filter(token => selectionText.includes(token.text));
      if (selectedTokens.length) {
        return selectedTokens.map(token => token.text).join(' ');
      }

      // DOM 命中有时拿到的是截断文本（例如 dsa-178），保留命中片段，
      // 由 resolveFieldSelectionOperator 按字段分词数决定 contains/is。
      const fragments = tokenizeSelectionText(selectionText)
        .filter(token => token.isCursorText && token.text && plain.includes(token.text));
      return fragments.map(token => token.text).join(' ');
    };

    // 1) DOM 相交叶子：必须有 VALUE 证据；只碰到 KEY/KEY 前缀则丢弃
    if (!kvPairs.length) {
      uniquePaths.forEach((path) => {
        const field = getFieldByName(path);
        if (!isLeafQueryableField(field)) {
          return;
        }
        const plain = getFieldPlainText(row, field);
        if (hasFieldValueOverlap(selectionText, plain)) {
          // 最小分词模式直接用 selectionText，由 resolveSelectionValues 拆最小单位；
          // 关闭时沿用 getSelectedFieldValue 的旧拼接结果。
          pushFieldValue(
            field,
            enableMinimalTokenCompletion ? selectionText : (getSelectedFieldValue(field) || selectionText),
          );
        }
      });
    }

    // 相交到 object/nested 父节点，且有效叶子不足时，按 VALUE/完整 KV 回落。
    // 已解析出 KV 时必须以 KEY 唯一解析结果为准，禁止再按 VALUE 扩散到同值字段。
    // 注意：部分 VALUE 命中时必须带上 selection 原文，不能直接塞完整 plain，
    // 否则同词（如 lobby）会因命中多个同值字段而每次 KEY/operator 不一致。
    if (!kvPairs.length && conditions.length < 2) {
      uniquePaths.forEach((path) => {
        const field = getFieldByName(path);
        if (!(hasMappedChildFields(path) || isStructField(field))) {
          return;
        }
        listChildLeafFields(path).forEach((child) => {
          const plain = getFieldPlainText(row, child);
          const shortKey = child.field_name.split('.').pop() ?? '';
          const valueHit = hasFieldValueOverlap(selectionText, plain);
          const escapedKey = shortKey.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          const completeKvHit = Boolean(shortKey)
            && (
              new RegExp(`"${escapedKey}"\\s*:\\s*"`).test(selectionText)
              || new RegExp(`(?:^|[\\s|{[,])${escapedKey}\\s*:\\s*\\S+`).test(selectionText)
            );
          if (completeKvHit) {
            pushFieldValue(child, plain);
            return;
          }
          if (valueHit) {
            pushFieldValue(child, getSelectedFieldValue(child) || selectionText);
          }
        });
      });
    }

    // 2) 文本 KV + 边界 orphan
    const { leading, trailing } = extractBoundaryOrphans(selectionText, kvPairs);

    if (leading && !isDanglingFieldKeyPrefix(row, parentHint, leading)) {
      pushFieldValue(findLeafFieldByPartialValue(row, parentHint, leading));
    }

    kvPairs.forEach((pair) => {
      const field = resolveFieldByKeyHint(pair.key, parentHint, row, pair.value);
      if (!field) {
        return;
      }
      const plain = getFieldPlainText(row, field);
      // 关闭最小分词时：部分 VALUE 仍走前缀补齐到截断点（旧行为）
      if (!enableMinimalTokenCompletion && pair.value && pair.value !== plain) {
        const partialValue = resolvePartialValueTokens(field, row, pair.value);
        if (partialValue && partialValue !== plain) {
          setFieldCondition(field, partialValue, 'contains match phrase');
          return;
        }
      }
      // 必须优先使用 selection 中实际解析出的 VALUE，而不是直接使用行内完整 VALUE。
      // 例如 `io_kubernetes_workload_name: dsa` 对完整值
      // `dsa-17841304550` 应生成 contains match phrase dsa，而不是 is 完整值。
      // 开启最小分词时 pushFieldValue 内部会拆成最小 token。
      if (pair.value) {
        pushFieldValue(field, pair.value);
      } else if (plain && plain !== '--') {
        pushFieldValue(field, plain);
      }
    });

    // trailing 残缺 KEY（如 container_im）直接丢弃；若其实是 VALUE 截断则补齐
    if (trailing) {
      if (!isDanglingFieldKeyPrefix(row, parentHint, trailing)) {
        pushFieldValue(findLeafFieldByPartialValue(row, parentHint, trailing));
      }
    }

    // 3) 仍不足时：用 parent 子字段 VALUE 命中补齐（不含纯 KEY 前缀）。
    if (!kvPairs.length && conditions.length < 2) {
      const scopeParent = parentHint || uniquePaths.find(path => hasMappedChildFields(path)) || '';
      if (scopeParent && hasMappedChildFields(scopeParent)) {
        listChildLeafFields(scopeParent).forEach((child) => {
          const plain = getFieldPlainText(row, child);
          if (hasFieldValueOverlap(selectionText, plain)) {
            pushFieldValue(child, plain);
          }
        });
      }
    }

    const deduped = dedupeSelectionConditions(conditions);
    if (!deduped.length) {
      return [];
    }

    // 跨字段/跨边界场景：1 条也返回（例如只补齐 container_id，丢弃 container_im）
    if (deduped.length >= 2 || isCrossFieldSelectionText(selectionText, uniquePaths.length, kvPairs.length)) {
      return deduped;
    }

    return [];
  };

  const applySelectionConditions = (conditions: SelectionCondition[]) => {
    conditions.forEach((item) => {
      handleAddCondition(
        item.field,
        item.operator,
        item.value,
        false,
        item.depth,
        item.isNestedField,
      );
    });
  };

  const appendFieldSelectionConditions = (
    row: Record<string, any>,
    field: Record<string, any>,
    selectionText: string,
    operator = 'is',
    conditionOptions: { depth?: string | number; isNestedField?: string } = {},
  ) => {
    const depth = conditionOptions.depth;
    const isNested = conditionOptions.isNestedField ?? 'false';
    const plain = getFieldPlainText(row, field);

    // 整段等值：保持 is + 完整 VALUE
    if (operator === 'is' && plain === selectionText) {
      handleAddCondition(field.field_name, operator, [plain], false, depth, isNested);
      return;
    }

    // 部分划选：按配置解析为最小分词或 selectionText 原文
    if (operator !== 'is' || plain !== selectionText) {
      const values = resolveSelectionValues(selectionText, field, row);
      const finalOperator = plain === selectionText ? 'is' : (operator === 'is' ? 'contains match phrase' : operator);
      values.forEach((token) => {
        handleAddCondition(field.field_name, finalOperator, [token], false, depth, isNested);
      });
      return;
    }

    handleAddCondition(field.field_name, operator, [selectionText], false, depth, isNested);
  };

  /**
   * 单分词划选：若 Range 只命中一个带 data-segment-field-name 的叶子，直接按该路径解析。
   * 避免未展开 JSON 时回落到根字段后再按 VALUE 反查，导致同词多次 KEY 漂移。
   */
  const resolveSingleSegmentLeafCondition = (
    range: Range,
    row: Record<string, any>,
    selectionText: string,
  ): SelectionCondition[] => {
    const startNode = range.startContainer as Node;
    const endNode = range.endContainer as Node;
    const startEl = (startNode instanceof Element ? startNode : startNode.parentElement);
    const endEl = (endNode instanceof Element ? endNode : endNode.parentElement);
    const startSegment = startEl?.closest?.('[data-segment-field-name]') as HTMLElement | null;
    const endSegment = endEl?.closest?.('[data-segment-field-name]') as HTMLElement | null;
    const startPath = startSegment?.getAttribute('data-segment-field-name') ?? '';
    const endPath = endSegment?.getAttribute('data-segment-field-name') ?? '';

    if (!startPath || !endPath || startPath !== endPath) {
      return [];
    }

    const segmentRole = startSegment?.getAttribute('data-segment-field-role')
      || endSegment?.getAttribute('data-segment-field-role')
      || '';
    const field = getFieldByName(startPath);
    const parentPath = getParentFieldPath(startPath);
    const parentField = getFieldByName(parentPath);

    // KEY 分词：父级字段 contains KEY 文本（同样走 Value 最小分词配置）
    if (segmentRole === 'key') {
      const keyField = isLeafQueryableField(parentField)
        ? parentField
        : (parentPath ? { field_name: parentPath, field_type: 'object' } : undefined);
      const conditionField = keyField?.field_name || parentPath || startPath;
      if (!conditionField) {
        return [];
      }
      const nestedFlag = resolveIsNestedSearchField(conditionField, row);
      const segmentText = enableMinimalTokenCompletion && startSegment === endSegment
        ? stripSelectionMarkup(startSegment?.textContent ?? '').trim()
        : '';
      const values = segmentText
        ? [segmentText]
        : resolveSelectionValues(selectionText, keyField as Record<string, any> | undefined, row);
      return values.map(token => ({
        field: conditionField,
        operator: 'contains match phrase',
        value: [token],
        depth: getFieldPathDepth(conditionField),
        isNestedField: nestedFlag ? 'true' : 'false',
      }));
    }

    if (!isLeafQueryableField(field)) {
      return [];
    }

    const plain = getFieldPlainText(row, field);
    const nestedFlag = resolveIsNestedSearchField(field.field_name, row);
    if (plain === selectionText) {
      return [{
        field: field.field_name,
        operator: 'is',
        value: [plain],
        depth: getFieldPathDepth(field.field_name),
        isNestedField: nestedFlag ? 'true' : 'false',
      }];
    }

    // 最小分词：相对完整 VALUE 的 Lucene 边界补齐（0a2bddc9-5 → 0a2bddc9 + 5657）
    // 若 Lucene 未命中且划选落在单一 valid-text 内，再回退该节点全文（lob → lobby）
    let values = enableMinimalTokenCompletion
      ? resolveSelectionValues(selectionText, field, row)
      : [selectionText];

    if (
      enableMinimalTokenCompletion
      && values.length === 1
      && values[0] === selectionText
      && startSegment
      && startSegment === endSegment
    ) {
      const segmentText = stripSelectionMarkup(startSegment.textContent ?? '').trim();
      if (segmentText && segmentText !== selectionText && segmentText.includes(selectionText)) {
        values = [segmentText];
      }
    }

    return values.map(token => ({
      field: field.field_name,
      operator: plain === token ? 'is' : 'contains match phrase',
      value: [token],
      depth: getFieldPathDepth(field.field_name),
      isNestedField: nestedFlag ? 'true' : 'false',
    }));
  };

  /**
   * 划词「添加到本次检索」主入口。
   *
   * Value 解析配置 enableMinimalTokenCompletion（默认 true）：
   * - true：按渲染分词把划选补齐/拆成最小可检索分词单位后再生成条件
   * - false：Value 直接使用完整 selectionText（关闭最小分词补齐）
   * 在 useSelectionSearch({ enableMinimalTokenCompletion: false }) 关闭。
   */
  const addSelectionToCurrentSearch = (selectionRange: Range, row: Record<string, any>) => {
    const selectionText = getSelectionTextByRange(selectionRange);
    if (!selectionText) {
      return;
    }

    // 单叶子分词命中：路径与操作符一次定死，避免后续分支因 DOM 边界抖动而漂移
    const singleSegmentConditions = resolveSingleSegmentLeafCondition(selectionRange, row, selectionText);
    if (singleSegmentConditions.length) {
      applySelectionConditions(singleSegmentConditions);
      return;
    }

    // String / JSON String：按 VALUE 分词数量决定「原文 contains」或「分词补齐 contains」
    const stringField = resolveStringFieldContext(selectionRange, row);
    if (stringField) {
      const stringConditions = resolveStringContainsConditions(selectionRange, row, stringField);
      if (stringConditions.length) {
        applySelectionConditions(stringConditions);
        return;
      }
    }

    // Object/Nested（含以字符串形式展示的 Object）：跨字段补全为 KEY.SubKey 等值
    const multiFieldConditions = resolveMultiFieldSelectionConditions(selectionRange, row);
    if (multiFieldConditions.length >= 1) {
      applySelectionConditions(multiFieldConditions);
      return;
    }

    const targetElement = getSelectionAnchorElement(selectionRange);
    const fulltextFieldItem = getInputQueryDefaultItem();
    const resolved = resolveSelectionSearchTarget(row, selectionText, targetElement);
    const targetField = resolved.field;
    const conditionOptions = {
      depth: resolved.depth,
      isNestedField: resolved.isNestedField,
    };

    if (targetField && ['date', 'date_nanos'].includes(targetField.field_type)) {
      const rawValue = getObjectValue(row, targetField);
      handleAddCondition(
        targetField.field_name,
        'is',
        [String(rawValue).replace(/<\/?mark>/gim, '')],
        false,
        conditionOptions.depth,
        conditionOptions.isNestedField,
      );
      return;
    }

    if (targetField && resolved.operator && !isStructField(targetField)) {
      appendFieldSelectionConditions(
        row,
        targetField,
        selectionText,
        resolved.operator,
        conditionOptions,
      );
      return;
    }

    if (resolved.fieldName && resolved.operator === 'contains match phrase') {
      handleAddCondition(
        resolved.fieldName,
        fulltextFieldItem.operator,
        [selectionText],
        false,
        conditionOptions.depth,
        conditionOptions.isNestedField,
      );
      return;
    }

    if (showCtxType.value === 'table') {
      if (!targetField) {
        handleAddCondition(FULLTEXT_FIELD_NAME, fulltextFieldItem.operator, [selectionText]);
        return;
      }

      appendFieldSelectionConditions(row, targetField, selectionText, 'is', conditionOptions);
      return;
    }

    const conditions: SelectionCondition[] = [];
    const appendedConditionKeys = new Set<string>();
    const fieldNameSet = new Set(filteredFieldList.value.map(item => item.field_name));
    const originFieldTokens = getOriginSegmentTokens(row);
    const originTokens = enableMinimalTokenCompletion
      ? extractMinimalIntersectingCursorTokens(selectionText, originFieldTokens)
      : completeSelectionByTokens(selectionText, originFieldTokens);

    originTokens.forEach((token) => {
      if (!token.text || token.tokenType === 'field-name' || fieldNameSet.has(token.text)) {
        return;
      }

      let field = getFieldByName(token.fieldName ?? '');
      if (
        isStructField(field)
        || (field && hasMappedChildFields(field.field_name))
        || (field && getFieldPlainText(row, field) !== token.text)
      ) {
        const leafField = findLeafFieldBySelection(row, token.fieldName ?? '', token.text);
        if (leafField) {
          field = leafField;
        }
      }

      const plainText = field ? getFieldPlainText(row, field) : '';
      const nestedFlag = field ? resolveIsNestedSearchField(field.field_name, row) : false;
      // 单 token VALUE：不把 messa 补成整段 /var/log/messages
      const isSingleTokenField = Boolean(field && getFieldCursorTokens(row, field).length <= 1);
      const useRawSelection = Boolean(
        field
        && isSingleTokenField
        && selectionText
        && plainText !== selectionText
        && plainText.includes(selectionText),
      );
      const rawValueText = useRawSelection ? selectionText : token.text;
      const valueList = field && isLeafQueryableField(field)
        ? resolveSelectionValues(rawValueText, field, row)
        : [rawValueText];

      let operator = fulltextFieldItem.operator;
      let conditionField = FULLTEXT_FIELD_NAME;

      if (useRawSelection && field && isLeafQueryableField(field)) {
        operator = 'contains match phrase';
        conditionField = field.field_name;
      } else if (field && isLeafQueryableField(field) && plainText === token.text) {
        operator = 'is';
        conditionField = field.field_name;
      } else if (
        field
        && isLeafQueryableField(field)
        && !hasMappedChildFields(field.field_name)
        && plainText.includes(token.text)
      ) {
        // 部分分词统一 contains，避免同词多次在 is/contains 间漂移
        operator = 'contains match phrase';
        conditionField = field.field_name;
      }

      valueList.forEach((valueText) => {
        const conditionKey = [conditionField, operator, valueText, nestedFlag ? '1' : '0'].join('__');
        if (!appendedConditionKeys.has(conditionKey)) {
          appendedConditionKeys.add(conditionKey);
          conditions.push({
            field: conditionField,
            operator,
            value: [valueText],
            depth: field ? getFieldPathDepth(field.field_name) : undefined,
            isNestedField: nestedFlag ? 'true' : 'false',
          });
        }
      });
    });

    if (!conditions.length) {
      handleAddCondition(FULLTEXT_FIELD_NAME, fulltextFieldItem.operator, [selectionText]);
      return;
    }

    applySelectionConditions(conditions);
  };

  return {
    FULLTEXT_FIELD_NAME,
    stripSelectionMarkup,
    getFieldByName,
    addSelectionToCurrentSearch,
    /** 当前是否开启划词 Value 最小分词补齐 */
    enableMinimalTokenCompletion,
  };
};
