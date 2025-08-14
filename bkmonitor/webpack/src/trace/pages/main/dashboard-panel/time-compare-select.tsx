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

import { defineComponent, ref } from 'vue';
import { computed } from 'vue';
import { watch } from 'vue';

import { Input, Message, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { COMPARE_TIME_OPTIONS } from './utils';

import './time-compare-select.scss';

export default defineComponent({
  name: 'TimeCompareSelect',
  props: {
    compareTimeOptions: { type: Array, default: () => COMPARE_TIME_OPTIONS },
    timeValue: { type: Array, default: () => [] },
  },
  emits: ['timeChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const localTimeValue = ref([]);
    const showCustomTime = ref(false);
    const customTimeVal = ref('');
    const compareTimeCustomList = ref([]);

    const compareTimeList = computed(() => {
      const allList = [...props.compareTimeOptions, ...compareTimeCustomList.value];
      const allListMap = new Map();
      for (const item of allList) {
        allListMap.set(item.id, item.name);
      }
      const value = localTimeValue.value;
      for (const item of value) {
        if (!allListMap.has(item))
          allList.push({
            id: item,
            name: item,
          });
      }
      return allList;
    });

    watch(
      () => props.timeValue,
      val => {
        localTimeValue.value = val;
      },
      { immediate: true }
    );

    function handleTimeChange(list: string[]) {
      localTimeValue.value = list;
      if (JSON.stringify(localTimeValue.value) !== JSON.stringify(props.timeValue)) {
        emit('timeChange', list);
      }
    }

    /**
     * @description 收起时，清空自定义时间 并且派出事件
     * @param val
     */
    function handleSelectToggle(val: boolean) {
      if (!val) {
        customTimeVal.value = '';
        showCustomTime.value = false;
        handleTimeChange(localTimeValue.value);
      }
    }

    function handleAddCustomTime() {
      const regular = /^([1-9][0-9]+)+(m|h|d|w|M|y)$/;
      const str = customTimeVal.value.trim();
      if (regular.test(str)) {
        handleAddCustom(str);
      } else {
        Message({
          theme: 'warning',
          message: t('按照提示输入'),
          offsetY: 40,
        });
      }
    }

    /**
     * @description 添加自定义时间
     * @param str
     */
    function handleAddCustom(str) {
      const timeValue = localTimeValue.value;
      if (compareTimeList.value.every(item => item.id !== str)) {
        compareTimeCustomList.value.push({
          id: str,
          name: str,
        });
      }
      !timeValue.includes(str) && timeValue.push(str);
      showCustomTime.value = false;
      customTimeVal.value = '';
      // handleTimeChange(localTimeValue.value);
    }

    return {
      localTimeValue,
      showCustomTime,
      customTimeVal,
      compareTimeList,
      t,
      handleSelectToggle,
      handleAddCustomTime,
      handleTimeChange,
    };
  },
  render() {
    return (
      <div class='dashboard-panel__time-compare-select'>
        <Select
          class='time-compare-select'
          v-model={this.localTimeValue}
          behavior='simplicity'
          filterable={false}
          multiple={true}
          size={'small'}
          onClear={() => this.handleTimeChange([])}
          onToggle={this.handleSelectToggle}
        >
          {{
            default: () => (
              <>
                {this.compareTimeList.map(item => (
                  <Select.Option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
                <div class='dashboard-panel__compare-time-select-custom'>
                  {this.showCustomTime ? (
                    <span class='time-input-wrap'>
                      <Input
                        v-model={this.customTimeVal}
                        size='small'
                        onEnter={this.handleAddCustomTime}
                      />
                      <span
                        class='help-icon icon-monitor icon-mc-help-fill'
                        v-bk-tooltips={this.t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
                      />
                    </span>
                  ) : (
                    <span
                      class='custom-text'
                      onClick={() => {
                        this.showCustomTime = !this.showCustomTime;
                      }}
                    >
                      {this.t('自定义')}
                    </span>
                  )}
                </div>
              </>
            ),
          }}
        </Select>
      </div>
    );
  },
});
