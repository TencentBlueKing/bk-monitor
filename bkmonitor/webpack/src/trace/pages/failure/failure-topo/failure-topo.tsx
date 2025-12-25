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
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import {
  type ICombo,
  type INode,
  Arrow,
  Graph,
  registerBehavior,
  registerCombo,
  registerEdge,
  registerNode,
  Tooltip,
} from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Loading, Message, Popover, Slider } from 'bkui-vue';
import { cloneDeep } from 'lodash';
import isEqual from 'lodash/isEqual';
import { feedbackIncidentRoot, incidentTopology } from 'monitor-api/modules/incident';
import { deepClone, random } from 'monitor-common/utils/utils.js';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import ExceptionComp from '../../../components/exception';
import ResourceGraph from '../resource-graph/resource-graph';
import { checkIsRoot, useIncidentInject } from '../utils';
import LegendPopoverContent from './components/legend-popover-content';
import ElkjsUtils from './elkjs-utils';
import FailureTopoDetail from './failure-topo-detail/failure-topo-detail';
import FailureTopoTooltips from './failure-topo-tooltips';
import FeedbackCauseDialog from './feedback-cause-dialog';
import formatTopoData from './format-topo-data';
import { NODE_TYPE_SVG } from './node-type-svg';
import ServiceCombo from './service-combo';
import TopoTools from './topo-tools';
import {
  canJumpByType,
  createConnectedParallelCurves,
  getApmServiceType,
  getNodeAttrs,
  handleToLink,
  truncateText,
} from './utils';

import type { IEdge, IEntity, IncidentDetailData, ITopoData, ITopoNode } from './types';

import './failure-topo.scss';

/** 增加画布离画布上下左右的留白区域 */
const GRAPH_DRAG_MARGIN = 100;

