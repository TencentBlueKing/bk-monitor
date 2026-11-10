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
import {
  applyPrimitiveMarkText,
  isMarkedJsonLike,
  joinMarkedJsonPath,
  MARKED_JSON_ROOT_PATH,
  mergePrimitiveMarks,
  parseMarkedJson,
  type PrimitiveMarkMap,
} from '@/views/retrieve-core/marked-json';
import JSONBig from 'json-bigint';

/** 单个节点一次性铺开的子项上限，超出部分点击「展开更多」按需渲染 */
const CHILD_RENDER_LIMIT = 500;
/** 单批渲染任务的时间预算，避免深层 JSON 长任务阻塞滚动 */
const RENDER_TIME_BUDGET = 8;

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

/** JSON 树递归上下文：层级 + 字段路径 + 结构路径 */
type JsonNodeContext = {
  depth: number;
  /** 展示 / 检索字段路径 */
  parentPath: string;
  /** 非空表示该子树由 JSON String 解析而来，检索仍绑定这个外层真实字段 */
  jsonStringFieldPath: string;
  /** 结构路径，与 marked-json 扫描器一致，用于标量命中侧通道 */
  nodePath: string;
};

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
  /** 数字 / 布尔等字面量上的检索命中：按结构路径重新包裹 <mark> */
  primitiveMarks?: PrimitiveMarkMap;
};
export default class JsonView {
  options: JsonViewConfig;
  targetEl: HTMLElement;
  jsonNodeMap: WeakMap<
    HTMLElement,
    {
      target?: any;
      isExpand?: boolean;
      context?: JsonNodeContext;
    }
  >;
  JSONBigInstance: JSONBig;
  renderTaskId: number;
  renderQueue: Array<() => void>;
  renderQueueHandle: number;
  activeDepth: number;
  /** 含嵌套 JSON String 解析结果的标量命中映射 */
  primitiveMarks: PrimitiveMarkMap;

