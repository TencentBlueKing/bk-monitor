/* eslint-disable @typescript-eslint/member-ordering */
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
import { copyMessage, xssFilter } from '@/common/util';
import RetrieveHelper from '@/views/retrieve-helper';
import { highlightPlainTextIntoFragment, parseResultMarkedText } from '@/views/retrieve-core/page-highlight';
import JSONBig from 'json-bigint';

export type JsonViewConfig = {
  onNodeExpand: (_args: { isExpand: boolean; node: any; targetElement: HTMLElement; rootElement: HTMLElement }) => void;
  jsonValue?: any;
  depth?: number;
  segmentRegStr?: string;
  field?: any;
  segmentRender?: (_value: string, _rootNode: HTMLElement) => void;
  batchSize?: number;
  initialBatchSize?: number;
  /**
   * 超过该深度后，不再把嵌套 JSON 字符串继续 parse 成树；
   * 默认与 depth 一致（JSON 解析深度配置）
   */
  maxParseDepth?: number;
};
export default class JsonView {
  options: JsonViewConfig;
  targetEl: HTMLElement;
  jsonNodeMap: WeakMap<HTMLElement, { target?: any; isExpand?: boolean; parentPath?: string }>;
  JSONBigInstance: JSONBig;
  renderTaskId: number;
  timeoutHandles: Set<number>;
  activeDepth: number;

  rootElClick?: (..._args) => void;
  targetElClickHandler?: EventListener;
  targetElMouseUpHandler?: EventListener;
  constructor(target: HTMLElement, options: JsonViewConfig) {
    this.options = { depth: 1, isExpand: false, ...options };
    this.targetEl = target;
    this.jsonNodeMap = new WeakMap();
    this.JSONBigInstance = JSONBig({ useNativeBigInt: true });
    this.renderTaskId = 0;
    this.timeoutHandles = new Set();
    this.activeDepth = Number(this.options.depth ?? 1);
  }

  private createJsonField(name: number | string) {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-field');

    const fieldText = document.createElement('span');
    fieldText.classList.add('bklog-json-view-text');
    // JSON String 的命中标记可能出现在 KEY 中。解析成对象后 key 会保留标记文本，
    // 必须在 DOM 渲染前转换成纯文本和高亮范围，避免标签泄漏。
    const { plainText, markRanges } = parseResultMarkedText(name);
    fieldText.appendChild(highlightPlainTextIntoFragment({
      text: plainText,
      resultRanges: markRanges,
    }));

    fieldEl.append(fieldText);
    return fieldEl;
  }

  private createJsonSymbol() {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-symbol');
    fieldEl.innerText = ':';
    return fieldEl;
  }

  private getBatchSize(isInitial = false) {
    const fallback = isInitial ? 60 : 120;
    const optionKey = isInitial ? 'initialBatchSize' : 'batchSize';
    const value = Number(this.options[optionKey]);

    return Number.isFinite(value) && value > 0 ? value : fallback;
  }

  private scheduleRender(callback: () => void) {
    const handle = window.setTimeout(() => {
      this.timeoutHandles.delete(handle);
      callback();
    }, 0);

    this.timeoutHandles.add(handle);
    return handle;
  }

  private clearScheduledRender() {
    for (const handle of this.timeoutHandles) {
      window.clearTimeout(handle);
    }

    this.timeoutHandles.clear();
  }

  /** 根字段名：用于 Object 多层级检索字段绑定 */
  private getRootFieldPath() {
    const field = this.options.field;
    if (!field) return '';
    return typeof field === 'string' ? field : (field.field_name ?? '');
  }

  /** 拼接 Object 多层级真实检索字段路径 */
  private buildSearchFieldPath(parentPath: string, key: number | string) {
    // 检索高亮标签只属于展示协议，不能进入字段路径和后续筛选条件。
    const { plainText: keyText } = parseResultMarkedText(key);
    if (!parentPath) return keyText;
    return parentPath.concat('.', keyText);
  }

