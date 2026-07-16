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

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  getClickTargetElement,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import UseSegmentPropInstance from './use-segment-pop';
import {
  ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH,
  ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH,
  splitRenderText,
  stripMark,
  truncateMarkedTextByChars,
} from '../storage/utils/retrieve-render-meta';

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
};

let activeSegmentClickContext: SegmentClickContext | null = null;

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
    const matched = this.config.fields?.find?.(item => item.field_name === fieldName);
    if (matched) return matched;
    // 动态新增 Visible 字段时，fields 列表可能尚未同步；根字段绑定始终可用
    if (this.config.field?.field_name === fieldName) {
      return this.config.field;
    }
    return undefined;
  }

  /**
   * 仅用于 json-formatter 检索字段解析：
   * 优先使用 JSON 树构建阶段绑定的 data-search-field-name（完整路径），
   * 再降级到 DOM field-name / 根字段绑定，避免影响 Expand KV 入口。
   */
  resolveFormatterSearchFieldName(domFieldName?: string | null, searchFieldName?: string | null) {
    const normalizeArrayPath = (path: string) => path.replace(/\.\d+(?=\.|$)/g, '');

    // 1) JSON 树节点已绑定完整检索路径：优先使用，不再回退到父级 object 字段
    if (typeof searchFieldName === 'string' && searchFieldName.length > 0) {
      const exact = this.getField(searchFieldName);
      if (exact?.field_name) {
        return exact.field_name;
      }

      const normalized = normalizeArrayPath(searchFieldName);
      if (normalized && normalized !== searchFieldName) {
        const matched = this.getField(normalized);
        if (matched?.field_name) {
          return matched.field_name;
        }
        return normalized;
      }

      return searchFieldName;
    }

    // 2) 非 JSON / 未绑定路径：沿用 DOM field-name
    if (typeof domFieldName === 'string' && domFieldName.length > 0) {
      const matched = this.getField(domFieldName);
      if (matched?.field_name) {
        return matched.field_name;
      }
      return domFieldName;
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

  private resolveClickFullPlainValue(
    ctx: SegmentClickContext,
    fieldName: string,
    field: Record<string, any> | undefined,
    selectedValue: string,
  ) {
    if (['date', 'date_nanos'].includes(field?.field_type)) {
      const raw = this.getPathValue(ctx.jsonValue, field?.field_name || fieldName)
        ?? ctx.jsonValue?.[field?.field_name || fieldName];
      return this.escapeString(String(raw ?? selectedValue ?? '')).replace(/<\/?mark>/g, '');
    }

    const leafValue = this.getObjectLeafValueFromContext(ctx, fieldName, undefined);
    if (leafValue !== undefined && leafValue !== null) {
      return this.escapeString(String(leafValue)).replace(/<\/?mark>/g, '');
    }

    // 根字段整段 VALUE（如 log / keyword 列）
    if (!fieldName || fieldName === ctx.rootFieldName) {
      const rootValue = typeof ctx.jsonValue === 'string' || typeof ctx.jsonValue === 'number'
        ? ctx.jsonValue
        : undefined;
      if (rootValue !== undefined && rootValue !== null) {
        return this.escapeString(String(rootValue)).replace(/<\/?mark>/g, '');
      }
    }

    return '';
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
   * 操作符判定（多次点击必须稳定）：
   * - KEY → contains
   * - 命中完整 VALUE → is
   * - 命中部分分词 → contains
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

    // Object/JSON 叶子或任意「部分命中」：完整等值用 is，否则 contains
    if (this.isObjectLeafClickContext(ctx, field, resolvedFieldName) || (fullPlain && selected && fullPlain !== selected)) {
      if (fullPlain && selected && fullPlain === selected) {
        return val === 'not' ? 'is not' : 'is';
      }
      return val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    if (ctx.parsedFromJsonString) {
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

    const resolvedFieldName = this.resolveFormatterSearchFieldName(ctx.name, ctx.searchFieldName);
    const activeField = this.getField(resolvedFieldName) ?? this.config.field;
    const selectedValue = ctx.value;
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? (this.getPathValue(ctx.jsonValue, activeField?.field_name)
        ?? ctx.jsonValue?.[activeField?.field_name]
        ?? selectedValue)
      : selectedValue;

    const operation = this.resolveSegmentClickOperation(
      val,
      ctx,
      activeField,
      resolvedFieldName,
      selectedValue,
    );

    const option = {
      fieldName: resolvedFieldName || activeField?.field_name,
      fieldType: activeField?.field_type,
      operation,
      value: target ?? selectedValue,
      depth: ctx.depth,
    };

    this.config.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();

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
    const searchFieldName = searchFieldElement?.getAttribute('data-segment-field-name')
      || searchFieldElement?.getAttribute('data-search-field-name');
    const segmentRole = searchFieldElement?.getAttribute('data-segment-field-role');
    const fieldType = valueElement?.getAttribute('data-field-type');

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
   */
  private getJsonSegmentRanges(text: string, rootFieldName: string) {
    const ranges: Array<{ start: number; end: number; fieldName: string; role?: 'key' | 'value' }> = [];
    let cursor = 0;

    const skipSpace = () => {
      while (/\s/.test(text[cursor] ?? '')) cursor += 1;
    };
    const readString = () => {
      const start = cursor;
      cursor += 1;
      while (cursor < text.length) {
        if (text[cursor] === '\\') {
          cursor += 2;
        } else if (text[cursor] === '"') {
          cursor += 1;
          return { start, end: cursor, contentStart: start + 1, contentEnd: cursor - 1 };
        } else {
          cursor += 1;
        }
      }
      return undefined;
    };
    const readPrimitive = () => {
      const start = cursor;
      while (cursor < text.length && !/[\s,}\]]/.test(text[cursor])) cursor += 1;
      return { start, end: cursor };
    };
    const readValue = (path: string) => {
      skipSpace();
      if (text[cursor] === '"') {
        const stringRange = readString();
        if (stringRange) {
          ranges.push({ start: stringRange.contentStart, end: stringRange.contentEnd, fieldName: path });
        }
        return;
      }
      if (text[cursor] === '{') {
        cursor += 1;
        skipSpace();
        while (cursor < text.length && text[cursor] !== '}') {
          const key = readString();
          if (!key) return;
          skipSpace();
          if (text[cursor] !== ':') return;
          cursor += 1;
          const childPath = `${path}.${text.slice(key.contentStart, key.contentEnd)}`;
          // KEY 的查询字段是其父级路径，值为 KEY 文本本身；不要把 KEY 当作叶子值。
          ranges.push({ start: key.contentStart, end: key.contentEnd, fieldName: path, role: 'key' });
          skipSpace();
          readValue(childPath);
          skipSpace();
          if (text[cursor] === ',') {
            cursor += 1;
            skipSpace();
          } else break;
        }
        if (text[cursor] === '}') cursor += 1;
        return;
      }
      if (text[cursor] === '[') {
        cursor += 1;
        let index = 0;
        skipSpace();
        while (cursor < text.length && text[cursor] !== ']') {
          readValue(`${path}.${index}`);
          index += 1;
          skipSpace();
          if (text[cursor] === ',') {
            cursor += 1;
            skipSpace();
          } else break;
        }
        if (text[cursor] === ']') cursor += 1;
        return;
      }
      const primitive = readPrimitive();
      if (primitive.end > primitive.start) ranges.push({ ...primitive, fieldName: path });
    };

    try {
      const parsed = JSON.parse(text);
      if (parsed === null || typeof parsed !== 'object') return [];
      skipSpace();
      readValue(rootFieldName);
    } catch {
      return [];
    }
    return ranges;
  }

  private bindRawJsonSegmentFields(target: HTMLElement, text: string, rootFieldName: string) {
    const ranges = this.getJsonSegmentRanges(text, rootFieldName);
    if (!ranges.length) return;

    let offset = 0;
    const segments = Array.from(target.querySelectorAll('.segment-content .valid-text')) as HTMLElement[];
    for (const segment of segments) {
      const segmentText = segment.textContent ?? '';
      const start = text.indexOf(segmentText, offset);
      if (start < 0) continue;
      const end = start + segmentText.length;
      const range = ranges.find(item => start < item.end && end > item.start);
      if (range) {
        segment.setAttribute('data-segment-field-name', range.fieldName);
        if (range.role) segment.setAttribute('data-segment-field-role', range.role);
      }
      offset = end;
    }
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
      if (text && fieldName && /^\s*[\[{]/.test(text)) {
        const valueElement = root.querySelector('.field-value') as HTMLElement;
        if (valueElement) this.bindRawJsonSegmentFields(valueElement, text, fieldName);
      }
    }
  }

  addWordSegmentClick(root: HTMLElement) {
    if (!root.hasAttribute('data-word-segment-click')) {
      root.setAttribute('data-word-segment-click', '1');
      root.addEventListener('click', (e) => {
        const validTextElement = (e.target as HTMLElement).closest?.('.valid-text') as HTMLElement | null;
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
      if (!element.getAttribute('data-has-word-split')) {
        const text = textValue ?? element.textContent;
        // getField 已含根字段回退；此处再兜底一次，避免动态 Visible 时 Object 整段不分词
        const field = this.getField(fieldName)
          ?? (this.config.field?.field_name === fieldName || !fieldName ? this.config.field : undefined);
        const vlaues = this.getSplitList(field, text);
        const targetElement = element as HTMLElement;

        targetElement.setAttribute('data-has-word-split', '1');
        targetElement.setAttribute('data-field-name', fieldName);
        // 非 JSON 树场景：根字段即检索字段；有 JSON 绑定时空缺时降级到此值
        if (fieldName) {
          targetElement.setAttribute('data-search-field-name', fieldName);
        }
        targetElement.setAttribute('data-field-type', field?.field_type ?? '');

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
        setListItem(1000, () => {
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

          element.firstChild.appendChild(appendElement);
        }

        requestAnimationFrame(() => {
          element.style.removeProperty('min-height');
        });
      }
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
      segmentRender: (value: string, rootNode: HTMLElement) => {
        this.renderLeafSegment(value, rootNode);
      },
    });

    this.editor.initClickEvent((e) => {
      const actionBtn = (e.target as HTMLElement).closest?.('.btn-json-leaf-more') as HTMLElement | null;
      if (actionBtn) {
        return;
      }
      const validTextElement = (e.target as HTMLElement).closest?.('.valid-text') as HTMLElement | null;
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

    const leafFieldName = rootNode.getAttribute('data-search-field-name') || this.config.field?.field_name;
    const leafField = this.getField(leafFieldName) ?? leafFieldName ?? this.config.field;
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
