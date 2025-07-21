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
import { toPng } from 'html-to-image';
import { deepClone } from 'monitor-common/utils/utils';
import { filterDictConvertedToWhere } from 'monitor-ui/chart-plugins/utils';

import { handleTransformToTimestamp } from '../../components/time-range/utils';
import { VariablesService, downFile, reviewInterval } from '../../utils';

import type { IExtendMetricData, ILogUrlParams, IViewOptions, PanelModel } from '../typings';
import type { IIableTdArrItem } from 'monitor-pc/pages/view-detail/utils';
/**
 * 数据检索日期范围转换
 * @param {*} timeRange number | string | array
 */
export const handleTimeRange = (timeRange: number | string | string[]): { startTime: number; endTime: number } => {
  let startTime = null;
  let endTime = null;
  if (typeof timeRange === 'number') {
    endTime = dayjs.tz().unix();
    startTime = endTime - timeRange / 1000;
  } else {
    switch (timeRange) {
      case 'today': // 今天到现在为止
        startTime = dayjs.tz().format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().unix();
        break;
      case 'yesterday': // 昨天
        startTime = dayjs.tz().subtract(1, 'days').format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().subtract(1, 'days').format('YYYY-MM-DD 23:59:59');
        break;
      case 'beforeYesterday': // 前天
        startTime = dayjs.tz().subtract(2, 'days').format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().subtract(2, 'days').format('YYYY-MM-DD 23:59:59');
        break;
      case 'thisWeek': // 本周一到现在为止
        startTime = dayjs.tz().day(0).format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().unix();
        break;
      default:
        // 自定义时间段
        if (typeof timeRange === 'string') {
          const timeArr = timeRange.split('--');
          startTime = timeArr[0].trim();
          endTime = timeArr[1].trim();
        } else {
          startTime = timeRange[0];
          endTime = timeRange[1];
        }
        break;
    }
    endTime = typeof endTime === 'number' ? endTime : dayjs.tz(endTime).unix();
    startTime = typeof startTime === 'number' ? startTime : dayjs.tz(startTime).unix();
  }
  return {
    startTime,
    endTime,
  };
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
/**
 * @description: 转换跳转日志平台所需的url参数
 * @param {ILogUrlParams} data
 * @return {*}
 */
export const transformLogUrlQuery = (data: ILogUrlParams): string => {
  const { keyword, addition, start_time, end_time, bizId, time_range } = data;
  let queryStr = '';
  const queryObj = {
    bizId,
    keyword,
    addition:
      addition?.map(set => ({
        field: set.key,
        operator: set.method,
        value: (set.value || []).join(','),
      })) || [],

    start_time: start_time ? dayjs.tz(start_time).format('YYYY-MM-DD HH:mm:ss') : undefined,

    end_time: end_time ? dayjs.tz(end_time).format('YYYY-MM-DD HH:mm:ss') : undefined,
    time_range,
  };
  queryStr = Object.keys(queryObj).reduce((str, key, i) => {
    const itemVal = (queryObj as any)[key];
    if (itemVal !== undefined) {
      const itemValStr = typeof itemVal === 'object' ? JSON.stringify(itemVal) : `${itemVal}`;
      str = `${str}${i ? '&' : ''}${key}=${encodeURIComponent(itemValStr)}`;
    }
    return str;
  }, '?');
  return queryStr;
};
/**
 * @description: 跳转到检索
 * @param {PanelModel} panel 图表数据
 * @param {IViewOptions} scopedVars 变量值
 * @param {Boolean} autoNavTo 是否自动导航到检索 默认为true, 否则返回对应的targets
 * @return {*}
 */
export function handleExplore(
  panel: PanelModel,
  scopedVars: IViewOptions & Record<string, any>,
  timeRange: string[],
  autoNavTo = true
) {
  const targets: PanelModel['targets'] = JSON.parse(JSON.stringify(panel.targets));
  const variablesService = new VariablesService(scopedVars);
  targets.forEach(target => {
    target.data.query_configs =
      target?.data?.query_configs.map((queryConfig: Record<string, any> | string) =>
        queryConfigTransform(variablesService.transformVariables(queryConfig), scopedVars)
      ) || [];
  });
  /** 判断跳转日志检索 */
  const isLog = targets.some(item =>
    item.data.query_configs.some(
      (set: { data_source_label: string; data_type_label: string }) =>
        set.data_source_label === 'bk_log_search' && set.data_type_label === 'log'
    )
  );
  if (!autoNavTo) return targets;
  if (isLog) {
    const [startTime, endTime] = timeRange;
    const queryConfig = targets[0].data.query_configs[0];
    const retrieveParams: ILogUrlParams = {
      // 检索参数
      bizId: window.cc_biz_id.toString(),
      keyword: queryConfig.query_string, // 搜索关键字
      addition: queryConfig.where || [],
      start_time: startTime,
      end_time: endTime,
      time_range: 'customized',
    };
    const indexSetId = queryConfig.index_set_id;
    const queryStr = transformLogUrlQuery(retrieveParams);
    const url = `${window.bk_log_search_url}#/retrieve/${indexSetId}${queryStr}`;
    window.open(url);
  } else {
    window.open(
      `${commOpenUrl('#/data-retrieval/')}?targets=${encodeURIComponent(JSON.stringify(targets))}&from=${
        timeRange[0]
      }&to=${timeRange[1]}`
    );
  }
}
/**
 * @description: 获取跳转url
 * @param {string} hash hash值
 * @return {*}
 */
export function commOpenUrl(hash: string) {
  let url = '';
  if (process.env.NODE_ENV === 'development') {
    url = `${process.env.proxyUrl}?bizId=${window.cc_biz_id}${hash}`;
  } else {
    url = location.href.replace(location.hash, hash);
  }
  return url;
}
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
    case 'bk_log_search|log':
      return `${data_source_label}.index_set.${index_set_id}.${metric_field}`;
    case 'bk_fta|alert':
    case 'bk_fta|event':
      return [data_source_label, data_type_label, alert_name ?? metric_field].join('.');
  }
  return '';
};
export const handleRelateAlert = (panel: PanelModel, timeRange: string[]) => {
  const metricIdMap: any = {};
  panel?.targets?.forEach(target => {
    if (target.data?.query_configs?.length) {
      target.data?.query_configs?.forEach((item: any) => {
        const metricId = getMetricId(
          item.data_source_label,
          item.data_type_label,
          item.metrics?.[0]?.field,
          item.table,
          item.index_set_id
        );
        metricIdMap[metricId] = 'true';
      });
    }
  });
  let queryString = '';
  Object.keys(metricIdMap).forEach(metricId => {
    queryString += `${queryString.length ? ' or ' : ''}指标ID : ${metricId}`;
  });
  queryString.length &&
    window.open(commOpenUrl(`#/event-center?queryString=${queryString}&from=${timeRange[0]}&to=${timeRange[1]}`));
};