  rootElClick?: (..._args) => void;
  targetElClickHandler?: EventListener;
  targetElMouseUpHandler?: EventListener;
  constructor(target: HTMLElement, options: JsonViewConfig) {
    this.options = { depth: 1, isExpand: false, ...options };
    this.targetEl = target;
    this.jsonNodeMap = new WeakMap();
    this.JSONBigInstance = JSONBig({ useNativeBigInt: true });
    this.renderTaskId = 0;
    this.renderQueue = [];
    this.renderQueueHandle = 0;
    this.activeDepth = Number(this.options.depth ?? 1);
    this.primitiveMarks = new Map();
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
    fieldText.appendChild(
      highlightPlainTextIntoFragment({
        text: displayText,
        resultRanges: displayText === plainText ? markRanges : [],
      }),
    );

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

  /**
   * 渲染任务统一进实例级队列并按时间片冲刷。
   * 深层 JSON 的叶子数量可达数千，逐个 setTimeout 会产生同等数量的宏任务，
   * 每个任务都要重新进入样式计算，滚动时表现为持续掉帧。
   */
  private scheduleRender(callback: () => void) {
    this.renderQueue.push(callback);
    this.ensureRenderQueueFlush();
  }

  private ensureRenderQueueFlush() {
    if (this.renderQueueHandle) {
      return;
    }

    this.renderQueueHandle = window.setTimeout(() => {
      this.renderQueueHandle = 0;
      this.flushRenderQueue();
    }, 0);
  }

  private flushRenderQueue() {
    const taskId = this.renderTaskId;
    const startTime = now();

    while (this.renderQueue.length) {
      if (taskId !== this.renderTaskId) {
        this.renderQueue.length = 0;
        return;
      }

      this.renderQueue.shift()?.();

      if (now() - startTime >= RENDER_TIME_BUDGET) {
        break;
      }
    }

    if (this.renderQueue.length) {
      this.ensureRenderQueueFlush();
    }
  }

  private clearScheduledRender() {
    this.renderQueue.length = 0;
    if (this.renderQueueHandle) {
      window.clearTimeout(this.renderQueueHandle);
      this.renderQueueHandle = 0;
    }
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

  private createObjectRow(key: number | string, value: any, context: JsonNodeContext) {
    const { parentPath, jsonStringFieldPath } = context;
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
    const childParentPath = jsonStringFieldPath ? rawSegmentFieldPath : rawSearchFieldPath || parentPath;
    row.append(
      this.createJsonNodeElment(value, {
        ...context,
        parentPath: childParentPath,
        nodePath: joinMarkedJsonPath(context.nodePath, parseResultMarkedText(key).plainText),
      }),
    );

    return row;
  }

  /** 超出上限的子项不再自动铺开，改为「展开更多」按需渲染，避免一次生成上万 DOM 节点 */
  private createMoreRowsButton(remaining: number, onExpand: () => void) {
    const button = document.createElement('span');
    button.classList.add('bklog-json-view-more-rows');
    button.textContent = `${window.$t?.('展开更多') ?? '展开更多'}（${remaining}）`;
    button.addEventListener('click', e => {
      e.stopPropagation();
      e.preventDefault();
      RetrieveHelper.jsonFormatter.setIsExpandNodeClick(true);
      button.remove();
      onExpand();
    });

    return button;
  }

  private appendObjectRowsInChunks(
    container: HTMLElement,
    entries: Array<[number | string, any]>,
    context: JsonNodeContext,
    taskId: number,
  ) {
    let startIndex = 0;
    let renderLimit = Math.min(entries.length, CHILD_RENDER_LIMIT);

    const appendChunk = (size: number) => {
      if (taskId !== this.renderTaskId) return;

      const fragment = document.createDocumentFragment();
      const endIndex = Math.min(startIndex + size, renderLimit);
      for (let index = startIndex; index < endIndex; index += 1) {
        const [key, value] = entries[index];
        fragment.append(this.createObjectRow(key, value, context));
      }

      startIndex = endIndex;
      container.append(fragment);

      if (startIndex < renderLimit) {
        this.scheduleRender(() => appendChunk(this.getBatchSize()));
        return;
      }

      if (startIndex < entries.length) {
        container.append(
          this.createMoreRowsButton(entries.length - startIndex, () => {
            renderLimit = Math.min(entries.length, startIndex + CHILD_RENDER_LIMIT);
            appendChunk(this.getBatchSize(true));
          }),
        );
      }
    };

    appendChunk(this.getBatchSize(true));
  }

  private createObjectChildNode(target, context: JsonNodeContext) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-child');
    node.classList.add('bklog-json-view-object');

    const entries: Array<[number | string, any]> = Array.isArray(target)
      ? target.map((item, index) => [index, item])
      : Object.keys(target ?? {}).map(key => [key, target[key]]);

    this.appendObjectRowsInChunks(node, entries, context, this.renderTaskId);

    return node;
  }

  private createObjectNode(target, context: JsonNodeContext) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-object');
    const isExpand = context.depth <= this.activeDepth;

    this.jsonNodeMap.set(node, {
      isExpand,
      target,
      context,
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
        child.push(this.createObjectChildNode(target, { ...context, depth: context.depth + 1 }));
      }

      const copyItem = document.createElement('span');
      copyItem.classList.add(...['bklog-json-view-copy', 'bklog-data-copy', 'bklog-icon']);
      copyItem.setAttribute('title', window.$t('复制'));

      node.append(nodeIconText, copyItem, ...child);
      return [node];
    }

    node.append(this.createObjectChildNode(target, context));
    return [node];
  }

  private bindSearchFieldPath(node: HTMLElement, fieldPath: string) {
    if (!fieldPath) return;
    node.setAttribute('data-search-field-name', this.clampMappedFieldPath(fieldPath));
  }

