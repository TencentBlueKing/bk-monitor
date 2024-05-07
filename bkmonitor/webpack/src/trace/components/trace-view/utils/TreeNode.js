/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
export default class TreeNode {
  static iterFunction(fn, depth = 0) {
    return node => fn(node.value, node, depth);
  }

  static searchFunction(search) {
    if (typeof search === 'function') {
      return search;
    }

    return (value, node) => (search instanceof TreeNode ? node === search : value === search);
  }

  constructor(value, children = []) {
    this.value = value;
    this.children = children;
  }

  get depth() {
    return this.children.reduce((depth, child) => Math.max(child.depth + 1, depth), 1);
  }

  get size() {
    let i = 0;

    this.walk(() => i++);
    return i;
  }

  addChild(child) {
    this.children.push(child instanceof TreeNode ? child : new TreeNode(child));
    return this;
  }

  find(search) {
    const searchFn = TreeNode.iterFunction(TreeNode.searchFunction(search));
    if (searchFn(this)) {
      return this;
    }
    // eslint-disable-next-line @typescript-eslint/prefer-for-of
    for (let i = 0; i < this.children.length; i++) {
      const result = this.children[i].find(search);
      if (result) {
        return result;
      }
    }
    return null;
  }

  getPath(search) {
    const searchFn = TreeNode.iterFunction(TreeNode.searchFunction(search));

    const findPath = (currentNode, currentPath) => {
      // skip if we already found the result
      const attempt = currentPath.concat([currentNode]);
      // base case: return the array when there is a match
      if (searchFn(currentNode)) {
        return attempt;
      }
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      for (let i = 0; i < currentNode.children.length; i++) {
        const child = currentNode.children[i];
        const match = findPath(child, attempt);
        if (match) {
          return match;
        }
      }
      return null;
    };

    return findPath(this, []);
  }

  paths(fn) {
    const stack = [];
    stack.push({ node: this, childIndex: 0 });
    const paths = [];
    while (stack.length) {
      const { node, childIndex } = stack[stack.length - 1];
      if (node.children.length >= childIndex + 1) {
        stack[stack.length - 1].childIndex++;
        stack.push({ node: node.children[childIndex], childIndex: 0 });
      } else {
        if (node.children.length === 0) {
          const path = stack.map(item => item.node.value);
          fn(path);
        }
        stack.pop();
      }
    }
    return paths;
  }

  walk(fn, depth = 0) {
    const nodeStack = [];
    let actualDepth = depth;
    nodeStack.push({ node: this, depth: actualDepth });
    while (nodeStack.length) {
      const { node, depth: nodeDepth } = nodeStack.pop();
      fn(node.value, node, nodeDepth);
      actualDepth = nodeDepth + 1;
      let i = node.children.length - 1;
      while (i >= 0) {
        nodeStack.push({ node: node.children[i], depth: actualDepth });

        i--;
      }
    }
  }
}
