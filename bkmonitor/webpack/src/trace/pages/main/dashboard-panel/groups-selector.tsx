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
import { watch } from 'vue';
import { shallowRef } from 'vue';

import { Select } from 'bkui-vue';

import './groups-selector.scss';

interface IItem {
  id: string;
  name: string;
}

export default defineComponent({
  name: 'GroupsSelector',
  props: {
    name: { type: String, default: 'Groups' },
    list: { type: Array, default: () => [] },
    value: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  emits: ['change'],
  setup(props, { emit }) {
    // 可选项
    const selectList = shallowRef<IItem[]>([]);
    // 已选项
    const selected = ref<string[]>([]);
    // 已选项tag
    const tagList = ref<IItem[]>([]);

    watch(
      () => props.list,
      val => {
        selectList.value = val;
      },
      { immediate: true }
    );

    /**
     * @description 选择
     * @param value
     */
    function handleChange(value: string[]) {
      const vSet = new Set(value);
      const tags = [];
      for (const v of selectList.value) {
        if (vSet.has(v.id)) {
          tags.push(v);
        }
      }
      tagList.value = tags;
      emit('change', value);
    }

    /**
     * @description 删除已选中的标签
     * @param item
     */
    function handleDelete(item: IItem) {
      const selectedTemp = [];
      for (const id of selected.value) {
        if (id !== item.id) {
          selectedTemp.push(id);
        }
      }
      selected.value = selectedTemp;
      handleChange(selectedTemp);
    }

    return {
      selectList,
      selected,
      tagList,
      handleChange,
      handleDelete,
    };
  },

  render() {
    return (
      <div class='dashboard-panel__groups-selector'>
        <div class='left-title'>{this.name}: </div>
        {this.loading ? (
          <span class='skeleton-element select-skeleton' />
        ) : (
          <div class='right-content'>
            {this.tagList.map(item => (
              <div
                key={item.id}
                class='selected-item'
              >
                <span>{item.name}</span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={() => this.handleDelete(item)}
                />
              </div>
            ))}
            <Select
              v-model={this.selected}
              input-search={false}
              popoverMinWidth={300}
              filterable
              multiple
              onChange={this.handleChange}
            >
              {{
                trigger: () => (
                  <div class='select-add'>
                    <span class='icon-monitor icon-mc-add' />
                  </div>
                ),
                default: () =>
                  this.selectList.map(item => (
                    <Select.Option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    />
                  )),
              }}
            </Select>
          </div>
        )}
      </div>
    );
  },
});
