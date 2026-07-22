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
import RetrieveHelper from '@/views/retrieve-helper';
import {
  buildSegmentPageHighlightRanges,
  highlightPlainTextIntoFragment,
  type HighlightRange,
} from '@/views/retrieve-core/page-highlight';
import {
  isKeywordLikeFieldType,
  isTextFieldType,
} from '@/views/retrieve-v2/search-bar/utils/sql-contains-wildcard';

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH,
  ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH,
  splitRenderText,
  stripMark,
  truncateMarkedTextByChars,
} from '../storage/utils/retrieve-render-meta';
import { normalizeArrayFieldPath, resolveMappedFieldPath } from './field-path';
import {
  getClickTargetElement,
  listOuterValidTextNodes,
  resolveOuterValidText,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import { getJsonSegmentRanges } from './json-segment-ranges';
import useStore from './use-store';
import UseSegmentPropInstance from './use-segment-pop';

import type { Ref } from 'vue';

export type FormatterConfig = {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
  field: any;
  onSegmentClick: (_args: any) => void;
  onSegmentRenderUpdate?: () => void;
  options?: Record<string, any>;
  precomputedSegments?: PrecomputedSegments;
};

export type SegmentAppendText = {
  text: string;
  onClick?: (..._args) => void;
  onMouseDown?: (..._args) => void;
  onMouseUp?: (..._args) => void;
  attributes?: Record<string, string>;
};
export type PrecomputedSegments = Record<string, Array<{
  text: string;
  isMark?: boolean;
  isCursorText?: boolean;
  isBlobWord?: boolean;
  isNotParticiple?: boolean;
  resultRanges?: HighlightRange[];
}>>;

/** 分词点击上下文：在 show tippy 时写入，避免共享 virtual-target / taskEventManager 串台导致多次点击结果漂移 */
type SegmentClickContext = {
  name: string;
  searchFieldName: string;
  value: string;
  depth: string;
  segmentRole: string;
  parsedFromJsonString: boolean;
  rootFieldName: string;
  rootFieldType: string;
  isVirtualObjNode: boolean;
  jsonValue: any;
  /** 真实点击的 .valid-text（tippy reference 是 body 虚拟节点，不能用来算分词位置） */
  tokenEl?: HTMLElement | null;
  tokenIndex?: number;
  tokenCount?: number;
  isSoleToken?: boolean;
};

let activeSegmentClickContext: SegmentClickContext | null = null;

/**
 * 分词重建比对缓存：禁止把大段原文写入 data-* Attr（DOM 属性拷贝开销极大）。
 * 需要完整 source 时按 data-field-name + Field / segmentResolveText 读取。
 */
const wordSplitSourceByElement = new WeakMap<HTMLElement, string>();

export const clearWordSplitSourceCache = (element?: HTMLElement | null) => {
  if (element) {
    wordSplitSourceByElement.delete(element);
  }
};

const SEGMENT_VIRTUAL_TARGET_ATTRS = [
  'data-field-value',
  'data-field-name',
  'data-search-field-name',
  'data-segment-field-name',
  'data-field-dpth',
  'data-segment-field-role',
] as const;

export default class UseJsonFormatter {
  editor?: JsonView;
  config: FormatterConfig;
  setValuePromise: Promise<any>;
  localDepth: number;
  getSegmentContent: (_keyRef: object, _fn: (..._args) => void) => Ref<HTMLElement>;
  keyRef: any;
  segmentTaskId: number;

  constructor(cfg: FormatterConfig) {
    this.config = cfg;
    this.setValuePromise = Promise.resolve(true);
    this.localDepth = 1;
    this.keyRef = {};
    this.segmentTaskId = 0;
    this.getSegmentContent = UseSegmentPropInstance.getSegmentContent.bind(UseSegmentPropInstance);
  }

  update(cfg) {
    this.config = cfg;
  }

  getField(fieldName: string) {
    if (!fieldName) return undefined;
    const normalized = normalizeArrayFieldPath(fieldName);
    const names = normalized && normalized !== fieldName ? [fieldName, normalized] : [fieldName];
    const matchInList = (list?: any[]) => {
      if (!Array.isArray(list)) return undefined;
      return list.find(item => names.includes(item?.field_name));
    };

    const matched = matchInList(this.config.fields);
    if (matched) return matched;
    // 动态新增 Visible 字段时，fields 列表可能尚未同步；根字段绑定始终可用
    if (names.includes(this.config.field?.field_name)) {
      return this.config.field;
    }

    // Visible 之外也要能命中完整字段列表（含 __ext_json / __ext_json.deployment 等虚拟中间层），
    // 否则深路径会被错误收敛到根字段。
    try {
      const store = useStore();
      const index = store.state?.indexFieldInfo?.fieldNameIndex;
      if (index && typeof index === 'object') {
        for (const name of names) {
          if (index[name]) return index[name];
        }
      }
      return matchInList(store.getters?.filteredFieldList)
        ?? matchInList(store.getters?.rawFieldList);
    } catch {
      return undefined;
    }
  }

  /**
   * 将 JSON 深路径收敛为 Fields 列表中真实存在的最长前缀。
   * 例：__ext_json.deployment.pod.node → __ext_json.deployment.pod
   */
  clampToMappedFieldPath(path?: string | null, fallback?: string) {
    const rootFallback = fallback ?? this.config.field?.field_name ?? '';
    if (!path) {
      return rootFallback;
    }
    return resolveMappedFieldPath(path, name => this.getField(name), rootFallback);
  }

  /**
   * 仅用于 json-formatter 检索字段解析：
   * 优先使用 JSON 树构建阶段绑定的 data-search-field-name / data-segment-field-name，
   * 再按 Fields 列表回溯收敛，禁止未映射深路径进入检索。
   */
  resolveFormatterSearchFieldName(domFieldName?: string | null, searchFieldName?: string | null) {
    // 1) JSON 树 / 分词节点路径：必须回归 Fields 列表
    if (typeof searchFieldName === 'string' && searchFieldName.length > 0) {
      return this.clampToMappedFieldPath(searchFieldName, this.config.field?.field_name);
    }

    // 2) 非 JSON / 未绑定路径：沿用 DOM field-name，同样做列表回归
    if (typeof domFieldName === 'string' && domFieldName.length > 0) {
      return this.clampToMappedFieldPath(domFieldName, this.config.field?.field_name);
    }

    // 3) 最后降级到 formatter 根字段绑定
    return this.config.field?.field_name;
  }

  getFieldNameValue() {
    const tippyInstance = segmentPopInstance.getInstance();
    const target = tippyInstance.reference as HTMLElement;
    let name = target.getAttribute('data-field-name');
    let searchFieldName = target.getAttribute('data-segment-field-name')
      || target.getAttribute('data-search-field-name');
    let value = target.getAttribute('data-field-value');
    let depth = target.getAttribute('data-field-dpth');
    const segmentRole = target.getAttribute('data-segment-field-role') || '';

    if (value === undefined || value === null) {
      value = target.textContent;
    }

    if (!searchFieldName) {
      searchFieldName = target.closest('[data-segment-field-name]')?.getAttribute('data-segment-field-name')
        || target.closest('[data-search-field-name]')?.getAttribute('data-search-field-name');
    }

    if (name === undefined || name === null) {
      const valueElement = tippyInstance.reference.closest('.field-value') as HTMLElement;
      name = valueElement?.getAttribute('data-field-name');
    }

    if (depth === undefined || depth === null) {
      depth = target.closest('[data-depth]')?.getAttribute('data-depth');
    }

    const parsedFromJsonString = target.closest('[data-json-string-parsed="true"]') !== null;
    return { value, name, depth, searchFieldName, parsedFromJsonString, segmentRole };
  }

  private clearVirtualTargetSegmentAttrs(target: HTMLElement) {
    SEGMENT_VIRTUAL_TARGET_ATTRS.forEach((attr) => {
      target.removeAttribute(attr);
    });
  }

  /**
   * JSON 展示树中的 value 可能来自 Object 的叶子节点，而 formatter 的根字段是
   * __ext 这样的虚拟 object。点击分词时不能再用根字段兜底，否则会把条件生成为
   * __ext 包含 token。这里仅给「JSON/Object 叶子」计算真实字段和操作符，普通字段
   * 继续沿用原有逻辑，避免影响划词和非 JSON 场景。
   */
  private getPathValue(value: any, path: string) {
    if (value === null || value === undefined || !path) return undefined;
    if (typeof value !== 'object') return undefined;
    if (Object.prototype.hasOwnProperty.call(value, path)) return value[path];

    return path.split('.').reduce((current, part) => {
      if (current === null || current === undefined) return undefined;
      return Object.prototype.hasOwnProperty.call(current, part) ? current[part] : undefined;
    }, value);
  }

  private getObjectLeafValueFromContext(ctx: SegmentClickContext, fieldName: string, fallback: any) {
    const rootName = ctx.rootFieldName;
    const relativePath = rootName && fieldName.startsWith(`${rootName}.`)
      ? fieldName.slice(rootName.length + 1)
      : fieldName;
    const rawValue = this.getPathValue(ctx.jsonValue, fieldName)
      ?? this.getPathValue(ctx.jsonValue, relativePath);
    return rawValue === undefined || rawValue === null ? fallback : rawValue;
  }

  /**
   * 将行内取值转为检索用完整 VALUE 文本。
   * 对象/数组禁止 String()（会变成 "[object Object]"），标量叶子才回填。
   */
  private toScalarPlainValue(value: any): string {
    if (value === undefined || value === null || value === '') return '';
    if (typeof value === 'object') {
      // BigNumber 等伪对象按字符串输出
      if (value._isBigNumber) {
        return this.escapeString(String(value)).replace(/<\/?mark>/g, '');
      }
      return '';
    }
    return this.escapeString(String(value)).replace(/<\/?mark>/g, '');
  }

  /**
   * date / date_nanos：时间格式化只影响 DOM 展示。
   * jsonValue 可能是整行 object，也可能是当前根字段的标量原始值（时间戳）。
   * 检索条件必须回取原始值，禁止用格式化后的展示串。
   */
  private resolveDateFieldRawValue(
    ctx: SegmentClickContext,
    fieldName: string,
    field: Record<string, any> | undefined,
    selectedValue?: string,
  ) {
    const name = field?.field_name || fieldName;
    const fromPath = this.getPathValue(ctx.jsonValue, name)
      ?? (name ? ctx.jsonValue?.[name] : undefined);
    if (fromPath !== undefined && fromPath !== null && fromPath !== '') {
      return fromPath;
    }

    const jsonValue = ctx.jsonValue;
    if (
      typeof jsonValue === 'string'
      || typeof jsonValue === 'number'
      || (jsonValue && typeof jsonValue === 'object' && jsonValue._isBigNumber)
    ) {
      return jsonValue;
    }

    return selectedValue;
  }

  private resolveClickFullPlainValue(
    ctx: SegmentClickContext,
    fieldName: string,
    field: Record<string, any> | undefined,
    selectedValue: string,
  ) {
    // KEY 分词：检索值就是 KEY 文本本身，不能用父级 Object 整段回填
    if (ctx.segmentRole === 'key') {
      return '';
    }

    if (['date', 'date_nanos'].includes(field?.field_type)) {
      const raw = this.resolveDateFieldRawValue(ctx, fieldName, field, selectedValue);
      return this.toScalarPlainValue(raw ?? selectedValue ?? '');
    }

    const leafValue = this.getObjectLeafValueFromContext(ctx, fieldName, undefined);
    if (leafValue !== undefined && leafValue !== null) {
      return this.toScalarPlainValue(leafValue);
    }

    // 根字段整段 VALUE（如 log / keyword 列）：优先按字段名从行数据取
    const pathValue = this.getPathValue(ctx.jsonValue, fieldName)
      ?? (fieldName ? ctx.jsonValue?.[fieldName] : undefined);
    if (pathValue !== undefined && pathValue !== null) {
      return this.toScalarPlainValue(pathValue);
    }

    if (!fieldName || fieldName === ctx.rootFieldName) {
      const rootValue = typeof ctx.jsonValue === 'string' || typeof ctx.jsonValue === 'number'
        ? ctx.jsonValue
        : undefined;
      if (rootValue !== undefined && rootValue !== null) {
        return this.toScalarPlainValue(rootValue);
      }
    }

    return '';
  }

  /**
   * 解析点击分词在「当前叶子字段 VALUE」可检索分词列表中的位置。
   *
   * 注意：
   * 1) tippy.reference 是 body 上的 virtual-target，必须传入真实 .valid-text
   * 2) Object/JSON 下 path 可能在节点自身或祖先，过滤统一用 closest
   * 3) 扫描根用 segment-content（含全部兄弟分词），再按叶子 path 过滤；
   *    不能拿单个 valid-text 当 root（querySelectorAll 不含自身）
   */
  private resolveValidTokenPosition(clickEl?: HTMLElement | null): {
    tokenIndex?: number;
    tokenCount?: number;
    isSoleToken: boolean;
  } {
    if (!clickEl) {
      return { isSoleToken: false };
    }

    // 必须归一到外层分词节点，避免高亮内层 mark.valid-text 干扰计数
    const active = resolveOuterValidText(clickEl);
    if (!active) {
      return { isSoleToken: false };
    }

    const resolvePath = (node: HTMLElement) => node.getAttribute('data-segment-field-name')
      || node.closest?.('[data-segment-field-name]')?.getAttribute('data-segment-field-name')
      || '';
    const resolveRole = (node: HTMLElement) => node.getAttribute('data-segment-field-role')
      || node.closest?.('[data-segment-field-role]')?.getAttribute('data-segment-field-role')
      || '';

    const fieldPath = resolvePath(active);
    const segmentRole = resolveRole(active);

    // 扫描根：整段分词容器，保证能看到同一叶子下的兄弟 .valid-text
    const scanRoot = (active.closest('.segment-content')
      || active.closest('.bklog-json-field-value')
      || active.closest('.field-value')
      || active.closest('[data-field-name][data-has-word-split]')
      || active.parentElement) as HTMLElement | null;
    if (!scanRoot) {
      return { isSoleToken: false };
    }

    const allTokens = listOuterValidTextNodes(scanRoot);
    const tokens = fieldPath
      ? allTokens.filter(node => resolvePath(node) === fieldPath && resolveRole(node) === segmentRole)
      : allTokens;

    const tokenCount = tokens.length;
    if (!tokenCount) {
      // 过滤后为空时，至少把当前节点视为唯一分词，避免默认 *value*
      return { tokenIndex: 0, tokenCount: 1, isSoleToken: true };
    }

    const tokenIndex = tokens.findIndex(node => node === active || node.contains(active));
    return {
      tokenIndex: tokenIndex >= 0 ? tokenIndex : undefined,
      tokenCount,
      isSoleToken: tokenCount === 1,
    };
  }

  private isObjectLeafClickContext(
    ctx: SegmentClickContext,
    field: Record<string, any> | undefined,
    resolvedFieldName: string,
  ) {
    const isObjectRoot = ctx.rootFieldType === 'object' || ctx.isVirtualObjNode;
    const isChildPath = Boolean(
      resolvedFieldName
      && ctx.rootFieldName
      && resolvedFieldName !== ctx.rootFieldName
      && resolvedFieldName.startsWith(`${ctx.rootFieldName}.`),
    );
    const isLeaf = Boolean(
      field
      && field.field_type !== 'object'
      && field.field_type !== 'nested'
      && field.field_type !== '__virtual__',
    );
    // DOM 挂在父级 Object（name=__ext）而检索路径已解析到子叶子
    const domIsParentObject = Boolean(
      isObjectRoot
      && isLeaf
      && ctx.name
      && resolvedFieldName
      && ctx.name !== resolvedFieldName,
    );

    return ctx.parsedFromJsonString || isChildPath || domIsParentObject;
  }

  /**
   * 操作符判定（字段类型优先，多次点击必须稳定）：
   * - keyword/flattened → contains（划词/点击分词原文）
   * - text → 完整 VALUE 用 is，否则 contains（分词本身即最小单位）
   * - 其他 → is（Value 侧补齐为完整 FieldValue）
   * - KEY → contains
   */
  private resolveSegmentClickOperation(
    val: string,
    ctx: SegmentClickContext,
    field: Record<string, any> | undefined,
    resolvedFieldName: string,
    selectedValue: string,
  ) {
    if (ctx.segmentRole === 'key') {
      return val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    if (val !== 'is' && val !== 'not') {
      return val;
    }

    const selected = this.escapeString(String(selectedValue ?? '')).replace(/<\/?mark>/g, '').trim();
    const fullPlain = this.resolveClickFullPlainValue(ctx, resolvedFieldName, field, selected).trim();
    const fieldType = field?.field_type ?? ctx.rootFieldType;

    // 其他类型（非 text / keyword / flattened）：统一等值
    if (
      fieldType
      && !isTextFieldType(fieldType)
      && !isKeywordLikeFieldType(fieldType)
      && fieldType !== 'string'
      && fieldType !== 'object'
      && fieldType !== 'nested'
      && fieldType !== '__virtual__'
    ) {
      return val === 'not' ? 'is not' : 'is';
    }

    if (isKeywordLikeFieldType(fieldType)) {
      if (fullPlain && selected && fullPlain === selected) {
        return val === 'not' ? 'is not' : 'is';
      }
      return val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    // text / string / object 叶子：完整等值用 is，否则 contains
    if (this.isObjectLeafClickContext(ctx, field, resolvedFieldName) || (fullPlain && selected && fullPlain !== selected)) {
      if (fullPlain && selected && fullPlain === selected) {
        return val === 'not' ? 'is not' : 'is';
      }
      return val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    // text 字段即便以 JSON 展示，点击分词仍按 contains（语句模式再格式化为引号短语）
    if (ctx.parsedFromJsonString || isTextFieldType(fieldType)) {
      return val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    return val === 'not' ? 'is not' : 'is';
  }

  onSegmentEnumClick(val, isLink) {
    // 优先使用 show tippy 时捕获的上下文，避免共享 virtual-target 残留属性 / 错误 formatter 实例污染结果
    const fallback = this.getFieldNameValue();
    const ctx: SegmentClickContext = activeSegmentClickContext ?? {
      name: fallback.name ?? '',
      searchFieldName: fallback.searchFieldName ?? '',
      value: String(fallback.value ?? ''),
      depth: fallback.depth ?? '',
      segmentRole: fallback.segmentRole ?? '',
      parsedFromJsonString: !!this.config.options?.parsedFromJsonString || !!fallback.parsedFromJsonString,
      rootFieldName: this.config.field?.field_name ?? '',
      rootFieldType: this.config.field?.field_type ?? '',
      isVirtualObjNode: !!this.config.field?.is_virtual_obj_node,
      jsonValue: this.config.jsonValue,
    };

    // Text/String JSON：检索字段固定外层根字段；Object/Nested 解析叶子路径
    const isObjectRoot = ctx.rootFieldType === 'object'
      || ctx.rootFieldType === 'nested'
      || ctx.isVirtualObjNode;
    const resolvedFieldName = ctx.parsedFromJsonString && ctx.rootFieldName && !isObjectRoot
      ? ctx.rootFieldName
      : this.resolveFormatterSearchFieldName(ctx.name, ctx.searchFieldName);
    const activeField = this.getField(resolvedFieldName) ?? this.config.field;
    const selectedValue = ctx.value;
    const fieldType = activeField?.field_type;
    const fullPlain = this.resolveClickFullPlainValue(
      ctx,
      resolvedFieldName || activeField?.field_name || '',
      activeField,
      selectedValue,
    );

    const tippyTarget = segmentPopInstance.getInstance()?.reference as HTMLElement | undefined;
    // tippy.reference 是 body 虚拟节点：优先用点击时缓存的真实 .valid-text / 预计算位置
    const tokenPos = (typeof ctx.tokenCount === 'number' && ctx.tokenCount > 0)
      ? {
        tokenIndex: ctx.tokenIndex,
        tokenCount: ctx.tokenCount,
        isSoleToken: Boolean(ctx.isSoleToken),
      }
      : this.resolveValidTokenPosition(ctx.tokenEl || tippyTarget);
    const selectedPlain = String(selectedValue ?? '').replace(/<\/?mark>/g, '').trim();
    const normalizedFullPlain = String(fullPlain ?? '').replace(/<\/?mark>/g, '').trim();
    const isSoleToken = tokenPos.isSoleToken
      || (Boolean(normalizedFullPlain)
        && normalizedFullPlain !== '--'
        && normalizedFullPlain === selectedPlain);

    let target = ['date', 'date_nanos'].includes(fieldType)
      ? this.resolveDateFieldRawValue(
        ctx,
        resolvedFieldName || activeField?.field_name || '',
        activeField,
        selectedValue,
      )
      : selectedValue;

    // 其他类型：Value 统一补齐为完整 FieldValue
    // date/date_nanos 已在上方回取原始时间戳，且 fullPlain 同源，避免被展示串覆盖
    if (
      fieldType
      && !['date', 'date_nanos'].includes(fieldType)
      && !isTextFieldType(fieldType)
      && !isKeywordLikeFieldType(fieldType)
      && fieldType !== 'string'
      && fieldType !== 'object'
      && fieldType !== 'nested'
      && fieldType !== '__virtual__'
      && fullPlain
      && fullPlain !== '--'
    ) {
      target = fullPlain;
    }

    const operation = this.resolveSegmentClickOperation(
      val,
      ctx,
      activeField,
      resolvedFieldName,
      selectedValue,
    );

    const option = {
      fieldName: resolvedFieldName || activeField?.field_name,
      // 叶子字段优先用 store/fields 精确类型；找不到时再退父级
      fieldType: this.getField(resolvedFieldName)?.field_type
        ?? activeField?.field_type
        ?? fieldType,
      operation,
      // 语句模式格式化（通配 / 引号）由 use-text-action 按字段类型统一处理
      value: target ?? selectedValue,
      fullPlain: normalizedFullPlain
        || (isSoleToken ? selectedPlain : ''),
      isSoleToken,
      tokenIndex: tokenPos.tokenIndex,
      tokenCount: tokenPos.tokenCount,
      depth: ctx.depth,
    };

    this.config.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
    activeSegmentClickContext = null;

    // 添加/排除检索后清空选区，避免残留划选让下次点击误走划词链路
    if (val === 'is' || val === 'not' || val === 'new-search-page-is') {
      window.getSelection()?.removeAllRanges();
    }
  }

  isValidTraceId(traceId) {
    const traceIdPattern = /^[a-f0-9]{32}$/;
    return traceIdPattern.test(traceId);
  }

  handleSegmentClick(e: MouseEvent, value) {
    // 如果是点击划选文本，则不进行处理
    if (RetrieveHelper.isClickOnSelection(e, 2) || window?.getSelection()?.toString()?.length > 1) {
      return;
    }
    if (!value.toString() || value === '--') {
      return;
    }

    const clickTarget = e.target as HTMLElement;
    const valueElement = clickTarget.closest('.field-value') as HTMLElement;
    const searchFieldElement = (clickTarget.closest('[data-segment-field-name]')
      || clickTarget.closest('[data-search-field-name]')) as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
    const fieldType = valueElement?.getAttribute('data-field-type')
      || this.config.field?.field_type
      || '';
    // Object/Nested 始终走叶子 segment 路径，即使 DOM 误带了 data-json-text-value
    const isObjectLikeField = fieldType === 'object'
      || fieldType === 'nested'
      || !!this.config.field?.is_virtual_obj_node;
    const isJsonTextValue = !isObjectLikeField && (
      valueElement?.getAttribute('data-json-text-value') === 'true'
      || !!this.config.options?.parsedFromJsonString
      || clickTarget.closest('[data-json-text-value="true"]') != null
      || clickTarget.closest('[data-json-string-parsed="true"]') != null
    );
    // Text/String JSON：检索字段固定为外层字段；Object 使用叶子 segment 路径并回归 Fields 列表
    const rawSearchFieldName = isJsonTextValue
      ? (valueElement?.getAttribute('data-search-field-name')
        || valueElement?.getAttribute('data-field-name')
        || this.config.field?.field_name
        || '')
      : (searchFieldElement?.getAttribute('data-segment-field-name')
        || searchFieldElement?.getAttribute('data-search-field-name')
        || '');
    const searchFieldName = this.clampToMappedFieldPath(
      rawSearchFieldName,
      this.config.field?.field_name,
    );
    const segmentRole = isJsonTextValue
      ? ''
      : searchFieldElement?.getAttribute('data-segment-field-role');

    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('[data-item-id="trace-view"]') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');

    // 根据字段信息隐藏虚拟字段相关的选项
    const isVirtualField = fieldType === '__virtual__';
    const virtualFieldHiddenItems = ['is', 'not', 'new-search-page-is']; // 需要隐藏的选项

    virtualFieldHiddenItems.forEach((itemId) => {
      const element = content.value.querySelector(`[data-item-id="${itemId}"]`) as HTMLElement;
      element?.style.setProperty('display', isVirtualField ? 'none' : 'inline-flex');
    });

    // 这里的动态样式用于只显示"添加到本次检索"、"从本次检索中排除"
    const hasSegmentLightStyle = document.getElementById('dynamic-segment-light-style') !== null;

    // 若是应用了动态样式(实时日志/上下文)，且是虚拟字段，则不显示弹窗(弹窗无内容)
    if (hasSegmentLightStyle && isVirtualField) {
      return;
    }

    const { offsetX, offsetY } = getClickTargetElement(e);
    const target = setPointerCellClickTargetHandler(e, { offsetX, offsetY });

    const depth = valueElement?.closest('[data-depth]')?.getAttribute('data-depth')
      ?? clickTarget.closest('[data-depth]')?.getAttribute('data-depth');

    // 共享 virtual-target 必须先清空再写入，否则上次 KEY role / 字段路径会残留，导致同词多次点击结果漂移
    this.clearVirtualTargetSegmentAttrs(target);
    target.setAttribute('data-field-value', String(value ?? ''));
    target.setAttribute('data-field-name', fieldName ?? '');
    target.setAttribute('data-search-field-name', searchFieldName ?? '');
    target.setAttribute('data-segment-field-name', searchFieldName ?? '');
    target.setAttribute('data-field-dpth', depth ?? '');
    if (segmentRole) {
      target.setAttribute('data-segment-field-role', segmentRole);
    }

    // tippy 挂在 body 虚拟节点上：分词位置必须在点击当下用外层 .valid-text 预计算
    const tokenEl = resolveOuterValidText(clickTarget) || clickTarget;
    const tokenPos = this.resolveValidTokenPosition(tokenEl);

    activeSegmentClickContext = {
      name: fieldName ?? '',
      searchFieldName: searchFieldName ?? '',
      value: String(value ?? ''),
      depth: depth ?? '',
      segmentRole: segmentRole ?? '',
      parsedFromJsonString: !!this.config.options?.parsedFromJsonString
        || clickTarget.closest('[data-json-string-parsed="true"]') != null,
      rootFieldName: this.config.field?.field_name ?? '',
      rootFieldType: this.config.field?.field_type ?? '',
      isVirtualObjNode: !!this.config.field?.is_virtual_obj_node,
      jsonValue: this.config.jsonValue,
      tokenEl,
      tokenIndex: tokenPos.tokenIndex,
      tokenCount: tokenPos.tokenCount,
      isSoleToken: tokenPos.isSoleToken,
    };

    // 再次注册当前实例回调，确保 taskEventManager.activeKey 指向本次点击的 formatter
    segmentPopInstance.show(target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
  }

  isTextField(field: any) {
    return field?.field_type === 'text';
  }

  isAnalyzed(field: any) {
    return field?.is_analyzed ?? false;
  }

  escapeString(val: string) {
    const map = {
      '&amp;': '&',
      '&lt;': '<',
      '&gt;': '>',
      '&quot;': '"',
      '&#x27;': "'",
    };

    return typeof val !== 'string'
      ? val
      : val.replace(new RegExp(`(${Object.keys(map).join('|')})`, 'g'), match => map[match]);
  }

  getSplitList(field: any, content: any, options: { usePrecomputedSegments?: boolean } = {}) {
    const fieldName = typeof field === 'string' ? field : field?.field_name;
    const usePrecomputedSegments = options.usePrecomputedSegments ?? true;
    const precomputedSegments = fieldName ? this.config.precomputedSegments?.[fieldName] : undefined;
    if (usePrecomputedSegments && Array.isArray(precomputedSegments)) {
      return precomputedSegments;
    }

    const value = this.escapeString(`${content}`);
    // 统一走 splitRenderText：分词边界与无 mark 时一致，<mark> 仅映射为 resultRanges
    return splitRenderText(value, field, {
      isSerializedComposite: field?.field_type === 'object' || field?.is_virtual_obj_node,
    });
  }

  getChildItem(item, pageRanges?: HighlightRange[]) {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    const text = item.text?.length ? item.text : '""';
    const textNode = document.createElement('span');
    const resultRanges = item.resultRanges?.length
      ? item.resultRanges
      : (item.isMark ? [{ start: 0, end: text.length }] : undefined);

    if (!(item.isNotParticiple || item.isBlobWord) && item.isCursorText) {
      textNode.classList.add('valid-text');
    } else if (item.isNotParticiple || item.isBlobWord) {
      textNode.classList.add('others-text');
    } else if (!item.isCursorText) {
      // MAX_TOKENS 截断尾巴：整段不可点长文本，单独标记，不改动 valid-text KEY/VALUE 分词
      const plain = text.replace(/<\/?mark>/g, '');
      if (plain.length > 1) {
        textNode.classList.add('blob-text');
      } else {
        textNode.classList.add('others-text');
      }
    }

    textNode.appendChild(highlightPlainTextIntoFragment({
      text: text.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      resultRanges,
      pageRanges,
    }));
    return textNode;
  }

  creatSegmentNodes = () => {
    const segmentNode = document.createElement('span');
    segmentNode.classList.add('segment-content');
    segmentNode.classList.add('bklog-scroll-cell');

    return segmentNode;
  };

  /**
   * Origin 模式下 JSON 解析开关关闭时，仍然保持原始字符串的渲染方式，
   * 但为 JSON 中的 KEY/VALUE 分词补充真实叶子字段路径。这样不会改变展示，
   * 也不会把 data-search-field-name（划词语义）改成子字段路径。
   *
   * 额外：仅为 MAX_TOKENS 截断尾巴（.blob-text）绑定根字段元信息与偏移，
   * 不改动已有 .valid-text 的 segment 绑定逻辑。
   */
  private annotateTruncatedBlobSpans(target: HTMLElement, text: string, rootFieldName: string) {
    const field = this.getField(rootFieldName)
      ?? (this.config.field?.field_name === rootFieldName ? this.config.field : undefined);
    const fieldType = field?.field_type ?? target.getAttribute('data-field-type') ?? '';
    const segmentRoot = target.querySelector('.segment-content') as HTMLElement | null;
    if (!segmentRoot) return;

    let offset = 0;
    const children = Array.from(segmentRoot.children) as HTMLElement[];
    for (const segment of children) {
      if (!(segment instanceof HTMLElement) || segment.classList.contains('last-placeholder')) {
        continue;
      }
      const segmentText = segment.textContent ?? '';
      const start = text.indexOf(segmentText, offset);
      if (start < 0) {
        continue;
      }
      // 只给 getChildItem 已标记的截断尾巴补元信息，绝不把普通 others-text 提升为 blob
      if (segment.classList.contains('blob-text')) {
        segment.setAttribute('data-blob-text-offset', String(start));
        segment.setAttribute('data-field-name', rootFieldName);
        segment.setAttribute('data-search-field-name', rootFieldName);
        if (fieldType) {
          segment.setAttribute('data-field-type', fieldType);
        }
      }
      offset = start + segmentText.length;
    }
  }

  /**
   * 解析 JSON KEY/VALUE 区间：优先用完整原文（segmentResolveText），
   * 截断展示串仅用于 DOM 分词偏移对齐（其为完整原文前缀）。
   */
  private resolveJsonSegmentRanges(displayText: string, rootFieldName: string) {
    const resolveText = String(this.config.options?.segmentResolveText ?? '').replace(/<\/?mark>/gim, '');
    const candidates = [resolveText, displayText].filter((item, index, list) => {
      if (!item || !/^\s*[\[{]/.test(item)) return false;
      return list.indexOf(item) === index;
    });
    for (const candidate of candidates) {
      const ranges = getJsonSegmentRanges(candidate, rootFieldName);
      if (ranges.length) {
        return ranges;
      }
    }
    return [];
  }

  private bindRawJsonSegmentFields(target: HTMLElement, displayText: string, rootFieldName: string) {
    // ranges 来自完整原文；offset 按截断展示串计算（前 1000 与原文前缀对齐）
    const ranges = this.resolveJsonSegmentRanges(displayText, rootFieldName);
    if (ranges.length) {
      let offset = 0;
      const segments = listOuterValidTextNodes(target.querySelector('.segment-content') ?? target);
      for (const segment of segments) {
        const segmentText = segment.textContent ?? '';
        const start = displayText.indexOf(segmentText, offset);
        if (start < 0) continue;
        const end = start + segmentText.length;
        const range = ranges.find(item => start < item.end && end > item.start);
        if (range) {
          // DOM 绑定即收敛：未映射深路径回溯到 Fields 最长前缀
          const mappedPath = this.clampToMappedFieldPath(range.fieldName, rootFieldName);
          segment.setAttribute('data-segment-field-name', mappedPath);
          if (range.role) segment.setAttribute('data-segment-field-role', range.role);
        }
        offset = end;
      }
    }

    // 仅标注截断长文本尾巴，不影响上述 valid-text KEY/VALUE 绑定
    this.annotateTruncatedBlobSpans(target, displayText, rootFieldName);
  }

  initStringAsValue(text?: string, appendText?: SegmentAppendText) {
    let root = this.getTargetRoot() as HTMLElement;
    if (root) {
      if (root.classList.contains('field-value')) {
        root = root.parentElement;
      }

      const fieldName = (root.querySelector('.field-name .black-mark') as HTMLElement)?.getAttribute('data-field-name');
      this.setNodeValueWordSplit(root, fieldName, '.field-value', text, appendText);
      // 未执行 JSON 解析时，setNodeValueWordSplit 仍按原始整段文本渲染。
      // 仅给可定位到的 JSON KEY/VALUE token 增加分词专用字段路径，
      // data-search-field-name 继续保留根字段，确保划词逻辑不变。
      const resolveText = String(this.config.options?.segmentResolveText ?? text ?? '')
        .replace(/<\/?mark>/gim, '');
      const lookLikeJson = text && /^\s*[\[{]/.test(text)
        || !!resolveText && /^\s*[\[{]/.test(resolveText);
      if (text && fieldName && lookLikeJson) {
        const valueElement = root.querySelector('.field-value') as HTMLElement;
        if (valueElement) {
          const field = this.getField(fieldName)
            ?? (this.config.field?.field_name === fieldName ? this.config.field : undefined);
          const isObjectLikeField = field?.field_type === 'object'
            || field?.field_type === 'nested'
            || !!field?.is_virtual_obj_node;
          // 仅 Text/String 的 JSON 外观打标；Object/Nested 依赖 data-segment-field-name 做叶子 KEY/VALUE 解析
          if (!isObjectLikeField) {
            valueElement.setAttribute('data-json-text-value', 'true');
          }
          this.bindRawJsonSegmentFields(valueElement, text, fieldName);
        }
      }
    }
  }

  addWordSegmentClick(root: HTMLElement) {
    if (!root.hasAttribute('data-word-segment-click')) {
      root.setAttribute('data-word-segment-click', '1');
      root.addEventListener('click', (e) => {
        const validTextElement = resolveOuterValidText(e.target as HTMLElement);
        if (validTextElement) {
          this.handleSegmentClick(e, validTextElement.textContent);
        }
      });
    }
  }

  setNodeValueWordSplit(
    target: HTMLElement,
    fieldName,
    valueSelector = '.bklog-json-field-value',
    textValue?: string,
    appendText?: SegmentAppendText,
  ) {
    this.addWordSegmentClick(target);
    for (const element of target.querySelectorAll(valueSelector)) {
      const targetElement = element as HTMLElement;
      const nextText = String(textValue ?? targetElement.textContent ?? '');
      const prevText = wordSplitSourceByElement.get(targetElement) ?? '';
      const hasSplit = targetElement.hasAttribute('data-has-word-split');
      const hasSegmentDom = Boolean(targetElement.querySelector('.segment-content, .valid-text'));
      // 内容变化、或 Vue 冲掉了分词 DOM 但标志残留时，必须重建，否则划词/点击解析漂移
      const shouldRebuild = !hasSplit || prevText !== nextText || (hasSplit && !hasSegmentDom);
      if (!shouldRebuild) {
        continue;
      }

      const text = nextText;
      targetElement.removeAttribute('data-has-word-split');
      // 兼容历史 DOM：曾把大段原文写入 Attr，重建时清掉
      targetElement.removeAttribute('data-word-split-source');
      // getField 已含根字段回退；此处再兜底一次，避免动态 Visible 时 Object 整段不分词
      const field = this.getField(fieldName)
        ?? (this.config.field?.field_name === fieldName || !fieldName ? this.config.field : undefined);
      const vlaues = this.getSplitList(field, text);

      targetElement.setAttribute('data-has-word-split', '1');
      // 原文只进内存 WeakMap，禁止写入 DOM Attr
      wordSplitSourceByElement.set(targetElement, text);
      targetElement.setAttribute('data-field-name', fieldName);
      // 非 JSON 树场景：根字段即检索字段；有 JSON 绑定时空缺时降级到此值
      if (fieldName) {
        targetElement.setAttribute('data-search-field-name', fieldName);
      }
      targetElement.setAttribute('data-field-type', field?.field_type ?? '');
      // 仅 Text/String 解析出的 JSON 外观打标；Object/Nested 绝不打此标
      const isObjectLikeField = field?.field_type === 'object'
        || field?.field_type === 'nested'
        || !!field?.is_virtual_obj_node;
      if (this.config.options?.parsedFromJsonString && !isObjectLikeField) {
        targetElement.setAttribute('data-json-text-value', 'true');
      } else {
        targetElement.removeAttribute('data-json-text-value');
      }

      if (targetElement.hasAttribute('data-with-intersection')) {
        targetElement.style.setProperty('min-height', [targetElement.offsetHeight, 'px'].join(''));
      }

      targetElement.innerHTML = '';

      const segmentContent = this.creatSegmentNodes();
      const segmentPageRanges = buildSegmentPageHighlightRanges(vlaues);

      const { setListItem, removeScrollEvent } = setScrollLoadCell(
        vlaues,
        targetElement,
        segmentContent,
        (item, index) => this.getChildItem(item, segmentPageRanges[index]),
      );
      removeScrollEvent();

      targetElement.append(segmentContent);
      const plainText = String(text ?? '').replace(/<\/?mark>/gim, '');
      // 必须覆盖 MAX_TOKENS 截断尾巴（通常为第 1001 个 token），否则 blob 不进 DOM
      setListItem(Math.max(1000, vlaues.length), () => {
        if (fieldName && plainText) {
          if (/^\s*[\[{]/.test(plainText)) {
            this.bindRawJsonSegmentFields(targetElement, plainText, fieldName);
          } else {
            this.annotateTruncatedBlobSpans(targetElement, plainText, fieldName);
          }
        }
        this.config.onSegmentRenderUpdate?.();
      });

      if (appendText !== undefined) {
        const appendElement = document.createElement('span');
        appendElement.textContent = appendText.text;
        if (appendText.onClick) {
          appendElement.addEventListener('click', appendText.onClick);
        }
        if (appendText.onMouseDown) {
          appendElement.addEventListener('mousedown', appendText.onMouseDown);
        }
        if (appendText.onMouseUp) {
          appendElement.addEventListener('mouseup', appendText.onMouseUp);
        }

        for (const key of Object.keys(appendText.attributes ?? {})) {
          appendElement.setAttribute(key, appendText.attributes[key]);
        }

        targetElement.firstChild?.appendChild(appendElement);
      }

      requestAnimationFrame(() => {
        targetElement.style.removeProperty('min-height');
      });
    }
  }

  handleExpandNode(args) {
    if (args.isExpand) {
      // const target = args.targetElement as HTMLElement;
      // const rootElement = args.rootElement as HTMLElement;
      // const fieldName = (rootElement.parentNode.querySelector('.field-name .black-mark') as HTMLElement)?.innerText;
      // this.setNodeValueWordSplit(target, fieldName, '.bklog-json-field-value');
    }
  }

  get computedOptions() {
    return {
      mode: 'view',
      navigationBar: false,
      statusBar: false,
      mainMenuBar: false,
      onExpand: this.handleExpandNode.bind(this),
      ...(this.config.options ?? {}),
    };
  }

  getTargetRoot() {
    if (Array.isArray(this.config.target.value)) {
      return this.config.target.value[0];
    }

    return this.config.target.value;
  }

  initEditor(depth) {
    const targetRoot = this.getTargetRoot();
    if (!targetRoot) {
      this.editor = undefined;
      return false;
    }

    this.localDepth = depth;
    this.editor = new JsonView(targetRoot, {
      onNodeExpand: this.handleExpandNode.bind(this),
      depth,
      field: this.config.field,
      parsedFromJsonString: !!this.config.options?.parsedFromJsonString,
      resolveFieldDisplayName: this.config.options?.resolveFieldDisplayName,
      resolveMappedFieldPath: (fieldPath: string) => this.clampToMappedFieldPath(
        fieldPath,
        this.config.field?.field_name,
      ),
      segmentRender: (value: string, rootNode: HTMLElement) => {
        this.renderLeafSegment(value, rootNode);
      },
    });

    this.editor.initClickEvent((e) => {
      const actionBtn = (e.target as HTMLElement).closest?.('.btn-json-leaf-more') as HTMLElement | null;
      if (actionBtn) {
        return;
      }
      const validTextElement = resolveOuterValidText(e.target as HTMLElement);
      if (validTextElement) {
        this.handleSegmentClick(e, validTextElement.textContent);
      }
    });

    return true;
  }

  /**
   * JSON 解析模式下：对叶子节点（string / number / boolean / bigint，
   * 或不可继续 parse 的字符串）做分词渲染并消费页面高亮状态。
   * 长字符串默认展示前 1000 字符；超出显示「更多」，展开最多 16KB，支持「收起」
   */
  renderLeafSegment(value: string, rootNode: HTMLElement, forceExpanded = false) {
    const taskId = this.segmentTaskId;
    const enableLeafTruncate = !!this.config.options?.enableLeafTruncate;
    const fullText = String(value ?? '');
    const plainLength = stripMark(fullText).length;
    const isTruncatable = enableLeafTruncate && plainLength > ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH;
    const isExpanded = forceExpanded || rootNode.getAttribute('data-leaf-expanded') === '1';

    let renderText = fullText;
    if (isTruncatable) {
      renderText = isExpanded
        ? truncateMarkedTextByChars(fullText, ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH)
        : truncateMarkedTextByChars(fullText, ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH);
      rootNode.setAttribute('data-leaf-truncatable', '1');
      rootNode.setAttribute('data-leaf-expanded', isExpanded ? '1' : '0');
    } else {
      rootNode.removeAttribute('data-leaf-truncatable');
      rootNode.removeAttribute('data-leaf-expanded');
    }

    const leafFieldName = this.clampToMappedFieldPath(
      rootNode.getAttribute('data-search-field-name')
        || rootNode.getAttribute('data-segment-field-name')
        || this.config.field?.field_name,
      this.config.field?.field_name,
    );
    const leafField = this.getField(leafFieldName) ?? leafFieldName ?? this.config.field;
    // 叶子节点属性也回写收敛后的路径，保证后续点击/划词读取一致
    if (leafFieldName) {
      rootNode.setAttribute('data-search-field-name', leafFieldName);
    }
    // JSON String 解析出的所有叶子都绑定外层真实字段用于检索，但外层字段的
    // precomputedSegments 表示整段原始 JSON，不能复用于单个叶子。否则每个
    // ip/name/port 都会重复渲染完整 JSON。叶子应基于自身 value 重新分词。
    const isParsedFromJsonStringLeaf = !!this.config.options?.parsedFromJsonString
      || rootNode.closest('[data-json-string-parsed="true"]') !== null;
    const vlaues = this.getSplitList(leafField, renderText, {
      usePrecomputedSegments: !isTruncatable && !isParsedFromJsonStringLeaf,
    });
    if (taskId !== this.segmentTaskId || !rootNode.isConnected) return;

    rootNode.innerHTML = '';
    const segmentContent = this.creatSegmentNodes();
    rootNode.append(segmentContent);

    if (!rootNode.classList.contains('bklog-scroll-box')) {
      rootNode.classList.add('bklog-scroll-box');
    }

    const segmentPageRanges = buildSegmentPageHighlightRanges(vlaues);
    const { setListItem, removeScrollEvent } = setScrollLoadCell(
      vlaues,
      rootNode,
      segmentContent,
      (item, index) => this.getChildItem(item, segmentPageRanges[index]),
    );
    removeScrollEvent();

    // 「更多/收起」必须与分词渲染解耦：setListItem 在词元一次填满时可能不回调 next
    if (isTruncatable) {
      this.appendLeafMoreAction(rootNode, fullText, isExpanded);
    }

    setListItem(600, this.config.onSegmentRenderUpdate);
  }

  appendLeafMoreAction(rootNode: HTMLElement, fullText: string, isExpanded: boolean) {
    const existing = rootNode.querySelector('.btn-json-leaf-more');
    existing?.remove();

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn-json-leaf-more';
    btn.textContent = isExpanded
      ? (window.$t?.('收起') ?? '收起')
      : (window.$t?.('更多') ?? '更多');
    btn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');

    const stop = (e: Event) => {
      e.stopPropagation();
      e.preventDefault();
      (e as any).stopImmediatePropagation?.();
    };

    btn.addEventListener('mousedown', stop);
    btn.addEventListener('mouseup', stop);
    btn.addEventListener('click', (e) => {
      stop(e);
      RetrieveHelper.jsonFormatter.setIsExpandNodeClick(true);
      const nextExpanded = rootNode.getAttribute('data-leaf-expanded') !== '1';
      rootNode.setAttribute('data-leaf-expanded', nextExpanded ? '1' : '0');
      this.renderLeafSegment(fullText, rootNode, nextExpanded);
    });

    // 放在分词容器之后，保证始终可见
    rootNode.append(btn);
  }

  setNodeExpand([currentDepth]) {
    this.editor?.expand(currentDepth);
  }

  setValue(depth) {
    this.setValuePromise = new Promise((resolve, reject) => {
      try {
        this.segmentTaskId += 1;
        if (!this.editor && !this.initEditor(depth)) {
          resolve(false);
          return;
        }

        this.editor?.setValue(this.config.jsonValue);
        this.setNodeExpand([depth]);
        this.localDepth = depth;
        resolve(true);
      } catch (e) {
        reject(e);
      }
    });

    return this.setValuePromise;
  }

  setExpand(depth) {
    this.setValuePromise?.then(() => {
      if (!this.editor && !this.initEditor(depth)) return;

      this.setNodeExpand([depth]);
      this.localDepth = depth;
    }).catch(() => undefined);
  }

  destroy() {
    this.segmentTaskId += 1;
    this.editor?.destroy();
    this.editor = undefined;
    const root = this.getTargetRoot() as HTMLElement;
    if (root) {
      let target = root;
      if (!root.classList.contains('field-value')) {
        target = root.querySelector('.field-value');
      }

      if (target?.hasAttribute('data-has-word-split')) {
        target.removeAttribute('data-has-word-split');
        target.removeAttribute('data-word-split-source');
        clearWordSplitSourceCache(target);
      }

      if (target && typeof this.config.jsonValue === 'string') {
        target.textContent = this.config.jsonValue;
      }
    }
  }

  getEditor() {
    return {
      setValue: this.setValue.bind(this),
      setExpand: this.setExpand.bind(this),
      initEditor: this.initEditor.bind(this),
      destroy: this.destroy.bind(this),
    };
  }
}
