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
import { computed, defineComponent, nextTick, onUnmounted, PropType, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Message, Tag, TimePicker } from 'bkui-vue';
import dayjs from 'dayjs';

import { getEventPaths } from '../../../../monitor-pc/utils';

import './time-tag-picker.scss';

interface CurrentTimeModel {
  value: string[];
  index: number;
  show: boolean;
  inputValue: string;
  showInput: boolean;
}

export default defineComponent({
  name: 'TimeTagPicker',
  props: {
    /** 名称 */
    label: { type: String, default: '' },
    /** 名称宽度 */
    labelWidth: { type: Number, default: 52 },
    /** 已选择时间 */
    modelValue: { type: Array as PropType<string[][]>, default: () => [] }
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const sourceValue = ref<string[][]>([]);
    const localValue = reactive<string[][]>([]);
    watch(
      () => props.modelValue,
      val => {
        localValue.splice(0, localValue.length, ...val);
      },
      {
        immediate: true
      }
    );
    const isChange = computed(() => {
      if (sourceValue.value.length !== localValue.length) return true;
      return localValue.some(val => !sourceValue.value.some(source => source[0] === val[0] && source[1] === val[1]));
    });

    const inputRef = ref();
    const currentTime = reactive<CurrentTimeModel>({
      /** 当前输入的时间 */
      value: [],
      /** 当前时间索引，用于判断是否是编辑 */
      index: -1,
      /** 时间选择器是否展示 */
      show: false,
      showInput: false,
      inputValue: ''
    });

    watch(
      () => currentTime.show,
      val => {
        if (val) {
          document.addEventListener('click', handleConfirm);
        } else {
          document.removeEventListener('click', handleConfirm);
        }
      }
    );

    onUnmounted(() => {
      document.removeEventListener('click', handleConfirm);
    });

    /**
     * 打开时间选择器
     * @param time 时间选择器回填的时间
     * @param ind 索引
     */
    function handleShowTime(e: Event, time?: string[], ind?: number) {
      currentTime.index = ind ?? -1;
      currentTime.value = time ? [...time] : [];
      currentTime.show = true;
      currentTime.showInput = !time;
      currentTime.inputValue = '';
      if (currentTime.showInput) {
        nextTick(() => {
          inputRef.value?.focus?.();
        });
      }
      sourceValue.value = JSON.parse(JSON.stringify(localValue));
      e.stopPropagation();
    }

    /**
     * 格式化时间Tag名称格式
     * @param time 时间
     * @returns 格式化后的名称
     */
    function tagNameFormat(time: string[]) {
      const isBefore = dayjs(time[0], 'hh:mm').isBefore(dayjs(time[1], 'hh:mm'));
      return isBefore ? time.join(' - ') : `${time[0]} - ${t('次日')}${time[1]}`;
    }

    /**
     * 删除时间
     * @param ind 索引
     */
    function handleTagClose(ind: number) {
      sourceValue.value = JSON.parse(JSON.stringify(localValue));
      localValue.splice(ind, 1);
      handleEmitData();
    }

    function handleTimeChange(val) {
      currentTime.inputValue = val.join(' - ');
      resetInputWidth();
    }

    const inputWidth = ref(8);
    const textTestRef = ref();
    function resetInputWidth() {
      nextTick(() => {
        inputWidth.value = textTestRef.value.offsetWidth;
      });
    }

    /**
     * 确认选择时间
     */
    function handleConfirm(e: Event) {
      if (getEventPaths(e, '.time-picker-popover').length) return;
      if (!currentTime.value.length && !currentTime.inputValue) {
        currentTime.show = false;
        currentTime.showInput = false;
        return;
      }

      const reg = /^(([0-1][0-9]|2[0-3]):[0-5][0-9])(?: ?)-(?: ?)(([0-1][0-9]|2[0-3]):[0-5][0-9])$/;
      if (currentTime.inputValue) {
        if (!reg.test(currentTime.inputValue)) {
          currentTime.show = false;
          currentTime.showInput = false;
          return;
        }
        const match = currentTime.inputValue.match(reg);
        currentTime.value = [match[1], match[3]];
      }

      if (
        validTimeOverlap(
          currentTime.value,
          localValue.filter((item, index) => index !== currentTime.index)
        )
      ) {
        currentTime.show = false;
        currentTime.showInput = false;
        Message({
          theme: 'warning',
          message: t('时间段重叠了')
        });
        return;
      }

      // 新增时间
      if (currentTime.index === -1) {
        localValue.push([...currentTime.value]);
      } else {
        // 编辑时间
        localValue.splice(currentTime.index, 1, [...currentTime.value]);
      }
      currentTime.show = false;
      currentTime.showInput = false;
      handleEmitData();
    }

    /**
     * 判断新日期是否在已存在的日期内
     * @param val 新日期
     * @param list 已有的日期
     * @returns
     */
    function validTimeOverlap(val, list) {
      return list.some(item => {
        const [start, end] = item;
        const [startTime, endTime] = val;
        const isBefore = dayjs(start, 'hh:mm').isBefore(dayjs(end, 'hh:mm'));
        const targetTimeStamp = {
          start: dayjs(start, 'hh:mm').valueOf(),
          end: dayjs(end, 'hh:mm')
            .add(isBefore ? 0 : 1, 'day')
            .valueOf()
        };
        const currentIsBefore = dayjs(startTime, 'hh:mm').isBefore(dayjs(endTime, 'hh:mm'));
        const currentTimeStamp = {
          start: dayjs(startTime, 'hh:mm').valueOf(),
          end: dayjs(endTime, 'hh:mm')
            .add(currentIsBefore ? 0 : 1, 'day')
            .valueOf()
        };
        return (
          dayjs(currentTimeStamp.start).isBetween(targetTimeStamp.start, targetTimeStamp.end, null, '[]') ||
          dayjs(currentTimeStamp.end).isBetween(targetTimeStamp.start, targetTimeStamp.end, null, '[]')
        );
      });
    }

    /**
     * 提交本地数据
     */
    function handleEmitData() {
      if (isChange.value) {
        emit('update:modelValue', localValue);
        emit('change', localValue);
      }
    }

    return {
      t,
      localValue,
      currentTime,
      inputWidth,
      inputRef,
      textTestRef,
      resetInputWidth,
      tagNameFormat,
      handleShowTime,
      handleTimeChange,
      handleTagClose,
      handleConfirm
    };
  },
  render() {
    return (
      <div class='time-tag-picker-wrapper-component'>
        {this.label && (
          <div
            class='label'
            style={{ width: `${this.labelWidth}px` }}
          >
            {this.label}
          </div>
        )}
        <TimePicker
          class='time-picker'
          v-model={this.currentTime.value}
          type='timerange'
          format='HH:mm'
          open={this.currentTime.show}
          appendToBody
          allowCrossDay
          onChange={this.handleTimeChange}
          ext-popover-cls='time-picker-popover'
        >
          {{
            trigger: () => (
              <div
                class='content'
                onClick={e => this.handleShowTime(e)}
              >
                <i class='icon-monitor icon-mc-time icon'></i>
                <div class='time-tag-list'>
                  {this.localValue.map((item, ind) => (
                    <Tag
                      class='time-tag'
                      closable
                      onClick={e => this.handleShowTime(e, item, ind)}
                      onClose={() => this.handleTagClose(ind)}
                    >
                      {this.tagNameFormat(item)}
                    </Tag>
                  ))}
                  {this.currentTime.showInput && (
                    <input
                      ref='inputRef'
                      class='custom-input'
                      style={{ width: `${this.inputWidth}px` }}
                      v-model={this.currentTime.inputValue}
                      onClick={e => e.stopPropagation()}
                      onInput={this.resetInputWidth}
                    ></input>
                  )}
                  {!this.localValue.length && !this.currentTime.showInput && (
                    <span class='placeholder'>{this.t('如')}：01:00 - 02:00</span>
                  )}
                </div>
              </div>
            )
          }}
        </TimePicker>
        <span
          class='text-width-test'
          ref='textTestRef'
        >
          {this.currentTime.inputValue}
        </span>
      </div>
    );
  }
});
