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

import { type PropType, defineComponent, ref, toRefs, watch } from 'vue';

import { Button, DatePicker, Input, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import IconFont from '../icon-font/icon-font';
import {
  type TimeRangeType,
  DEFAULT_TIME_RANGE,
  handleTransformTime,
  handleTransformToTimestamp,
  intTimestampStr,
  shortcuts,
  shortcutsMap,
} from './utils';

import './time-range.scss';

/**
 * 图表选择时间范围组件
 */
export default defineComponent({
  name: 'TimeRange',
  emit: ['timeChange', 'update:modelValue'],
  props: {
    modelValue: {
      type: Array as PropType<TimeRangeType>,
      default: () => ['now-1h', 'now'],
    },
  },
  setup(props, { emit }) {
    const { modelValue } = toRefs(props);
    const { t } = useI18n();

    /** 日历组件的值 */
    const timestamp = ref<TimeRangeType>(['', '']);

    /** 面板展示状态 */
    const open = ref(false);
    /** 是否展示面板的时间段 */
    const isPanelTimeRange = ref(false);

    /** 组件选中的时间范围 */
    const localValue = ref<TimeRangeType>(['now-1h', 'now']);

    const timeRangeDisplay = ref(shortcutsMap.get(DEFAULT_TIME_RANGE.join(' -- ')));
    /**
     * 控制日历面板是否展示
     * @param show
     */
    const handleShowPanel = (show: boolean) => {
      open.value = show ?? !open.value;
    };
    const handleOpenChange = (val: boolean) => {
      !val && (open.value = val);
    };
    /**
     * 处理trigger的时间展示
     */
    const timeRangeDisplayChange = () => {
      const timeArr = isPanelTimeRange.value ? timestamp.value : localValue.value;
      let timeDisplay = timeArr.join(' -- ');
      if (shortcutsMap.get(timeDisplay)) {
        timeDisplay = shortcutsMap.get(timeDisplay);
      }
      timeRangeDisplay.value = timeDisplay;
    };

    /** 将value转换成时间区间 */
    const handleTransformTimeValue = (value: TimeRangeType = modelValue.value) => {
      const dateArr = handleTransformTime(value);
      timestamp.value = [dateArr[0], dateArr[1]];
    };

    /** 日历组件值变更 */
    const handleDatePickerChagne = (date: TimeRangeType) => {
      timestamp.value = date.map((item, index) => `${item} ${!index ? '00:00:00' : '23:59:59'}`) as TimeRangeType;
      isPanelTimeRange.value = true;
    };

    /** 校验之间范围的合法性 */
    const handleValidateTimeRange = (): boolean => {
      const timeRange = handleTransformToTimestamp(modelValue.value);
      /** 时间格式错误 */
      if (timeRange.some(item => !item)) return false;
      /** 时间范围有误 */
      if (timeRange[0] > timeRange[1]) return false;
      return true;
    };
    /** 将value转换成时间区间 */
    // const handleTransformTimestamp = (value: TimeRangeType = modelValue.value) => {
    //   const dateArr = handleTransformTime(value);
    //   timestamp.value = [dateArr[0], dateArr[1]];
    // };
    /** 确认操作 */
    const handleConfirm = () => {
      const pass = handleValidateTimeRange();
      if (!pass) {
        localValue.value = [...modelValue.value];
        open.value = false;
      } else {
        handleTimeRangeChange();
        timeRangeDisplayChange();
      }
    };
    /** 格式化绝对时间点 */
    const formatTime = (value: TimeRangeType) =>
      value.map(item => {
        const m = dayjs.tz(intTimestampStr(item));
        return m.isValid() ? m.format('YYYY-MM-DD HH:mm:ss') : item;
      });
    /** 对外更新值 */
    const handleTimeRangeChange = () => {
      open.value = false;
      handleTransformTimeValue(timestamp.value);
      const newVal = isPanelTimeRange.value ? timestamp.value : formatTime(localValue.value);
      emit('timeChange', newVal);
      emit('update:modelValue', newVal);
    };

    /**
     * 自定义输入时间范围
     * @param index 值索引
     */
    const handleCustomInput = (index: number) => {
      isPanelTimeRange.value = false;
      if (!localValue.value[index]) {
        localValue.value[index] = dayjs.tz().format('YYYY-MM-DD HH:mm:ss');
      }
    };

    /** 点击快捷时间选项 */
    const handleShortcutChange = data => {
      if (data?.value) {
        isPanelTimeRange.value = false;
        const value = [...data.value] as TimeRangeType;
        handleTransformTimeValue(value);
        localValue.value = value;
      }
      handleTimeRangeChange();
      timeRangeDisplayChange();
    };

    watch(
      () => props.modelValue,
      val => {
        localValue.value = val;
        handleTransformTimeValue();
        timeRangeDisplayChange();
      }
    );

    return {
      open,
      timestamp,
      localValue,
      timeRangeDisplay,
      isPanelTimeRange,
      handleShowPanel,
      handleOpenChange,
      handleDatePickerChagne,
      handleConfirm,
      handleCustomInput,
      handleShortcutChange,
      handleTransformTimeValue,
      t,
    };
  },
  render() {
    return (
      <DatePicker
        class='time-range-date-picker'
        v-slots={{
          trigger: () => (
            <Popover
              v-slots={{
                content: () => (
                  <div class='time-range-tips-content'>
                    <div>{this.timestamp[0]}</div>
                    <div>to</div>
                    <div>{this.timestamp[1]}</div>
                  </div>
                ),
              }}
              placement='bottom'
              theme='light time-range-tips'
              onAfterShow={() => {
                this.handleTransformTimeValue();
              }}
            >
              <span
                class={['time-range-trigger', { active: this.open }]}
                onClick={() => this.handleShowPanel(true)}
              >
                <IconFont
                  classes={['icon-time-range']}
                  icon='icon-mc-time'
                />
                <span>{this.timeRangeDisplay}</span>
              </span>
            </Popover>
          ),
          confirm: () => (
            <div class='time-range-footer'>
              <Button
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.t('确定')}
              </Button>
            </div>
          ),
          header: () => (
            <i18n-t
              class='time-range-custom'
              keypath='从 {0} 至 {1}'
              tag='div'
              // 20231025 禁止 MouseUp 事件冒泡是为了防止点击 header 插槽空间时导致整个弹窗关闭。（原因不明，暂时无法调试出是哪里的问题）
              onMouseup={e => e.stopPropagation()}
            >
              <Input
                class='custom-input'
                v-model={this.localValue[0]}
                onInput={() => this.handleCustomInput(0)}
              />
              <Input
                class='custom-input'
                v-model={this.localValue[1]}
                onInput={() => this.handleCustomInput(1)}
              />
            </i18n-t>
          ),
          shortcuts: () => (
            <ul class='shortcuts-list'>
              {shortcuts.map(item => (
                <li
                  class='shortcuts-item'
                  onClick={() => this.handleShortcutChange(item)}
                >
                  {item.text}
                </li>
              ))}
            </ul>
          ),
        }}
        extPopoverCls='time-range-popover'
        open={this.open}
        type={'daterange'}
        value={this.timestamp}
        appendToBody
        onChange={this.handleDatePickerChagne}
        onOpen-change={this.handleOpenChange}
      />
    );
  },
});
