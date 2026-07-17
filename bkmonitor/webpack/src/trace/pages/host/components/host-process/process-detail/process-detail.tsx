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

import {
  type PropType,
  computed,
  ref as deepRef,
  defineComponent,
  onBeforeUnmount,
  provide,
  shallowRef,
  watch,
} from 'vue';

import { Exception, Loading, Sideslider } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { useMetricAggregation } from '../../../composables/use-metric-aggregation';
import { useProcessMetric } from '../../../composables/use-process-metric';
import { formatProcessUptimeDetail, PROCESS_DETAIL_TABS, PROCESS_PORT_STATUS_MAP } from '../../../constants/process';
import { buildScopedVars, DashboardPanel } from '../../dashbords';
import GroupManageDialog from '../../host-metric/group-manage-dialog';
import MetricToolbar from '../../host-metric/metric-toolbar';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import TimeRange from '@/components/time-range/time-range';
import { getDefaultTimezone } from '@/i18n/dayjs';

import type { ProcessDetailTab } from '../../../constants/process';
import type { ProcessItem } from '../../../types/process';
import type { TimeRangeType } from '@/components/time-range/utils';
import type { CompareTarget, IHostTopoHostNode, IHostTopoTreeNode } from '@/pages/host/types';

import './process-detail.scss';

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
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
    compareHostList: {
      type: Array as PropType<IHostTopoHostNode[]>,
      default: () => [],
    },
  },
  emits: {
    'update:show': (_v: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    // 抽屉本地的时间范围与刷新（独立于页面顶栏，仅驱动详情内图表）
    const timeRange = deepRef<TimeRangeType>(['now-1d', 'now']);
    const timezone = shallowRef(getDefaultTimezone());
    const refreshInterval = shallowRef(-1);
    const refreshImmediate = shallowRef('');
    // 向下游图表（useEcharts）提供本地时间范围与刷新信号
    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);

    // 自动刷新定时器：间隔 > 0 时周期性触发图表刷新
    let refreshTimer: null | ReturnType<typeof setInterval> = null;
    const clearRefreshTimer = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    };
    watch(refreshInterval, value => {
      clearRefreshTimer();
      if (value > 0) {
        refreshTimer = setInterval(() => {
          refreshImmediate.value = random(5);
        }, value);
      }
    });
    onBeforeUnmount(clearRefreshTimer);

    // 汇聚 Toolbar 状态（与系统指标一致，受控分发给 Toolbar 与图表）
    const aggregation = useMetricAggregation();
    // 进程指标数据：取数走带缓存的 panel / order
    const metricCtrl = useProcessMetric({
      keyword: () => aggregation.state.keyword,
      ungroupTitle: () => t('未分组'),
    });

    /** 根据选中节点类型，生成当前目标的查询参数 */
    const currentTarget = computed<CompareTarget>(() => {
      if ('bk_host_id' in props.selectedNode) {
        return {
          bk_target_ip: props.selectedNode.ip,
          bk_target_cloud_id: props.selectedNode.bk_cloud_id,
          bk_host_id: props.selectedNode.bk_host_id,
        };
      }

      return {
        bk_inst_id: props.selectedNode.bk_inst_id,
        bk_obj_id: props.selectedNode.bk_obj_id,
      };
    });

    // 变量取值：仅请求态字段变化才会触发图表重新取数
    const scopedVars = computed(() => buildScopedVars(aggregation.state, currentTarget.value));

    /** 当前二级 Tab，默认指标视图 */
    const activeTab = shallowRef<ProcessDetailTab>('metric');
    /** 视图分组管理弹窗 */
    const settingShow = shallowRef(false);

    // 打开抽屉时按需加载指标数据（service 已做缓存，重复打开不会重复请求）
    watch(
      () => props.show,
      show => {
        if (show) {
          metricCtrl.load();
        }
      },
      { immediate: true }
    );

    const handleClose = () => emit('update:show', false);

    /** 详情标题：进程名 / 主机 IP */
    const detailTitle = computed(() => {
      const process = props.process;
      if (!process) return t('进程详情');
      return `${process.name} / ${process.hostIp}`;
    });

    /** 抽屉头部：标题 + 右侧时间/刷新工具 */
    const renderHeader = () => (
      <div class='process-detail-header'>
        <div class='process-detail-header__left'>
          <i
            class='icon-monitor icon-arrow-left process-detail-header__collapse'
            onClick={handleClose}
          />
          <span class='process-detail-header__title'>{detailTitle.value}</span>
        </div>
        <div class='process-detail-header__tools'>
          <TimeRange
            modelValue={timeRange.value}
            timezone={timezone.value}
            onUpdate:modelValue={(value: TimeRangeType) => (timeRange.value = value)}
            onUpdate:timezone={(value: string) => (timezone.value = value)}
          />
          <span class='process-detail-header__divider' />
          <RefreshRate
            value={refreshInterval.value}
            onImmediate={() => (refreshImmediate.value = random(5))}
            onSelect={(value: number) => (refreshInterval.value = value)}
          />
        </div>
      </div>
    );

    /** 详情头部块：LOGO + 标题 + key-value 信息 */
    const renderInfo = () => {
      const process = props.process;
      if (!process) return null;
      const portConfig = PROCESS_PORT_STATUS_MAP[process.portStatus];
      return (
        <div class='process-detail__info'>
          <div class='process-detail__logo'>
            <i class='icon-monitor icon-mc-process' />
          </div>
          <div class='process-detail__info-main'>
            <div class='process-detail__info-title'>{detailTitle.value}</div>
            <div class='process-detail__info-meta'>
              <div class='process-detail__kv'>
                <span class='process-detail__kv-label'>{t('用户')}：</span>
                <span class='process-detail__kv-value'>{process.user || '--'}</span>
              </div>
              <div class='process-detail__kv'>
                <span class='process-detail__kv-label'>{t('运行时长')}：</span>
                <span class='process-detail__kv-value'>{formatProcessUptimeDetail(process.uptime)}</span>
              </div>
              <div class='process-detail__kv'>
                <span class='process-detail__kv-label'>{t('端口')}：</span>
                <span
                  style={{ backgroundColor: portConfig?.color || '#c4c6cc' }}
                  class='process-detail__kv-dot'
                />
                <span class='process-detail__kv-value'>{`${process.protocol} ${process.bindIp}: ${process.port}`}</span>
              </div>
              <div class='process-detail__kv'>
                <span class='process-detail__kv-label'>{t('启动命令')}：</span>
                <span class='process-detail__kv-value'>{process.startCommand || '--'}</span>
              </div>
            </div>
          </div>
        </div>
      );
    };

    /** 二级 Tab：指标视图 / Profiling */
    const renderTabs = () => (
      <div class='process-detail__tabs'>
        {PROCESS_DETAIL_TABS.map(tab => (
          <div
            key={tab.id}
            class={['process-detail__tab', { 'is-active': activeTab.value === tab.id }]}
            onClick={() => (activeTab.value = tab.id)}
          >
            <i class={['icon-monitor', tab.icon, 'process-detail__tab-icon']} />
            <span>{t(tab.label)}</span>
          </div>
        ))}
      </div>
    );

    /** 指标视图：与系统指标组件展示一致（Toolbar + 图表 + 视图分组管理） */
    const renderMetric = () => (
      <div class='process-detail__metric'>
        <MetricToolbar
          currentTarget={props.selectedNode.name}
          targetList={props.compareHostList}
          value={aggregation.state}
          onChange={aggregation.updateState}
          onOpenSetting={() => (settingShow.value = true)}
        />
        <DashboardPanel
          class='process-detail__charts'
          columns={aggregation.state.columns}
          rows={metricCtrl.rows.value}
          scopedVars={scopedVars.value}
        />
        <GroupManageDialog
          isShow={settingShow.value}
          orderData={metricCtrl.orderData.value}
          submitLoading={metricCtrl.loading.value}
          onReset={metricCtrl.handleReset}
          onSave={metricCtrl.handleSave}
          onUpdate:isShow={(v: boolean) => (settingShow.value = v)}
        />
      </div>
    );

    /** Profiling 本期未开发，展示占位 */
    const renderProfiling = () => (
      <div class='process-detail__placeholder'>
        <Exception
          description={t('功能开发中')}
          scene='part'
          type='building'
        />
      </div>
    );

    const renderContent = () => (
      <Loading
        class='process-detail'
        loading={metricCtrl.loading.value}
      >
        {renderInfo()}
        {renderTabs()}
        {activeTab.value === 'metric' ? renderMetric() : renderProfiling()}
      </Loading>
    );

    return () => (
      <Sideslider
        width={1200}
        extCls='process-detail-sideslider'
        isShow={props.show}
        quickClose
        onUpdate:isShow={(v: boolean) => emit('update:show', v)}
      >
        {{
          header: renderHeader,
          default: renderContent,
        }}
      </Sideslider>
    );
  },
});
