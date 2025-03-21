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

import { DimensionsTypeEnum } from './typing';

export const fieldTypeMap = {
  integer: {
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
};

/**
 * @description 固定维度信息数据类型显示排序顺序及固定类型与图表颜色的映射顺序
 */
export const eventChartMap = {
  [DimensionsTypeEnum.WARNING]: 0,
  [DimensionsTypeEnum.NORMAL]: 1,
  [DimensionsTypeEnum.DEFAULT]: 2,
};
export const EVENT_CHART_COLORS = ['#F5C78E', '#70A0FF', '#A3B1CC'];

/**
 * @description 根据事件类型获取图表颜色
 * @param {DimensionsTypeEnum} type 事件类型
 */
export const getEventLegendColorByType = (type: DimensionsTypeEnum) => {
  const index = eventChartMap[type];
  if (index == null) {
    return;
  }
  return EVENT_CHART_COLORS[eventChartMap[type]];
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
