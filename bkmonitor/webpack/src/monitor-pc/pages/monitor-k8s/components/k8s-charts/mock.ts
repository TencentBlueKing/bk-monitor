import type { IPanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

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
export const PanelList: IPanelModel[] = [
  {
    id: 'bk_monitor.time_series.k8s.container.network',
    title: '网络',
    type: 'row',
    collapsed: true,
    panels: [
      {
        id: 'bk_monitor.time_series.k8s.container.container_network_receive_bytes_total',
        type: 'graph',
        title: '网络入带宽',
        subTitle: 'container_network_receive_bytes_total',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_network_receive_bytes_total',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                    {
                      id: 'rate',
                      params: [
                        {
                          id: 'window',
                          value: '2m',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
      {
        id: 'bk_monitor.time_series.k8s.container.container_network_transmit_bytes_total',
        type: 'graph',
        title: '网络出带宽',
        subTitle: 'container_network_transmit_bytes_total',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_network_transmit_bytes_total',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                    {
                      id: 'rate',
                      params: [
                        {
                          id: 'window',
                          value: '2m',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
    ],
  },
  {
    id: 'bk_monitor.time_series.k8s.container.cpu',
    title: 'CPU',
    type: 'row',
    collapsed: true,
    panels: [
      {
        id: 'bk_monitor.time_series.k8s.container.container_cpu_system_seconds_total',
        type: 'graph',
        title: 'container_cpu_system_seconds_total',
        subTitle: 'container_cpu_system_seconds_total',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_cpu_system_seconds_total',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                    {
                      id: 'rate',
                      params: [
                        {
                          id: 'window',
                          value: '2m',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
      {
        id: 'bk_monitor.time_series.k8s.container.container_cpu_usage_seconds_total',
        type: 'graph',
        title: 'container_cpu_usage_seconds_total',
        subTitle: 'container_cpu_usage_seconds_total',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_cpu_usage_seconds_total',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                    {
                      id: 'rate',
                      params: [
                        {
                          id: 'window',
                          value: '2m',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
      {
        id: 'bk_monitor.time_series.k8s.container.container_cpu_user_seconds_total',
        type: 'graph',
        title: 'container_cpu_user_seconds_total',
        subTitle: 'container_cpu_user_seconds_total',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_cpu_user_seconds_total',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                    {
                      id: 'rate',
                      params: [
                        {
                          id: 'window',
                          value: '2m',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
    ],
  },
  {
    id: 'bk_monitor.time_series.k8s.container.memory',
    title: '内存',
    type: 'row',
    collapsed: true,
    panels: [
      {
        id: 'bk_monitor.time_series.k8s.container.container_memory_rss',
        type: 'graph',
        title: '内存实际使用量',
        subTitle: 'container_memory_rss',
        options: {
          legend: {
            displayMode: 'list',
            placement: 'right',
          },
        },
        targets: [
          {
            data: {
              expression: 'A',
              query_configs: [
                {
                  metrics: [
                    {
                      alias: 'A',
                      table: '',
                      field: 'container_memory_rss',
                      method: '$method',
                    },
                  ],
                  interval: '$interval',
                  table: '',
                  data_source_label: 'bk_monitor',
                  data_type_label: 'time_series',
                  group_by: ['$group_by'],
                  where: [],
                  functions: [
                    {
                      id: 'time_shift',
                      params: [
                        {
                          id: 'n',
                          value: '$time_shift',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      },
    ],
  },
];
