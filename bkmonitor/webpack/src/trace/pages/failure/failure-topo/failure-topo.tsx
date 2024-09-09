/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { useI18n } from 'vue-i18n';

import {
  Arrow,
  Graph,
  type ICombo,
  type INode,
  Tooltip,
  registerBehavior,
  registerCombo,
  registerEdge,
  registerNode,
} from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Loading, Message, Popover, Slider } from 'bkui-vue';
import { feedbackIncidentRoot, incidentTopology } from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils.js';
import { debounce } from 'throttle-debounce';

import ResourceGraph from '../resource-graph/resource-graph';
import { useIncidentInject } from '../utils';
import ElkjsUtils from './elkjs-utils';
import FailureTopoTooltips from './failure-topo-tooltips';
import FeedbackCauseDialog from './feedback-cause-dialog';
import formatTopoData from './format-topo-data';
import { NODE_TYPE_SVG } from './node-type-svg';
import TopoTools from './topo-tools';
import { getNodeAttrs, truncateText } from './utils';

import type { IEdge, IEntity, ITopoData, ITopoNode, IncidentDetailData } from './types';

import './failure-topo.scss';

const NODE_TYPE = [
  {
    text: '异常',
    status: 'error',
  },
  {
    text: '正常',
    status: 'normal',
  },
];