  private createObjectRow(key: number | string, value: any, depth: number, parentPath: string) {
    const row = document.createElement('div');
    const searchFieldPath = this.buildSearchFieldPath(parentPath, key);
    row.classList.add('bklog-json-view-row');
    // 使用去标记后的字段名，避免后续点击和筛选携带 HTML 协议标签。
    row.setAttribute('data-field-name', parseResultMarkedText(key).plainText);
    // data-search-field-name 绑定真实检索字段（含根字段前缀）
    row.setAttribute('data-search-field-name', searchFieldPath);
    row.append(this.createJsonField(key));
    row.append(this.createJsonSymbol());
    row.append(this.createJsonNodeElment(value, depth, searchFieldPath));

    return row;
  }

  private appendObjectRowsInChunks(
    container: HTMLElement,
    entries: Array<[number | string, any]>,
    depth: number,
    taskId: number,
    parentPath: string,
  ) {
    let startIndex = 0;

    const appendChunk = (size: number) => {
      if (taskId !== this.renderTaskId) return;

      const fragment = document.createDocumentFragment();
      const endIndex = Math.min(startIndex + size, entries.length);
      for (let index = startIndex; index < endIndex; index += 1) {
        const [key, value] = entries[index];
        fragment.append(this.createObjectRow(key, value, depth, parentPath));
      }

      startIndex = endIndex;
      container.append(fragment);

      if (startIndex < entries.length) {
        this.scheduleRender(() => appendChunk(this.getBatchSize()));
      }
    };

    appendChunk(this.getBatchSize(true));
  }

  private createObjectChildNode(target, depth, parentPath: string) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-child');
    node.classList.add('bklog-json-view-object');

    const entries: Array<[number | string, any]> = Array.isArray(target)
      ? target.map((item, index) => [index, item])
      : Object.keys(target ?? {}).map(key => [key, target[key]]);

    this.appendObjectRowsInChunks(node, entries, depth, this.renderTaskId, parentPath);

