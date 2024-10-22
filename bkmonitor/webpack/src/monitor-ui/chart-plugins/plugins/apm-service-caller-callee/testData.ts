/*
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

export const dashboardPanelList = [
  {
    id: 1,
    title: '请求数',
    type: 'apm-timeseries-chart',
    gridPos: {
      x: 0,
      y: 0,
      w: 24,
      h: 6,
    },
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: '请求',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              table: '${table_id}',
              metrics: [
                {
                  field: 'bk_apm_count',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: [],
              display: true,
              where: [
                {
                  key: 'kind',
                  method: 'eq',
                  value: ['3'],
                },
                {
                  condition: 'or',
                  key: 'kind',
                  method: 'eq',
                  value: ['4'],
                },
              ],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [],
            },
          ],
          stack: 'all',
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '${table_id}',
                metrics: [
                  {
                    field: 'bk_apm_count',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: [],
                display: true,
                where: [
                  {
                    key: 'kind',
                    method: 'eq',
                    value: ['3'],
                  },
                  {
                    condition: 'or',
                    key: 'kind',
                    method: 'eq',
                    value: ['4'],
                  },
                ],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [],
              },
            ],
          },
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'request_count',
        unit: 'number',
        enableContextmenu: true,
      },
      time_series: {
        type: 'bar',
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 2,
    title: '错误数',
    type: 'apm-timeseries-chart',
    gridPos: {
      x: 0,
      y: 0,
      w: 24,
      h: 6,
    },
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: '类型1',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              table: '${table_id}',
              metrics: [
                {
                  field: 'bk_apm_count',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: [],
              display: true,
              where: [
                {
                  key: 'kind',
                  method: 'eq',
                  value: ['3'],
                },
                {
                  condition: 'or',
                  key: 'kind',
                  method: 'eq',
                  value: ['4'],
                },
              ],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [],
            },
          ],
          stack: 'all',
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '${table_id}',
                metrics: [
                  {
                    field: 'bk_apm_count',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: [],
                display: true,
                where: [
                  {
                    key: 'kind',
                    method: 'eq',
                    value: ['3'],
                  },
                  {
                    condition: 'or',
                    key: 'kind',
                    method: 'eq',
                    value: ['4'],
                  },
                ],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [],
              },
            ],
          },
          fill_bar: true,
        },
      },
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: '类型2',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              table: '${table_id}',
              metrics: [
                {
                  field: 'bk_apm_count',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: [],
              display: true,
              where: [
                {
                  key: 'kind',
                  method: 'eq',
                  value: ['2'],
                },
                {
                  condition: 'or',
                  key: 'kind',
                  method: 'eq',
                  value: ['5'],
                },
              ],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [],
            },
          ],
          stack: 'all',
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '${table_id}',
                metrics: [
                  {
                    field: 'bk_apm_count',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: [],
                display: true,
                where: [
                  {
                    key: 'kind',
                    method: 'eq',
                    value: ['2'],
                  },
                  {
                    condition: 'or',
                    key: 'kind',
                    method: 'eq',
                    value: ['5'],
                  },
                ],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [],
              },
            ],
          },
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'request_count',
        unit: 'number',
        enableContextmenu: true,
      },
      time_series: {
        type: 'bar',
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 3,
    title: '响应耗时',
    gridPos: {
      x: 0,
      y: 0,
      w: 24,
      h: 6,
    },
    type: 'apm-timeseries-chart',
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'P50',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              table: '${table_id}',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_bucket',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: ['le'],
              display: true,
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'rate',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'histogram_quantile',
                  params: [
                    {
                      id: 'scalar',
                      value: 0.5,
                    },
                  ],
                },
              ],
            },
          ],
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                table: '${table_id}',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'rate',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.5,
                      },
                    ],
                  },
                ],
              },
            ],
          },
          fill_bar: true,
        },
      },
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'P95',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              table: '${table_id}',
              metrics: [
                {
                  field: 'bk_apm_duration_bucket',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: ['le'],
              display: true,
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'rate',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'histogram_quantile',
                  params: [
                    {
                      id: 'scalar',
                      value: 0.95,
                    },
                  ],
                },
              ],
            },
          ],
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '${table_id}',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'rate',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.95,
                      },
                    ],
                  },
                ],
              },
            ],
          },
          fill_bar: true,
        },
      },
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'MAX',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              table: '${table_id}',
              metrics: [
                {
                  field: 'bk_apm_duration_bucket',
                  method: 'SUM',
                  alias: 'A',
                },
              ],
              group_by: ['le'],
              display: true,
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'rate',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'histogram_quantile',
                  params: [
                    {
                      id: 'scalar',
                      value: 0.99,
                    },
                  ],
                },
              ],
            },
          ],
          unify_query_param: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '${table_id}',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'SUM',
                    alias: 'A',
                  },
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'rate',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.99,
                      },
                    ],
                  },
                ],
              },
            ],
          },
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
];
export const dialogPanelList = [
  {
    id: 1,
    title: '',
    type: 'caller-pie-chart',
    gridPos: {
      x: 0,
      y: 0,
      w: 24,
      h: 6,
    },
    targets: [],
    options: {
      apm_time_series: {
        metric: 'request_count',
        unit: 'number',
        enableContextmenu: true,
      },
      time_series: {
        type: 'bar',
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 2,
    title: '',
    type: 'apm-timeseries-chart',
    gridPos: {
      x: 0,
      y: 0,
      w: 24,
      h: 6,
    },
    targets: [],
    options: {
      apm_time_series: {
        metric: 'request_count',
        unit: 'number',
        enableContextmenu: true,
      },
      time_series: {
        type: 'bar',
        hoverAllTooltips: true,
      },
    },
  },
];
export const dashboardPanels = [
  {
    id: 1,
    title: '请求量',
    gridPos: {
      x: 0,
      y: 0,
      w: 8,
      h: 6,
    },
    type: 'caller-line-chart',
    targets: [
      {
        alias: 'AVG',
        api: 'apm_metric.dynamicUnifyQuery',
        compareFieldsSort: [],
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          unit: 'ns',
          expression: 'a / b',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_sum',
                  method: 'SUM',
                  alias: 'a',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
            },
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_total',
                  method: 'SUM',
                  alias: 'b',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: null,
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
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
          unify_query_param: {
            expression: 'a / b',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_sum',
                    method: 'SUM',
                    alias: 'a',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                ],
              },
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_total',
                    method: 'SUM',
                    alias: 'b',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: null,
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
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
          fill_bar: true,
          emphasis: {
            itemStyle: {
              borderWidth: 6,
              shadowColor: 'red',
              shadowBlur: 10,
            },
          },
        },
        datasource: 'time_series',
        field: {},
        fields: {},
        fieldsKey: '',
        fieldsSort: [],
        isMultiple: false,
        data_type: 'time_series',
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 2,
    title: '成功率',
    gridPos: {
      x: 8,
      y: 0,
      w: 8,
      h: 6,
    },
    type: 'caller-line-chart',
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'AVG',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          unit: 'ns',
          expression: 'a / b',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_sum',
                  method: 'SUM',
                  alias: 'a',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
            },
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_total',
                  method: 'SUM',
                  alias: 'b',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: null,
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
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
          unify_query_param: {
            expression: 'a / b',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_sum',
                    method: 'SUM',
                    alias: 'a',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                ],
              },
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_total',
                    method: 'SUM',
                    alias: 'b',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: null,
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
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
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 3,
    title: '异常率/超时率',
    gridPos: {
      x: 16,
      y: 0,
      w: 8,
      h: 6,
    },
    type: 'caller-line-chart',
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'AVG',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          unit: 'ns',
          expression: 'a / b',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_sum',
                  method: 'SUM',
                  alias: 'a',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
            },
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_total',
                  method: 'SUM',
                  alias: 'b',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: null,
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
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
          unify_query_param: {
            expression: 'a / b',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_sum',
                    method: 'SUM',
                    alias: 'a',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                ],
              },
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_total',
                    method: 'SUM',
                    alias: 'b',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: null,
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
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
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 4,
    title: '耗时',
    gridPos: {
      x: 0,
      y: 6,
      w: 8,
      h: 6,
    },
    type: 'caller-line-chart',
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'AVG',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          unit: 'ns',
          expression: 'a / b',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_sum',
                  method: 'SUM',
                  alias: 'a',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
            },
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_total',
                  method: 'SUM',
                  alias: 'b',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: null,
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
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
          unify_query_param: {
            expression: 'a / b',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_sum',
                    method: 'SUM',
                    alias: 'a',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                ],
              },
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_total',
                    method: 'SUM',
                    alias: 'b',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: null,
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
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
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 5,
    title: '耗时分布',
    gridPos: {
      x: 8,
      y: 6,
      w: 8,
      h: 6,
    },
    type: 'caller-line-chart',
    targets: [
      {
        data_type: 'time_series',
        api: 'apm_metric.dynamicUnifyQuery',
        datasource: 'time_series',
        alias: 'AVG',
        data: {
          app_name: '${app_name}',
          service_name: '${service_name}',
          unit: 'ns',
          expression: 'a / b',
          query_configs: [
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_duration_sum',
                  method: 'SUM',
                  alias: 'a',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: 'time',
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
            },
            {
              data_source_label: 'custom',
              data_type_label: 'time_series',
              metrics: [
                {
                  field: 'bk_apm_total',
                  method: 'SUM',
                  alias: 'b',
                },
              ],
              table: '${table_id}',
              data_label: '',
              index_set_id: null,
              group_by: [],
              where: [],
              interval_unit: 's',
              time_field: null,
              filter_dict: {
                service_name: '${service_name}',
              },
              functions: [
                {
                  id: 'increase',
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
          unify_query_param: {
            expression: 'a / b',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_sum',
                    method: 'SUM',
                    alias: 'a',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
                    params: [
                      {
                        id: 'window',
                        value: '2m',
                      },
                    ],
                  },
                ],
              },
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_total',
                    method: 'SUM',
                    alias: 'b',
                  },
                ],
                table: '${table_id}',
                data_label: '',
                index_set_id: null,
                group_by: [],
                where: [],
                interval_unit: 's',
                time_field: null,
                filter_dict: {
                  service_name: '${service_name}',
                },
                functions: [
                  {
                    id: 'increase',
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
          fill_bar: true,
        },
      },
    ],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
  {
    id: 6,
    title: '耗时热力图',
    gridPos: {
      x: 16,
      y: 6,
      w: 8,
      h: 6,
    },
    type: 'apm-heatmap',
    targets: [],
    options: {
      apm_time_series: {
        metric: 'avg_duration',
        unit: 'μs',
        enableContextmenu: true,
      },
      time_series: {
        hoverAllTooltips: true,
      },
    },
  },
];
