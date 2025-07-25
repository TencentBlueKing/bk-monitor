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
import { getUnitInfo } from 'monitor-api/modules/strategies';
import { random } from 'monitor-common/utils';

import type { IViewOptions } from '../typings';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

export const isEqualObject = (v: Record<string, any>, o: Record<string, any>, keys: string[] = []): boolean => {
  if (v === o) return true;
  return Object.keys(v).every(key => !keys.includes(key) || v[key] !== o[key]);
};

/**
 * @description: 由一个组件上下文ctx开始, 向上查找最近的一个组件
 * @param {any} ctx 当前组件this
 * @param {string} componentName 目标组件名
 */
export const findComponentUpper = (ctx: any, componentName: string) => {
  let parent = ctx.$parent;
  const { name } = parent.$options;
  while (parent && name !== componentName) {
    parent = ctx.$parent;
  }
  return parent;
};

/**
 * @description: 设置dom style
 * @param {HTMLElement} el 目标dom
 * @param {Record} styleObj style对象
 */
export const setStyle = (el: HTMLElement, styleObj: Record<string, string>) => {
  const styles = { ...styleObj };
  const styleArr = Object.keys(styles).map(key => `${key}:${styles[key]};`);
  el.setAttribute('style', styleArr.join(''));
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

export const createImg = (url: string) => {
  const img = document.createElement('img');
  img.src = url;
  return img;
};
/**
 *
 * @param obj
 * @param result
 * @returns
 */
export const flattenObject = (obj: Record<string, any>, result = {}): Record<string, any> => {
  for (const [key, value] of Object.entries(obj || {})) {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      flattenObject(value, result);
    } else {
      result[key] = value;
    }
  }
  return result;
};
/**
 * @description: 将viewOptions传入queryConfig用于跳转到其他页面
 * @param {any} queryConfig
 * @param {IViewOptions} viewOptions
 * @return {*}
 */
export const queryConfigTransform = (queryConfig: any, viewOptions: IViewOptions) => ({
  ...queryConfig,
  group_by: viewOptions?.group_by?.length ? viewOptions?.group_by : queryConfig?.group_by,
  interval: viewOptions?.interval || queryConfig?.interval,
  method: viewOptions?.method || queryConfig?.method,
  filter_dict: flattenObject(queryConfig?.filter_dict || {}),
});

