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

import type { AlertK8sTargetItem, K8sTableColumnKeysEnum } from '../../../../../typings';

import './k8s-target-selector.scss';

/** 唯一标识字段名 */
const TARGET_UNIQUE_ID_KEY = '__target_unique_id__';

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
    change: (selectedTarget: AlertK8sTargetItem) => selectedTarget,
  },
  setup(props, { emit }) {
    /** 一次遍历构建选择器列表与映射对象 */
    const targetSelectorData = computed(() =>
      (props.targetList ?? []).reduce<{
        targetListWithUniqueId: Array<AlertK8sTargetItem & Record<string, string>>;
        targetMap: Record<string, AlertK8sTargetItem>;
      }>(
        (prev, curr) => {
          const id = getTargetUniqueId(curr);
          if (!id) return prev;
          prev.targetListWithUniqueId.push({
            ...curr,
            [TARGET_UNIQUE_ID_KEY]: id,
          });
          prev.targetMap[id] = curr;
          return prev;
        },
        {
          targetListWithUniqueId: [],
          targetMap: {},
        }
      )
    );

    /** 当前选中对象的唯一标识 */
    const currentTargetUniqueId = computed(() => getTargetUniqueId(props.currentTarget));

    /**
     * @method getTargetUniqueId
     * @description 基于目标对象所有属性值生成唯一标识
     * @param {AlertK8sTargetItem} target 目标对象
     */
    const getTargetUniqueId = (target?: AlertK8sTargetItem) =>
      Object.keys(target ?? {})
        .sort()
        .map(key => target?.[key as K8sTableColumnKeysEnum] ?? '')
        .join('-');

    /**
     * @method handleSelected
     * @description 选择器值改变事件
     * @param {string} selectedId 选中的维度值
     */
    const handleSelected = (selectedId: string) => {
      const selectedTarget = targetSelectorData.value.targetMap[selectedId];
      if (!selectedTarget) return;
      emit('change', selectedTarget);
    };

    return {
      targetSelectorData,
      currentTargetUniqueId,
      handleSelected,
    };
  },
  render() {
    return (
      <div class='k8s-target-selector'>
        <Select
          displayKey={this.groupBy}
          filterable={false}
          idKey={TARGET_UNIQUE_ID_KEY}
          list={this.targetSelectorData.targetListWithUniqueId}
          modelValue={this.currentTargetUniqueId}
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
