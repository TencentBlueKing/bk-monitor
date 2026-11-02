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
import { type PropType, computed, defineComponent, watch } from 'vue';

// import { type DateValue, DatePicker } from '@blueking/date-picker';
import { Button, Sideslider } from 'bkui-vue';
// import { random } from 'monitor-common/utils';
import { buildHostMonitorTarget, hostMonitorHash } from 'monitor-common/utils/host-monitor-url';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import EmptyStatus from '../../../../components/empty-status/empty-status';
// import RefreshRate from '../../../../components/refresh-rate/refresh-rate';
import { DEFAULT_AGGREGATION_STATE } from '../../constants/aggregation';
import { type HostContentTab, HOST_DETAIL_TAB_LIST } from '../../constants/constants';
import { isHostNode } from '../../utils/topo-tree';
import HostLoading from '../host-loading/host-loading';
import HostMetric from '../host-metric/host-metric';
import HostProcess from '../host-process/host-process';
import { type HostObserveMode, useHostObserveTarget } from './use-host-observe-target';
import { useHostStore } from '@/store/modules/host';

import type { TimeRangeType } from '../../../../components/time-range/utils';
import type { MetricAggregationState } from '../../types/aggregation';
import type { IHostTopoHostNode } from '../../types/topo';

import '../host-content-tabs/host-content-tabs.scss';
import './host-observe-panel.scss';
import '@blueking/date-picker/vue3/vue3.css';

const EMPTY_COMPARE_HOSTS: IHostTopoHostNode[] = [];

const resetAggregation = (state: MetricAggregationState) => {
  Object.assign(state, JSON.parse(JSON.stringify(DEFAULT_AGGREGATION_STATE)));
};

const isHostDetailTab = (value: string): value is 'process' | 'system' => value === 'system' || value === 'process';

