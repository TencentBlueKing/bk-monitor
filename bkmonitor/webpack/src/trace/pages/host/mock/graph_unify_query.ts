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
export const data = {
  series: [
    {
      dimensions: {},
      target: 'MAX(load5)',
      metric_field: '_result_',
      datapoints: [
        [0.19, 1782799500000],
        [0.2, 1782799560000],
        [0.25, 1782799620000],
        [0.22, 1782799680000],
        [0.19, 1782799740000],
        [0.26, 1782799800000],
        [0.22, 1782799860000],
        [0.24, 1782799920000],
        [0.24, 1782799980000],
        [0.23, 1782800040000],
        [0.2, 1782800100000],
        [0.19, 1782800160000],
        [0.2, 1782800220000],
        [0.24, 1782800280000],
        [0.2, 1782800340000],
        [0.22, 1782800400000],
        [0.18, 1782800460000],
        [0.33, 1782800520000],
        [0.33, 1782800580000],
        [0.3, 1782800640000],
        [0.27, 1782800700000],
        [0.25, 1782800760000],
        [0.25, 1782800820000],
        [0.23, 1782800880000],
        [0.24, 1782800940000],
        [0.25, 1782801000000],
        [0.29, 1782801060000],
        [0.23, 1782801120000],
        [0.22, 1782801180000],
        [0.19, 1782801240000],
        [0.16, 1782801300000],
        [0.17, 1782801360000],
        [0.16, 1782801420000],
        [0.12, 1782801480000],
        [0.13, 1782801540000],
        [0.13, 1782801600000],
        [0.11, 1782801660000],
        [0.1, 1782801720000],
        [0.11, 1782801780000],
        [0.09, 1782801840000],
        [0.08, 1782801900000],
        [0.08, 1782801960000],
        [0.08, 1782802020000],
        [0.08, 1782802080000],
        [0.09, 1782802140000],
        [0.07, 1782802200000],
        [0.06, 1782802260000],
        [0.05, 1782802320000],
        [0.07, 1782802380000],
        [0.07, 1782802440000],
        [0.17, 1782802500000],
        [0.24, 1782802560000],
        [0.2, 1782802620000],
        [0.3, 1782802680000],
        [0.27, 1782802740000],
        [0.28, 1782802800000],
        [0.24, 1782802860000],
        [0.22, 1782802920000],
        [0.18, 1782802980000],
        [0.17, 1782803040000],
      ],
      alias: '_result_',
      stat: {
        count: [0, 60],
        sum: [0, 11.330000000000002],
        min: [1782802320000, 0.05],
        max: [1782800520000, 0.33],
        avg: [0, 0.18883333333333335],
        last: [1782803040000, 0.17],
      },
      type: 'line',
      dimensions_translation: {},
      unit: 'none',
    },
  ],
  metrics: [
    {
      id: 6940,
      bk_tenant_id: 'system',
      result_table_id: 'system.load',
      result_table_name: '负载',
      metric_field: 'load5',
      metric_field_name: '5分钟平均负载',
      unit: 'none',
      unit_conversion: 1,
      dimensions: [
        {
          id: 'bk_agent_id',
          name: 'Agent ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_biz_id',
          name: '业务ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_cloud_id',
          name: '采集器云区域ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_host_id',
          name: '采集主机ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_target_cloud_id',
          name: '云区域ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_target_host_id',
          name: '目标主机ID',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'bk_target_ip',
          name: '目标IP',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'hostname',
          name: '主机名',
          is_dimension: true,
          type: 'string',
        },
        {
          id: 'ip',
          name: '采集器IP',
          is_dimension: true,
          type: 'string',
        },
      ],
      plugin_type: '',
      related_name: 'system',
      related_id: 'system',
      collect_config: '',
      collect_config_ids: '',
      result_table_label: 'os',
      data_source_label: 'bk_monitor',
      data_type_label: 'time_series',
      data_target: 'host_target',
      default_dimensions: ['bk_target_ip', 'bk_target_cloud_id'],
      default_condition: [],
      description: '5分钟平均负载',
      collect_interval: 1,
      category_display: '物理机',
      result_table_label_name: '操作系统',
      extend_fields: {},
      use_frequency: 4,
      is_duplicate: 0,
      readable_name: 'system.load.load5',
      metric_md5: '5f5901b9e66abad5e393ed27d54e96ed',
      data_label: '',
      metric_id: 'bk_monitor.system.load.load5',
    },
  ],
};
