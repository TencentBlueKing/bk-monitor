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
import { optimizedSplit } from '@/hooks/hooks-helper';
import LuceneSegment from '@/hooks/lucene.segment';
import useStore from '@/hooks/use-store';
import { getInputQueryDefaultItem } from '@/views/retrieve-v2/search-bar/utils/const.common';

export const FULLTEXT_FIELD_NAME = '*';
const SELECTION_MAX_TOKENS = 1000;
const STRUCT_FIELD_TYPES = new Set(['object', 'nested']);

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
   * 与字段展示分词保持一致：自定义分词符走 optimizedSplit，否则走 LuceneSegment。
   */
  const tokenizeSelectionText = (
    value: string,
    extra?: Partial<SelectionToken>,
    field?: Record<string, any>,
  ) => {
    const text = stripSelectionMarkup(value);
    if (!text) {
      return [] as SelectionToken[];
    }

    let splitList: Array<{ text: string; isCursorText?: boolean }> = [];
    if (field?.tokenize_on_chars) {
      splitList = optimizedSplit(text, field.tokenize_on_chars);
    } else {
      splitList = LuceneSegment.split(text, SELECTION_MAX_TOKENS);
    }

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

    // 优先取 JSON 树绑定的完整检索路径（含 KEY.SubKey），再回退到 data-field-name
    return (
      startElement?.closest?.('[data-search-field-name]')
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

    return candidates.find(field => getFieldPlainText(row, field) === normalizedSelection)
      ?? candidates.find((field) => {
        const plainText = getFieldPlainText(row, field);
        return Boolean(plainText) && plainText !== '--' && plainText.includes(normalizedSelection);
      });
  };

  /**
   * 将划选范围补全到完整分词边界。
   */
  const completeSelectionByTokens = (selectionText: string, tokens: SelectionToken[]) => {
    if (!selectionText || !tokens.length) {
      return [];
    }

    const normalizedSelection = stripSelectionMarkup(selectionText);
    if (!normalizedSelection) {
      return [];
    }

    const plainText = tokens.map(item => item.text).join('');
    const selectionStart = plainText.indexOf(normalizedSelection);
    if (selectionStart < 0) {
      return [];
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
      return [];
    }

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
   * 划选检索目标解析（以 Fields 列表为权威，不直接依据 Value 运行时类型）：
   * 1) 简单叶子字段：KEY = VALUE
   * 2) Fields 无子字段映射的文本/JSON 字符串字段：KEY 包含 VALUE
   * 3) Object + Fields 声明 KEY.SubKey：KEY.SubKey = VALUE
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
      const parentPath = getParentFieldPath(targetField.field_name);
      const isMappedChildLeaf = Boolean(
        parentPath
        && (hasMappedChildFields(parentPath) || isStructField(getFieldByName(parentPath))),
      );

      if (plainText === selectionText || isMappedChildLeaf) {
        return buildTarget(targetField, targetField.field_name, 'is', nestedFlag);
      }

      if (!hasMappedChildFields(targetField.field_name)) {
        const operator = targetField.field_type === 'text' ? 'is' : 'contains match phrase';
        return buildTarget(targetField, targetField.field_name, operator, nestedFlag);
      }

      return buildTarget(targetField, targetField.field_name, 'is', nestedFlag);
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
    const searchPath = el.getAttribute('data-search-field-name')
      ?? el.closest?.('[data-search-field-name]')?.getAttribute('data-search-field-name')
      ?? '';
    const fieldPath = el.getAttribute('data-field-name')
      ?? el.closest?.('[data-field-name]')?.getAttribute('data-field-name')
      ?? '';
    return searchPath || fieldPath;
  };

  /**
   * 将短 KEY（如 io_kubernetes_workload_name）解析为 Fields 中的完整路径。
   */
  const resolveFieldByKeyHint = (keyHint: string, parentHint = '') => {
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

    // 全局按末级 KEY 匹配（优先更长路径）
    const suffix = `.${normalizedHint}`;
    let matched: Record<string, any> | undefined;
    iterateFieldPools((field) => {
      if (!isLeafQueryableField(field)) {
        return;
      }
      if (field.field_name === normalizedHint || field.field_name.endsWith(suffix)) {
        if (!matched || field.field_name.length > matched.field_name.length) {
          matched = field;
        }
      }
    });
    return matched;
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
    if (selectionText.includes(plainText) || plainText === selectionText) {
      return true;
    }

    const minLen = Math.min(4, plainText.length);
    if (plainText.length < minLen) {
      return false;
    }

    // 提取划选中的候选 value 碎片（去掉 JSON 标点）
    const fragments = selectionText
      .split(/["'\s|,:{}\[\]]+/)
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
   * Fields 列表未声明子字段，且 VALUE 为 JSON String（或 DOM 标记为 JSON String 解析）。
   * 此类字段划词统一走「包含」，而不是 KEY.SubKey 等值。
   */
  const isJsonStringFieldByList = (
    field: Record<string, any> | undefined,
    row: Record<string, any>,
    targetElement?: HTMLElement | null,
  ) => {
    if (!isLeafQueryableField(field) || hasMappedChildFields(field.field_name)) {
      return false;
    }

    if (targetElement?.closest?.('[data-json-string-parsed="true"]') != null
      || targetElement?.getAttribute?.('data-json-string-parsed') === 'true') {
      return true;
    }

    const rawValue = getRowFieldValue(row, field);
    if (typeof rawValue === 'string' && /^\s*[{\[]/.test(rawValue)) {
      return true;
    }

    const plain = getFieldPlainText(row, field);
    return /^\s*[{\[]/.test(plain) && /[}\]]\s*$/.test(plain);
  };

  const resolveJsonStringFieldContext = (range: Range, row: Record<string, any>) => {
    const targetElement = getSelectionAnchorElement(range);
    const candidatePath = normalizeArrayFieldPath(
      targetElement?.getAttribute('data-search-field-name')
      ?? targetElement?.getAttribute('data-field-name')
      ?? '',
    );

    // JSON String 解析节点上的 data-search-field-name 已是外层真实字段
    const directField = getFieldByName(candidatePath);
    if (isJsonStringFieldByList(directField, row, targetElement)) {
      return directField;
    }

    // 兜底：相交路径中找 JSON String 外层字段
    const paths = [...new Set(
      collectIntersectedSearchNodes(range)
        .map(resolveFieldPathFromElement)
        .map(normalizeArrayFieldPath)
        .filter(Boolean),
    )];

    for (const path of paths) {
      const field = getFieldByName(path);
      if (isJsonStringFieldByList(field, row, targetElement)) {
        return field;
      }
      // 若路径落在虚构子路径上，回退父级
      const parentPath = getParentFieldPath(path);
      const parentField = getFieldByName(parentPath);
      if (isJsonStringFieldByList(parentField, row, targetElement)) {
        return parentField;
      }
    }

    return undefined;
  };

  /** 从 JSON String 中提取可补齐原子（KEY + 字符串 VALUE） */
  const extractJsonStringAtoms = (jsonText: string) => {
    const atoms = new Set<string>();
    const stringRegex = /"((?:\\.|[^"\\])*)"/g;
    let match = stringRegex.exec(jsonText);
    while (match) {
      const atom = match[1].replace(/\\"/g, '"').trim();
      if (atom) {
        atoms.add(atom);
      }
      match = stringRegex.exec(jsonText);
    }
    return [...atoms];
  };

  /**
   * 将划选碎片补齐为 JSON 原子词：
   * - ina → China（VALUE 后缀）
   * - onlin → online_cnt（KEY 前缀）
   */
  const completeFragmentsAgainstJsonAtoms = (fragments: string[], atoms: string[]) => {
    const completed: string[] = [];
    const seen = new Set<string>();

    fragments.forEach((raw) => {
      const fragment = sanitizeSelectionFragment(raw);
      if (!fragment || fragment.length < 2) {
        return;
      }

      const exact = atoms.find(atom => atom === fragment);
      const endHits = atoms.filter(atom => atom !== fragment && atom.endsWith(fragment));
      const startHits = atoms.filter(atom => atom !== fragment && atom.startsWith(fragment));
      const includeHits = atoms.filter(atom =>
        atom !== fragment
        && atom.includes(fragment)
        && fragment.length >= Math.min(4, atom.length));

      const hit = exact
        ?? endHits.sort((a, b) => a.length - b.length)[0]
        ?? startHits.sort((a, b) => a.length - b.length)[0]
        ?? includeHits.sort((a, b) => a.length - b.length)[0];

      if (hit && !seen.has(hit)) {
        seen.add(hit);
        completed.push(hit);
      }
    });

    return completed;
  };

  /**
   * JSON String 字段划词 → 外层字段「包含」多个补齐分词。
   * 例：body 中划选 ina","onlin → body contains China / body contains online_cnt
   */
  const resolveJsonStringContainsConditions = (
    range: Range,
    row: Record<string, any>,
    field: Record<string, any>,
  ): SelectionCondition[] => {
    const selectionText = getSelectionTextByRange(range);
    if (!selectionText) {
      return [];
    }

    const plain = getFieldPlainText(row, field);
    const atoms = extractJsonStringAtoms(plain);
    if (!atoms.length) {
      return [];
    }

    const kvPairs = parseJsonKvPairsFromText(selectionText);
    const { leading, trailing } = extractBoundaryOrphans(selectionText, kvPairs);
    const boundaryParts = selectionText
      .split(/"\s*,\s*"?|,\s*"/)
      .map(sanitizeSelectionFragment)
      .filter(Boolean);

    const tokenCompleted = completeSelectionByTokens(
      selectionText,
      tokenizeSelectionText(plain, {
        fieldName: field.field_name,
        tokenType: 'field-value',
      }, field),
    ).map(token => token.text);

    const fragments = [
      ...boundaryParts,
      leading,
      trailing,
      ...kvPairs.flatMap(pair => [pair.key, pair.value]),
      ...tokenCompleted,
    ].filter(Boolean);

    const completedTokens = completeFragmentsAgainstJsonAtoms(fragments, atoms);
    if (!completedTokens.length) {
      return [];
    }

    return completedTokens.map(token => ({
      field: field.field_name,
      operator: 'contains match phrase',
      value: [token],
      depth: getFieldPathDepth(field.field_name),
      isNestedField: 'false',
    }));
  };

  /**
   * 跨字段划选智能解析：
   * 1) DOM 相交叶子：必须有 VALUE 重叠证据才采纳（仅擦到 KEY 前缀则丢弃）
   * 2) 完整 "key":"value" / key:value → 补齐完整字段值
   * 3) leading VALUE 截断碎片 → 补齐；trailing 残缺 KEY → 丢弃
   * 4) 跨边界场景下，即使只解析出 1 条有效条件也返回（如只补齐 container_id）
   */
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
    const parentHint = inferParentHintFromPaths(uniquePaths)
      || getParentFieldPath(anchorPath)
      || (hasMappedChildFields(anchorPath) ? anchorPath : '')
      || '';

    const conditions: SelectionCondition[] = [];
    const appendedFields = new Set<string>();

    const pushFieldValue = (field?: Record<string, any>, rawValue?: string) => {
      if (!isLeafQueryableField(field)) {
        return;
      }
      const plain = rawValue && rawValue !== '--'
        ? stripSelectionMarkup(rawValue)
        : getFieldPlainText(row, field);
      if (!plain || plain === '--') {
        return;
      }
      if (appendedFields.has(field.field_name)) {
        return;
      }
      appendedFields.add(field.field_name);
      conditions.push(buildConditionFromFieldWithRow(field, plain, row, 'is'));
    };

    // 1) DOM 相交叶子：必须有 VALUE 证据；只碰到 KEY/KEY 前缀则丢弃
    uniquePaths.forEach((path) => {
      const field = getFieldByName(path);
      if (!isLeafQueryableField(field)) {
        return;
      }
      const plain = getFieldPlainText(row, field);
      if (hasFieldValueOverlap(selectionText, plain)) {
        pushFieldValue(field, plain);
      }
    });

    // 相交到 object/nested 父节点，且有效叶子不足时，按 VALUE/完整 KV 回落
    if (conditions.length < 2) {
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
          if (valueHit || completeKvHit) {
            pushFieldValue(child, plain);
          }
        });
      });
    }

    // 2) 文本 KV + 边界 orphan
    const kvPairs = parseJsonKvPairsFromText(selectionText);
    const { leading, trailing } = extractBoundaryOrphans(selectionText, kvPairs);

    if (leading && !isDanglingFieldKeyPrefix(row, parentHint, leading)) {
      pushFieldValue(findLeafFieldByPartialValue(row, parentHint, leading));
    }

    kvPairs.forEach((pair) => {
      const field = resolveFieldByKeyHint(pair.key, parentHint);
      if (!field) {
        return;
      }
      // 完整/部分 value 都补齐为行内完整值
      const plain = getFieldPlainText(row, field);
      if (plain && plain !== '--') {
        pushFieldValue(field, plain);
        return;
      }
      // 行内无值时退化用解析出的 value
      if (pair.value) {
        pushFieldValue(field, pair.value);
      }
    });

    // trailing 残缺 KEY（如 container_im）直接丢弃；若其实是 VALUE 截断则补齐
    if (trailing) {
      if (!isDanglingFieldKeyPrefix(row, parentHint, trailing)) {
        pushFieldValue(findLeafFieldByPartialValue(row, parentHint, trailing));
      }
    }

    // 3) 仍不足时：用 parent 子字段 VALUE 命中补齐（不含纯 KEY 前缀）
    if (conditions.length < 2) {
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
    const completedTokens = completeSelectionByTokens(selectionText, getFieldSegmentTokens(row, field));
    if (!completedTokens.length) {
      handleAddCondition(field.field_name, operator, [selectionText], false, depth, isNested);
      return;
    }

    completedTokens.forEach((token) => {
      handleAddCondition(field.field_name, operator, [token.text], false, depth, isNested);
    });
  };

  const addSelectionToCurrentSearch = (selectionRange: Range, row: Record<string, any>) => {
    const selectionText = getSelectionTextByRange(selectionRange);
    if (!selectionText) {
      return;
    }

    // JSON String 字段（Fields 无子字段映射）：划词补齐为多个「包含」条件
    // 例：body 中划选 ina","onlin → body contains China / body contains online_cnt
    const jsonStringField = resolveJsonStringFieldContext(selectionRange, row);
    if (jsonStringField) {
      const jsonContainsConditions = resolveJsonStringContainsConditions(
        selectionRange,
        row,
        jsonStringField,
      );
      if (jsonContainsConditions.length) {
        applySelectionConditions(jsonContainsConditions);
        return;
      }
    }

    // Object/Nested 跨字段划选：按 VALUE 证据拆 KEY.SubKey 等值条件
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
    const originTokens = completeSelectionByTokens(selectionText, getOriginSegmentTokens(row));

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
      const parentPath = field ? getParentFieldPath(field.field_name) : '';
      const isMappedChildLeaf = Boolean(
        field
        && parentPath
        && (hasMappedChildFields(parentPath) || isStructField(getFieldByName(parentPath))),
      );
      let operator = fulltextFieldItem.operator;
      let conditionField = FULLTEXT_FIELD_NAME;

      if (field && isLeafQueryableField(field) && plainText === token.text) {
        operator = 'is';
        conditionField = field.field_name;
      } else if (field && isLeafQueryableField(field) && isMappedChildLeaf) {
        operator = 'is';
        conditionField = field.field_name;
      } else if (
        field
        && isLeafQueryableField(field)
        && !hasMappedChildFields(field.field_name)
        && plainText.includes(token.text)
      ) {
        operator = field.field_type === 'text' ? 'is' : 'contains match phrase';
        conditionField = field.field_name;
      }

      const conditionKey = [conditionField, operator, token.text, nestedFlag ? '1' : '0'].join('__');
      if (!appendedConditionKeys.has(conditionKey)) {
        appendedConditionKeys.add(conditionKey);
        conditions.push({
          field: conditionField,
          operator,
          value: [token.text],
          depth: field ? getFieldPathDepth(field.field_name) : undefined,
          isNestedField: nestedFlag ? 'true' : 'false',
        });
      }
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
  };
};
