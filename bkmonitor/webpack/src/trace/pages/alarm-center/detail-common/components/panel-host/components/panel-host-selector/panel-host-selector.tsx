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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import { Select } from 'bkui-vue';

import { AlertDetailHostSelectorTypeEnum } from '../../../../../typings/constants';
import { getMockData } from './mock-data';

import './panel-host-selector.scss';

export default defineComponent({
  name: 'PanelHostSelector',
  props: {
    /** 选择器类型(主机|模块) */
    selectorType: {
      type: String as PropType<AlertDetailHostSelectorTypeEnum>,
    },
    /** 选择器选中值 */
    value: {
      type: String,
      default: '',
    },
  },
  emits: {
    change: (selectedId: string) => typeof selectedId === 'string',
  },
  setup(props, { emit }) {
    /** 选择器列表 */
    const hostList = getMockData(props.selectorType);
    /** 选择器配置 */
    const selectConfig = computed(() =>
      props.selectorType === AlertDetailHostSelectorTypeEnum.MODULE
        ? {
            idKey: 'bk_inst_id',
            displayKey: 'bk_inst_name',
          }
        : {
            idKey: 'bk_host_id',
            displayKey: 'display_name',
            descriptionKey: 'alias_name',
          }
    );

    /**
     * @description 选择器值改变事件
     * @param selected Id 选择器选中值
     */
    function handleSelected(selectedId: string) {
      const idKey = get(selectConfig)?.idKey;
      const targetItem = hostList.find(e => e?.[get(selectConfig)?.idKey] === selectedId);
      console.log('================ selectedId ================', selectedId);
      console.log('================ item ================', targetItem);

      emit('change', selectedId);
    }
    return { hostList, selectConfig, handleSelected };
  },
  render() {
    /** 是否展示描述 */
    const showDescription = this.selectConfig?.descriptionKey;

    return (
      <div class='panel-host-selector'>
        <Select
          list={this.hostList}
          popoverOptions={{ boundary: 'parent' }}
          {...this.selectConfig}
          onSelect={this.handleSelected}
        >
          {{
            trigger: () => (
              <div class='host-selector-trigger-container'>
                <div class='trigger-prefix'>
                  <span>主机：</span>
                </div>
                <div class='trigger-main'>
                  <span class='selected-text'>demo_k8s / k8s / 9.146.98.234</span>
                  {showDescription ? <span class='selected-description'>{'(VM-980-234-Host)'}</span> : null}
                </div>
                <div class='trigger-suffix'>
                  <i class='icon-monitor icon-mc-triangle-down' />
                </div>
              </div>
            ),
            optionRender: ({ item }) => (
              <div class='host-selector-item'>
                <span class='item-display-name'>{item?.[this.selectConfig?.displayKey]}</span>
                {showDescription ? (
                  <span class='item-description'>{`(${item?.[this.selectConfig?.descriptionKey]})`}</span>
                ) : null}
              </div>
            ),
          }}
        </Select>
      </div>
    );
  },
});
