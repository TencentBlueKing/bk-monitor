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
  /** 根值是否由 JSON String 解析得到；此时叶子筛选必须作用于外层字段 */
  parsedFromJsonString?: boolean;
  /** 将真实字段路径转换为展示别名；返回原路径时沿用 JSON 原始 KEY。 */
  resolveFieldDisplayName?: (_fieldPath: string) => string;
  /**
   * 将 JSON 深路径收敛为 Fields 列表中真实存在的最长前缀。
   * 例：__ext_json.name.first_name → __ext_json.name（若 first_name 未声明）
   */
  resolveMappedFieldPath?: (_fieldPath: string) => string;
};
export default class JsonView {
  options: JsonViewConfig;
  targetEl: HTMLElement;
  jsonNodeMap: WeakMap<HTMLElement, {
    target?: any;
    isExpand?: boolean;
    parentPath?: string;
    jsonStringFieldPath?: string;
  }>;
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

  private createJsonField(name: number | string, fieldPath = '') {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-field');

    const fieldText = document.createElement('span');
    fieldText.classList.add('bklog-json-view-text');
    // JSON String 的命中标记可能出现在 KEY 中。解析成对象后 key 会保留标记文本，
    // 必须在 DOM 渲染前转换成纯文本和高亮范围，避免标签泄漏。
    const { plainText, markRanges } = parseResultMarkedText(name);
    const displayName = fieldPath ? this.options.resolveFieldDisplayName?.(fieldPath) : undefined;
    const displayText = displayName && displayName !== fieldPath ? displayName : plainText;
    fieldText.appendChild(highlightPlainTextIntoFragment({
      text: displayText,
      resultRanges: displayText === plainText ? markRanges : [],
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

  /**
   * 计算叶子节点对应的真实检索字段：
   * - JSON String 仅是前端展示解析，ES 中仍只有外层字段，不能构造 KEY.SubKey；
   * - 原始 Object 才使用完整的 KEY.SubKey 路径。
   */
  private buildSearchFieldPath(parentPath: string, key: number | string, jsonStringFieldPath = '') {
    // 检索高亮标签只属于展示协议，不能进入字段路径和后续筛选条件。
    const { plainText: keyText } = parseResultMarkedText(key);
    if (jsonStringFieldPath) return jsonStringFieldPath;
    if (!parentPath) return keyText;
    return parentPath.concat('.', keyText);
  }

  /** DOM 绑定前按 Fields 列表收敛路径，避免挂上无效深路径 */
  private clampMappedFieldPath(fieldPath: string) {
    if (!fieldPath) return fieldPath;
    return this.options.resolveMappedFieldPath?.(fieldPath) ?? fieldPath;
  }

  private createObjectRow(
    key: number | string,
    value: any,
    depth: number,
    parentPath: string,
    jsonStringFieldPath = '',
  ) {
    const row = document.createElement('div');
    const rawSearchFieldPath = this.buildSearchFieldPath(parentPath, key, jsonStringFieldPath);
    // JSON String：检索字段固定外层；Object：按 Fields 列表收敛（未映射子路径回溯到最长前缀）
    const searchFieldPath = this.clampMappedFieldPath(rawSearchFieldPath);
    row.classList.add('bklog-json-view-row');
    // 使用去标记后的字段名，避免后续点击和筛选携带 HTML 协议标签。
    row.setAttribute('data-field-name', parseResultMarkedText(key).plainText);
    // data-search-field-name 绑定真实可检索字段（已回归 Fields 列表）
    row.setAttribute('data-search-field-name', searchFieldPath);
    // Object 深路径同样收敛，禁止挂上 Fields 未声明的 __ext_json.name.first_name。
    const rawSegmentFieldPath = jsonStringFieldPath
      ? [parentPath, parseResultMarkedText(key).plainText].filter(Boolean).join('.')
      : rawSearchFieldPath;
    const segmentFieldPath = this.clampMappedFieldPath(rawSegmentFieldPath);
    row.setAttribute('data-segment-field-name', segmentFieldPath);
    if (jsonStringFieldPath) {
      row.setAttribute('data-json-string-parsed', 'true');
    }
    // JSON String 解析出的子 KEY 只是展示结构，并不是真实字段路径。
    // 它们的筛选仍绑定外层真实字段，但不能被外层字段别名替换。
    const displayFieldPath = jsonStringFieldPath ? '' : searchFieldPath;
    row.append(this.createJsonField(key, displayFieldPath));
    row.append(this.createJsonSymbol());
    // 子节点继续用未收敛的展示路径向下展开，保证 JSON 树结构完整；
    // 每个子行会再次 clamp，最终 DOM 属性只保留 Fields 映射字段。
    const childParentPath = jsonStringFieldPath
      ? rawSegmentFieldPath
      : (rawSearchFieldPath || parentPath);
    row.append(this.createJsonNodeElment(value, depth, childParentPath, jsonStringFieldPath));

    return row;
  }

  private appendObjectRowsInChunks(
    container: HTMLElement,
    entries: Array<[number | string, any]>,
    depth: number,
    taskId: number,
    parentPath: string,
    jsonStringFieldPath = '',
  ) {
    let startIndex = 0;

    const appendChunk = (size: number) => {
      if (taskId !== this.renderTaskId) return;

      const fragment = document.createDocumentFragment();
      const endIndex = Math.min(startIndex + size, entries.length);
      for (let index = startIndex; index < endIndex; index += 1) {
        const [key, value] = entries[index];
        fragment.append(this.createObjectRow(key, value, depth, parentPath, jsonStringFieldPath));
      }

      startIndex = endIndex;
      container.append(fragment);

      if (startIndex < entries.length) {
        this.scheduleRender(() => appendChunk(this.getBatchSize()));
      }
    };

    appendChunk(this.getBatchSize(true));
  }

  private createObjectChildNode(target, depth, parentPath: string, jsonStringFieldPath = '') {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-child');
    node.classList.add('bklog-json-view-object');

    const entries: Array<[number | string, any]> = Array.isArray(target)
      ? target.map((item, index) => [index, item])
      : Object.keys(target ?? {}).map(key => [key, target[key]]);

    this.appendObjectRowsInChunks(node, entries, depth, this.renderTaskId, parentPath, jsonStringFieldPath);

    return node;
  }

  private createObjectNode(target, depth, parentPath: string, jsonStringFieldPath = '') {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-object');
    const isExpand = depth <= this.activeDepth;

    this.jsonNodeMap.set(node, {
      isExpand,
      target,
      parentPath,
      jsonStringFieldPath,
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
        child.push(this.createObjectChildNode(target, depth + 1, parentPath, jsonStringFieldPath));
      }

      const copyItem = document.createElement('span');
      copyItem.classList.add(...['bklog-json-view-copy', 'bklog-data-copy', 'bklog-icon']);
      copyItem.setAttribute('title', window.$t('复制'));

      node.append(nodeIconText, copyItem, ...child);
      return [node];
    }

    node.append(this.createObjectChildNode(target, depth, parentPath, jsonStringFieldPath));
    return [node];
  }

  private bindSearchFieldPath(node: HTMLElement, fieldPath: string) {
    if (!fieldPath) return;
    node.setAttribute('data-search-field-name', this.clampMappedFieldPath(fieldPath));
  }

  private createJsonNodeElment(target: any, depth = 1, parentPath = '', inheritedJsonStringFieldPath = '') {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-node');
    node.classList.add(`bklog-data-depth-${depth}`);
    node.setAttribute('data-depth', `${depth}`);
    let formatTarget = target;
    let jsonStringFieldPath = inheritedJsonStringFieldPath;
    this.bindSearchFieldPath(node, jsonStringFieldPath || parentPath);
    // Parsing depth controls expansion only. Every created node must still recognize
    // Object/Array values (including JSON strings), so increasing depth can expand
    // Nested fields that were initially collapsed. Children remain lazily rendered.
    if (typeof target === 'string' && /^\s*(\{|\[)/.test(target)) {
      try {
        formatTarget = this.JSONBigInstance.parse(target);
        jsonStringFieldPath = parentPath || this.getRootFieldPath();
      } catch (e) {
        console.error(e);
      }
    }

    const nodeType = typeof formatTarget;

    if (nodeType === 'object' && formatTarget !== null) {
      node.append(...this.createObjectNode(formatTarget, depth, parentPath, jsonStringFieldPath));
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
    const rootPath = this.getRootFieldPath();
    const jsonStringFieldPath = this.options.parsedFromJsonString ? rootPath : '';
    this.targetEl.append(this.createJsonNodeElment(value, 1, rootPath, jsonStringFieldPath));
  }

  private setNodeExpand = (jsonNode: HTMLElement, isExpand: boolean, target: any) => {
    let childNode = jsonNode.querySelector('.bklog-json-view-child');
    if (isExpand && !childNode) {
      const leafNode = jsonNode.closest('.bklog-json-view-node');
      const depth = Number(leafNode.getAttribute('data-depth') ?? 1);
      const nodeMeta = this.jsonNodeMap.get(jsonNode);
      const parentPath = nodeMeta?.parentPath
        ?? leafNode?.getAttribute('data-search-field-name')
        ?? this.getRootFieldPath();
      childNode = this.createObjectChildNode(target, depth + 1, parentPath, nodeMeta?.jsonStringFieldPath);
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
    const targetDepth = Math.max(0, Number(depth) || 0);
    this.activeDepth = targetDepth;

    const updateElementExpandState = (element: Element, isNextExpand: boolean) => {
      const objectElement = element.children[0] as HTMLElement;
      if (!objectElement?.classList.contains('bklog-json-view-object')) return;

      const nodeMeta = this.jsonNodeMap.get(objectElement);
      if (!nodeMeta || nodeMeta.isExpand === isNextExpand) return;

      this.setNodeExpand(objectElement, isNextExpand, nodeMeta.target);
      nodeMeta.isExpand = isNextExpand;
    };

    // querySelectorAll returns a static collection. Query depth by depth so that
    // Nested children created by the previous expansion are handled in this pass.
    for (let currentDepth = 1; currentDepth <= targetDepth; currentDepth += 1) {
      const selector = `[data-depth="${currentDepth}"]`;
      for (const element of this.targetEl.querySelectorAll(selector)) {
        updateElementExpandState(element, true);
      }
    }

    // Collapse already rendered nodes that exceed the new depth.
    for (const element of this.targetEl.querySelectorAll('[data-depth]')) {
      if (Number(element.getAttribute('data-depth')) > targetDepth) {
        updateElementExpandState(element, false);
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
