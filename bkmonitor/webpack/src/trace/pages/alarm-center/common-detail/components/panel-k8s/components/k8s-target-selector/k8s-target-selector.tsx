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

import { type PropType, computed, defineComponent } from 'vue';

import { Select } from 'bkui-vue';

import { type AlertK8sTargetItem, type K8sTableColumnKeysEnum } from '../../../../../typings';

import './k8s-target-selector.scss';

export default defineComponent({
  name: 'K8sTargetSelector',
  props: {
    /** 可选择关联容器对象列表 */
    targetList: {
      type: Array as PropType<AlertK8sTargetItem[]>,
      default: () => [],
    },
    /** 当前选择器数据的维度 */
    groupBy: {
      type: String as PropType<K8sTableColumnKeysEnum>,
    },
    /** 当前选择器选中的关联容器对象 */
    currentTarget: {
      type: Object as PropType<AlertK8sTargetItem>,
    },
  },
  emits: {
    /** 选择器值改变事件 */
    change: (selectedTarget: AlertK8sTargetItem) => true,
  },
  setup(props, { emit }) {
    /** 选择器列表数组转换为 kv 对象结构 */
    const targetMap = computed(() =>
      (props.targetList ?? []).reduce((prev, curr) => {
        const id = curr[props.groupBy];
        if (!id) return prev;
        prev[id] = curr;
        return prev;
      }, {})
    );

    /**
     * @method handleSelected
     * @description 选择器值改变事件
     * @param {string} selectedId 选中的维度值
     */
    const handleSelected = (selectedId: string) => {
      emit('change', targetMap.value[selectedId]);
    };

    return {
      targetMap,
      handleSelected,
    };
  },
  render() {
    return (
      <div class='k8s-target-selector'>
        <Select
          displayKey={this.groupBy}
          filterable={false}
          idKey={this.groupBy}
          list={this.targetList}
          modelValue={this.currentTarget?.[this.groupBy]}
          popoverOptions={{ boundary: 'parent' }}
          onSelect={this.handleSelected}
        >
          {{
            trigger: () => (
              <div class='k8s-target-selector-trigger-container'>
                <div class='trigger-prefix'>
                  <span>{this.groupBy || '--'}：</span>
                </div>
                <div class='trigger-main'>
                  <span class='selected-text'>{this.currentTarget?.[this.groupBy] ?? '--'}</span>
                </div>
                <div class='trigger-suffix'>
                  <i class='icon-monitor icon-mc-triangle-down' />
                </div>
              </div>
            ),
          }}
        </Select>
      </div>
    );
  },
});
