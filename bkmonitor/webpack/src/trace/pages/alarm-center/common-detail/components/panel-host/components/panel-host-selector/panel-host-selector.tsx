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

import {
  type HostLevelChartParams,
  type ModuleLevelChartParams,
  type TreeNodeItem,
  AlertDetailHostSelectorTypeEnum,
} from '../../../../../typings';
import { getMockData } from './mock-data';

import './panel-host-selector.scss';

/** 不同级别的select配置 */
const HOST_SELECTOR_CONFIG_MAP = {
  [AlertDetailHostSelectorTypeEnum.HOST]: {
    idKey: 'bk_target_ip',
    displayKey: 'display_name',
    descriptionKey: 'alias_name',
    prefixText: '主机',
  },
  [AlertDetailHostSelectorTypeEnum.MODULE]: {
    idKey: 'bk_inst_id',
    displayKey: 'bk_inst_name',
    descriptionKey: '',
    prefixText: '模块',
  },
};

export default defineComponent({
  name: 'PanelHostSelector',
  props: {
    /** 选择器类型(主机|模块) */
    selectorType: {
      type: String as PropType<AlertDetailHostSelectorTypeEnum>,
    },
    /** 选择器选中值 */
    currentTarget: {
      type: Object as PropType<HostLevelChartParams | ModuleLevelChartParams>,
    },
  },
  emits: {
    change: (selectedTarget: HostLevelChartParams | ModuleLevelChartParams) => selectedTarget,
  },
  setup(props, { emit }) {
    /** 上游路径 */
    const upstreamPath = shallowRef('demo_k8s / k8s / ');
    /** 选择器列表 */
    const hostList = shallowRef<TreeNodeItem[]>(getMockData(props.selectorType));
    /** 是否为模块选择器 */
    const isModuleLevel = computed(() => props.selectorType === AlertDetailHostSelectorTypeEnum.MODULE);
    /** 选择器配置 */
    const selectConfig = computed(() => HOST_SELECTOR_CONFIG_MAP[props.selectorType]);
    /** 当前选择器选中的节点对象 */
    const selectedItem = computed(() => convertChartParamToNode(props.currentTarget));

    /**
     * @description 将图表接口所需结构转换为节点数据结构
     * @param {HostLevelChartParams | ModuleLevelChartParams} target 图表接口所需结构
     */
    function convertChartParamToNode(target: HostLevelChartParams | ModuleLevelChartParams) {
      const id = isModuleLevel.value ? target?.bk_inst_id : target?.bk_target_ip;
      const idKey = get(selectConfig)?.idKey;
      return hostList.value.find(e => e?.[idKey] === id);
    }

    /**
     * @description 将节点数据结构转换为图表接口所需结构
     * @param {TreeNodeItem} nodeItem 节点数据
     */
    function convertNodeToCharParam(nodeItem: TreeNodeItem): HostLevelChartParams | ModuleLevelChartParams {
      if (props.selectorType === AlertDetailHostSelectorTypeEnum.MODULE) {
        return {
          bk_inst_id: nodeItem.bk_inst_id,
          bk_obj_id: nodeItem.bk_obj_id,
        };
      }
      return {
        bk_target_ip: nodeItem.bk_host_id,
        bk_target_cloud_id: nodeItem.bk_cloud_id,
      };
    }

    /**
     * @description 选择器值改变事件
     * @param {string} selected Id 选择器选中值
     */
    function handleSelected(selectedId: string) {
      const idKey = get(selectConfig)?.idKey;
      const targetItem = hostList.value.find(e => e?.[idKey] === selectedId);
      const transformItem = convertNodeToCharParam(targetItem);
      emit('change', transformItem);
    }

    return { selectedItem, isModuleLevel, upstreamPath, hostList, selectConfig, handleSelected };
  },
  render() {
    const { idKey, displayKey, descriptionKey } = this.selectConfig;
    return (
      <div class='panel-host-selector'>
        <Select
          filterable={true}
          list={this.hostList}
          modelValue={this.selectedItem?.[idKey]}
          popoverOptions={{ boundary: 'parent' }}
          {...this.selectConfig}
          onSelect={this.handleSelected}
        >
          {{
            trigger: () => (
              <div class='host-selector-trigger-container'>
                <div class='trigger-prefix'>
                  <span>{this.selectConfig.prefixText}：</span>
                </div>
                <div class='trigger-main'>
                  <span class='selected-text'>{`${this.upstreamPath}${this.selectedItem?.[displayKey] ?? '--'}`}</span>
                  {!this.isModuleLevel && this.selectedItem?.[descriptionKey] ? (
                    <span class='selected-description'>{`(${this.selectedItem?.[descriptionKey]})`}</span>
                  ) : null}
                </div>
                <div class='trigger-suffix'>
                  <i class='icon-monitor icon-mc-triangle-down' />
                </div>
              </div>
            ),
            optionRender: ({ item }) => (
              <div class='host-selector-item'>
                <span class='item-display-name'>{item?.[displayKey]}</span>
                {!this.isModuleLevel ? <span class='item-description'>{`(${item?.[descriptionKey]})`}</span> : null}
              </div>
            ),
          }}
        </Select>
      </div>
    );
  },
});
