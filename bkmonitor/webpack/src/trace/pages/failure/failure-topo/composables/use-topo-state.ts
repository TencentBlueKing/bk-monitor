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

/**
 * @file 拓扑图核心状态管理 Composable
 * @description 负责管理 FailureTopo 组件的共享响应式状态（不含拓扑数据缓存）
 *
 * ## 职责
 * - 管理所有 inject / computed / ref / shallowRef 声明
 * - 管理 DOM ref 引用
 * - 管理 UI 控制状态、数据缓存、tooltip 状态、时间轴状态等
 * - 管理 Graph 实例和 Tooltip 插件实例的 shallowRef
 *
 * ## 相关 composable
 * - use-topo-data: 数据获取与布局计算
 * - use-topo-interaction: 交互 handler
 * - use-topo-timeline: 时间轴播放
 * - use-topo-tooltip: Tooltip 相关逻辑
 * - use-topo-graph: Graph 初始化 + 事件绑定 + resize + 生命周期
 */

import { type Ref, type ShallowRef, computed, ref as deepRef, inject, shallowRef, toRef } from 'vue';

import { useI18n } from 'vue-i18n';

import { incidentAlarmDetailInject } from '../../composables/use-alarm-detail';
import { useIncidentInject } from '../../utils';

import type { SpaceInfo } from '../../../../components/data-access';
import type { G6TooltipInstance } from '../types/composable';
import type { ComboLabelPoint, DetailType, ErrorData, TooltipType } from '../types/g6';
import type { IEdge, IEntity, IncidentDetailData, IncidentResults, ITopoNode } from '../types/topo';
import type { Graph } from '@antv/g6';

// ============================================================================
// 组件实例薄接口（仅覆盖本模块实际调用的方法 / 属性）
// ============================================================================

/** 资源图组件暴露面：关闭资源图自身 tooltip */
export type ResourceGraphExpose = {
  hideToolTips?: () => void;
};

/** Vue Tooltip 组件暴露面：交互侧调用 hide，G6 getContent 读取 $el */
export type TooltipCompExpose = {
  $el?: HTMLElement;
  hide?: () => void;
};

// ============================================================================
// Props 类型
// ============================================================================

export interface TopoStateProps {
  isCollapsed: boolean;
  /** 左侧菜单选中的节点 ID 列表（Vue Array prop 可能为 number/string） */
  selectNode: ReadonlyArray<number | string>;
}

// ============================================================================
// Composable
// ============================================================================

export type UseTopoStateReturn = ReturnType<typeof useTopoState>;

