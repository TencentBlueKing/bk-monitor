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

import { defineComponent, onMounted } from 'vue';
import { watch } from 'vue';

import { Message, ResizeLayout } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import CommonHeader from '../../components/common-header/common-header';
import { useHostStore } from '../../store/modules/host';
import AlarmTools from './components/alarm-tools/index';
import HostContentTabs from './components/host-content-tabs/host-content-tabs';
import HostLocationBar from './components/host-location-bar/host-location-bar';
import HostTopoTree from './components/host-topo-tree/host-topo-tree';
import { useHostTopoTree } from './composables/use-host-topo-tree';
import { useHostUrlParams } from './composables/use-host-url-params';
import { HOST_PAGE_HEADER_NAV_BAR_LIST } from './constants/constants';

import type { IHostTopoHostNode } from './types';

import './host.scss';

export default defineComponent({
  name: 'HostPage',
  setup() {
    const { t } = useI18n();
    const { timeRange, timezone, refreshImmediate, refreshInterval, scene } = storeToRefs(useHostStore());
    const { urlParams, getUrlParams, setUrlParams } = useHostUrlParams();
    // 拓扑树控制器（Controller），由页面统一持有，向侧边栏与标题栏分发
    const topoTree = useHostTopoTree();

    watch(
      () => urlParams.value,
      () => {
        setUrlParams({});
      }
    );

    onMounted(() => {
      topoTree.loadTopoTree();
      getUrlParams();
    });

    /** 主机对比：本期表格内容未开发，先以消息提示反馈交互（占位） */
    const handleCompare = (payload: { source: IHostTopoHostNode; target: IHostTopoHostNode }) => {
      Message({
        theme: 'primary',
        message: `${t('主机对比')}：${payload.source.ip} vs ${payload.target.ip}`,
      });
    };

    return {
      t,
      timeRange,
      timezone,
      refreshImmediate,
      refreshInterval,
      scene,
      topoTree,
      handleCompare,
    };
  },
  render() {
    return (
      <div class='host-page'>
        <CommonHeader
          class='host-page-header'
          hideFeature={['gotoOld']}
          refreshImmediate={this.refreshImmediate}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange}
          timezone={this.timezone}
          onImmediateRefreshChange={value => (this.refreshImmediate = value)}
          onRefreshIntervalChange={value => (this.refreshInterval = value)}
          onTimeRangeChange={value => (this.timeRange = value)}
          onTimezoneChange={value => (this.timezone = value)}
        >
          {{
            left: () => (
              <div class='host-page-header-left'>
                <ul class='host-page-header-nav'>
                  {HOST_PAGE_HEADER_NAV_BAR_LIST.map(item => (
                    <li
                      key={item.value}
                      class={['host-page-header-nav-item', { active: item.value === this.scene }]}
                      onClick={() => (this.scene = item.value)}
                    >
                      <div class='bar-name'>{this.t(item.label)}</div>
                    </li>
                  ))}
                </ul>

                {this.scene === 'host' && <HostLocationBar selectedNode={this.topoTree.selectedNode.value} />}
              </div>
            ),
            accessGuide: () => <AlarmTools />,
          }}
        </CommonHeader>
        <div class='host-page-content'>
          {this.scene === 'host' ? (
            <ResizeLayout
              class='host-page-content-layout'
              v-slots={{
                aside: () => (
                  <HostTopoTree
                    context={this.topoTree}
                    onCompare={this.handleCompare}
                  />
                ),
                main: () => (
                  <div class='host-page-content-main'>
                    <HostContentTabs
                      compareHostList={this.topoTree.compareHostList.value}
                      selectedNode={this.topoTree.selectedNode.value}
                    />
                  </div>
                ),
              }}
              border={false}
              initialDivide={280}
              max={800}
              min={200}
              placement='left'
              collapsible
              immediate
            />
          ) : (
            // 进程监控场景本期占位
            <div class='host-page-process-placeholder' />
          )}
        </div>
      </div>
    );
  },
});
