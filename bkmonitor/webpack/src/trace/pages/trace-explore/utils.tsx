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

import type { IDimensionField, IDimensionFieldTreeItem } from './typing';

export const fieldTypeMap = {
  integer: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },

  long: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  double: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  keyword: {
    name: window.i18n.tc('字符串'),
    icon: 'icon-monitor icon-Str',
    color: '#6498B3',
    bgColor: '#D9E5EB',
  },
  text: {
    name: window.i18n.tc('文本'),
    icon: 'icon-monitor icon-text1',
    color: '#508CC8',
    bgColor: '#E1E7F2',
  },
  date: {
    name: window.i18n.tc('时间'),
    icon: 'icon-monitor icon-Time',
    color: '#CDAE71',
    bgColor: '#EDE7DB',
  },
  object: {
    name: window.i18n.tc('对象'),
    icon: 'icon-monitor icon-Object',
    color: '#979BA5',
    bgColor: '#E8EAF0',
  },
  boolean: {
    name: window.i18n.tc('布尔'),
    icon: 'icon-monitor icon-buer',
    color: '#cb7979',
    bgColor: '#F5E1E1',
  },
  other: {
    name: window.i18n.tc('其他'),
    icon: 'icon-monitor icon-Others',
    fontSize: '10px',
    color: '#B59D8D',
    bgColor: '#EBE0D9',
  },
};

export const topKColorList = ['#F59789', '#F5C78E', '#5AB8A8', '#92D4F1', '#A3B1CC'];

/**
 * @description "包含" 筛选区域checkbox值映射filter配置
 */
const checkboxFilterMapByMode = {
  trace: {
    error: {
      key: 'error',
      operator: 'logic',
      value: [],
    },
  },
  span: {
    root_span: { key: 'parent_span_id', operator: 'equal', value: [''] },
    entry_span: { key: 'kind', operator: 'equal', value: ['2', '5'] },
    error: { key: 'status.code', operator: 'equal', value: ['2'] },
  },
};

/**
 * @description 根据当前激活视角和checkbox值获取filter配置
 * @param mode 当前激活的视角
 * @param val 需要获取对应filter配置的checkbox值
 *
 */
export const getFilterByCheckboxFilter = (mode: 'span' | 'trace', val: string) => {
  const filterMap = checkboxFilterMapByMode[mode];
  return filterMap[val];
};

/**
 * @description 简易观察者模式
 */
export class ExploreSubject {
  name: string;
  set: Set<ExploreObserver>;
  constructor(name: string) {
    this.name = name;
    this.set = new Set();
  }

  addObserver(observer: ExploreObserver) {
    this.set.add(observer);
  }

  notifyObservers(...args) {
    for (const observer of this.set) {
      if (observer) {
        observer.notify(...args);
      }
    }
  }
  deleteObserver(observer: ExploreObserver) {
    this.set.delete(observer);
  }

  destroy() {
    this.set.clear();
  }
}

export class ExploreObserver {
  constructor(
    private $vm,
    private fn
  ) {}

  notify(...args): void {
    this.fn.call(this.$vm, ...args);
  }
}

/** 维度列表转换tree结构 */
export function convertToTree(data: IDimensionField[]): IDimensionFieldTreeItem[] {
  const root: IDimensionFieldTreeItem[] = [];
  for (const item of data) {
    const parts = item.name.split('.');
    if (parts.length < 2) {
      root.push({ ...item, levelName: item.alias });
      continue;
    }

    let currentLevel = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      let node = currentLevel.find(n => n.levelName === part);
      if (!node) {
        node = { ...item, levelName: part };
        // 若非末层节点，初始化
        if (i < parts.length - 1) {
          node.children = [];
          node.type = 'object';
          node.name = part;
          node.alias = part;
        }
        currentLevel.push(node);
      }
      // 更新当前层级到子节点
      if (node.children) currentLevel = node.children;
      else currentLevel = []; // 末层节点无需children
    }
  }
  root.forEach(node => calculateCounts(node));
  return root;
}

// 递归计算所有节点的count值
const calculateCounts = (node: IDimensionFieldTreeItem) => {
  if (!node.children || node.children.length === 0) {
    if (node.children) node.count = 0;
    return 0;
  }
  let total = node.children.filter(child => !child.children).length;
  for (const child of node.children) {
    total += calculateCounts(child); // 递归累加子孙数量
  }
  node.count = total;
  return total;
};
