/*
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

import dayjs from 'dayjs';

import { type ITabItem, EKind } from './type';
export const CALLER_CALLEE_TYPE: ITabItem[] = [
  {
    label: window.i18n.t('主调'),
    id: EKind.caller,
  },
  {
    label: window.i18n.t('被调'),
    id: EKind.callee,
  },
];
export type CallerCalleeType = (typeof CALLER_CALLEE_TYPE)[number]['id'];
export const PERSPECTIVE_TYPE = [
  {
    label: window.i18n.t('单视角'),
    id: 'single',
  },
  {
    label: window.i18n.t('多视角'),
    id: 'multiple',
  },
];

export const CHART_TYPE = [
  {
    label: '饼图',
    id: 'caller-pie-chart',
  },
  {
    label: '柱状图',
    id: 'caller-bar-chart',
  },
];

export const TAB_TABLE_REQUEST_COLUMN = [
  {
    label: '数值',
    prop: 'request_total_0s',
  },
  {
    label: '占比',
    prop: 'proportions_request_total_0s',
  },
];

export const TAB_TABLE_TYPE = [
  {
    label: window.i18n.t('请求量'),
    id: 'request',
    columns: TAB_TABLE_REQUEST_COLUMN,
  },
  {
    label: window.i18n.t('成功/异常/超时率'),
    id: 'timeout',
    columns: [],
  },
  {
    label: window.i18n.t('耗时（ms）'),
    id: 'consuming',
    columns: [],
  },
];

export const SYMBOL_LIST = [
  {
    value: 'eq',
    label: window.i18n.t('等于'),
  },
  {
    value: 'neq',
    label: window.i18n.t('不等于'),
  },
  {
    value: 'before_req',
    label: window.i18n.t('前匹配'),
  },
  {
    value: 'after_req',
    label: window.i18n.t('后匹配'),
  },
  {
    value: 'include',
    label: window.i18n.t('包含'),
  },
  {
    value: 'exclude',
    label: window.i18n.t('不包含'),
  },
  {
    value: 'reg',
    label: window.i18n.t('正则'),
  },
];
const CALL_INTERVAL_LIST = [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60, 120, 180, 240, 300, 600];
/**
 *
 * @param rawInterval 原始周期
 * @description 修正周期 (只能从上面的周期列表中向上取值) api仅支持 单位 m
 */
export const intervalLowBound = (rawInterval: number) => {
  const list = CALL_INTERVAL_LIST.map(v => v - rawInterval);
  const index = list.findIndex(v => v > 0);
  return CALL_INTERVAL_LIST.at(index) || CALL_INTERVAL_LIST.at(-1);
};
/* 异常率/超时率 */
export enum EChartType {
  exceptionRate = 'exception_rate',
  timeoutRate = 'timeout_rate',
}

const recordCallOptionKindKey = '____apm-service-caller-callee-kind____';
const recordCallOptionChartKey = '____apm-service-caller-callee-chart____';

export function formatDateRange(start: number, end: number) {
  const formatStr = 'MM-DD HH:mm:ss';
  const year = new Date(start).getFullYear();
  return `${year}（${dayjs(start).format(formatStr)} ~ ${dayjs(end).format(formatStr)}）`;
}

/**
 * @description 处理时间要展示的格式 2024（11-21  18:00:00 ～ 11-22  18:00:00）
 * @param timeArr
 * @returns
 */
export function formatPreviousDayAndWeekTimestamps(timeArr: number[]) {
  const start = getPreviousDayAndWeekTimestamps(timeArr[0]);
  const end = getPreviousDayAndWeekTimestamps(timeArr[1]);

  return {
    '1d': formatDateRange(start.yesterday, end.yesterday),
    '1w': formatDateRange(start.lastWeek, end.lastWeek),
  };
}

/**
 * @description 计算某个时间的前一天/前一周
 * @param timestamp
 * @returns
 */
export function getPreviousDayAndWeekTimestamps(timestamp) {
  const oneDayInMilliseconds = 24 * 60 * 60; // 一天的毫秒数
  const oneWeekInMilliseconds = 7 * oneDayInMilliseconds; // 一周的毫秒数

  const previousDayTimestamp = timestamp - oneDayInMilliseconds;
  const previousWeekTimestamp = timestamp - oneWeekInMilliseconds;

  return {
    yesterday: previousDayTimestamp * 1000,
    lastWeek: previousWeekTimestamp * 1000,
  };
}

/**
 * @description 获取调用者调用被调用者的图表
 * @param keyObject
 * @returns
 */
export function getRecordCallOptionChart(keyObject) {
  return getRecord(recordCallOptionChartKey, keyObject, EChartType.exceptionRate);
}

/**
 * @description 获取调用者调用被调用者的类型
 * @param keyObject
 * @returns
 */
