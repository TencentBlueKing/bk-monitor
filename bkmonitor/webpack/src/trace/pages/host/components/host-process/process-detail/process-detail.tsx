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

import { type PropType, computed, defineComponent, onBeforeUnmount, provide, shallowRef, watch } from 'vue';

import { Exception, Sideslider } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import RefreshRate from '../../../../../components/refresh-rate/refresh-rate';
import ChartSkeleton from '../../../../../components/skeleton/chart-skeleton';
import TimeRange from '../../../../../components/time-range/time-range';
import { getDefaultTimezone } from '../../../../../i18n/dayjs';
import { ProcessDetailTabEnum } from '../../../../../pages/host/constants/enum';
import { PROCESS_DETAIL_TABS, PROCESS_PORT_STATUS_MAP } from '../../../../../pages/host/constants/process';
import { formatProcessUptimeDetail } from '../../../../../pages/host/utils/process';
import { useMetricAggregation } from '../../../composables/use-metric-aggregation';
import { useProcessMetric } from '../../../composables/use-process-metric';
import { type ScopedVarMap, buildScopedVars, DashboardPanel } from '../../dashbords';
import GroupManageDialog from '../../host-metric/group-manage-dialog';
import MetricToolbar from '../../host-metric/metric-toolbar';
import { useHostStore } from '@/store/modules/host';

import type { TimeRangeType } from '../../../../../components/time-range/utils';
import type {
  CompareTarget,
  IHostTopoHostNode,
  IHostTopoTreeNode,
  ProcessDetailTabType,
} from '../../../../../pages/host/types';
import type { CustomOptions } from '../../../../trace-explore/components/explore-chart/use-echarts';
import type { ProcessItem } from '../../../types/process';

import './process-detail.scss';

/**
 * @description 进程详情抽屉组件
 * 以 Sideslider 形式展示单个进程的基本信息（名称、用户、运行时长、端口、启动命令）
 * 与指标视图（MetricToolbar + DashboardPanel），支持本地时间范围与自动刷新。
 */