export const isShadowEqual = (v: Record<string, any>, o: Record<string, any>) => {
  if ((v && !o) || (!v && o)) return false;
  if (JSON.stringify(v) === JSON.stringify(o)) return true;
  const vKeys = Object.keys(v);
  const oKeys = Object.keys(o);
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

export const specialEqual = (v: any, o: any) => {
  // biome-ignore lint/suspicious/noDoubleEquals: <explanation>
  if (v === o || v == o) return true;
  // biome-ignore lint/suspicious/noDoubleEquals: <explanation>
  if ([[], null, undefined, 0, {}].some(i => i == v) && [[], null, undefined, 0, {}].some(i => i == o)) return true;
  if (Array.isArray(v) && Array.isArray(o)) {
    return JSON.stringify(v.slice().sort()) === JSON.stringify(o.slice().sort());
  }
  if (JSON.stringify([v]) === JSON.stringify([o])) return true;
  return false;
};

/** 阈值方法映射数据 */
const methodMap = {
  gte: '>=',
  gt: '>',
  lte: '<=',
  lt: '<',
  eq: '=',
  neq: '!=',
};
/** 处理阈值线画图数据 */
export const handleThreshold = async (detectionsConfig: IDetectionConfig, yAxisNeedUnit = true) => {
  const thresholdLine = await getThresholds(detectionsConfig, yAxisNeedUnit);
  const markLine = getMarkLine(thresholdLine);
  const markArea = getMarkArea(thresholdLine);
  return {
    markLine,
    markArea,
  };
};
// 获取阈值信息
export const getThresholds = async (detectionsConfig: IDetectionConfig, yAxisNeedUnit: boolean) => {
  if (!detectionsConfig?.data?.length) return [];
  const lineColor = {
    1: '#ea3636',
    2: '#ffd000',
    3: '#ff8000',
  };
  let unitSeries = [];
  if (detectionsConfig.unit && yAxisNeedUnit) {
    const data = await getUnitInfo({ unit_id: detectionsConfig.unitType }).catch(() => ({}));
    unitSeries = data.unit_series || [];
  }
  let list = [];
  /**
   * 根据阈值生成阈值的配置
   */
  const handleThresholdOption = (list, level, unitConversion, title?: () => void) => {
    const result = [];
    list.forEach(cfg => {
      const thresholdVal = unitConversion ? unitConversion.unit_conversion * +cfg.threshold : +cfg.threshold;
      const thresholdTitle = methodMap[cfg.method] ? `(${methodMap[cfg.method]}${thresholdVal})` : '';
      result.push({
        name: title?.(cfg) || cfg?.name || `${window.i18n.t('静态阈值')}${thresholdTitle}`,
        // 动态单位转换
        yAxis: thresholdVal,
        method: cfg.method,
        condition: cfg.condition,
        lineStyle: {
          color: lineColor[level],
        },
        label: {
          color: lineColor[level],
        },
        itemStyle: {
          color: lineColor[level],
          opacity: 0.1,
        },
      });
    });
    return result;
  };
  /** 时序预测的预测阈值  */
  detectionsConfig.data
    .filter(item => item.type === 'TimeSeriesForecasting')
    .forEach(item => {
      const { config, level } = item;
      const unitConversion = unitSeries.find(item => item.suffix === detectionsConfig.unit);
      list = [
        ...list,
        ...handleThresholdOption(config?.thresholds?.[0], level, unitConversion, val => {
          const value = unitConversion ? unitConversion.unit_conversion * val.threshold : val.threshold;
          return `${window.i18n.t('阈值')}(${methodMap[val.method]}${value})`;
        }),
      ];
      // config?.[0].forEach((cfg) => {
      //   const thresholdTitle = methodMap[cfg.method] ? `(${methodMap[cfg.method]}${cfg.threshold})` : '';
      //   list.push({
      //     name: item.title || `${window.i18n.t('静态阈值')}${thresholdTitle}`,
      //     // 动态单位转换
      //     yAxis: unitConversion ? unitConversion.unit_conversion * +cfg.threshold : +cfg.threshold,
      //     method: cfg.method,
      //     condition: cfg.condition,
      //     lineStyle: {
      //       color: lineColor[level]
      //     },
      //     label: {
      //       color: lineColor[level]
      //     },
      //     itemStyle: {
      //       color: lineColor[level],
      //       opacity: 0.1
      //     }
      //   });
      // });
    });
  /** 静态阈值 */
  detectionsConfig.data
    .filter(item => item.type === 'Threshold')
    .forEach(item => {
      const { config, level } = item;
      const unitConversion = unitSeries.find(item => item.suffix === detectionsConfig.unit);
      list = [...list, ...handleThresholdOption(config?.[0], level, unitConversion)];
    });

  return list;
};
/** 阈值线 */
const getMarkLine = (thresholdLine: any[]) => {
  const markLine = {
    symbol: [],
    label: {
      show: true,
      position: 'insideStartTop',
    },
    lineStyle: {
      color: '#FD9C9C',
      type: 'dashed',
      distance: 3,
      width: 1,
    },
    emphasis: {
      label: {
        show: true,
        formatter(v: any) {
          return `${v.name || ''}: ${v.value}`;
        },
      },
    },
    data: thresholdLine.map((item: any) => ({
      ...item,
      label: {
        show: true,
        formatter() {
          return '';
        },
      },
    })),
  };
  return markLine;
};

/** 阈值区间 */
const getMarkArea = (thresholdLine: any[]) => {
  const handleSetThresholdAreaData = (thresholdLine: any[]) => {
    const threshold = thresholdLine.filter(item => item.method && !['eq', 'neq'].includes(item.method));

    const openInterval = ['gte', 'gt']; // 开区间
    const closedInterval = ['lte', 'lt']; // 闭区间

    const data = [];

    for (let index = 0; index < threshold.length; index++) {
      const current = threshold[index];
      const nextThreshold = threshold[index + 1];
      // 判断是否为一个闭合区间
      let yAxis;
      if (
        openInterval.includes(current.method) &&
        nextThreshold &&
        nextThreshold.condition === 'and' &&
        closedInterval.includes(nextThreshold.method) &&
        nextThreshold.yAxis >= current.yAxis
      ) {
        yAxis = nextThreshold.yAxis;
        index += 1;
      } else if (
        closedInterval.includes(current.method) &&
        nextThreshold &&
        nextThreshold.condition === 'and' &&
        openInterval.includes(nextThreshold.method) &&
        nextThreshold.yAxis <= current.yAxis
      ) {
        yAxis = nextThreshold.yAxis;
        index += 1;
      } else if (openInterval.includes(current.method)) {
        yAxis = 'max';
      } else if (closedInterval.includes(current.method)) {
        yAxis = current.yAxis < 0 ? current.yAxis : 0;
      }

      yAxis !== undefined &&
        data.push([
          {
            ...current,
          },
          {
            yAxis,
            y: yAxis === 'max' ? '0%' : '',
          },
        ]);
    }
    return data;
  };
  const markArea = {
    label: {
      show: false,
    },
    silent: true,
    data: handleSetThresholdAreaData(thresholdLine),
  };
  return markArea;
};

/**
 * 将k8s视图图表的filter_dict转换成where, 跳转新增策略、保存仪表盘时使用
 * @param queryConfig 图表panel的query_configs一条数据
 * @param excludes 排除filter_dict的key, 默认去除业务id bk_biz_id
 */
export const filterDictConvertedToWhere = (
  queryConfig: Record<string, any> = {},
  excludes: string[] = ['bk_biz_id']
): Record<string, any> => {
  try {
    const filterDict = structuredClone(queryConfig.filter_dict || {});
    const filterDictTargets = queryConfig.filter_dict?.targets || [];
    if ('targets' in filterDict) {
      filterDict.targets = undefined;
    }
    let where = [];
    const flatFilterDict = flattenObject(queryConfig.filter_dict || {});
    where = Object.entries({
      ...flatFilterDict,
      ...filterDictTargets[0],
    }).reduce((total, item) => {
      const [key, value] = item;
      if (
        value === undefined ||
        value === 'undefined' ||
        value === null ||
        value === '' ||
        (Array.isArray(value) && (value.length === 0 || value.some(v => typeof v === 'object'))) ||
        (typeof value === 'object' && !Object.keys(value).length)
      ) {
        return total;
      }

      const res = {
        key,
        condition: 'and',
        method: 'eq',
        value: Array.isArray(value) ? value.map(val => `${val}`) : [`${value}`],
      };
      if (!excludes.includes(key)) total.push(res);
      return total;
    }, []);
    queryConfig.where = [...(queryConfig?.where || []), ...where];
  } catch (error) {
    console.error(error);
  }
  return queryConfig;
};

export const getMetricId = (
  data_source_label: string,
  data_type_label: string,
  metric_field: string,
  result_table_id: string,
  index_set_id?: string,
  bkmonitor_strategy_id?: string,
  custom_event_name?: string,
  alert_name?: string
) => {
  const metaId = `${data_source_label}|${data_type_label}`;
  switch (metaId) {
    case 'bk_monitor|time_series':
    case 'custom|time_series':
    case 'bk_data|time_series':
      return [data_source_label, result_table_id, metric_field].join('.');
    case 'bk_monitor|event':
      return [data_source_label, metric_field].join('.');
    case 'bk_monitor|log':
      return [data_source_label, data_type_label, result_table_id].join('.');
    case 'bk_monitor|alert':
      return [data_source_label, data_type_label, bkmonitor_strategy_id ?? metric_field].join('.');
    case 'custom|event':
      return [data_source_label, data_type_label, result_table_id, custom_event_name].join('.');
    case 'bk_log_search|log':
      return `${data_source_label}.index_set.${index_set_id}`;
    case 'bk_log_search|series':
      return `${data_source_label}.index_set.${index_set_id}.${metric_field}`;
    case 'bk_fta|alert':
    case 'bk_fta|event':
      return [data_source_label, data_type_label, alert_name ?? metric_field].join('.');
  }
  return '';
};
/** 解析指标ID */
export const parseMetricId = (metricId: string) => {
  const splitFieldList = metricId.split('.');
  const dataSourceLabel = splitFieldList[0];
  switch (dataSourceLabel) {
    // biome-ignore lint/suspicious/noFallthroughSwitchClause: <explanation>
    case 'bk_monitor':
      if (splitFieldList[1] === 'log') {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'log',
          result_table_id: splitFieldList[2],
        };
      }
      if (splitFieldList.length === 2) {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'event',
          result_table_id: 'system.event',
          metric_field: splitFieldList[1],
        };
      }
      if (splitFieldList[1] === 'alert') {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'alert',
          metric_field: splitFieldList[2],
        };
      }
      if ([3, 4].includes(splitFieldList.length)) {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'time_series',
          result_table_id: splitFieldList.slice(1, -1).join('.'),
          metric_field: splitFieldList.slice(-1).join(''),
        };
      }
    case 'custom':
      if (splitFieldList[1] === 'event') {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'event',
          result_table_id: splitFieldList[2],
          metric_field: splitFieldList[3],
        };
      }
      return {
        data_source_label: dataSourceLabel,
        data_type_label: 'time_series',
        result_table_id: splitFieldList.slice(1, 3).join('.'),
        metric_field: splitFieldList[3],
      };
    case 'bk_log_search':
      if (splitFieldList.length === 3) {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'log',
          index_set_id: splitFieldList[2],
        };
      }
      return {
        data_source_label: dataSourceLabel,
        data_type_label: 'time_series',
        index_set_id: splitFieldList[2],
        metric_field: splitFieldList[3],
      };
    case 'bk_data':
      return {
        data_source_label: dataSourceLabel,
        data_type_label: 'time_series',
        result_table_id: splitFieldList[1],
        metric_field: splitFieldList[2],
      };
    case 'bk_fta':
      return {
        data_source_label: dataSourceLabel,
        data_type_label: splitFieldList[1],
        metric_field: splitFieldList.slice(2).join('.'),
      };
    case 'apm':
      if (splitFieldList[1] === 'log') {
        return {
          data_source_label: dataSourceLabel,
          data_type_label: 'log',
          result_table_id: splitFieldList[2],
        };
      }
      return {
        data_source_label: dataSourceLabel,
        data_type_label: 'time_series',
        result_table_id: splitFieldList[1],
        metric_field: splitFieldList[2],
      };
    default:
      return {};
  }
};
export const MAX_PONIT_COUNT = 2880;
export const MIN_PONIT_COUNT = 1440;
export const INTERVAL_CONTANT_LIST = [10, 30, 60, 2 * 60, 5 * 60, 10 * 60, 30 * 60, 60 * 60];
export const reviewInterval = (interval: 'auto' | number | string, timeRange: number, step: number) => {
  let reviewInterval = interval;
  if (interval === 'auto') {
    reviewInterval = interval;
  } else if (interval?.toString().match(/\d+[s|h|w|m|d|M|y]$/)) {
    const now = dayjs.tz();
    const nowUnix = now.unix();
    const [, v, unit] = interval.toString().match(/(\d+)([s|h|w|m|d|M|y])$/);
    reviewInterval = +Math.max(now.add(+v, unit as any).unix() - nowUnix, step || 10);
  } else {
    reviewInterval = +step || 60;
  }
  return reviewInterval;
};