export function getRecordCallOptionKind(keyObject) {
  return getRecord(recordCallOptionKindKey, keyObject, EKind.callee);
}

/**
 * @description 记录调用者调用被调用者的图表
 * @param keyObject
 * @param chart
 */
export function setRecordCallOptionChart(keyObject, chart) {
  setRecord(recordCallOptionChartKey, keyObject, chart);
}

/**
 * @description 记录调用者调用被调用者的类型
 * @param keyObject
 * @param kind
 */
export function setRecordCallOptionKind(keyObject, kind) {
  setRecord(recordCallOptionKindKey, keyObject, kind);
}

/**
 * @description 通用检索函数，用于获取服务调用信息
 * @param storageKey 存储键
 * @param keyObject 服务的键对象
 * @param defaultValue 默认值
 * @returns
 */
function getRecord(storageKey, keyObject, defaultValue) {
  if (!(keyObject?.app_name && keyObject?.service_name)) {
    return defaultValue;
  }
  try {
    const key = `__${keyObject.app_name}__${keyObject.service_name}__`;
    const listStr = localStorage.getItem(storageKey);
    if (listStr) {
      const list = JSON.parse(listStr);
      for (const item of list) {
        if (item.key === key) {
          return item.value || defaultValue;
        }
      }
    }
  } catch (err) {
    console.log(err);
  }
  return defaultValue;
}
/**
 * @description 通用存储函数，用于存储服务调用信息
 * @param storageKey 存储键
 * @param keyObject 服务的键对象
 * @param value 需要存储的值
 */
function setRecord(storageKey, keyObject, value) {
  if (!(keyObject?.app_name && keyObject?.service_name)) {
    return;
  }
  try {
    const listStr = localStorage.getItem(storageKey);
    const obj = {
      key: `__${keyObject.app_name}__${keyObject.service_name}__`,
      value,
    };
    const list = listStr ? JSON.parse(listStr) : [];
    const resultList = list.filter(item => item.key !== obj.key);

    if (resultList.length >= 50) {
      resultList.splice(resultList.length - 1, resultList.length - 50);
    }

    resultList.unshift(obj);
    localStorage.setItem(storageKey, JSON.stringify(resultList));
  } catch (err) {
    console.log(err);
  }
}

export const createDrillDownList = (
  menuList: { disabled: boolean; id: string; name: string; selected: boolean }[],
  position: { x: number; y: number },
  clickHandler: (id: string) => void,
  instance: any
) => {
  const id = 'contextmenu-list-pop-wrapper';

  const removeEl = () => {
    const remove = document.getElementById(id);
    if (remove) {
      remove.remove();
      setTimeout(() => {
        instance?.dispatchAction({
          type: 'restore',
        });
        instance?.dispatchAction({
          type: 'takeGlobalCursor',
          key: 'dataZoomSelect',
          dataZoomSelectActive: true,
        });
      }, 500);
    }
  };

  removeEl();
  const el = document.createElement('div');
  el.className = `${id} pop-drill-down-list`;
  el.id = id;
  el.style.left = `${(() => {
    const { clientWidth } = document.body;
    if (position.x + 110 > clientWidth) {
      return position.x - 110;
    }
    return position.x;
  })()}px`;
  el.style.top = `${(() => {
    const MAX_HEIGHT = 260;
    const { clientHeight } = document.body;
    if (position.y + MAX_HEIGHT > clientHeight) {
      return position.y - MAX_HEIGHT;
    }
    return position.y;
  })()}px`;
  el.addEventListener('click', (e: any | Event) => {
    const { dataset } = e.target;
    if (e.target.classList.contains('contextmenu-list-item') && !e.target.classList.contains('active')) {
      clickHandler?.(dataset.id);
      document.removeEventListener('click', removeWrap);
      removeEl();
    }
  });
  const listEl = menuList
    .map(
      item =>
        `<div class="${item.disabled ? 'contextmenu-list-item-disabled' : 'contextmenu-list-item'} ${item.selected ? 'active' : ''}" data-id="${item.id}" data-disabled="${item.disabled}" title="${item.disabled ? window.i18n.t('当前维度外层已选中') : ''}">${item.name}</div>`
    )
    .join('');
  el.innerHTML = `
  <div class="contextmenu-list-item-title">
    ${window.i18n.t('下钻至')}
  </div>
  ${listEl}
`;
  document.body.appendChild(el);
  const eventHasId = (event: any | Event, id: string) => {
    let target = event.target;
    let has = false;
    while (target) {
      if (target.id === id) {
        has = true;
        break;
      }
      target = target?.parentNode;
    }
    return has;
  };
  function removeWrap(event: MouseEvent) {
    if (!eventHasId(event, id)) {
      removeEl();
    }
  }
  document.addEventListener('click', removeWrap);
};
