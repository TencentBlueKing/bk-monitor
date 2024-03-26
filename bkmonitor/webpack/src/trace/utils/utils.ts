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

import dayjs from 'dayjs';
import { xssFilter } from 'monitor-common/utils/xss';

import { IExtendMetricData } from '../plugins/typings';

export const specialEqual = (v: any, o: any) => {
  if (v === o || v == o) return true;
  if ([[], null, undefined, 0, {}].some(i => i == v) && [[], null, undefined, 0, {}].some(i => i == o)) return true;
  if (Array.isArray(v) && Array.isArray(o)) {
    return JSON.stringify(v.slice().sort()) === JSON.stringify(o.slice().sort());
  }
  if (JSON.stringify([v]) === JSON.stringify([o])) return true;
  return false;
};

export const isShadowEqual = (v: Record<string, any>, o: Record<string, any>) => {
  if ((v && !o) || (!v && o)) return false;
  if (JSON.stringify(v) === JSON.stringify(o)) return true;
  const vKeys = Object.keys(v);
  const oKeys = Object.keys(v);
  if (vKeys.length !== oKeys.length) return false;
  if (vKeys.some(key => !oKeys.includes(key))) return false;
  let ret = true;
  vKeys.some(key => {
    if (specialEqual(v[key], o[key])) return false;
    ret = false;
    return true;
  });
  return ret;
};

export const MAX_PONIT_COUNT = 2880;
export const MIN_PONIT_COUNT = 1440;
export const INTERVAL_CONTANT_LIST = [10, 30, 60, 2 * 60, 5 * 60, 10 * 60, 30 * 60, 60 * 60];
export const reviewInterval = (interval: number | 'auto' | string, timeRange: number, step: number) => {
  let reviewInterval = interval;
  if (interval === 'auto') {
    reviewInterval = interval;
  } else if (interval?.toString().match(/\d+[s|h|w|m|d|M|y]$/)) {
    const now = dayjs.tz();
    const nowUnix = now.unix();
    const [, v, unit] = interval.toString().match(/(\d+)([s|h|w|m|d|M|y])$/) as any;
    reviewInterval = +Math.max(now.add(+v, unit as any).unix() - nowUnix, step || 10);
  } else {
    reviewInterval = +step || 60;
  }
  return reviewInterval;
};

export const recheckInterval = (interval: number | 'auto' | string, timeRange: number, step: number) => {
  let reviewInterval = interval;
  if (interval === 'auto') {
    const minInterval = (timeRange / (step || 60) / MAX_PONIT_COUNT) * 60;
    const maxInterval = (timeRange / (step || 60) / MIN_PONIT_COUNT) * 60;
    let minStep = Infinity;
    let val = 0;
    INTERVAL_CONTANT_LIST.forEach(v => {
      const step1 = Math.abs(v - minInterval);
      const step2 = Math.abs(v - maxInterval);
      val = Math.min(step1, step2) <= minStep ? v : val;
      minStep = Math.min(step1, step2, minStep);
    });
    reviewInterval = Math.max(val, step);
  } else if (interval?.toString().match(/\d+[s|h|w|m|d|M|y]$/)) {
    const now = dayjs.tz();
    const nowUnix = now.unix();
    const [, v, unit] = interval.toString().match(/(\d+)([s|h|w|m|d|M|y])$/) as any;
    reviewInterval = +Math.max(now.add(+v, unit as any).unix() - nowUnix, step || 60);
  } else {
    reviewInterval = step === undefined ? 60 : Math.max(10, step);
  }
  return reviewInterval;
};

