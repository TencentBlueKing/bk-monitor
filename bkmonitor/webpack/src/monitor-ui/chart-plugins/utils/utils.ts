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
  if (v === o || v == o) return true;
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
          return `${window.i18n.tc('阈值')}(${methodMap[val.method]}${value})`;
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
      let yAxis = undefined;
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
    const filterDictTargets = queryConfig.filter_dict?.targets || [];
    let where = [];
    if (!!filterDictTargets.length) {
      where = Object.entries(filterDictTargets[0]).reduce((total, item) => {
        const [key, value] = item;
        if (value === undefined || value === 'undefined') return total;
        const res = {
          key,
          condition: 'and',
          method: 'eq',
          value: Array.isArray(value) ? value.map(val => `${val}`) : [`${value}`],
        };
        if (!excludes.includes(key)) total.push(res);
        return total;
      }, []);
    }
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

function getTextWidth(text: string, fontSize: number): number {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = `${fontSize}px sans-serif`; // 设置字体样式
  const metrics = context.measureText(text); // 测量文本的宽度
  return metrics.width; // 返回文本的宽度
}

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
  } else {
    const padLength = Math.round((widthInPx - textWidth) / 3.56); // 假设字符的宽度为 3.56px
    const paddedText = String(targetText).padStart(padLength + String(targetText).length, ' '); // 向前填充空格
    return paddedText;
  }
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
  el.className = id;
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
  document.addEventListener('click', removeWrap);
};