  private createJsonNodeElment(target: any, context: JsonNodeContext) {
    const { depth, parentPath, nodePath } = context;
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-node');
    node.classList.add(`bklog-data-depth-${depth}`);
    node.setAttribute('data-depth', `${depth}`);
    let formatTarget = target;
    let jsonStringFieldPath = context.jsonStringFieldPath;
    this.bindSearchFieldPath(node, jsonStringFieldPath || parentPath);
    // Parsing depth controls expansion only. Every created node must still recognize
    // Object/Array values (including JSON strings), so increasing depth can expand
    // Nested fields that were initially collapsed. Children remain lazily rendered.
    if (isMarkedJsonLike(target)) {
      // 嵌套 JSON String 同样可能带检索高亮：保留 <mark>，跨结构命中由 parseMarkedJson 收敛
      const parsed = parseMarkedJson(target, text => this.JSONBigInstance.parse(text));
      if (parsed.isJson) {
        formatTarget = parsed.value;
        jsonStringFieldPath = parentPath || this.getRootFieldPath();
        mergePrimitiveMarks(this.primitiveMarks, nodePath, parsed.primitiveMarks);
      }
    }

    const nodeType = typeof formatTarget;

    if (nodeType === 'object' && formatTarget !== null) {
      node.append(...this.createObjectNode(formatTarget, { ...context, jsonStringFieldPath }));
    } else {
      node.classList.add('bklog-json-field-value');
      // string / number / boolean / bigint 叶子统一走 segmentRender，
      // 以便消费 pageHighlightState（含大小写/精确/正则匹配模式）
      const isPrimitiveLeaf =
        nodeType === 'string' || nodeType === 'number' || nodeType === 'boolean' || nodeType === 'bigint';
      const plainLeafText =
        formatTarget !== null && formatTarget !== undefined && formatTarget !== '' ? String(formatTarget) : '';
      // 数字 / 布尔字面量无法内嵌 <mark>，命中信息在解析阶段存入侧通道，渲染前按结构路径回填
      const leafText =
        nodeType === 'string'
          ? plainLeafText
          : applyPrimitiveMarkText(plainLeafText, this.primitiveMarks.get(nodePath));
      if (isPrimitiveLeaf && plainLeafText !== '' && typeof this.options.segmentRender === 'function') {
        const taskId = this.renderTaskId;
        this.scheduleRender(() => {
          if (taskId === this.renderTaskId && node.isConnected) {
            this.options.segmentRender(leafText, node);
          }
        });
      } else {
        const displayValue = plainLeafText || '--';
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
    this.primitiveMarks = new Map(this.options.primitiveMarks ?? []);
    this.targetEl.append(
      this.createJsonNodeElment(value, {
        depth: 1,
        parentPath: rootPath,
        jsonStringFieldPath: this.options.parsedFromJsonString ? rootPath : '',
        nodePath: MARKED_JSON_ROOT_PATH,
      }),
    );
  }

  private setNodeExpand = (jsonNode: HTMLElement, isExpand: boolean, target: any) => {
    let childNode = jsonNode.querySelector('.bklog-json-view-child');
    if (isExpand && !childNode) {
      const leafNode = jsonNode.closest('.bklog-json-view-node');
      const depth = Number(leafNode.getAttribute('data-depth') ?? 1);
      const nodeMeta = this.jsonNodeMap.get(jsonNode);
      const parentPath =
        nodeMeta?.context?.parentPath ?? leafNode?.getAttribute('data-search-field-name') ?? this.getRootFieldPath();
      childNode = this.createObjectChildNode(target, {
        depth: depth + 1,
        parentPath,
        jsonStringFieldPath: nodeMeta?.context?.jsonStringFieldPath ?? '',
        nodePath: nodeMeta?.context?.nodePath ?? MARKED_JSON_ROOT_PATH,
      });
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
      targetNode.classList.contains('bklog-json-view-icon-expand') ||
      targetNode.classList.contains('bklog-json-view-icon-text')
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
    if (RetrieveHelper.isMouseSelectionUpEvent(e) || RetrieveHelper.isClickOnSelection(e, 2)) {
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
