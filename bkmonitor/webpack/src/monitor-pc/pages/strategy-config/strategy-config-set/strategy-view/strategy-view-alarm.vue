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
  <div class="strategy-view-alarm">
    <div class="alarm-title">图表标题</div>
    <div class="alarm-content-wrap">
      <div class="alarm-bar" />
      <div class="alarm-label mt10">
        <span
          v-for="(item, index) in labels"
          :key="index"
          class="alarm-label-item"
        >
          {{ item }}
        </span>
      </div>
      <div class="alarm-legend mt20">
        <div
          v-for="item in data.alarmAggregation"
          :key="item.level"
          class="alarm-legend-item"
        >
          <span
            class="legend-icon"
            :style="{ background: levelMap[item.level] }"
          />
          <span class="legend-name">{{ item.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';

import dayjs from 'dayjs';

import { handleTimeRange } from '../../../../utils/index';

@Component({ name: 'strategy-view-alarm' })
export default class StrategyViewAlarm extends Vue {
  private data = {
    range: 1 * 60 * 60 * 1000,
    alarmAggregation: [],
  };
  private levelMap = {
    1: '#ea3636',
    2: '#ff9c01',
    3: '#ffde3a',
    4: '#7dccac',
    5: '#d8d8d8',
    6: '#979ba5',
  };
  private labelNums = 6;

  private get labels() {
    const { startTime, endTime } = handleTimeRange(this.data.range);
    const step = (endTime - startTime) / this.labelNums;

    const labels = [];
    let curTime = startTime;
    while (curTime <= endTime) {
      curTime = curTime + step;
      labels.push(dayjs.tz(curTime * 1000).format('hh:mm'));
    }
    return labels;
  }

  private created() {
    this.data.alarmAggregation = [
      {
        level: 1,
        name: this.$t('致命'),
      },
      {
        level: 2,
        name: this.$t('预警'),
      },
      {
        level: 3,
        name: this.$t('提醒'),
      },
      {
        level: 4,
        name: this.$t('正常'),
      },
      {
        level: 5,
        name: this.$t('无数据'),
      },
      {
        level: 6,
        name: this.$t('信号屏蔽'),
      },
    ];
  }
}
</script>
<style lang="scss" scoped>
.strategy-view-alarm {
  .alarm-title {
    font-weight: 700;
  }

  .alarm-content-wrap {
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    padding: 0 22px;

    .alarm-bar {
      height: 16px;
      background: red;
    }

    .alarm-label {
      display: flex;
      justify-content: space-between;
    }

    .alarm-legend {
      display: flex;
      justify-content: center;

      &-item {
        display: flex;
        align-items: center;
        margin-right: 8px;

        .legend-icon {
          display: inline-block;
          width: 12px;
          height: 12px;
          margin-right: 3px;
        }
      }
    }
  }
}
</style>
