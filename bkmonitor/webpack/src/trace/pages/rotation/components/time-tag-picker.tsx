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
import { type PropType, computed, defineComponent, nextTick, onUnmounted, reactive, ref, watch } from 'vue';

import { Tag, TimePicker } from 'bkui-vue';
import dayjs from 'dayjs';
import { getEventPaths } from 'monitor-pc/utils';
import { useI18n } from 'vue-i18n';

import './time-tag-picker.scss';

interface CurrentTimeModel {
  index: number;
  inputValue: string;
  show: boolean;
  showInput: boolean;
  value: string[];
}

export default defineComponent({
  name: 'TimeTagPicker',
  props: {
    /** 名称 */
    label: { type: String, default: '' },
    /** 名称宽度 */
    labelWidth: { type: Number, default: 52 },
    /** 已选择时间 */
    modelValue: { type: Array as PropType<string[][]>, default: () => [] },
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
        immediate: true,
      }
    );
    const isChange = computed(() => {
      if (sourceValue.value.length !== localValue.length) return true;
      return localValue.some(val => !sourceValue.value.some(source => source[0] === val[0] && source[1] === val[1]));
    });
    const isShowMsg = ref(false);

    const inputRef = ref();
    const currentTime = reactive<CurrentTimeModel>({
      /** 当前输入的时间 */
      value: [],
      /** 当前时间索引，用于判断是否是编辑 */
      index: -1,
      /** 时间选择器是否展示 */
      show: false,
      showInput: false,
      inputValue: '',
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
    function handleShowTime(e: Event, time: string[], ind?: number) {
      e.stopPropagation();
      if (currentTime.show) {
        handleConfirm(e);
        return;
      }
      currentTime.index = ind ?? -1;
      currentTime.value = [...time];
      currentTime.show = true;
      currentTime.showInput = !ind && ind !== 0;
      currentTime.inputValue = time.join(' - ');
      nextTick(() => {
        if (time) {
          inputWidth.value = textTestRef.value.offsetWidth;
        }
        inputRef.value?.focus?.();
      });
      sourceValue.value = JSON.parse(JSON.stringify(localValue));
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
      currentTime.show = false;
      handleEmitData();
    }

    function handleTimeChange(val) {
      currentTime.inputValue = val.join(' - ');
      localValue[currentTime.index] = val;
      resetInputWidth();
    }

    const reg = /^(([0-1][0-9]|2[0-3]):[0-5][0-9])(?: ?)-(?: ?)(([0-1][0-9]|2[0-3]):[0-5][0-9])$/;
    const inputWidth = ref(8);
    const textTestRef = ref();
    function resetInputWidth() {
      if (reg.test(currentTime.inputValue)) {
        const match = currentTime.inputValue.match(reg);
        currentTime.value = [match[1], match[3]];
      }
      nextTick(() => {
        inputWidth.value = textTestRef.value.offsetWidth;
      });
    }

    /**
     * 确认选择时间
     */
    function handleConfirm(e: Event) {
      isShowMsg.value = false;
      if (getEventPaths(e, '.time-tag-picker-popover').length) return;
      if (!currentTime.value.length && !currentTime.inputValue) {
        initCurrentTime();
        return;
      }

      if (currentTime.inputValue) {
        if (!reg.test(currentTime.inputValue)) {
          initCurrentTime();
          return;
        }
        const match = currentTime.inputValue.match(reg);
        currentTime.value = [match[1], match[3]];
      } else {
        initCurrentTime();
        return;
      }

      // 新增时间
      if (currentTime.index === -1) {
        localValue.push([...currentTime.value]);
      } else {
        // 编辑时间
        localValue.splice(currentTime.index, 1, [...currentTime.value]);
      }
      initCurrentTime();
      handleEmitData();
    }

    function initCurrentTime() {
      currentTime.show = false;
      currentTime.showInput = false;
      currentTime.value = ['00:00', '23:59'];
      currentTime.inputValue = '';
      currentTime.index = -1;
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
      handleConfirm,
    };
  },
  render() {
    return (
      <div class='time-tag-picker-wrapper-component'>
        {this.label && (
          <div
            style={{ width: `${this.labelWidth}px` }}
            class='label'
          >
            {this.label}
          </div>
        )}
        <TimePicker
          class='time-picker'
          v-model={this.currentTime.value}
          ext-popover-cls='time-tag-picker-popover'
          format='HH:mm'
          open={this.currentTime.show}
          type='timerange'
          allowCrossDay
          appendToBody
          onChange={this.handleTimeChange}
        >
          {{
            trigger: () => (
              <div
                class='content'
                onClick={e => this.handleShowTime(e, ['00:00', '23:59'])}
              >
                <i class='icon-monitor icon-mc-time icon' />
                <div class='time-tag-list'>
                  {this.localValue.map((item, ind) => (
                    <Tag
                      key={`${item.join('_')}_${ind}`}
                      class='time-tag'
                      closable
                      onClick={e => this.handleShowTime(e, item, ind)}
                      onClose={() => this.handleTagClose(ind)}
                    >
                      {this.currentTime.index === ind ? (
                        <input
                          ref='inputRef'
                          style={{ width: `${this.inputWidth}px` }}
                          class='edit-custom-input'
                          v-model={this.currentTime.inputValue}
                          onClick={e => e.stopPropagation()}
                          onInput={this.resetInputWidth}
                        />
                      ) : (
                        <span>{this.tagNameFormat(item)}</span>
                      )}
                    </Tag>
                  ))}
                  {this.currentTime.showInput && (
                    <input
                      ref='inputRef'
                      style={{ width: `${this.inputWidth}px` }}
                      class='custom-input'
                      v-model={this.currentTime.inputValue}
                      onClick={e => e.stopPropagation()}
                      onInput={this.resetInputWidth}
                    />
                  )}
                  <span class={['placeholder', !this.localValue.length && !this.currentTime.showInput && 'show']}>
                    {this.t('如')}：01:00 - 02:00
                  </span>
                </div>
              </div>
            ),
          }}
        </TimePicker>
        <span
          ref='textTestRef'
          class='text-width-test'
        >
          {this.currentTime.inputValue}
        </span>
      </div>
    );
  },
});
