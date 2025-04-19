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
export const getStatisticsInfo = (params, options) => {
  return new Promise(resolve => {
    console.log('getStatisticsInfo', params, options);
    setTimeout(() => {
      resolve([
        {
          field: 'start_time',
          total_count: 5170088,
          field_count: 5170088,
          distinct_count: 5151798,
          field_percent: 1,
          value_analysis: {
            max: 1742808209140534,
            min: 1742455412965676,
            avg: 1742611966626709.2,
            median: 1742583930172003.8,
          },
        },
      ]);
    }, 500);
  });
};

export const getStatisticsChartData = (params, options) => {
  return new Promise(resolve => {
    console.log('getStatisticsChartData', params, options);
    setTimeout(() => {
      resolve({
        series: [
          {
            dimensions: {
              span_name: 'promqlExecQueue',
            },
            target: 'COUNT(_index){span_name=build-metadata-query}',
            metric_field: '_result_',
            datapoints: [
              [4, 1744936200000],
              [3, 1744936260000],
              [9, 1744936320000],
              [7, 1744936380000],
              [5, 1744936440000],
              [0, 1744936500000],
            ],
            alias: '_result_',
            type: 'bar',
            dimensions_translation: {},
            unit: '',
          },
          {
            dimensions: {
              span_name: 'promqlExecQueue',
            },
            target: 'COUNT(_index){span_name=promqlExecQueue',
            metric_field: '_result_',
            datapoints: [
              [3, 1744936200000],
              [3, 1744936260000],
              [3, 1744936320000],
              [3, 1744936380000],
              [4, 1744936440000],
              [0, 1744936500000],
            ],
            alias: '_result_',
            type: 'bar',
            dimensions_translation: {},
            unit: '',
          },
          {
            dimensions: {
              span_name: 'kubelet',
            },
            target: 'COUNT(_index){span_name=kubelet}',
            metric_field: '_result_',
            datapoints: [
              [51, 1744936200000],
              [18, 1744936260000],
              [44, 1744936320000],
              [41, 1744936380000],
              [23, 1744936440000],
              [0, 1744936500000],
            ],
            alias: '_result_',
            type: 'bar',
            dimensions_translation: {},
            unit: '',
          },
          {
            dimensions: {
              span_name: 'promqlSort',
            },
            target: 'COUNT(_index){span_name=promqlSort}',
            metric_field: '_result_',
            datapoints: [
              [0, 1744936200000],
              [0, 1744936260000],
              [1, 1744936320000],
              [0, 1744936380000],
              [1, 1744936440000],
              [0, 1744936500000],
            ],
            alias: '_result_',
            type: 'bar',
            dimensions_translation: {},
            unit: '',
          },
        ],
        metrics: [],
      });
    }, 500);
  });
};

export const getFieldTopK = (params, options?) => {
  return new Promise(resolve => {
    setTimeout(() => {
      console.log(params, options);
      const data =
        Math.random() < 0.5
          ? {
              field: 'apiVersion',
              total: 2143,
              distinct_count: 8,
              list: [
                {
                  value: 'v1',
                  alias: 'v1',
                  count: 1730,
                  proportions: 80.73,
                },
                {
                  value: 'apps/v1',
                  alias: 'apps/v1',
                  count: 331,
                  proportions: 15.45,
                },
                {
                  value: 'batch/v1',
                  alias: 'batch/v1',
                  count: 49,
                  proportions: 2.29,
                },
                {
                  value: 'batch/v1beta1',
                  alias: 'batch/v1beta1',
                  count: 21,
                  proportions: 0.98,
                },
                {
                  value: 'kyverno.io/v1',
                  alias: 'kyverno.io/v1',
                  count: 7,
                  proportions: 0.33,
                },
              ],
            }
          : {
              field: 'type',
              total: 2143,
              distinct_count: 2,
              list: [
                {
                  value: 'Normal',
                  alias: 'Normal',
                  count: 2119,
                  proportions: 98.88,
                },
                {
                  value: 'Warning',
                  alias: 'Warning',
                  count: 24,
                  proportions: 1.12,
                },
              ],
            };
      resolve(data);
    }, 1000);
  });
};
