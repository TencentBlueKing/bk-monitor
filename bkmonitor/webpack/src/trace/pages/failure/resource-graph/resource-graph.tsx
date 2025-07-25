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
import { type Ref, defineComponent, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';

import {
  type ICombo,
  Arrow,
  Graph,
  registerBehavior,
  registerCombo,
  registerEdge,
  registerLayout,
  registerNode,
} from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Exception, Loading } from 'bkui-vue';
import { incidentTopologyUpstream } from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils.js';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import ErrorImg from '../../../static/img/error.svg';
import NoDataImg from '../../../static/img/no-data.svg';
import FailureTopoTooltips from '../failure-topo/failure-topo-tooltips';
import { NODE_TYPE_SVG } from '../failure-topo/node-type-svg';
import TopoTooltip from '../failure-topo/topo-tppltip-plugin';
import { getApmServiceType, getNodeAttrs } from '../failure-topo/utils';
import { useIncidentInject } from '../utils';
import { createGraphData } from './resource-data';

import type { IEdge, ITopoCombo, ITopoData, ITopoNode } from '../failure-topo/types';

import './resource-graph.scss';

export default defineComponent({
  name: 'ResourceGraph',
  props: {
    resourceNodeId: {
      type: String,
      default: '',
    },
    entityId: {
      type: String,
      default: '0#0.0.0.0',
    },
    entityName: {
      type: String,
      default: '',
    },
    content: {
      type: String,
      default: '',
    },
    modelData: {
      type: Object,
      default: () => {},
    },
  },
  emits: ['toDetail', 'hideToolTips', 'collapseResource'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const graphRef = ref<HTMLElement>(null);
    const graphData = ref<ITopoData>({
      nodes: [],
      combos: [],
      edges: [],
    });
    /** 子combo位置前一个节点的位置 */
    let openNodePrev = null;
    /** 子combo位置之后的节点 */
    let nextNodes = [];
    let tooltips = null;
    const openAggregatedComboMap = {};
    /** 缓存所有节点的位置 */
    let maxNodeWidth = 0;
    const tooltipsModel = shallowRef();
    const tooltipsEdge: Ref<IEdge> = shallowRef();
    const tooltipsType = ref<string>('node');
    const tooltipsRef = ref<InstanceType<typeof FailureTopoTooltips>>();
    const incidentId = useIncidentInject();
    const loading = ref<boolean>(false);
    let graph: Graph;
    // 右侧画布数据获取检测
    const exceptionData = ref({
      showException: true,
      type: '',
      msg: '',
    });
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
    /** 渲染g6 */
    const renderGraph = () => {
      graph.data(JSON.parse(JSON.stringify(graphData.value)));
      graph.render();
      if (props.resourceNodeId) {
        const node = graph.findById(props.resourceNodeId);
        node && graph.setItemState(node, 'running', true);
      }
    };

    /** 删除展开的combo 并清除combo的信息 */
    const deleteChildCombo = (comboItem, needUpdate = true) => {
      maxNodeWidth = 0;
      const comboModel = comboItem.getModel();
      graphData.value.combos = graphData.value.combos.filter(combo => combo && combo.id !== comboModel.id);
      const node: ITopoNode = graphData.value.nodes.find(item => {
        return item.id === comboModel.aggregated_node;
      });
      const filterId = node.comboId;
      node.comboId = node.originComboId as string;
      node.showAggregated = false;
      node.aggregated_nodes = node.aggregated_nodes_copy as ITopoNode[];
      graphData.value.nodes = graphData.value.nodes.filter(node => node.comboId !== filterId);
      graphData.value.edges.forEach(edge => {
        if (edge.oldSource) {
          edge.source = edge.oldSource as string;
          edge.aggregatedCombo = false;
        }
        if (edge.oldTarget) {
          edge.target = edge.oldTarget as string;
          edge.aggregatedCombo = false;
        }
      });
      openAggregatedComboMap[node.originComboId] = false;
      if (!needUpdate) return;
      graph.clear();
      renderGraph();
    };
    /** 创建聚合combo 保存节点前后关系 修改节点与边的关系 */
    const createdChildCombo = (nodeItem: any) => {
      const combos = graph.getCombos();
      const model = nodeItem.getModel();
      if (openAggregatedComboMap[model.comboId]) {
        const combo = combos.find(item => item.getModel().id === openAggregatedComboMap[model.comboId]);
        deleteChildCombo(combo, false);
      }
      const nodeBBox = nodeItem.getBBox();
      const comboNodes = graphData.value.nodes.filter(node => node.comboId === model.comboId);
      const nodeIndex = comboNodes.findIndex(item => item.id === model.id); // JSON.parse(JSON.stringify(graphData.value.nodes.find(item => item.id === model.id)));
      const node = comboNodes[nodeIndex];
      /** 缓存节点前后关系 用于修正坐标 */
      openNodePrev = comboNodes[nodeIndex - 1] || null;
      nextNodes = comboNodes.slice(nodeIndex + 1, comboNodes.length);
      graphData.value.edges.forEach(edge => {
        if (edge.source === model.id) {
          edge.oldSource = edge.source;
          edge.source = node.comboId + node.id;
          edge.aggregatedCombo = true;
        } else if (edge.target === model.id) {
          edge.oldTarget = edge.target;
          edge.target = node.comboId + node.id;
          edge.aggregatedCombo = true;
        }
        edge.sourceAnchor = 0;
        edge.targetAnchor = 0;
      });

      const len = node.aggregated_nodes.length;
      const aggregateNodes = [];
      /** 创建一个用于展开子节点的combo */
      const combo: ITopoCombo = {
        comboId: node.comboId,
        id: node.comboId + node.id,
        parentId: node.comboId,
        aggregated_node: node.id,
        collapse: false,
        x: nodeBBox.x + ((len + 10) * 50) / 2 + 46,
        y: nodeBBox.y + 30,
        anchorPoints: [[0.5, 1]],
        fixSize: [(len + 1) * 100, 40],
        style: {
          radius: 40,
          padding: 0,
          stroke: '#979797', // 描边颜色
          lineWidth: 2, // 描边宽度
          lineDash: [4, 4], // 虚线的模式，表示线段长为 4，间隔为 4
        },
      };
      /** 将聚合子节点展开comboid设置为展开的combo */
      node.originComboId = node.comboId;
      node.comboId = node.comboId + node.id;
      node.showAggregated = true;
      node.aggregated_nodes.forEach(item => {
        const { is_root, is_anomaly } = item.entity;
        item.status = is_root || is_anomaly ? (is_root ? 'root' : 'error') : 'normal';
        item.comboId = node.comboId;
        item.showAggregated = true;
        item.type = 'resource-node';
        aggregateNodes.push(item);
      });
      graphData.value.nodes = graphData.value.nodes.concat(aggregateNodes);
      node.aggregated_nodes_copy = node.aggregated_nodes;
      node.aggregated_nodes = [];
      graphData.value.combos.push(combo);
      graphData.value.combos = graphData.value.combos.filter(combo => !!combo);
      openAggregatedComboMap[node.originComboId] = node.comboId;
      renderGraph();
    };
    /** 关闭弹窗， 主要用于左侧画布出现弹窗时关闭当前弹窗，避免出现2个 */
    const hideToolTips = () => {
      tooltipsRef?.value?.hide?.();
      tooltips?.hide?.();
    };
    /** 自定义节点 */
    const registerCustomNode = () => {
      registerNode('resource-node', {
        afterDraw(cfg, group) {
          const { entity, is_feedback_root, alert_all_recorved } = cfg as any;
          const nodeAttrs = getNodeAttrs(cfg as ITopoNode);
          if (entity.is_root || is_feedback_root) {
            group.addShape('circle', {
              attrs: {
                lineDash: [3],
                lineWidth: 1, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 25, // 圆半径
                stroke: entity.is_root ? '#F55555' : '#FF9C01',
              },
              name: 'resource-node-root-border',
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
              name: 'resource-node-rect',
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 20,
                textAlign: 'center',
                textBaseline: 'middle',
                text: t('根因'),
                fontSize: 11,
                fill: '#fff',
                ...nodeAttrs.textAttrs,
              },
              name: 'resource-node-text',
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
          const { aggregated_nodes, entity, is_feedback_root, showAggregated } = cfg as any;
          const nodeAttrs = getNodeAttrs(cfg as ITopoNode);
          const isRoot = entity.is_root || entity.is_feedback_root;
          const isAggregated = aggregated_nodes.length > 0;
          let nodeShapeWrap = null;
          if (!showAggregated) {
            nodeShapeWrap = group.addShape('rect', {
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
          }
          const nodeShape = group.addShape('circle', {
            zIndex: 10,
            attrs: {
              lineWidth: 1, // 描边宽度
              cursor: 'pointer', // 手势类型
              r: 20, // 圆半径
              ...nodeAttrs.groupAttrs,
              fill: isRoot ? '#F55555' : nodeAttrs.groupAttrs.fill,
            },
            name: 'resource-node-shape',
          });
          if (showAggregated) nodeShapeWrap = nodeShape;
          group.addShape('image', {
            zIndex: 9,
            attrs: {
              x: -12,
              y: -12,
              width: 24,
              height: 24,
              cursor: 'pointer', // 手势类型
              img: NODE_TYPE_SVG[getApmServiceType(entity)],
            },
            name: 'resource-node-img',
          });
          group.addShape('circle', {
            attrs: {
              lineWidth: 0, // 描边宽度
              cursor: 'pointer', // 手势类型
              r: 22, // 圆半径
              stroke: 'rgba(5, 122, 234, 1)',
            },
            name: 'resource-node-running',
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
                x: -15,
                y: 12,
                width: 30,
                height: 16,
                cursor: 'pointer',
                radius: 8,
                fill: '#fff',
                ...nodeAttrs?.rectAttrs,
              },
              name: 'resource-aggregated-node-rect',
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 20,
                isAggregateNode: aggregated_nodes.length > 0,
                textAlign: 'center',
                cursor: 'pointer',
                textBaseline: 'middle',
                text: entity.is_root ? t('根因') : aggregated_nodes.length + 1,
                fontSize: 12,
                fill: '#fff',
                ...nodeAttrs.textAttrs,
              },
              name: 'resource-aggregated-node-text',
            });
          }
          group.addShape('text', {
            zIndex: 11,
            attrs: {
              x: 0,
              y: aggregated_nodes?.length || entity.is_root || is_feedback_root ? 36 : 28,
              textAlign: 'center',
              textBaseline: 'middle',
              cursor: 'pointer',
              text: accumulatedWidth(entity?.properties?.entity_show_type || entity.entity_type),
              fontSize: 10,
              ...nodeAttrs.textNameAttrs,
            },
            name: 'resource-node-type-text',
          });
          aggregated_nodes.length === 0 &&
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: entity.is_root || is_feedback_root ? 48 : 40,
                textAlign: 'center',
                cursor: 'point',
                textBaseline: 'middle',
                text: accumulatedWidth(entity.entity_name),
                fontSize: 10,
                ...nodeAttrs.textNameAttrs,
              },
              name: 'resource-node-name-text',
            });
          return nodeShapeWrap;
        },
        setState(name, value, item) {
          const group = item.getContainer();
          const shape = group.get('children')?.[0]; // 顺序根据 draw 时确定
          if (name === 'hover') {
            shape?.attr({
              shadowColor: value ? 'rgba(0, 0, 0, 0.5)' : false,
              shadowBlur: value ? 6 : false,
              shadowOffsetX: value ? 0 : false,
              shadowOffsetY: value ? 2 : false,
              strokeOpacity: value ? 0.6 : 1,
              cursor: 'pointer', // 手势类型
            });
          } else if (name === 'running') {
            const runningShape = group.find(e => e.get('name') === 'resource-node-running');
            const runningShadowShape = group.find(e => e.get('name') === 'topo-node-running-shadow');
            const rootBorderShape = group.find(e => e.get('name') === 'resource-node-root-border');
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
            }
          } else if (name === 'dark') {
            group.attr({
              opacity: value ? 0.4 : 1,
            });
          }
        },
      });
    };
    /** 自定义combo */
    const registerCustomEdge = () => {
      registerEdge(
        'resource-edge',
        {
          afterDraw(cfg, group) {
            if (!cfg.count) return;
            // 获取图形组中的第一个图形，在这里就是边的路径图形
            const shape = group.get('children')[0];
            // 获取路径图形的中点坐标
            const midPoint = shape.getPoint(0.5);
            // 在中点增加一个矩形，注意矩形的原点在其左上角
            (cfg.count as number) > 1 &&
              group.addShape('rect', {
                zIndex: 10,
                attrs: {
                  // cursor: 'pointer',
                  width: 10,
                  height: 10,
                  cursor: 'point',
                  fill: 'rgba(58, 59, 61, 1)',
                  // x 和 y 分别减去 width / 2 与 height / 2，使矩形中心在 midPoint 上
                  x: midPoint.x - 5,
                  y: midPoint.y - 5,
                  radius: 5,
                },
              });
            (cfg.count as number) > 1 &&
              group.addShape('text', {
                zIndex: 11,
                attrs: {
                  x: midPoint.x,
                  y: midPoint.y,
                  cursor: 'point',
                  textAlign: 'center',
                  textBaseline: 'middle',
                  text: cfg.count,
                  fontSize: 12,
                  fill: '#fff',
                  // cursor: 'pointer'
                },
                name: 'resource-node-text',
              });
            // 如果展开的是子combo 需要修正下线的连接为，将线的连接位置改为combo的收起按钮的位置
            const { targetNode, sourceNode } = cfg as { sourceNode: any; targetNode: any };
            const targetNodeBBox = targetNode.getBBox();
            const sourceNodeBBox = sourceNode.getBBox();
            if (sourceNode.getType() === 'combo' && sourceNodeBBox.y < targetNodeBBox.y) {
              const cPath = shape.attrs.path[1];
              shape.attr('path', [['M', cfg.startPoint.x, cfg.startPoint.y + 7], cPath]);
            }
            if (targetNode.getType() === 'combo' && targetNode.y > sourceNodeBBox.y) {
              const cPath = shape.attrs.path[1];
              cPath[cPath.length - 1] = cPath[cPath.length - 1] + 7;
              shape.attr('path', [['M', cfg.startPoint.x, cfg.startPoint.y], cPath]);
            }
          },
          setState(name, value, item) {
            const { is_anomaly } = item.getModel();
            const highlightColor = is_anomaly ? '#F55555' : '#699DF4';
            const darkColor = is_anomaly ? '#F55555' : '#63656D';
            if (name === 'highlight') {
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
    /** 基于canvas或者坐标位置 */
    const getCanvasByPoint = combo => {
      const comboBBox = combo.getBBox();
      return {
        topLeft: graph.getCanvasByPoint(comboBBox.x, comboBBox.y),
        bottomRight: graph.getCanvasByPoint(comboBBox.x + comboBBox.width, comboBBox.y + comboBBox.height),
      };
    };
    /** 自定义拖拽 */
    const registerCustomBehavior = () => {
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
          if (e.item && ['node', 'edge'].includes(e.item.getType())) {
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
          if (e.item && ['node', 'edge'].includes(e.item.getType())) {
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
              bottomCombo: ITopoCombo;
              height: number;
              topCombo: ITopoCombo;
              width: number;
              xCombo: ITopoCombo;
            };
            let { movementX, movementY } = e.originalEvent;
            // 大于零向上拖动
            if (movementY < 0) {
              const { bottomRight } = getCanvasByPoint(comboRect.bottomCombo);
              bottomRight.y < comboRect.height && (movementY = 0);
            } else {
              const { topLeft } = getCanvasByPoint(comboRect.topCombo);
              topLeft.y > 0 && (movementY = 0);
            }
            const { topLeft, bottomRight } = getCanvasByPoint(comboRect.xCombo);
            /** 大于0向左拖动 */
            if (movementX < 0) {
              bottomRight.x < comboRect.width && (movementX = 0);
            } else {
              topLeft.x > 0 && (movementX = 0);
            }
            graph.translate(movementX, movementY);
          }
        },
        onMouseUp(e) {
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
              bottomRight.y < height && (dy = 0);
            } else {
              const topCombo = combos[0];
              const { topLeft } = getCanvasByPoint(topCombo);
              topLeft.y > 0 && (dy = 0);
            }
            dx = 0;
          } else {
            const topCombo = combos[0];
            const { topLeft, bottomRight } = getCanvasByPoint(topCombo);
            /** 大于0判断右侧 否则判断左侧 */
            if (deltaX > 0) {
              bottomRight.x < width && (dx = 0);
            } else {
              topLeft.x > 0 && (dx = 0);
            }
            dy = 0;
          }
          graph.translate(dx, dy);
        },
      });
    };
    /** 自定义combo */
    const registerCustomCombo = () => {
      registerCombo(
        'resource-combo',
        {
          labelPosition: 'left',
          labelAutoRotate: false,
          drawShape(cfg, group) {
            const keyShape = group.addShape('rect', {
              zIndex: 100,
              attrs: {
                fill: '#ddd',
                x: 0,
                y: 0,
              },
              name: 'resource-combo-shape',
            });
            const w = graph.getWidth();
            // const height = graph.getHeight();
            const { height } = document.querySelector('.resource-graph').getBoundingClientRect();
            const combos = graphData.value.combos.filter(combos => combos && !combos?.parentId);
            const comboxHeight = Math.max((height - 40) / combos.length, 120);
            if (cfg.groupName) {
              group.addShape('text', {
                zIndex: 101,
                attrs: {
                  x: -w / 2 + 8,
                  y: -comboxHeight / 2 + 5,
                  textAlign: 'left',
                  text: cfg.groupName,
                  fontSize: 12,
                  fontWeight: 400,
                  fill: '#979BA5',
                },
                name: 'resource-combo-title',
              });
            }
            group.addShape('text', {
              zIndex: 101,
              attrs: {
                x: -w / 2 + 8,
                y: 0,
                textAlign: 'left',
                text: cfg.title,
                fontSize: 12,
                fill: '#EAEBF0',
              },
              name: 'resource-combo-text',
            });
            if (cfg.anomaly_count) {
              group.addShape('text', {
                zIndex: 11,
                attrs: {
                  x: -w / 2 + 8,
                  y: 22,
                  textAlign: 'left',
                  text: cfg.anomaly_count,
                  fontSize: 12,
                  fontWeight: 700,
                  fill: '#FF6666',
                },
                name: 'resource-combo-text',
              });
            }
            group.addShape('text', {
              zIndex: 101,
              attrs: {
                x: -w / 2 + 8 + (cfg.anomaly_count ? 10 : 0),
                y: 22,
                textAlign: 'left',
                text: cfg.subTitle,
                fontSize: 12,
                fontWeight: 700,
                fill: '#EAEBF0',
              },
              name: 'resource-combo-count-text',
            });
            group.addShape('rect', {
              zIndex: 100,
              attrs: {
                x: -w / 2 + 80,
                y: -comboxHeight / 2 - 26,
                width: 1,
                height: comboxHeight + 40,
                fill: '#14161A',
              },
              name: 'resource-combo-bg',
            });
            group.addShape('rect', {
              zIndex: 100,
              attrs: {
                x: -w / 2 - 60,
                y: comboxHeight / 2 + 14, // 定位在combo底部
                width: w + 120,
                height: 1,
                fill: '#14161A',
              },
              name: 'resource-combo-bottom-border',
            });
            return keyShape;
          },
        },
        'rect'
      );
      registerCombo(
        'resource-child-combo',
        {
          labelPosition: 'left',
          labelAutoRotate: false,
          defaultExpandAll: false,
          drawShape(cfg, group) {
            const keyShape = group.addShape('rect', {
              zIndex: 10,
              attrs: {
                ...cfg.style,
                fill: '#313238',
                stroke: '#979BA5',
              },
              name: 'resource-combo-shape',
            });
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -15,
                y: cfg.style.height - 16,
                width: 30,
                height: 16,
                cursor: 'pointer',
                radius: 8,
                fill: '#313238',
                stroke: '#979BA5',
              },
              name: 'resource-collapse-combo-rect',
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: cfg.style.height - 9,
                textAlign: 'center',
                textBaseline: 'middle',
                cursor: 'pointer',
                text: '> <',
                fontWeight: 700,
                fontSize: 12,
                fill: '#C5C7CD',
              },
              name: 'resource-collapse-combo-img',
            });
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -30,
                y: cfg.style.height - 20,
                width: 60,
                height: 26,
                cursor: 'pointer',
                fill: '#313238',
                opacity: 0,
                radius: 8,
                stroke: '#979BA5',
              },
              name: 'resource-collapse-combo-click-wrap',
            });
            return keyShape;
          },
          setState(name, value, item) {
            const { nodes } = graph.getComboChildren(item as ICombo);
            if (name === 'highlight') {
              nodes.forEach(node => {
                graph.setItemState(node, 'dark', false);
                graph.setItemState(node, 'highlight', true);
              });
            } else if (name === 'dark') {
              nodes.forEach(node => {
                graph.clearItemStates(node, ['dark', 'highlight']);
              });
            }
          },
        },
        'rect'
      );
    };
    /** 自定义tips */
    const registerCustomTooltip = () => {
      tooltips = new TopoTooltip(
        {
          offsetX: 10,
          offsetY: 10,
          trigger: 'click',
          itemTypes: ['node', 'edge'],
          getContent: e => {
            const type = e.item.getType();
            const model = e.item.getModel();
            if (type === 'edge') {
              const { nodes = [] } = props.modelData;
              const targetModel = nodes.find(item => item.id === model.target);
              const sourceModel = nodes.find(item => item.id === model.source);
              tooltipsModel.value = [sourceModel, targetModel];
              tooltipsEdge.value = model as IEdge;
              model.nodes = [
                {
                  ...sourceModel,
                  entity: {
                    is_anomaly: model.source_is_anomaly,
                    is_on_alert: model.source_is_on_alert,
                    entity_name: model.source_name,
                    entity_type: model.source_type,
                  },
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
            }
            tooltipsType.value = type;
            return tooltipsRef.value.$el;
          },
        },
        e => {
          const { item } = e;
          const model: ITopoNode = item.getModel();
          if (item.getType() === 'node' && model.aggregated_nodes.length > 0) {
            return true;
          }
          if (['resource-aggregated-node-rect', 'resource-aggregated-node-text'].indexOf(e.target?.cfg?.name) !== -1)
            return true;
        }
      );
    };
    /** 自定义布局 */
    const registerCustomLayout = () => {
      registerLayout('resource-layout', {
        execute() {
          const { nodes, combos } = this;
          const nodeBegin = 80;
          const { height } = document.querySelector('.resource-graph').getBoundingClientRect();
          // const height = graph.getHeight();
          const combosArr = graphData.value.combos.filter(combos => {
            return !combos?.parentId;
          });
          const comboxHeight = Math.max((height - 40) / combosArr.length, 120);
          const nodeSize = 46;
          combos
            .filter(item => !item.parentId)
            .forEach((combo, comboIndex) => {
              const comboNodes = nodes.filter(node => node.comboId.toString() === combo.id.toString());
              const xBegin = nodeBegin + nodeSize / 2;
              const yBegin = comboxHeight / 2 + comboIndex * comboxHeight;
              comboNodes.forEach((node, index) => {
                // node.fixSize = [width, comboxHeight];
                node.x = xBegin + index * 120;
                node.y = yBegin + 22;
                maxNodeWidth = Math.max(maxNodeWidth, node.x);
              });
            });
        },
      });
    };
    /** 获取数据 */
    const getTopologyUpstream = () => {
      if (!props.entityId) {
        exceptionData.value.showException = true;
        exceptionData.value.type = 'noData';
        exceptionData.value.msg = t('暂无数据');
        return;
      }
      loading.value = true;
      incidentTopologyUpstream(
        { id: incidentId.value, entity_id: props.entityId },
        {
          needMessage: false,
        }
      )
        .then(res => {
          exceptionData.value.showException = false;
          const { ranks, edges } = res;
          if (ranks.length === 0 && edges.length === 0) {
            graph?.destroy?.();
            graph = null;
            exceptionData.value.showException = true;
            exceptionData.value.type = 'noData';
            exceptionData.value.msg =
              props.entityId.indexOf('Unknown') !== -1 ? t('第三方节点不支持查看从属') : t('暂无数据');
          } else {
            exceptionData.value.showException = false;
          }

          const ranksMap = {};
          ranks.forEach(rank => {
            if (ranksMap[rank.rank_category.category_name]) {
              ranksMap[rank.rank_category.category_name].push(rank);
            } else {
              ranksMap[rank.rank_category.category_name] = [rank];
            }
          });
          graphData.value = createGraphData(ranksMap, edges);
          if (!graph) {
            setTimeout(() => {
              init();
              renderGraph();
            }, 100);
          } else {
            renderGraph();
          }
        })
        .catch(err => {
          if (err) {
            exceptionData.value.showException = true;
            exceptionData.value.type = 'error';
            exceptionData.value.msg = err.data?.error_details ? err.data.error_details.overview : err.message;
          }
        })
        .finally(() => {
          setTimeout(() => {
            loading.value = false;
          }, 300);
        });
    };
    watch(
      () => props.entityId,
      () => {
        getTopologyUpstream();
      },
      { immediate: true }
    );
    /** 计算combo宽度用于调整所有combo宽度保持一致 */
    const computedMaxWidth = (nodes, combos) => {
      const nodesW = nodes.map(node => {
        const bbox = node.getBBox();
        return bbox.maxX + bbox.width / 2;
      });
      const comboW = combos.map(combo => {
        const bbox = combo.getBBox();
        return bbox.maxX + bbox.width / 2;
      });
      return Math.max(Math.max.apply(null, nodesW), Math.max.apply(null, comboW));
    };
    /** 修复当前combo前后的节点的位置 */
    const fixComboPrevAndNext = (nodes, combo) => {
      if (!combo) return {};
      const comboBBox = combo.getBBox();
      if (openNodePrev?.id) {
        const prevNode = graph.findById(openNodePrev.id).getBBox();
        /** 修复一次 防止点击展开的combo会根前一个节点重合 */
        graph.updateItem(combo, {
          x: prevNode.x + comboBBox.width / 2 + 80,
          y: prevNode.y + comboBBox.height / 2,
        });
      }
      /** 重排 combo后的节点 */
      if (nextNodes.length > 0) {
        nextNodes.forEach(node => {
          const graphNode = graph.findById(node.id);
          graph.updateItem(graphNode, {
            x: graphNode.getBBox().x + comboBBox.width + 24,
          });
        });
      }
      /** 重排combo内的节点 */
      const { nodes: childNodes } = graph.getComboChildren(combo);
      childNodes.forEach((node, index) => {
        const comboBBox = combo.getBBox();
        const xBegin = 100; /** 节点的宽度为46 名称为120 */
        const x = comboBBox.x + 65;
        const y = comboBBox.y + comboBBox.height / 2 - 12; /** 节点存在文字展示的问题需要减少一点偏移 */
        graph.updateItem(node, {
          x: x + index * xBegin,
          y,
        });
      });
    };
    /** 画布相关的 */
    const init = () => {
      if (!graphRef.value) return;
      const { width, height } = graphRef.value.getBoundingClientRect();
      registerCustomNode();
      registerCustomEdge();
      registerCustomCombo();
      registerCustomBehavior();
      registerCustomTooltip();
      registerCustomLayout();
      graph = new Graph({
        container: graphRef.value as HTMLElement,
        width,
        height,
        fitView: false,
        fitViewPadding: 0,
        groupByTypes: false,
        plugins: [tooltips],
        layout: {
          type: 'resource-layout',
          rankdir: 'BT',
          preventOverlap: true,
          minNodeSpacing: 20,
          ranksep: 40, // 设置层间距为 80
          nodesep: 30,
        },
        defaultNode: {
          type: 'circle',
          size: 40,
          style: {
            cursor: 'pointer',
          },
        },
        defaultEdge: {
          type: 'quadratic',
          size: 1,
          color: '#63656D',
          cursor: 'default',
        },
        defaultCombo: {
          // type: 'rect',
          type: 'resource-combo',
          style: {
            cursor: 'grab',
            fill: '#292A2B',
            radius: 0,
            lineWidth: 0,
          },
        },
        modes: {
          default: ['drag-canvas-move', 'custom-scroll-canvas'],
        },
      });
      /** 设置节点 边 combo */
      graph.node(node => {
        return {
          ...node,
          type: 'resource-node',
        };
      });
      graph.edge((cfg: any) => {
        const { is_anomaly, edge_type } = cfg;
        const isInvoke = edge_type === 'ebpf_call';
        const color = is_anomaly ? '#F55555' : '#63656E';
        const edg = {
          ...cfg,
          shape: 'quadratic',
          style: {
            cursor: 'pointer',
            lineAppendWidth: 15,
            endArrow:
              isInvoke || is_anomaly
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
            lineWidth: is_anomaly ? 2 : 1,
            lineDash: is_anomaly ? [4, 2] : false,
          },
        };
        if (!cfg.color) return edg;
        return {
          ...edg,
          shape: 'quadratic',
          type: 'resource-edge',
          cursor: 'pointer',
        };
      });
      graph.combo(combo => {
        if (combo.parentId) {
          return {
            ...combo,
            type: 'resource-child-combo',
          };
        }
        return {
          ...combo,
          type: 'resource-combo',
        };
      });
      /** 重要 修复combo及节点的位置 */
      graph.on('afterlayout', () => {
        const combos = graph.getCombos();
        const filterCombos = combos.filter(item => !item.get('model').parentId);
        const graphWidth = graph.getWidth();
        const { height } = document.querySelector('.resource-graph').getBoundingClientRect();
        const comboxHeight = Math.max((height - 40) / filterCombos.length, 120);
        filterCombos.forEach(combo => {
          // 获取 Combo 中包含的节点和边的范围
          const nodeBegin = 80;
          const updateConfig = {
            size: [graphWidth, comboxHeight],
            x: graphWidth / 2 + 20,
          };
          graph.updateItem(combo, updateConfig);
          /** 修正node节点位置保证node节点不会出现在左侧title区域 */
          const { nodes, combos } = graph.getComboChildren(combo);
          const xBegin = nodeBegin + 50 / 2;
          const fixBegin = xBegin - 10;

          const fixPositionNode = nodes.find(node => {
            const nodeBbox = node.getBBox();
            return nodeBbox.x < fixBegin;
          });
          if (!fixPositionNode) {
            return;
          }
          nodes.forEach((node, index) => {
            const nodeBbox = node.getBBox();
            graph.updateItem(node, {
              x: nodeBbox.x < fixBegin && index < 1 ? xBegin : xBegin * (index + 1),
            });
          });
          fixComboPrevAndNext(nodes, combos[0]);
          maxNodeWidth = computedMaxWidth(nodes, combos);
        });
        /** 延迟修正，主要解决combo渲染后会因为节点导致宽度等变化，所以等渲染完后最后修复一次 */
        setTimeout(() => {
          /** combo的宽度随节点多少来决定，但是希望所有combo的宽度一致 */
          const comboWidthS = filterCombos.map(combo => {
            const bbox = combo.getBBox();
            return bbox.width;
          });
          const maxWidth = Math.max.apply(null, [...comboWidthS, graphWidth, maxNodeWidth + 60]);
          filterCombos.forEach((combo, index) => {
            const group = combo.getContainer();
            const model = combo.get('model');
            const bbox = combo.getBBox();
            const { nodes, combos } = graph.getComboChildren(combo);
            const prevBox = filterCombos[index - 1]?.getBBox();
            const padding = prevBox ? prevBox.y + prevBox.height : '';
            if (maxWidth > graphWidth) {
              graph.updateItem(combo, {
                size: [maxWidth, comboxHeight],
                x: (maxWidth > graphWidth ? maxWidth : graphWidth) / 2 + 20,
                y: bbox.height / 2 + Number(padding) + 5,
              });
              let shape = null;
              /** 宽度变化后修复左侧标题栏位置 */
              group.find((e): any => {
                if (e.get('name') === 'resource-combo-count-text') {
                  e.attr({ x: -maxWidth / 2 - 8 + (model.anomaly_count ? 10 : 0) });
                } else if (e.get('name') === 'resource-combo-bg') {
                  e.attr({ x: -maxWidth / 2 + 80 });
                } else if (e.get('name') === 'resource-combo-bottom-border') {
                  e.attr({ x: -maxWidth / 2 - 60 });
                } else if (e.get('name') !== 'resource-combo-shape') {
                  e.attr({ x: -maxWidth / 2 - 8 });
                } else {
                  shape = e;
                }
              });
              /** 修正node节点位置保证node节点不会出现在左侧title区域 */
              if (nodes.length) {
                const shapeBbox = shape.getBBox();
                const left = -shapeBbox.maxX + shapeBbox.width / 2 + 140;
                const node = nodes[0];
                const nodeBbox = node.getBBox();
                if (nodes.length > 2 && nodeBbox.x > left) {
                  nodes.forEach((node, index) => {
                    graph.updateItem(node, {
                      x: left + index * 120,
                    });
                  });
                }
                if (nodes.length === 1) {
                  graph.updateItem(node, {
                    x: graphWidth / 2 + 80,
                  });
                }
              }
            }
            /** 修复子combo中节点位置 */
            if (combos.length > 0) {
              fixComboPrevAndNext(nodes, combos[0]);
            }
          });
        }, 50);
      });
      /** 清除高亮的节点 */
      graph.on('click', e => {
        if (!e.item || e.item.getType() !== 'node') {
          clearAllStats();
        }
      });
      graph.on('node:mouseenter', e => {
        const { item } = e;
        if (['resource-node-type-text', 'resource-node-name-text'].includes(e.target.get('name'))) {
          return;
        }
        graph.setItemState(item, 'hover', true);
      });
      /** 清除高亮状态 */
      function clearAllStats() {
        graph.setAutoPaint(false);
        graph.getEdges().forEach(function (edge) {
          graph.clearItemStates(edge, ['dark', 'highlight']);
          // edge.toFront();
        });
        graph.getNodes().forEach(function (node) {
          graph.clearItemStates(node, ['dark', 'highlight']);
          node.toFront();
        });
        graph.paint();
        graph.setAutoPaint(true);
      }
      // 监听鼠标离开节点
      graph.on('node:mouseleave', e => {
        const nodeItem = e.item;
        graph.setItemState(nodeItem, 'hover', false);
      });
      /** 子combo点击收起 */
      graph.on('combo:click', e => {
        tooltips.hide();
        const { item, target } = e;
        if (
          [
            'resource-collapse-combo-click-wrap',
            'resource-collapse-combo-rect',
            'resource-collapse-combo-img',
          ].includes(target.cfg.name)
        ) {
          deleteChildCombo(item);
        }
        tooltips.hide();
      });
      graph.on('aftertranslate', e => {
        // 存储或更新图形平移后的状态
        graph.set('currentTransform', {
          x: e.x,
          y: e.y,
          k: graph.getZoom(),
        });
      });
      /** 点击tips时，关闭左侧打开的tips */
      graph.on('tooltipchange', ({ action }) => {
        action === 'show' && emit('hideToolTips');
      });
      /** 设置高亮 */
      graph.on('node:click', e => {
        const { target } = e;
        let nodeItem = e.item;
        if (['resource-aggregated-node-rect', 'resource-aggregated-node-text'].includes(target.cfg.name)) {
          tooltipsRef?.value?.hide?.();
          tooltips?.hide?.();
          graphData.value.combos.push(createdChildCombo(nodeItem) as any);
          return;
        }
        graph.setAutoPaint(false);
        const nodeModel = nodeItem.getModel();
        /** 如点击的节点是子combo中的节点 则将点击对象修改为子combo */
        if (nodeModel.showAggregated) {
          nodeItem = graph.findById((nodeModel as ITopoNode).comboId);
        }
        /** 更新节点状态 */
        graph.getNodes().forEach(function (node) {
          graph.clearItemStates(node, ['dark', 'highlight']);
          graph.setItemState(node, 'dark', true);
          node.toFront();
        });
        /** 根据边关系调整最后的高亮效果 */
        graph.getEdges().forEach(function (edge) {
          const source = edge.getSource();
          const target = edge.getTarget();

          if (source === nodeItem) {
            graph.setItemState(target, 'dark', false);
            graph.setItemState(target, 'highlight', true);
            graph.setItemState(edge, 'highlight', true);
            // edge.toFront();
            nodeItem.getType() === 'node' && nodeItem.toFront();
          } else if (target === nodeItem) {
            graph.setItemState(source, 'dark', false);
            graph.setItemState(source, 'highlight', true);
            graph.setItemState(edge, 'highlight', true);
            // edge.toFront();
          } else {
            graph.setItemState(edge, 'highlight', false);
          }
        });

        graph.setItemState(nodeItem, 'dark', false);
        graph.setItemState(nodeItem, 'highlight', true);
        graph.paint();
        graph.setAutoPaint(true);
        return;
      });
      nextTick(() => {
        addListener(graphRef.value as HTMLElement, onResize);
      });
    };
    /** 窗口宽度变化 */
    function handleResize() {
      if (!graph || graph.get('destroyed') || !graphRef.value) return;
      const { height } = document.querySelector('.resource-graph').getBoundingClientRect();
      const { width } = graphRef.value.getBoundingClientRect();
      tooltipsRef?.value?.hide?.();
      tooltips?.hide?.();
      graph.changeSize(width, height);
      graph.render();
      /** 打开时会触发导致动画消失 */
      if (props.resourceNodeId) {
        const node = graph.findById(props.resourceNodeId);

        node && graph.setItemState(node, 'running', true);
      }
    }
    const onResize = debounce(300, handleResize);
    onMounted(() => {
      init();
    });
    onUnmounted(() => {
      graphRef.value && removeListener(graphRef.value as HTMLElement, onResize);
    });
    const handleToDetail = node => {
      emit('toDetail', node);
    };
    const handleException = () => {
      const { type, msg } = exceptionData.value;
      if (!type && !msg) return '';
      return (
        <Exception
          class='exception-wrap'
          v-slots={{
            type: () => (
              <img
                class='custom-icon'
                alt=''
                src={type === 'noData' ? NoDataImg : ErrorImg}
              />
            ),
          }}
        >
          <div style={{ color: type === 'noData' ? '#979BA5' : '#E04949' }}>
            <div class='exception-title'>{type === 'noData' ? msg : t('查询异常')}</div>
            {type === 'error' && <div class='exception-desc'>{msg}</div>}
          </div>
        </Exception>
      );
    };
    const handleCollapseResource = () => {
      emit('collapseResource');
    };
    return {
      graphRef,
      tooltipsRef,
      tooltipsModel,
      tooltipsEdge,
      tooltipsType,
      hideToolTips,
      handleToDetail,
      loading,
      graph,
      exceptionData,
      handleException,
      handleCollapseResource,
      t,
    };
  },
  render() {
    return (
      <div class='resource-graph'>
        <Loading
          class='resource-graph-loading'
          color='#292A2B'
          loading={this.loading}
        >
          <div class='graph-title'>
            <span class='graph-title_label'>{this.t('从属关系')}</span>
            {this.entityName && <span class='graph-title_line' />}
            <span
              key={this.entityName}
              class='graph-title_value'
              v-overflow-tips={{
                text: this.entityName,
              }}
            >
              {this.entityName}
            </span>

            <span onClick={this.handleCollapseResource}>
              <i class='icon-monitor icon-gongneng-shouqi graph-title_icon' />
            </span>
          </div>
          {this.exceptionData.showException ? (
            this.handleException()
          ) : (
            <div
              ref='graphRef'
              class='graph-wrapper'
            />
          )}
        </Loading>
        <div style='display: none'>
          <FailureTopoTooltips
            ref='tooltipsRef'
            edge={this.tooltipsEdge}
            model={this.tooltipsModel}
            showViewResource={false}
            type={this.tooltipsType}
            onToDetail={this.handleToDetail}
          />
        </div>
      </div>
    );
  },
});
