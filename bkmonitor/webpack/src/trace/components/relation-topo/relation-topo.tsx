/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
  defineComponent,
  inject,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  toRefs,
  watch,
} from 'vue';
import { useI18n } from 'vue-i18n';

import G6, { type Graph, type IEdge, type INode } from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Alert, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { traceDiagram } from 'monitor-api/modules/apm_trace';

import { formatDuration } from '../../components/trace-view/utils/date';
import GraphTools from '../../plugins/charts/flame-graph/graph-tools/graph-tools';
import ViewLegend from '../../plugins/charts/view-legend/view-legend';
import BlueCollapseIcon from '../../static/img/blue-collapse.svg';
import BlueExpandIcon from '../../static/img/blue-expand.svg';
import CollapseIcon from '../../static/img/collapse.svg';
import ExpandIcon from '../../static/img/expand.svg';
import { useTraceStore } from '../../store/modules/trace';
import {
  COMPARE_ADDED_COLOR,
  COMPARE_REMOVED_COLOR,
  getDiffPercentColor,
  getSingleDiffColor,
  updateTemporaryCompareTrace,
} from '../../utils/compare';
import transformTraceTree from '../trace-view/model/transform-trace-data';

import type { ITopoNode } from '../../typings';
import type { Span } from '../trace-view/typings';

import './relation-topo.scss';

interface IState {
  keyword: string[];
  canvasWidth: number;
  canvasHeight: number;
  zoomValue: number;
  minZoomVal: number;
  maxZoomVal: number;
  matchesNodeIds: string[];
  curMathesFocusIndex: number;
  curSelectedSpanId: string;
  isCompareView: boolean;
}

const RelationTopoProps = {
  compareTraceID: {
    type: String,
    default: '',
  },
  updateMatchedSpanIds: Function as PropType<(count: number) => void>,
};