export default defineComponent({
  name: 'HostObservePanel',
  props: {
    mode: {
      type: String as PropType<HostObserveMode>,
      default: 'inline',
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 内嵌到主机页时同步页签到地址栏；抽屉使用独立 store，不写地址栏。 */
    syncUrl: {
      type: Boolean,
      default: false,
    },
    bkHostId: {
      type: [String, Number],
      default: '',
    },
    ip: {
      type: String,
      default: '',
    },
    bkCloudId: {
      type: [String, Number],
      default: '',
    },
    bkBizId: {
      type: [String, Number],
      default: '',
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
    timezone: {
      type: String,
      default: '',
    },
    refreshInterval: {
      type: Number,
      default: -1,
    },
    activeTab: {
      type: String,
      default: '',
    },
    hostProcessName: {
      type: String,
      default: '',
    },
    selectedNode: {
      type: Object as PropType<IHostTopoHostNode | null>,
      default: null,
    },
    compareHostList: {
      type: Array as PropType<IHostTopoHostNode[]>,
      default: () => [],
    },
    hostMetadataError: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    close: () => true,
    retryHostMetadata: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const hostStore = useHostStore();
    const { activeTab: storeActiveTab, hostProcessName, refreshInterval, timeRange, timezone } = storeToRefs(hostStore);

    const bkHostId = () => String(props.bkHostId ?? '');
    const bkCloudId = () => (props.bkCloudId == null || props.bkCloudId === '' ? '' : String(props.bkCloudId));
    const target = useHostObserveTarget({
      bkBizId: () => String(props.bkBizId ?? ''),
      bkCloudId,
      bkHostId,
      enabled: () => props.mode === 'inline' || props.isShow,
      ip: () => props.ip,
      mode: () => props.mode,
      selectedNode: () => props.selectedNode,
    });

    const queryTab = () => {
      const value = route.query.activeTab;
      const raw = Array.isArray(value) ? value[0] : value;
      return raw == null ? '' : String(raw);
    };

    const resolveInlineTab = (): 'process' | 'system' => {
      const fromQuery = queryTab();
      if (isHostDetailTab(fromQuery)) return fromQuery;
      if (storeActiveTab.value === 'process') return 'process';
      return 'system';
    };

    if (props.mode === 'inline' && props.syncUrl) {
      storeActiveTab.value = resolveInlineTab();
      watch(
        () => route.query.activeTab,
        () => {
          const fromQuery = queryTab();
          if (isHostDetailTab(fromQuery) && storeActiveTab.value !== fromQuery) {
            storeActiveTab.value = fromQuery;
          }
        }
      );
    }

    const sessionKey = computed(() => {
      if (props.mode !== 'drawer' || !props.isShow) return '';
      return [bkHostId(), props.ip, bkCloudId(), props.activeTab, props.hostProcessName].join('|');
    });

    watch(
      sessionKey,
      (key, previous) => {
        if (!key) {
          if (previous) refreshInterval.value = -1;
          return;
        }
        const range = props.timeRange;
        if (Array.isArray(range) && range.length >= 2 && range[0] != null && range[1] != null) {
          timeRange.value = [range[0], range[1]] as string[];
        }
        if (props.timezone) timezone.value = props.timezone;
        const interval = Number(props.refreshInterval);
        refreshInterval.value = Number.isFinite(interval) ? interval : -1;
        const processName = props.hostProcessName || '';
        hostProcessName.value = processName;
        storeActiveTab.value = processName || props.activeTab === 'process' ? 'process' : 'system';
        resetAggregation(hostStore.metricAggregationState);
        resetAggregation(hostStore.processMetricAggregationState);
      },
      { immediate: true }
    );

    const readyNode = computed(() => {
      const node = props.mode === 'inline' ? props.selectedNode : target.host.value;
      if (!node || !isHostNode(node) || node.metadataPending) return null;
      return node;
    });

    const activeDetailTab = computed<'process' | 'system'>(() =>
      storeActiveTab.value === 'process' ? 'process' : 'system'
    );

    const compareHosts = computed(() => (props.mode === 'drawer' ? EMPTY_COMPARE_HOSTS : props.compareHostList));

    const subtitle = computed(() => {
      const node = readyNode.value;
      if (!node) return props.ip || bkHostId();
      return node.display_name || node.bk_host_innerip || node.ip || String(node.bk_host_id);
    });

    const showInlineMetadataError = computed(
      () => props.mode === 'inline' && props.hostMetadataError && !readyNode.value
    );

    const handleTabChange = (value: HostContentTab) => {
      if (!isHostDetailTab(value)) return;
      storeActiveTab.value = value;
    };

    const handleTabKeydown = (event: KeyboardEvent, index: number) => {
      const lastIndex = HOST_DETAIL_TAB_LIST.length - 1;
      const nextIndexMap: Partial<Record<KeyboardEvent['key'], number>> = {
        ArrowLeft: index === 0 ? lastIndex : index - 1,
        ArrowRight: index === lastIndex ? 0 : index + 1,
        End: lastIndex,
        Home: 0,
      };
      const nextIndex = nextIndexMap[event.key];
      if (nextIndex === undefined) return;
      event.preventDefault();
      handleTabChange(HOST_DETAIL_TAB_LIST[nextIndex].value);
    };

    const handleClose = () => {
      emit('close');
    };

    const handleOpenPage = () => {
      const hostId = readyNode.value?.bk_host_id;
      if (!hostId) return;
      const processName = hostProcessName.value || '';
      const query: Record<string, string> = {
        activeTab: activeDetailTab.value,
        from: String(timeRange.value[0] ?? ''),
        refreshInterval: String(refreshInterval.value),
        to: String(timeRange.value[1] ?? ''),
        timezone: timezone.value,
      };
      if (processName) query.hostProcessName = processName;
      const hash = hostMonitorHash(
        buildHostMonitorTarget({
          bkHostId: String(hostId),
          processName: processName || undefined,
          query,
        })
      );
      const url = new URL(location.href);
      const bizId = readyNode.value?.bk_biz_id;
      if (bizId) url.searchParams.set('bizId', String(bizId));
      url.hash = hash.replace(/^#/, '');
      window.open(url.toString());
    };

    const renderStatus = () => {
      if (showInlineMetadataError.value) {
        return (
          <div
            class='host-content-tabs__host-status'
            role='status'
          >
            {t('主机信息加载失败')}
            <Button
              theme='primary'
              text
              onClick={() => emit('retryHostMetadata')}
            >
              {t('重试')}
            </Button>
          </div>
        );
      }
      if (props.mode === 'drawer' && target.error.value) {
        return (
          <div class='host-observe-panel__status'>
            <EmptyStatus
              scene='part'
              type='500'
              onOperation={() => target.reload()}
            />
          </div>
        );
      }
      if ((props.mode === 'drawer' && target.loading.value) || (props.mode === 'inline' && !readyNode.value)) {
        return (
          <HostLoading
            columns={hostStore.metricAggregationState.columns}
            variant='dashboard'
          />
        );
      }
      return null;
    };

    const renderContent = () => {
      const status = renderStatus();
      if (status) return status;
      const node = readyNode.value;
      if (!node) return null;
      if (activeDetailTab.value === 'process') {
        return (
          <HostProcess
            compareHostList={compareHosts.value}
            host={node}
          />
        );
      }
      return (
        <HostMetric
          compareHostList={compareHosts.value}
          selectedNode={node}
        />
      );
    };

    const renderBody = () => (
      <div class='host-observe-panel'>
        {/* {props.mode === 'drawer' && (
          <div class='host-observe-panel__toolbar'>
            <DatePicker
              class='time-range-date-picker'
              behavior='simplicity'
              modelValue={timeRange.value as DateValue}
              timezone={timezone.value}
              onUpdate:modelValue={(value: DateValue) => {
                timeRange.value = value as string[];
              }}
              onUpdate:timezone={(value: string) => {
                // 只写入抽屉自己的 store。updateTimezone 会改 window.timezone 和 sessionStorage，事件检索会跟着变。
                timezone.value = value;
              }}
            />
            <RefreshRate
              value={refreshInterval.value}
              onImmediate={() => {
                hostStore.refreshImmediate = random(5);
              }}
              onSelect={(value: number) => {
                refreshInterval.value = value;
              }}
            />
          </div>
        )} */}
        <div class='host-content-tabs'>
          <div
            class='host-content-tabs__tabs'
            aria-label={t('主机观测视图')}
            role='tablist'
          >
            {HOST_DETAIL_TAB_LIST.map((tab, index) => {
              const isActive = activeDetailTab.value === tab.value;
              return (
                <button
                  id={`host-observe-tab-${tab.value}`}
                  key={tab.value}
                  class={['host-content-tabs__tab', { 'is-active': isActive }]}
                  aria-controls='host-observe-panel'
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
            id='host-observe-panel'
            class='host-content-tabs__content'
            aria-labelledby={`host-observe-tab-${activeDetailTab.value}`}
            role='tabpanel'
          >
            {renderContent()}
          </div>
        </div>
      </div>
    );

    const renderTitle = () => (
      <div class='host-observe-drawer__title'>
        <span class='title-text'>{t('主机监控')}</span>
        {subtitle.value ? <span class='title-sub'>{subtitle.value}</span> : null}
        <i
          class='icon-monitor icon-mc-goto title-goto'
          v-bk-tooltips={{
            content: t('在新页面打开'),
            placement: 'right',
            zIndex: 10001,
          }}
          onClick={handleOpenPage}
        />
      </div>
    );

    return {
      handleClose,
      renderBody,
      renderTitle,
    };
  },
  render() {
    if (this.mode === 'inline') return this.renderBody();
    return (
      <Sideslider
        width='80vw'
        extCls='host-observe-drawer'
        isShow={this.isShow}
        renderDirective='if'
        quickClose
        transfer
        onUpdate:isShow={(visible: boolean) => {
          if (!visible) this.handleClose();
        }}
      >
        {{
          header: () => this.renderTitle(),
          default: () => (this.isShow ? this.renderBody() : null),
        }}
      </Sideslider>
    );
  },
});
