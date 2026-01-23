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
import tippy from 'tippy.js';

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import store from '../store/index';
import { ActionType, MatchType, type FormData } from '@/views/retrieve-v2/search-result-tab/personalized-configuration/types';
import {
  getClickTargetElement,
  optimizedSplit,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import LuceneSegment from './lucene.segment';
import UseSegmentPropInstance, { type DynamicContentOption } from './use-segment-pop';

import type { Ref } from 'vue';

export type FormatterConfig = {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
  field: any;
  onSegmentClick: (_args: any) => void;
  options?: Record<string, any>;
};

export type SegmentAppendText = { text: string; onClick?: (..._args) => void; attributes?: Record<string, string> };

/**
 * 正则匹配范围信息
 */
export interface RegexMatchRange {
  start: number;
  end: number;
  matchedValue: string;
  taskName: string;
  jumpLink: string;
}

/**
 * 正则匹配配置（用于存储到 DOM）
 */
export interface RegexMatchConfig {
  taskName: string;
  jumpLink: string;
  matchedValue: string;
}

/**
 * 带匹配信息的分词结果
 */
export interface TokenWithMatch {
  text: string;
  isMark: boolean;
  isCursorText: boolean;
  isNotParticiple?: boolean;
  isBlobWord?: boolean;
  matchedConfigs?: RegexMatchConfig[];
}

export default class UseJsonFormatter {
  editor: JsonView;
  config: FormatterConfig;
  setValuePromise: Promise<any>;
  localDepth: number;
  getSegmentContent: (_keyRef: object, _fn: (..._args) => void) => Ref<HTMLElement>;
  keyRef: any;

  constructor(cfg: FormatterConfig) {
    this.config = cfg;
    this.setValuePromise = Promise.resolve(true);
    this.localDepth = 1;
    this.keyRef = {};
    this.getSegmentContent = UseSegmentPropInstance.getSegmentContent.bind(UseSegmentPropInstance);
  }

  update(cfg) {
    this.config = cfg;
  }

  getField(fieldName: string) {
    return this.config.fields.find(item => item.field_name === fieldName);
  }

  getFieldNameValue() {
    const tippyInstance = segmentPopInstance.getInstance();
    const target = tippyInstance.reference;
    let name = target.getAttribute('data-field-name');
    let value = target.getAttribute('data-field-value');
    let depth = target.getAttribute('data-field-dpth');

    if (value === undefined) {
      value = target.textContent;
    }

    if (name === undefined) {
      const valueElement = tippyInstance.reference.closest('.field-value') as HTMLElement;
      name = valueElement?.getAttribute('data-field-name');
    }

    if (depth === undefined) {
      depth = target.closest('[data-depth]')?.getAttribute('data-depth');
    }

    return { value, name, depth };
  }

  onSegmentEnumClick(val, isLink) {
    const { name, value, depth } = this.getFieldNameValue();
    const activeField = this.getField(name);
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.config.jsonValue?.[activeField?.field_name]
      : value;

    const option = {
      fieldName: activeField?.field_name,
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
    if (RetrieveHelper.isClickOnSelection(e, 2)) {
      return;
    }
    if (!value.toString() || value === '--') {
      return;
    }

    const valueElement = (e.target as HTMLElement).closest('.field-value') as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
    const fieldType = valueElement?.getAttribute('data-field-type');

    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('[data-item-id="trace-view"]') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');

    // 从点击的元素获取预计算的匹配配置
    const clickedElement = e.target as HTMLElement;
    const matchedConfigsAttr = clickedElement?.getAttribute('data-matched-configs');

    // 动态内容处理
    const dynamicOptions = this.getDynamicOptions(value, fieldName, matchedConfigsAttr);
    UseSegmentPropInstance.setDynamicContent(dynamicOptions);

    // 根据字段信息隐藏虚拟字段相关的选项
    const isVirtualField = fieldType === '__virtual__';
    const virtualFieldHiddenItems = ['is', 'not', 'new-search-page-is']; // 需要隐藏的选项

    virtualFieldHiddenItems.forEach((itemId) => {
      const element = content.value.querySelector(`[data-item-id="${itemId}"]`) as HTMLElement;
      element?.style.setProperty('display', isVirtualField ? 'none' : 'inline-flex');
    });

    // 这里的动态样式用于只显示"添加到本次检索"、"从本次检索中排除"
    const hasSegmentLightStyle = document.getElementById('dynamic-segment-light-style') !== null;

    // 若是应用了动态样式(实时日志/上下文)，且是虚拟字段，并且没有设置自定义跳转内容，此时弹窗无内容，不显示弹窗
    if (hasSegmentLightStyle && isVirtualField && dynamicOptions === null) {
      return;
    }

    const { offsetX, offsetY } = getClickTargetElement(e);
    const target = setPointerCellClickTargetHandler(e, { offsetX, offsetY });

    const depth = valueElement.closest('[data-depth]')?.getAttribute('data-depth');

    target.setAttribute('data-field-value', value);
    target.setAttribute('data-field-name', fieldName);
    target.setAttribute('data-field-dpth', depth);

    segmentPopInstance.show(target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
  }

  /**
   * 获取动态选项配置
   * 根据个性化配置判断返回需要追加的跳转选项
   * 优先使用字段匹配，如果没有匹配内容再判断预计算的正则匹配配置
   * @param value 点击的值
   * @param fieldName 字段名
   * @param matchedConfigsAttr 预计算的匹配配置（从 DOM 属性获取）
   */
  getDynamicOptions(
    value: string, fieldName: string, matchedConfigsAttr?: string | null,
  ): DynamicContentOption[] | null {
    const options: DynamicContentOption[] = [];

    const personalizationSettings: FormData[] = store.
      state.indexFieldInfo?.custom_config?.personalization?.settings ?? [];

    // 1. 优先使用字段匹配
    const fieldJumpSettings = personalizationSettings.filter(
      setting => setting.actionType === ActionType.JUMP && setting.matchType === MatchType.FIELD,
    );

    for (const setting of fieldJumpSettings) {
      if (fieldName === setting.selectField) {
        options.push({
          text: setting.taskName,
          iconName: 'icon bklog-icon bklog-jump',
          onClick: () => {
            const jumpUrl = setting.jumpLink.replace(/\{[^}]+\}/g, encodeURIComponent(value));
            window.open(jumpUrl, '_blank');
          },
        });
      }
    }

    // 2. 如果字段匹配没有结果，再使用预计算的正则匹配配置
    if (options.length === 0 && matchedConfigsAttr) {
      try {
        const matchedConfigs: RegexMatchConfig[] = JSON.parse(matchedConfigsAttr);
        for (const config of matchedConfigs) {
          options.push({
            text: config.taskName,
            iconName: 'icon bklog-icon bklog-jump',
            onClick: () => {
              const jumpUrl = config.jumpLink.replace(/\{[^}]+\}/g, encodeURIComponent(config.matchedValue));
              window.open(jumpUrl, '_blank');
            },
          });
        }
      } catch {
        // JSON 解析失败，忽略
      }
    }

    return options.length > 0 ? options : null;
  }

  isTextField(field: any) {
    return field?.field_type === 'text';
  }

  isAnalyzed(field: any) {
    return field?.is_analyzed ?? false;
  }

  /**
   * 获取正则匹配的范围信息
   * 在分词前预先计算所有正则匹配的位置
   * 对于同一位置被多个正则匹配的情况，只保留最后一次匹配的信息
   * @param content 原始内容
   * @returns 匹配范围数组（每个位置只保留最后一个匹配）
   */
  getRegexMatchedRanges(content: string): RegexMatchRange[] {
    // 使用 Map 以 "start-end" 为 key，保证同一位置只保留最后一个匹配
    const rangeMap = new Map<string, RegexMatchRange>();

    const personalizationSettings: FormData[] = store.
      state.indexFieldInfo?.custom_config?.personalization?.settings ?? [];

    // 只处理正则匹配类型的跳转配置
    const regexJumpSettings = personalizationSettings.filter(
      setting => setting.actionType === ActionType.JUMP && setting.matchType === MatchType.REGEX
    );

    for (const setting of regexJumpSettings) {
      try {
        const regex = new RegExp(setting.regex, 'g');
        let match: RegExpExecArray | null;
        while ((match = regex.exec(content)) !== null) {
          const key = `${match.index}-${match.index + match[0].length}`;
          // 后面的匹配会覆盖前面的，保留最后一个
          rangeMap.set(key, {
            start: match.index,
            end: match.index + match[0].length,
            matchedValue: match[0],
            taskName: setting.taskName,
            jumpLink: setting.jumpLink,
          });
          // 防止零宽匹配导致无限循环
          if (match[0].length === 0) {
            regex.lastIndex++;
          }
        }
      } catch {
        // 正则表达式无效，跳过
      }
    }

    return Array.from(rangeMap.values());
  }

  /**
   * 为分词结果附加匹配信息
   * 只有当 token 的范围完全在匹配范围内时才附加配置
   * @param tokens 分词结果
   * @param matchedRanges 匹配范围数组
   * @returns 带匹配信息的分词结果
   */
  attachMatchInfoToTokens(tokens: TokenWithMatch[], matchedRanges: RegexMatchRange[]): TokenWithMatch[] {
    if (matchedRanges.length === 0) {
      return tokens;
    }

    let currentPos = 0;
    return tokens.map(token => {
      const tokenStart = currentPos;
      const tokenEnd = currentPos + token.text.length;
      currentPos = tokenEnd;

      // 查找所有包含此 token 的匹配范围
      const matchedConfigs: RegexMatchConfig[] = [];
      for (const range of matchedRanges) {
        // token 必须完全在匹配范围内
        if (range.start <= tokenStart && tokenEnd <= range.end) {
          matchedConfigs.push({
            taskName: range.taskName,
            jumpLink: range.jumpLink,
            matchedValue: range.matchedValue,
          });
        }
      }

      if (matchedConfigs.length > 0) {
        return {
          ...token,
          matchedConfigs,
        };
      }

      return token;
    });
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

  getSplitList(field: any, content: any): TokenWithMatch[] {
    /** 匹配带属性和不带属性的 mark 标签 */
    const markRegStr = '<mark\\b[^>]*>(.*?)</mark>';

    const value = this.escapeString(`${content}`);

    // 预计算正则匹配范围
    const matchedRanges = this.getRegexMatchedRanges(value);

    let tokens: TokenWithMatch[];

    if (this.isAnalyzed(field)) {
      if (field.tokenize_on_chars) {
        // 这里进来的都是开了分词的情况
        tokens = optimizedSplit(value, field.tokenize_on_chars) as TokenWithMatch[];
      } else {
        tokens = LuceneSegment.split(value, 1000) as TokenWithMatch[];
      }
    } else {
      tokens = [
        {
          text: value,
          isNotParticiple: this.isTextField(field),
          isMark: new RegExp(markRegStr).test(value),
          isCursorText: true,
        },
      ];
    }

    // 附加匹配信息到 token
    return this.attachMatchInfoToTokens(tokens, matchedRanges);
  }

  getChildItem(item: TokenWithMatch) {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    // 统一处理所有 mark 标签（带属性和不带属性）
    if (item.isMark) {
      const wrapper = document.createElement('span');
      wrapper.classList.add('valid-text');

      // 如果有匹配配置，存储到 data 属性
      if (item.matchedConfigs && item.matchedConfigs.length > 0) {
        wrapper.setAttribute('data-matched-configs', JSON.stringify(item.matchedConfigs));
      }

      // 使用 DOMParser 安全解析 HTML
      const parser = new DOMParser();
      const doc = parser.parseFromString(`<div>${item.text}</div>`, 'text/html');
      const container = doc.body.firstChild;

      container.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          // 普通文本节点直接添加
          wrapper.appendChild(document.createTextNode(node.textContent));
        } else if (node.nodeType === Node.ELEMENT_NODE && node.nodeName === 'MARK') {
          // mark 元素节点
          const sourceMarkEl = node as HTMLElement;
          const mrkNode = document.createElement('mark');
          mrkNode.textContent = sourceMarkEl.textContent;

          // 复制原有属性（style, data-tag 等）
          Array.from(sourceMarkEl.attributes).forEach((attr) => {
            mrkNode.setAttribute(attr.name, attr.value);
          });

          mrkNode.classList.add('valid-text');

          // 如果有 data-tag，添加 tippy tooltip
          const dataTag = sourceMarkEl.getAttribute('data-tag');
          if (dataTag) {
            tippy(mrkNode, {
              content: dataTag,
              arrow: true,
            });
          }

          wrapper.appendChild(mrkNode);
        }
      });

      return wrapper;
    }

    if (!(item.isNotParticiple || item.isBlobWord)) {
      const validTextNode = document.createElement('span');
      if (item.isCursorText) {
        validTextNode.classList.add('valid-text');
      }
      validTextNode.textContent = item.text?.length ? item.text : '""';

      // 如果有匹配配置，存储到 data 属性
      if (item.matchedConfigs && item.matchedConfigs.length > 0) {
        validTextNode.setAttribute('data-matched-configs', JSON.stringify(item.matchedConfigs));
      }

      return validTextNode;
    }

    const textNode = document.createElement('span');
    textNode.classList.add('others-text');
    textNode.textContent = item.text?.length ? item.text : '""';

    // 如果有匹配配置，存储到 data 属性
    if (item.matchedConfigs && item.matchedConfigs.length > 0) {
      textNode.setAttribute('data-matched-configs', JSON.stringify(item.matchedConfigs));
    }

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
        if ((e.target as HTMLElement).classList.contains('valid-text')) {
          this.handleSegmentClick(e, (e.target as HTMLElement).textContent);
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
        element?.setAttribute('data-has-word-split', '1');
        element?.setAttribute('data-field-name', fieldName);
        element?.setAttribute('data-field-type', field?.field_type);

        if (element.hasAttribute('data-with-intersection')) {
          (element as HTMLElement).style.setProperty('min-height', `${(element as HTMLElement).offsetHeight}px`);
        }

        element.innerHTML = '';

        const segmentContent = this.creatSegmentNodes();

        const { setListItem, removeScrollEvent } = setScrollLoadCell(
          vlaues,
          element as HTMLElement,
          segmentContent,
          this.getChildItem,
        );
        removeScrollEvent();

        element.append(segmentContent);
        setListItem(1000);

        if (appendText !== undefined) {
          const appendElement = document.createElement('span');
          appendElement.textContent = appendText.text;
          if (appendText.onClick) {
            appendElement.addEventListener('click', appendText.onClick);
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
    if (this.getTargetRoot()) {
      this.localDepth = depth;
      this.editor = new JsonView(this.getTargetRoot(), {
        onNodeExpand: this.handleExpandNode.bind(this),
        depth,
        field: this.config.field,
        segmentRender: (value: string, rootNode: HTMLElement) => {
          const vlaues = this.getSplitList(this.config.field, value);
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
          setListItem(600);
        },
      });

      this.editor.initClickEvent((e) => {
        if ((e.target as HTMLElement).classList.contains('valid-text')) {
          this.handleSegmentClick(e, (e.target as HTMLElement).textContent);
        }
      });
    }
  }

  setNodeExpand([currentDepth]) {
    this.editor.expand(currentDepth);
  }

  setValue(depth) {
    this.setValuePromise = new Promise((resolve, reject) => {
      try {
        this.editor.setValue(this.config.jsonValue);
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
      this.setNodeExpand([depth]);
      this.localDepth = depth;
    });
  }

  destroy() {
    this.editor?.destroy();
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
