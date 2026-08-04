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
import { type PropType, computed, defineComponent, provide, ref, watch } from 'vue';

import { bkTooltips } from 'bkui-vue';
import deepMerge from 'deepmerge';
import { toBlob, toPng } from 'html-to-image';
import { hexToRgbA } from 'monitor-common/utils/utils';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import { handleTransformToTimestampMs } from '../../../../components/time-range/utils';
import { createAutoTimeRange } from '../../../../plugins/charts/failure-chart/failure-alarm-chart';
import TagDisplay from '../../../../plugins/charts/failure-chart/TagDisplay';
import ChartTitle from '../../../../plugins/components/chart-title';
import { chartDetailProvideKey } from '../../../../plugins/hooks/chart';
import AlarmCharts from '../../../alarm-center/common-detail/components/alarm-view/echarts/alarm-charts';
import { checkIsRoot } from '../../utils';
import FailureViewMonitorCharts, {
  FAILURE_VIEW_CHART_HAS_DATA_KEY,
  FAILURE_VIEW_MONITOR_CHARTS_KEY,
} from './failure-view-monitor-charts';

import type { IMenuItem } from '../../../../plugins/typings';
import type { AlarmDetail } from '../../../alarm-center/typings/detail';
import type { DateValue } from '@blueking/date-picker';

import './failure-view-alarm-chart.scss';

/** 故障视图告警面板数据（incidentAlertView 单条 alert） */
export type FailureAlertPanel = {
  [key: string]: any;
  alert_id?: number | string;
  alert_name?: string;
  anomaly_timestamps?: number[];
  begin_time?: number;
  bk_biz_id?: number;
  data_type?: string;
  dimensions?: Array<{
    display_key: string;
    display_value: string;
    key: string;
    value: string;
  }>;
  end_time?: null | number;
  entity?: { component_type?: string; is_root?: boolean };
  extra_info?: Record<string, any>;
  first_anomaly_time?: number;
  graph_panel?: {
    id?: number | string;
    subTitle?: string;
    targets?: any[];
    title?: string;
    type?: string;
  };
  id?: number | string;
  is_current_primary?: boolean;
  is_feedback_root?: boolean;
  severity?: number;
};

/** 与 FailureChart 默认配色一致 */
const colorList = ['#FDB980', '#3A84FF', '#94F5A4', '#FFB848', '#EA3636', '#7B61FF', '#2DCB56', '#FF9C01'];

/**
 * @description 将故障告警 panel 适配为 AlarmCharts 所需 detail
 */
export const adaptAlertToAlarmDetail = (alert: FailureAlertPanel): AlarmDetail => {
  const raw = alert || ({} as FailureAlertPanel);
  const graphPanel = raw.graph_panel || {};
  return {
    ...raw,
    id: raw.id ?? raw.alert_id,
    anomaly_timestamps: raw.anomaly_timestamps || [],
    begin_time: raw.begin_time || 0,
    end_time: raw.end_time ?? null,
    first_anomaly_time: raw.first_anomaly_time || raw.begin_time || 0,
    data_type: raw.data_type || '',
    severity: raw.severity ?? 3,
    graph_panel: {
      ...graphPanel,
      title: graphPanel.title || '',
      subTitle: graphPanel.subTitle || '',
      targets: graphPanel.targets || [],
    },
  } as unknown as AlarmDetail;
};

/**
 * @description 基于告警时间计算默认 DateValue（毫秒时间戳）
 */
export const getAlertDefaultTimeRange = (alert: FailureAlertPanel): DateValue => {
  const interval = alert?.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
  const { startTime, endTime } = createAutoTimeRange(alert?.begin_time || 0, alert?.end_time || 0, interval);
  return handleTransformToTimestampMs([startTime, endTime]);
};