    return node;
  }

  private createObjectNode(target, depth, parentPath: string) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-object');
    const isExpand = depth <= this.activeDepth;

    this.jsonNodeMap.set(node, {
      isExpand,
      target,
      parentPath,
    });

    if (typeof target === 'object' && target !== null) {
      const iconExpand = document.createElement('span');
      iconExpand.classList.add('bklog-json-view-icon-expand');
      iconExpand.classList.add(isExpand ? 'is-expand' : 'is-collapse');
      iconExpand.innerText = '▶';
      node.append(iconExpand);

      const nodeIconText = document.createElement('span');
      nodeIconText.classList.add('bklog-json-view-icon-text');
      const text = Array.isArray(target) ? '[...]' : '{...}';
      nodeIconText.innerText = text;

      const child: HTMLElement[] = [];

      if (isExpand) {
        child.push(this.createObjectChildNode(target, depth + 1, parentPath));
      }

      const copyItem = document.createElement('span');
      copyItem.classList.add(...['bklog-json-view-copy', 'bklog-data-copy', 'bklog-icon']);
      copyItem.setAttribute('title', window.$t('复制'));

      node.append(nodeIconText, copyItem, ...child);
      return [node];
    }

    node.append(this.createObjectChildNode(target, depth, parentPath));
    return [node];
  }

  private bindSearchFieldPath(node: HTMLElement, fieldPath: string) {
    if (!fieldPath) return;
    node.setAttribute('data-search-field-name', fieldPath);
  }

  private createJsonNodeElment(target: any, depth = 1, parentPath = '') {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-node');
    node.classList.add(`bklog-data-depth-${depth}`);
    node.setAttribute('data-depth', `${depth}`);
    this.bindSearchFieldPath(node, parentPath);
    let formatTarget = target;
    const maxParseDepth = Number(this.options.maxParseDepth ?? this.options.depth ?? 1);

    // 仅在配置的 JSON 解析深度内继续 parse 嵌套 JSON 字符串；
    // 超出深度的可解析字符串按叶子字符串处理（由上层决定是否 1000/更多）
    if (typeof target === 'string' && depth <= maxParseDepth && /^(\{|\[)/.test(target)) {
      try {
        formatTarget = this.JSONBigInstance.parse(target);
      } catch (e) {
        console.error(e);
      }
    }

    const nodeType = typeof formatTarget;

    if (nodeType === 'object' && formatTarget !== null) {
      // 超出最大解析深度的 object/array：转为字符串叶子，走 1000/更多，而不再继续展开树
      if (depth > maxParseDepth) {
        let overflowText = '';
        try {
          overflowText = JSON.stringify(formatTarget);
        } catch {
          overflowText = String(formatTarget);
        }
        node.classList.add('bklog-json-field-value');
        if (overflowText && typeof this.options.segmentRender === 'function') {
          const taskId = this.renderTaskId;
          this.scheduleRender(() => {
            if (taskId === this.renderTaskId && node.isConnected) {
              this.options.segmentRender(overflowText, node);
            }
          });
        } else {
          node.innerHTML = `<span class="segment-content bklog-scroll-cell"><span class="valid-text">${xssFilter(overflowText || '--')}</span></span>`;
        }
        return node;
      }

      node.append(...this.createObjectNode(formatTarget, depth, parentPath));
    } else {
      node.classList.add('bklog-json-field-value');
      // string / number / boolean / bigint 叶子统一走 segmentRender，
      // 以便消费 pageHighlightState（含大小写/精确/正则匹配模式）
      const isPrimitiveLeaf = nodeType === 'string'
        || nodeType === 'number'
        || nodeType === 'boolean'
        || nodeType === 'bigint';
      const leafText = formatTarget !== null && formatTarget !== undefined && formatTarget !== ''
        ? String(formatTarget)
        : '';
      if (isPrimitiveLeaf && leafText !== '' && typeof this.options.segmentRender === 'function') {
        const taskId = this.renderTaskId;
        this.scheduleRender(() => {
          if (taskId === this.renderTaskId && node.isConnected) {
            this.options.segmentRender(leafText, node);
          }
        });
      } else {
        const displayValue = leafText || '--';
        node.innerHTML = `<span class="segment-content bklog-scroll-cell"><span class="valid-text">${xssFilter(displayValue)}</span></span>`;
      }
    }

    return node;
  }

  private setJsonViewSchema(value: any) {
    this.activeDepth = Number(this.options.depth ?? 1);
    this.renderTaskId += 1;
    this.clearScheduledRender();
    this.targetEl.innerHTML = '';
    this.targetEl.append(this.createJsonNodeElment(value, 1, this.getRootFieldPath()));
  }

  private setNodeExpand = (jsonNode: HTMLElement, isExpand: boolean, target: any) => {
    let childNode = jsonNode.querySelector('.bklog-json-view-child');
    if (isExpand && !childNode) {
      const leafNode = jsonNode.closest('.bklog-json-view-node');
      const depth = Number(leafNode.getAttribute('data-depth') ?? 1);
      const parentPath = this.jsonNodeMap.get(jsonNode)?.parentPath
        ?? leafNode?.getAttribute('data-search-field-name')
        ?? this.getRootFieldPath();
      childNode = this.createObjectChildNode(target, depth + 1, parentPath);
      jsonNode.append(childNode);
    }

    const collapseClassName = isExpand ? 'is-collapse' : 'is-expand';
    const expandClassName = isExpand ? 'is-expand' : 'is-collapse';

    childNode.classList.remove(collapseClassName);
    childNode.classList.add(expandClassName);

    const targetNode = jsonNode.querySelector('.bklog-json-view-icon-expand');
    targetNode.classList.remove(collapseClassName);
    targetNode.classList.add(expandClassName);
  };

  private handleTargetElementClick(e) {
    const targetNode = e.target as HTMLElement;
    if (
      targetNode.classList.contains('bklog-json-view-icon-expand')
      || targetNode.classList.contains('bklog-json-view-icon-text')
    ) {
      const storeNode = targetNode.closest('.bklog-json-view-object') as HTMLElement;
      if (this.jsonNodeMap.get(storeNode)) {
        RetrieveHelper.jsonFormatter.setIsExpandNodeClick(true);
        const { isExpand, target } = this.jsonNodeMap.get(storeNode) ?? {};
        this.jsonNodeMap.get(storeNode).isExpand = !isExpand;
        this.setNodeExpand(storeNode, !isExpand, target);
        this.options.onNodeExpand?.({
          isExpand: !isExpand,
          node: target,
          targetElement: storeNode,
          rootElement: this.targetEl,
        });
      }
    }

    if (targetNode.classList.contains('bklog-json-view-copy')) {
      const storeNode = targetNode.closest('.bklog-json-view-object') as HTMLElement;

      if (this.jsonNodeMap.has(storeNode)) {
        const { target } = this.jsonNodeMap.get(storeNode) ?? {};
        copyMessage(JSON.stringify(target) || '', window.$t?.('复制成功'));
      }
    }

    this.rootElClick?.(e);
  }

  private handleMouseUp(e: MouseEvent) {
    // 与行级划词判定对齐：仅「本次拖拽划选」或「点在当前选区上」时放行冒泡；
    // 残留选区下的普通点击仍拦截，避免误触发行展开/收起。
    if (
      RetrieveHelper.isMouseSelectionUpEvent(e)
      || RetrieveHelper.isClickOnSelection(e, 2)
    ) {
      return;
    }
    e.stopPropagation();
  }

  public setValue(val: any) {
    this.options.jsonValue = val;
    this.setJsonViewSchema(val);
  }

  public initClickEvent(fn?: (..._args) => void) {
    if (this.targetElClickHandler) {
      this.targetEl.removeEventListener('click', this.targetElClickHandler);
    }
    if (this.targetElMouseUpHandler) {
      this.targetEl.removeEventListener('mouseup', this.targetElMouseUpHandler);
    }

    this.rootElClick = fn;
    this.targetElClickHandler = this.handleTargetElementClick.bind(this) as EventListener;
    this.targetElMouseUpHandler = this.handleMouseUp.bind(this) as EventListener;
    this.targetEl.addEventListener('click', this.targetElClickHandler);
    this.targetEl.addEventListener('mouseup', this.targetElMouseUpHandler);
  }

  public expand(depth: number) {
    this.activeDepth = depth;
    for (const element of this.targetEl.querySelectorAll('[data-depth]')) {
      const elementDepth = element.getAttribute('data-depth');
      const objectElement = element.children[0] as HTMLElement;

      if (objectElement?.classList.contains('bklog-json-view-object')) {
        const { target, isExpand } = this.jsonNodeMap.get(objectElement);
        const isNextExpand = depth >= Number(elementDepth);

        if (isNextExpand !== isExpand) {
          this.setNodeExpand(objectElement, isNextExpand, target);
          this.jsonNodeMap.get(objectElement).isExpand = isNextExpand;
        }
      }
    }
  }

  public destroy() {
    this.renderTaskId += 1;
    this.clearScheduledRender();
    if (this.targetEl.querySelector('.bklog-json-view-node')) {
      this.targetEl.innerHTML = '';
      if (this.targetElClickHandler) {
        this.targetEl.removeEventListener('click', this.targetElClickHandler);
        this.targetElClickHandler = undefined;
      }
      if (this.targetElMouseUpHandler) {
        this.targetEl.removeEventListener('mouseup', this.targetElMouseUpHandler);
        this.targetElMouseUpHandler = undefined;
      }
    }
  }
}