/**
 * @description: 下载图表为png图片
 * @param {string} title 图片标题
 * @param {HTMLElement} targetEl 截图目标元素 默认组件$el
 * @param {*} customSave 自定义保存图片
 */
export function handleStoreImage(title: string, targetEl: HTMLElement, customSave = false) {
  return toPng(targetEl)
    .then(dataUrl => {
      if (customSave) return dataUrl;
      downFile(dataUrl, `${title}.png`);
    })
    .catch(() => {});
}

export interface IUnifyQuerySeriesItem {
  datapoints: Array<[number, number]>;
  target: string;
}
/**
 * 根据图表接口响应的数据转换成表格展示的原始数据
 * @param data unify_query响应的series数据
 */
export const transformSrcData = (data: IUnifyQuerySeriesItem[]) => {
  let tableThArr = []; /** 表头数据 */
  let tableTdArr: any[] = []; /** 表格数据 */

  tableThArr = data.map(item => item.target); // 原始数据表头
  tableThArr.unshift('time');
  //  原始数据表格数据
  tableTdArr = data[0].datapoints.map(set => [
    {
      value: dayjs.tz(set[1]).format('YYYY-MM-DD HH:mm:ss'),
      originValue: set[1],
    },
  ]);
  data.forEach(item => {
    item.datapoints.forEach((set, index) => {
      tableTdArr[index]?.push({
        max: false,
        min: false,
        value: set[0],
        originValue: set[0],
      });
    });
  });
  // 计算极值
  const maxMinMap = tableThArr.map(() => ({
    max: null,
    min: null,
  }));
  tableThArr.forEach((th, index) => {
    if (index > 0) {
      const map: any = maxMinMap[index];
      map.min = tableTdArr[0][index].value;
      map.max = map.min;
      tableTdArr.forEach(td => {
        const cur = td[index]?.value;
        cur > map.max && cur !== null && (map.max = cur);
        cur < map.min && cur !== null && (map.min = cur);
      });
    }
  });
  tableTdArr.forEach(th => {
    th.forEach((td: { value: null; max: boolean; min: boolean }, i: number) => {
      if (i > 0) {
        if (maxMinMap[i].max !== null && td.value === maxMinMap[i].max) {
          td.max = true;
          maxMinMap[i].max = null;
        }
        if (maxMinMap[i].min !== null && td.value === maxMinMap[i].min) {
          td.min = true;
          maxMinMap[i].min = null;
        }
        td.min && td.max && (td.max = false);
      }
    });
  });
  return {
    tableThArr,
    tableTdArr,
  };
};

