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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { type HostContentTab, type HostPerspective, HOST_PERSPECTIVE_TAB_MAP } from '../../constants/constants';
import { isHostNode } from '../../utils/topo-tree';
import HostList from '../host-list/host-list';
import HostMetric from '../host-metric/host-metric';
import HostProcess from '../host-process/host-process';

import type { IHostTopoHostNode, IHostTopoTreeNode } from '../../types';

import './host-content-tabs.scss';

export default defineComponent({
  name: 'HostContentTabs',
  props: {
    /** 当前选中的拓扑节点 / 主机（决定内容区视角与各 Tab 数据） */
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
    /** 对比主机列表 */
    compareHostList: {
      type: Array as PropType<IHostTopoHostNode[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 当前视角：选中主机叶子 → host 视角，否则 → topo 视角 */
    const perspective = computed<HostPerspective>(() =>
      props.selectedNode && isHostNode(props.selectedNode) ? 'host' : 'topo'
    );

    /** 当前视角对应的 Tab 列表 */
    const tabList = computed(() => HOST_PERSPECTIVE_TAB_MAP[perspective.value]);

    /** 当前激活 Tab */
    const activeTab = shallowRef<HostContentTab>(tabList.value[0].value);

    // 切换视角时重置为该视角的第一个 Tab（host → 系统指标，topo → 主机列表）
    watch(perspective, () => {
      activeTab.value = tabList.value[0].value;
    });

    const handleTabChange = (value: HostContentTab) => {
      activeTab.value = value;
    };

    /** 按激活 Tab 渲染对应内容组件 */
    const renderContent = () => {
      switch (activeTab.value) {
        case 'list':
          return <HostList selectedNode={props.selectedNode} />;
        case 'metric':
        case 'system':
          // 指标汇聚（topo）与系统指标（host）视觉一致，复用同一组件
          return (
            <HostMetric
              compareHostList={props.compareHostList}
              selectedNode={props.selectedNode}
            />
          );
        case 'process':
          return <HostProcess host={props.selectedNode as IHostTopoHostNode} />;
        default:
          return null;
      }
    };

    return () => (
      <div class='host-content-tabs'>
        <div class='host-content-tabs__tabs'>
          {tabList.value.map(tab => (
            <div
              key={tab.value}
              class={['host-content-tabs__tab', { 'is-active': activeTab.value === tab.value }]}
              onClick={() => handleTabChange(tab.value)}
            >
              <i class={['icon-monitor', tab.icon, 'host-content-tabs__tab-icon']} />
              <span>{t(tab.label)}</span>
            </div>
          ))}
        </div>
        <div
          class={{
            'is-host-list': activeTab.value === 'list',
            'host-content-tabs__content': true,
          }}
        >
          {renderContent()}
        </div>
      </div>
    );
  },
});