const TAG_TYPE = [
  {
    text: '未恢复告警',
    status: 'notRestored',
  },
  {
    text: '已恢复 / 已解决 / 已失效告警',
    status: 'restored',
  },
  {
    text: '根因',
    status: 'root',
  },
  {
    text: '反馈的根因',
    status: 'feedBackRoot',
  },
];
/** 增加画布离画布上下左右的留白区域可 */
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
  },
  emits: ['toDetail', 'playing', 'toDetailTab', 'changeSelectNode', 'refresh'],
  setup(props, { emit }) {
    /** 缓存resize render后执行的回调函数，主要用于点击播放之前收起右侧资源图时的回调 */
    const resizeCacheCallback = ref(null);
    const detailInfo = ref({});
    const cacheResize = ref<boolean>(false);
    const wrapRef = ref<HTMLDivElement>();
    const refreshTime = ref<number>(30 * 1000);
    const topoTools = ref(null);
    let refreshTimeout = null;
    const topoGraphRef = ref<HTMLDivElement>(null);
    const graphRef = ref<HTMLElement>(null);
    let graph: Graph;
    let tooltips = null;
    // 边的动画定时器
    const edgeInterval = [];
    let playTime = null;
    /** g6 默认缩放级别 数值 / 10 为真实结果值  */
    const MIN_ZOOM = 0.8;
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
    const tooltipsType = ref<string>('node');
    const tooltipsRef = ref<InstanceType<typeof FailureTopoTooltips>>();
    const resourceGraphRef = ref<InstanceType<typeof ResourceGraph>>();
    let topoRawData: ITopoData = null;
    const autoAggregate = ref<boolean>(true);
    const aggregateConfig = ref({});
    // const shouldUpdateNode = ref(null);
    const showLegend = ref<boolean>(localStorage.getItem('showLegend') === 'true');

    const feedbackCauseShow = ref<boolean>(false);
    const feedbackModel: Ref<{ entity: IEntity }> = ref(null);
    const incidentId = useIncidentInject();
    const nodeEntityId = ref<string>('');
    const loading = ref<boolean>(false);
    let activeAnimation = [];
    const resourceNodeId = ref<string>('');
    const zoomValue = ref<number>(10);
    const showResourceGraph = ref<boolean>(false);
    const savedMatrix = ref(null);
    /** 检测文字长度 */
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
          if (entity.is_root || is_feedback_root) {
            group.addShape('circle', {
              attrs: {
                lineDash: [3],
                lineWidth: 1, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 25, // 圆半径
                stroke: entity.is_root ? '#F55555' : '#FF9C01',
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
                fill: entity.is_root ? '#F55555' : '#FF9C01',
              },
              name: 'topo-node-rect',
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 20,
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
          const isRoot = entity.is_root || entity.is_feedback_root;
          const isAggregated = aggregated_nodes.length > 0;
          const nodeShapeWrap = group.addShape('rect', {
            zIndex: 10,
            attrs: {
              x: isRoot ? -25 : -20,
              y: isRoot ? -28 : -22,
              lineWidth: 1, // 描边宽度
              cursor: 'pointer', // 手势类型
              width: isRoot ? 50 : 40, // 根因有外边框整体宽度为50
              height: isRoot ? 82 : isAggregated ? 63 : 67, // 根因展示根因提示加节点类型加节点名称 聚合节点展示聚合提示加类型 普通节点展示名字与类型
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
            },
            draggable: true,
            name: 'topo-node-shape',
          });
          group.addShape('image', {
            zIndex: 12,
            attrs: {
              x: -12,
              y: -12,
              width: 24,
              height: 24,
              cursor: 'pointer', // 手势类型
              img: NODE_TYPE_SVG[entity.entity_type],
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

          if (aggregated_nodes?.length) {
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -17,
                y: 12,
                width: 32,
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
                  y: 20,
                  cursor: 'cursor',
                  textAlign: 'center',
                  textBaseline: 'middle',
                  text: anomaly_count,
                  fontSize: 11,
                  fill: '#F55555',
                  ...nodeAttrs.textAttrs,
                },
                name: 'topo-node-err-text',
              });
            (anomaly_count as number) > 0 &&
              group.addShape('text', {
                zIndex: 11,
                attrs: {
                  x: -2,
                  y: 20,
                  cursor: 'default',
                  textAlign: 'center',
                  textBaseline: 'middle',
                  text: '/',
                  fontSize: 11,
                  fill: '#979BA5',
                  ...nodeAttrs.textAttrs,
                },
                name: 'topo-node-err-text',
              });

            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0 + ((anomaly_count as number) > 0 ? 5 : 0),
                y: 20,
                textAlign: 'center',
                cursor: 'cursor',
                textBaseline: 'middle',
                text:
                  entity.is_root || is_feedback_root
                    ? truncateText(t('根因'), 28, 11, 'PingFangSC-Medium')
                    : aggregated_nodes.length + 1,
                fontSize: 11,
                fill: '#fff',
                ...nodeAttrs.textAttrs,
              },
              name: 'topo-node-text',
            });
          }
          group.addShape('text', {
            zIndex: 11,
            attrs: {
              x: 0,
              y: aggregated_nodes?.length || entity.is_root || is_feedback_root ? 36 : 28,
              textAlign: 'center',
              textBaseline: 'middle',
              cursor: 'cursor',
              text: accumulatedWidth(entity.entity_type),
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
                y: entity.is_root || is_feedback_root ? 48 : 40,
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
      registerCombo('service-combo', {
        drawShape(cfg, group) {
          const { style } = cfg;
          const rect = group.addShape('rect', {
            fixSize: [400, 300],
            attrs: {
              fixSize: [400, 300],
              ...style,
              radius: 6, // 圆角矩形
            },
            name: 'combo-rect',
          });
          /** 一期数据暂时不需要展示，二期需要打开所以代码不能直接删除 */
          // group.addShape('circle', {
          //   zIndex: 10,
          //   attrs: {
          //     x: 14,
          //     y: 14,
          //     lineWidth: 1, // 描边宽度
          //     cursor: 'pointer', // 手势类型
          //     r: 8, // 圆半径
          //     fill: 'rgba(255, 102, 102, 0.4)',
          //     stroke: '#F55555',
          //     opacity: 0,
          //     // ...nodeAttrs.groupAttrs,
          //   },
          //   draggable: true,
          //   name: 'service-image-shape',
          // });
          // group.addShape('image', {
          //   zIndex: 12,
          //   attrs: {
          //     x: 8,
          //     y: 8,
          //     width: 12,
          //     height: 12,
          //     cursor: 'pointer', // 手势类型
          //     img: NODE_TYPE_SVG.BcsPod,
          //     opacity: 0,
          //   },
          //   draggable: true,
          //   name: 'service-image',
          // });

          group.addShape('text', {
            zIndex: 12,
            attrs: {
              opacity: 0,
              x: 0,
              y: 14,
              cursor: 'default',
              textAlign: 'center',
              textBaseline: 'middle',
              text: cfg.label,
              fontSize: 14,
              fill: '#979BA5',
            },
            draggable: true,
            name: 'service-label',
          });
          return rect;
        },
        setState(name, value, item) {
          if (name === 'hover') {
            const group = item.getContainer();
            const label = group.find(e => e.get('name') === 'service-label');
            label.attr({
              opacity: value ? 1 : 0,
            });
          }
        },
      });
    };
    /** 画布自定义边 */
    const registerCustomEdge = () => {
      registerEdge(
        'topo-edge',
        {
          afterDraw(cfg, group) {
            const shape = group.get('children')[0];
            const { is_anomaly, anomaly_score, events } = cfg;
            const lineDash = anomaly_score === 0 ? [6] : [10];
            if (is_anomaly) {
              const { direction } = events[0];
              let index = 0;
              // 这里改为定时器执行，自带的动画流动速度控制不了
              edgeInterval.push(
                setInterval(() => {
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
                }, 30)
              );
            }

            if (!cfg.aggregated || !cfg.count) return;
            // 获取路径图形的中点坐标
            const midPoint = shape.getPoint(0.5);
            // 在中点增加一个矩形，注意矩形的原点在其左上角
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                cursor: 'pointer',
                width: 10,
                height: 10,
                fill: 'rgba(58, 59, 61, 1)',
                // x 和 y 分别减去 width / 2 与 height / 2，使矩形中心在 midPoint 上
                x: midPoint.x - 5,
                y: midPoint.y - 5,
                radius: 5,
              },
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                cursor: 'pointer',
                x: midPoint.x,
                y: midPoint.y,
                textAlign: 'center',
                textBaseline: 'middle',
                text: cfg.count,
                fontSize: 12,
                fill: '#fff',
              },
              name: 'topo-node-text',
            });
          },
          setState(name, value, item) {
            const { is_anomaly } = item.getModel();
            const highlightColor = is_anomaly ? '#F55555' : '#699DF4';
            const darkColor = is_anomaly ? '#F55555' : '#63656D';
            if (name === 'show-animate') {
              const group = item.getContainer();
              const shape = group.get('children')[0];
              const length = shape.getTotalLength();
              const stroke = shape.attr('stroke');
              shape.attr('stroke', highlightColor);
              shape.attr('opacity', 0);
              item.show();
              shape.animate(
                ratio => {
                  const startLen = ratio * length;
                  const cfg = {
                    opacity: 1,
                    quadraticDash: [startLen, length - startLen],
                  };
                  return cfg;
                },
                {
                  duration: 1000,
                  easing: 'easeLinear',
                  callback: () => {
                    shape.attr('stroke', stroke);
                  },
                }
              );
            } else if (name === 'highlight') {
              const group = item.getContainer();
              const shape = group.get('children')[0];
              shape.attr('stroke', value ? highlightColor : darkColor);
              group.attr({
                opacity: value ? 1 : 0.4,
              });
              shape?.cfg?.endArrowShape?.attr({
                opacity: value ? 1 : 0.2,
                stroke: value ? highlightColor : darkColor,
                fill: value ? highlightColor : darkColor,
              });
            } else if (name === 'dark') {
              const group = item.getContainer();
              const shape = group.get('children')[0];
              setTimeout(() => {
                group.attr({
                  opacity: 1,
                });
                shape?.cfg?.endArrowShape?.attr({
                  opacity: 1,
                  fill: darkColor,
                  stroke: darkColor,
                });
              });
            }
          },
          update: undefined,
        },
        'quadratic'
      );
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
              graph.getNodes().forEach(node => {
                if (node.getModel().subComboId === item.getID()) {
                  (this.currentNodes as INode[]).push(node);
                }
              });
            }
            this.origin = { x: e.x, y: e.y };
          }
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
              // 获取节点内名为'topo-node-type-text'的Shape
              const nameTextShape = item.get('group').find(s => s.get('name') === 'topo-node-name-text');
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
          combos.forEach(combo => {
            const { width } = combo.getBBox();
            if (width > xComboWidth) {
              xCombo = combo;
              xComboWidth = width;
            }
          });
          this.comboRect = {
            ...((this as any).comboRect || {}),
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
              topCombo: ICombo;
              bottomCombo: ICombo;
              xCombo: ICombo;
              width: number;
              height: number;
            };
            let { movementX, movementY } = e.originalEvent;
            // 大于零向上拖动
            if (movementY < 0) {
              const { bottomRight } = getCanvasByPoint(comboRect.bottomCombo);
              bottomRight.y + GRAPH_DRAG_MARGIN < comboRect.height && (movementY = 0);
            } else {
              const { topLeft } = getCanvasByPoint(comboRect.topCombo);
              topLeft.y - GRAPH_DRAG_MARGIN > 0 && (movementY = 0);
            }
            const { topLeft, bottomRight } = getCanvasByPoint(comboRect.xCombo);
            /** 大于0向左拖动 */
            if (movementX < 0) {
              bottomRight.x + GRAPH_DRAG_MARGIN < comboRect.width && (movementX = 0);
            } else {
              topLeft.x - GRAPH_DRAG_MARGIN > 0 && (movementX = 0);
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
              bottomRight.y + GRAPH_DRAG_MARGIN < height && (dy = 0);
            } else {
              const topCombo = combos[0];
              const { topLeft } = getCanvasByPoint(topCombo);
              topLeft.y - GRAPH_DRAG_MARGIN > 0 && (dy = 0);
            }
            dx = 0;
          } else {
            const topCombo = combos[0];
            const { topLeft, bottomRight } = getCanvasByPoint(topCombo);
            /** 大于0判断右侧 否则判断左侧 */
            if (deltaX > 0) {
              bottomRight.x + GRAPH_DRAG_MARGIN < width && (dx = 0);
            } else {
              topLeft.x - GRAPH_DRAG_MARGIN > 0 && (dx = 0);
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
      const { height } = document.querySelector('.failure-topo').getBoundingClientRect();
      const { width } = graphRef.value.getBoundingClientRect();
      tooltipsRef?.value?.hide?.();
      tooltips?.hide?.();
      graph.changeSize(width, height - 40);
      /** 将红线置顶 */
      setTimeout(toFrontAnomalyEdge, 500);
      const combos = graph.getCombos().map(combo => combo.getModel());
      ElkjsUtils.setRootComboStyle(combos, graph.getWidth());
      graph.refresh();
      graph.render();
      const zoom = localStorage.getItem('failure-topo-zoom');
      if (zoom) {
        handleZoomChange(zoom);
        zoomValue.value = Number(zoom);
      }
      // graph.fitCenter();
      timelinePosition.value = topoRawDataCache.value.diff.length - 1;
      /** 打开时会触发导致动画消失 */
      if (resourceNodeId.value) {
        const isNavSelectNode = navSelectNode.value.some(node => node.id === resourceNodeId.value);
        if (isNavSelectNode) {
          navSelectNode.value.forEach(node => {
            graph.setItemState(graph.findById(node.id), 'running', true);
          });
          return;
        }
        const node = graph.findById(resourceNodeId.value);
        node && graph.setItemState(node, 'running', true);
      }

      /** 恢复视图状态 */
      if (savedMatrix.value) {
        graph.getGroup().setMatrix(savedMatrix.value);
      }
    }

    const onResize = debounce(300, handleResize);

    /**
     * 清洗ComboID避免重复ID导致绘制错误
     * API返回数据ComboID和nodeID会重复
     */
    const formatResponseData = data => {
      const { combos = [], nodes = [], sub_combos = [] } = data || {};
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
          fill: '#3A3B3D',
          radius: 6,
          stroke: '#3A3B3D',
          opacity: 0.8,
        },
        labelCfg: {
          style: {
            fill: '#979BA5',
            fontSize: 12,
          },
        },
      });
    };

    /** 获取数据 */
    const getGraphData = async (isAutoRefresh = false) => {
      loading.value = !isAutoRefresh;
      clearTimeout(refreshTimeout);
      const renderData = await incidentTopology({
        id: incidentId.value,
        auto_aggregate: autoAggregate.value,
        aggregate_config: aggregateConfig.value,
        only_diff: true,
        start_time: isAutoRefresh
          ? topoRawDataCache.value.diff[topoRawDataCache.value.diff.length - 1].create_time + 1
          : incidentId.value.substr(0, 10),
      })
        .then(res => {
          let { latest, diff, complete } = res;
          diff = diff.filter(item => item.content.nodes.length > 0 || item.content.edges.length > 0);
          complete.combos = latest.combos;
          complete.sub_combos = latest.sub_combos;
          formatResponseData(complete);
          const { combos = [], edges = [], nodes = [], sub_combos = [] } = complete || {};
          ElkjsUtils.setSubCombosMap(ElkjsUtils.getSubComboCountMap(nodes));
          const resolvedCombos = [...combos, ...ElkjsUtils.resolveSumbCombos(sub_combos)];
          const processedNodes = [];
          diff.forEach(item => {
            item.showNodes = [...processedNodes];
            processedNodes.push(...item.content.nodes);
          });
          topoRawDataCache.value.diff = diff;
          topoRawDataCache.value.latest = latest;
          topoRawDataCache.value.complete = { ...complete, combos: resolvedCombos };

          const diffLen = topoRawDataCache.value.diff.length;
          timelinePosition.value = diffLen - 1;
          return ElkjsUtils.getTopoRawData(resolvedCombos, edges, nodes);
        })
        .finally(() => {
          loading.value = false;
          if (refreshTime.value !== -1) {
            refreshTimeout = setTimeout(() => {
              getGraphData(true);
            }, refreshTime.value);
          }
        });
      if (isAutoRefresh) return;
      topoRawData = renderData;
      const rootNode = topoRawData.nodes.find(node => node.entity.is_root);
      if (!resourceNodeId.value && rootNode) {
        resourceNodeId.value = rootNode.id;
        nodeEntityId.value = rootNode.entity.entity_id;
      }
    };

    /** 布局计算 */
    const resolveLayout = (data): Promise<any> => {
      const copyData = JSON.parse(JSON.stringify(data));
      const { layoutNodes, edges, nodes } = formatTopoData(copyData);
      const resolvedData = ElkjsUtils.getKlayGraphData({ nodes: layoutNodes, edges, source: nodes });

      return ElkjsUtils.getLayoutData(resolvedData).then(layouted => {
        ElkjsUtils.updatePositionFromLayouted(layouted, copyData);
        ElkjsUtils.OptimizeLayout(layouted, copyData, edges);
        ElkjsUtils.setRootComboStyle(copyData.combos, graph.getWidth());

        return { layouted, data: copyData };
      });
    };
    /** 确认某个节点是否在画布之外 */
    const isNodeOutOfCanvas = node => {
      const canvasWidth = graph.get('width');
      const canvasHeight = graph.get('height');
      const matrix = graph.get('group').getMatrix();
      const { x, y, width } = node.getModel();

      /** 拖动画布偏移节点位置是不变的，需要考虑画布的偏移和缩放 */
      const transformedX = x * matrix[0] + matrix[6];
      const transformedY = y * matrix[4] + matrix[7];

      /** 计算节点边界 */
      const fraction = width / 3;
      /** 检查节点的位置是否超出画布边界 */
      if (
        transformedX - fraction < 0 ||
        transformedX + fraction > canvasWidth ||
        transformedY < 0 ||
        transformedY > canvasHeight
      ) {
        return true;
      }
      return false;
    };

    /** 移动根因节点到画布中心 */
    const moveRootNodeCenter = (isRecordMatrix = false) => {
      if (isRecordMatrix) {
        /** 记录当前画布的移动坐标 */
        const matrix = graph.getGroup().getMatrix();
        if (matrix) {
          /** 保存当前的变换矩阵 */
          savedMatrix.value = matrix.slice();
        }
      } else {
        const rootNode = topoRawData.nodes.find(node => node.entity.is_root);
        const node = graph.findById(resourceNodeId.value || rootNode.id);
        if (!isNodeOutOfCanvas(node)) {
          return;
        }
        // x轴居中，y轴在视图范围内即可
        const { x, y, height } = node.getModel();
        const graphWidth = graph.get('width');
        const graphHeight = graph.get('height');
        const centerX = graphWidth / 2;
        const dx = centerX - x;
        const h = (height as number) / 2;
        // 计算 y 轴上的偏移量，使节点在画布范围内
        let dy = 0;
        if (y < h) {
          dy = h - y; // 节点超过上边界
        } else if (y > graphHeight - h) {
          dy = graphHeight - h - y; // 节点超过下边界
        }

        graph.translate(dx, dy);
      }
    };
    /** 错误的线置于顶层 */
    const toFrontAnomalyEdge = () => {
      const edges = graph.getEdges();
      edges.forEach(edge => {
        const edgeModel = edge.getModel();
        if (edgeModel.is_anomaly) {
          edge.toFront();
        }
      });
    };
    /** 渲染数据 */
    const renderGraph = (data = topoRawDataCache.value.complete, renderComplete = false) => {
      edgeInterval.forEach(interval => {
        clearInterval(interval);
      });

      resolveLayout(data).then(resp => {
        graph.data(resp.data);
        graph.render();
        if (resourceNodeId.value) {
          const node = graph.findById(resourceNodeId.value);
          node && graph.setItemState(node, 'running', true);
        }
        isRenderComplete.value = renderComplete;
        // 默认渲染最后帧
        // handleTimelineChange(topoRawDataCache.value.diff.length - 1);
        /** 获取用户拖动设置后的zoom缩放级别 */
        const zoom = localStorage.getItem('failure-topo-zoom');
        if (zoom) {
          handleZoomChange(zoom);
          zoomValue.value = Number(zoom);
        }
        moveRootNodeCenter();
        /** 布局渲染完将红线置顶 */
        setTimeout(toFrontAnomalyEdge, 500);
      });
    };
    /** 初始化图表相关 */
    onMounted(async () => {
      await getGraphData();

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
          type: 'quadratic',
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
        const { is_anomaly, edge_type, anomaly_score } = cfg;
        const isInvoke = edge_type === 'ebpf_call';
        const color = is_anomaly ? '#F55555' : '#63656E';
        const edg = {
          ...cfg,
          shape: 'quadratic',
          style: {
            cursor: 'pointer',
            lineAppendWidth: 15,
            endArrow: isInvoke
              ? {
                  path: Arrow.triangle(12, 12, 0),
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
        return {
          ...edg,
          shape: 'quadratic',
          type: 'topo-edge',
        };
      });
      graph.combo((cfg: any) => {
        return {
          ...cfg,
          ...(cfg.parentId
            ? {
                style: {
                  stroke: '#626366',
                  lineWidth: 1,
                  lineDash: [2, 3],
                },
                labelCfg: {
                  style: {
                    opacity: 0,
                  },
                },
              }
            : {}),
        };
      });
      renderGraph();
      /** 点击tips时，关闭右侧资源打开的tips */
      graph.on('tooltipchange', ({ action }) => {
        if (action === 'show' && showResourceGraph.value) {
          resourceGraphRef.value.hideToolTips();
        }
      });
      /** 点击非节点清楚高亮状态 */
      graph.on('click', e => {
        if (!e.item || e.item.getType() !== 'node') {
          clearAllStats();
        }
        setTimeout(toFrontAnomalyEdge, 500);
      });
      /** serverCombo 移动展示name */
      graph.on('combo:mouseenter', e => {
        const { item } = e;
        if (!item.getModel().parentId) return;
        graph.setItemState(item, 'hover', true);
        const label = item.getContainer().find(element => element.get('type') === 'text');
        if (label) {
          label.attr('opacity', 1); // 悬停时显示标签
        }
      });
      /** serverCombo 移出隐藏name */
      graph.on('combo:mouseleave', e => {
        const { item } = e;
        if (!item.getModel().parentId) return;
        graph.setItemState(item, 'hover', false);
        const label = item.getContainer().find(element => element.get('type') === 'text');
        if (label) {
          label.attr('opacity', 0); // 悬停时显示标签
        }
      });

      graph.on('node:mouseenter', e => {
        const { item } = e;
        graph.setItemState(item, 'hover', true);
        /** 移动到service Combo中的节点 需要给父级也加上hover态度 */
        const model = item.getModel() as ITopoNode;
        if (model.subComboId) {
          const combo = graph.findById(model.subComboId);
          if (!combo) return;
          const label = combo.getContainer().find(element => element.get('type') === 'text');
          if (label) {
            label.attr('opacity', 1); // 悬停时显示标签
          }
          combo && graph.setItemState(combo, 'hover', true);
        }
        return;
      });
      /** 监听手势缩放联动缩放轴数据 */
      graph.on('viewportchange', ({ action }) => {
        if (action === 'zoom') {
          zoomValue.value = graph.getZoom() * 10;
        }
      });
      // 监听鼠标离开节点
      graph.on('node:mouseleave', e => {
        const nodeItem = e.item;
        /** 移出隐藏名称 */
        const model = nodeItem.getModel() as ITopoNode;
        if (model.subComboId) {
          const combo = graph.findById(model.subComboId);
          if (!combo) return;
          const label = combo.getContainer().find(element => element.get('type') === 'text');
          if (label) {
            label.attr('opacity', 0);
          }
        }
        graph.setItemState(nodeItem, 'hover', false);
      });
      /** resize之后的render 调用一次缓存的函数 通知可以播放 */
      graph.on('afterrender', () => {
        resizeCacheCallback.value?.();
      });
      /** 设置节点高亮状态 */
      graph.on('node:click', ({ item }) => {
        // const nodeItem = e.item;
        graph.setAutoPaint(false);
        graph.getNodes().forEach(function (node) {
          graph.clearItemStates(node, ['dark', 'highlight']);
          graph.setItemState(node, 'dark', true);
          node.toFront();
        });
        /** 根据边的关系设置节点状态 */
        graph.getEdges().forEach(function (edge) {
          if (edge.getSource() === item) {
            graph.setItemState(edge.getTarget(), 'dark', false);
            graph.setItemState(edge.getTarget(), 'highlight', true);
            graph.setItemState(edge, 'highlight', true);
            edge.toFront();
          } else if (edge.getTarget() === item) {
            graph.setItemState(edge.getSource(), 'dark', false);
            graph.setItemState(edge.getSource(), 'highlight', true);
            graph.setItemState(edge, 'highlight', true);
            edge.toFront();
          } else {
            graph.setItemState(edge, 'highlight', false);
          }
        });

        graph.setItemState(item, 'dark', false);
        graph.setItemState(item, 'highlight', true);
        graph.paint();
        graph.setAutoPaint(true);
      });
      /** 清除高亮状态 */
      function clearAllStats() {
        graph.setAutoPaint(false);
        graph.getEdges().forEach(function (edge) {
          graph.clearItemStates(edge, ['dark', 'highlight']);
          edge.toFront();
        });
        graph.getNodes().forEach(function (node) {
          graph.clearItemStates(node, ['dark', 'highlight']);
          node.toFront();
        });
        graph.paint();
        graph.setAutoPaint(true);
      }

      graph.on('combo:click', () => {
        tooltipsRef.value.hide();
        tooltips.hide();
      });
      /** 触发下一帧播放 */
      graph.on('afteritemstatechange', ({ state }) => {
        if (state && !(state as string).includes('show-animate')) return;
        clearTimeout(playTime);
        playTime = setTimeout(() => {
          timelinePosition.value = timelinePosition.value + 1;
          handlePlay({ value: isPlay.value });
        }, 1000);
      });
      nextTick(() => {
        addListener(graphRef.value as HTMLElement, onResize);
      });
    });
    onUnmounted(() => {
      edgeInterval.forEach(interval => {
        clearInterval(interval);
      });
      clearTimeout(playTime);
      clearTimeout(refreshTimeout);
      graphRef.value && removeListener(graphRef.value as HTMLElement, onResize);
    });
    /** 打开资源拓朴 */
    const handleViewResource = ({ sourceNode, node }) => {
      if (!showResourceGraph.value) {
        showResourceGraph.value = !showResourceGraph.value;
      } else {
        const node = graph.findById(sourceNode.id);
        graph.setItemState(node, 'running', true);
      }
      if (resourceNodeId.value && resourceNodeId.value !== sourceNode.id) {
        const node = graph.findById(resourceNodeId.value);
        graph.setItemState(node, 'running', false);
      }
      resourceNodeId.value = sourceNode.id;
      nodeEntityId.value = node?.entity?.entity_id || node?.model?.entity?.entity_id;
      moveRootNodeCenter(true);
      tooltipsRef.value.hide();
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
      });
    };
    /** 反馈新根因， 反馈后需要重新调用接口拉取数据 */
    const handleFeedBack = model => {
      tooltipsRef.value.hide();
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
    const handleRenderTimeline = (hideNodes = []) => {
      const hideNodeArr = timelinePosition.value === 0 ? topoRawDataCache.value.complete.nodes : hideNodes;
      /** 播放时关闭查看资源态 */
      showResourceGraph.value = false;
      /** 播放时清楚自动刷新 */
      clearTimeout(refreshTimeout);
      hideNodeArr.forEach(({ id }) => {
        const node = graph.findById(id);
        node && graph.hideItem(node);
      });
      /** 对比node是否已经展示，已经展示还存在diff中说明只是状态变更以及对比每个展示的node都需要判断边关系的node是在展示状态 */
      const { showNodes } = topoRawDataCache.value.diff[timelinePosition.value];
      const currNodes = topoRawDataCache.value.diff[timelinePosition.value].content.nodes;
      const currEdges = topoRawDataCache.value.diff[timelinePosition.value].content.edges;
      const randomStr = random(8);
      let next = false;
      const edges = graph.getEdges();
      edges.forEach(edge => {
        const edgeModel = edge.getModel();
        const targetEdge = currEdges.find(item => item.source === edgeModel.source && edgeModel.target === item.target);

        if (targetEdge) {
          graph.updateItem(edge, { ...edge, ...targetEdge });
        }
      });
      currNodes.forEach(item => {
        const node = graph.findById(item.id);
        const model = node?.getModel?.();
        const isShow = showNodes.find(node => node.id === item.id);
        if (!isShow) {
          if (node) {
            next = true;
            /** diff中的节点 comboId没有经过布局处理，延用node之前已设置过的id即可 */
            graph.updateItem(node, {
              ...node,
              ...item,
              comboId: model.comboId,
              subComboId: model.subComboId,
            });
            graph.setItemState(node, 'show-animate', randomStr);
            const edges = (node as any).getEdges();
            edges.forEach(edge => {
              const edgeModel = edge.getModel();
              const edgeNode = [...showNodes, ...currNodes].find(node => {
                return edgeModel.source === item.id ? node.id === edgeModel.target : node.id === edgeModel.source;
              });
              edgeNode && graph.setItemState(edge, 'show-animate', randomStr);
              // graph.setItemState(edge, 'show-animate', randomStr);
            });
          }
        } else {
          /** diff中的节点  comboId没有经过布局处理，延用node之前已设置过的id即可 */
          graph.updateItem(node, { ...item, comboId: model.comboId, subComboId: model.subComboId });
        }
      });
      const combos = graph.getCombos().filter(combo => combo.getModel().parentId);
      combos.forEach(combo => {
        const { id } = combo.getModel();
        const nodes = topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
        const showNodes = nodes.filter(({ id }) => {
          const node = graph.findById(id);
          return node?._cfg.visible;
        });
        graph[showNodes.length > 1 ? 'showItem' : 'hideItem'](combo);
      });

      return currNodes.length === 0 || !next;
    };
    /** 判断资源图是否开启状态 是的话关闭状态并等待重新布局 */
    const handleResetPlay = playOption => {
      if (showResourceGraph.value) {
        showResourceGraph.value = false;
        resizeCacheCallback.value = () => {
          setTimeout(() => handlePlay(playOption), 300);
          resizeCacheCallback.value = null;
        };
        return;
      }
      handlePlay(playOption);
    };
    /** 播放 */
    const handlePlay = playOption => {
      const { value, isStart = true } = playOption;
      if ('timeline' in playOption) {
        timelinePosition.value = 0;
      }
      isPlay.value = value;
      if (value) {
        const len = topoRawDataCache.value.diff.length;
        if (timelinePosition.value === len || timelinePosition.value + 1 === len) {
          timelinePosition.value = topoRawDataCache.value.diff.length - 1;
          isPlay.value = false;
          emit('playing', false);
          handleChangeRefleshTime(refreshTime.value);
          return;
        }
        emit('playing', true, timelinePosition.value);
        let hideNodes = [];
        if (!isStart) {
          /** 直接切换到对应帧时，直接隐藏掉未出现的帧，并更新当前帧每个node的节点数据 */
          const { showNodes, content } = topoRawDataCache.value.diff[timelinePosition.value];
          hideNodes = topoRawDataCache.value.complete.nodes.filter(node => {
            const showNode = [...showNodes, ...content.nodes].find(item => item.id === node.id);
            return !showNode;
          });
        }
        const next = isStart ? handleRenderTimeline() : handleRenderTimeline(hideNodes);
        if (next) {
          timelinePosition.value = timelinePosition.value + 1;
          handlePlay({ value: true });
        }
      }
    };
    /** 点击展示某一帧的图 */
    const handleTimelineChange = (value, init = false) => {
      if (!init && (value === timelinePosition.value || isPlay.value)) return;
      timelinePosition.value = value;
      if (!isPlay.value && topoRawDataCache.value.diff[value]) {
        /** 切换帧时 */
        showResourceGraph.value = false;
        /** 直接切换到对应帧时，直接隐藏掉未出现的帧，并更新当前帧每个node的节点数据 */
        const { showNodes, content } = topoRawDataCache.value.diff[value];
        topoRawDataCache.value.complete.nodes.forEach(({ id }) => {
          const showNode = [...showNodes, ...content.nodes].find(item => item.id === id);
          const diffNode = content.nodes.find(item => item.id === id);
          if (!showNode && !diffNode) {
            const node = graph.findById(id);
            node && graph.hideItem(node);
          } else if (diffNode) {
            const node = graph.findById(diffNode.id);
            const model = node?.getModel?.();
            node && graph.showItem(node);
            node && graph.updateItem(node, { ...diffNode, comboId: model.comboId, subComboId: model.subComboId });
          }
        });
        const edges = graph.getEdges();
        edges.forEach(edge => {
          const edgeModel = edge.getModel();
          const targetEdge = content.edges.find(
            item => item.source === edgeModel.source && edgeModel.target === item.target
          );
          if (targetEdge) {
            graph.updateItem(edge, { ...edge, ...targetEdge });
          }
        });
        /** 子combo需要根据节点时候有展示来决定 */
        const combos = graph.getCombos().filter(combo => combo.getModel().parentId);
        combos.forEach(combo => {
          const { id } = combo.getModel();
          const nodes = topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
          const showNodes = nodes.filter(({ id }) => {
            const node = graph.findById(id);
            return node?._cfg.visible;
          });
          graph[showNodes.length > 1 ? 'showItem' : 'hideItem'](combo);
        });
      }
    };
    /** 查看资源展开收起 */
    const handleExpandResourceChange = () => {
      showResourceGraph.value = !showResourceGraph.value;
      moveRootNodeCenter(true);
    };
    const handleResetZoom = () => {
      zoomValue.value = 10;
      graph.zoomTo(1);
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
      topoRawData?.nodes?.forEach?.(node => {
        if (val.includes(node.id)) {
          rootNode.push({
            id: node.id,
            entityId: node.entity.entity_id,
          });
        } else if (node.aggregated_nodes.length) {
          /** 检测是否是个被聚合节点，如果是则展示节点为父节点id，请求数据为本身id */
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
          /** 清除之前节点状态 */
          graph.findAllByState('node', 'running').forEach?.(node => {
            graph.setItemState(node, 'running', false);
          });
          navSelectNode.value?.map?.((item, index) => {
            /** 多个节点只设置第一个节点会资源图节点 */
            if (index === 0) {
              if (item.entityId !== nodeEntityId.value) {
                showResourceGraph.value = false;
                resourceNodeId.value = item.id;
                nodeEntityId.value = item.entityId;
              }
              moveRootNodeCenter();
            }
            graph.setItemState(graph.findById(item.id), 'running', true);
          });
        }
      }
    );
    const handleToDetailSlider = node => {
      detailInfo.value = node;
      const data = JSON.parse(JSON.stringify({ ...node }));
      data.nodeId = node.id;
      data.id = node.alert_ids[0];
      window.__BK_WEWEB_DATA__?.showDetailSlider?.(data);
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
    return {
      isPlay,
      nodeEntityId,
      topoTools,
      showResourceGraph,
      timelinePosition,
      topoGraphRef,
      tooltipsEdge,
      graphRef,
      loading,
      zoomValue,
      resourceGraphRef,
      tooltipsRef,
      wrapRef,
      showLegend,
      tooltipsModel,
      feedbackCauseShow,
      feedbackModel,
      resourceNodeId,
      topoRawDataCache,
      tooltipsType,
      handleToDetail,
      handleHideToolTips,
      handleFeedBackChange,
      handleFeedBack,
      handleShowLegend,
      handleViewResource,
      handleUpdateZoom,
      handleZoomChange,
      handleResetZoom,
      handleUpdateAggregateConfig,
      handleChangeRefleshTime,
      handleTimelineChange,
      handlePlay,
      handleResetPlay,
      handleExpandResourceChange,
      handleToDetailSlider,
      handleToDetailTab,
      detailInfo,
      refresh,
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
          timelinePlayPosition={this.timelinePosition}
          topoRawDataList={this.topoRawDataCache.diff}
          onChangeRefleshTime={this.handleChangeRefleshTime}
          onPlay={this.handleResetPlay}
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
              style={{ width: this.showResourceGraph ? '70%' : '100%' }}
              class='topo-graph-wrapper-padding'
            >
              <div
                id='topo-graph'
                ref='graphRef'
                class='topo-graph'
              />
              <div class='failure-topo-graph-zoom'>
                <Popover
                  extCls='failure-topo-graph-legend-popover'
                  v-slots={{
                    content: (
                      <div class='failure-topo-graph-legend-content'>
                        <ul class='node-type'>
                          <li class='node-type-title'>{this.$t('节点图例')}</li>
                          {NODE_TYPE.map(node => {
                            return (
                              <li key={node.status}>
                                <span class='circle-wrap'>
                                  <span class={['circle', node.status]}>
                                    {'error' === node.status && <i class='icon-monitor icon-mc-pod' />}
                                    {['feedBackRoot', 'root'].includes(node.status) && this.$t('根因')}
                                  </span>
                                </span>
                                <span>{this.$t(node.text)}</span>
                              </li>
                            );
                          })}
                        </ul>
                        <ul class='node-type node-line-type'>
                          <li class='node-type-title'>{this.$t('标签图例')}</li>
                          {TAG_TYPE.map(node => {
                            return (
                              <li key={node.status}>
                                <span class='circle-wrap'>
                                  <span class={['circle', node.status]}>
                                    {['notRestored', 'restored'].includes(node.status) && (
                                      <i class='icon-monitor icon-menu-event' />
                                    )}
                                    {['feedBackRoot', 'root'].includes(node.status) && this.$t('根因')}
                                  </span>
                                </span>
                                <span>{this.$t(node.text)}</span>
                              </li>
                            );
                          })}
                        </ul>
                        <ul class='node-line-type'>
                          <li class='node-line-title'>{this.$t('边图例')}</li>
                          <li>
                            <span class='line' />
                            <span>{this.$t('从属关系')}</span>
                          </li>
                          <li>
                            <span class='line arrow' />
                            <span>{this.$t('调用关系')}</span>
                          </li>
                          <li>
                            <span class='line dash' />
                            <span>{this.$t('故障传播')}</span>
                          </li>
                        </ul>
                      </div>
                    ),
                    default: (
                      <div
                        class={['failure-topo-graph-legend', this.showLegend && 'failure-topo-graph-legend-active']}
                        v-bk-tooltips={{
                          content: this.$t('显示图例'),
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
                    minValue={8}
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
                  v-bk-tooltips={{ content: this.$t('重置比例'), boundary: this.wrapRef, zIndex: 999999 }}
                  onClick={this.handleResetZoom}
                >
                  <i class='icon-monitor icon-mc-restoration-ratio' />
                </div>
              </div>
              {!this.isPlay && (
                <div
                  class='expand-resource'
                  onClick={this.handleExpandResourceChange}
                >
                  <i
                    class={`icon-monitor ${this.showResourceGraph ? 'icon-arrow-right' : 'icon-mc-tree'} expand-icon`}
                  />
                </div>
              )}
            </div>
            {this.showResourceGraph && !this.isPlay && (
              <ResourceGraph
                ref='resourceGraphRef'
                entityId={this.nodeEntityId}
                modelData={this.topoRawDataCache.complete}
                resourceNodeId={this.resourceNodeId}
                onHideToolTips={this.handleHideToolTips}
                onToDetail={this.handleToDetail}
              />
            )}
          </div>
        </Loading>
        <FeedbackCauseDialog
          data={this.feedbackModel}
          visible={this.feedbackCauseShow}
          onEditSuccess={this.handleFeedBackChange}
          onRefresh={this.refresh}
          onUpdate:isShow={(val: boolean) => (this.feedbackCauseShow = val)}
        />
        <div style='display: none'>
          <FailureTopoTooltips
            ref='tooltipsRef'
            edge={this.tooltipsEdge}
            model={this.tooltipsModel}
            type={this.tooltipsType}
            onFeedBack={this.handleFeedBack}
            onToDetail={this.handleToDetail}
            onToDetailSlider={this.handleToDetailSlider}
            onToDetailTab={this.handleToDetailTab}
            onViewResource={this.handleViewResource}
          />
        </div>
      </div>
    );
  },
});
