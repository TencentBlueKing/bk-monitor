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
  <DateRangePicker
    :class="['king-date-picker', { daily: isDaily, 'has-shortcut': shortText && !isShowDatePicker }]"
    :clearable="false"
    allow-input
    :format="isDaily ? 'YYYY-MM-DD' : 'YYYY-MM-DD HH:mm:ss'"
    :value-type="isDaily ? 'YYYY-MM-DD' : 'YYYY-MM-DD HH:mm:ss'"
    :enable-time-picker="pickerType === 'datetimerange'"
    :range-input-props="shortText && !isShowDatePicker ? { inputProps: [{ value: shortText }, { value: '' }] } : {}"
    :popup-props="{ placement: isDaily ? 'bottom-right' : 'bottom-left', onVisibleChange: handleOpenChange }"
    :presets="presets"
    presets-placement="left"
    :value="datePickerValue"
    @change="handleDateChange"
    @pick="pickedDates += 1"
    @confirm="handleConfirm"
    @preset-click="handlePresetClick"
  />
</template>

<script>
  import { DateRangePicker } from 'tdesign-vue-next';

  export default {
    components: { DateRangePicker },
  emits: ["update:date-picker-value","update:datePickerValue","update:time-range","update:timeRange","date-picker-change","datePickerChange"],

    props: {
      isDaily: {
        type: Boolean,
        default: false,
      },
      timeRange: {
        // 显示自定义时间范围，customized 显示组件默认选择范围
        type: String,
        required: true,
      },
      datePickerValue: {
        type: Array,
        required: true,
      },
      pickerType: {
        type: String,
        default: 'datetimerange',
      },
    },
    data() {
      return {
        isShowDatePicker: false,
        pickedDates: 0,
        dateHistory: {}, // 日期组件历史值，每次开启记录，关闭比较，变化就搜索
        shortTextEnum: this.isDaily
          ? {
              customized: '',
              '7d': this.$t('近{n}天', { n: 7 }),
              '14d': this.$t('近{n}天', { n: 14 }),
              '30d': this.$t('近{n}天', { n: 30 }),
              [this.$t('近{n}天', { n: 7 })]: '7d',
              [this.$t('近{n}天', { n: 14 })]: '14d',
              [this.$t('近{n}天', { n: 30 })]: '30d',
            }
          : {
              customized: '',
              '5s': this.$t('近 5 秒'),
              '5m': this.$t('近 5 分钟'),
              '15m': this.$t('近 15 分钟'),
              '30m': this.$t('近 30 分钟'),
              '1h': this.$t('近 1 小时'),
              '4h': this.$t('近 4 小时'),
              '12h': this.$t('近 12 小时'),
              '1d': this.$t('近 1 天'),
              [this.$t('近 5 秒')]: '5s',
              [this.$t('近 5 分钟')]: '5m',
              [this.$t('近 15 分钟')]: '15m',
              [this.$t('近 30 分钟')]: '30m',
              [this.$t('近 1 小时')]: '1h',
              [this.$t('近 4 小时')]: '4h',
              [this.$t('近 12 小时')]: '12h',
              [this.$t('近 1 天')]: '1d',
            },
        shortcuts: this.isDaily
          ? [
              {
                text: this.$t('近{n}天', { n: 7 }),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 7 * 86400 * 1000);
                  return [start, end];
                },
              },
              {
                text: this.$t('近{n}天', { n: 14 }),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 14 * 86400 * 1000);
                  return [start, end];
                },
              },
              {
                text: this.$t('近{n}天', { n: 30 }),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 30 * 86400 * 1000);
                  return [start, end];
                },
              },
            ]
          : [
              {
                text: this.$t('近 5 秒'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 5 * 1000);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 5 分钟'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 5 * 60);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 15 分钟'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 15 * 60);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 30 分钟'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 30 * 60);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 1 小时'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 60 * 60);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 4 小时'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 60 * 60 * 4);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 12 小时'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 60 * 60 * 12);
                  return [start, end];
                },
              },
              {
                text: this.$t('近 1 天'),
                value() {
                  const end = new Date();
                  const start = new Date();
                  start.setTime(start.getTime() - 1000 * 60 * 60 * 24);
                  return [start, end];
                },
              },
            ],
      };
    },
    computed: {
      presets() {
        return Object.fromEntries(this.shortcuts.map(item => [item.text, item.value]));
      },
      shortText() {
        return this.shortTextEnum[this.timeRange];
      },
    },
    methods: {
      handleDateChange(date, context) {
        this.$emit('update:date-picker-value', date);
        if (context.trigger !== 'preset') this.$emit('update:time-range', 'customized');
        // 原生组件完成选择后会自行关闭弹层，同步执行关闭后的刷新逻辑。
        if (context.trigger === 'enter' || (context.trigger === 'pick' && this.pickedDates >= 2)) {
          this.handleOpenChange(false);
        }
      },
      handlePresetClick({ preset }) {
        this.$emit('update:time-range', this.shortTextEnum[Object.keys(preset)[0]]);
        this.handleOpenChange(false);
      },
      handleConfirm({ partial }) {
        if (partial === 'end') this.handleOpenChange(false);
      },
      handleOpenChange(state) {
        if (state === this.isShowDatePicker) return;
        this.isShowDatePicker = state;
        if (state) this.pickedDates = 0;
        // 因为事件可能会在日期数据变化前触发，所以需要等数据更新后再处理
        this.$nextTick(() => {
          if (state === true) {
            this.dateHistory = {
              timeRange: this.timeRange,
              time0: this.datePickerValue[0],
              time1: this.datePickerValue[1],
            };
          } else {
            if (this.datePickerValue.length !== 2 || this.datePickerValue.some(time => !time)) return;
            // 关闭日期组件，检查值是否变化
            const { timeRange, time0, time1 } = this.dateHistory;
            if (this.timeRange !== 'customized') {
              // 快捷键模式
              if (timeRange !== this.timeRange) {
                this.$emit('date-picker-change');
              }
            } else {
              // 正常模式
              const [newTime0, newTime1] = this.datePickerValue;
              if (time0 !== newTime0 || time1 !== newTime1) {
                this.$emit('date-picker-change');
              }
            }
          }
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
  .king-date-picker {
    width: 320px;
    max-width: 100%;
    min-width: 0;

    &.daily {
      width: 240px;
    }

    &.has-shortcut {
      :deep(.t-range-input__inner-right),
      :deep(.t-range-input__inner-separator) {
        display: none;
      }
    }
  }
</style>
