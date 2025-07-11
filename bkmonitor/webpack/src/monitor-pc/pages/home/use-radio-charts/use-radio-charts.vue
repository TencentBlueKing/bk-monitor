<!--
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
-->
<template>
  <panel-card
    class="use-radio-charts"
    :title="$t('主机性能状态分布')"
  >
    <div
      class="sub-title"
      slot="title"
    >
      {{ $t('（数据缓存2mins）') }}
    </div>
    <div
      v-if="options.length"
      class="radio-content"
    >
      <template v-for="(optionList, index) in options">
        <div
          class="radio-content-wrap"
          :key="index"
        >
          <div
            v-for="(option, key) in optionList"
            class="chart-item"
            :class="{ 'item-border': index === 0, 'border-left': !(key % 2) }"
            :key="key"
          >
            <monitor-pie-echart
              class="chart-set"
              :height="200"
              :options="option"
              chart-type="pie"
              @chart-click="e => handleChartClick(e, option)"
            >
              <div
                class="slot-center"
                slot="chartCenter"
              >
                <div
                  style="width: 56px; font-size: 14px; text-align: center"
                  class="slot-center-name"
                >
                  {{ option.name }}
                </div>
              </div>
            </monitor-pie-echart>
          </div>
        </div>
      </template>
    </div>
  </panel-card>
</template>

<script>
import MonitorPieEchart from 'monitor-ui/monitor-echarts/monitor-echarts';

import { gotoPageMixin } from '../../../common/mixins';
import PanelCard from '../components/panel-card/panel-card';

