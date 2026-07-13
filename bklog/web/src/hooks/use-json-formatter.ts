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
import { highlightPlainTextIntoFragment } from '@/views/retrieve-core/page-highlight';

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  getClickTargetElement,
  optimizedSplit,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import LuceneSegment from './lucene.segment';
import UseSegmentPropInstance from './use-segment-pop';
import {
  ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH,
  ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH,
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
}>>;
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
    return this.config.fields.find(item => item.field_name === fieldName);
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
    let searchFieldName = target.getAttribute('data-search-field-name');
    let value = target.getAttribute('data-field-value');
    let depth = target.getAttribute('data-field-dpth');

    if (value === undefined || value === null) {
      value = target.textContent;
    }

    if (!searchFieldName) {
      searchFieldName = target.closest('[data-search-field-name]')?.getAttribute('data-search-field-name');
    }

    if (name === undefined || name === null) {
      const valueElement = tippyInstance.reference.closest('.field-value') as HTMLElement;
      name = valueElement?.getAttribute('data-field-name');
    }

    if (depth === undefined || depth === null) {
      depth = target.closest('[data-depth]')?.getAttribute('data-depth');
    }

    return { value, name, depth, searchFieldName };
  }

  onSegmentEnumClick(val, isLink) {
    const { name, value, depth, searchFieldName } = this.getFieldNameValue();
    const resolvedFieldName = this.resolveFormatterSearchFieldName(name, searchFieldName);
    const activeField = this.getField(resolvedFieldName) ?? this.config.field;
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.config.jsonValue?.[activeField?.field_name]
      : value;

    const option = {
      fieldName: resolvedFieldName || activeField?.field_name,
      fieldType: activeField?.field_type,
      operation: val === 'not' ? 'is not' : val,
      value: target ?? value,
      depth,
    };

    this.config.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
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
    const searchFieldElement = clickTarget.closest('[data-search-field-name]') as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
    const searchFieldName = searchFieldElement?.getAttribute('data-search-field-name');
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

    target.setAttribute('data-field-value', value);
    target.setAttribute('data-field-name', fieldName ?? '');
    if (searchFieldName) {
      target.setAttribute('data-search-field-name', searchFieldName);
    }
    target.setAttribute('data-field-dpth', depth ?? '');

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

    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = this.escapeString(`${content}`);
    if (this.isAnalyzed(field)) {
      if (field.tokenize_on_chars) {
        // 这里进来的都是开了分词的情况
        return optimizedSplit(value, field.tokenize_on_chars);
      }

      return LuceneSegment.split(value, 1000);
    }

    // 非 analyzed（含 Object stringify）：必须按 <mark> 切开，
    // 否则任意子字段命中都会把整段 VALUE 标成 isMark，导致 Column 整块高亮。
    if (new RegExp(markRegStr, 'i').test(value)) {
      return value
        .split(/(<mark>.*?<\/mark>)/gi)
        .filter(Boolean)
        .map((part) => {
          const isMark = /<mark>.*?<\/mark>/i.test(part);
          return {
            text: part.replace(/<\/?mark>/gi, ''),
            isMark,
            isNotParticiple: this.isTextField(field),
            isCursorText: true,
          };
        });
    }

    return [
      {
        text: value,
        isNotParticiple: this.isTextField(field),
        isMark: false,
        isCursorText: true,
      },
    ];
  }

  getChildItem(item) {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    const text = item.text?.length ? item.text : '""';
    const textNode = document.createElement('span');

    if (item.isMark) {
      textNode.classList.add('valid-text');
      textNode.appendChild(highlightPlainTextIntoFragment({
        text: text.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
        resultHighlighted: true,
      }));
      return textNode;
    }

    if (!(item.isNotParticiple || item.isBlobWord)) {
      if (item.isCursorText) {
        textNode.classList.add('valid-text');
      }
      textNode.appendChild(highlightPlainTextIntoFragment({ text }));
      return textNode;
    }

    textNode.classList.add('others-text');
    textNode.appendChild(highlightPlainTextIntoFragment({ text }));
    return textNode;
  }

  creatSegmentNodes = () => {
    const segmentNode = document.createElement('span');
    segmentNode.classList.add('segment-content');
    segmentNode.classList.add('bklog-scroll-cell');

    return segmentNode;
  };

  initStringAsValue(text?: string, appendText?: SegmentAppendText) {
    let root = this.getTargetRoot() as HTMLElement;
    if (root) {
      if (root.classList.contains('field-value')) {
        root = root.parentElement;
      }

      const fieldName = (root.querySelector('.field-name .black-mark') as HTMLElement)?.getAttribute('data-field-name');
      this.setNodeValueWordSplit(root, fieldName, '.field-value', text, appendText);
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
        const field = this.getField(fieldName);
        const vlaues = this.getSplitList(field, text);
        const targetElement = element as HTMLElement;

        targetElement.setAttribute('data-has-word-split', '1');
        targetElement.setAttribute('data-field-name', fieldName);
        // 非 JSON 树场景：根字段即检索字段；有 JSON 绑定时空缺时降级到此值
        if (fieldName) {
          targetElement.setAttribute('data-search-field-name', fieldName);
        }
        targetElement.setAttribute('data-field-type', field?.field_type);

        if (targetElement.hasAttribute('data-with-intersection')) {
          targetElement.style.setProperty('min-height', [targetElement.offsetHeight, 'px'].join(''));
        }

        targetElement.innerHTML = '';

        const segmentContent = this.creatSegmentNodes();

        const { setListItem, removeScrollEvent } = setScrollLoadCell(
          vlaues,
          targetElement,
          segmentContent,
          this.getChildItem,
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
      maxParseDepth: depth,
      field: this.config.field,
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
   * 或不可再 parse / 已超深度的残留字符串）做分词渲染并消费页面高亮状态。
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

    const vlaues = this.getSplitList(this.config.field, renderText, { usePrecomputedSegments: false });
    if (taskId !== this.segmentTaskId || !rootNode.isConnected) return;

    rootNode.innerHTML = '';
    const segmentContent = this.creatSegmentNodes();
    rootNode.append(segmentContent);

    if (!rootNode.classList.contains('bklog-scroll-box')) {
      rootNode.classList.add('bklog-scroll-box');
    }

    const { setListItem, removeScrollEvent } = setScrollLoadCell(
      vlaues,
      rootNode,
      segmentContent,
      this.getChildItem,
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