export default defineComponent({
  name: 'ProcessDetail',
  props: {
    /** 是否展示抽屉 */
    show: {
      type: Boolean,
      default: false,
    },
    /** 当前查看的进程 */
    process: {
      type: Object as PropType<null | ProcessItem>,
      default: null,
    },
    /** 当前选中的拓扑节点（主机或拓扑实例），用于驱动详情取数 */
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
    /** 对比主机列表，透传给 Toolbar 用于对比目标选择 */
    compareHostList: {
      type: Array as PropType<IHostTopoHostNode[]>,
      default: () => [],
    },
  },
  emits: {
    /** 抽屉显隐更新（v-model:show） */
    'update:show': (_v: boolean) => true,
  },
  setup(props) {
    const { t } = useI18n();
    const { processMetricAggregationState } = storeToRefs(useHostStore());

    /** 当前二级 Tab，默认指标视图 */
    const activeTab = shallowRef<ProcessDetailTabType>(ProcessDetailTabEnum.METRIC);
    /** 抽屉本地的时间范围（独立于页面顶栏，仅驱动详情内图表） */
    const timeRange = shallowRef<TimeRangeType>(['now-1d', 'now']);
    /** 抽屉本地时区，跟随 timeRange 一起下发给图表 */
    const timezone = shallowRef(getDefaultTimezone());
    /** 自动刷新间隔（秒），-1 表示关闭 */
    const refreshInterval = shallowRef(-1);
    /** 立即刷新信号：变更该值即触发下游图表重新取数 */
    const refreshImmediate = shallowRef('');
    /** 自动刷新定时器引用：间隔 > 0 时周期性触发图表刷新 */
    let refreshTimer: null | ReturnType<typeof setInterval> = null;

    const cacheTimeRange = shallowRef(null);
    const showRestore = shallowRef(false);
    const handleDataZoomChange = (value: string[]) => {
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

    /** 汇聚 Toolbar 状态（受控分发给 Toolbar 与图表） */
    const aggregation = useMetricAggregation(processMetricAggregationState.value);
    /** 进程指标数据：取数走带缓存的 panel / order */
    const { rows, orderData, loading, settingShow, load, handleReset, handleSave } = useProcessMetric({
      keyword: () => aggregation.state.keyword,
      ungroupTitle: () => t('未分组'),
    });

    // 向下游图表（useEcharts）提供本地时间范围与刷新间隔
    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);
    provide('viewOptions', aggregation.viewOptions);

    /** 根据选中节点类型，生成当前目标的查询参数 */
    const currentTarget = computed<CompareTarget | null>(() => {
      const node = props.selectedNode;
      if (!node) return null;
      if ('bk_host_id' in node) {
        return {
          bk_target_ip: node.ip,
          bk_target_cloud_id: node.bk_cloud_id,
          bk_host_id: node.bk_host_id,
        };
      }

      return {
        bk_inst_id: node.bk_inst_id,
        bk_obj_id: node.bk_obj_id,
      };
    });

    /** 变量取值：仅请求态字段变化才会触发图表重新取数 */
    const scopedVars = computed<ScopedVarMap>(() => ({
      ...buildScopedVars(aggregation.state, currentTarget.value),
      // 进程态需把进程名下发给图表查询，等价于旧版 variables.display_name
      ...(props.process?.name ? { display_name: props.process.name } : {}),
    }));

    /**
     * 图表自定义配置：图例名称中的进程唯一标识（如 127.0.0.1_elasticsearch_1000）替换为进程名展示。
     * 注：取数仍使用唯一 id，此处仅做展示层替换，保留名称其余部分（如同环比后缀）。
     */
    const chartCustomOptions: CustomOptions = {
      series: seriesData =>
        seriesData.map(item => {
          // @ts-expect-error
          const dimensions = item.dimensions;
          // @ts-expect-error
          return { ...item, alias: dimensions ? `${dimensions.display_name}|${dimensions.pid}` : item.alias };
        }),
    };

    /**
     * @description 清除自动刷新定时器
     */
    const clearRefreshTimer = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    };

    /**
     * @description 启动自动刷新定时器
     * @param interval - 刷新间隔（毫秒），<= 0 时不启动
     */
    const startRefreshTimer = (interval: number) => {
      if (interval > 0) {
        refreshTimer = setInterval(() => {
          refreshImmediate.value = random(5);
        }, interval);
      }
    };

    /**
     * @description 抽屉头部区域渲染函数（标题 + 时间范围 + 自动刷新）
     */
    const renderHeader = () => {
      return (
        <div class='process-detail-header'>
          <div class='process-detail-header-left'>
            <span class='process-detail-header-title'>{t('进程详情')}</span>
          </div>
          <div class='process-detail-header-tools'>
            <TimeRange
              modelValue={timeRange.value}
              timezone={timezone.value}
              onUpdate:modelValue={(v: TimeRangeType) => {
                timeRange.value = v;
              }}
              onUpdate:timezone={(v: string) => {
                timezone.value = v;
              }}
            />
            <span class='process-detail-header-divider' />
            <RefreshRate
              value={refreshInterval.value}
              onImmediate={() => {
                refreshImmediate.value = random(5);
              }}
              onSelect={(v: number) => {
                refreshInterval.value = v;
              }}
            />
          </div>
        </div>
      );
    };

    /**
     * @description 抽屉进程基本信息区域渲染函数（进程名、用户、运行时长、端口、启动命令）
     */
    const renderInfo = () => {
      const process = props.process;
      if (!process) return null;
      const portConfig = PROCESS_PORT_STATUS_MAP[process.portStatus];
      return (
        <div class='process-detail-info'>
          <div class='process-detail-logo'>
            <i class='icon-monitor icon-jincheng1' />
          </div>
          <div class='process-detail-info-main'>
            <div class='process-detail-info-title'>{`${process.name} / ${process.hostIp}`}</div>
            <div class='process-detail-info-meta'>
              <div class='process-detail-kv'>
                <span class='process-detail-kv-label'>{t('运行用户')}：</span>
                <span class='process-detail-kv-value'>{process.user || '--'}</span>
              </div>
              <div class='process-detail-kv'>
                <span class='process-detail-kv-label'>{t('运行时长')}：</span>
                <span class='process-detail-kv-value'>{formatProcessUptimeDetail(process.uptime)}</span>
              </div>
              <div class='process-detail-kv'>
                <span class='process-detail-kv-label'>{t('实例数')}：</span>
                <span class='process-detail-kv-value'>{process.instanceCount ?? '--'}</span>
              </div>
              <div class='process-detail-kv'>
                <span class='process-detail-kv-label'>{t('端口')}：</span>
                <span
                  style={{ backgroundColor: portConfig?.color || '#c4c6cc' }}
                  class='process-detail-kv-dot'
                />
                <span class='process-detail-kv-value'>
                  {process.protocol && process.bindIp && process.port
                    ? `${process.protocol} ${process.bindIp}:${process.port}`
                    : '--'}
                </span>
              </div>
              <div class='process-detail-kv'>
                <span class='process-detail-kv-label'>{t('启动命令')}：</span>
                <span class='process-detail-kv-value'>{process.startCommand || '--'}</span>
              </div>
            </div>
          </div>
        </div>
      );
    };

    /**
     * @description 抽屉Tabs区域渲染函数
     */
    const renderTabs = () => (
      <div class='process-detail-tabs'>
        {PROCESS_DETAIL_TABS.map(tab => (
          <div
            key={tab.id}
            class={['process-detail-tab', { 'is-active': activeTab.value === tab.id }]}
            onClick={() => {
              activeTab.value = tab.id;
            }}
          >
            <i class={['icon-monitor', tab.icon, 'process-detail-tab-icon']} />
            <span>{tab.label}</span>
          </div>
        ))}
      </div>
    );

    /**
     * @description 图表区域加载态骨架屏（参考告警中心仪表盘分组，按当前列数渲染两行图表骨架）
     */
    const renderSkeleton = () => (
      <div
        style={{ gridTemplateColumns: `repeat(${processMetricAggregationState.value.columns}, minmax(0, 1fr))` }}
        class='process-detail-skeleton'
      >
        {new Array(3 * processMetricAggregationState.value.columns).fill(0).map((_, index) => (
          <ChartSkeleton key={index} />
        ))}
      </div>
    );

    /**
     * @description 抽屉内容区域渲染函数
     * 指标 Tab：展示 MetricToolbar + DashboardPanel + GroupManageDialog
     * 其他 Tab：展示「功能开发中」占位
     */
    const renderContent = () => {
      if (activeTab.value === ProcessDetailTabEnum.METRIC) {
        return (
          <div class='process-detail-metric'>
            <MetricToolbar
              currentTarget={props.selectedNode?.name}
              targetList={props.compareHostList}
              value={processMetricAggregationState.value}
              onChange={aggregation.updateState}
              onOpenSetting={() => {
                settingShow.value = true;
              }}
            />
            {loading.value ? (
              renderSkeleton()
            ) : (
              <DashboardPanel
                class='process-detail-charts'
                columns={processMetricAggregationState.value.columns}
                customOptions={chartCustomOptions}
                rows={rows.value}
                scopedVars={scopedVars.value}
              />
            )}
            <GroupManageDialog
              isShow={settingShow.value}
              orderData={orderData.value}
              submitLoading={loading.value}
              onReset={handleReset}
              onSave={handleSave}
              onUpdate:isShow={(v: boolean) => {
                settingShow.value = v;
              }}
            />
          </div>
        );
      }

      return (
        <div class='process-detail-placeholder'>
          <Exception
            description={t('功能开发中')}
            scene='part'
            type='building'
          />
        </div>
      );
    };

    /** 抽屉显隐变化时统一管理数据加载与定时器生命周期 */
    watch(
      () => props.show,
      show => {
        if (show) {
          load();
          startRefreshTimer(refreshInterval.value);
        } else {
          clearRefreshTimer();
        }
      },
      { immediate: true }
    );

    /** 仅刷新间隔变化时调整定时器（抽屉关闭时不启停） */
    watch(refreshInterval, value => {
      clearRefreshTimer();
      if (props.show) {
        startRefreshTimer(value);
      }
    });

    /** 组件卸载前清除定时器，避免内存泄漏 */
    onBeforeUnmount(clearRefreshTimer);

    return {
      renderHeader,
      renderInfo,
      renderTabs,
      renderContent,
    };
  },
  render() {
    return (
      <Sideslider
        width={1200}
        extCls='process-detail-sideslider'
        isShow={this.show}
        quickClose
        onUpdate:isShow={v => this.$emit('update:show', v)}
      >
        {{
          header: this.renderHeader,
          default: () => (
            <div class='process-detail'>
              {this.renderInfo()}
              {this.renderTabs()}
              {this.renderContent()}
            </div>
          ),
        }}
      </Sideslider>
    );
  },
});