export default {
  name: 'UseRadioCharts',
  components: {
    PanelCard,
    MonitorPieEchart,
  },
  mixins: [gotoPageMixin],
  props: {
    series: {
      type: Array,
      required: true,
    },
    showExample: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      colorMaps: {
        '0 ~ 20%': '#a3c5fd',
        '20 ~ 40%': '#699df4',
        '40 ~ 60%': '#3a84ff',
        '60 ~ 80%': '#ffb848',
        '80 ~ 100%': '#ff9c01',
      },
      defaultSerise: [
        {
          data: [
            {
              name: '0 ~ 20%',
              y: 3,
            },
            {
              name: '20 ~ 40%',
              y: 4,
            },
            {
              name: '40 ~ 60%',
              y: 5,
            },
            {
              name: '60 ~ 80%',
              y: 6,
            },
            {
              name: '80 ~ 100%',
              y: 7,
            },
          ],
          metric_id: 'system.cpu_summary.usage',
          name: 'CPU',
        },
        {
          data: [
            {
              name: '0 ~ 20%',
              y: 3,
            },
            {
              name: '20 ~ 40%',
              y: 4,
            },
            {
              name: '40 ~ 60%',
              y: 5,
            },
            {
              name: '60 ~ 80%',
              y: 6,
            },
            {
              name: '80 ~ 100%',
              y: 7,
            },
          ],
          metric_id: 'system.cpu_summary.usage',
          name: this.$t('应用内存使用率'),
        },
        {
          data: [
            {
              name: '0 ~ 20%',
              y: 3,
            },
            {
              name: '20 ~ 40%',
              y: 4,
            },
            {
              name: '40 ~ 60%',
              y: 5,
            },
            {
              name: '60 ~ 80%',
              y: 6,
            },
            {
              name: '80 ~ 100%',
              y: 7,
            },
          ],
          metric_id: 'system.cpu_summary.usage',
          name: this.$t('磁盘空间使用率'),
        },
        {
          data: [
            {
              name: '0 ~ 20%',
              y: 3,
            },
            {
              name: '20 ~ 40%',
              y: 4,
            },
            {
              name: '40 ~ 60%',
              y: 5,
            },
            {
              name: '60 ~ 80%',
              y: 6,
            },
            {
              name: '80 ~ 100%',
              y: 7,
            },
          ],
          metric_id: 'system.cpu_summary.usage',
          name: this.$t('磁盘I/O利用率'),
        },
      ],
      chartIdMap: {
        [this.$t('CPU使用率')]: 'cpu_usage',
        [this.$t('应用内存使用率')]: 'mem_usage',
        [this.$t('磁盘I/O利用率')]: 'io_util',
        [this.$t('磁盘空间使用率')]: 'disk_in_use',
      },
    };
  },
  computed: {
    options() {
      let data = this.defaultSerise;
      if (!this.showExample) {
        data = this.series;
      }
      const options = data.map(item => {
        const itemData = item.data.slice();
        return {
          name: item.name,
          tooltip: {
            trigger: 'item',
          },
          legend: {
            show: true,
            formatter: ['{a|{name}}'].join('\n'),
            right: 20,
            top: 48,
            width: 300,
            icon: 'circle',
            padding: 0,
            textStyle: {
              rich: {
                a: {
                  width: 100,
                  color: !itemData.some(set => set.y > 0) ? '#cccccc' : '#63656E',
                  lineHeight: 25,
                },
              },
            },
          },
          series: [
            {
              type: 'pie',
              radius: ['55%', '70%'],
              left: -260,
              avoidLabelOverlap: false,
              label: {
                show: false,
                position: 'center',
              },
              labelLine: {
                show: false,
              },
              data: itemData
                .sort((a, b) => +a.name.slice(0, 1) - +b.name.slice(0, 1))
                .map(set => {
                  const itemColor = Math.abs(set.y) > 0 ? this.colorMaps[set.name] : '#cccccc';
                  return {
                    name: set.name,
                    value: set.y,
                    ...set,
                    itemStyle: {
                      color: itemColor,
                    },
                    tooltip: {
                      formatter: () => `<span style="color:${itemColor}">\u25CF</span> <b> ${set.name}</b>
                  <br/>${item.name}: <b><span style="color:#FFFFFF">${set.y}</span>${this.$t('台')}</b><br/>`,
                      textStyle: {
                        fontSize: 12,
                      },
                    },
                  };
                }),
            },
          ],
        };
      });
      return options.reduce(
        (pre, cur, index) => {
          index % 2 ? pre[0].push(cur) : pre[1].push(cur);
          return pre;
        },
        [[], []]
      );
    },
  },
  methods: {
    gotoPerformace(target) {
      // agent状态默认为正常
      this.$router.push({
        name: 'performance',
        params: {
          search: [
            target,
            {
              id: 'status',
              value: [0],
            },
          ],
        },
      });
    },
    handleChartClick(params, option) {
      if (params.data.ip_list?.length) {
        const scopes = params.name.replace(/\s+/g, '').replace(/%/g, '').split('~');
        this.gotoPerformace({
          id: this.chartIdMap[option.name],
          value: [
            {
              condition: '>=',
              value: scopes[0],
            },
            {
              condition: '<=',
              value: scopes[1],
            },
          ],
        });
      }
      return false;
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.use-radio-charts {
  .sub-title {
    font-size: 12px;
    line-height: 20px;
    color: #999;
  }

  .content {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-around;

    &-chart {
      position: relative;
      z-index: 1;
      width: 40%;
      padding: 20px 0;

      @media only screen and (max-width: 1882px) {
        .slot-center {
          left: 97px;
        }
      }

      .slot-center {
        position: absolute;
        top: 55px;
        left: 47px;
        z-index: 1;
        width: 56px;
        height: 38px;
        font-size: $fontSmSize;
        line-height: 19px;
        color: $defaultFontColor;
        text-align: center;
      }

      &-no-data {
        position: absolute;
        top: 30px;
        left: 32px;
        z-index: 888;
        width: 125px;
        height: 125px;
        background: #fff;
        border: 12.5px solid $defaultBorderColor;
        border-radius: 100%;

        .name {
          position: absolute;
          top: 31px;
          left: 22px;
          width: 56px;
          height: 38px;
          font-size: $fontSmSize;
          line-height: 19px;
          color: $defaultFontColor;
          text-align: center;
        }
      }
    }

    &-border {
      width: 0px;
      height: 160px;
      border: 0.5px solid #ddd;
    }

    .border-b {
      border-bottom: 1px solid #ddd;
    }
  }

  .radio-content {
    display: flex;
    flex-direction: column;
    margin: 0 -20px;

    &-wrap {
      display: flex;
      align-items: center;

      .chart-item {
        position: relative;
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: center;

        &.item-border {
          &::after {
            position: absolute;
            right: 60px;
            bottom: 0px;
            left: 60px;
            height: 1px;
            content: ' ';
            background: rgb(221, 221, 221);
          }
        }

        &.border-left {
          &::before {
            position: absolute;
            top: 20px;
            right: 0px;
            bottom: 20px;
            z-index: 99;
            width: 1px;
            content: ' ';
            background: #ddd;
          }
        }

        .chart-set {
          position: relative;
          flex: 0 0 516px;
          width: 516px;
          min-width: 516px;
          max-width: 516px;

          .slot-center {
            position: absolute;
            left: -157px;
          }
        }
      }
    }
  }
}
</style>