/**
 * 根据表格数据转换成csv字符串
 * @param tableThArr 表头数据
 * @param tableTdArr 表格数据
 */
export const transformTableDataToCsvStr = (tableThArr: string[], tableTdArr: Array<IIableTdArrItem[]>): string => {
  const csvList: string[] = [tableThArr.join(',')];
  tableTdArr.forEach(row => {
    const rowString = row.reduce((str, item, index) => str + (index ? ',' : '') + item.value, '');
    csvList.push(rowString);
  });
  const csvString = csvList.join('\n');
  return csvString;
};

/**
 * 根据csv字符串下载csv文件
 * @param csvStr csv字符串
 */
export const downCsvFile = (csvStr: string, name = 'csv-file.csv') => {
  csvStr = `\ufeff${csvStr}`;
  const blob = new Blob([csvStr], { type: 'text/csv,charset=UTF-8' });
  const href = window.URL.createObjectURL(blob);
  downFile(href, name);
};

/**
 * @description: 跳转到策略
 * @param {PanelModel} panel
 * @param {IExtendMetricData} metric
 * @param {IViewOptions} viewOptions
 * @param {*} isAll
 * @return {*}
 */
export function handleAddStrategy(
  panel: PanelModel,
  metric: IExtendMetricData | null,
  scopedVars: IViewOptions & Record<string, any>,
  timeRange: string[]
) {
  try {
    let result: any = null;
    const targets: PanelModel['targets'] = JSON.parse(JSON.stringify(panel.targets));
    const [startTime, endTime] = handleTransformToTimestamp(timeRange as any);
    const interval = reviewInterval(
      scopedVars.interval!,
      dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
      panel.collect_interval
    );
    const variablesService = new VariablesService({ ...scopedVars, interval });
    if (!metric) {
      result = {
        expression: '',
        query_configs: [],
      };
      targets.forEach(target => {
        target.data?.query_configs?.forEach((queryConfig: any) => {
          const resultMetrics = result.query_configs.map(
            (item: { metrics: { field: any }[] }) => item.metrics[0].field
          );
          if (!resultMetrics.includes(queryConfig.metrics[0].field)) {
            let config = deepClone(queryConfig);
            config = variablesService.transformVariables(config);
            result.query_configs.push({ ...queryConfigTransform(filterDictConvertedToWhere(config), scopedVars) });
          }
        });
      });
    } else {
      targets.forEach(target => {
        target.data?.query_configs?.forEach((queryConfig: any) => {
          if (queryConfig.metrics.map((item: { field: any }) => item.field).includes(metric.metric_field) && !result) {
            let config = deepClone(queryConfig);
            config = variablesService.transformVariables(config);
            result = {
              ...target.data,
              query_configs: [queryConfigTransform(filterDictConvertedToWhere(config), scopedVars)],
            };
          }
        });
      });
    }
    window.open(`${commOpenUrl('#/strategy-config/add')}?data=${JSON.stringify(result)}`);
  } catch (e) {
    console.info(e);
  }
}