export const recheckInterval = (interval: 'auto' | number | string, timeRange: number, step: number) => {
  let reviewInterval = interval;
  if (interval === 'auto') {
    const minInterval = (timeRange / (step || 60) / MAX_PONIT_COUNT) * 60;
    const maxInterval = (timeRange / (step || 60) / MIN_PONIT_COUNT) * 60;
    let minStep = Number.POSITIVE_INFINITY;
    let val: number;
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
    const [, v, unit] = interval.toString().match(/(\d+)([s|h|w|m|d|M|y])$/);
    reviewInterval = +Math.max(now.add(+v, unit as any).unix() - nowUnix, step || 60);
  } else {
    reviewInterval = step === undefined ? 60 : Math.max(10, step);
  }
  return reviewInterval;
};

export const flattenObj = obj => {
  const res = {};

  for (const key in obj) {
    if (typeof obj[key] === 'object' && obj[key] !== null) {
      flatten(res, obj[key], `${key}`);
    } else {
      res[key] = obj[key];
    }
  }

  function flatten(res, obj, keyname) {
    for (const key in obj) {
      if (typeof obj[key] === 'object' && obj[key] !== null) {
        flatten(res, obj[key], `${keyname}.${key}`);
      } else {
        res[`${keyname}.${key}`] = obj[key];
      }
    }
  }
  return res;
};

