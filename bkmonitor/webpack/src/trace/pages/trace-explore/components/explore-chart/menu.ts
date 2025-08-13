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

import { toPng } from 'html-to-image';
import { deepClone } from 'monitor-common/utils';
import { filterDictConvertedToWhere } from 'monitor-ui/chart-plugins/utils';

import { commOpenUrl, getMetricId, transformLogUrlQuery } from '@/plugins/utls/menu';
import { downFile } from '@/utils';

import type { IDataQuery, IExtendMetricData, ILogUrlParams } from '@/plugins/typings';

/**
 * @description: 跳转到检索
 * @param {IDataQuery[]} targets 目标
 * @param {string[]} timeRange 时间范围
 * @param {Boolean} autoNavTo 是否自动导航到检索 默认为true, 否则返回对应的targets
 * @return {*}
 */
export function handleExplore(targets: IDataQuery[], timeRange: string[], autoNavTo = true) {
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

export const handleRelateAlert = (targets: IDataQuery[], timeRange: string[]) => {
  const metricIdMap: any = {};
  targets?.forEach(target => {
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

export function handleAddStrategy(targets: IDataQuery[], metric: IExtendMetricData | null) {
  try {
    let result: any = null;
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
            const config = deepClone(queryConfig);
            result.query_configs.push({ ...filterDictConvertedToWhere(config) });
          }
        });
      });
    } else {
      targets.forEach(target => {
        target.data?.query_configs?.forEach((queryConfig: any) => {
          if (!result) {
            const config = deepClone(queryConfig);
            result = {
              ...target.data,
              query_configs: [filterDictConvertedToWhere(config)],
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
