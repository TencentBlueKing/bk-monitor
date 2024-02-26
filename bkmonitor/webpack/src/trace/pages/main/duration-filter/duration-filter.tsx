/* eslint-disable no-restricted-properties */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineComponent, onMounted, PropType, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Input, Slider } from 'bkui-vue';
import { debounce } from 'monitor-common/utils/utils';

import { ISliderItem } from '../../../components/chart-filtering/chart-filtering';
import { formatDuration } from '../../../components/trace-view/utils/date';

import './duration-filter.scss';

const DEFAULT_SLIDER_VALUE = {
  curValue: [0, 1000], // 当前选择范围
  scaleRange: [0, 0], // 刻度范围
  min: 0, // 最小值
  max: 1000, // 最大值
  step: 10, // 步长
  disable: false
};

export default defineComponent({
  name: 'DurationFilter',
  props: {
    range: {
      type: Array as PropType<number[]> | null,
      default: null
    }
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 滑动选择器配置 */
    const durationSlider = ref<ISliderItem>({ ...DEFAULT_SLIDER_VALUE });
    const startVal = ref<string>('');
    const endVal = ref<string>('');
    const startError = ref<boolean>(false);
    const endError = ref<boolean>(false);
    const errMsg = ref<string>('');
    const showExchange = ref<boolean>(false);
    /** 输入框内容校验 */
    const inputReg = /^([1-9][0-9]*|0)(\.[0-9]*[1-9])?(ns|μs|ms|s)$/;

    onMounted(() => {
      if (props.range) {
        const [start, end] = props.range;
        startVal.value = `${start / 1000}ms`;
        endVal.value = `${end / 1000}ms`;
        handleSetSlider(false);
      }
    });

    watch(
      () => props.range,
      val => {
        if (!val) handleClear();
      }
    );

    /** 触发重新检索 */
    const handleChangeDebounce = debounce(
      () => {
        // 接口参数单位为 μs
        const value = durationSlider.value.curValue.map(val => Number(val * 1000));
        emit('change', value);
      },
      300,
      false
    );
    /** 设置滑动选择器配置 */
    const handleSetSlider = (isUpdate = true) => {
      const start = formatToMs(startVal.value);
      const end = formatToMs(endVal.value);
      if (start > end) {
        // 当最小耗时大于最大耗时
        showExchange.value = true;
        errMsg.value = t('最小耗时不能大于最大耗时，');
      } else {
        Object.assign(durationSlider.value, {
          curValue: [start, end],
          min: start,
          max: end,
          step: Math.abs(start - end) / 100,
          disable: start === end
        });
        errMsg.value = '';
        showExchange.value = false;
        isUpdate && handleChangeDebounce();
      }
    };
    /** 将输入框内容转化为 ms 单位 */
    const formatToMs = (str: string) => {
      const parseStr = str.split(/(ns|μs|ms|s)$/);
      const [value, unit] = parseStr;
      switch (unit) {
        case 'ns':
          return Number(value) / Math.pow(10, 6);
        case 'μs':
          return Number(value) / Math.pow(10, 3);
        case 'ms':
          return Number(value);
        case 's':
          return Number(value) * Math.pow(10, 3);
        default:
          return 0;
      }
    };
    /** 拖动滑动选择器改变范围数值 */
    const handleSliderChange = (rangeValue: number[] = []) => {
      const [start, end] = rangeValue;
      startVal.value = formatDuration(start * 1000) === '0μs' ? '0ns' : formatDuration(start * 1000);
      endVal.value = formatDuration(end * 1000) === '0μs' ? '0ns' : formatDuration(end * 1000);
      startError.value = false;
      endError.value = false;
      errMsg.value = '';
    };
    /** 输入框数值改变 */
    const handleInputChange = (val: string, type: 'start' | 'end') => {
      const isError = !inputReg.test(val);
      type === 'start' ? (startError.value = isError) : (endError.value = isError);
      if (!startError.value && !endError.value) {
        errMsg.value = '';
        if (startVal.value.trim() !== '' && endVal.value.trim() !== '') {
          // 起始时间均有值
          handleSetSlider();
        }
      } else {
        errMsg.value = t('单位仅支持ns, μs, ms, s');
      }
    };
    /** 数值互换 */
    const handleExchange = () => {
      const tempStart = startVal.value;
      const temEnd = endVal.value;
      startVal.value = temEnd;
      endVal.value = tempStart;
      handleSetSlider();
    };
    const handleRangeChange = (value: number[]) => {
      const [start, end] = value;
      // 默认不赋值 解决组件api初始化问题
      if (startVal.value === '' && endVal.value === '' && start === 0 && end === 1000) return;

      handleSliderChange(value);
    };
    /** 清空耗时查询 */
    const handleClear = () => {
      startVal.value = '';
      endVal.value = '';
      startError.value = false;
      endError.value = false;
      errMsg.value = '';
      durationSlider.value = { ...DEFAULT_SLIDER_VALUE };
    };

    return {
      durationSlider,
      startVal,
      endVal,
      startError,
      endError,
      errMsg,
      showExchange,
      handleSliderChange,
      handleInputChange,
      handleExchange,
      handleRangeChange,
      handleChangeDebounce
    };
  },
  render() {
    return (
      <div class='duration-filter-container'>
        <div class='filter-tools'>
          <div class={['verify-input', { 'is-error': this.startError }]}>
            <Input
              placeholder={'0ns'}
              v-model={this.startVal}
              onChange={val => this.handleInputChange(val, 'start')}
            />
          </div>
          <Slider
            range
            class='duration-slider'
            v-model={this.durationSlider.curValue}
            minValue={this.durationSlider.min}
            maxValue={this.durationSlider.max}
            step={this.durationSlider.step}
            disable={this.durationSlider.disable}
            onChange={() => this.handleChangeDebounce()}
            onUpdate:modelValue={this.handleRangeChange}
          />
          <div class={['verify-input', { 'is-error': this.endError }]}>
            <Input
              placeholder={'1s'}
              v-model={this.endVal}
              onChange={val => this.handleInputChange(val, 'end')}
            />
          </div>
        </div>
        {!!this.errMsg && (
          <div class='err-msg'>
            {this.errMsg}
            {this.showExchange && (
              <span
                class='exchange-btn'
                onClick={this.handleExchange}
              >
                {this.$t('数值互换')}
              </span>
            )}
          </div>
        )}
      </div>
    );
  }
});
