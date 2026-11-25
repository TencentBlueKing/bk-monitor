import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { BarChart } from 'echarts/charts';
import { BrushComponent, GridComponent, ToolboxComponent } from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useI18n } from 'vue-i18n';
import VueEcharts from 'vue-echarts';

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import { findSpanRowView } from '../utils/duration-stats';
import {
  BUCKET_GAP,
  buildTrendBuckets,
  DEFAULT_TREND_AGGREGATE,
  filterSpansByTimeRange,
  MIN_BUCKET_WIDTH,
  pickBucketSpans,
  pickTrendSpans,
  pickTrendSpansByFilter,
  resolveBucketCount,
  resolveBucketTimeRange,
  stripSpanChilds,
} from '../utils/trend-buckets';
import { formatCompactToken } from '../utils/transform';
import DurationStatsPanel from './duration-stats-panel';
import TokenStatsPanel from './token-stats-panel';

import type { LlmExecutionFilter, LlmFlowSpan, LlmSpanRowView } from '../utils/typings';
import type { LlmTrendAggregate, LlmTrendSeriesKey, LlmTrendTimeRange, LlmTrendVisible } from '../utils/trend-buckets';

import './trend-chart.scss';

use([BarChart, GridComponent, BrushComponent, ToolboxComponent, CanvasRenderer]);

/** 鼠标移到柱子上后，延迟收起面板，给用户从柱子移动到面板内点击按钮的时间 */
const PANEL_HIDE_DELAY = 300;
/** 鼠标在柱子上停留该时长后才弹出面板，快速划过不弹出 */
const PANEL_SHOW_DELAY = 300;
/** 面板与锚点（绘图区上 / 下边缘）的间距，避免贴住图表 */
const PANEL_OFFSET = 6;

/** 顶部留白：容纳 Y 轴最大值文案一半高度，避免贴顶被裁切 */
const GRID_TOP_PADDING = 8;
/** 单侧绘图区高度，与设计稿 Top / Bottom 一致 */
const PLOT_HEIGHT = 40;
/** 底部时间轴文案高度（axisLabel margin 8 + 字号 12） */
const AXIS_LABEL_HEIGHT = 20;
/** 上下两块绘图区之间的留白 */
const PLOT_GAP = 4;
/** 图表高度：顶部留白 + 上下各 40px 绘图区 + 4px 间隔 + 20px 时间轴 */
const CHART_HEIGHT = GRID_TOP_PADDING + PLOT_HEIGHT * 2 + PLOT_GAP + AXIS_LABEL_HEIGHT;
/** Y 轴标签预留最小宽度，与设计稿 Y-耗时 / Y-Token 的 44px 对齐 */
const AXIS_WIDTH = 44;
/** Y 轴标签文案字体，与 axisLabel 保持一致，用于测量文案宽度 */
const AXIS_LABEL_FONT = '12px Arial, sans-serif';
/** Y 轴标签文案与绘图区的间距（ECharts axisLabel 默认 margin） */
const AXIS_LABEL_MARGIN = 8;
/** Y 轴标签区额外留白，避免长文案贴边被裁切 */
const AXIS_LABEL_PADDING = 4;
/** 耗时柱颜色 */
const DURATION_COLOR = '#3A84FF';
/** 耗时柱 hover 颜色 */
const DURATION_EMPHASIS_COLOR = '#2A6FD6';
/** 总 Token 柱颜色 */
const TOKEN_COLOR = '#4DB8A9';
/** 总 Token 柱 hover 颜色 */
const TOKEN_EMPHASIS_COLOR = '#3FA696';
/** 网格线颜色 */
const GRID_LINE_COLOR = '#F0F1F5';
/** 坐标轴文案颜色 */
const AXIS_LABEL_COLOR = '#8F9FBD';
/** 单根柱子的最大宽度（像素）：数据点较少时不再随容器拉伸，固定上限避免柱子过宽 */
const MAX_BUCKET_WIDTH = 64;
/**
 * Y 轴基线相对数据极差的留白比例：轴底 = 有效最小值 - (最大值 - 有效最小值) * 该系数。
 * 基线跟随极差而非数值大小，例如各桶都集中在 340K~360K 时也能拉开明显柱高差异
 * （最小柱约占绘图区 1/(1+系数) 高度）；差距本就很大时基线自然回落，不会过度失真。
 */
