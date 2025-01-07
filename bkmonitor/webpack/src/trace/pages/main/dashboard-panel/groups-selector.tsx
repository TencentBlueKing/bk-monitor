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

import { Select } from 'bkui-vue';

import './groups-selector.scss';

interface IItem {
  id: string;
  name: string;
}

export default defineComponent({
  name: 'GroupsSelector',
  setup() {
    const data = [
      {
        id: '1',
        name: '组名称1',
      },
      {
        id: '2',
        name: '组名称2',
      },
      {
        id: '3',
        name: '组名称3',
      },
      {
        id: '4',
        name: '组名称4',
      },
    ];
    const selectList = ref<IItem[]>([]);
    const selected = ref<string[]>([]);
    const tagList = ref<IItem[]>([]);

    init();

    function init() {
      selectList.value = data;
    }

    function handleChange(value: string[]) {
      const vSet = new Set(value);
      const tags = [];
      for (const v of data) {
        if (vSet.has(v.id)) {
          tags.push(v);
        }
      }
      tagList.value = tags;
    }

    function handleDelete(item: IItem) {
      const delIndex = selected.value.findIndex(v => v === item.id);
      selected.value.splice(delIndex, 1);
      handleChange(selected.value);
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
        <div class='left-title'>Group: </div>
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
      </div>
    );
  },
});