/**
 * @description 将文字填充到指定宽度
 * @param targetText
 * @param widthInPx
 * @returns
 */
export function padTextToWidth(targetText: string, widthInPx: number): string {
  if (!widthInPx) {
    return targetText;
  }
  const textWidth = getTextWidth(targetText, 12); // 获取目标文本的实际宽度（假设这个函数可以获取文本的宽度）
  // console.log(textWidth);
  if (textWidth >= widthInPx) {
    return targetText; // 如果目标文本宽度已经大于或等于目标宽度，直接返回目标文本
  }
  const padLength = Math.round((widthInPx - textWidth) / 3.56); // 假设字符的宽度为 3.56px
  const paddedText = String(targetText).padStart(padLength + String(targetText).length, ' '); // 向前填充空格
  return paddedText;
}

function getTextWidth(text: string, fontSize: number): number {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = `${fontSize}px sans-serif`; // 设置字体样式
  const metrics = context.measureText(text); // 测量文本的宽度
  return metrics.width; // 返回文本的宽度
}

/**
 * @description 格式化时间单位和值
 * @param value
 * @param unit
 * @returns
 */
export const formatTimeUnitAndValue = (value: number, unit: string) => {
  const units = [
    {
      unit: 'μs',
      value: 1,
    },
    {
      unit: 'ms',
      value: 1000,
    },
    {
      unit: 's',
      value: 1000000,
    },
    {
      unit: 'min',
      value: 60000000,
    },
    {
      unit: 'hour',
      value: 3600000000,
    },
    {
      unit: 'day',
      value: 86400000000,
    },
  ];
  let curValue = value;
  let curUnit = unit;
  if (!units.map(item => item.unit).includes(unit)) {
    return {
      value: curValue,
      unit: curUnit,
    };
  }
  while (Math.abs(curValue) >= 1000 && curUnit !== 'day') {
    const index = units.findIndex(item => item.unit === curUnit);
    curValue = value / units[index + 1].value;
    curUnit = units[index + 1].unit;
  }
  return {
    value: curValue.toFixed(2),
    unit: curUnit,
  };
};

