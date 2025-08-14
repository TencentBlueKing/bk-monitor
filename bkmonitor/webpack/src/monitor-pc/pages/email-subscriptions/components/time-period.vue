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
  <div class="time-period-wrap">
    <bk-radio-group
      v-model="typeValue"
      class="radio-group"
      @change="getValue"
    >
      <bk-radio
        v-for="(item, index) in radioMap"
        :key="index"
        class="radio-item"
        :value="item.id"
      >
        {{ item.name }}
      </bk-radio>
    </bk-radio-group>
    <div class="time-select">
      <!-- 按小时 -->
      <bk-select
        v-if="typeValue === 5"
        key="hour-selector"
        v-model="hour"
        class="hour"
        :clearable="false"
        style="width: 200px"
        @change="getValue"
      >
        <bk-option
          v-for="item in hourList"
          :id="item.id"
          :key="'hour' + item.id"
          :name="`${item.name}${$t('小时')}`"
        />
      </bk-select>
      <!-- 每周几 -->
      <bk-select
        v-if="typeValue === 3"
        key="week-selector"
        v-model="week"
        class="week"
        :clearable="false"
        multiple
        style="width: 200px"
        @change="getValue"
      >
        <bk-option
          v-for="item in weekList"
          :key="'week' + item.id"
          v-bind="item"
        />
      </bk-select>
      <!-- 每月几号 -->
      <bk-select
        v-if="typeValue === 4"
        key="month-selector"
        v-model="month"
        class="month"
        multiple
        :clearable="false"
        style="width: 200px"
        @change="getValue"
      >
        <bk-option
          v-for="item in 31"
          :id="item"
          :key="item"
          :name="item + '号'"
        />
      </bk-select>
      <!-- 时间选择 -->
      <bk-time-picker
        v-if="[2, 3, 4].includes(typeValue)"
        v-model="dayTime"
        style="width: 168px"
        :clearable="false"
        :placeholder="'选择时间'"
        @change="v => getValue(v, 'time')"
      />
      <!-- 是否包含周末 -->
      <!-- <bk-checkbox-group
        style="width: 168px;"
        v-if="typeValue === 2"
        v-model="includeWeekend"
        @change="getValue"> -->
      <bk-checkbox
        v-if="typeValue === 2"
        v-model="includeWeekend"
        v-en-style="'width: 160px'"
        style="font-size: 12px"
        @change="getValue"
        >{{ $t('包含周末') }}</bk-checkbox
      >
      <!-- </bk-checkbox-group> -->
      <!-- 仅一次 -->
      <bk-date-picker
        v-if="typeValue === 1"
        v-model="onceTime"
        style="width: 168px"
        :clearable="false"
        :type="'datetime'"
        :options="datePickerOptions"
        @change="v => getValue(v, 'datetime')"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Model, Vue, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';

import type { EType, IRadioMap, ITimePeriodValue } from '../types';
/** 按天频率 包含周末 */
const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
/** 按天频率 不包含周末 */
const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];
/**
 * 时间周期组件
 */
@Component({
  name: 'time-period',
})
export default class TimePeriod extends Vue {
  @Model('updateValue', {
    default: () => ({
      type: 2,
      runTime: '09:30:20',
      dayList: [1],
      weekList: [1],
    }),
    type: Object,
  })
  value: ITimePeriodValue;

  // 时间数据
  typeValue: EType = 2;
  weekList: IRadioMap[] = [
    { name: window.i18n.t('星期一'), id: 1 },
    { name: window.i18n.t('星期二'), id: 2 },
    { name: window.i18n.t('星期三'), id: 3 },
    { name: window.i18n.t('星期四'), id: 4 },
    { name: window.i18n.t('星期五'), id: 5 },
    { name: window.i18n.t('星期六'), id: 6 },
    { name: window.i18n.t('星期日'), id: 7 },
  ];
  week: number[] = [1];
  month: number[] = [1];
  hour = 0.5;
  hourList = [
    { name: 0.5, id: 0.5 },
    { name: 1, id: 1 },
    { name: 2, id: 2 },
    { name: 6, id: 6 },
    { name: 12, id: 12 },
  ];
  //   dayTime: Date | string = new Date()
  dayTime: Date | string = dayjs.tz(new Date()).format('HH:mm:ss');

  includeWeekend = true;
  onceTime: Date = new Date();

  // datePicker配置
  datePickerOptions: any = {
    disabledDate: (v: string) => {
      const item: number = +new Date(v);
      const cur: Date = new Date();
      const start: number = +new Date(cur.getFullYear(), 0, 1, 0, 0, 0, 0);
      const end: number = +new Date(cur.getFullYear(), 11, 31, 23, 59, 59, 0);
      return !(item >= start && item <= end);
    },
  };

  // 时间类型选择
  radioMap: IRadioMap[] = [
    { id: 5, name: window.i18n.t('按小时') },
    { id: 2, name: window.i18n.t('按天') },
    { id: 3, name: window.i18n.t('按周') },
    { id: 4, name: window.i18n.t('按月') },
    { id: 1, name: window.i18n.t('仅一次') },
  ];

  // 值更新
  @Watch('value', { immediate: true })
  valueChage(val: ITimePeriodValue, oldVal: ITimePeriodValue): void {
    if (JSON.stringify(val) !== JSON.stringify(oldVal)) {
      // 回显
      this.displayBack(val);
      this.getValue();
    }
  }

  /**
   * 数据回显展示
   * @params val 外部传入数据
   */
  displayBack(val: ITimePeriodValue) {
    if (!val) return;
    const { type, runTime, weekList, dayList, hour } = val;
    this.typeValue = type;
    if ([2, 3, 4].includes(type)) {
      this.dayTime = runTime;
    }
    switch (type) {
      case 1: // 仅一次
        this.onceTime = new Date(runTime);
        break;
      case 2: // 按天
        this.includeWeekend = INCLUDES_WEEKEND.every(item => weekList.includes(item));
        break;
      case 3: // 按周
        this.week = weekList;
        break;
      case 4: // 按月
        this.month = dayList;
        break;
      case 5: // 按小时
        this.hour = hour;
    }
  }

  /**
   * 双向绑定的值更新
   */
  @Emit('updateValue')
  getValue(v?, type?: 'datetime' | 'time'): ITimePeriodValue {
    const value: ITimePeriodValue = {
      type: this.typeValue,
      runTime: '',
      dayList: [],
      weekList: [],
      hour: 0,
    };
    if ([2, 3, 4].includes(this.typeValue)) value.runTime = `${type === 'time' ? v : this.dayTime}`;
    switch (this.typeValue) {
      case 1: // 仅一次
        value.runTime = dayjs.tz(type === 'datetime' ? v : this.onceTime).format('YYYY-MM-DD HH:mm:ss');
        break;
      case 2: // 按天
        // value.runTime = this.dayTime
        value.weekList = this.includeWeekend ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND;
        break;
      case 3: // 按周
        value.weekList = this.week;
        break;
      case 4: // 按月
        value.dayList = this.month;
        break;
      case 5: // 按小时
        value.hour = this.hour;
        break;
    }
    return value;
  }
}
</script>

<style lang="scss" scoped>
.time-period-wrap {
  .radio-group {
    .radio-item {
      font-size: 12px;

      &:not(:last-child) {
        margin-right: 54px;
      }
    }
  }

  .time-select {
    display: flex;
    align-items: center;
    width: 300px;
    margin-top: 10px;

    .week,
    .month {
      display: inline-block;
    }

    & > :not(:last-child) {
      margin-right: 8px;
    }
  }
}
</style>