const AXIS_BASELINE_PADDING = 0.1;
/**
 * 依据序列数值抬高 Y 轴基线。忽略 0 值（空桶 / 无 Token 的 Span），
 * 否则存在空桶时最小值恒为 0，基线被拖回原点、放大失效。
 * 全为 0 或无数据时返回 0，退回原始基线。
 */
const resolveAxisMin = (values: number[]) => {
  const positives = values.filter(value => value > 0);
  if (!positives.length) return 0;
  const min = Math.min(...positives);
  const max = Math.max(...positives);
  // 数值完全相等时极差为 0，抬高基线会产生退化零值域，退回原始基线
  if (max === min) return 0;
  return Math.max(0, min - (max - min) * AXIS_BASELINE_PADDING);
};

/** 耗时 Y 轴刻度分段数 */
const DURATION_SPLIT_NUMBER = 4;
/** 总 Token Y 轴刻度分段数 */
const TOKEN_SPLIT_NUMBER = 2;

/** 离屏 canvas 上下文，按 axisLabel 字体测量文案宽度；非浏览器环境为 null */
let measureContext: CanvasRenderingContext2D | null | undefined;

/** 测量一组文案在图上的最大渲染宽度（像素），无法测量时返回 0 */
const measureAxisLabelWidth = (texts: string[]): number => {
  if (!texts.length) return 0;
  if (measureContext === undefined) {
    measureContext = typeof document !== 'undefined' ? document.createElement('canvas').getContext('2d') : null;
  }
  const context = measureContext;
  if (!context) return 0;
  context.font = AXIS_LABEL_FONT;
  return texts.reduce((max, text) => Math.max(max, context.measureText(text).width), 0);
};

/** 将数值向上取整到 1 / 2 / 5 × 10^n 的友好刻度上界，覆盖 ECharts 对 dataMax 做 nice 后的最大值 */
const resolveNiceCeil = (value: number): number => {
  if (!Number.isFinite(value) || value <= 0) return 0;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
};

/**
 * 生成某侧 Y 轴可能出现的刻度文案，用于测量最长文案宽度。
 * ECharts 会把 dataMax 向上取整到友好刻度作为轴顶，这里按相同口径采样刻度值。
 */
const sampleAxisLabelTexts = (
  min: number,
  max: number,
  splitNumber: number,
  format: (value: number) => string
): string[] => {
  const top = Math.max(resolveNiceCeil(max), min);
  const step = splitNumber > 0 ? (top - min) / splitNumber : 0;
  const texts: string[] = [];
  for (let index = 0; index <= splitNumber; index += 1) {
    texts.push(format(min + step * index));
  }
  return texts;
};

/** 依据两侧 Y 轴最长刻度文案动态计算标签区宽度，至少保留设计稿的 AXIS_WIDTH */
const resolveAxisWidth = (durations: number[], tokens: number[]): number => {
  const durationMin = resolveAxisMin(durations);
  const tokenMin = resolveAxisMin(tokens);
  const durationWidth = measureAxisLabelWidth(
    sampleAxisLabelTexts(durationMin, Math.max(...durations, 0), DURATION_SPLIT_NUMBER, value =>
      formatDuration(value || 0, '', 0)
    )
  );
  const tokenWidth = measureAxisLabelWidth(
    sampleAxisLabelTexts(tokenMin, Math.max(...tokens, 0), TOKEN_SPLIT_NUMBER, value => formatCompactToken(value || 0))
  );
  const measured = Math.max(durationWidth, tokenWidth);
  return Math.max(AXIS_WIDTH, Math.ceil(measured) + AXIS_LABEL_MARGIN + AXIS_LABEL_PADDING);
};

