/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, defineComponent, shallowRef, watch } from 'vue';
import { shallowReactive } from 'vue';

import { type InputValue, type SliderValue, Input, Slider } from 'tdesign-vue-next';
import { useI18n } from 'vue-i18n';

import {
  type TDurationBaseUnit,
  DURATION_UNIT_TIPS,
  formatDuration,
  isValidTimeFormat,
  parseDuration,
} from './duration-input-utils';

import './duration-input.scss';

/** 无有效范围时滑块的默认量程（基础单位） */
const DEFAULT_SLIDER_MAX = 1000;

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
    baseUnit: {
      type: String as PropType<TDurationBaseUnit>,
      default: 'μs',
    },
  },
  emits: {
    change: (_val: number[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 滑块状态：min 固定 0，max 为当前量程，value 为 [起始值, 结束值]，单位与 baseUnit 一致 */
    const sliderValue = shallowReactive<Record<string, number | number[]>>({
      min: 0,
      max: DEFAULT_SLIDER_MAX,
      value: [0, DEFAULT_SLIDER_MAX],
    });
    /** 起始 / 结束输入框的原始字符串（带单位，如 "1.5s"） */
    const startInput = shallowRef('');
    const endInput = shallowRef('');

    watch(
      () => props.value,
      val => {
        watchPropValue(val);
      },
      { immediate: true }
    );
    /** 基础单位变化时（切换字段）原值含义已变，需按新单位重新格式化 */
    watch(
      () => props.baseUnit,
      () => {
        watchPropValue(props.value);
      }
    );
    /** 外部值回写：格式化后同步到输入框，仅在与当前输入不一致时刷新，避免打断用户正在输入的内容 */
    function watchPropValue(val: number[]) {
      const startVal = formatDuration(val[0], props.baseUnit);
      const endVal = formatDuration(val[1], props.baseUnit);
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
      const isValid = isValidTimeFormat(val as string, props.baseUnit);
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
      const isValid = isValidTimeFormat(val as string, props.baseUnit);
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
      const startVal = formatDuration(val[0], props.baseUnit);
      const endVal = formatDuration(val[1], props.baseUnit);
      startInput.value = startVal;
      endInput.value = endVal;
      handleChange(false);
    }
    /**
     * 处理时间范围变更事件
     * 将输入框的时间字符串转换为数值并触发change事件
     */
    function handleChange(isInput = true) {
      const startVal = parseDuration(startInput.value, props.baseUnit);
      const endVal = parseDuration(endInput.value, props.baseUnit);
      if (startVal === props.value[0] && endVal === props.value[1]) {
        return;
      }
      if (isInput) {
        sliderInit(startVal, endVal);
      }
      emit('change', [startVal, endVal]);
    }

    /** 按当前 [起始值, 结束值] 重置滑块量程；区间非法（起 >= 止）时回退到默认量程 */
    function sliderInit(startVal: number, endVal: number) {
      if (startVal >= endVal) {
        sliderValue.max = DEFAULT_SLIDER_MAX;
        sliderValue.value = [0, DEFAULT_SLIDER_MAX];
      } else {
        sliderValue.max = Math.max(endVal, DEFAULT_SLIDER_MAX);
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
                {DURATION_UNIT_TIPS}
              </div>
            ),
          }}
        >
          <Input
            v-model={this.startInput}
            autoWidth={true}
            placeholder={`0${this.baseUnit}`}
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
                {DURATION_UNIT_TIPS}
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