export function useTopoState(props: TopoStateProps) {
  const { t } = useI18n();

  // ---------------------------------------------------------------------------
  // Inject — 从父组件注入的共享数据
  // ---------------------------------------------------------------------------

  /** 当前选中的业务 ID 列表，由上层 DataAccess 提供 */
  const bkzIds = inject<Ref<string[]>>('bkzIds');
  /** 事件详情数据，由 FailureDetail 页面注入 */
  const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
  /** 事件各数据源的分析结果状态，由 FailureDetail 页面注入 */
  const incidentResults = inject<Ref<IncidentResults>>('incidentResults');
  /** 当前事件 ID，用于接口请求参数 */
  const incidentId = useIncidentInject();
  /** 告警详情数据更新方法，点击节点时同步刷新右侧告警面板 */
  const { updateAlarmDetailData } = incidentAlarmDetailInject();

  // ---------------------------------------------------------------------------
  // Inject 派生 computed
  // ---------------------------------------------------------------------------

  const incidentDetailData: Ref<IncidentDetailData> = computed(() => incidentDetail.value);

  /** 根据 bkzIds 构建空间列表，传入 DataAccess 组件以获取各业务的数据权限 */
  const dataAccessSpaceList = computed<SpaceInfo[]>(() => {
    const bizId = bkzIds?.value?.[0];
    if (!bizId) return [];
    // current_snapshot 在 IncidentDetailData 中为宽松 Record，此处收窄到 bk_biz_ids 结构
    const snap = incidentDetailData.value?.current_snapshot as
      | undefined
      | { bk_biz_ids?: Array<{ bk_biz_id: number; bk_biz_name?: string }> };
    const bizName = snap?.bk_biz_ids?.find(({ bk_biz_id }) => String(bk_biz_id) === String(bizId))?.bk_biz_name;
    return [{ bk_biz_id: Number(bizId), space_name: bizName || String(bizId), space_id: Number(bizId) }];
  });

  /** 拓扑数据状态 */
  const topoStatus = computed(() => {
    if (incidentResults.value.incident_topology) {
      if (
        incidentResults.value.incident_topology.enabled &&
        incidentResults.value.incident_topology.status === 'finished'
      ) {
        return 'normal';
      }
      if (
        incidentResults.value.incident_topology.enabled &&
        incidentResults.value.incident_topology.status === 'canceled'
      ) {
        return 'nodata';
      }
      return 'empty';
    }
    return null;
  });

  // ---------------------------------------------------------------------------
  // DOM Ref — 模板引用
  // ---------------------------------------------------------------------------

  /** 拓扑图整体容器 div，用于监听 resize 和计算画布尺寸 */
  const wrapRef = deepRef<HTMLDivElement>();
  /** G6 画布挂载的 div，initGraph 时作为 container 传入 */
  const topoGraphRef = deepRef<HTMLDivElement>(null);
  /** G6 画布 DOM 容器（不是 Graph 实例），用于获取画布真实宽高和 CSS 操作 */
  const graphRef = deepRef<HTMLElement>(null);
  /** 拓扑工具栏组件实例引用 */
  const topoTools = deepRef(null);
  /** Tooltip 弹层组件实例引用，用于手动控制显隐 */
  const tooltipCompRef = deepRef<TooltipCompExpose>();
  /** 右侧资源图组件实例引用，用于调用资源图方法 */
  const resourceGraphRef = deepRef<ResourceGraphExpose>();

  // ---------------------------------------------------------------------------
  // G6 实例 Ref — shallowRef（在 use-topo-graph 中赋值）
  // ---------------------------------------------------------------------------

  /** G6 Graph 实例，在 use-topo-graph 的 initGraph 中赋值，其他 composable 通过 .value 访问 */
  const graphInstanceRef = shallowRef<Graph>() as ShallowRef<Graph | undefined>;
  /** G6 Tooltip 插件实例，在 use-topo-graph 的 registerCustomTooltip 中赋值 */
  const g6TooltipRef = shallowRef<G6TooltipInstance>() as ShallowRef<G6TooltipInstance | undefined>;

  // ---------------------------------------------------------------------------
  // 核心状态
  // ---------------------------------------------------------------------------

  /** 缓存 resize render 后执行的回调，主要用于点击播放前收起右侧面板时延迟执行 */
  const resizeCacheCallback = deepRef<(() => void) | null>(null);
  /** 边/节点详情信息，传入 Tooltip 组件展示 */
  const detailInfo = deepRef<ITopoNode | Record<string, unknown>>({});
  /** 标记当前是否在 resize 过程中，防止 resize 与 render 冲突 */
  const cacheResize = deepRef<boolean>(false);
  /** 自动刷新间隔时间（毫秒），默认 5 分钟，由工具栏的刷新时间设置组件修改 */
  const refreshTime = deepRef<number>(5 * 60 * 1000);

  /** 缓存根 combo 拖拽后 label 的坐标，拖拽结束时更新 combo label 位置 */
  const rootComboMovePoint = deepRef<ComboLabelPoint>({ x: null, y: null });

  // ---------------------------------------------------------------------------
  // UI 控制状态
  // ---------------------------------------------------------------------------

  /** 数据加载中标记，请求拓扑数据时置 true */
  const loading = deepRef<boolean>(false);
  /** 画布数据获取错误信息 */
  const errorData = deepRef<ErrorData>({
    isError: false,
    isNoData: false,
    msg: '',
  });
  /** 是否已完成首次渲染（含 detail 区域），用于控制渲染后动画播放等逻辑 */
  const isRenderComplete = deepRef<boolean>(false);
  /** 缩放级别数值，值 / 10 为真实缩放比（如 10 → 1.0，5 → 0.5），工具栏滑块控制 */
  const zoomValue = deepRef<number>(10);
  /** 是否显示图例面板，持久化到 localStorage */
  const showLegend = deepRef<boolean>(localStorage.getItem('showLegend') === 'true');
  /** 是否显示右侧服务概览面板 */
  const showServiceOverview = deepRef<boolean>(false);
  /** 是否显示右侧资源图面板 */
  const showResourceGraph = deepRef<boolean>(false);

  // ---------------------------------------------------------------------------
  // Tooltip 状态（逻辑在 use-topo-tooltip，状态仍在此声明）
  // ---------------------------------------------------------------------------

  /** 当前 hover/click 的节点模型数据，单个节点或聚合节点数组 */
  const tooltipsModel = shallowRef<ITopoNode | ITopoNode[]>();
  /** 当前 hover/click 的边数据 */
  const tooltipsEdge: Ref<IEdge> = shallowRef();
  /** 边详情数据，在边概览 Tooltip 中展示 */
  const edgeDetail: Ref<IEdge> = shallowRef();
  /** 是否通过 click（而非 hover）触发边 Tooltip，click 时 Tooltip 不自动消失 */
  const isClickEdgeItem = deepRef<boolean>(false);
  /** 当前 hover/click 的节点详情数据，在节点概览 Tooltip 中展示 */
  const nodeDetail: Ref<ITopoNode> = deepRef(null);
  /** 当前选中节点关联的所有边数据，在 Tooltip 中展示关联关系 */
  const curLinkedEdges: Ref<IEdge[]> = shallowRef();
  /** Tooltip 类型：'node' 或 'edge'，决定展示哪种 Tooltip 组件 */
  const tooltipsType = deepRef<TooltipType>('node');
  /** 详情面板类型：'node' 或 'edge'，决定详情面板展示内容 */
  const detailType = deepRef<DetailType>('node');
  /** 是否在 Tooltip 中展示资源从属信息（关联资源视图） */
  const showViewResource = deepRef<boolean>(true);

  // ---------------------------------------------------------------------------
  // 时间轴状态（逻辑在 use-topo-timeline，状态仍在此声明）
  // ---------------------------------------------------------------------------

  /** 当前停留帧索引，0 = 最早帧，越大越新（末帧为最新）；由 slider 和播放动画控制 */
  const timelinePosition = deepRef<number>(0);
  /** 是否正在播放时间轴动画（自动逐帧推进） */
  const isPlay = deepRef<boolean>(false);

  // ---------------------------------------------------------------------------
  // 反馈 / 交互状态
  // ---------------------------------------------------------------------------

  /** 是否显示根因反馈弹窗 */
  const feedbackCauseShow = deepRef<boolean>(false);
  /** 反馈弹窗的模型数据，包含被反馈的实体信息 */
  const feedbackModel: Ref<{ entity: IEntity }> = deepRef(null);
  /** 当前选中的节点实体 ID，用于资源图和详情面板的关联查询 */
  const nodeEntityId = deepRef<string>('');
  /** 当前选中的节点实体名称，用于 Tooltip 标题显示 */
  const nodeEntityName = deepRef<string>('');
  /** 当前选中资源图的节点 ID，用于定位资源图中的对应节点 */
  const resourceNodeId = deepRef<string>('');
  /** 当前选中资源图的边 ID，用于定位资源图中的对应边 */
  const resourceEdgeId = deepRef<string>('');

  // ---------------------------------------------------------------------------
  // Props 派生（保持响应式，供 interaction / watch 使用）
  // ---------------------------------------------------------------------------

  /** 左侧菜单选中的节点 ID 列表 */
  const selectNode = toRef(props, 'selectNode');

  // ---------------------------------------------------------------------------
  // Props 派生 computed
  // ---------------------------------------------------------------------------

  /** 计算拓扑图容器宽度，根据右侧面板（资源图 410px / 服务概览 360px）动态减去占用宽度 */
  const getTopoWidth = computed(() => {
    let width = 0;
    if (showResourceGraph.value) width += 410;
    if (showServiceOverview.value) width += 360;
    return width ? `calc(100% - ${width}px)` : `calc(100% - ${1}px)`;
  });

  return {
    // hooks — 从父组件注入或派生的共享数据
    t,
    bkzIds,
    incidentDetailData,
    incidentId,
    updateAlarmDetailData,
    // props
    selectNode,
    // DOM refs — 模板引用
    wrapRef,
    topoGraphRef,
    graphRef,
    topoTools,
    tooltipCompRef,
    resourceGraphRef,
    // G6 实例 refs — shallowRef（在 use-topo-graph 中赋值）
    graphInstanceRef,
    g6TooltipRef,
    // core — 核心运行状态
    resizeCacheCallback,
    detailInfo,
    cacheResize,
    refreshTime,
    rootComboMovePoint,
    // UI — 界面控制状态
    loading,
    errorData,
    isRenderComplete,
    zoomValue,
    showLegend,
    showServiceOverview,
    showResourceGraph,
    // tooltip — Tooltip 状态
    tooltipsModel,
    tooltipsEdge,
    edgeDetail,
    isClickEdgeItem,
    nodeDetail,
    curLinkedEdges,
    tooltipsType,
    detailType,
    showViewResource,
    // timeline — 时间轴状态
    timelinePosition,
    isPlay,
    // feedback — 反馈 / 交互状态
    feedbackCauseShow,
    feedbackModel,
    nodeEntityId,
    nodeEntityName,
    resourceNodeId,
    resourceEdgeId,
    // computed — 派生计算属性
    dataAccessSpaceList,
    topoStatus,
    getTopoWidth,
  };
}
