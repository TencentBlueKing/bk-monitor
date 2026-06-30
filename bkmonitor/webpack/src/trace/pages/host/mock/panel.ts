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
export const panel = {
  id: 'bk_monitor.time_series.system.load.load5',
  type: 'graph',
  title: '5分钟平均负载',
  subTitle: 'system.load.load5',
  targets: [
    {
      data: {
        expression: 'A',
        query_configs: [
          {
            metrics: [
              {
                field: 'load5',
                method: '$method',
                alias: 'A',
              },
            ],
            interval: '$interval', // 汇聚周期 变量
            table: 'system.load',
            data_source_label: 'bk_monitor',
            data_type_label: 'time_series',
            group_by: ['$group_by'], // 汇聚维度 变量
            where: [],
            functions: [
              {
                id: 'time_shift',
                params: [
                  {
                    id: 'n',
                    value: '$time_shift', // 时间偏移 变量
                  },
                ],
              },
            ],
            filter_dict: {
              targets: ['$current_target', '$compare_targets'], // 目标对比 变量
            },
          },
        ],
      },
      ignore_group_by: ['bk_host_id'],
      alias: '',
      datasource: 'time_series',
      data_type: 'time_series',
      api: 'grafana.graphUnifyQuery',
    },
  ],
  matchDisplay: {
    os_type: 'linux',
  },
};
