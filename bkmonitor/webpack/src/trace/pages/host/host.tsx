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

import { computed, defineComponent, onMounted, provide, shallowRef } from 'vue';
import { watch } from 'vue';

import { ResizeLayout } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import CommonHeader from '../../components/common-header/common-header';
import { useHostStore } from '../../store/modules/host';
import AlarmTools from './components/alarm-tools/index';
import HostContentTabs from './components/host-content-tabs/host-content-tabs';
import HostDetailView from './components/host-detail-view/host-detail-view';
import HostLocationBar from './components/host-location-bar/host-location-bar';
import HostTopoTree from './components/host-topo-tree/host-topo-tree';
import { useHostDetail } from './composables/use-host-detail';
import { useHostTopoTree } from './composables/use-host-topo-tree';
import { useHostUrlParams } from './composables/use-host-url-params';
import { HOST_PAGE_HEADER_NAV_BAR_LIST } from './constants/constants';

import type { IHostListRow } from './types';

import './host.scss';

export default defineComponent({
  name: 'HostPage',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    /** 是否锁定搜索条件（来自 URL query 参数，分享链接场景使用） */
    const isLockSearch = ((route.query.lockSearch || 'false') as string) === 'true';
    /** 是否为分享链接入口（来自 URL query 参数） */
    const isShareLink = ((route.query.shareLink || 'false') as string) === 'true';
    const { timeRange, timezone, refreshImmediate, refreshInterval, scene, nodeId } = storeToRefs(useHostStore());

    /** 缩放前的时间范围缓存，用于"复位"操作恢复 */
    const cacheTimeRange = shallowRef(null);
    /** 是否显示"复位时间范围"按钮 */
    const showRestore = shallowRef(false);
    /** 图表数据缩放回调：记录缩放前时间范围，更新当前时间范围并显示复位按钮 */
    const handleDataZoomChange = (value: any[]) => {
      if (JSON.stringify(timeRange.value) !== JSON.stringify(value)) {
        cacheTimeRange.value = JSON.parse(JSON.stringify(timeRange.value));
        timeRange.value = value;
        showRestore.value = true;
      }
    };
    /**
     * @description 复位时间范围
     */
    const handleRestore = () => {
      const cacheTime = JSON.parse(JSON.stringify(cacheTimeRange.value));
      timeRange.value = cacheTime;
      showRestore.value = false;
    };

    provide('showRestore', showRestore);
    provide('handleDataZoomChange', handleDataZoomChange);
    provide('handleRestore', handleRestore);

    // 拓扑树控制器（Controller），由页面统一持有，向侧边栏与标题栏分发
    const topoTree = useHostTopoTree(nodeId);
    const { urlParams, getUrlParams, setUrlParams, handleSelectNode } = useHostUrlParams();
    // 主机详情数据（基于选中节点动态生成）
    const { detailData, loading: detailLoading } = useHostDetail(topoTree.selectedNode);

    /** 时间范围选择器禁用提示文案（分享链接锁定搜索时显示） */
    const timeRangeDisabledTip = computed(() => {
      return isShareLink && isLockSearch ? t('该分享链接仅包含当前时间范围') : '';
    });

    watch(
      () => urlParams.value,
      () => {
        setUrlParams();
      }
    );

    onMounted(() => {
      getUrlParams();
    });

    /** 点击主机列表 IP 单元格时，设置 nodeId 并触发拓扑树定位聚焦到对应主机节点 */
    const handleSelectIpCell = (row: IHostListRow) => {
      nodeId.value = String(row.bk_host_id);
      topoTree.handleSelectNodeOfNodeId();
    };

    return {
      t,
      timeRange,
      timezone,
      refreshImmediate,
      refreshInterval,
      scene,
      topoTree,
      detailData,
      detailLoading,
      timeRangeDisabledTip,
      handleSelectNode,
      handleSelectIpCell,
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
          timeRangeDisabledTip={this.timeRangeDisabledTip}
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
            accessGuide: () => <AlarmTools selectedNode={this.topoTree.selectedNode.value} />,
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
                    onSelectNode={node => this.handleSelectNode(node)}
                  />
                ),
                main: () => (
                  <ResizeLayout
                    class='host-page-content-inner-layout'
                    v-slots={{
                      main: () => (
                        <div class='host-page-content-main'>
                          <HostContentTabs
                            compareHostList={this.topoTree.compareHostList.value}
                            selectedNode={this.topoTree.selectedNode.value}
                            onSelectIpCell={this.handleSelectIpCell}
                          />
                        </div>
                      ),
                      aside: () => (
                        <HostDetailView
                          width={320}
                          data={this.detailData}
                          loading={this.detailLoading}
                        />
                      ),
                    }}
                    border={false}
                    initialDivide={undefined}
                    max={600}
                    min={300}
                    placement='right'
                    collapsible
                    immediate
                  />
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
