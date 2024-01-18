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
import { defineComponent, PropType, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Select } from 'bkui-vue';

import { IConditionItem } from '../typings';

import './condition-item.scss';

export default defineComponent({
  name: 'ConditionItem',
  props: {
    data: {
      type: Object as PropType<IConditionItem>,
      default: () => null
    },
    labelList: {
      type: Array as PropType<string[]>,
      default: () => []
    },
    valueList: {
      type: Array as PropType<string[]>,
      default: () => []
    }
  },
  emits: ['change', 'delete'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const localValue = reactive<IConditionItem>({
      key: '',
      method: 'eq',
      value: ''
    });
    const labelStatus = reactive({
      toggle: false,
      hover: false
    });

    watch(
      () => props.data,
      newVal => {
        newVal && Object.assign(localValue, newVal);
      },
      {
        immediate: true
      }
    );

    function handleEmitData() {
      emit('change', { ...localValue });
    }

    function handleDelete() {
      emit('delete');
    }

    return {
      t,
      localValue,
      labelStatus,
      handleEmitData,
      handleDelete
    };
  },

  render() {
    return (
      <div class='condition-item-component'>
        <div class='header-label'>
          <div class='label-wrap'>
            <span
              class={{
                label: true,
                active: this.labelStatus.toggle,
                hover: this.labelStatus.hover,
                placeholder: !this.localValue.key
              }}
            >
              {this.localValue.key || this.t('选择')}
            </span>
            <div
              onMouseover={() => (this.labelStatus.hover = true)}
              onMouseout={() => (this.labelStatus.hover = false)}
            >
              <Select
                v-model={this.localValue.key}
                class='label-select'
                onToggle={toggle => (this.labelStatus.toggle = toggle)}
                popover-min-width={120}
                clearable={false}
                onChange={this.handleEmitData}
              >
                {this.labelList.map(option => (
                  <Select.Option
                    key={option}
                    id={option}
                    name={option}
                  ></Select.Option>
                ))}
              </Select>
            </div>
          </div>
          <span class={['method', this.localValue.method]}>=</span>
          <i
            class='icon-monitor icon-mc-delete-line'
            onClick={this.handleDelete}
          ></i>
        </div>
        <div class='content'>
          <Select
            v-model={this.localValue.value}
            onChange={this.handleEmitData}
          >
            {this.valueList.map(option => (
              <Select.Option
                key={option}
                id={option}
                name={option}
              ></Select.Option>
            ))}
          </Select>
        </div>
      </div>
    );
  }
});
