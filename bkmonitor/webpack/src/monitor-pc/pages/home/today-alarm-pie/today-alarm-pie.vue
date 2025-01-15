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
  <section class="today-alarm">
    <div
      ref="todayAlarm"
      class="today-alarm__chart"
    >
      <span
        v-if="!seriesData.length || !seriesData.some(item => item.count > 0)"
        class="alarm-title"
        >{{ $t('未恢复告警分布') }}</span
      >
      <monitor-pie-echart
        v-if="seriesData.length && seriesData.some(item => item.count > 0)"
        :series="series"
        :title="$t('未恢复告警分布')"
        chart-type="pie"
        :options="{
          legend: { show: false },
          tool: {
            show: true,
            moreShow: false,
          },
        }"
        height="320"
        @chart-click="handlePieItemClick"
      >
        <div
          slot="chartCenter"
          class="slot-center"
          @click="unrecoveredClickHandle"
        >
          <bk-popover :content="$t('查看告警列表')">
            <div class="alarm-num">
              {{ unrecoveredCount }}
            </div>
          </bk-popover>
        </div>
      </monitor-pie-echart>
      <div
        v-else
        class="no-data"
      >
        <div class="no-data-desc">
          {{ $t('告警空空，一身轻松') }}
        </div>
      </div>
    </div>
    <div class="today-alarm__footer">
      <div
        class="item"
        @click="itemClickHandle(1)"
      >
        <h3 class="serious">
          {{ seriesData.length ? seriesData.find(item => item.level === 1).count : 0 }}
        </h3>
        <div>{{ $t('致命') }}</div>
      </div>
      <div
        class="item"
        @click="itemClickHandle(2)"
      >
        <h3 class="normal">
          {{ seriesData.length ? seriesData.find(item => item.level === 2).count : 0 }}
        </h3>
        <div>{{ $t('预警') }}</div>
      </div>
      <div
        class="item"
        @click="itemClickHandle(3)"
      >
        <h3 class="slight">
          {{ seriesData.length ? seriesData.find(item => item.level === 3).count : 0 }}
        </h3>
        <div>{{ $t('提醒') }}</div>
      </div>
    </div>
  </section>
</template>

<script>
import MonitorPieEchart from 'monitor-ui/monitor-echarts/monitor-echarts';

import { gotoPageMixin } from '../../../common/mixins';

export default {
  name: 'TodayAlarmPie',
  components: {
    MonitorPieEchart,
  },
  mixins: [gotoPageMixin],
  props: {
    seriesData: {
      type: Array,
      required: true,
    },
    unrecoveredCount: {
      type: [String, Number],
      required: true,
    },
  },
  data() {
    return {
      seriesDataMap: {
        1: {
          name: this.$t('致命'),
          color: '#EA3636',
        },
        2: {
          name: this.$t('预警'),
          color: '#FF9C01',
        },
        3: {
          name: this.$t('提醒'),
          color: '#FFD000',
        },
      },
    };
  },
  computed: {
    series() {
      return [
        {
          label: { show: false },
          cursor: 'pointer',
          data: this.seriesData.map(item => {
            const seriesMapData = this.seriesDataMap[item.level];
            return {
              value: item.count,
              name: seriesMapData.name,
              level: item.level,
              itemStyle: {
                color: seriesMapData.color,
              },
              tooltip: {
                formatter: () => `<span style="color:${seriesMapData.color}">\u25CF</span> <b> ${seriesMapData.name}</b>
              <br/>${this.$t('告警数量')}: <b>${item.count}</b><br/>`,
                textStyle: {
                  fontSize: 12,
                },
              },
            };
          }),
        },
      ];
    },
  },
  methods: {
    handlePieItemClick(params) {
      params?.data && this.itemClickHandle(params.data.level);
    },
    itemClickHandle(level) {
      this.$router.push({
        name: 'event-center',
        query: {
          data: JSON.stringify({
            condition: { severity: [level] },
            activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          }),
        },
      });
    },
    unrecoveredClickHandle() {
      this.$router.push({
        name: 'event-center',
        query: {
          data: JSON.stringify({
            activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          }),
        },
      });
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.today-alarm {
  &__chart {
    position: relative;
    min-width: 348px;
    min-height: 330px;

    .alarm-title {
      float: left;
      height: 19px;
      margin: 20px 0px 0px 18px;
      font-size: 14px;
      font-weight: bold;
      line-height: 19px;
      color: #63656e;
    }

    .slot-center {
      @include hover();

      .alarm-num {
        height: 30px;
        font-size: 24px;
        font-weight: 600;
        line-height: 30px;
        color: #313238;
        text-align: center;
      }

      .alarm-name {
        height: 19px;
        font-size: $fontSmSize;
        line-height: 19px;
        color: #3a84ff;
      }
    }

    .no-data {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 220px;
      height: 220px;
      text-align: center;
      background: #fff;
      background-image: url('../../../static/images/svg/no-alarm.svg');
      background-repeat: no-repeat;
      background-size: contain;
      transform: translate3d(-110px, -120px, 0);

      &-desc {
        position: absolute;
        bottom: -40px;
        width: 100%;
        font-size: 20px;
        font-weight: 300;
        color: $defaultFontColor;
        text-align: center;
      }

      .alarm-num {
        height: 45px;
        font-size: 32px;
        font-weight: 600;
        line-height: 45px;
        color: #313238;
        text-align: center;
      }

      .alarm-name {
        height: 19px;
        font-size: $fontSmSize;
        line-height: 19px;
        color: #3a84ff;
      }
    }
  }

  &__footer {
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    border-top: 1px solid $defaultBorderColor;

    .item {
      display: inline-block;
      flex: 1;
      height: 72px;
      border-right: 1px solid $defaultBorderColor;

      &:hover {
        cursor: pointer;
        background: #fafbfd;
      }

      h3 {
        height: 33px;
        margin: 7px 0 0 0;
        font-size: 24px;
        font-weight: 600;
        line-height: 33px;
        text-align: center;
      }

      div {
        font-size: $fontSmSize;
        color: #63656e;
        text-align: center;
      }

      .serious {
        color: $deadlyAlarmColor;
      }

      .normal {
        color: $warningAlarmColor;
      }

      .slight {
        color: $remindAlarmColor;
      }
    }

    :nth-child(3) {
      border-right: 0;
    }
  }
}
</style>