/**
 * @description 故障视图单图：ChartTitle 对齐 FailureChart，图表主体复用 AlarmCharts(showTitle=false)
 *
 * 复位按钮说明（仅本文件标题区，不改公共 AlarmCharts / MonitorCharts）：
 *  1. 展示位置：ChartTitle
 *  2. 显示条件：本图有可渲染数据，且发生本地框选或收到有效联动 zoom
 *  3. 无数据图：不展示复位，且不向 AlarmCharts 透传 linkedZoomRange（不响应联动缩放）
 *  4. 点击复位：stopPropagation → AlarmCharts.handleRestore → emit restore 清 linkedZoom
 *  5. 框选锁定：仍由 AlarmCharts.showRestore + FailureViewMonitorCharts 负责
 */
export default defineComponent({
  name: 'FailureViewAlarmChart',
  directives: {
    bkTooltips,
  },
  props: {
    /** 故障告警面板数据（等价 FailureChart 的 detail + title/subtitle 来源） */
    alert: {
      type: Object as PropType<FailureAlertPanel>,
      required: true,
    },
    /** 来自同组其他图表的联动 zoom 范围（仅在同 Collapse 组内传播） */
    linkedZoomRange: {
      type: Array as unknown as PropType<DateValue | null>,
      default: null,
    },
    /** 图表配色（与 FailureChart.colors 一致，用于面积图） */
    colors: {
      type: Array as PropType<string[]>,
      default: () => colorList,
    },
    /** echarts 联动组标识（同组图表 tooltip / dataZoom 联动） */
    groupId: {
      type: String,
      default: '',
    },
    /**
     * 当前图表是否处于视口内（由 FailureAlarmChart 基于 viewportPanelIds 计算）。
     * 控制 tooltip 联动：仅视口内的图表才显示联动 tooltip。
     * dataZoom 后 VueEcharts 重建时，新 echarts 实例会自动携带 group，
     * 但 hoverAllTooltips=false 可以在 formatter 层面阻止 tooltip 渲染。
     */
    isInViewport: {
      type: Boolean,
      default: true,
    },
  },
  emits: [
    'dataZoomChange',
    'restore',
    'successLoad',
    // 以下事件与 FailureChart 保持一致，便于外层按需承接
    'full-screen',
    'export-data-retrieval',
    'add-strategy',
    'collect-chart',
    'on-transform-area',
    'on-yaxis-set-scale',
    'relate-alert',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 组件根节点：截图 / 查找 echarts 实例 */
    const failureChartWrapRef = ref<HTMLElement | null>(null);
    /** AlarmCharts 实例，用于标题区复位按钮调用内部 handleRestore */
    const alarmChartsRef = ref<null | { handleRestore?: () => void }>(null);
    /**
     * 标题区复位按钮可见性（与 AlarmCharts 内部 showRestore 语义对齐，但多一道「有数据」门禁）
     */
    const showRestoreBtn = ref(false);
    /**
     * 当前图是否已拉到可渲染 options；由 FailureViewMonitorCharts 写入。
     * loading 期间子组件不改写该值，避免缩放重拉时短暂变 false。
     */
    const chartHasData = ref(false);

    // 与 ChartWrapper 一致，注入给 ChartTitle / AlertActionList
    provide(chartDetailProvideKey, props.alert);
    /** 仅告警视图：让公共 AlarmCharts 渲染专用 MonitorCharts（含缩放锁定等逻辑） */
    provide(FAILURE_VIEW_MONITOR_CHARTS_KEY, FailureViewMonitorCharts);
    /** 供 FailureViewMonitorCharts 回写「是否有数据」 */
    provide(FAILURE_VIEW_CHART_HAS_DATA_KEY, chartHasData);

    /**
     * 仅有数据的图才接收联动 zoom；无数据时传 null，避免 AlarmCharts 误开 showRestore。
     * 若加载完成后才判定有数据且父级仍持有 linkedZoomRange，computed 从 null→range 会触发内部 watch。
     */
    const effectiveLinkedZoomRange = computed(() => (chartHasData.value ? props.linkedZoomRange : null));

    /** 联动 zoom（已过滤无数据）到来时显示复位 */
    watch(effectiveLinkedZoomRange, val => {
      if (val && Array.isArray(val) && val.length === 2) {
        showRestoreBtn.value = true;
      }
    });

    /** 变为无数据时强制隐藏复位（例如本来就空图） */
    watch(chartHasData, hasData => {
      if (!hasData) {
        showRestoreBtn.value = false;
      }
    });

    /** —— 与 FailureChart 字段语义对齐 —— */
    /** detail：告警面板本身 */
    const detail = computed(() => props.alert);
    /** AlarmCharts 所需适配 detail */
    const alarmDetail = computed(() => adaptAlertToAlarmDetail(props.alert));
    /** 业务 ID */
    const bizId = computed(() => Number(props.alert?.bk_biz_id) || undefined);
    /** 主标题：graph_panel.title（对应 FailureChart props.title） */
    const title = computed(() => props.alert?.graph_panel?.title || '');
    /** 副标题：graph_panel.subTitle（对应 FailureChart props.subtitle） */
    const subtitle = computed(() => props.alert?.graph_panel?.subTitle || '');
    /** 图表类型 */
    const chartType = computed(() => (props.alert?.graph_panel?.type === 'bar' ? 'bar' : 'line'));
    /** 根因 / 主告警标识（对应 FailureChart 从 chartInfo inject） */
    const isRootCause = computed(() => !!props.alert?.is_feedback_root);
    const isRoot = computed(() => checkIsRoot(props.alert?.entity));
    const isCurrentPrimary = computed(() => !!props.alert?.is_current_primary);
    /** 维度（对应 FailureChart.dimensionsList） */
    const dimensionsList = computed(() => props.alert?.dimensions || []);

    /** 默认时间范围（仅基于告警数据计算，不受 zoom 联动影响） */
    const defaultTimeRange = computed<DateValue>(() => {
      return getAlertDefaultTimeRange(props.alert);
    });

    /**
     * @description 与 FailureChart.chartOption 一致：默认 tool.list + FailureAlarmChart 覆盖项
     * FailureAlarmChart 曾透传 options.tool.list = ['screenshot','set', ...(area/explore)]
     */
    const chartOption = computed(() => {
      const failAlarmOverride = {
        tool: {
          list: ['screenshot', 'set', ...(chartType.value === 'bar' ? [] : ['area', 'explore'])],
        },
      };
      return deepMerge(
        {
          tooltip: {
            trigger: 'axis',
            triggerOn: 'mousemove|click',
          },
          legend: {
            asTable: false,
            toTheRight: false,
            maxHeight: 30,
          },
          tool: {
            show: true,
            moreList: ['explore', 'set', 'strategy', 'area'],
            // FailureChart 默认完整菜单
            list: ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'strategy', 'area', 'relate-alert'],
          },
          annotation: {
            show: false,
            list: ['ip', 'process', 'strategy'],
          },
        },
        failAlarmOverride as any,
        {
          arrayMerge: (_destinationArray, sourceArray) => sourceArray,
        }
      );
    });

    /**
     * @description 获取 AlarmCharts 内 echarts 实例（适配 area / set）
     */
    const getChartInstance = () => {
      const root = failureChartWrapRef.value;
      if (!root) return null;
      const candidates = root.querySelectorAll<HTMLElement>('.echart-container > div, .echarts, [_echarts_instance_]');
      for (const el of Array.from(candidates)) {
        const instance = echarts.getInstanceByDom(el);
        if (instance) return instance;
      }
      return null;
    };

    /** —— 以下 handler 签名 / 分支与 FailureChart 对齐 —— */

    const handleCollectChart = () => {
      emit('collect-chart');
    };
    const handleFullScreen = () => {
      emit('full-screen');
    };
    const handleAddStrategy = () => {
      emit('add-strategy');
    };
    const handleExplore = () => {
      // FailureChart 原文：emit('export-data-retrieval')，由 FailureAlarmChart 打开检索
      // 此处直接执行 FailureAlarmChart.handleToDataRetrieval 逻辑，并同步向外抛出
      emit('export-data-retrieval');
      const targets = props.alert?.graph_panel?.targets;
      if (!targets) return;
      const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
        props.alert?.bk_biz_id
      }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`;
      window.open(url, '_blank');
    };

    /**
     * @description 截图（对齐 FailureChart.handleStoreImage，截当前组件根节点）
     */
    const handleStoreImage = async () => {
      const el = failureChartWrapRef.value;
      if (!el) return;
      const fileName = `${title.value || 'chart'}.png`;
      if ((window.navigator as any)?.msSaveOrOpenBlob) {
        toBlob(el)
          .then(blob => (window.navigator as any).msSaveOrOpenBlob(blob, fileName))
          .catch(() => {});
        return;
      }
      toPng(el)
        .then(dataUrl => {
          const tagA = document.createElement('a');
          tagA.download = fileName;
          tagA.href = dataUrl;
          document.body.appendChild(tagA);
          tagA.click();
          tagA.remove();
        })
        .catch(e => console.info(e));
    };

    /**
     * @description Y 轴自适应（对齐 FailureChart.handleSetYAxisSetScale，操作 AlarmCharts 内实例）
     */
    const handleSetYAxisSetScale = (needScale: boolean) => {
      emit('on-yaxis-set-scale', needScale);
      const chart = getChartInstance();
      if (chartType.value === 'line' && chart) {
        const options = chart.getOption() as any;
        chart.setOption({
          ...options,
          yAxis: {
            scale: needScale,
            min: needScale ? 'dataMin' : 0,
          },
        });
      }
    };

    /**
     * @description 面积图切换（对齐 FailureChart.handleTransformArea）
     */
    const handleTransformArea = (isArea: boolean) => {
      emit('on-transform-area', isArea);
      const chart = getChartInstance();
      if (chartType.value === 'line' && chart) {
        const options = chart.getOption() as any;
        chart.setOption({
          ...options,
          series: (options.series || []).map((item: any, index: number) => ({
            ...item,
            areaStyle: {
              color: isArea ? hexToRgbA(props.colors[index % props.colors.length], 0.2) : 'transparent',
            },
          })),
        });
      }
    };

    /**
     * @description 对齐 FailureChart.handleMoreToolItemSet
     */
    const handleMoreToolItemSet = (item: IMenuItem) => {
      switch (item.id) {
        case 'save':
          handleCollectChart();
          break;
        case 'screenshot':
          handleStoreImage();
          break;
        case 'fullscreen':
          handleFullScreen();
          break;
        case 'area':
          handleTransformArea(item.checked);
          break;
        case 'set':
          handleSetYAxisSetScale(!item.checked);
          break;
        case 'explore':
          handleExplore();
          break;
        case 'strategy':
          handleAddStrategy();
          break;
        case 'relate-alert':
          emit('relate-alert');
          break;
        default:
          break;
      }
    };

    /**
     * @description 对齐 FailureChart.handleSelectChildMenu
     */
    const handleSelectChildMenu = (data: { child: IMenuItem; menu: IMenuItem }) => {
      switch (data.menu.id) {
        case 'more':
          if (data.child.id === 'screenshot') {
            setTimeout(() => {
              handleStoreImage();
            }, 300);
          }
          break;
        default:
          break;
      }
    };

    /**
     * @description 对齐 FailureChart.handleSuccessLoad
     */
    const handleSuccessLoad = () => {
      emit('successLoad');
    };

    /** 本图主动框选：仅有数据时才会走到此处，同步显示标题复位并广播联动 */
    const handleDataZoomChange = (value: DateValue) => {
      if (!chartHasData.value) return;
      showRestoreBtn.value = true;
      emit('dataZoomChange', value);
    };

    /**
     * @description 标题区复位：阻止冒泡，避免 ChartTitle 整行点击打开 TitleMenu
     * AlarmCharts.handleRestore 会 syncRestore + emit restore，由 onRestore 再清父级 linkedZoom
     */
    const handleTitleRestore = (e: Event) => {
      e.stopPropagation();
      showRestoreBtn.value = false;
      alarmChartsRef.value?.handleRestore?.();
    };

    /** AlarmCharts 复位完成（含标题按钮触发）后向上清理 linkedZoomRange */
    const handleRestore = () => {
      showRestoreBtn.value = false;
      emit('restore');
    };

    return {
      t,
      failureChartWrapRef,
      alarmChartsRef,
      showRestoreBtn,
      effectiveLinkedZoomRange,
      detail,
      alarmDetail,
      bizId,
      title,
      subtitle,
      isRootCause,
      isRoot,
      isCurrentPrimary,
      dimensionsList,
      defaultTimeRange,
      chartOption,
      handleMoreToolItemSet,
      handleSelectChildMenu,
      handleSuccessLoad,
      handleDataZoomChange,
      handleTitleRestore,
      handleRestore,
    };
  },
  render() {
    return (
      <div
        ref='failureChartWrapRef'
        class='failure-view-alarm-chart'
      >
        {/* ChartTitle 段与 FailureChart 保持一致 */}
        {this.title && (
          <div class='echart-header'>
            <ChartTitle
              class='chart-title-wrap'
              v-slots={{
                title: () => (
                  <div class='root-head'>
                    <span class='txt'>
                      {this.detail?.alert_name ? `${this.detail.alert_name}：` : ''}
                      {this.title}
                    </span>
                    {(this.isRoot || this.isRootCause) && (
                      <label class={['root', { 'is-root-cause': this.isRootCause }, { 'is-root': this.isRoot }]}>
                        {this.t('根因')}
                      </label>
                    )}
                  </div>
                ),
                subtitle: () => (
                  <div class='sub-head'>
                    <span
                      class='txt'
                      v-bk-tooltips={{
                        content: (
                          <div style={{ 'max-width': '360px' }}>
                            {this.t('指标：')}
                            <br />
                            {this.subtitle}
                          </div>
                        ),
                      }}
                    >
                      {this.subtitle}
                    </span>
                  </div>
                ),
                tagTitle: () => (
                  <div class='tag-head'>
                    <TagDisplay
                      tagsList={this.dimensionsList}
                      tipsName={this.t('维度：')}
                    />
                  </div>
                ),
                /** 复位仅放标题工具区；无数据或未缩放时不渲染 */
                customTools: () =>
                  this.showRestoreBtn ? (
                    <span
                      class='failure-view-title-restore'
                      onClick={this.handleTitleRestore}
                    >
                      {this.t('复位')}
                    </span>
                  ) : null,
              }}
              isCurrentPrimary={this.isCurrentPrimary}
              isShowAlarm={true}
              menuList={this.chartOption.tool.list || []}
              showMore={true}
              subtitle={this.subtitle || ''}
              title={this.detail?.alert_name ? `${this.detail?.alert_name}：${this.title}` : this.title}
              onMenuClick={this.handleMoreToolItemSet}
              onSelectChild={this.handleSelectChildMenu}
              onSuccessLoad={this.handleSuccessLoad}
            />
          </div>
        )}
        <div class='failure-view-alarm-chart__body'>
          <AlarmCharts
            ref='alarmChartsRef'
            bizId={this.bizId}
            defaultTimeRange={this.defaultTimeRange}
            detail={this.alarmDetail}
            groupId={this.$props.groupId}
            hoverAllTooltips={this.$props.isInViewport}
            linkedZoomRange={this.effectiveLinkedZoomRange}
            showTitle={false}
            onDataZoomChange={this.handleDataZoomChange}
            onRestore={this.handleRestore}
          />
        </div>
      </div>
    );
  },
});
