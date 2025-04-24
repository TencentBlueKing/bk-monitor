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

import { defineComponent, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { useDebounceFn } from '@vueuse/core';
import { Input, Slider } from 'bkui-vue';

import { formatDuration } from '../trace-view/utils/date';
import { TIME_CONSUMING_EMITS, TIME_CONSUMING_PROPS } from './typing';
import { TIME_CONSUMING_REGEXP } from './utils';

import './time-consuming.scss';

const DEFAULT_SLIDER_VALUE = {
  curValue: [0, 1000], // 当前选择范围
  scaleRange: [0, 0], // 刻度范围
  min: 0, // 最小值
  max: 1000, // 最大值
  step: 10, // 步长
  disable: false,
};

export default defineComponent({
  name: 'TimeConsuming',
  props: TIME_CONSUMING_PROPS,
  emits: TIME_CONSUMING_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const durationSlider = shallowRef({ ...DEFAULT_SLIDER_VALUE });
    const startValue = shallowRef('');
    const endValue = shallowRef('');
    const startError = shallowRef(false);
    const endError = shallowRef(false);
    const errMsg = shallowRef('');

    watch(
      () => props.value,
      val => {
        if (val.length > 1) {
          const [start, end] = val;
          startValue.value = `${Number(start) / 1000}ms`;
          endValue.value = `${Number(end) / 1000}ms`;
          handleSetSlider(false);
        }
      },
      { immediate: true }
    );

    const handleChangeDebounce = useDebounceFn(() => {
      const value = durationSlider.value.curValue.map(val => Number(val * 1000));
      emit('change', value);
    }, 300);

    function handleInputChange(val: string, type: 'end' | 'start') {
      const isError = !TIME_CONSUMING_REGEXP.test(val);
      if (type === 'start') {
        startError.value = isError;
      } else {
        endError.value = isError;
      }
      if (!startError.value && !endError.value) {
        errMsg.value = '';
        if (startValue.value.trim() !== '' && endValue.value.trim() !== '') {
          // 起始时间均有值
          handleSetSlider();
        }
      } else if (!startValue.value && !endValue.value) {
        errMsg.value = '';
        startError.value = false;
        endError.value = false;
        durationSlider.value = { ...DEFAULT_SLIDER_VALUE };
        emit('change', null);
      } else {
        errMsg.value = t('单位仅支持ns, μs, ms, s, m, h, d');
      }
    }

    function handleSetSlider(isUpdate = true) {
      const start = formatToMs(startValue.value);
      const end = formatToMs(endValue.value);
      if (start > end) {
        // 当最小耗时大于最大耗时
        errMsg.value = t('最小耗时不能大于最大耗时，');
      } else {
        Object.assign(durationSlider.value, {
          curValue: [start, end],
          min: start,
          max: end,
          step: Math.abs(start - end) / 100,
          disable: start === end,
        });
        errMsg.value = '';
        isUpdate && handleChangeDebounce();
      }
    }
    /** 将输入框内容转化为 ms 单位 */
    function formatToMs(str: string) {
      let totalMs = 0;
      const unitMap = {
        ns: 1 / 10 ** 6,
        μs: 1 / 10 ** 3,
        ms: 1,
        s: 10 ** 3,
        m: 10 ** 3 * 60,
        h: 10 ** 3 * 3600,
        d: 10 ** 3 * 3600 * 24,
      };
      for (const part of str.split(' ')) {
        const parseStr = part.split(/(ns|μs|ms|s|m|h|d)$/);
        const [value, unit] = parseStr;
        totalMs += Number(value) * (unitMap[unit] || 0);
      }
      return totalMs;
    }

    function handleRangeChange(value: number[]) {
      const [start, end] = value;
      // 默认不赋值 解决组件api初始化问题
      if (startValue.value === '' && endValue.value === '' && start === 0 && end === 1000) return;

      handleSliderChange(value);
    }

    function handleSliderChange(rangeValue: number[] = []) {
      const [start, end] = rangeValue;
      startValue.value = formatDuration(start * 1000) === '0μs' ? '0ns' : formatDuration(start * 1000);
      endValue.value = formatDuration(end * 1000) === '0μs' ? '0ns' : formatDuration(end * 1000);
      startError.value = false;
      endError.value = false;
      errMsg.value = '';
    }

    return {
      startValue,
      endValue,
      durationSlider,
      startError,
      endError,
      handleInputChange,
      handleChangeDebounce,
      handleRangeChange,
    };
  },
  render() {
    return (
      <div class={['time-consuming-component', this.styleType ? this.styleType : 'default']}>
        {this.styleType !== 'form' && <span class='time-consuming-title'>{this.$t('耗时')}</span>}
        <div
          class={['input-wrap', { 'is-error': this.startError }]}
          v-bk-tooltips={{
            placement: 'bottom',
            content: (
              <div>
                {this.$t('支持')}
                ns, μs, ms, s, m, h, d
              </div>
            ),
          }}
        >
          <Input
            v-model={this.startValue}
            placeholder={'0ns'}
            size={this.styleType !== 'form' ? 'small' : 'default'}
            onChange={val => this.handleInputChange(val, 'start')}
          />
        </div>
        <div class='slider-wrap'>
          <Slider
            v-model={this.durationSlider.curValue}
            disable={this.durationSlider.disable}
            maxValue={this.durationSlider.max}
            minValue={this.durationSlider.min}
            step={this.durationSlider.step}
            range
            onChange={() => this.handleChangeDebounce()}
            onUpdate:modelValue={this.handleRangeChange}
          />
        </div>

        <div
          class={['input-wrap', { 'is-error': this.endError }]}
          v-bk-tooltips={{
            placement: 'bottom',
            content: (
              <div>
                {this.$t('支持')}
                ns, μs, ms, s, m, h, d
              </div>
            ),
          }}
        >
          <Input
            v-model={this.endValue}
            placeholder={'1s'}
            size={this.styleType !== 'form' ? 'small' : 'default'}
            onChange={val => this.handleInputChange(val, 'end')}
          />
        </div>
      </div>
    );
  },
});
