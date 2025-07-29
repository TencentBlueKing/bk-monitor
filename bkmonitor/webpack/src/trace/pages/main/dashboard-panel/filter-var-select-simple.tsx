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

import { defineComponent, ref, watch } from 'vue';
import type { PropType } from 'vue';

import { Select } from 'bkui-vue';

import './filter-var-select-simple.scss';

interface IOption {
  id: string;
  name: string;
}

export default defineComponent({
  name: 'FilterVarSelectSimple',
  props: {
    label: { type: String, default: '' },
    field: { type: String, default: 'key' },
    multiple: { default: false, type: Boolean },
    options: { default: () => [], type: Array as PropType<IOption[]> },
    value: { default: '', type: [String, Array, Number] },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const localValue = ref('');

    watch(
      () => props.value,
      val => {
        localValue.value = val;
      },
      { immediate: true }
    );

    function handleSelectChange() {
      emit('change', localValue.value);
    }

    return {
      localValue,
      handleSelectChange,
    };
  },
  render() {
    return (
      <span class='dashboard__filter-var-select-simple-wrap'>
        {this.label && <span class='filter-var-label'>{this.label}</span>}
        <Select
          class='bk-select-simplicity filter-var-select'
          v-model={this.localValue}
          behavior='simplicity'
          clearable={false}
          filterable={false}
          multiple={this.multiple}
          size={'small'}
          onChange={this.handleSelectChange}
        >
          {{
            default: () =>
              this.options.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              )),
          }}
        </Select>
      </span>
    );
  },
});