export const createMenuList = (
  menuList: { id: string; name: string }[],
  position: { x: number; y: number },
  clickHandler: (id: string) => void,
  instance: any,
  className?: string
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
    document.removeEventListener('wheel', removeWrapWheel);
  };
  removeEl();
  const el = document.createElement('div');
  el.className = `${id} ${className || ''}`;
  el.id = id;
  el.style.left = `${(() => {
    const { clientWidth } = document.body;
    if (position.x + 110 > clientWidth) {
      return position.x - 110;
    }
    return position.x;
  })()}px`;
  el.style.top = `${(() => {
    const { clientHeight } = document.body;
    if (position.y + 32 * menuList.length > clientHeight) {
      return position.y - 32 * menuList.length;
    }
    return position.y;
  })()}px`;
  el.addEventListener('click', (e: any | Event) => {
    if (e.target.classList.contains('contextmenu-list-item')) {
      clickHandler?.(e.target.dataset.id);
      document.removeEventListener('click', removeWrap);
      removeEl();
    }
  });
  const listEl = menuList
    .map(item => `<div class="contextmenu-list-item" data-id="${item.id}">${item.name}</div>`)
    .join('');
  el.innerHTML = listEl;
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
  function removeWrapWheel(event: WheelEvent) {
    if (Math.abs(event.deltaY) > 10) {
      removeEl();
    }
  }
  document.addEventListener('click', removeWrap);
  document.addEventListener('wheel', removeWrapWheel);
};