export default defineComponent({
  name: 'FailureTopo',
  props: {
    selectNode: {
      type: Array,
      default: () => {
        return [];
      },
    },
    isCollapsed: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['toDetail', 'playing', 'toDetailTab', 'changeSelectNode', 'refresh', 'closeCollapse'],
  setup(props, { emit }) {
    const router = useRouter();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    /** 缓存resize render后执行的回调函数，主要用于点击播放之前收起右侧资源图时的回调 */
    const resizeCacheCallback = ref(null);
    const detailInfo = ref({});
    const cacheResize = ref<boolean>(false);
    const wrapRef = ref<HTMLDivElement>();
    const refreshTime = ref<number>(5 * 60 * 1000);
    const topoTools = ref(null);
    let refreshTimeout = null;
    const topoGraphRef = ref<HTMLDivElement>(null);
    const graphRef = ref<HTMLElement>(null);
    // 缓存当前combo拖拽后label的坐标
    const rootComboMovePoint = ref({ x: null, y: null });
    let graph: Graph;
    let tooltips = null;
    // 边的动画定时器
    let edgeInterval = [];
    let playTime = null;
    // 播放队列：存储需要播放的帧索引
    let playQueue: number[] = [];
    // 队列处理标志：避免重复处理队列
    let isProcessingQueue = false;
    /** g6 默认缩放级别 数值 / 10 为真实结果值  */
    const MIN_ZOOM = 0.2;
    const { t } = useI18n();
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
      return incidentDetail.value;
    });
    /** 当前停留帧 */
    const timelinePosition = ref<number>(0);
    const isPlay = ref<boolean>(false);
    const topoRawDataCache = ref({
      diff: [],
      latest: {
        nodes: [],
      },
      complete: {
        nodes: [],
        combos: [],
        edges: [],
      },
    });
    /** 判断是否渲染过编辑区域 */
    const isRenderComplete = ref<boolean>(false);
    const tooltipsModel = shallowRef<ITopoNode | ITopoNode[]>();
    const tooltipsEdge: Ref<IEdge> = shallowRef();
    // 用于边概览中的信息展示
    const edgeDetail: Ref<IEdge> = shallowRef();
    const isClickEdgeItem = ref<boolean>(false);
    // 用于节点概览中的信息展示
    const nodeDetail: Ref<ITopoNode> = ref(null);
    // 节点关联边数据
    const curLinkedEdges: Ref<IEdge[]> = shallowRef();
    const tooltipsType = ref<string>('node');
    const detailType = ref<string>('node');
    const tooltipsRef = ref<InstanceType<typeof FailureTopoTooltips>>();
    const resourceGraphRef = ref<InstanceType<typeof ResourceGraph>>();
    let topoRawData: ITopoData = null;
    const autoAggregate = ref<boolean>(true);
    const aggregateCluster = ref(true);
    const aggregateConfig = ref({});
    // const shouldUpdateNode = ref(null);
    const showLegend = ref<boolean>(localStorage.getItem('showLegend') === 'true');
    // 左侧画布数据获取检测
    const errorData = ref({
      isError: false,
      msg: '',
    });
    const isNoData = ref(false);
    // 展示资源从属相关信息
    const showViewResource = ref<boolean>(true);
    const feedbackCauseShow = ref<boolean>(false);
    const feedbackModel: Ref<{ entity: IEntity }> = ref(null);
    const incidentId = useIncidentInject();
    const nodeEntityId = ref<string>('');
    const nodeEntityName = ref<string>('');
    const loading = ref<boolean>(false);
    let activeAnimation = [];
    const resourceNodeId = ref<string>('');
    const resourceEdgeId = ref<string>('');
    const zoomValue = ref<number>(10);
    const showServiceOverview = ref<boolean>(false);
    const showResourceGraph = ref<boolean>(false);
    /** 检测文字长度，溢出截断 */
    const accumulatedWidth = (text, maxWidth = 80) => {
      const context = graph.get('canvas').get('context'); // 获取canvas上下文用于测量文本
      const textWidth = context.measureText(text).width;
      if (textWidth > maxWidth) {
        let truncatedText = '';
        let accumulatedWidth = 0;

        // 逐个字符检查，直到累计宽度超过最大宽度，然后截断
        for (const char of text) {
          accumulatedWidth += context.measureText(char).width;
          if (accumulatedWidth > maxWidth) break;
          truncatedText += char;
        }
        return `${truncatedText}...`;
      }
      return text;
    };
    /** 画布自定义节点 */
    const registerCustomNode = () => {
      registerNode('topo-node', {
        afterDraw(cfg, group) {
          const nodeAttrs = getNodeAttrs(cfg as ITopoNode);
          const { entity, alert_all_recorved, is_feedback_root } = cfg as ITopoNode;
          const isRoot = checkIsRoot(entity);
          if (isRoot || is_feedback_root) {
            group.addShape('circle', {
              attrs: {
                lineDash: [3],
                lineWidth: 1, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 25, // 圆半径
                stroke: isRoot ? '#F55555' : '#FF9C01',
              },
              name: 'topo-node-root-border',
            });
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -15,
                y: 12,
                width: 30,
                height: 16,
                radius: 8,
                stroke: '#3A3B3D',
                fill: isRoot ? '#F55555' : '#FF9C01',
              },
              name: 'topo-node-rect',
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 21,
                textAlign: 'center',
                textBaseline: 'middle',
                text: truncateText(t('根因'), 28, 11, 'PingFangSC-Medium'),
                fontSize: 11,
                fill: '#fff',
                ...nodeAttrs.textAttrs,
              },
              name: 'topo-node-text',
            });
          }
          if (entity.is_on_alert || alert_all_recorved) {
            group.addShape('circle', {
              attrs: {
                x: 15,
                y: -14,
                zIndex: 10,
                lineWidth: 1, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 8, // 圆半径
                fill: entity.is_on_alert ? '#F55555' : '#6C6F78',
              },
              name: 'topo-tag-border',
            });
            group.addShape('image', {
              zIndex: 12,
              attrs: {
                x: 9,
                y: -21,
                width: 12,
                height: 12,
                cursor: 'pointer', // 手势类型
                img: NODE_TYPE_SVG.Alert,
              },
              draggable: true,
              name: 'topo-tag-img',
            });
          }
        },
        draw(cfg, group) {
          const { entity, aggregated_nodes, anomaly_count, is_feedback_root } = cfg as ITopoNode;
          const nodeAttrs: any = getNodeAttrs(cfg as ITopoNode);
          const isRoot = checkIsRoot(entity);
          const showRoot = isRoot || entity.is_feedback_root;
          const isAggregated = aggregated_nodes.length > 0;
          const nodeShapeWrap = group.addShape('rect', {
            zIndex: 10,
            attrs: {
              x: showRoot ? -25 : -20,
              y: showRoot ? -28 : -22,
              lineWidth: 1, // 描边宽度
              cursor: 'pointer', // 手势类型
              width: showRoot ? 50 : 40, // 根因有外边框整体宽度为50
              height: showRoot ? 82 : isAggregated ? 63 : 67, // 根因展示根因提示加节点类型加节点名称 聚合节点展示聚合提示加类型 普通节点展示名字与类型
            },
            draggable: true,
            name: 'topo-node-shape-wrap',
          });
          group.addShape('circle', {
            zIndex: 10,
            attrs: {
              lineWidth: 1, // 描边宽度
              cursor: 'pointer', // 手势类型
              r: 20, // 圆半径
              ...nodeAttrs.groupAttrs,
              fill: showRoot ? '#F55555' : nodeAttrs.groupAttrs.fill,
            },
            draggable: true,
            name: 'topo-node-shape',
          });
          group.addShape('image', {
            zIndex: 12,
            attrs: {
              x: -14,
              y: -14,
              width: 28,
              height: 28,
              cursor: 'pointer', // 手势类型
              img: NODE_TYPE_SVG[getApmServiceType(entity)],
            },
            draggable: true,
            name: 'topo-node-img',
          });
          group.addShape('circle', {
            attrs: {
              lineWidth: 0, // 描边宽度
              cursor: 'pointer', // 手势类型
              r: 22, // 圆半径
              stroke: 'rgba(5, 122, 234, 1)',
            },
            name: 'topo-node-running',
          });
          group.addShape('circle', {
            attrs: {
              lineWidth: 0,
              cursor: 'pointer',
              r: 27,
              stroke: '#3a84ff4d',
            },
            name: 'topo-node-running-shadow',
          });

          if (aggregated_nodes?.length) {
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: (anomaly_count as number) > 0 ? -17 : -8,
                y: 12,
                width: (anomaly_count as number) > 0 ? 32 : 16,
                cursor: 'pointer',
                height: 16,
                radius: 8,
                fill: '#fff',
                ...nodeAttrs.rectAttrs,
              },
              name: 'topo-node-rect',
            });
            (anomaly_count as number) > 0 &&
              group.addShape('text', {
                zIndex: 11,
                attrs: {
                  x: -9,
                  y: 21,
                  cursor: 'cursor',
                  textAlign: 'center',
                  textBaseline: 'middle',
                  text: anomaly_count,
                  fontSize: 11,
                  ...nodeAttrs.textAttrs,
                  fill: '#FF6666',
                },
                name: 'topo-node-err-text',
              });
            (anomaly_count as number) > 0 &&
              group.addShape('text', {
                zIndex: 11,
                attrs: {
                  x: -2,
                  y: 21,
                  cursor: 'default',
                  textAlign: 'center',
                  textBaseline: 'middle',
                  text: '/',
                  fontSize: 11,
                  ...nodeAttrs.textAttrs,
                  fill: '#979BA5',
                },
                name: 'topo-node-err-text',
              });

            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0 + ((anomaly_count as number) > 0 ? 5 : 0),
                y: 21,
                textAlign: 'center',
                cursor: 'cursor',
                textBaseline: 'middle',
                text:
                  isRoot || is_feedback_root
                    ? truncateText(t('根因'), 28, 11, 'PingFangSC-Medium')
                    : aggregated_nodes.length + 1,
                fontSize: 11,
                fill: '#EAEBF0',
                ...nodeAttrs.textAttrs,
              },
              name: 'topo-node-text',
            });
          }
          group.addShape('text', {
            zIndex: 11,
            attrs: {
              x: 0,
              y: aggregated_nodes?.length || isRoot || is_feedback_root ? 36 : 28,
              textAlign: 'center',
              textBaseline: 'middle',
              cursor: 'cursor',
              text: accumulatedWidth(entity?.properties?.entity_show_type || entity.entity_type),
              fontSize: 10,
              ...nodeAttrs.textNameAttrs,
            },
            name: 'topo-node-type-text',
          });
          aggregated_nodes.length === 0 &&
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: isRoot || is_feedback_root ? 48 : 40,
                textAlign: 'center',
                textBaseline: 'middle',
                cursor: 'cursor',
                text: accumulatedWidth(entity.entity_name),
                fontSize: 10,
                ...nodeAttrs.textNameAttrs,
              },
              name: 'topo-node-name-text',
            });
          group.sort();
          return nodeShapeWrap;
        },
        setState(name, value, item) {
          const group = item.getContainer();
          if (name === 'hover') {
            const shape = group.find(e => e.get('name') === 'topo-node-shape');
            shape?.attr({
              shadowColor: value ? 'rgba(0, 0, 0, 0.5)' : false,
              shadowBlur: value ? 6 : false,
              shadowOffsetX: value ? 0 : false,
              shadowOffsetY: value ? 2 : false,
              strokeOpacity: value ? 0.6 : 1,
              cursor: 'pointer', // 手势类型
            });
          } else if (name === 'running') {
            const runningShape = group.find(e => e.get('name') === 'topo-node-running');
            const runningShadowShape = group.find(e => e.get('name') === 'topo-node-running-shadow');
            const rootBorderShape = group.find(e => e.get('name') === 'topo-node-root-border');
            if (value) {
              rootBorderShape?.attr({
                opacity: 0,
              });
              runningShape.attr({
                lineWidth: 3,
                r: 24,
                strokeOpacity: 1,
              });
              runningShadowShape.attr({
                lineWidth: 3,
                r: 27,
                strokeOpacity: 1,
              });
            } else {
              rootBorderShape?.attr({
                opacity: 1,
              });
              runningShape.attr({
                lineWidth: 0, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 22, // 圆半径
                stroke: 'rgba(5, 122, 234, 1)',
              });
              runningShadowShape.attr({
                lineWidth: 0,
                cursor: 'pointer',
                r: 27,
                stroke: '#3a84ff4d',
              });
              activeAnimation.forEach(animation => animation?.stop?.());
              activeAnimation = [];
            }
          } else if (name === 'show-animate') {
            group.attr({
              opacity: 0,
            });
            item.show();
            group.animate(
              {
                opacity: 1,
              },
              {
                duration: 1000,
              }
            );
          } else if (name === 'dark') {
            group.attr({
              opacity: value ? 0.4 : 1,
            });
          }
        },
      });
    };
    /** 自定义service combo */
    const registerCustomCombo = () => {
      registerCombo('service-combo', ServiceCombo, 'rect');
    };
    /** 自定义边公共工具函数 */
    const edgeUtils = {
      // 绘制高亮边
      handelCreateHighlightEdge(shape: any, group: any) {
        const offset = shape.attrs.endArrow ? 6 : 0;
        const [left, right, mid] = createConnectedParallelCurves(
          shape.attrs.path,
          Math.max(shape.attrs.lineWidth - 1, 1),
          offset
        );
        group.addShape('path', {
          attrs: {
            ...shape.attrs,
            stroke: 'rgba(58, 132, 255, 1)',
            endArrow: false,
            lineDash: false,
            lineWidth: 0,
            path: right,
          },
          name: 'select-edge-path-right',
        });
        group.addShape('path', {
          attrs: {
            ...shape.attrs,
            stroke: 'rgba(58, 132, 255, 1)',
            endArrow: false,
            lineDash: false,
            lineWidth: 0,
            path: left,
          },
          name: 'select-edge-path-left',
        });

        group.addShape('path', {
          attrs: {
            ...shape.attrs,
            endArrow: false,
            stroke: 'rgba(58, 132, 255, 1)',
            lineDash: false,
            lineWidth: 0,
            path: mid,
          },
          name: 'select-edge-path-mid',
        });
      },
      // 处理边动画
      handleEdgeAnimation(shape: any, item: any, cfg: any, edgeInterval: any[]) {
        // biome-ignore lint/complexity/noForEach: <explanation>
        const { is_anomaly, anomaly_score, events, edge_type } = cfg;
        const lineDash = anomaly_score === 0 ? [6] : [10];
        if (is_anomaly && events?.[0] && edge_type === 'ebpf_call') {
          const { direction } = events[0];
          let index = 0;
          // 这里改为定时器执行，自带的动画流动速度控制不了
          const interVal = {
            id: cfg.id,
            timer: setInterval(() => {
              if (item.hasState('highlight')) {
                item.toFront();
              }
              shape.animate(() => {
                index = index + 1;
                if (index > (anomaly_score === 0 ? 60 : 120)) {
                  index = 0;
                }
                const res = {
                  lineDash,
                  lineDashOffset: direction === 'reverse' ? index : -index,
                };
                return res;
              });
            }, 30),
          };
          // 避免反复存储
          const intervalIndex = edgeInterval.findIndex(item => item.id === cfg.id);
          if (intervalIndex === -1) {
            edgeInterval.push(interVal);
          } else {
            clearInterval(edgeInterval[intervalIndex].timer);
            edgeInterval[intervalIndex] = null;
            edgeInterval.splice(intervalIndex, 1, interVal);
          }
        }
      },
      // 添加聚合点
      addAggregationMarkers(cfg: any, group: any) {
        if (!cfg.aggregated || !cfg.count) return;
        const shape = group.get('children')[0];
        // 获取路径图形的中点坐标
        const midPoint = shape.getPoint(0.5);
        // 在中点增加一个圆形，注意圆形的原点在其左上角
        group.addShape('circle', {
          zIndex: 10,
          attrs: {
            cursor: 'pointer',
            r: 10,
            fill: '#212224',
            // 使圆形中心在 midPoint 上
            x: midPoint.x,
            y: midPoint.y,
          },
        });
        group.addShape('text', {
          zIndex: 11,
          attrs: {
            cursor: 'pointer',
            x: midPoint.x,
            y: midPoint.y + 1,
            textAlign: 'center',
            textBaseline: 'middle',
            text: cfg.count,
            fontSize: 12,
            fill: '#fff',
          },
          name: 'topo-node-text',
        });
      },
      // 处理状态变化
      handleEdgeState(name: string, value: any, item: any) {
        const model = item.getModel();
        const group = item.getContainer();
        const shape = group.get('children')[0];
        const { is_anomaly } = model;
        const colors = {
          highlight: is_anomaly ? '#F55555' : '#699DF4',
          dark: is_anomaly ? '#F55555' : '#63656E',
        };
        switch (name) {
          case 'show-animate':
            item.show();
            break;
          case 'highlight':
            // biome-ignore lint/complexity/noForEach: <explanation>
            group.get('children').forEach(shape => {
              const name = shape.get('name');
              if (name?.includes('select-edge-path')) {
                shape.attr('lineWidth', value ? 1 : 0);
              }
            });
            group.attr('opacity', 1);
            if (shape.attrs.endArrow) {
              shape.attr({
                endArrow: {
                  opacity: 1,
                  ...shape.attrs.endArrow,
                  stroke: value ? '#3A84FF' : colors.dark,
                },
              });
            }
            break;
          case 'dark':
            group.attr('opacity', value ? 1 : 0.4);
            break;
        }
      },
    };
    /** 拖拽时设置combox label轴的位置 */
    const moveComboLabelPosition = (point: { x?: number; y?: number }) => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getCombos().forEach(combo => {
        if (!combo.getModel().parentId) {
          (combo.getContainer() as any).shapeMap['text-shape'].attr(point);
        }
      });
    };
    /** 自定义边类型工厂函数 */
    const createEdgeConfig = () => ({
      afterDraw(cfg: any, group: any) {
        const shape = group.get('children')[0];
        const item = group.get('item');
        edgeUtils.handleEdgeAnimation(shape, item, cfg, edgeInterval);
        edgeUtils.addAggregationMarkers(cfg, group);
        // 绘制异常选中的高亮边
        edgeUtils.handelCreateHighlightEdge(shape, group);
      },
      setState(name: string, value: any, item: any) {
        edgeUtils.handleEdgeState(name, value, item);
      },
      update: undefined,
    });
    /** 画布自定义边 */
    const registerCustomEdge = () => {
      // 普通边
      registerEdge('topo-edge', createEdgeConfig(), 'quadratic');
      // 自环边
      registerEdge('topo-edge-loop', createEdgeConfig(), 'loop');
    };
    /** 获取相对位置 */
    const getCanvasByPoint = combo => {
      const comboBBox = combo.getBBox();
      return {
        topLeft: graph.getCanvasByPoint(comboBBox.x, comboBBox.y),
        bottomRight: graph.getCanvasByPoint(comboBBox.x + comboBBox.width, comboBBox.y + comboBBox.height),
      };
    };
    /** 自定义插件 */
    const registerCustomBehavior = () => {
      // node 自定义拖动 防止node拖出combo
      registerBehavior('drag-node-with-fixed-combo', {
        getEvents() {
          return {
            'combo:dragstart': 'onDragStart',
            'combo:drag': 'onDrag',
            'combo:dragend': 'onDragEnd',
            'node:dragstart': 'onDragStart',
            'node:drag': 'onDrag',
            'node:dragend': 'onDragEnd',
          };
        },
        onDragStart(e) {
          const { item } = e;
          const combos = graph.getCombos();
          const model = item.getModel();
          // 存储当前节点所在的 combo ID
          if (item.get('type') === 'node' || (item.get('type') === 'combo' && model.parentId)) {
            const combo = combos.find(combo =>
              [model.comboId, model.subComboId, model.parentId].includes(combo.getID())
            );
            this.currentComboId = combo ? combo.getID() : null;
            this.currentNodes = [];
            /** 如果拖动的是combo */
            if (item.get('type') === 'combo') {
              // biome-ignore lint/complexity/noForEach: <explanation>
              graph.getNodes().forEach(node => {
                if (node.getModel().subComboId === item.getID()) {
                  (this.currentNodes as INode[]).push(node);
                }
              });
            }
            this.origin = { x: e.x, y: e.y };
          }
          // 拖动combo或者节点时，隐藏Tooltip
          const comboLabelTooltip = document.getElementById('combo-label-tooltip');
          comboLabelTooltip.style.visibility = 'hidden';
          const nodeInfoTooltip = document.getElementById('node-detail-tips');
          nodeInfoTooltip.style.visibility = 'hidden';
        },
        onDrag(e) {
          const { item, x, y } = e;
          if (this.currentComboId) {
            const combos = graph.getCombos();
            let dragBbox = item.getBBox();
            const combo = combos.find(combo => combo.getID() === this.currentComboId);
            const comboBBox = combo.getBBox();
            const nodeSize = 40; // 假设节点的边长为40
            const { x: originX, y: originY } = this.origin as { x: number; y: number };
            let dx = x - originX;
            let dy = y - originY;

            if (item.get('type') === 'node') {
              const model = item.getModel();
              const isAggregatedNode = model.aggregated_nodes.length > 0;
              // 聚合节点不会展示 节点名称用外层容器节点类型判断， 非聚合节点用节点名称判断
              const nameTextShape = item
                .get('group')
                .find(s => s.get('name') === (isAggregatedNode ? 'topo-node-type-text' : 'topo-node-name-text'));
              const nameShapeBBox = nameTextShape?.getBBox?.() || {
                width: 0,
                y: 0,
                height: 0,
              };
              // 获取该Shape相对于画布的边界框
              // 根据节点中心位置和边长计算出节点的新边界框
              dragBbox = {
                minX: model.x + nameShapeBBox.minX,
                maxX: model.x + nameShapeBBox.maxX,
                minY: model.y + nameShapeBBox.minY - (nodeSize + nameShapeBBox.height * 2),
                maxY: model.y + nameShapeBBox.maxY,
              };
            }
            if (dragBbox.minX + dx < comboBBox.minX) {
              dx = comboBBox.minX - dragBbox.minX;
            }
            if (dragBbox.maxX + dx > comboBBox.maxX) {
              dx = comboBBox.maxX - dragBbox.maxX;
            }
            if (dragBbox.minY + dy < comboBBox.minY) {
              dy = comboBBox.minY - dragBbox.minY;
            }
            if (dragBbox.maxY + dy > comboBBox.maxY) {
              dy = comboBBox.maxY - dragBbox.maxY;
            }
            // 如果节点新位置还在Combo内，可以移动
            item.toFront(); // 如果需要的话可以让节点到最前方显示
            const model = item.getModel();
            graph.updateItem(item, {
              x: model.x + dx,
              y: model.y + dy,
            });
            // biome-ignore lint/complexity/noForEach: <explanation>
            (this.currentNodes as INode[]).forEach(node => {
              const model = node.getModel();
              graph.updateItem(node, {
                x: model.x + dx,
                y: model.y + dy,
              });
              node.toFront();
            });
            this.origin = { x: e.x, y: e.y };
          }
        },
        onDragEnd() {
          // 清除临时信息
          this.currentComboId = undefined;
          this.currentNodes = undefined;
          setTimeout(toFrontAnomalyEdge);
        },
      });
      // 自定义拖拽
      registerBehavior('drag-canvas-move', {
        getEvents() {
          return {
            mouseenter: 'omMouseenter',
            mousedown: 'onMouseDown',
            mousemove: 'onMouseMove',
            mouseup: 'onMouseUp',
            mouseleave: 'onMouseLeave',
          };
        },
        omMouseenter(e) {
          const itemType = e?.item?.getType();
          const model = e?.item?.getModel();
          /** 子combo/节点/和边不响应拖动 */
          if (['node', 'edge'].includes(itemType) || (itemType === 'combo' && model?.parentId)) {
            return;
          }
          const canvas = graph.get('canvas');
          const el = canvas.get('el'); // 获取到画布实际的 DOM 元素
          this.comboRect = {
            el,
          };
          (this.comboRect as any).el.cursor = 'grab';
        },
        onMouseDown(e) {
          const itemType = e?.item?.getType();
          const model = e?.item?.getModel();
          if (['node', 'edge'].includes(itemType) || (itemType === 'combo' && model?.parentId)) {
            return;
          }
          e.item &&
            graph.updateItem(e.item, {
              style: {
                cursor: 'grabbing',
              },
            });
          (this as any).comboRect.el.style.cursor = 'grabbing';
          this.dragging = true;
          const combos = graph.getCombos().filter(combo => !combo.getModel().parentId);
          let xCombo = combos[0];
          let xComboWidth = 0;
          // biome-ignore lint/complexity/noForEach: <explanation>
          combos.forEach(combo => {
            const { width } = combo.getBBox();
            if (width > xComboWidth) {
              xCombo = combo;
              xComboWidth = width;
            }
            if (rootComboMovePoint.value.x) {
              (combo.getContainer() as any).shapeMap['text-shape'].attr({
                x: rootComboMovePoint.value.x,
              });
            }
          });
          const comboModel = combos[0].getModel() as { height: number; width: number };
          this.comboRect = {
            ...((this as any).comboRect || {}),
            labelPoint: {
              x: -(comboModel.width / 2 + 10),
              y: -(comboModel.height / 2 + 30),
            },
            xCombo,
            topCombo: combos[0],
            bottomCombo: combos[combos.length - 1],
            width: graph.getWidth(),
            height: graph.getHeight() + 20,
          };
        },
        onMouseMove(e) {
          if (this.dragging) {
            const comboRect = this.comboRect as {
              bottomCombo: ICombo;
              height: number;
              labelPoint: { x: number; y: number };
              topCombo: ICombo;
              width: number;
              xCombo: ICombo;
            };
            let { movementX, movementY } = e.originalEvent;
            // 大于零向上拖动
            if (movementY < 0) {
              const { bottomRight } = getCanvasByPoint(comboRect.bottomCombo);
              if (bottomRight.y + GRAPH_DRAG_MARGIN < comboRect.height) {
                movementY = 0;
              }
            } else {
              const { topLeft } = getCanvasByPoint(comboRect.topCombo);
              if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
                movementY = 0;
              }
            }
            const { topLeft, bottomRight } = getCanvasByPoint(comboRect.xCombo);
            /** 大于0向左拖动 */
            if (movementX < 0) {
              if (bottomRight.x + GRAPH_DRAG_MARGIN < comboRect.width) {
                movementX = 0;
              }
            } else {
              if (topLeft.x - GRAPH_DRAG_MARGIN > 0) {
                movementX = 0;
              }
            }
            graph.translate(movementX, movementY);
          }
        },
        onMouseUp(e) {
          if (!this.dragging) {
            return;
          }
          this.dragging = false;
          e.item &&
            e.item.getType() === 'combo' &&
            graph.updateItem(e.item, {
              style: {
                cursor: 'grab',
              },
            });
          (this as any).comboRect.el.style.cursor = 'grab';
          rootComboMovePoint.value.x && moveComboLabelPosition({ x: rootComboMovePoint.value.x });
        },
        onMouseLeave(e) {
          if (this.dragging) {
            e.item &&
              e.item.getType() === 'combo' &&
              graph.updateItem(e.item, {
                style: {
                  cursor: 'grab',
                },
              });
            (this as any).comboRect.el.style.cursor = 'grab';
            this.dragging = false;
          }
        },
      });

      registerBehavior('custom-scroll-canvas', {
        getEvents() {
          return {
            wheel: 'onWheel',
          };
        },
        onWheel: e => {
          e.preventDefault();
          e.stopPropagation();
          const { deltaX, deltaY } = e;
          const sensitivity = 2; // 设置滚动灵敏度
          let dx = -deltaX * sensitivity;
          let dy = -deltaY * sensitivity;
          // 获取所有combos的布局信息
          const combos = graph.getCombos().filter(combo => !combo.getModel().parentId);
          const width = graph.getWidth();
          const height = graph.getHeight() + 20;
          if (Math.abs(deltaY) > Math.abs(deltaX)) {
            // vertical scroll
            if (deltaY > 0) {
              const bottomCombo = combos[combos.length - 1];
              const { bottomRight } = getCanvasByPoint(bottomCombo);
              if (bottomRight.y + GRAPH_DRAG_MARGIN < height) {
                dy = 0;
              }
            } else {
              const topCombo = combos[0];
              const { topLeft } = getCanvasByPoint(topCombo);
              if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
                dy = 0;
              }
            }
            dx = 0;
          } else {
            const topCombo = combos[0];
            const { topLeft, bottomRight } = getCanvasByPoint(topCombo);
            /** 大于0判断右侧 否则判断左侧 */
            if (deltaX > 0) {
              if (bottomRight.x + GRAPH_DRAG_MARGIN < width) {
                dx = 0;
              }
            } else {
              if (topLeft.x - GRAPH_DRAG_MARGIN > 0) {
                dx = 0;
              }
            }
            dy = 0;
          }
          graph.translate(dx, dy);
        },
      });
    };
    /** 自定义tips */
    const registerCustomTooltip = () => {
      tooltips = new Tooltip({
        // offsetX: 10,
        // offsetY: 10,
        fixToNode: [1, 1],
        container: document.querySelector('.topo-graph') as HTMLDivElement,
        trigger: 'click',
        itemTypes: ['edge', 'node'],
        getContent: e => {
          const type = e.item.getType();
          const model = e.item.getModel();
          if (type === 'edge') {
            const { nodes = [] } = topoRawDataCache.value.complete;
            const targetModel = nodes.find(item => item.id === model.target);
            const sourceModel = nodes.find(item => item.id === model.source);
            tooltipsModel.value = [sourceModel, targetModel];
            tooltipsEdge.value = model as IEdge;

            edgeDetail.value = model as IEdge;
            isClickEdgeItem.value = false;

            model.nodes = [
              {
                ...sourceModel,
                events: model.events || [],
              },
              {
                ...targetModel,
                events: model.events || [],
              },
            ];
            // biome-ignore lint/complexity/noForEach: <explanation>
            (model.aggregated_edges as ITopoNode[]).forEach(node => {
              node.id = random(10);
              const targetModel = nodes.find(item => item.id === node.target);
              const sourceModel = nodes.find(item => item.id === node.source);
              /** 聚合节点在nodes集合中第一层可能找不到直接取边中的信息制造entity */
              node.nodes = [
                {
                  entity: {
                    is_anomaly: node.source_is_anomaly,
                    is_on_alert: node.source_is_on_alert,
                    entity_name: node.source_name,
                    entity_type: node.source_type,
                  },
                  ...sourceModel,
                  events: node.events || [],
                },
                {
                  entity: {
                    is_anomaly: node.target_is_anomaly,
                    is_on_alert: node.target_is_on_alert,
                    entity_name: node.target_name,
                    entity_type: node.target_type,
                  },
                  ...targetModel,
                  events: node.events || [],
                },
              ];
            });

            // 点击非聚合边，直接打开边概览
            if (!model.aggregated) {
              handleViewServiceFromTopo({ type: 'edge', data: model, sourceNode: null, isAggregatedEdge: false });
            }
          } else {
            tooltipsModel.value = model as ITopoNode;
            // nodeEntityId.value = tooltipsModel.value.entity.entity_id;
          }
          tooltipsType.value = type;
          return tooltipsRef.value.$el as HTMLDivElement;
        },
      });
    };

    /** 窗口变化 */
    function handleResize() {
      if (!graph || graph.get('destroyed') || !graphRef.value) return;
      /** 播放过程中不只需resize，等待播放完毕后判断 resize*/
      if (isPlay.value) {
        cacheResize.value = true;
        return;
      }
      const graphWidth = graph.getWidth();
      const { height } = document.querySelector('.failure-topo').getBoundingClientRect();
      const { width } = graphRef.value.getBoundingClientRect();
      tooltipsRef?.value?.hide?.();
      rootComboMovePoint.value = { x: null, y: null };
      tooltips?.hide?.();
      const combosList = graph.getCombos().map(combo => combo.getModel());
      ElkjsUtils.setRootComboStyle(combosList, width, !(graphWidth - width > 450));
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getCombos().forEach(combo => {
        if (!combo.getModel()?.parentId) {
          const com = combosList.find(c => c.id === combo.getID());
          graph.updateItem(combo, com);
        }
      });
      graph.changeSize(width, height - 40);
      graph.get('viewController').changeSize(width, height - 40);
      graph.layout();
      graph.translate(graphWidth - width > 450 ? -10 : 0, 0);
      const zoom = localStorage.getItem('failure-topo-zoom');
      if (zoom) {
        handleZoomChange(zoom);
        zoomValue.value = Number(zoom);
      }
      timelinePosition.value = topoRawDataCache.value.diff.length - 1;
      /** 打开时会触发导致动画消失 */
      if (resourceNodeId.value) {
        const isNavSelectNode = navSelectNode.value.some(node => node.id === resourceNodeId.value);
        if (isNavSelectNode) {
          // biome-ignore lint/complexity/noForEach: <explanation>
          navSelectNode.value.forEach(node => {
            graph.setItemState(graph.findById(node.id), 'running', true);
          });
          return;
        }
        const node = graph.findById(resourceNodeId.value);
        node && graph.setItemState(node, 'running', true);
      }
      if (!resourceEdgeId.value) {
        // biome-ignore lint/complexity/noForEach: <explanation>
        graph.getEdges().forEach(edge => {
          edge && graph.setItemState(edge, 'highlight', false);
        });
      }
    }

    const onResize = debounce(300, handleResize);

    /**
     * 清洗ComboID避免重复ID导致绘制错误
     * API返回数据ComboID和nodeID会重复
     */
    const formatResponseData = data => {
      const { combos = [], nodes = [], sub_combos = [] } = data || {};
      // biome-ignore lint/complexity/noForEach: <explanation>
      nodes.forEach(node =>
        Object.assign(node, {
          width: 90,
          height: 92,
          comboId: ElkjsUtils.getComboId(node.comboId),
          subComboId: ElkjsUtils.getComboId(node.subComboId),
        })
      );
      combos.forEach(formatComboOption);
      sub_combos.forEach(formatSubcomboOption);
    };

    const formatSubcomboOption = combo => {
      Object.assign(combo, {
        id: ElkjsUtils.getComboId(combo.id),
        isCombo: true,
        comboId: ElkjsUtils.getComboId(combo.comboId),
      });
    };

    const formatComboOption = combo => {
      Object.assign(combo, {
        id: ElkjsUtils.getComboId(combo.id),
        isCombo: true,
        comboId: ElkjsUtils.getComboId(combo.comboId),
        type: 'rect',
        style: {
          cursor: 'grab',
          fill: '#1D2024',
          radius: 4,
          stroke: '#333333',
        },
        labelCfg: {
          style: {
            fill: '#C4C6CC',
            fontSize: 12,
          },
        },
      });
    };

    /** 获取数据 */
    const getGraphData = async (isAutoRefresh = false) => {
      loading.value = !isAutoRefresh;
      if (!wrapRef.value) return;
      clearTimeout(refreshTimeout);
      const renderData = await incidentTopology(
        {
          id: incidentId.value,
          auto_aggregate: autoAggregate.value,
          aggregate_cluster: aggregateCluster.value ?? false,
          aggregate_config: aggregateConfig.value,
          only_diff: true,
          start_time: isAutoRefresh
            ? topoRawDataCache.value.diff[topoRawDataCache.value.diff.length - 1].create_time + 1
            : incidentId.value.substr(0, 10),
        },
        { needMessage: false }
      )
        .then(res => {
          const { latest, diff, complete } = res;
          complete.combos = latest.combos;
          formatResponseData(complete);
          const { combos = [], edges = [], nodes = [], sub_combos = [] } = complete || {};
          isNoData.value = combos.length === 0;
          errorData.value.isError = false;
          ElkjsUtils.setSubCombosMap(ElkjsUtils.getSubComboCountMap(nodes));
          const resolvedCombos = [...combos, ...ElkjsUtils.resolveSumbCombos(sub_combos)];
          const processedNodes = [];
          const processedEdges = [];
          const processedSubCombos = [];
          // biome-ignore lint/complexity/noForEach: <explanation>
          diff.forEach(item => {
            item.showNodes = [...processedNodes];
            // biome-ignore lint/complexity/noForEach: <explanation>
            item.content.nodes.forEach(showNode => {
              const index = processedNodes.findIndex(node => node.id === showNode.id);
              if (index !== -1) {
                processedNodes[index] = showNode;
              } else {
                processedNodes.push(showNode);
              }
            });
            processedNodes.push(item.content.nodes);
            // biome-ignore lint/complexity/noForEach: <explanation>
            item.content.edges.forEach(edge => {
              const key = edge.target + edge.source;
              const index = processedEdges.findIndex(item => item.target + item.source === key);
              if (index !== -1) {
                processedEdges[index] = edge;
              } else {
                processedEdges.push(edge);
              }
            });
            item.showSubCombos = [...processedSubCombos];
            processedSubCombos.push(...item.content.sub_combos);
            item.showEdges = [...processedEdges];
          });
          topoRawDataCache.value.diff = diff;
          topoRawDataCache.value.latest = latest;
          topoRawDataCache.value.complete = { ...complete, combos: resolvedCombos };
          const diffLen = topoRawDataCache.value.diff.length;
          timelinePosition.value = diffLen - 1;
          return ElkjsUtils.getTopoRawData(resolvedCombos, edges, nodes);
        })
        .catch(err => {
          errorData.value.isError = true;
          errorData.value.msg = err.data?.error_details ? err.data.error_details.overview : err.message;
          isNoData.value = false;
        })
        .finally(() => {
          if (!graph) {
            initGraph();
          }
          loading.value = false;
          if (refreshTime.value !== -1) {
            refreshTimeout = setTimeout(() => {
              getGraphData(true);
            }, refreshTime.value);
          }
        });
      if (isAutoRefresh) return;
      topoRawData = renderData as ITopoData;
      const rootNode = topoRawData.nodes.find(node => node.entity.is_root);
      if (!resourceNodeId.value && rootNode) {
        resourceNodeId.value = rootNode.id;
        nodeEntityId.value = rootNode.entity.entity_id;
        nodeEntityName.value = rootNode.entity.entity_name;
      }
    };

    /** 布局计算 */
    const resolveLayout = (data): Promise<any> => {
      const copyData = JSON.parse(JSON.stringify(data));
      const { layoutNodes, edges, nodes } = formatTopoData(copyData);
      const resolvedData = ElkjsUtils.getKlayGraphData({ nodes: layoutNodes, edges, source: nodes });
      return ElkjsUtils.getLayoutData(resolvedData).then(layouted => {
        ElkjsUtils.updatePositionFromLayouted(layouted, copyData);
        data.sub_combos?.length > 0 && ElkjsUtils.OptimizeLayout(layouted, copyData, edges);
        ElkjsUtils.setRootComboStyle(copyData.combos, graph.getWidth());
        return { layouted, data: copyData };
      });
    };
    function isItemInView(graph, itemId, containerWidth, containerHeight) {
      // 获取图表实例中的项目
      const item = graph.findById(itemId);
      if (!item) {
        console.error(`Item with id: ${itemId} not found`);
        return false;
      }

      const itemBBox = item.getBBox();

      // 当前组的矩阵，用于考虑缩放
      const matrix = graph.get('group').getMatrix();
      const currentScale = matrix ? matrix[0] : 1;

      // 获取项目位置基于缩放后的实际位置，进行缩放校正
      const scaledBBox = {
        minX: itemBBox.minX * currentScale,
        minY: itemBBox.minY * currentScale,
        maxX: itemBBox.maxX * currentScale,
        maxY: itemBBox.maxY * currentScale,
      };

      // 检查项目是否完全在视口内
      return (
        scaledBBox.minX >= 0 &&
        scaledBBox.maxX <= containerWidth &&
        scaledBBox.minY >= 0 &&
        scaledBBox.maxY <= containerHeight
      );
    }

    function moveToCenterIfNeeded(graph, itemId, containerWidth, containerHeight) {
      if (isItemInView(graph, itemId, containerWidth, containerHeight)) {
        console.info(`Item with id: ${itemId} is already in view`);
        graph.moveTo(0, 0);
        return;
      }

      const item = graph.findById(itemId);
      const itemBBox = item.getBBox();

      // 获取缩放比例
      const matrix = graph.get('group').getMatrix();
      const currentScale = matrix ? matrix[0] : 1;

      // 画布中心位置
      const canvasCenterX = containerWidth / 2;
      const canvasCenterY = containerHeight / 2;

      // 项目的中心位置
      const itemCenterX = (itemBBox.minX + itemBBox.maxX) / 2;
      const itemCenterY = (itemBBox.minY + itemBBox.maxY) / 2;

      // 计算将项目移动到画布中心所需的偏移量
      const moveX = canvasCenterX - itemCenterX * currentScale;
      const moveY = canvasCenterY - itemCenterY * currentScale;

      // 移动视口到目标位置
      graph.translate(moveX, moveY);
    }
    /** 线置于顶层 */
    const toFrontAnomalyEdge = () => {
      const edges = graph.getEdges();
      // biome-ignore lint/complexity/noForEach: <explanation>
      edges.forEach(edge => {
        edge.toFront();
      });
    };
    /** 渲染数据 */
    const renderGraph = (data = topoRawDataCache.value.complete, renderComplete = false) => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      edgeInterval.forEach(interval => {
        clearInterval(interval.timer);
      });
      edgeInterval = [];
      resolveLayout(data).then(resp => {
        graph.data(resp.data);
        graph.render();
        if (resourceNodeId.value) {
          const node = graph.findById(resourceNodeId.value);
          node && graph.setItemState(node, 'running', true);
        }
        setHighlightEdge();
        isRenderComplete.value = renderComplete;
        // 默认渲染最后帧
        // handleTimelineChange(topoRawDataCache.value.diff.length - 1);
        /** 获取用户拖动设置后的zoom缩放级别 */
        const zoom = localStorage.getItem('failure-topo-zoom');
        if (zoom) {
          handleZoomChange(zoom);
          zoomValue.value = Number(zoom);
        }
        moveToCenterIfNeeded(graph, resourceNodeId.value, graphRef.value.clientWidth, graphRef.value.clientHeight);
        // biome-ignore lint/complexity/noForEach: <explanation>
        data.nodes.forEach(node => {
          if (node.is_deleted) {
            const deleteNode = graph.findById(node.id) as INode;
            if (!deleteNode) return;
            // biome-ignore lint/complexity/noForEach: <explanation>
            deleteNode.getEdges().forEach(edge => edge.hide());
            deleteNode.hide();
          }
        });
        /** 布局渲染完将红线置顶 */
        setTimeout(toFrontAnomalyEdge, 500);
      });
    };
    // 清除边状态
    const clearEdgeState = (item: any, highlight = true) => {
      graph.getEdges().forEach(edge => {
        graph.clearItemStates(edge, ['dark', highlight && 'highlight']);
        graph.setItemState(item, 'dark', true);
        edge.toFront();
      });
    };
    onMounted(() => {
      getGraphData().then(initGraph);
    });

    /** 初始化图表相关 */
    const initGraph = async () => {
      if (!topoRawData) return;
      const { width, height } = graphRef.value.getBoundingClientRect();
      const maxHeight = Math.max(160 * ElkjsUtils.getRootCombos(topoRawData).length, height);
      registerCustomNode();
      registerCustomBehavior();
      registerCustomEdge();
      registerCustomTooltip();
      registerCustomCombo();
      graph = new Graph({
        container: graphRef.value as HTMLElement,
        width,
        height: maxHeight,
        fitViewPadding: 40,
        fitCenter: false,
        fitView: false,
        minZoom: MIN_ZOOM,
        maxZoom: 2,
        groupByTypes: false,
        plugins: [tooltips],
        defaultNode: {
          type: 'circle',
          size: 40,
          style: {
            cursor: 'pointer',
          },
          // 定义连接点
          anchorPoints: [
            [0.5, 0], // 顶部中间
            [0, 0.5], // 左侧中间
            [1, 0.5], // 右侧中间
            [0.5, 1], // 底部中间
          ],
        },
        defaultEdge: {
          size: 1,
          color: '#63656D',
          style: {
            cursor: 'pointer',
          },
        },
        modes: {
          default: [
            'drag-node-with-fixed-combo',
            'drag-canvas-no-move',
            'drag-canvas-move',
            {
              type: 'scroll-canvas',
              scalableRange: -0.92,
            },
          ],
        },
        comboStateStyles: {
          active: {
            fill: '#3A3B3D',
            stroke: '#3A3B3D',
          },
          inactive: {
            fill: '#3A3B3D',
            stroke: '#3A3B3D',
          },
        },
      });
      graph.node(node => {
        return {
          ...node,
          stateStyles: {
            active: {
              stroke: '#3A3B3D',
            },
          },
          type: 'topo-node',
        };
      });
      graph.edge((cfg: any) => {
        const { is_anomaly, edge_type, anomaly_score, source, target } = cfg;
        const isInvoke = edge_type === 'ebpf_call';
        const color = is_anomaly ? '#F55555' : '#63656E';
        const isSelfLoop = source === target;

        const edg = {
          ...cfg,
          shape: 'quadratic',
          style: {
            cursor: 'pointer',
            lineAppendWidth: 15,
            endArrow:
              isInvoke || is_anomaly
                ? {
                    path: Arrow.triangle(10, 10, 0),
                    d: 0,
                    fill: color,
                    stroke: color,
                    lineDash: [0, 0],
                  }
                : false,
            // fill: isInvoke ? '#F55555' : '#63656E',
            stroke: color,
            lineWidth: is_anomaly ? (anomaly_score > 0 ? 3 : 1.5) : 1,
            lineDash: is_anomaly ? [4, 2] : false,
          },
        };
        if (!cfg.color) return edg;
        if (isSelfLoop) {
          return {
            ...edg,
            shape: 'loop',
            type: 'topo-edge-loop',
            loopCfg: {
              dist: 60, // 自环边与节点的距离
              clockwise: true, // 顺时针方向
            },
          };
        }
        return {
          ...edg,
          shape: 'quadratic',
          type: 'topo-edge',
        };
      });
      graph.combo((cfg: any) => {
        const originLabel = cfg.originLabel || cfg.label;
        const model = {
          ...cfg,
          originLabel: originLabel,
        };
        if (cfg.parentId) {
          // label宽度为cfg.width减去"反馈根因节点"文本宽度
          const labelWidth = cfg.width - (cfg.is_feedback_root ? 90 : 56);
          const link = canJumpByType(cfg);
          const fill = link ? '#699DF4' : '#C4C6CC';
          return {
            ...model,
            type: 'service-combo',
            label: accumulatedWidth(cfg.label, labelWidth),
            style: {
              fill: '#34383d',
              stroke: '#7A7C80',
              lineWidth: 1,
              lineDash: [2, 3],
              opacity: 1,
              radius: 4,
            },
            labelCfg: {
              style: {
                fill,
                opacity: 1,
                cursor: link ? 'pointer' : 'default',
              },
              // 启用 label 事件捕获
              triggerable: true,
            },
          };
        }
        return model;
      });
      renderGraph();
      /** 点击tips时，关闭右侧资源打开的tips */
      graph.on('tooltipchange', ({ action }) => {
        if (action === 'show' && showResourceGraph.value) {
          resourceGraphRef.value.hideToolTips();
        }
      });
      /** 点击非节点、非边，清除高亮状态 */
      graph.on('click', e => {
        if (!e.item || (e.item.getType() !== 'node' && e.item.getType() !== 'edge')) {
          clearAllStats();
        }
        setTimeout(toFrontAnomalyEdge, 500);
      });

      // 展示被截断的combo label的详细信息
      const comboLabelTooltip = document.getElementById('combo-label-tooltip');
      comboLabelTooltip.innerHTML = ' ';
      graph.on('combo:mouseenter', e => {
        const { item } = e;
        const model = item.getModel();

        const fullLabel = model.originLabel;
        // 只有被截断的combo label才显示 Tooltip
        if (fullLabel && fullLabel !== model.label) {
          // 获取 Combo 的包围盒坐标
          const bbox = item.getBBox();
          // 转换画布坐标到页面坐标
          const canvasPoint = graph.getCanvasByPoint(bbox.x, bbox.y);
          const containerRect = graph.getContainer().getBoundingClientRect();
          const x = containerRect.left + canvasPoint.x;
          const y = containerRect.top + canvasPoint.y;

          comboLabelTooltip.innerHTML = `
            <p><span class='combo-label-text'>名称：</span>${fullLabel as string}</p>
            <p><span class='combo-label-text'>类型：</span>${(model.entity as any)?.properties?.entity_category as string}</p>
          `;
          const tooltipHeight = comboLabelTooltip.offsetHeight;
          comboLabelTooltip.style.left = `${x}px`;
          comboLabelTooltip.style.top = `${y - tooltipHeight}px`;
          comboLabelTooltip.style.visibility = 'visible';
        }

        // 移入展示"反馈新根因"文本
        if (!item.getModel().parentId) return;
        graph.setItemState(item, 'hover', true);
        const feedbackImg = item.getContainer().find(ele => ele.get('name') === 'sub-combo-feedback-img');
        const feedbackText = item.getContainer().find(ele => ele.get('name') === 'sub-combo-feedback-text');
        if (feedbackImg) feedbackImg.attr('opacity', 1);
        if (feedbackText) feedbackText.attr('opacity', 1);
      });

      graph.on('combo:mouseleave', e => {
        // 移出隐藏combo label的Tooltip
        comboLabelTooltip.style.visibility = 'hidden';

        // 移出隐藏"反馈新根因"文本
        const { item } = e;
        const model = item.getModel();
        if (!model.parentId) return;
        graph.setItemState(item, 'hover', false);
        const container = item.getContainer();
        const feedbackImg = container.find(ele => ele.get('name') === 'sub-combo-feedback-img');
        const feedbackText = container.find(ele => ele.get('name') === 'sub-combo-feedback-text');

        if (feedbackImg) feedbackImg.attr('opacity', 0);
        if (feedbackText) feedbackText.attr('opacity', 0);
      });

      // 展示节点的详细信息
      const nodeInfoTooltip = document.getElementById('node-detail-tips');
      // 初始化时清空工具提示内容
      nodeInfoTooltip.innerHTML = ' ';
      graph.on('node:mouseenter', e => {
        const { item } = e;
        graph.setItemState(item, 'hover', true);

        /**
         * 处理组合节点Combo的悬停状态联动
         * 当节点属于某个Combo时，需要同时激活父Combo的悬停状态
         */
        const model = item.getModel() as ITopoNode;
        if (model.subComboId) {
          const combo = graph.findById(model.subComboId);
          if (!combo) return;
          // const label = combo.getContainer().find(element => element.get('type') === 'text');
          // if (label) {
          //   label.attr('opacity', 1); // 悬停时显示标签
          // }
          combo && graph.setItemState(combo, 'hover', true);
        }

        /**
         * 计算并显示节点信息工具提示
         * 1. 获取节点在画布中的位置
         * 2. 转换为页面绝对坐标
         * 3. 动态调整提示框位置避免超出视口
         */
        // 获取节点的包围盒
        const bbox = item.getBBox();
        // 将画布坐标转换为页面坐标
        // 获取节点左上角画布坐标
        const canvasPoint = graph.getCanvasByPoint(bbox.x, bbox.y);
        // 获取画布容器视口信息
        const containerRect = graph.getContainer().getBoundingClientRect();
        // 计算页面绝对X坐标、Y坐标
        const x = containerRect.left + canvasPoint.x;
        const y = containerRect.top + canvasPoint.y;

        // 生成工具提示内容
        nodeInfoTooltip.innerHTML = handleNodeInfoTooltip(model);
        // 获取提示框渲染后尺寸
        const { offsetWidth, offsetHeight } = nodeInfoTooltip;

        // 判断节点是否靠近画布左侧/右侧边缘
        const isNearLeft = canvasPoint.x < offsetWidth / 2;
        const isNearRight = canvasPoint.x + offsetWidth / 2 >= containerRect.width;
        if (isNearLeft) {
          // 提示框左对齐节点左上角
          nodeInfoTooltip.style.left = `${x}px`;
        } else if (isNearRight) {
          // 提示框右对齐节点左上角
          nodeInfoTooltip.style.left = `${x - offsetWidth}px`;
        } else {
          // 提示框中心对齐节点顶部中心
          nodeInfoTooltip.style.left = `${x - offsetWidth / 2 + 40}px`;
        }
        // 提示框底部对齐节点顶部，预留5px间隙
        nodeInfoTooltip.style.top = `${y - offsetHeight - 5}px`;
        nodeInfoTooltip.style.visibility = 'visible';
        return;
      });
      /** 监听手势缩放联动缩放轴数据 */
      graph.on('viewportchange', ({ action }) => {
        if (action === 'zoom') {
          zoomValue.value = graph.getZoom() * 10;
        }
        const currentZoom = graph.getZoom();
        // if (action === 'translate') {
        const comboModel = (graph.getCombos() as any)[0].getModel() as { height: number; width: number };
        const labelPoint = {
          x: -(comboModel.width / 2 + 10) * currentZoom,
          y: -(comboModel.height / 2 + 30) * currentZoom,
        };
        const canvasCenter = graph.getGraphCenterPoint(); // 画布中心
        if (canvasCenter.x < Math.abs(labelPoint.x)) {
          const x = -(canvasCenter.x - 5) / currentZoom;
          moveComboLabelPosition({ x });
          rootComboMovePoint.value.x = x;
        } else {
          rootComboMovePoint.value.x = null;
          moveComboLabelPosition({ x: labelPoint.x / currentZoom });
        }
        // }
      });
      // 监听鼠标离开节点
      graph.on('node:mouseleave', e => {
        // 鼠标移出隐藏node详情Tooltip
        nodeInfoTooltip.style.visibility = 'hidden';

        const nodeItem = e.item;
        // 移出隐藏名称
        const model = nodeItem.getModel() as ITopoNode;
        if (model.subComboId) {
          const combo = graph.findById(model.subComboId);
          if (!combo) return;
          // const label = combo.getContainer().find(element => element.get('type') === 'text');
          // if (label) {
          //   label.attr('opacity', 0);
          // }
        }
        graph.setItemState(nodeItem, 'hover', false);
      });
      /** resize之后的render 调用一次缓存的函数 通知可以播放 */
      graph.on('afterrender', () => {
        resizeCacheCallback.value?.();
      });
      /** 设置节点高亮状态 */
      graph.on('node:click', event => {
        const { item } = event;
        graph.setAutoPaint(false);
        /** 根据边的关系设置节点状态 */
        // biome-ignore lint/complexity/noForEach: <explanation>
        graph.getEdges().forEach(edge => {
          if (edge.getSource() === item) {
            graph.setItemState(edge, 'dark', true);
            edge.toFront();
          } else if (edge.getTarget() === item) {
            graph.setItemState(edge, 'dark', true);
            edge.toFront();
          } else {
            graph.setItemState(edge, 'dark', false);
          }
        });
        // biome-ignore lint/complexity/noForEach: <explanation>
        graph.getNodes().forEach(node => {
          graph.clearItemStates(node, ['dark', 'highlight']);
          graph.setItemState(node, 'dark', true);
          node.toFront();
        });
        graph.setItemState(item, 'dark', false);
        graph.setItemState(item, 'highlight', true);
        graph.paint();
        graph.setAutoPaint(true);
      });
      /** 设置边高亮状态 */
      graph.on('edge:click', ({ item }) => {
        graph.setAutoPaint(false);
        // biome-ignore lint/complexity/noForEach: <explanation>
        const { source, target, count } = item.getModel();
        clearEdgeState(item, count === 1);
        graph.paint();
        graph.setAutoPaint(true);
        item.toFront();
        resourceEdgeId.value = `${source}-${target}`;
        // 非聚合的则直接切换
        if (count === 1) {
          graph.setItemState(item, 'highlight', true);
          graph.setItemState(item, 'dark', true);
        }
      });
      /** 清除高亮状态 */
      function clearAllStats() {
        graph.setAutoPaint(false);
        // biome-ignore lint/complexity/noForEach: <explanation>
        graph.getEdges().forEach(edge => {
          const { source, target } = edge.getModel();
          if (`${source}-${target}` === resourceEdgeId.value) {
            edge.toFront();
            return;
          }
          graph.clearItemStates(edge, ['dark', 'highlight']);
          // graph.setItemState(edge, 'dark', true);
          edge.toFront();
        });
        // biome-ignore lint/complexity/noForEach: <explanation>
        graph.getNodes().forEach(node => {
          graph.clearItemStates(node, ['dark', 'highlight']);
          node.toFront();
        });
        graph.paint();
        graph.setAutoPaint(true);
      }

      graph.on('combo:click', e => {
        tooltipsRef.value?.hide?.();
        tooltips.hide();
        comboLabelTooltip.style.visibility = 'hidden';

        // 点击"反馈新根因"，打开反馈弹窗
        const { target, item } = e;
        const model = item.getModel();
        if (model.type !== 'service-combo') return;
        if (target.get('name') === 'text-shape') {
          handleToLink(model, bkzIds.value, incidentDetailData.value);
          return;
        }
        if (target.get('className') === 'sub-combo-label-feedback') {
          handleFeedBack(model);
        }
      });
      /** 触发下一帧播放 - 动画完成后继续处理队列 */
      graph.on('afteritemstatechange', ({ state }) => {
        if (state && !(state as string).includes('show-animate')) return;
        // 如果正在播放且正在处理队列，动画完成后继续处理队列
        if (isPlay.value && isProcessingQueue && processNext) {
          clearTimeout(playTime);
          playTime = setTimeout(() => {
            // 动画完成后继续处理队列中的下一帧
            if (isPlay.value && playQueue.length > 0 && processNext) {
              processNext();
            }
          }, 1000);
        }
      });
      nextTick(() => {
        addListener(graphRef.value as HTMLElement, onResize);
      });
    };
    onUnmounted(() => {
      edgeInterval.forEach(interval => {
        clearInterval(interval.timer);
      });
      edgeInterval = [];
      clearTimeout(playTime);
      clearTimeout(refreshTimeout);
      // 清空播放队列
      playQueue = [];
      isProcessingQueue = false;
      graphRef.value && removeListener(graphRef.value as HTMLElement, onResize);
    });

    /** 处理节点详情info tooltip内部结构 */
    const handleNodeInfoTooltip = (model: ITopoNode) => {
      let nodeDetailTips = [];
      const isShowRootText = model.is_feedback_root || checkIsRoot(model?.entity);
      // 节点名称
      nodeDetailTips.push({ label: t('名称'), value: model.entity.entity_name });
      // 节点告警信息
      if (model.alert_display?.alert_name) {
        nodeDetailTips.push({
          label: t('包含告警'),
          value: `${model.alert_display?.alert_name} ${
            model.alert_display?.alert_name && model.alert_ids?.length > 1
              ? t('等共 {0} 个同类告警', [model.alert_ids.length])
              : ''
          } `,
        });
      }
      // 节点异常信息
      if (isShowRootText && model.entity?.rca_trace_info?.abnormal_message) {
        nodeDetailTips.push({ label: t('异常信息'), value: model.entity.rca_trace_info.abnormal_message });
      }
      // 节点其他信息组
      const res = [
        { label: t('分类'), value: model.entity.rank.rank_category.category_alias },
        { label: t('节点类型'), value: model.entity.properties?.entity_category || model.entity.rank_name },
        { label: t('所属业务'), value: `[#${model.bk_biz_id}] ${model.bk_biz_name}` },
      ];
      nodeDetailTips = nodeDetailTips.concat(res);
      // 节点服务信息
      if (model.entity?.tags?.BcsService) {
        nodeDetailTips.push({ label: t('所属服务'), value: model.entity?.tags?.BcsService?.name });
      }

      return nodeDetailTips
        .map(
          item =>
            `<div
              key=${item.label}
              class='node-detail-tips_item'
            >
              <span class='item-label'>${item.label}：</span>
              <span class='item-value'>${item.value}</span>
            </div>`
        )
        .join('');
    };

    /** 处理单个边的公共逻辑*/
    const processEdge = (edge, nodes, isAggregatedEdge = false) => {
      const model = deepClone(edge);
      model.id = `edge-${random(10)}`;
      const getEntityData = prefix =>
        isAggregatedEdge
          ? {
              entity: {
                is_anomaly: model[`${prefix}_is_anomaly`],
                is_on_alert: model[`${prefix}_is_on_alert`],
                entity_name: model[`${prefix}_name`],
                entity_type: model[`${prefix}_type`],
              },
            }
          : {};

      const targetModel = nodes.find(item => item.id === model.target);
      const sourceModel = nodes.find(item => item.id === model.source);
      model.nodes = [
        {
          ...getEntityData('source'),
          ...sourceModel,
          events: model.events || [],
        },
        {
          ...getEntityData('target'),
          ...targetModel,
          events: model.events || [],
        },
      ];

      return model;
    };

    /** 整合关联边数据 */
    const filterEdges = (edges, nodes, nodeId) => {
      const result = [];
      const checkAndProcess = (edge, isAggregated = false) => {
        if (edge.source === nodeId || edge.target === nodeId) {
          result.push(processEdge(edge, nodes, isAggregated));
        }
      };

      // biome-ignore lint/complexity/noForEach: <explanation>
      edges.forEach(mainEdge => {
        checkAndProcess(mainEdge);
        // biome-ignore lint/complexity/noForEach: <explanation>
        mainEdge.aggregated_edges?.forEach(aggEdge => {
          checkAndProcess(aggEdge, true);
        });
      });
      return result;
    };
    // 切换node清除高亮边信息
    const setHighlightEdge = (highlight = true, nodeId = '') => {
      if (resourceEdgeId.value) {
        const edge = graph.getEdges().find(edge => {
          const { source, target } = edge.getModel();
          return `${source}-${target}` === resourceEdgeId.value;
        });
        highlight && edge && graph.setItemState(edge, 'highlight', true);
        if (!highlight && edge) {
          const statesToClear = nodeId && resourceEdgeId.value.includes(nodeId) ? ['highlight'] : ['highlight', 'dark'];
          graph.clearItemStates(edge, statesToClear);
        }
      }
      if (!highlight) resourceEdgeId.value = '';
    };
    /** 通过主画布的tooltip打开节点/边概览 */
    const handleViewServiceFromTopo = ({ type, data, sourceNode, isAggregatedEdge }) => {
      if (type === 'node') {
        setHighlightEdge(false, sourceNode.id);
        if (!showServiceOverview.value) {
          showServiceOverview.value = true;
        } else {
          const node = graph.findById(sourceNode.id);
          graph.setItemState(node, 'running', true);
        }
        // 如果之前有选中的节点且不是当前节点，取消其'running'状态
        if (resourceNodeId.value && resourceNodeId.value !== sourceNode.id) {
          const node = graph.findById(resourceNodeId.value);
          graph.setItemState(node, 'running', false);
        }

        nodeDetail.value = data;
        const { edges = [], nodes = [] } = topoRawDataCache.value.complete;
        curLinkedEdges.value = filterEdges(edges, nodes, data.id);

        // 保存当前选中节点的ID
        resourceNodeId.value = sourceNode.id;
        nodeEntityId.value = data?.entity?.entity_id || data?.model?.entity?.entity_id;
        emit('changeSelectNode', sourceNode.id);
      } else {
        if (!showServiceOverview.value) {
          showServiceOverview.value = true;
        }
        edgeDetail.value = data;
        isClickEdgeItem.value = true;
        // 处理聚合边,聚合边只有明确选中才高亮
        if (isAggregatedEdge) {
          const edges = graph.getEdges();
          // 遍历每个边，查找匹配的属性
          const edge = edges.find(edge => {
            const model = edge.getModel();
            return (
              model.source === sourceNode?.[0]?.entity?.entity_id && model.target === sourceNode?.[1]?.entity?.entity_id
            );
          });
          if (!edge.hasState('highlight')) {
            clearEdgeState(edge);
            graph.setItemState(edge, 'highlight', true);
            graph.setItemState(edge, 'dark', true);
          }
        }
      }
      // 当前节点/边的类型
      detailType.value = type;
      tooltipsRef.value.hide();
      tooltips.hide();
    };

    /** 通过资源拓扑的tooltip打开节点/边概览 */
    const handleViewServiceFromResource = ({ type, data }) => {
      if (type === 'node') {
        if (!showServiceOverview.value) {
          showServiceOverview.value = true;
        }
        nodeDetail.value = data;
        const { edges = [], nodes = [] } = topoRawDataCache.value.complete;
        curLinkedEdges.value = filterEdges(edges, nodes, data.id);
        detailType.value = 'node';
        showViewResource.value = false;
      }
    };

    /** 通过顶部开关打开节点/边概览，展示当前选中节点的概览 */
    const handleViewServiceFromTop = () => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getNodes().forEach(node => {
        const model = node.getModel();
        if ((model.entity as { entity_id: string })?.entity_id === nodeEntityId.value) {
          nodeDetail.value = model;
          detailType.value = 'node';
          const { edges = [], nodes = [] } = topoRawDataCache.value.complete;
          curLinkedEdges.value = filterEdges(edges, nodes, model.id);
        }
      });
    };

    /** 打开资源拓朴 */
    const handleViewResource = ({ sourceNode, node }) => {
      if (!showResourceGraph.value) {
        showResourceGraph.value = !showResourceGraph.value;
      } else {
        const node = graph.findById(sourceNode.id);
        graph.setItemState(node, 'running', true);
      }
      // 如果之前有选中的节点(resourceNodeId.value存在)且不是当前节点，则取消其'running'状态
      if (resourceNodeId.value && resourceNodeId.value !== sourceNode.id) {
        const node = graph.findById(resourceNodeId.value);
        graph.setItemState(node, 'running', false);
      }
      // 保存当前选中节点的ID
      resourceNodeId.value = sourceNode.id;
      nodeEntityId.value = node?.entity?.entity_id || node?.model?.entity?.entity_id;
      nodeEntityName.value = node?.entity?.entity_name || node?.model?.entity?.entity_name;
      nodeDetail.value = sourceNode;
      tooltips.hide();
      emit('changeSelectNode', sourceNode.id);
    };
    /** 反馈根因 */
    const feedbackIncidentRootApi = (isCancel = false) => {
      const { id, incident_id, bk_biz_id } = incidentDetailData.value;
      const params = {
        id,
        incident_id,
        bk_biz_id,
        feedback: {
          incident_root: feedbackModel.value.entity.entity_id,
          content: '',
        },
      };
      if (isCancel) {
        (params as any).is_cancel = true;
      }
      feedbackIncidentRoot(params).then(async () => {
        Message({
          theme: 'success',
          message: t('取消反馈成功'),
        });
        await getGraphData();
        renderGraph();

        // 刷新节点概览数据
        setTimeout(() => {
          handleViewServiceFromTop();
        }, 500);
      });
    };
    /** 反馈新根因， 反馈后需要重新调用接口拉取数据 */
    const handleFeedBack = model => {
      tooltipsRef.value?.hide?.();
      tooltips.hide();
      feedbackModel.value = model;
      if (model.is_feedback_root) {
        feedbackIncidentRootApi(true);
        return;
      }
      feedbackCauseShow.value = true;
    };
    /** 聚合规则变化 */
    const handleUpdateAggregateConfig = async config => {
      aggregateConfig.value = config.aggregate_config;
      autoAggregate.value = config.auto_aggregate;
      aggregateCluster.value = config.aggregate_cluster;
      await getGraphData();
      renderGraph();
    };
    /** 自动刷新时间变化 */
    const handleChangeRefleshTime = RefleshTime => {
      clearTimeout(refreshTimeout);
      refreshTime.value = RefleshTime;
      if (RefleshTime !== -1 && !isPlay.value) {
        refreshTimeout = setTimeout(() => getGraphData(true), RefleshTime);
      }
    };
    /** 播放某一帧的图 */
    const handleRenderTimeline = () => {
      /** 播放时关闭查看资源态 */
      showResourceGraph.value = false;
      /** 播放时关闭查看节点/边概览态 */
      showServiceOverview.value = false;
      /** 播放时清楚自动刷新 */
      clearTimeout(refreshTimeout);
      /** 对比node是否已经展示，已经展示还存在diff中说明只是状态变更以及对比每个展示的node都需要判断边关系的node是在展示状态 */
      const { showNodes, content, showEdges, showSubCombos } = topoRawDataCache.value.diff[timelinePosition.value];
      const currNodes = topoRawDataCache.value.diff[timelinePosition.value].content.nodes;
      const currEdges = topoRawDataCache.value.diff[timelinePosition.value].content.edges;
      const randomStr = random(8);
      let next = false;

      // 处理边的更新，与 handleTimelineChange 保持一致
      const edges = graph.getEdges();
      const findEdges = (edges, target) => {
        return edges.find(item => item.source === target.source && target.target === item.target);
      };
      const updateEdges = currEdges;
      // biome-ignore lint/complexity/noForEach: <explanation>
      edges.forEach(edge => {
        const edgeModel = edge.getModel();
        const targetEdge = findEdges(updateEdges, edgeModel);
        if (targetEdge) {
          graph.updateItem(edge, { ...edge, ...targetEdge });
        } else {
          // 如果当前帧没有该边，尝试从 showEdges 或 complete.edges 中恢复
          const currEdges =
            findEdges(showEdges, edgeModel) || findEdges(topoRawDataCache.value.complete.edges, edgeModel);
          if (currEdges && edgeModel && !isEqual(currEdges, edgeModel)) {
            graph.updateItem(edge, { ...edge, ...currEdges });
          }
        }
      });

      // 处理节点的更新，与 handleTimelineChange 保持一致
      // 遍历所有 complete.nodes，确保所有节点状态都正确
      // biome-ignore lint/complexity/noForEach: <explanation>
      topoRawDataCache.value.complete.nodes.forEach(({ id }) => {
        // 查找节点：与 handleTimelineChange 的逻辑保持一致
        // showNode: 在 showNodes 和 currNodes 的合并数组中查找（用于获取节点数据）
        const showNode = [...showNodes, ...currNodes].reverse().find(item => item.id === id);
        const deleteNodeIds = showNodes.filter(item => item.is_deleted).map(item => item.id);
        const diffNode = currNodes.find(item => item.id === id);
        // nodeInShowNodes: 单独在 showNodes 中查找，用于判断节点是否之前存在
        const nodeInShowNodes = showNodes.find(item => item.id === id);
        // diffData: 节点在 showNodes 中但不在 currNodes 中（之前存在，当前帧没有变化）
        const diffData = !diffNode && nodeInShowNodes;
        const updateNode = diffData ? showNode : diffNode;

        if ((!nodeInShowNodes && !diffNode) || deleteNodeIds.includes(id)) {
          // 节点应该隐藏：既不在 showNodes 中，也不在 currNodes 中，或者被标记为删除
          const node = graph.findById(id);
          node && graph.hideItem(node);
        } else if (diffNode || diffData) {
          // 节点应该显示：在 currNodes 中（当前帧有变化）或在 showNodes 中（之前存在）
          const node = graph.findById(updateNode.id);
          if (node) {
            const model = node?.getModel?.();
            // 判断是否为新节点：在 currNodes 中但不在 showNodes 中
            const isNewNode = !nodeInShowNodes && diffNode;

            if (isNewNode) {
              // 新节点：需要设置动画
              next = true;
              graph.updateItem(node, {
                ...node,
                ...updateNode,
                comboId: model.comboId,
                subComboId: model.subComboId,
              });
              graph.setItemState(node, 'show-animate', randomStr);
              const edges = (node as any).getEdges();
              // biome-ignore lint/complexity/noForEach: <explanation>
              edges.forEach(edge => {
                const edgeModel = edge.getModel();
                const edgeNode = [...showNodes, ...currNodes].find(node => {
                  return edgeModel.source === updateNode.id
                    ? node.id === edgeModel.target
                    : node.id === edgeModel.source;
                });
                edgeNode && graph.setItemState(edge, 'show-animate', randomStr);
              });
            } else {
              // 已存在的节点：需要更新状态
              // 与 handleTimelineChange 的逻辑保持一致
              if (diffNode?.is_deleted) {
                // 节点被标记为删除
                node?.hide?.();
                (node as any)?.getEdges()?.forEach(edge => edge?.hide());
              } else {
                // 节点应该显示
                // 如果节点之前是隐藏状态，先显示
                if (model.is_deleted) {
                  node?.show?.();
                  (node as any)?.getEdges()?.forEach(edge => edge?.show());
                }
                // 更新节点数据
                graph.showItem(node);
                graph.updateItem(node, {
                  ...updateNode,
                  is_deleted: false,
                  comboId: model.comboId,
                  subComboId: model.subComboId,
                });
              }
            }
          }
        }
      });

      // 处理 combo 的更新，与 handleTimelineChange 保持一致
      const combos = graph.getCombos().filter(combo => combo.getModel().parentId);
      // biome-ignore lint/complexity/noForEach: <explanation>
      combos.forEach(combo => {
        const { entity, id, comboId } = combo.getModel() as ITopoNode;
        // 使用 showSubCombos 和 content.sub_combos，与 handleTimelineChange 保持一致
        const updateCombo = [...showSubCombos, ...content.sub_combos]
          .reverse()
          .find(item => item.id === entity.entity_id);
        const nodes = topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
        const showNodes = nodes.filter(({ id }) => {
          const node = graph.findById(id);
          return node?._cfg.visible;
        });
        updateCombo &&
          graph.updateItem(combo, {
            ...combo,
            id,
            comboId,
            is_feedback_root: updateCombo.is_feedback_root,
            entity: {
              ...updateCombo.entity,
            },
            alert_all_recorved: updateCombo.alert_all_recorved,
            is_on_alert: updateCombo.is_on_alert,
          });
        updateCombo && ServiceCombo.labelChange(combo);

        graph[showNodes.length > 0 ? 'showItem' : 'hideItem'](combo);
      });
      return currNodes.length === 0 || !next;
    };
    /** 判断资源图或者节点/边概览是否为开启状态 是的话关闭状态并等待重新布局 */
    const handleResetPlay = playOption => {
      if (showResourceGraph.value || showServiceOverview.value) {
        showResourceGraph.value = false;
        showServiceOverview.value = false;
        resizeCacheCallback.value = () => {
          setTimeout(() => handlePlay(playOption), 500);
          resizeCacheCallback.value = null;
        };
        return;
      }
      handlePlay(playOption);
    };
    /** 处理播放队列中的下一帧 */
    let processNext: (() => void) | null = null;

    /** 处理播放队列 */
    const processPlayQueue = () => {
      if (isProcessingQueue || playQueue.length === 0) {
        return;
      }

      isProcessingQueue = true;
      processNext = () => {
        // 检查播放状态和队列状态
        if (!isPlay.value) {
          // 如果暂停了，停止处理但保留队列状态
          isProcessingQueue = false;
          return;
        }

        if (playQueue.length === 0) {
          // 队列处理完成
          isProcessingQueue = false;
          isPlay.value = false;
          emit('playing', false);
          handleChangeRefleshTime(refreshTime.value);
          return;
        }

        // 检查队列中的第一个帧是否与当前位置一致（避免重复处理）
        const nextIndex = playQueue[0];
        if (nextIndex === timelinePosition.value && playQueue.length > 1) {
          // 如果队列第一个帧与当前位置一致，且还有后续帧，跳过当前帧
          playQueue.shift();
          processNext();
          return;
        }

        const currentIndex = playQueue.shift();
        if (currentIndex === undefined) {
          isProcessingQueue = false;
          return;
        }

        const len = topoRawDataCache.value.diff.length;
        if (currentIndex >= len) {
          timelinePosition.value = topoRawDataCache.value.diff.length - 1;
          isPlay.value = false;
          emit('playing', false);
          handleChangeRefleshTime(refreshTime.value);
          isProcessingQueue = false;
          return;
        }

        timelinePosition.value = currentIndex;
        emit('playing', true, currentIndex);

        // 直接渲染当前帧，不再需要预先计算 hideNodes
        handleRenderTimeline();

        // 延迟处理下一帧，确保DOM渲染完成
        clearTimeout(playTime);
        playTime = setTimeout(() => {
          if (isPlay.value && playQueue.length > 0) {
            // 继续处理队列中的下一帧
            processNext();
          } else {
            // 队列处理完成或已暂停
            isProcessingQueue = false;
            if (isPlay.value && playQueue.length === 0) {
              // 队列处理完成
              isPlay.value = false;
              emit('playing', false);
              handleChangeRefleshTime(refreshTime.value);
            }
          }
        }, 600); // 没有动画时，短暂延迟即可
      };

      processNext();
    };

    /** 播放 */
    const handlePlay = playOption => {
      const { value } = playOption;
      // 注意：isStart 参数在队列版本中不再使用，队列处理函数会根据 currentIndex 自动判断

      if ('timeline' in playOption) {
        timelinePosition.value = 0;
        // 重置时清空队列
        playQueue = [];
        isProcessingQueue = false;
      }

      isPlay.value = value;

      if (value) {
        // 开始播放
        const len = topoRawDataCache.value.diff.length;

        // 如果队列为空，或者队列第一个帧不等于当前位置，需要重新构建队列
        // 这包括以下情况：
        // 1. 首次播放（队列为空）
        // 2. 暂停后恢复播放，但用户手动切换了帧（队列第一个帧 != 当前位置）
        // 3. 播放时用户点击了其他帧（已在 handleTimelineChange 中处理，但这里作为兜底）
        if (playQueue.length === 0 || (playQueue.length > 0 && playQueue[0] !== timelinePosition.value)) {
          // 重新构建从当前位置到末尾的播放队列
          playQueue = [];
          for (let i = timelinePosition.value; i < len; i++) {
            playQueue.push(i);
          }
        }

        // 如果队列为空，说明已经播放完毕
        if (playQueue.length === 0) {
          timelinePosition.value = topoRawDataCache.value.diff.length - 1;
          isPlay.value = false;
          emit('playing', false);
          handleChangeRefleshTime(refreshTime.value);
          return;
        }

        // 开始处理队列
        // 如果之前正在处理但被暂停了，需要重置标志并重新开始
        if (isProcessingQueue) {
          isProcessingQueue = false;
        }
        processPlayQueue();
      } else {
        // 暂停播放：不清空队列，保留队列状态以便恢复播放
        // 清除定时器，停止队列处理
        clearTimeout(playTime);
        // 重置处理标志，确保恢复播放时可以重新开始
        isProcessingQueue = false;
        // 注意：processNext 函数内部会检查 isPlay.value，如果为 false 会自动停止
        // 但我们需要重置 isProcessingQueue，以便恢复播放时可以重新调用 processPlayQueue
      }
    };
    /** 点击展示某一帧的图 */
    const handleTimelineChange = (value, init = false) => {
      if (!init && value === timelinePosition.value) return;

      // 如果正在播放时切换帧，需要重新构建队列并立即渲染当前帧
      if (isPlay.value && !init) {
        // 清空当前队列，重新构建从新位置开始的队列
        playQueue = [];
        clearTimeout(playTime);
        isProcessingQueue = false;
        const len = topoRawDataCache.value.diff.length;
        // 构建从新位置到末尾的播放队列
        for (let i = value; i < len; i++) {
          playQueue.push(i);
        }
        // 如果队列为空，停止播放
        if (playQueue.length === 0) {
          isPlay.value = false;
          emit('playing', false);
          handleChangeRefleshTime(refreshTime.value);
        } else {
          // 立即渲染当前帧，然后继续播放队列
          // 渲染当前帧
          if (topoRawDataCache.value.diff[value]) {
            handleRenderTimeline();
          }
          // 继续处理队列
          processPlayQueue();
        }
        // 直接返回，避免执行下面的非播放状态下的渲染逻辑
        return;
      }

      timelinePosition.value = value;
      if (!isPlay.value && topoRawDataCache.value.diff[value]) {
        /** 切换帧时 */
        showResourceGraph.value = false;
        showServiceOverview.value = false;
        /** 直接切换到对应帧时，直接隐藏掉未出现的帧，并更新当前帧每个node的节点数据 */
        /** 注意：需要支持从后往前切换的场景，确保所有节点都按照目标帧的状态来处理 */
        const { showNodes, content, showEdges, showSubCombos } = topoRawDataCache.value.diff[value];
        const updateEdges = content.edges;
        // biome-ignore lint/complexity/noForEach: <explanation>
        topoRawDataCache.value.complete.nodes.forEach(({ id }) => {
          // 查找节点：与 handleRenderTimeline 的逻辑保持一致
          // showNode: 在 showNodes 和 content.nodes 的合并数组中查找（用于获取节点数据）
          const showNode = [...showNodes, ...content.nodes].reverse().find(item => item.id === id);
          const deleteNodeIds = showNodes.filter(item => item.is_deleted).map(item => item.id);
          const diffNode = content.nodes.find(item => item.id === id);
          // nodeInShowNodes: 单独在 showNodes 中查找，用于判断节点是否之前存在
          const nodeInShowNodes = showNodes.find(item => item.id === id);
          // diffData: 节点在 showNodes 中但不在 content.nodes 中（之前存在，当前帧没有变化）
          const diffData = !diffNode && nodeInShowNodes;
          const updateNode = diffData ? showNode : diffNode;

          if ((!nodeInShowNodes && !diffNode) || deleteNodeIds.includes(id)) {
            // 节点应该隐藏：既不在 showNodes 中，也不在 content.nodes 中，或者被标记为删除
            const node = graph.findById(id);
            node && graph.hideItem(node);
          } else if (diffNode || diffData) {
            // 节点应该显示：在 content.nodes 中（当前帧有变化）或在 showNodes 中（之前存在）
            const node = graph.findById(updateNode.id);
            if (node) {
              const model = node?.getModel?.();
              // 如果节点之前是隐藏状态，先显示
              if (model.is_deleted) {
                node?.show?.();
                (node as any)?.getEdges()?.forEach(edge => edge?.show());
              }
              // 更新节点数据
              graph.showItem(node);
              graph.updateItem(node, { ...updateNode, comboId: model.comboId, subComboId: model.subComboId });
            }
          }
        });
        const edges = graph.getEdges();
        const findEdges = (edges, target) => {
          return edges.find(item => item.source === target.source && target.target === item.target);
        };
        // biome-ignore lint/complexity/noForEach: <explanation>
        edges.forEach(edge => {
          const edgeModel = edge.getModel();

          const targetEdge = findEdges(updateEdges, edgeModel);
          if (targetEdge) {
            graph.updateItem(edge, { ...edge, ...targetEdge });
          } else {
            const currEdges =
              findEdges(showEdges, edgeModel) || findEdges(topoRawDataCache.value.complete.edges, edgeModel);
            if (currEdges && edgeModel && !isEqual(currEdges, edgeModel)) {
              graph.updateItem(edge, { ...edge, ...currEdges });
            }
          }
        });
        /** 子combo需要根据节点时候有展示来决定 */
        const combos = graph.getCombos().filter(combo => combo.getModel().parentId);
        // biome-ignore lint/complexity/noForEach: <explanation>
        combos.forEach(combo => {
          const { id, comboId, entity } = combo.getModel() as ITopoNode;
          const updateCombo = [...showSubCombos, ...content.sub_combos]
            .reverse()
            .find(item => item.id === entity.entity_id);
          const nodes = topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
          const showNodes = nodes.filter(({ id }) => {
            const node = graph.findById(id);
            return node?._cfg.visible;
          });
          updateCombo &&
            graph.updateItem(combo, {
              ...combo,
              id,
              comboId,
              is_feedback_root: updateCombo.is_feedback_root,
              entity: {
                ...updateCombo.entity,
              },
              alert_all_recorved: updateCombo.alert_all_recorved,
              is_on_alert: updateCombo.is_on_alert,
            });
          updateCombo && ServiceCombo.labelChange(combo);
          graph[showNodes.length > 0 ? 'showItem' : 'hideItem'](combo);
        });
      }
    };
    /** 收起查看资源 或者 节点/边概览 */
    const handleCollapseChange = (isResourceGraph = false) => {
      if (isResourceGraph) {
        showResourceGraph.value = false;
      } else {
        showServiceOverview.value = false;
      }
      resourceEdgeId.value = '';
    };

    const handleResetZoom = () => {
      zoomValue.value = 10;
      graph.zoomTo(1);
      graph.moveTo(0, 0);
      localStorage.setItem('failure-topo-zoom', String(zoomValue.value));
    };
    /** 画布缩放 */
    const handleZoomChange = value => {
      if (graph?.zoomTo) {
        graph.zoomTo(value / 10);
        localStorage.setItem('failure-topo-zoom', String(value));
        zoomValue.value = value;
      }
    };
    const handleUpdateZoom = val => {
      if (isPlay.value) {
        return;
      }
      const value = Math.max(MIN_ZOOM, zoomValue.value + Number(val));
      zoomValue.value = zoomValue.value + Number(val);
      handleZoomChange(value);
    };
    /** 图例展示 */
    const handleShowLegend = () => {
      showLegend.value = !showLegend.value;
      localStorage.setItem('showLegend', String(showLegend.value));
    };
    /** 根因变化 */
    const handleFeedBackChange = async () => {
      await getGraphData();
      renderGraph();
      feedbackCauseShow.value = false;

      // 刷新节点概览数据
      setTimeout(() => {
        handleViewServiceFromTop();
      }, 500);
    };
    const handleToDetail = node => {
      emit('toDetail', node);
    };
    /** 右侧资源图tips打开时，左侧tips关闭 */
    const handleHideToolTips = () => {
      tooltipsRef?.value?.hide?.();
      tooltips?.hide?.();
    };
    /** 根据左侧选中节点组计算出画布高亮节点信息 */
    const navSelectNode = computed(() => {
      const val = [...props.selectNode];
      const rootNode = [];
      if (!val.length) return rootNode;
      // biome-ignore lint/complexity/noForEach: <explanation>
      topoRawData?.nodes?.forEach?.(node => {
        if (val.includes(node.id)) {
          rootNode.push({
            id: node.id,
            entityId: node.entity.entity_id,
          });
        } else if (node.aggregated_nodes.length) {
          /** 检测是否是个被聚合节点，如果是则展示节点为父节点id，请求数据为本身id */
          // biome-ignore lint/complexity/noForEach: <explanation>
          node.aggregated_nodes.forEach(aggNode => {
            val.includes(aggNode.id) &&
              rootNode.push({
                id: node.id,
                entityId: aggNode.entity.entity_id,
              });
          });
        }
      });
      return rootNode;
    });
    /** 左侧菜单选中联动 */
    watch(
      () => props.selectNode,
      val => {
        if (val.length) {
          if (!graph) return;
          /** 清除之前节点状态 */
          // biome-ignore lint/complexity/noForEach: <explanation>
          graph.findAllByState('node', 'running').forEach?.(node => {
            graph.setItemState(node, 'running', false);
          });
          navSelectNode.value?.map?.((item, index) => {
            /** 多个节点只设置第一个节点为资源图节点 */
            if (index === 0) {
              if (item.entityId !== nodeEntityId.value) {
                showResourceGraph.value = false;
                showServiceOverview.value = false;
                resourceNodeId.value = item.id;
                nodeEntityId.value = item.entityId;
                nodeEntityName.value = item.entity_name;
              }
              moveToCenterIfNeeded(
                graph,
                resourceNodeId.value,
                graphRef.value.clientWidth,
                graphRef.value.clientHeight
              );
            }
            graph.setItemState(graph.findById(item.id), 'running', true);
          });
        }
      }
    );
    const handleToDetailSlider = node => {
      detailInfo.value = node;
      const data = cloneDeep(node);
      data.nodeId = node.id;
      data.id = node.alert_ids[0];
      window.__BK_WEWEB_DATA__?.showDetailSlider?.(data);
    };
    const handleRootToSpan = () => {
      const rootNode = topoRawData.nodes.find(node => node.entity.is_root);
      rootNode && goToTracePage(rootNode.entity, 'traceDetail');
    };
    const goToTracePage = (entity: IEntity, type) => {
      const { rca_trace_info, observe_time_rage } = entity;
      const query: Record<string, number | string> = {};
      const incidentQuery = {
        trace_id: rca_trace_info?.abnormal_traces[0].trace_id || '',
        span_id: rca_trace_info?.abnormal_traces[0].span_id || '',
        type,
      };
      if (observe_time_rage && Object.keys(observe_time_rage).length > 0) {
        query.start_time = observe_time_rage.start_at;
        query.end_time = observe_time_rage.end_at;
      }
      const { origin, pathname } = window.location;
      const baseUrl = bkzIds.value[0] ? `${origin}${pathname}?bizId=${bkzIds.value[0]}` : '';
      const newPage = router.resolve({
        path: '/trace/home',
        query: {
          app_name: rca_trace_info?.abnormal_traces_query.app_name,
          refreshInterval: '-1',
          filterMode: 'queryString',
          query: rca_trace_info.abnormal_traces_query.query,
          sceneMode: 'trace',
          incident_query: encodeURIComponent(JSON.stringify(incidentQuery)),
          ...query,
        },
      });
      window.open(baseUrl + newPage.href, '_blank');
    };
    const handleToDetailTab = node => {
      const { alert_display, alert_ids } = node;
      const name = alert_display?.alert_name || '';
      const len = alert_ids.length;
      const alertObj = {
        ids: `告警ID: ${alert_ids.join(' OR 告警ID: ')}`,
        label: `${name} 等共 ${len} 个告警`,
      };
      emit('toDetailTab', alertObj);
    };
    const refresh = () => {
      emit('refresh');
    };

    const getTopoWidth = computed(() => {
      let width = 0;
      if (showResourceGraph.value) width += 410;
      if (showServiceOverview.value) width += 360;
      return width ? `calc(100% - ${width}px)` : `calc(100% - ${1}px)`;
    });

    /** 点击节点概览中的关联边，画布中对应的边高亮 */
    const handleHighlightEdge = (edge: ITopoNode) => {
      // 对于聚合边，每个边上会携带当前最外层作为容器变的属性，聚合边需要高亮的是容器边
      const isAggregated = edge?.properties?.aggregated_by?.length > 0;
      const sourceId = isAggregated ? edge.properties.aggregated_by[0] : edge.source;
      const targetId = isAggregated ? edge.properties.aggregated_by[1] : edge.target;
      resourceEdgeId.value = `${sourceId}-${targetId}`;
      graph.setAutoPaint(false);
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getNodes().forEach(function (node) {
        graph.clearItemStates(node, ['dark', 'highlight']);
        graph.setItemState(node, 'highlight', true);
        node.toFront();
      });
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getEdges().forEach(curEdge => {
        graph.clearItemStates(curEdge, ['dark', 'highlight']);
        graph.setItemState(curEdge, 'dark', true);
        const sourceNode = curEdge.getSource();
        const targetNode = curEdge.getTarget();
        if (sourceNode.getID() === sourceId && targetNode.getID() === targetId) {
          graph.setItemState(curEdge, 'dark', false);
          graph.setItemState(curEdge, 'highlight', true);
          curEdge.toFront();
        }
      });
      graph.paint();
      graph.setAutoPaint(true);
    };

    const handleHideTooltips = () => {
      tooltipsRef.value.hide();
      tooltips.hide();
    };

    /** 右侧资源拓扑、节点/边概览侧滑同时打开时，关闭左侧侧滑 */
    watch(
      () => [showServiceOverview.value, showResourceGraph.value],
      ([showService, showResource]) => {
        if (showService && showResource) {
          emit('closeCollapse', true);
        }
        if (!showService) {
          resourceEdgeId.value = '';
        }
      }
    );

    /** 右侧资源拓扑、节点/边概览侧滑同时打开时，打开左侧侧滑，关闭节点/边概览侧滑 */
    watch(
      () => props.isCollapsed,
      val => {
        if (!val && showServiceOverview.value && showResourceGraph.value) {
          showServiceOverview.value = false;
        }
      }
    );

    return {
      isPlay,
      nodeEntityId,
      topoTools,
      showResourceGraph,
      showServiceOverview,
      timelinePosition,
      topoGraphRef,
      tooltipsEdge,
      edgeDetail,
      isClickEdgeItem,
      graphRef,
      loading,
      zoomValue,
      resourceGraphRef,
      tooltipsRef,
      wrapRef,
      showLegend,
      tooltipsModel,
      nodeDetail,
      feedbackCauseShow,
      feedbackModel,
      resourceNodeId,
      topoRawDataCache,
      tooltipsType,
      detailType,
      errorData,
      isNoData,
      nodeEntityName,
      detailInfo,
      getTopoWidth,
      curLinkedEdges,
      refreshTime,
      showViewResource,
      handleToDetail,
      handleHideToolTips,
      handleRootToSpan,
      handleFeedBackChange,
      handleFeedBack,
      handleShowLegend,
      handleViewResource,
      handleViewServiceFromResource,
      handleViewServiceFromTop,
      handleViewServiceFromTopo,
      handleUpdateZoom,
      handleZoomChange,
      handleResetZoom,
      handleUpdateAggregateConfig,
      handleChangeRefleshTime,
      handleTimelineChange,
      handlePlay,
      handleResetPlay,
      handleToDetailSlider,
      setHighlightEdge,
      handleToDetailTab,
      refresh,
      goToTracePage,
      t,
      handleCollapseChange,
      handleHighlightEdge,
      handleHideTooltips,
    };
  },
  render() {
    return (
      <div
        id='failure-topo'
        ref='wrapRef'
        class={['failure-topo', this.isPlay && 'failure-topo-play']}
      >
        <TopoTools
          ref='topoTools'
          v-model:showResource={this.showResourceGraph}
          v-model:showService={this.showServiceOverview}
          timelinePlayPosition={this.timelinePosition}
          topoRawDataList={this.topoRawDataCache.diff}
          onChangeRefleshTime={this.handleChangeRefleshTime}
          onPlay={this.handleResetPlay}
          onShowService={this.handleViewServiceFromTop}
          onTimelineChange={this.handleTimelineChange}
          onUpdate:AggregationConfig={this.handleUpdateAggregateConfig}
        />
        <Loading
          class='failure-topo-loading'
          color='#292A2B'
          loading={this.loading}
        >
          <div
            ref='topoGraphRef'
            class='topo-graph-wrapper'
          >
            <div
              style={{ width: this.getTopoWidth }}
              class='topo-graph-wrapper-padding'
            >
              {this.errorData.isError || this.isNoData ? (
                <ExceptionComp
                  errorMsg={this.errorData.msg}
                  imgHeight={100}
                  isDarkTheme={true}
                  isError={this.errorData.isError}
                  title={this.errorData.isError ? this.t('查询异常') : this.t('暂无数据')}
                />
              ) : (
                <>
                  <div
                    id='topo-graph'
                    ref='graphRef'
                    class='topo-graph'
                  />
                  <div class='failure-topo-graph-zoom'>
                    <Popover
                      extCls='failure-topo-graph-legend-popover'
                      v-slots={{
                        content: <LegendPopoverContent />,
                        default: (
                          <div
                            class={['failure-topo-graph-legend', this.showLegend && 'failure-topo-graph-legend-active']}
                            v-bk-tooltips={{
                              content: this.t('显示图例'),
                              disabled: this.showLegend,
                              boundary: this.wrapRef,
                            }}
                            onClick={this.handleShowLegend}
                          >
                            <i class='icon-monitor icon-legend' />
                          </div>
                        ),
                      }}
                      always={true}
                      arrow={false}
                      boundary='body'
                      disabled={!this.showLegend}
                      isShow={this.showLegend}
                      offset={{ crossAxis: 90, mainAxis: 10 }}
                      placement='top'
                      renderType='auto'
                      theme='dark common-table'
                      trigger='manual'
                      zIndex={100}
                    />
                    <span class='failure-topo-graph-line' />
                    <div class='failure-topo-graph-zoom-slider'>
                      <div
                        class={['failure-topo-graph-setting', { disabled: this.isPlay }]}
                        onClick={this.handleUpdateZoom.bind(this, -2)}
                      >
                        <i class='icon-monitor icon-minus-line' />
                      </div>
                      <Slider
                        class='slider'
                        v-model={this.zoomValue}
                        disable={this.isPlay}
                        maxValue={20}
                        minValue={2}
                        onChange={this.handleZoomChange}
                        onUpdate:modelValue={this.handleZoomChange}
                      />
                      <div
                        class={['failure-topo-graph-setting', { disabled: this.isPlay }]}
                        onClick={this.handleUpdateZoom.bind(this, 2)}
                      >
                        <i class='icon-monitor icon-plus-line' />
                      </div>
                    </div>
                    <span class='failure-topo-graph-line' />
                    <div
                      class={['failure-topo-graph-proportion', { disabled: this.isPlay }]}
                      v-bk-tooltips={{ content: this.t('重置比例'), boundary: this.wrapRef, zIndex: 999999 }}
                      onClick={this.handleResetZoom}
                    >
                      <i class='icon-monitor icon-mc-restoration-ratio' />
                    </div>
                  </div>
                </>
              )}
            </div>
            {this.showResourceGraph && !this.isPlay && (
              <ResourceGraph
                ref='resourceGraphRef'
                entityId={this.nodeEntityId}
                entityName={this.nodeEntityName}
                modelData={this.topoRawDataCache.complete}
                resourceNodeId={this.resourceNodeId}
                onCollapseResource={this.handleCollapseChange}
                onHideToolTips={this.handleHideToolTips}
                onViewService={this.handleViewServiceFromResource}
              />
            )}
            {this.showServiceOverview && !this.isPlay && (
              <FailureTopoDetail
                edge={this.edgeDetail}
                isClickEdgeItem={this.isClickEdgeItem}
                linkedEdges={this.curLinkedEdges}
                model={this.nodeDetail}
                refreshTime={this.refreshTime}
                showServiceOverview={this.showServiceOverview}
                showViewResource={this.showViewResource}
                type={this.detailType}
                onClearHighlightEdge={this.setHighlightEdge.bind(this)}
                onCollapseService={this.handleCollapseChange}
                onFeedBack={this.handleFeedBack}
                onHighlightEdge={this.handleHighlightEdge}
                onToDetail={this.handleToDetail}
                onToDetailSlider={this.handleToDetailSlider}
                onToDetailTab={this.handleToDetailTab}
                onToTracePage={this.goToTracePage}
              />
            )}
          </div>
        </Loading>
        <FeedbackCauseDialog
          data={this.feedbackModel}
          visible={this.feedbackCauseShow}
          onEditSuccess={this.handleFeedBackChange}
          onRefresh={this.refresh}
          onUpdate:isShow={(val: boolean) => {
            this.feedbackCauseShow = val;
          }}
        />
        <div style='display: none'>
          <FailureTopoTooltips
            ref='tooltipsRef'
            edge={this.tooltipsEdge}
            model={this.tooltipsModel}
            type={this.tooltipsType}
            onHide={this.handleHideTooltips}
            onViewResource={this.handleViewResource}
            onViewService={this.handleViewServiceFromTopo}
          />
        </div>
        <div
          id='combo-label-tooltip'
          class='combo-label-tooltip'
        />
        <div
          id='node-detail-tips'
          class='node-detail-tips'
        />
      </div>
    );
  },
});
