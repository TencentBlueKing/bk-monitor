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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { Input, Select } from 'bkui-vue';

import './time-select.scss';
export interface ITimeListItem {
  id: string;
  name: string;
}
export default defineComponent({
  name: 'TimeSelect',
  props: {
    // 选择时间列表
    list: {
      type: Array as PropType<ITimeListItem[]>,
      default: () => [],
    },
    value: {
      type: String,
      default: '',
    },
    tip: {
      type: String,
      default: '',
    },
  },
  emits: ['change', 'addItem'],
  setup(props, { emit }) {
    // 自定义时间值
    const customTimeVal = shallowRef('');
    // 是否显示自定义编辑时间框
    const showCustomTime = shallowRef(false);
    /**
     * @description: 自定义时间输入触发
     * @param {string} v 值
     * @param {any} e 事件event
     * @return {*}
     */
    const handleKeyDown = (v: string, e: any) => {
      if (/enter/i.test(e.code) && /^([1-9][0-9]+)+(m|h|d|w|M|y)$/.test(customTimeVal.value)) {
        if (props.list.every(item => item.id !== customTimeVal.value)) {
          emit('addItem', {
            id: customTimeVal.value,
            name: customTimeVal.value,
          });
        }
        emit('change', customTimeVal.value);
        customTimeVal.value = '';
        showCustomTime.value = false;
        document.body.click();
      }
    };

    const handleChange = (v: string) => {
      customTimeVal.value = '';
      emit('change', v);
    };

    return {
      customTimeVal,
      showCustomTime,
      handleKeyDown,
      handleChange,
    };
  },
  render() {
    return (
      <div class='time-select'>
        <Select
          clearable={false}
          modelValue={this.value}
          onSelect={this.handleChange}
        >
          {this.list.map(item => (
            <Select.Option
              id={item.id}
              key={item.id}
              name={item.name}
            >
              {item.name}
            </Select.Option>
          ))}
          <div class='time-select-custom'>
            {this.showCustomTime ? (
              <span class='time-input-wrap'>
                <Input
                  v-model={this.customTimeVal}
                  size='small'
                  onKeydown={this.handleKeyDown}
                />
                <span
                  class='help-icon icon-monitor icon-mc-help-fill'
                  v-bk-tooltips={{
                    allowHTML: false,
                    content: this.tip || this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年'),
                  }}
                />
              </span>
            ) : (
              <span
                class='custom-text'
                onClick={() => {
                  this.showCustomTime = !this.showCustomTime;
                }}
              >
                {this.$t('自定义')}
              </span>
            )}
          </div>
        </Select>
      </div>
    );
  },
});
