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

import { Dropdown } from 'bkui-vue';

import { PANEL_LAYOUT_LIST } from './utils';

import './layout-select.scss';

export default defineComponent({
  name: 'LayoutSelect',
  props: {
    layoutActive: { type: Number, default: 0 },
  },
  emits: ['layoutChange'],
  setup(props, { emit }) {
    const dropdownRef = ref(null);
    /** 图表布局图表 */
    const panelLayoutList = PANEL_LAYOUT_LIST;

    const currentLayout = computed(() => {
      return panelLayoutList[props.layoutActive - 1];
    });

    function handleChangeLayout(id: number) {
      emit('layoutChange', id);
      dropdownRef.value.popoverRef.hide();
    }

    return {
      currentLayout,
      panelLayoutList,
      dropdownRef,
      handleChangeLayout,
    };
  },
  render() {
    return (
      <Dropdown
        ref={'dropdownRef'}
        trigger='hover'
      >
        {{
          default: () => (
            <span class='dashboard-panel__layout-select'>
              <i
                class='icon-monitor icon-mc-two-column'
                v-bk-tooltips={{
                  content: this.currentLayout.name,
                  delay: 200,
                  appendTo: 'parent',
                  allowHTML: false,
                }}
              />
              {<span class='layout-name'>{this.currentLayout.name}</span>}
            </span>
          ),
          content: () => (
            <Dropdown.DropdownMenu>
              {this.panelLayoutList.map(item => (
                <Dropdown.DropdownItem
                  key={item.id}
                  extCls={'dashboard-panel__layout-select-item'}
                  onClick={() => this.handleChangeLayout(item.id)}
                >
                  {item.name}
                </Dropdown.DropdownItem>
              ))}
            </Dropdown.DropdownMenu>
          ),
        }}
      </Dropdown>
    );
  },
});
