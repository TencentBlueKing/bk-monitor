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

export type JsonViewConfig = {
  onNodeExpand: (args: { isExpanded: boolean; node: any }) => void;
  jsonValue: any;
  depth: number;
};
export default class JsonView {
  options: JsonViewConfig;
  targetEl: HTMLElement;
  jsonNodeMap: WeakMap<HTMLElement, { target: any; isExpand: boolean }>;
  constructor(target: HTMLElement, options: JsonViewConfig) {
    this.options = Object.assign({}, { depth: 1 }, options);
    this.targetEl = target;
    this.jsonNodeMap = new WeakMap();
  }

  setValue(val: any) {
    this.options.jsonValue = val;
  }

  formatJsonValueToArray() {
    const targetValue = [];
    if (Array.isArray(this.options.jsonValue)) {
      return targetValue;
    }

    return [this.options.jsonValue];
  }

  createJsonField(name: number | string) {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-field');
    fieldEl.innerText = `${name}`;
    return fieldEl;
  }

  createJsonSymbol() {
    const fieldEl = document.createElement('span');
    fieldEl.classList.add('bklog-json-view-symbol');
    fieldEl.innerText = ':';
    return fieldEl;
  }

  createObjectChildNode(target, depth) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-child bklog-json-view-object');
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

    Object.keys(target).forEach(key => {
      const row = document.createElement('div');
      row.classList.add('bklog-json-view-row');
      row.append(this.createJsonField(key));
      row.append(this.createJsonSymbol());
      row.append(this.createJsonNodeElment(target[key]));

      node.append(row);
    });

    return node;
  }

  createObjectNode(target, depth) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-object');
    const iconExpand = document.createElement('span');
    iconExpand.classList.add('bklog-json-view-icon-expand');

    const isExpand = depth <= this.options.depth;
    this.jsonNodeMap.set(node, {
      isExpand,
      target,
    });

    const nodeIconText = document.createElement('span');
    nodeIconText.classList.add('bklog-json-view-icon-text');
    const text = Array.isArray(target) ? '[...]' : '{...}';
    nodeIconText.innerText = text;

    const child: HTMLElement[] = [];

    if (depth <= this.options.depth) {
      child.push(this.createObjectChildNode(target, depth + 1));
    }

    return [node, nodeIconText, ...child];
  }

  createJsonNodeElment(target: any, depth = 1) {
    const node = document.createElement('div');
    node.classList.add('bklog-json-view-node');
    node.setAttribute('data-depth', `${depth}`);
    const nodeType = typeof target;

    if (nodeType === 'object') {
      node.append(...this.createObjectNode(target, depth + 1));
    } else {
      node.append(target);
    }

    return node;
  }

  initClickEvent() {
    this.targetEl.addEventListener('click', e => {
      if ((e.target as HTMLElement).classList.contains('bklog-json-view-icon-expand')) {
        const storeNode = (e.target as HTMLElement).closest('.bklog-json-view-object') as HTMLElement;

        const { isExpand, target } = this.jsonNodeMap.get(storeNode);
        const childNode = storeNode.querySelector('.bklog-json-view-child');
        if (!childNode) {
          storeNode.append(this.createObjectChildNode(target, 1));
        }
      }
    });
  }

  setJsonViewSchema(value: any) {
    this.targetEl.append(this.createJsonNodeElment(value));
  }
}
