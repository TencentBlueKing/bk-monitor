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

import { defineComponent, shallowRef, watch, type PropType } from 'vue';
import { shallowReactive } from 'vue';
import { useI18n } from 'vue-i18n';

import { Input, type InputValue, Slider, type SliderValue } from 'tdesign-vue-next';

import { formatDuration, isValidTimeFormat, parseDuration } from './duration-input-utils';

import './duration-input.scss';

export default defineComponent({
  name: 'DurationInput',
  props: {
    value: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    styleType: {
      type: String as PropType<'default' | 'form'>,
      default: 'default',
    },
  },
  emits: {
    change: (_val: number[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const sliderValue = shallowReactive<Record<string, number | number[]>>({
      min: 0,
      max: 1000,
      value: [0, 1000],
    });
    const startInput = shallowRef('');
    const endInput = shallowRef('');

    watch(
      () => props.value,
      val => {
        watchPropValue(val);
      },
      { immediate: true }
    );
    function watchPropValue(val: number[]) {
      const startVal = formatDuration(val[0]);
      const endVal = formatDuration(val[1]);
      const isStartNE = startVal !== startInput.value;
      const isEndNE = endVal !== endInput.value;
      if (isStartNE) {
        startInput.value = startVal;
      }
      if (isEndNE) {
        endInput.value = endVal;
      }
      if (isStartNE || isEndNE) {
        sliderInit(val[0], val[1]);
      }
    }
    /**
     * 处理开始时间输入框变更事件
     * @param val - 输入框的值
     */
    function handleStartInputChange(val: InputValue) {
      const isValid = isValidTimeFormat(val as string);
      if (isValid || val === '') {
        startInput.value = val as string;
        handleChange();
      } else {
        startInput.value = '';
      }
    }
    /**
     * 处理开始结束输入框变更事件
     * @param val - 输入框的值
     */
    function handleEndInputChange(val: InputValue) {
      const isValid = isValidTimeFormat(val as string);
      if (isValid || val === '') {
        endInput.value = val as string;
        handleChange();
      } else {
        endInput.value = '';
      }
    }
    /**
     * 处理滑块拖动结束事件
     * @param val - 滑块当前值，格式为[最小值, 最大值]
     */
    function handleSliderChangeEnd(val: SliderValue) {
      sliderValue.value = val;
      const startVal = formatDuration(val[0]);
      const endVal = formatDuration(val[1]);
      startInput.value = startVal;
      endInput.value = endVal;
      handleChange(false);
    }
    /**
     * 处理时间范围变更事件
     * 将输入框的时间字符串转换为数值并触发change事件
     */
    function handleChange(isInput = true) {
      const startVal = parseDuration(startInput.value);
      const endVal = parseDuration(endInput.value);
      if (startVal === props.value[0] && endVal === props.value[1]) {
        return;
      }
      if (isInput) {
        sliderInit(startVal, endVal);
      }
      emit('change', [startVal, endVal]);
    }

    function sliderInit(startVal, endVal) {
      if (startVal > endVal || startVal === endVal) {
        sliderValue.max = 1000;
        sliderValue.value = [0, 1000];
      } else {
        if (endVal > 1000) {
          sliderValue.max = endVal;
        }
        sliderValue.value = [startVal, endVal];
      }
    }

    return {
      startInput,
      endInput,
      sliderValue,
      t,
      handleStartInputChange,
      handleEndInputChange,
      handleSliderChangeEnd,
    };
  },
  render() {
    return (
      <div class={['duration-input-component', this.styleType]}>
        <div
          class='input-wrap'
          v-bk-tooltips={{
            placement: 'bottom',
            content: (
              <div>
                {this.t('支持')}
                μs/us, ms, s, m, h, d
              </div>
            ),
          }}
        >
          <Input
            v-model={this.startInput}
            autoWidth={true}
            placeholder={'0μs'}
            size={this.styleType === 'default' ? 'small' : 'medium'}
            onBlur={this.handleStartInputChange}
            onEnter={this.handleStartInputChange}
          />
        </div>

        <div class='duration-slider'>
          <Slider
            tooltipProps={{
              overlayClassName: 'duration-input-component-slider-tip',
            }}
            max={this.sliderValue.max as number}
            min={this.sliderValue.min as number}
            range={true}
            value={this.sliderValue.value}
            onChangeEnd={this.handleSliderChangeEnd}
          />
        </div>
        <div
          class='input-wrap'
          v-bk-tooltips={{
            placement: 'bottom',
            content: (
              <div>
                {this.t('支持')}
                μs/us, ms, s, m, h, d
              </div>
            ),
          }}
        >
          <Input
            v-model={this.endInput}
            autoWidth={true}
            placeholder={'+∞'}
            size={this.styleType === 'default' ? 'small' : 'medium'}
            onBlur={this.handleEndInputChange}
            onEnter={this.handleEndInputChange}
          />
        </div>
      </div>
    );
  },
});