export const createMetricTitleTooltips = (metricData: IExtendMetricData) => {
  const data = metricData;
  const curActive = `${data.data_source_label}_${data.data_type_label}`;
  const options = [
    // 公共展示项
    { val: data.metric_field, label: window.i18n.t('指标名') },
    { val: data.metric_field_name, label: window.i18n.t('指标别名') }
  ];
  const elList = {
    bk_monitor_time_series: [
      // 监控采集
      ...options,
      { val: data.related_id, label: window.i18n.t('插件ID') },
      { val: data.related_name, label: window.i18n.t('插件名') },
      { val: data.result_table_id, label: window.i18n.t('分类ID') },
      { val: data.result_table_name, label: window.i18n.t('分类名') },
      { val: data.description, label: window.i18n.t('含义') }
    ],
    bk_log_search_time_series: [
      // 日志采集
      ...options,
      { val: data.related_name, label: window.i18n.t('索引集') },
      { val: data.result_table_id, label: window.i18n.t('索引') },
      { val: data.extend_fields?.scenario_name, label: window.i18n.t('数据源类别') },
      { val: data.extend_fields?.storage_cluster_name, label: window.i18n.t('数据源名') }
    ],
    bk_data_time_series: [
      // 数据平台
      ...options,
      { val: data.result_table_id, label: window.i18n.t('表名') }
    ],
    custom_time_series: [
      // 自定义指标
      ...options,
      { val: data.extend_fields?.bk_data_id, label: window.i18n.t('数据ID') },
      { val: data.result_table_name, label: window.i18n.t('数据名') }
    ],
    bk_monitor_log: [...options]
  };
  // 拨测指标融合后不需要显示插件id插件名
  const resultTableLabel = data.result_table_label;
  const relatedId = data.related_id;
  if (resultTableLabel === 'uptimecheck' && !relatedId) {
    const list = elList.bk_monitor_time_series;
    elList.bk_monitor_time_series = list.filter(
      item => item.label !== window.i18n.t('插件ID') && item.label !== window.i18n.t('插件名')
    );
  }
  const curElList = (elList as any)[curActive] || [...options];
  let content =
    curActive === 'bk_log_search_time_series'
      ? `<div class="item">${xssFilter(data.related_name)}.${xssFilter(data.metric_field)}</div>\n`
      : `<div class="item">${xssFilter(data.result_table_id)}.${xssFilter(data.metric_field)}</div>\n`;
  if (data.collect_config) {
    const collectorConfig = data.collect_config
      .split(';')
      .map(item => `<div>${xssFilter(item)}</div>`)
      .join('');
    curElList.splice(0, 0, { label: window.i18n.t('采集配置'), val: collectorConfig });
  }

  if (data.metric_field === data.metric_field_name) {
    const index = curElList.indexOf((item: { label: string }) => item.label === window.i18n.t('指标别名'));
    curElList.splice(index, 1);
  }
  curElList.forEach((item: { label: any; val: any }) => {
    content += `<div class="item"><div>${item.label}：${
      window.i18n.t('采集配置') === item.label ? item.val : xssFilter(item.val) || '--'
    }</div></div>\n`;
  });
  return content;
};

/**
 * 下载文件
 * @param url 资源地址
 * @param name 资源名称
 */
export const downFile = (url: string, name = ''): void => {
  const element = document.createElement('a');
  element.setAttribute('href', url);
  element.setAttribute('download', name);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
};

/** Trace span类型 icon 枚举 */
export const getSpanKindIcon = (kind: number) => {
  switch (kind) {
    case 0:
      return 'undefined';
    case 1:
      return 'neibutiaoyong';
    case 2:
    case 3:
      return 'tongbu';
    case 4:
    case 5:
      return 'yibu';
    default:
      return '';
  }
};

/**
 * 把Byte数值转换成最适合的单位数值
 * @param size 大小
 * @returns 最终结果
 */
export const transformByte = (size: number) => {
  const units = ['Byte', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  let index = 0;
  let number = size;

  if (isNaN(size) || size < 0) {
    return '-';
  }

  while (number > 1024 && index < units.length - 1) {
    number /= 1024;
    index += 1;
  }

  number = Math.round(number * 100) / 100;
  return `${number}${units[index]}`;
};
