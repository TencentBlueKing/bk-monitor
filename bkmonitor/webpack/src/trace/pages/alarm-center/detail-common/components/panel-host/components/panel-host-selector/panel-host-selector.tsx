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

import { type PropType, defineComponent } from 'vue';

import { Select } from 'bkui-vue';

import { AlertDetailHostSelectorTypeEnum } from '../../../../../typings/constants';

import './panel-host-selector.scss';

export default defineComponent({
  name: 'PanelHostSelector',
  props: {
    /** 选择器类型 */
    type: {
      type: String as PropType<AlertDetailHostSelectorTypeEnum>,
      default: AlertDetailHostSelectorTypeEnum.HOST,
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
    /**
     * @description 选择器值改变事件
     * @param selected Id 选择器选中值
     */
    function handleSelectChange(selectedId: string) {
      emit('change', selectedId);
    }
    return { handleSelectChange };
  },
  render() {
    return (
      <Select class='panel-host-selector'>
        {{
          trigger: () => (
            <div class='host-selector-trigger-container'>
              <div class='trigger-prefix'>
                <span>主机：</span>
              </div>
              <div class='trigger-main'>
                <span class='selected-text'>demo_k8s / k8s / 9.146.98.234</span>
                <span class='selected-description'>{'(VM-980-234-Host)'}</span>
              </div>
              <div class='trigger-suffix'>
                <i class='icon-monitor icon-mc-triangle-down' />
              </div>
            </div>
          ),
        }}
      </Select>
    );
  },
});