type VueEchartsInstance = InstanceType<typeof VueEcharts>;

/**
 * 「耗时、总 Token 趋势图」。
 * flow 为已点开 Trace 累加合并后的完整 Span 树，懒加载到达后逐渐并入，共用一条时间轴。
 * 排除 Agent Span（容器节点，耗时 / Token 由其子 Span 承担），按时间等分桶聚合，
 * 上半区耗时向上、下半区总 Token 向下，共享底部时间轴；图例「只看」由外部 legend 控制，框选后支持复位。
 */
export default defineComponent({
  name: 'LlmTrendChart',
  props: {
    /** 已点开 Trace 累加合并后的完整 Span 树 */
    flow: {
      type: Array as PropType<LlmFlowSpan[]>,
      default: () => [],
    },
    /** 合并的 Trace 中仍有 flow 懒加载中，此时不渲染空态避免闪烁 */
    flowLoading: {
      type: Boolean,
      default: false,
    },
    /** 序列可见性，由工具栏图例控制 */
    visible: {
      type: Object as PropType<LlmTrendVisible>,
      default: () => ({ duration: true, token: true }),
    },
    /** 类型筛选，与工具栏 Tab 联动；仅作用于趋势图聚合，关键字不影响 */
    filter: {
      type: String as PropType<LlmExecutionFilter>,
      default: 'all',
    },
    /** 框选或复位后的时间范围（微秒），由外层持有并回传；null 表示未框选 */
    range: {
      type: Array as unknown as PropType<LlmTrendTimeRange | null>,
      default: null,
    },
    /** 桶内多 Span 的聚合方式：默认取最大值，可切换为 span 总和 */
    aggregate: {
      type: String as PropType<LlmTrendAggregate>,
      default: DEFAULT_TREND_AGGREGATE,
    },
  },
  emits: {
    /** 面板「定位」：外层展开祖先链并滚动到 Span */
    locate: (_spanId: string) => true,
    /** 面板「详情」：外层打开 Span 侧栏 */
    'view-detail': (_row: LlmSpanRowView) => true,
    /** 框选或复位：外层据此同步趋势图与 Span 列表的时间范围 */
    select: (_range: LlmTrendTimeRange | null) => true,
  },
  setup(props, { emit }) {
    /** hover 离开柱子后延迟收起面板，给用户移至面板内点击按钮的时间 */
    let panelHideTimer = 0;
    /** hover 柱子后延迟弹出面板的计时器，快速划过时取消 */
    let panelShowTimer = 0;
    /** 正在等待弹出的桶下标与序列，同一柱子重复 mouseover 不重置计时 */
    let pendingBucketIndex = -1;
    let pendingSeriesKey: LlmTrendSeriesKey | null = null;
    const { t } = useI18n();
    const chartRef = useTemplateRef<VueEchartsInstance>('chart');
    const wrapRef = useTemplateRef<HTMLElement>('wrap');
    const popoverRef = useTemplateRef<{
      updatePopover?: (virtualEl?: null, props?: Record<string, unknown>) => void;
    }>('popover');
    /** 绘图区宽度（扣除 Y 轴标签区），用于推导桶数 */
    const plotWidth = shallowRef(0);
    /** 当前 hover 的桶下标，-1 表示未激活 */
    const activeBucketIndex = shallowRef(-1);
    /** 当前 hover 的序列：耗时或总 Token，决定弹出哪个统计面板 */
    const activeSeries = shallowRef<LlmTrendSeriesKey | null>(null);
    /** 弹出面板锚点（绘图区上 / 下边缘、桶柱中心）相对图表容器的样式 */
    const anchorStyle = shallowRef<Record<string, string>>({ left: '0px', top: '0px' });
    /** 面板可用的最大高度（锚点到对应视口边界），超出内部滚动 */
    const panelMaxHeight = shallowRef<number | undefined>();
    /** 面板展开方向：耗时在上方，总 Token 在下方 */
    const panelPlacement = shallowRef<'top' | 'bottom'>('bottom');
    let resizeObserver: ResizeObserver | undefined;
    /** 鼠标是否处于按下状态；框选过程中划过桶柱不弹面板 */
    const isPointerDown = shallowRef(false);
    /** 存在框选范围时展示复位按钮，与 Span 列表共用外层状态 */
    const showRestore = computed(() => Boolean(props.range));
    const spans = computed(() => pickTrendSpansByFilter(pickTrendSpans(props.flow), props.filter));
    /** 框选后只保留范围内 Span，使趋势图随划选收敛到所选时间段 */
    const visibleSpans = computed(() => filterSpansByTimeRange(spans.value, props.range));
    const buckets = computed(() =>
      buildTrendBuckets(
        visibleSpans.value,
        resolveBucketCount(plotWidth.value, visibleSpans.value.length),
        props.aggregate
      )
    );
    const hasData = computed(() => buckets.value.length > 0);
    const panelShow = computed(() => activeBucketIndex.value >= 0 && activeSeries.value !== null);
    /** hover 序列是否为「总 Token」，用于切换面板类型 */
    const isTokenSeries = computed(() => activeSeries.value === 'token');
    /** 当前桶时间段内的非 Agent Span，作为面板统计口径；剪掉 childs 避免面板按 childs 递归重复统计 */
    const bucketFlow = computed(() => {
      const index = activeBucketIndex.value;
      const list = buckets.value;
      if (!panelShow.value || !list[index]) return [];
      return stripSpanChilds(pickBucketSpans(visibleSpans.value, list[index], index === list.length - 1));
    });
    const options = computed(() => {
      const list = buckets.value;
      const times = list.map(item => dayjs(item.time / 1000).format('HH:mm:ss'));
      const durations = props.visible.duration ? list.map(item => item.duration) : [];
      const tokens = props.visible.token ? list.map(item => item.tokens) : [];
      const durationAxisMin = resolveAxisMin(durations);
      const tokenAxisMin = resolveAxisMin(tokens);
      /** Y 轴标签区宽度：按两侧可见序列的最长刻度文案动态计算，避免长文案被裁切 */
      const axisWidth = resolveAxisWidth(durations, tokens);

      const axisLabel = {
        color: AXIS_LABEL_COLOR,
        fontSize: 12,
        fontFamily: 'Arial, sans-serif',
        hideOverlap: true,
      };

      return {
        animation: false,
        grid: [
          { left: axisWidth, right: 0, top: GRID_TOP_PADDING, height: PLOT_HEIGHT, containLabel: false },
          {
            left: axisWidth,
            right: 0,
            top: GRID_TOP_PADDING + PLOT_HEIGHT + PLOT_GAP,
            height: PLOT_HEIGHT,
            containLabel: false,
          },
        ],
        xAxis: [
          {
            type: 'category',
            gridIndex: 0,
            data: times,
            boundaryGap: true,
            // 两块接缝处不画线，仅保留 4px 留白分隔
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
          },
          {
            type: 'category',
            gridIndex: 1,
            data: times,
            boundaryGap: true,
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { ...axisLabel, margin: 8 },
          },
        ],
        yAxis: [
          {
            type: 'value',
            gridIndex: 0,
            min: durationAxisMin,
            max: 'dataMax',
            splitNumber: 4,
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: true, lineStyle: { color: GRID_LINE_COLOR } },
            axisLabel: { ...axisLabel, formatter: (value: number) => formatDuration(value || 0, '', 0) },
          },
          {
            type: 'value',
            gridIndex: 1,
            inverse: true,
            min: tokenAxisMin,
            max: 'dataMax',
            splitNumber: 2,
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: true, lineStyle: { color: GRID_LINE_COLOR } },
            axisLabel: { ...axisLabel, formatter: (value: number) => formatCompactToken(value || 0) },
          },
        ],
        brush: {
          xAxisIndex: 'all',
          seriesIndex: 'all',
          brushLink: 'all',
          brushType: 'lineX',
          brushMode: 'single',
          transformable: true,
          brushStyle: {
            color: 'rgba(58, 132, 255, 0.12)',
            borderColor: '#3a84ff',
            borderWidth: 1,
            borderType: 'dashed',
          },
          outOfBrush: { colorAlpha: 0.2 },
          inBrush: { colorAlpha: 1 },
        },
        toolbox: { show: false, feature: { brush: { type: ['lineX', 'clear'] } } },
        series: [
          {
            name: t('耗时'),
            type: 'bar',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: durations,
            barCategoryGap: `${BUCKET_GAP}px`,
            barMinWidth: MIN_BUCKET_WIDTH,
            barMaxWidth: MAX_BUCKET_WIDTH,
            itemStyle: { color: DURATION_COLOR },
            emphasis: { itemStyle: { color: DURATION_EMPHASIS_COLOR } },
          },
          {
            name: t('总 Token'),
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: tokens,
            barCategoryGap: `${BUCKET_GAP}px`,
            barMinWidth: MIN_BUCKET_WIDTH,
            barMaxWidth: MAX_BUCKET_WIDTH,
            itemStyle: { color: TOKEN_COLOR },
            emphasis: { itemStyle: { color: TOKEN_EMPHASIS_COLOR } },
          },
        ],
      };
    });

    /** 激活 brush 光标，使框选成为默认操作（与监控趋势图一致） */
    const enableBrush = () => {
      const instance = chartRef.value?.chart;
      if (!instance || instance.isDisposed() || !hasData.value) return;
      instance.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'brush',
        brushOption: { brushType: 'lineX', brushMode: 'single' },
      });
    };

    /** 框选结束：把分类轴下标区间换算为微秒时间范围，交外层同步趋势图与 Span 列表 */
    const handleBrushEnd = (event: { areas?: { coordRange?: number[] }[] }) => {
      const range = resolveBucketTimeRange(buckets.value, event?.areas?.[0]?.coordRange);
      if (range) emit('select', range);
    };

    const handleRestore = () => {
      const instance = chartRef.value?.chart;
      if (instance && !instance.isDisposed()) {
        instance.dispatchAction({ type: 'brush', areas: [] });
      }
      emit('select', null);
      nextTick(enableBrush);
    };

    /** 宽度变化重算桶数（桶数变化会重建 options，需重新激活 brush） */
    const syncPlotWidth = (width: number) => {
      const next = Math.max(0, width - AXIS_WIDTH);
      if (next === plotWidth.value) return;
      plotWidth.value = next;
    };

    const clearPanelHideTimer = () => {
      if (panelHideTimer) {
        window.clearTimeout(panelHideTimer);
        panelHideTimer = 0;
      }
    };

    const clearPanelShowTimer = () => {
      if (panelShowTimer) {
        window.clearTimeout(panelShowTimer);
        panelShowTimer = 0;
      }
      pendingBucketIndex = -1;
      pendingSeriesKey = null;
    };

    /** 收起统计面板 */
    const hidePanel = () => {
      clearPanelHideTimer();
      clearPanelShowTimer();
      activeBucketIndex.value = -1;
      activeSeries.value = null;
    };

    /** 从柱子移开后延迟收起，允许鼠标移入面板继续操作 */
    const scheduleHidePanel = () => {
      clearPanelHideTimer();
      clearPanelShowTimer();
      panelHideTimer = window.setTimeout(hidePanel, PANEL_HIDE_DELAY);
    };

    /** 依据桶柱在画布上的像素位置，把锚点定位到柱体中心，耗时柱面板向上展开、总 Token 柱面板向下展开 */
    const syncAnchorPosition = (index: number, seriesIndex: number, key: LlmTrendSeriesKey) => {
      const instance = chartRef.value?.chart;
      if (!instance || instance.isDisposed()) return;
      // convertToPixel 返回画布坐标，画布与容器左上角对齐；仅取横向的桶中心
      const [x] = instance.convertToPixel({ xAxisIndex: seriesIndex, yAxisIndex: seriesIndex }, [index, 0]) as number[];
      const height = instance.getHeight();
      const isToken = key === 'token';
      panelPlacement.value = isToken ? 'bottom' : 'top';
      anchorStyle.value = { left: `${x}px`, top: isToken ? `${height}px` : '0px' };
      const rect = instance.getDom().getBoundingClientRect();
      panelMaxHeight.value = isToken
        ? Math.max(200, window.innerHeight - rect.top - height - PANEL_OFFSET - 16)
        : Math.max(200, rect.top - PANEL_OFFSET - 16);
    };

    /**
     * 按当前展开方向重算面板位置。
     * bkui Popover 内部不监听 placement，且不传参调用时方向会退化为默认 bottom，
     * 因此这里显式带上 placement（offset / padding 保持组件默认值，只覆盖方向）。
     */
    const repositionPanel = () => {
      popoverRef.value?.updatePopover?.(null, {
        placement: panelPlacement.value,
        offset: PANEL_OFFSET,
        padding: 0,
        arrow: true,
      });
    };

    /** seriesIndex 0 为耗时、1 为总 Token，其余或非法下标不弹面板 */
    const resolveSeriesKey = (seriesIndex?: number): LlmTrendSeriesKey | null => {
      if (seriesIndex === 0) return 'duration';
      if (seriesIndex === 1) return 'token';
      return null;
    };

    /** 在图表上按下鼠标即进入框选，期间划过桶柱不再弹出面板 */
    const handleChartMouseDown = () => {
      isPointerDown.value = true;
      hidePanel();
    };

    /** 松开鼠标（含图表外松开）解除框选态 */
    const handleWindowMouseUp = () => {
      isPointerDown.value = false;
    };

    const handleBarMouseOver = (event: { dataIndex?: number; seriesIndex?: number }) => {
      // 框选拖拽过程中划过桶柱不弹面板
      if (isPointerDown.value) return;
      const key = resolveSeriesKey(event?.seriesIndex);
      if (!key || typeof event.dataIndex !== 'number') return;
      clearPanelHideTimer();
      if (activeBucketIndex.value === event.dataIndex && activeSeries.value === key) return;
      const index = event.dataIndex;
      const seriesIndex = event.seriesIndex as number;
      // 同一柱子仍在延迟等待中，重复 mouseover 不重置计时
      if (!panelShow.value && pendingBucketIndex === index && pendingSeriesKey === key) return;
      clearPanelShowTimer();
      const show = () => {
        panelShowTimer = 0;
        pendingBucketIndex = -1;
        pendingSeriesKey = null;
        activeBucketIndex.value = index;
        activeSeries.value = key;
        syncAnchorPosition(index, seriesIndex, key);
        nextTick(repositionPanel);
      };
      // 已有面板展开时切换柱子无需再延迟，避免鼠标在柱间移动时面板闪烁
      if (panelShow.value) {
        show();
      } else {
        pendingBucketIndex = index;
        pendingSeriesKey = key;
        panelShowTimer = window.setTimeout(show, PANEL_SHOW_DELAY);
      }
    };

    const handleBarMouseOut = (event: { seriesIndex?: number }) => {
      if (!resolveSeriesKey(event?.seriesIndex)) return;
      scheduleHidePanel();
    };

    const handleStatsLocate = (spanId: string) => {
      hidePanel();
      emit('locate', spanId);
    };

    const handleStatsViewDetail = (spanId: string) => {
      const row = findSpanRowView(bucketFlow.value, spanId);
      hidePanel();
      if (row) emit('view-detail', row);
    };

    onMounted(() => {
      const el = wrapRef.value;
      if (!el) return;
      resizeObserver = new ResizeObserver(() => syncPlotWidth(el.clientWidth));
      resizeObserver.observe(el);
      syncPlotWidth(el.clientWidth);
      // 在图表外松开同样要解除框选态，故监听 window
      window.addEventListener('mouseup', handleWindowMouseUp);
    });

    onBeforeUnmount(() => {
      resizeObserver?.disconnect();
      clearPanelHideTimer();
      clearPanelShowTimer();
      window.removeEventListener('mouseup', handleWindowMouseUp);
    });

    // 数据、图例或框选范围变化后桶重建，既有的 hover 面板锚点已失效，需先收起
    watch(
      options,
      () => {
        hidePanel();
        nextTick(enableBrush);
      },
      { flush: 'post' }
    );

    return {
      t,
      chartRef,
      wrapRef,
      popoverRef,
      hasData,
      showRestore,
      panelShow,
      isTokenSeries,
      anchorStyle,
      panelMaxHeight,
      panelPlacement,
      bucketFlow,
      options,
      handleBrushEnd,
      handleRestore,
      enableBrush,
      handleChartMouseDown,
      repositionPanel,
      handleBarMouseOver,
      handleBarMouseOut,
      hidePanel,
      clearPanelHideTimer,
      scheduleHidePanel,
      handleStatsLocate,
      handleStatsViewDetail,
    };
  },
  render() {
    return (
      <div class='llm-trend-chart-wrap'>
        {this.hasData ? (
          <div
            ref='wrap'
            class='llm-trend-chart'
            onMousedown={this.handleChartMouseDown}
          >
            <VueEcharts
              ref='chart'
              initOptions={{ renderer: 'canvas' }}
              option={this.options}
              style={{ height: `${CHART_HEIGHT}px` }}
              autoresize
              updateOptions={{ notMerge: true }}
              onBrushEnd={this.handleBrushEnd}
              onFinished={() => nextTick(this.enableBrush)}
              onGlobalout={this.scheduleHidePanel}
              onMouseout={this.handleBarMouseOut}
              onMouseover={this.handleBarMouseOver}
            />
            {/* 以桶柱心为参考元素，hover 耗时 / 总 Token 柱时弹出该桶时间段内的对应统计面板 */}
            <Popover
              ref='popover'
              boundary='body'
              extCls='llm-trend-stats-popover'
              clickContentAutoHide={false}
              isShow={this.panelShow}
              padding={0}
              placement={this.panelPlacement}
              theme='light'
              width={680}
              trigger='manual'
              onAfterShow={this.repositionPanel}
              v-slots={{
                default: () => (
                  <span
                    style={this.anchorStyle}
                    class='llm-trend-stats-anchor'
                  />
                ),
                content: () => (
                  <div
                    class='llm-trend-stats-panel'
                    onMouseenter={this.clearPanelHideTimer}
                    onMouseleave={this.scheduleHidePanel}
                  >
                    {this.isTokenSeries ? (
                      <TokenStatsPanel
                        flow={this.bucketFlow}
                        maxHeight={this.panelMaxHeight}
                        flowLoaded
                        hideEmptyTab
                        onLocate={this.handleStatsLocate}
                        onView-detail={this.handleStatsViewDetail}
                      />
                    ) : (
                      <DurationStatsPanel
                        flow={this.bucketFlow}
                        maxHeight={this.panelMaxHeight}
                        flowLoaded
                        hideEmptyTab
                        onLocate={this.handleStatsLocate}
                        onView-detail={this.handleStatsViewDetail}
                      />
                    )}
                  </div>
                ),
              }}
            />
          </div>
        ) : this.flowLoading ? null : (
          <div class='llm-trend-empty'>{this.t('暂无数据')}</div>
        )}
        {/* 复位按钮放在图表外层：框选范围内无数据时图表被空态替换，仍需保留复位入口 */}
        {this.showRestore && (
          <span
            class='llm-trend-restore'
            onClick={this.handleRestore}
          >
            {this.t('复位')}
          </span>
        )}
      </div>
    );
  },
});
