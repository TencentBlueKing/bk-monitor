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

import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { useHostStore } from '../../../../store/modules/host';
import {
  type HostContentTab,
  type HostPerspective,
  getHostPerspectiveTabList,
  resolveHostContentTab,
} from '../../constants/constants';
import { isHostNode } from '../../utils/topo-tree';
import HostList from '../host-list/host-list';
import HostMetric from '../host-metric/host-metric';
import HostProcess from '../host-process/host-process';

import type { IHostListRow, IHostTopoHostNode, IHostTopoTreeNode } from '../../types';

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
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    selectIpCell: (_row: IHostListRow) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();
    const { activeTab: hostActiveTab } = storeToRefs(useHostStore());

    /** 当前视角：选中主机叶子 → host 视角，否则 → topo 视角 */
    const perspective = computed<HostPerspective>(() =>
      props.selectedNode && isHostNode(props.selectedNode) ? 'host' : 'topo'
    );

    /** 当前视角对应的 Tab 列表 */
    const tabList = computed(() => getHostPerspectiveTabList(perspective.value, !!window.enable_cmdb_level));

    /** 当前激活 Tab */
    const activeTab = shallowRef<HostContentTab>(resolveHostContentTab(route.query.activeTab, tabList.value));

    watch(activeTab, value => {
      if (hostActiveTab.value !== value) {
        hostActiveTab.value = value;
      }
    });

    // URL 参数会在父组件挂载时写入 store；同步校验视角和能力，避免恢复到不可用 Tab。
    watch(
      [() => props.selectedNode, perspective, hostActiveTab],
      () => {
        const requestedTab = hostActiveTab.value || route.query.activeTab;
        // 拓扑尚未返回时无法判断 nodeId 是否为主机，先保留合法的主机详情直达 Tab。
        if (!props.selectedNode && (requestedTab === 'system' || requestedTab === 'process')) {
          activeTab.value = requestedTab;
          if (hostActiveTab.value !== requestedTab) {
            hostActiveTab.value = requestedTab;
          }
          return;
        }
        const nextActiveTab = resolveHostContentTab(requestedTab, tabList.value);
        activeTab.value = nextActiveTab;
        if (hostActiveTab.value !== nextActiveTab) {
          hostActiveTab.value = nextActiveTab;
        }
      },
      { immediate: true }
    );

    const handleTabChange = (value: HostContentTab) => {
      activeTab.value = value;
    };

    const handleTabKeydown = (event: KeyboardEvent, index: number) => {
      const lastIndex = tabList.value.length - 1;
      const nextIndexMap: Partial<Record<KeyboardEvent['key'], number>> = {
        ArrowLeft: index === 0 ? lastIndex : index - 1,
        ArrowRight: index === lastIndex ? 0 : index + 1,
        End: lastIndex,
        Home: 0,
      };
      const nextIndex = nextIndexMap[event.key];
      if (nextIndex === undefined) {
        return;
      }
      event.preventDefault();
      handleTabChange(tabList.value[nextIndex].value);
      const tabElements = (event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLElement>(
        '[role="tab"]'
      );
      tabElements?.[nextIndex]?.focus();
    };

    /** 点击主机列表 IP 单元格时向上冒泡，由页面层处理拓扑树聚焦 */
    const handleSelectIpCell = row => {
      if (props.readonly) {
        return;
      }
      emit('selectIpCell', row);
    };

    /**
     * @description 点击主机列表进程标签，新开页跳转至该主机的进程视图并默认打开进程详情
     * @param {IHostListRow} row - 当前主机行数据
     * @param {string} processName - 被点击的进程名称
     */
    const handleProcessClick = (row: IHostListRow, processName: string) => {
      if (props.readonly) {
        return;
      }
      const targetRoute = router.resolve({
        name: 'host',
        query: {
          ...route.query,
          activeTab: 'process',
          nodeId: String(row.bk_host_id),
          hostProcessName: processName,
        },
      });
      window.open(location.href.replace(location.hash, targetRoute.href), '_blank');
    };

    /** 按激活 Tab 渲染对应内容组件 */
    const renderContent = () => {
      switch (activeTab.value) {
        case 'list':
          return (
            <HostList
              readonly={props.readonly}
              selectedNode={props.selectedNode}
              onProcessClick={handleProcessClick}
              onSelectIpCell={handleSelectIpCell}
            />
          );
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
          return (
            <HostProcess
              compareHostList={props.compareHostList}
              host={props.selectedNode as IHostTopoHostNode}
            />
          );
        default:
          return null;
      }
    };

    return () => (
      <div class='host-content-tabs'>
        <div
          class='host-content-tabs__tabs'
          aria-label={t('主机观测视图')}
          role='tablist'
        >
          {tabList.value.map((tab, index) => {
            const isActive = activeTab.value === tab.value;
            return (
              <button
                id={`host-content-tab-${tab.value}`}
                key={tab.value}
                class={['host-content-tabs__tab', { 'is-active': isActive }]}
                aria-controls='host-content-panel'
                aria-selected={isActive}
                role='tab'
                tabindex={isActive ? 0 : -1}
                type='button'
                onClick={() => handleTabChange(tab.value)}
                onKeydown={(event: KeyboardEvent) => handleTabKeydown(event, index)}
              >
                <i class={['icon-monitor', tab.icon, 'host-content-tabs__tab-icon']} />
                <span>{t(tab.label)}</span>
              </button>
            );
          })}
        </div>
        <div
          id='host-content-panel'
          class={{
            'is-host-list': activeTab.value === 'list',
            'host-content-tabs__content': true,
          }}
          aria-labelledby={`host-content-tab-${activeTab.value}`}
          role='tabpanel'
        >
          {props.selectedNode && renderContent()}
        </div>
      </div>
    );
  },
});
