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
import JSONBig from 'json-bigint';

export type JsonViewConfig = {
  onNodeExpand: (args: { isExpand: boolean; node: any; targetElement: HTMLElement; rootElement: HTMLElement }) => void;
  jsonValue?: any;
  depth?: number;
  segmentRegStr?: string;
  field?: any;
  segmentRender?: (value: string, rootNode: HTMLElement) => void;
};
export default class JsonView {
  options: JsonViewConfig;
  targetEl: HTMLElement;
  jsonNodeMap: WeakMap<HTMLElement, { target?: any; isExpand?: boolean }>;
  JSONBigInstance: JSONBig;

  rootElClick?: (...args) => void;
  constructor(target: HTMLElement, options: JsonViewConfig) {
    this.options = { depth: 1, isExpand: false, ...options };
    this.targetEl = target;
    this.jsonNodeMap = new WeakMap();
    this.JSONBigInstance = JSONBig({ useNativeBigInt: true });
  }

  private createJsonField(name: number | string) {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-field');

    const fieldText = document.createElement('span');
    fieldText.classList.add('bklog-json-view-text');
    fieldText.innerText = `${name}`;

    fieldEl.append(fieldText);
    return fieldEl;
  }

  private createJsonSymbol() {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-symbol');
    fieldEl.innerText = ':';
    return fieldEl;
  }

  private createObjectChildNode(target, depth) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-child');
    node.classList.add('bklog-json-view-object');
    if (Array.isArray(target)) {
      target.forEach((item, index) => {
        const row = document.createElement('div');
        row.classList.add('bklog-json-view-row');
        row.append(this.createJsonField(index));
        row.append(this.createJsonSymbol());
        row.append(this.createJsonNodeElment(item, depth));

        node.append(row);
      });

      return node;
    }

    for (const key of Object.keys(target ?? {})) {
      const row = document.createElement('div');
      row.classList.add('bklog-json-view-row');
      row.setAttribute('data-field-name', key);
      row.append(this.createJsonField(key));
      row.append(this.createJsonSymbol());
      row.append(this.createJsonNodeElment(target[key], depth));

      node.append(row);
    }

    return node;
  }

  private createObjectNode(target, depth) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-object');
    const isExpand = depth <= this.options.depth;

    this.jsonNodeMap.set(node, {
      isExpand,
      target,
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
        child.push(this.createObjectChildNode(target, depth + 1));
      }

      const copyItem = document.createElement('span');
      copyItem.classList.add(...['bklog-json-view-copy', 'bklog-data-copy', 'bklog-icon']);
      copyItem.setAttribute('title', window.$t('复制'));

      node.append(nodeIconText, copyItem, ...child);
      return [node];
    }

    node.append(this.createObjectChildNode(target, depth));
    return [node];
  }

  private createJsonNodeElment(target: any, depth = 1) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-node');
    node.classList.add(`bklog-data-depth-${depth}`);
    node.setAttribute('data-depth', `${depth}`);
    let formatTarget = target;

    if (typeof target === 'string' && /^(\{|\[)/.test(target)) {
      try {
        formatTarget = this.JSONBigInstance.parse(target);
      } catch (e) {
        console.error(e);
      }
    }

    const nodeType = typeof formatTarget;

    if (nodeType === 'object' && formatTarget !== null) {
      node.append(...this.createObjectNode(formatTarget, depth));
    } else {
      node.classList.add('bklog-json-field-value');
      if (nodeType === 'string' && typeof this.options.segmentRender === 'function') {
        setTimeout(() => {
          this.options.segmentRender(formatTarget, node);
        });
      } else {
        node.innerHTML = `<span class="segment-content bklog-scroll-cell"><span class="valid-text">${xssFilter(formatTarget)}</span></span>`;
      }
    }

    return node;
  }

  private setJsonViewSchema(value: any) {
    this.targetEl.innerHTML = '';
    this.targetEl.append(this.createJsonNodeElment(value, 1));
  }

  private setNodeExpand = (jsonNode: HTMLElement, isExpand: boolean, target: any) => {
    let childNode = jsonNode.querySelector('.bklog-json-view-child');
    if (isExpand && !childNode) {
      const leafNode = jsonNode.closest('.bklog-json-view-node');
      const depth = Number(leafNode.getAttribute('data-depth') ?? 1);
      childNode = this.createObjectChildNode(target, depth + 1);
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
    e.stopPropagation();
    e.preventDefault();
  }

  public setValue(val: any) {
    this.options.jsonValue = val;
    this.setJsonViewSchema(val);
  }

  public initClickEvent(fn?: (...args) => void) {
    this.rootElClick = fn;
    this.targetEl.addEventListener('click', this.handleTargetElementClick.bind(this));
    this.targetEl.addEventListener('mouseup', this.handleMouseUp.bind(this));
  }

  public expand(depth: number) {
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
    if (this.targetEl.querySelector('.bklog-json-view-node')) {
      this.targetEl.innerHTML = '';
      this.targetEl.removeEventListener('click', this.handleTargetElementClick.bind(this));
      this.targetEl.removeEventListener('mouseup', this.handleMouseUp.bind(this));
    }
  }
}