export default defineComponent({
  name: 'RelationTopo',
  props: RelationTopoProps,
  emits: ['showSpanDetail', 'spanListChange', 'compareSpanListChange', 'update:loading'],
  setup(props, { emit, expose }) {
    let graph: any = null;
    const { t } = useI18n();
    const store = useTraceStore();

    const state = reactive<IState>({
      /** 搜索关键字 */
      keyword: [],
      /** 画布宽度 */
      canvasWidth: 0,
      /** 画布高度 */
      canvasHeight: 0,
      /** 缩放比例 */
      zoomValue: 100,
      /** 缩放滑动条最小值 */
      minZoomVal: 0.1,
      /** 缩放滑动条最大值 */
      maxZoomVal: 1,
      /** 搜索匹配节点id */
      matchesNodeIds: [],
      /** 当前选中展开详情的 spanID */
      curSelectedSpanId: '',
      /** 定位搜索结果当前高亮索引 */
      curMathesFocusIndex: -1,
      isCompareView: false,
    });
    const graphContainer = ref<Element>();
    const emptyText = ref<string>('加载中...');
    const empty = ref<boolean>(true);
    const isDbClickZoom = ref<boolean>(false);
    /** 是否显示缩略图 */
    const showThumbnail = ref<boolean>(false);
    /** 是否显示图例 */
    const showLegend = ref<boolean>(false);
    const graphToolsRect = ref({ width: 0, height: 0 });
    /** 对比错误信息提示 */
    const showCompareError = ref<boolean>(false);
    const topoThumbnailRef = ref<HTMLDivElement>();
    const topoGraphContent = ref<HTMLDivElement>();
    const compareWarningAlert = ref(''); // 对比错误提示警告
    const isShowDuration = ref(true); // 节点是否显示耗时
    let compareData = {};
    let compareSpans = []; // 对比 spans
    let compareOriginalSpans = []; // 对比 original_data spans

    const traceData = computed(() => store.traceData);
    /** 节点 */
    const nodes = computed(() => traceData.value.topo_nodes || []);
    /** 节点间的关系边 */
    const edges = computed(() => traceData.value?.topo_relation || []);
    /** 起始节点 */
    const rootNodeId = computed(() => traceData.value?.trace_info?.root_span_id || '');
    const graphData = computed(() => ({
      nodes: nodes.value || [],
      edges: edges.value || [],
    }));
    const graphLayout = computed(() => ({
      type: 'dagre',
      rankdir: 'TB', // 布局的方向 从上至下
      nodesep: 70, // 节点的水平间距
      ranksep: 30, // 相邻层间距
      workerEnabled: true,
      workerScriptURL: 'https://unpkg.com/@antv/layout@0.3.20/dist/layout.min.js',
      // workerScriptURL: 'https://unpkg.com/@antv/layout@1.2.0/dist/index.min.js'

      // type: 'dagre',
      // rankdir: 'LR', // 布局的方向 从左至右
      // nodesep: 16, // 节点的间距
      // ranksep: 80, // 层间距
      // workerEnabled: true,
      // workerScriptURL: 'https://unpkg.com/@antv/layout@0.3.20/dist/layout.min.js'
      // // workerScriptURL: 'https://unpkg.com/@antv/layout@1.2.0/dist/index.min.js'
    }));
    const ellipsisDirection = computed(() => store.ellipsisDirection);

    const isFullscreen = inject('isFullscreen', false);

    watch(ellipsisDirection, () => {
      // 切换头部/尾部显示
      graph.getNodes().forEach((node: any) => {
        const model = node.getModel();
        const { group } = node._cfg;
        parseEndPointName(model, group);
        parseServiceName(model, group);
      });
    });
    watch(
      () => nodes.value,
      () => {
        graph?.destroy();
        initGraph();
      },
      { deep: true }
    );
    watch(
      () => [store.loading, store.traceViewFilters],
      ([loading, filters]) => {
        showThumbnail.value = false;
        showLegend.value = false;
        if (loading && showCompareError.value) {
          handleCloseCompareMessage();
        }

        if (isShowDuration.value !== (filters as string[]).includes('duration')) {
          isShowDuration.value = (filters as string[]).includes('duration');
          graph?.destroy();
          initGraph();
        }
      }
    );

    /** 拓扑图事件监听 */
    const bindListener = (graph: Graph) => {
      graph.on('node:mouseenter', e => {
        const { id } = e.item.get('model');
        const activeNode = graph.getNodes().find((node: any) => node.get('model').id === id);
        activeNode && graph.setItemState(activeNode, 'active', true);
      });

      graph.on('node:mouseleave', () => {
        graph.getNodes().forEach(node => graph.setItemState(node, 'active', false));
      });

      graph.on('node:click', e => {
        // const span = e.item?.get('model');
        // state.curSelectedSpanId = span.id;
        // const allNodes = graph?.getNodes() || [];
        // allNodes.forEach((node: { getModel: () => any; }) => {
        //   const model = node.getModel();
        //   graph?.setItemState(node, 'selected', model.id === span.id);
        // });
        // handleSpanDetailChange(span);

        const span = e.item?.get('model');
        const { spans, operationName, id, collapsed } = span;
        state.curSelectedSpanId = id;
        const allNodes = graph?.getNodes() || [];
        allNodes.forEach((node: { getModel: () => any }) => {
          const model = node.getModel();
          graph?.setItemState(node as INode, 'selected', model.id === id);
        });
        if (collapsed) {
          // 折叠节点 下钻span-list展开
          emit('spanListChange', spans, `${operationName} x ${spans.length}`);
        } else {
          if (state.isCompareView) {
            // 对比模式下从对比spans集合获取完整的span信息
            const data = compareSpans.find(item => item.span_id === span.id);
            emit('showSpanDetail', data);
          } else {
            emit('showSpanDetail', id);
          }
        }
      });

      graph.on('collapse-icon:click', e => {
        // 阻止冒泡
        e.stopPropagation();

        const node = e.item as any;
        const isCollapse = node.hasState('collapse'); // 当前节点是否已折叠

        // 递归展开/收起子节点
        const hideChildNodes = (nodeList: any) => {
          nodeList.forEach((nodeItem: any) => {
            isCollapse ? nodeItem.show() : nodeItem.hide();
            nodeItem?.getOutEdges().forEach((edgeItem: any) => (isCollapse ? edgeItem.show() : edgeItem.hide()));
            if (nodeItem?.getNeighbors('target').length) {
              graph?.setItemState(nodeItem, 'collapse', !isCollapse);
              hideChildNodes(nodeItem?.getNeighbors('target'));
            }
          });
        };

        // 展开/收起当前点击节点所有边
        node?.getOutEdges().forEach((item: any) => (isCollapse ? item.show() : item.hide()));
        hideChildNodes(node?.getNeighbors('target'));
        graph?.setItemState(node, 'collapse', !isCollapse);
      });

      graph.on('collapse-icon:mouseenter', e => {
        const node = e.item as any;
        const isCollapse = node.hasState('collapse'); // 当前节点是否已折叠
        graph?.setItemState(node, 'collapseHover', isCollapse ? BlueExpandIcon : BlueCollapseIcon);
      });

      graph.on('collapse-icon:mouseleave', e => {
        const node = e.item as any;
        const isCollapse = node.hasState('collapse'); // 当前节点是否已折叠
        graph?.setItemState(node, 'collapseHover', isCollapse ? ExpandIcon : CollapseIcon);
      });

      graph.on('afterrender', () => {
        if (isDbClickZoom.value) {
          isDbClickZoom.value = false;
        } else {
          // TODO 先默认将整体缩放至80% 后续根据宽度优化初始缩放比例
          graph.zoomTo(0.8, { x: state.canvasWidth / 2, y: state.canvasHeight / 2 });
          state.zoomValue = 80;

          handleHighlightNode();
          /** 画布移动到起点节点 */
          rootNodeId.value && graph.focusItem(rootNodeId.value);
          // graph.translate(- graph.getWidth() / 2 + 40, 0);
          graph.translate(-100, -graph.getHeight() / 2 + 40);
          empty.value = false;
        }
        setTimeout(() => {
          if (!showLegend.value && !showThumbnail.value) {
            showThumbnail.value = true;
            graphToolsRect.value = {
              width: 240,
              height: 148,
            };
          }
        }, 500);
      });

      graph.on('wheelzoom', () => {
        state.zoomValue = Math.ceil(graph.getZoom() * 100);
      });

      /** 双击放大 */
      graph.on('dblclick', evt => {
        const { x, y } = evt;
        const ratio = state.zoomValue + 20 > state.maxZoomVal * 100 ? 100 : state.zoomValue + 20;
        graph.zoomTo(ratio / 100, { x, y });
        state.zoomValue = ratio;
        isDbClickZoom.value = true;
      });
    };
    /**
     * @description: 缩放
     * @param { number } ratio 缩放比例
     */
    const handleGraphZoom = (ratio: number) => {
      state.zoomValue = ratio;
      // 以画布中心为圆心放大/缩小
      const { canvasWidth, canvasHeight } = state;
      graph?.zoomTo(ratio / 100, { x: canvasWidth / 2, y: canvasHeight / 2 });
    };
    /** 展示图例 */
    const handleShowLegend = () => {
      showLegend.value = !showLegend.value;
      showThumbnail.value = false;
      if (showLegend.value) {
        graphToolsRect.value = {
          width: 120,
          height: 300,
        };
      }
    };
    /**
     * @description: 绘制自定义节点
     * @param  {Object} cfg 节点的配置项
     * @param  {G.Group} group 图形分组，节点中图形对象的容器
     */
    const drawNode = (cfg: ITopoNode, group: any) => {
      /** 搜索定位当前节点高亮外边框 */
      group.addShape('rect', {
        attrs: {
          x: -12,
          y: -12,
          width: 248,
          height: 72,
          stroke: '',
          radius: 4,
          fill: 'transparent',
        },
        name: 'custom-node-outline',
      });

      /** 节点基础矩形结构 */
      const keyShape = group.addShape('rect', {
        attrs: {
          x: 0,
          y: 0,
          width: 224,
          height: 48,
          stroke: '#DCDEE5',
          radius: 2,
          fill: '#FFFFFF',
          cursor: 'pointer',
        },
        name: 'main-box',
      });

      /** 左侧颜色描边矩形 */
      group.addShape('rect', {
        attrs: {
          x: 0,
          y: 0,
          width: 4,
          height: 48,
          fill: cfg.color,
          radius: 2,
          cursor: 'pointer',
        },
        name: 'left-border-rect',
      });

      let durationRect;
      if (
        // 显示耗时或者对比存在 added 或者 removed 标签的情况下
        isShowDuration.value ||
        (state.isCompareView && ['added', 'removed'].includes(cfg.diff_info?.[cfg.id]?.mark))
      ) {
        /** 耗时背景矩形 */
        durationRect = group.addShape('rect', {
          attrs: {
            fill: '#979BA5',
            radius: 2,
            cursor: 'pointer',
          },
          name: 'duration-container',
        });

        /** 耗时文字 */
        // 对比模式下 added 或 removed 节点 耗时区域显示标签
        const isDiffAdded = state.isCompareView && cfg.diff_info?.[cfg.id]?.mark === 'added';
        const isDiffRemoved = state.isCompareView && cfg.diff_info?.[cfg.id]?.mark === 'removed';
        const durationText = group.addShape('text', {
          attrs: {
            text: isDiffAdded || isDiffRemoved ? cfg.diff_info[cfg.id].mark : `${formatDuration(cfg.duration)}`,
            x: 16,
            y: 14,
            fontSize: 12,
            textAlign: 'left',
            textBaseline: 'middle',
            fill: isDiffAdded ? COMPARE_ADDED_COLOR : isDiffRemoved ? COMPARE_REMOVED_COLOR : '#FFFFFF',
            cursor: 'pointer',
          },
          name: 'duration-text',
        });

        /** 根据耗时文字长度设置其背景矩形长度和位置 */
        const durationBBox = durationText.getBBox();
        durationRect.attr({
          x: 12,
          y: durationBBox.minY - 1,
          width: durationBBox.width + 8,
          height: durationBBox.height + 2,
        });
      }

      let containerWidth = 224;
      /** 折叠节点 显示被折叠的数量 */
      if (cfg.collapsed) {
        const collapsedCircle = group.addShape('circle', {
          attrs: {
            fill: '#A2AFD2',
            cursor: 'pointer',
          },
          name: 'collapsed-container',
        });

        const collapsedText = group.addShape('text', {
          attrs: {
            text: cfg.spans.length,
            x: 210,
            y: 14,
            fontSize: 12,
            textAlign: 'right',
            textBaseline: 'middle',
            fill: '#fff',
            cursor: 'pointer',
          },
          name: 'collapsedText',
        });

        /** 折叠数字长度和位置 */
        const collapsedBBox = collapsedText.getBBox();
        /** 折叠数字背景 */
        collapsedCircle.attr({
          x: collapsedBBox.x + collapsedBBox.width / 2,
          y: 14,
          r: cfg.spans.length > 100 ? 10 : 8,
        });

        containerWidth = collapsedCircle.getBBox().x;
      }

      /** 接口名称文字 */
      let endpointMaxWidth = containerWidth - 12; // 12为间距
      let endpointX = 12;
      if (durationRect) {
        const durationRectBBox = durationRect.getBBox();
        const { x, width } = durationRectBBox;
        endpointMaxWidth = containerWidth - (x + width); // 计算可放置最大宽度
        endpointX += x + width - 6;
      }
      group.addShape('text', {
        attrs: {
          text: fittingString(cfg.operationName, endpointMaxWidth, 12),
          x: endpointX,
          y: 14,
          fontSize: 12,
          textAlign: 'left',
          textBaseline: 'middle',
          fill: cfg.error ? '#EA3636' : '#313238',
          cursor: 'pointer',
        },
        name: 'endpoint-text',
      });

      /** icon */
      group.addShape('image', {
        attrs: {
          x: 12,
          y: 28,
          width: 14,
          height: 14,
          cursor: 'pointer',
          img: cfg.icon,
        },
        name: 'icon',
      });

      /** 服务名称文字 */
      const serviceMaxWidth = 184; // 计算可放置最大宽度
      group.addShape('text', {
        attrs: {
          text: fittingString(cfg.service_name, serviceMaxWidth, 12),
          x: 34,
          y: 40,
          fontSize: 12,
          textAlign: 'left',
          fill: '#979BA5',
          cursor: 'pointer',
        },
        name: 'server-text',
      });

      /** 非叶子节点 需包含展开/收起按钮 */
      if (edges.value?.some(item => item.source === cfg.id)) {
        /** 展开/收起按钮 */
        group.addShape('image', {
          attrs: {
            x: 104,
            y: 40,
            // x: 216,
            // y: 17,
            width: 14,
            height: 14,
            cursor: 'pointer',
            img: CollapseIcon,
          },
          name: 'collapse-icon',
        });
      }

      return keyShape;
    };
    /**
     * @description: 自定义节点 state 状态设置
     * @param  {String} name 状态名称
     * @param  {Object} value 状态值
     * @param  {Node} node 节点
     */
    const setNodeState = (name: string, value: boolean, item: any) => {
      const group = item.get('group');
      const model = item.get('model');
      // 搜索结果定位高亮
      if (name === 'focus') {
        const nodeMainShape = group.find((e: any) => e.get('name') === 'custom-node-outline');
        nodeMainShape.attr({
          fill: value ? 'rgba(255,226,148,0.30)' : 'transparent',
        });
      }
      // 未匹配的搜索结果
      if (name === 'disabled') {
        const nodeMainShape = group.find((e: any) => e.get('name') === 'main-box');
        const defaultNodeFill = state.isCompareView ? model.bgColor : '#FFFFFF';
        nodeMainShape.attr({
          fill: value ? '#FAFBFD' : defaultNodeFill,
          stroke: value ? 'transparent' : '#DCDEE5',
        });

        const leftBorderShape = group.find((e: any) => e.get('name') === 'left-border-rect');
        leftBorderShape.attr({
          opacity: value ? 0.3 : 1,
        });

        if (isShowDuration.value || ['added', 'removed'].includes(model.diff_info?.[model.id]?.mark)) {
          const durationShape = group.find((e: any) => e.get('name') === 'duration-container');
          const isDiffAdded = model.diff_info?.[model.id]?.mark === 'added';
          const isDiffRemoved = model.diff_info?.[model.id]?.mark === 'removed';
          const defaultDurationFill = state.isCompareView
            ? isDiffAdded || isDiffRemoved
              ? '#FFFFFF'
              : '#63656E'
            : '#979BA5';
          durationShape?.attr({
            fill: value ? '#DCDEE5' : defaultDurationFill,
          });
        }

        const endpointShape = group.find((e: any) => e.get('name') === 'endpoint-text');
        const defaultEndpointFill = model.error ? (state.isCompareView ? '#FFFFFF' : '#EA3636') : '#313238';
        endpointShape.attr({
          fill: value ? '#979BA5' : defaultEndpointFill,
        });

        const iconShape = group.find((e: any) => e.get('name') === 'icon');
        iconShape.attr({
          opacity: value ? 0.3 : 1,
        });

        const serverShape = group.find((e: any) => e.get('name') === 'server-text');
        const defaultServiceFill = state.isCompareView ? '#313238' : '#979BA5';
        serverShape.attr({
          fill: value ? '#C4C6CC' : defaultServiceFill,
        });
      }

      if (name === 'active') {
        const nodeMainShape = group.find((e: any) => e.get('name') === 'main-box');
        nodeMainShape.attr({
          shadowColor: value ? '#C4C6CC' : '',
          shadowBlur: value ? 10 : 0,
        });
        parseEndPointName(model, group, value);
        parseServiceName(model, group, value);
      }

      if (name === 'selected') {
        const { id } = model;
        const nodeMainShape = group.find((e: any) => e.get('name') === 'main-box');
        nodeMainShape.attr({
          stroke: value && id === state.curSelectedSpanId ? '#3A84FF' : '#DCDEE5',
        });
      }

      if (name === 'collapse') {
        const iconShape = group.find((e: any) => e.get('name') === 'collapse-icon');
        iconShape.attr({
          img: value ? ExpandIcon : CollapseIcon,
        });
      }

      if (name === 'collapseHover') {
        const iconShape = group.find((e: any) => e.get('name') === 'collapse-icon');
        iconShape.attr({
          img: value,
        });
      }
    };
    /**
     * 计算
     * @param {string} str The origin string
     * @param {number} maxWidth max width
     * @param {number} fontSize font size
     * @return {string} the processed result
     */
    const fittingString = (str: string, maxWidth: number, fontSize: number) => {
      const ellipsis = '...';
      const ellipsisLength = G6.Util.getTextSize(ellipsis, fontSize)[0];
      const isRtl = ellipsisDirection.value === 'rtl';
      let currentWidth = 0;
      let res = str;
      const pattern = /[\u4E00-\u9FA5]+/; // distinguish the Chinese charactors and letters
      const parseStr = isRtl ? str.split('').reverse().join('') : str;
      parseStr
        .split('')
        // .reverse()
        .join('')
        .split('')
        .forEach((letter, i) => {
          if (currentWidth > maxWidth - ellipsisLength) return;
          if (pattern.test(letter)) {
            // Chinese charactors
            currentWidth += fontSize;
          } else {
            // get the width of single letter according to the fontSize
            currentWidth += G6.Util.getLetterWidth(letter, fontSize);
          }
          if (currentWidth > maxWidth - ellipsisLength) {
            // -2 为了向前偏移两位留出间距的空间
            res = isRtl ? `${ellipsis}${str.slice(-i - 2)}` : `${str.substring(0, i - 2)}${ellipsis}`;
          }
        });
      return res;
    };
    /** 高亮搜索匹配 focus */
    const handleNodeFocus = () => {
      const allNodes = graph?.getNodes() || [];
      allNodes.forEach((node: { getModel: () => any }) => {
        const model = node.getModel();
        const matchesId = state.matchesNodeIds[state.curMathesFocusIndex] || '';
        graph?.setItemState(node, 'focus', model.id === matchesId);
      });
    };
    /** 根据当前所选分类显示高亮节点 */
    const handleHighlightNode = (classifyIds?: string[]) => {
      const targetNodes = []; // 所选分类节点
      const allEdges: IEdge[] = []; // 所有边
      const allNodes = graph?.getNodes() || []; // 所有节点
      const matches: string[] = []; // 搜索关键字匹配

      allNodes.forEach((node: { getModel: () => any; getEdges: () => any[] }) => {
        const model = node.getModel();
        // 关键字搜索匹配
        const isKeywordMatch = classifyIds
          ? classifyIds.includes(model.id)
          : state.keyword.every((val: string) => model.service_name?.toLowerCase().indexOf(val?.toLowerCase()) > -1);
        if (isKeywordMatch) {
          matches.push(model.id);
        }
        // 高亮当前分类的节点 根据分类、关键字搜索匹配过滤
        const isDisabled = !isKeywordMatch;
        graph?.setItemState(node, 'disabled', isDisabled);
        // 保存高亮节点 用于设置关联边高亮
        if (!isDisabled) targetNodes.push(model.id);
        // 获取所有边且去重
        node.getEdges().forEach(edge => {
          if (!allEdges.includes(edge)) allEdges.push(edge);
        });
      });

      if (state.keyword.length || classifyIds?.length) {
        state.curMathesFocusIndex = 0;
        state.matchesNodeIds = matches;
        graph.focusItem(matches[0], true, { duration: 200 });
        props.updateMatchedSpanIds?.(matches.length);
        handleNodeFocus();
      } else {
        props.updateMatchedSpanIds?.(0);
      }
    };
    /** 对比模式下节点tooltips内容 */
    const getTooltipsContent = e => {
      const { operationName, diff_info: diffInfo } = e.item.getModel();

      const diffInfoList = Object.keys(diffInfo).map(item => {
        let diffPercent = '';
        const { baseline, comparison, mark } = diffInfo[item];
        if (mark === 'changed') {
          diffPercent = `${(((baseline - comparison) / comparison) * 100).toFixed(2)}%`;
        }
        return {
          ...diffInfo[item],
          id: item,
          diffPercent,
        };
      });
      const outDiv = document.createElement('div');

      let listHtml = '';
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      for (let i = 0; i < diffInfoList.length; i++) {
        const { id, comparison, baseline, diffPercent } = diffInfoList[i];
        listHtml += `
        <tr>
        <td>${id}</td>
        <td>${baseline}</td>
        <td>${comparison}</td>
        <td>${diffPercent}</td>
      </tr>
        `;
      }

      outDiv.innerHTML = `
        <div>Span: ${operationName}</div>
        <table class="tips-table">
          <thead>
            <th>${t('耗时对比')}</th>
            <th>${t('当前')}</th>
            <th>${t('参照')}</th>
            <th>${t('差异')}</th>
          </thead>
          <tbody>
            ${listHtml}
          </tbody>
      </table>
      `;

      return outDiv;
    };
    /**
     * @description: 初始化实例拓扑图
     */
    const initGraph = () => {
      const { width, height } = (graphContainer.value as unknown as HTMLDivElement).getBoundingClientRect();
      state.canvasWidth = width;
      state.canvasHeight = height;

      /** 自定义节点 */
      G6.registerNode(
        'custom-node',
        {
          /**
           * 绘制节点，包含文本
           * @param  {Object} cfg 节点的配置项
           * @param  {G.Group} group 图形分组，节点中图形对象的容器
           * @return {G.Shape} 返回一个绘制的图形作为 keyShape，通过 node.get('keyShape') 可以获取。
           */
          draw: (cfg, group) => drawNode(cfg as any, group),
          /**
           * 设置节点的状态，主要是交互状态，业务状态请在 draw 方法中实现
           * 单图形的节点仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
           * @param  {String} name 状态名称
           * @param  {Object} value 状态值
           * @param  {Node} node 节点
           */
          setState: (name, value, item) => setNodeState(name as string, value as boolean, item as any),
          getAnchorPoints: () => [
            [0.5, 1],
            [0.5, 0],
            // [1, 0.5],
            // [0, 0.5]
          ],
        },
        'rect'
      );

      /** 自定义边 */
      G6.registerEdge(
        'line-dash',
        {
          /**
           * 设置边的状态，主要是交互状态，业务状态请在 draw 方法中实现
           * 单图形的边仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
           * @param  {String} name 状态名称
           * @param  {Object} value 状态值
           * @param  {Edge} edge 边
           */
          // setState: (name, value, item) => setEdgeState(name, value, item)
        },
        'cubic-vertical'
        // 'cubic-horizontal'
      );

      const grid = new G6.Grid();
      const minimap = new G6.Minimap({
        container: topoThumbnailRef.value,
        size: [236, 146],
      });
      const plugins = [grid, minimap];

      // 对比差异 tooltips
      if (state.isCompareView) {
        const nodeTooltip = () =>
          new G6.Tooltip({
            offsetX: 0, // x 方向偏移值
            // trigger: 'click',
            fixToNode: [0.9, 0.5], // 固定出现在相对于目标节点的某个位置
            className: 'node-tooltips-container',
            // 允许出现 tooltip 的 item 类型
            itemTypes: ['node'],
            // 自定义 tooltip 内容
            getContent: e => getTooltipsContent(e),
          });
        plugins.push(nodeTooltip() as any);
      }

      graph = new G6.Graph({
        container: graphContainer.value as unknown as HTMLElement, // 指定挂载容器
        width,
        height,
        minZoom: state.minZoomVal, // 画布最小缩放比例
        maxZoom: state.maxZoomVal, // 画布最大缩放比例
        // fitCenter: true, // 图的中心将对齐到画布中心
        // fitView: true, // 将图适配到画布大小，可以防止超出画布或留白太多
        fitViewPadding: [0, 40, 0, 10],
        animate: false,
        modes: {
          // 设置画布的交互模式
          default: [
            'drag-canvas', // 拖拽画布
            'zoom-canvas', // 缩放画布
            // !!this.serviceName ? '' : 'drag-node' // 拖拽节点 服务拓扑不可拖拽节点
          ],
        },
        /** 图布局 */
        layout: graphLayout.value,
        defaultEdge: {
          // 边的配置
          type: 'line-dash',
          radius: 20,
          style: {
            stroke: '#C4C6CC',
            lineWidth: 1,
            // 箭头样式
            endArrow: {
              path: G6.Arrow.triangle(10, 10, 0), // 路径
              fill: '#C4C6CC', // 填充颜色
              stroke: '#C4C6CC', // 描边颜色
              strokeOpacity: 0, // 描边透明度
            },
          },
        },
        defaultNode: {
          // 节点配置
          type: 'custom-node',
        },
        plugins,
      });
      graph.data(state.isCompareView ? compareData : graphData.value); // 读取数据源到图上
      graph.render(); // 渲染图
      bindListener(graph); // 图监听事件
    };
    const handleClientResize = () => {
      if (!graph || graph.get('destroyed')) return;
      const { width, height } = (graphContainer.value as unknown as HTMLElement).getBoundingClientRect();
      state.canvasWidth = width;
      state.canvasHeight = height;
      // 修改画布大小
      graph.changeSize(width, height);
      // 将拓扑图移到画布中心
      // graph.fitCenter();
      // graph.fitView();
    };
    const handleKeywordFilter = (value: string[]) => {
      state.keyword = value;
      handleHighlightNode();
    };
    const nextResult = () => {
      state.curMathesFocusIndex += 1;
      const curMathesFocusId = state.matchesNodeIds[state.curMathesFocusIndex];
      graph.focusItem(curMathesFocusId, true, { duration: 200 });
      handleNodeFocus();
    };
    const prevResult = () => {
      state.curMathesFocusIndex -= 1;
      const curMathesFocusId = state.matchesNodeIds[state.curMathesFocusIndex];
      graph.focusItem(curMathesFocusId, true, { duration: 200 });
      handleNodeFocus();
    };
    const clearSearch = () => {
      state.curMathesFocusIndex = -1;
      state.matchesNodeIds = [];
      handleNodeFocus();
    };
    const handleClassifyFilter = (matchedSpanIds: Set<string>) => {
      const ids = Array.from(matchedSpanIds);
      handleHighlightNode(ids);
    };
    /** 接口名称文本溢出处理 */
    const parseEndPointName = (model: any, group: any, value = false) => {
      const { operationName, collapsed } = model;
      const endPointText = group.find((e: { get: (arg0: string) => string }) => e.get('name') === 'endpoint-text');
      const durationShape = group.find((e: any) => e.get('name') === 'duration-container');
      const collapsedShape = group.find((e: any) => e.get('name') === 'collapsed-container');
      const containerWidth = collapsed ? collapsedShape.getBBox().x : 224;

      let endPointMaxWidth = containerWidth - 12; // 12为间距
      if (durationShape) {
        const durationRectBBox = durationShape.getBBox();
        const { x, width } = durationRectBBox;
        endPointMaxWidth = containerWidth - (x + width); // 计算可放置最大宽
      }
      // 区域是否够长 ? 展示内容不变 : 展示完整
      const cutEndPointStr = fittingString(operationName, endPointMaxWidth, 12);
      if (cutEndPointStr !== operationName) {
        endPointText.attr({
          text: value ? operationName : cutEndPointStr,
        });
      }
    };

    /** 服务名称文本溢出处理 */
    const parseServiceName = (model: any, group: any, value = false) => {
      const { service_name: serviceName } = model;
      const serviceText = group.find((e: { get: (arg0: string) => string }) => e.get('name') === 'server-text');
      const serviceMaxWidth = 184; // 计算可放置最大宽度
      // 区域是否够长 ? 展示内容不变 : 展示完整
      const cutStr = fittingString(serviceName, serviceMaxWidth, 12);
      if (cutStr !== serviceName) {
        serviceText.attr({
          text: value ? serviceName : cutStr,
        });
      }
    };

    /** 对比 */
    const viewCompare = async traceID => {
      if (traceID) {
        const { appName, trace_id: sourceTraceID } = traceData.value;
        const params = {
          bk_biz_id: window.bk_biz_id,
          app_name: appName,
          trace_id: sourceTraceID,
          diff_trace_id: traceID,
          diagram_type: 'topo',
        };
        handleCloseCompareMessage();
        showCompareError.value = false;
        showThumbnail.value = false;
        showLegend.value = false;
        emit('update:loading', true);
        await traceDiagram(params, { needMessage: false })
          .then(data => {
            if (data?.diagram_data?.similarity_check) {
              const { diagram_data: diagramData, original_data: originalData, trace_tree: traceTree } = data;
              const nodes = (diagramData.nodes || []).map(node => ({
                ...node,
                bgColor: getDiffPercentColor(node.diff_info),
              }));
              compareData = {
                nodes,
                edges: diagramData.relations || [],
              };
              updateTemporaryCompareTrace(traceID);
              state.isCompareView = true;
              graph?.destroy();
              initGraph();

              // 更新 compare spanlist
              const { spans: baselineSpans } = transformTraceTree(traceTree); // 对比参照的 traceTree spans
              const baselineOriginalData = originalData; // 对比参照的 original_data spans
              const { spans: currentSpans } = store.traceTree; // 当前 traceTree spans
              const { original_data: currentOriginalData } = traceData.value; // 当前 original_data spans
              // 对比 spans
              compareSpans = [];
              compareOriginalSpans = [];
              nodes.forEach(node => {
                // 通过拓扑图nodes.spans节点匹配 当前 和 参照 的 spans
                node.spans.forEach(span => {
                  const targetSpan = [...baselineSpans, ...currentSpans].find((item: Span) => span === item.span_id);
                  const { mark } = node.diff_info[span];
                  const bgColor = getSingleDiffColor(node.diff_info[span]);
                  compareSpans.push({ ...targetSpan, bgColor, mark });
                  compareOriginalSpans.push(
                    [...baselineOriginalData, ...currentOriginalData].find(item => span === item.span_id)
                  );
                });
              });
              emit('compareSpanListChange', compareSpans);
              store.updateCompareTraceOriginalData(compareOriginalSpans);
            } else {
              showCompareErrorMessage(t('差异过大不对比'));
            }
          })
          .catch(err => {
            showCompareErrorMessage(err.message);
          })
          .finally(() => emit('update:loading', false));
      } else {
        handleCloseCompareMessage();
        if (state.isCompareView) {
          handleCancelCompare();
        }
      }
    };
    /** 取消对比 */
    const handleCancelCompare = () => {
      state.isCompareView = false;
      graph?.destroy();
      initGraph();
    };
    /** 提示对比错误信息 */
    const showCompareErrorMessage = message => {
      compareWarningAlert.value = message;
      setTimeout(() => {
        showCompareError.value = true;
        handleCancelCompare();
      }, 10);
    };
    /** 关闭对比 Message 提示 */
    const handleCloseCompareMessage = () => {
      compareWarningAlert.value = '';
    };
    /**
     * @description: show thumbnail
     */
    const handleShowThumbnail = () => {
      if (!graph) return;
      showThumbnail.value = !showThumbnail.value;
      if (showThumbnail.value) {
        graphToolsRect.value = {
          width: 240,
          height: 148,
        };
      }
      showLegend.value = false;
    };
    /**
     * @desc 导出图片
     */
    const downloadAsImage = () => {
      if (!graph) return;
      const { trace_id: traceID } = traceData.value;
      const name = `${traceID}_${dayjs.tz().format('YYYY-MM-DD HH:mm:ss')}`;
      graph.downloadFullImage(name, 'image/png', {
        backgroundColor: '#fff',
        padding: 30,
      });
    };

    onMounted(() => {
      state.isCompareView = !!(props.compareTraceID ?? false);
      setTimeout(() => {
        try {
          if (!state.isCompareView) initGraph();
        } catch {
          empty.value = false;
        }
      }, 100);
      addListener(graphContainer.value as HTMLDivElement, handleClientResize);
    });

    onBeforeUnmount(() => {
      removeListener(graphContainer.value as HTMLDivElement, handleClientResize);
      graph?.destroy();
    });

    expose({
      nextResult,
      prevResult,
      clearSearch,
      handleKeywordFilter,
      handleClassifyFilter,
      viewCompare,
    });

    return {
      ...toRefs(state),
      graphContainer,
      handleGraphZoom,
      isFullscreen,
      emptyText,
      empty,
      showThumbnail,
      showLegend,
      topoThumbnailRef,
      topoGraphContent,
      handleShowThumbnail,
      downloadAsImage,
      graphToolsRect,
      handleShowLegend,
      compareWarningAlert,
    };
  },

  render() {
    return (
      <div class='relation-topo'>
        {this.empty && <div class='empty-chart'>{this.emptyText}</div>}
        <div
          ref='graphContainer'
          class='graph-container'
        />
        <div class='graph-tools'>
          <Popover
            width={this.graphToolsRect.width}
            height={this.graphToolsRect.height}
            extCls='topo-thumbnail-popover'
            allowHtml={false}
            arrow={false}
            boundary={'parent'}
            content={this.topoGraphContent}
            isShow={this.showThumbnail || this.showLegend}
            placement='top-start'
            renderType='auto'
            theme='light'
            trigger='manual'
            zIndex={1001}
          >
            {{
              default: () => (
                <GraphTools
                  class='topo-graph-tools'
                  legendActive={this.showLegend}
                  minScale={10}
                  scaleStep={10}
                  scaleValue={this.zoomValue}
                  thumbnailActive={this.showThumbnail}
                  onScaleChange={this.handleGraphZoom}
                  onShowLegend={this.handleShowLegend}
                  onShowThumbnail={this.handleShowThumbnail}
                  onStoreImg={this.downloadAsImage}
                />
              ),
              content: () => (
                <div
                  ref='topoGraphContent'
                  class='topo-graph-content'
                >
                  <div
                    ref='topoThumbnailRef'
                    style={`display: ${this.showLegend ? 'none' : 'block'}`}
                    class='topo-thumbnail'
                  />
                  {this.showLegend && <ViewLegend />}
                </div>
              ),
            }}
          </Popover>
        </div>
        {this.compareWarningAlert.length ? (
          <Alert
            class='compare-warning-alert'
            theme='warning'
            title={this.compareWarningAlert}
            closable
          />
        ) : (
          ''
        )}
      </div>
    );
  },
});