/* 用于echarts 与非echarts图表的联动处理， 利用provide inject进行数据传递 */
export class CustomChartConnector {
  curTime = 0;
  customInstanceMap = new Map(); // 存储自定义实例
  groupId = ''; // 存储groupId
  instanceMap = new Map(); // 存储实例
  constructor(groupId) {
    this.groupId = groupId;
  }
  // 删除所有实例
  removeChartInstance() {
    this.instanceMap = new Map();
    this.customInstanceMap = new Map();
  }
  // 存储echarts 图的实例
  setChartInstance(id, instance) {
    this.instanceMap.set(id, instance);
  }
  // 存储自定图的实例
  setCustomChartInstance(id, instance) {
    this.customInstanceMap.set(id, instance);
  }
  // 更新echart图的hover坐标
  updateAxisPointer(id, time) {
    try {
      this.curTime = time;
      for (const [chartId, instance] of this.customInstanceMap) {
        if (chartId !== id) {
          instance?.dispatchAction({
            type: 'showTip',
            x: time,
          });
        }
      }
    } catch (err) {
      console.error(err);
    }
  }
  // 更新自定图的hover坐标
  updateCustomAxisPointer(id, time) {
    try {
      this.curTime = time;
      this.updateAxisPointer(id, time);
      for (const [chartId, instance] of this.instanceMap) {
        if (chartId !== id) {
          if (instance) {
            if (time) {
              let seriesIndex = -1;
              for (const seriesItem of instance?.options?.series || []) {
                seriesIndex += 1;
                let dataIndex = -1;
                let is = false;
                for (const dataItem of seriesItem.data) {
                  dataIndex += 1;
                  const valueTime = Array.isArray(dataItem) ? dataItem?.[0] : dataItem?.value?.[0];
                  if (valueTime === time) {
                    instance?.dispatchAction({
                      type: 'showTip',
                      seriesIndex,
                      dataIndex,
                    });
                    is = true;
                    break;
                  }
                }
                if (is) {
                  break;
                }
              }
            } else {
              instance?.dispatchAction({
                type: 'hideTip',
              });
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
    }
  }
}

// 根据传入的 field 去重
export const deduplicateByField = (arr, field = 'id') => {
  const map = new Map();

  for (const item of arr) {
    // 去重
    item[field] && map.set(item[field], item);
  }

  // 从 map 的 values 中生成去重后的数组
  return Array.from(map.values());
};

// 将时间字符串转换为秒
export const convertToSeconds = (timeString: string): number => {
  // 定义不同时间单位对应的秒数
  const timeUnits: { [key: string]: number } = {
    s: 1, // 秒
    m: 60, // 分钟
    h: 3600, // 小时
    d: 86400, // 天
  };

  // 使用正则表达式解析输入字符串
  const regex = /^(\d+)([smhd])$/;
  const match = timeString.match(regex);

  if (!match) {
    return 60;
  }

  const value = Number.parseInt(match[1], 10);
  const unit = match[2];

  // 计算并返回总秒数
  return value * timeUnits[unit];
};

/**
 * 为数据节点及其子节点分配唯一 ID。
 *
 * @param data - 目标数据，可以是单个节点或节点数组。
 * @param idProperty - 用于存储 ID 的属性名称，默认为 'id'。
 * @param idLength - 生成 ID 的长度，默认为 8。
 *
 * 此函数会递归地为每个节点及其所有子节点生成唯一的 ID，
 * 并将其存储在指定的属性中。适用于层级结构的数据。
 */
export const assignUniqueIds = (data, idProperty = 'id', idLength = 8) => {
  const assignId = obj => {
    obj[idProperty] = random(idLength);
    if (obj.children && Array.isArray(obj.children)) {
      for (const child of obj.children) {
        assignId(child);
      }
    }
  };

  if (Array.isArray(data)) {
    for (const item of data) {
      assignId(item);
    }
  } else {
    assignId(data);
  }
};
