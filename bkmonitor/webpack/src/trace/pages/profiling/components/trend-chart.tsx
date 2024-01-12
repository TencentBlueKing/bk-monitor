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
import { defineComponent, ref } from 'vue';
import { Collapse, Radio } from 'bkui-vue';

import TimeSeries from '../../../plugins/charts/time-series/time-series';
import { PanelModel } from '../../../plugins/typings';

import './trend-chart.scss';

export default defineComponent({
  name: 'TrendChart',
  props: {
    content: {
      type: String,
      default: ''
    }
  },
  setup() {
    const collapse = ref(true);
    const panel = new PanelModel({
      id: 6,
      title: '响应耗时',
      gridPos: {
        x: 16,
        y: 16,
        w: 8,
        h: 4
      },
      type: 'graph',
      targets: [
        {
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
          datasource: 'time_series',
          alias: 'MAX',
          data: {
            expression: 'C',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '2_bkapm_metric_datalink_bkop.__default__',
                metrics: [
                  {
                    field: 'bk_apm_duration_max',
                    method: 'MAX',
                    alias: 'C'
                  }
                ],
                group_by: [],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {},
                functions: []
              }
            ]
          }
        },
        {
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
          datasource: 'time_series',
          alias: 'P99',
          data: {
            expression: 'B',
            query_configs: [
              {
                data_source_label: 'custom',
                data_type_label: 'time_series',
                table: '2_bkapm_metric_datalink_bkop.__default__',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'AVG',
                    alias: 'B'
                  }
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {},
                functions: [
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.99
                      }
                    ]
                  }
                ]
              }
            ]
          }
        },
        {
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
          datasource: 'time_series',
          alias: 'P95',
          data: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                table: '2_bkapm_metric_datalink_bkop.__default__',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'AVG',
                    alias: 'A'
                  }
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {},
                functions: [
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.95
                      }
                    ]
                  }
                ]
              }
            ]
          }
        },
        {
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
          datasource: 'time_series',
          alias: 'P50',
          data: {
            expression: 'A',
            query_configs: [
              {
                data_source_label: 'custom',
                table: '2_bkapm_metric_datalink_bkop.__default__',
                data_type_label: 'time_series',
                metrics: [
                  {
                    field: 'bk_apm_duration_bucket',
                    method: 'AVG',
                    alias: 'A'
                  }
                ],
                group_by: ['le'],
                display: true,
                where: [],
                interval_unit: 's',
                time_field: 'time',
                filter_dict: {},
                functions: [
                  {
                    id: 'histogram_quantile',
                    params: [
                      {
                        id: 'scalar',
                        value: 0.5
                      }
                    ]
                  }
                ]
              }
            ]
          }
        }
      ]
    });
    function handleCollapseChange(v) {
      collapse.value = v;
    }
    return {
      panel,
      collapse,
      handleCollapseChange
    };
  },
  render() {
    return (
      <div class='trend-chart'>
        <Collapse.CollapsePanel
          modelValue={this.collapse}
          onUpdate:modelValue={this.handleCollapseChange}
          v-slots={{
            content: () => (
              <div class='trend-chart-wrap'>
                {this.collapse && (
                  <TimeSeries
                    panel={this.panel}
                    showChartHeader={false}
                    showHeaderMoreTool={false}
                  />
                )}
              </div>
            )
          }}
        >
          <div
            class='trend-chart-header'
            onClick={e => e.stopPropagation()}
          >
            <Radio.Group
              type='capsule'
              modelValue='all'
            >
              <Radio.Button label='all'>{this.$t('总趋势')}</Radio.Button>
              <Radio.Button label='trace'>{this.$t('Trace 数据')}</Radio.Button>
            </Radio.Group>
          </div>
        </Collapse.CollapsePanel>
      </div>
    );
  }
});
