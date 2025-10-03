/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { xssFilter } from 'monitor-common/utils/xss';

import type { MetricDetailV2 } from '@/pages/query-template/typings/metric';

export const getMetricTip = (data: MetricDetailV2) => {
  if (!data) {
    return '';
  }
  if (data.isNullMetric) throw Error('Metric data is wrong');
  const sourceType =
    data.data_source_label === 'bk_log_search' && data.data_type_label === 'time_series'
      ? 'log_time_series'
      : `${data.data_source_label}_${data.data_type_label}`;
  if (data.result_table_label === 'uptimecheck' && data.default_condition) {
    const response = (data.default_condition as any[]).find(
      item => item.key === 'response_code' || item.key === 'message'
    );
    if (response && !response.value) {
      return '';
    }
  }
  const options = [
    // 公共展示项
    { val: data.metric_field, label: window.i18n.t('指标名') },
    { val: data.metric_field_name, label: window.i18n.t('指标别名') },
  ];
  const unit = !data?.unit || data.unit === 'none' ? '--' : data.unit;
  const elList = {
    bk_monitor_time_series: [
      // 监控采集指
      ...options,
      { val: data.related_id, label: window.i18n.t('插件ID') },
      { val: data.related_name, label: window.i18n.t('插件名') },
      { val: data.result_table_id, label: window.i18n.t('分类ID') },
      { val: data.result_table_name, label: window.i18n.t('分类名') },
      { val: data.result_table_label_name, label: window.i18n.t('监控对象') },
      { val: unit, label: window.i18n.t('单位') },
      { val: data.description, label: window.i18n.t('含义') },
    ],
    log_time_series: [
      // 日志平台指标
      ...options,
      { val: data.related_name, label: window.i18n.t('索引集') },
      { val: data.result_table_id, label: window.i18n.t('索引') },
      { val: data?.extend_fields?.scenario_name, label: window.i18n.t('数据源类别') },
      { val: data?.extend_fields?.storage_cluster_name, label: window.i18n.t('数据源名') },
      { val: data.result_table_label_name, label: window.i18n.t('监控对象') },
      { val: unit, label: window.i18n.t('单位') },
    ],
    bk_log_search_log: [
      // 日志平台指标
      ...options,
      { val: data.related_name, label: window.i18n.t('索引集') },
      { val: data.result_table_id, label: window.i18n.t('索引') },
      { val: data?.extend_fields?.scenario_name, label: window.i18n.t('数据源类别') },
      { val: data?.extend_fields?.storage_cluster_name, label: window.i18n.t('数据源名') },
    ],
    bk_data_time_series: [
      // 计算平台指标
      ...options,
      { val: data.result_table_id, label: window.i18n.t('表名') },
      { val: data.result_table_label_name, label: window.i18n.t('监控对象') },
      { val: unit, label: window.i18n.t('单位') },
    ],
    custom_time_series: [
      // 自定义指标
      ...options,
      { val: data?.extend_fields?.bk_data_id, label: window.i18n.t('数据ID') },
      { val: data.result_table_name, label: window.i18n.t('数据名') },
      { val: data.result_table_label_name, label: window.i18n.t('监控对象') },
      { val: unit, label: window.i18n.t('单位') },
    ],
    bk_apm_time_series: [
      // 应用监控trace指标
      ...options,
      { val: data.related_id, label: window.i18n.t('插件ID') },
      { val: data.related_name, label: window.i18n.t('插件名') },
      { val: data.result_table_id, label: window.i18n.t('分类ID') },
      { val: data.result_table_name, label: window.i18n.t('分类名') },
      { val: data.result_table_label_name, label: window.i18n.t('监控对象') },
      { val: unit, label: window.i18n.t('单位') },
      { val: data.description, label: window.i18n.t('含义') },
    ],
    custom_event: [
      // 自定义事件
      ...options,
    ],
    bk_monitor_event: [
      // 系统事件
      ...options,
    ],
    bk_monitor_alert: [
      // 告警策略
      { val: data.metric_field_name, label: window.i18n.t('策略名称') },
    ],
    bk_fta_alert: [
      // 第三方告警
      { val: data.metric_field_name, label: window.i18n.t('告警名称') },
    ],
    bk_fta_event: [
      // fta事件第三方告警
      { val: data.metric_field_name, label: window.i18n.t('告警名称') },
    ],
    bk_apm_log: [
      { val: data.metric_field_name, label: window.i18n.t('应用名称') },
      { val: data.result_table_id, label: window.i18n.t('结果表') },
    ],
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
  const curElList = elList[sourceType] || [];
  const metricNameValue = (result_table_id, metric_field) => {
    if (result_table_id && metric_field) {
      return `${result_table_id}.${metric_field}`;
    }
    if (result_table_id && !metric_field) {
      return `${result_table_id}`;
    }
    return data.metric_id;
  };
  let content =
    sourceType === 'log_time_series'
      ? `<div class="item">${xssFilter(data.related_name)}.${xssFilter(data.metric_field)}</div>\n`
      : `<div class="item">${xssFilter(metricNameValue(data.result_table_id, data.metric_field) as string)}</div>\n`;
  if (data.collect_config) {
    const collectorConfig = data.collect_config
      .split(';')
      .map(item => `<div>${xssFilter(item)}</div>`)
      .join('');
    curElList.splice(0, 0, { label: window.i18n.t('采集配置'), val: collectorConfig });
  }

  if (data.metric_field === data.metric_field_name) {
    curElList.forEach((item, index) => {
      if (item.label === window.i18n.t('指标别名')) {
        curElList.splice(index, 1);
      }
    });
  }
  for (const item of curElList || []) {
    content += `<div class="item"><div>${item.label}：${
      (window.i18n.t('采集配置') === item.label ? item.val : xssFilter(item.val)) || '--'
    }</div></div>\n`;
  }

  return content;
};
