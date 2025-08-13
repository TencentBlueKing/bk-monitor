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
import { docCookies, LANGUAGE_COOKIE_KEY, xssFilter } from 'monitor-common/utils';

import type { ICommonChartTips, IExtendMetricData } from '../typings';

export const createTooltip = (tipsData: ICommonChartTips) => {
  const liHtmlList =
    tipsData?.list?.map(item => {
      if (item.value === null) return '';
      const markStyle = item.isCurrent ? "color: '#ffffff';font-weight: bold;" : "color: '#fafbfd';";
      return `<li style="display: flex;align-items: center;flex: 1;margin-right: 5px;">
    <span
     style="background-color:${item.color};margin-right: 10px;width: 6px;height: 6px; border-radius: 50%;">
    </span>
    <span style="${markStyle}${item.style || ''}">${item.name}:</span>
    <span style="${markStyle} flex: 1;margin-left: 5px;${item.style || ''}">
    ${item.value} ${item.unit || ''}</span>
    </li>`;
    }) || [];
  if (!liHtmlList.length) return '';
  return `<div style="z-index:12; border-radius: 6px">
  <p style="text-align:center;margin: 0 0 5px 0;font-weight: bold;">
      ${tipsData.title}
  </p>
  <ul style="padding: 0;margin: 0; ${tipsData.style || ''}">
      ${liHtmlList?.join('')}
  </ul>
  </div>`;
};

export const createMetricTitleTooltips = (metricData: IExtendMetricData) => {
  const data = metricData;
  const curActive = `${data.data_source_label}_${data.data_type_label}`;
  const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
  const enName = !data.metric_field_name || data.metric_field_name === data.metric_field ? '' : data.metric_field_name;
  const options = [
    // 公共展示项
    { val: isEn ? enName || data.metric_field : data.metric_field, label: window.i18n.t('指标名') },
    { val: data.metric_field_name, label: window.i18n.t('指标别名') },
  ];
  const elList = {
    bk_monitor_time_series: [
      // 监控采集
      ...options,
      { val: data.related_id, label: window.i18n.t('插件ID') },
      { val: data.related_name, label: window.i18n.t('插件名') },
      { val: data.result_table_id, label: window.i18n.t('分类ID') },
      { val: data.result_table_name, label: window.i18n.t('分类名') },
      { val: data.description, label: window.i18n.t('含义') },
    ],
    bk_log_search_time_series: [
      // 日志采集
      ...options,
      { val: data.related_name, label: window.i18n.t('索引集') },
      { val: data.result_table_id, label: window.i18n.t('索引') },
      { val: data.extend_fields.scenario_name, label: window.i18n.t('数据源类别') },
      { val: data.extend_fields.storage_cluster_name, label: window.i18n.t('数据源名') },
    ],
    bk_data_time_series: [
      // 数据平台
      ...options,
      { val: data.result_table_id, label: window.i18n.t('表名') },
    ],
    custom_time_series: [
      // 自定义指标
      ...options,
      { val: data.extend_fields.bk_data_id, label: window.i18n.t('数据ID') },
      { val: data.result_table_name, label: window.i18n.t('数据名') },
    ],
    bk_monitor_log: [...options],
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
  const curElList = elList[curActive] || [...options];
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
    const index = curElList.indexOf(item => item.label === window.i18n.t('指标别名'));
    curElList.splice(index, 1);
  }
  curElList.forEach(item => {
    content += `<div class="item"><div>${item.label}：${
      item.label === window.i18n.t('采集配置') ? item.val : xssFilter(item.val) || '--'
    }</div></div>\n`;
  });
  return content;
};
