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
export const PANEL_INTERVAL_LIST = [
  {
    name: 'auto',
    id: 'auto',
  },
  {
    name: window.i18n.t('10 秒'),
    id: '10s',
  },
  {
    name: window.i18n.t('30 秒'),
    id: '30s',
  },
  {
    name: window.i18n.t('60 秒'),
    id: '60s',
  },
  {
    name: window.i18n.t('2 分钟'),
    id: '2m',
  },
  {
    name: window.i18n.t('5 分钟'),
    id: '5m',
  },
  {
    name: window.i18n.t('10 分钟'),
    id: '10m',
  },
  {
    name: window.i18n.t('30 分钟'),
    id: '30m',
  },
  {
    name: window.i18n.t('1 小时'),
    id: '1h',
  },
];

export const COMPARE_TIME_OPTIONS = [
  {
    id: '1h',
    name: window.i18n.t('1 小时前'),
  },
  {
    id: '1d',
    name: window.i18n.t('昨天'),
  },
  {
    id: '1w',
    name: window.i18n.t('上周'),
  },
  {
    id: '1M',
    name: window.i18n.t('一月前'),
  },
];

export const PANEL_LAYOUT_LIST = [
  {
    id: 1,
    name: window.i18n.t('一列'),
  },
  {
    id: 2,
    name: window.i18n.t('两列'),
  },
  {
    id: 3,
    name: window.i18n.t('三列'),
  },
  {
    id: 4,
    name: window.i18n.t('四列'),
  },
  {
    id: 5,
    name: window.i18n.t('五列'),
  },
];

export const METHOD_LIST = [
  {
    id: 'SUM',
    name: 'SUM',
  },
  {
    id: 'AVG',
    name: 'AVG',
  },
  {
    id: 'MAX',
    name: 'MAX',
  },
  {
    id: 'MIN',
    name: 'MIN',
  },
  {
    id: 'COUNT',
    name: 'COUNT',
  },
];

export const CP_METHOD_LIST = [
  {
    id: 'CP50',
    name: 'P50',
  },
  {
    id: 'CP90',
    name: 'P90',
  },
  {
    id: 'CP95',
    name: 'P95',
  },
  {
    id: 'CP99',
    name: 'P99',
  },
  {
    id: 'sum_without_time',
    name: 'SUM(PromQL)',
  },
  {
    id: 'max_without_time',
    name: 'MAX(PromQL)',
  },
  {
    id: 'min_without_time',
    name: 'MIN(PromQL)',
  },
  {
    id: 'count_without_time',
    name: 'COUNT(PromQL)',
  },
  {
    id: 'avg_without_time',
    name: 'AVG(PromQL)',
  },
];

export const DEFAULT_METHOD = 'AVG';

/**
 * @description 查找targetNode是否含有指定名称为targetStr className | id | tagName
 * @param targetNode DOM节点
 * @param targetStr className | id | tagName
 * @returns
 */
export const hasTargetCondition = (targetNode: HTMLElement, targetStr: string): boolean => {
  const [prefix, ...args] = targetStr.split('');
  const content = args.join('');
  return (
    (prefix === '.' && targetNode.className?.includes(content)) ||
    (prefix === '#' && targetNode.id?.includes(content)) ||
    targetStr.toLocaleUpperCase() === targetNode.nodeName
  );
};
/**
 * 不传targetStr参数时: 获取event事件的父级列表
 * 传入targetStr参数时: 查找targetStr
 * @param event 事件对象
 * @param targetStr 目标节点
 * @returns event事件的父集列表 或者 targetStr
 */
export const getEventPaths = (event: any | Event, targetStr = ''): (any | Event)[] => {
  if (event.path) {
    return targetStr ? event.path : event.path.filter(dom => hasTargetCondition(dom, targetStr));
  }
  const path = [];
  let target = event.target;
  while (target) {
    if (targetStr) {
      if (hasTargetCondition(target, targetStr)) {
        path.push(target);
        return path;
      }
    } else {
      path.push(target);
    }
    target = target.parentNode;
  }
  return path;
};
