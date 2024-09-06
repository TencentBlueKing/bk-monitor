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

// import Vue from 'vue';
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import G6, { type IGroup, type ModelConfig, type Graph, type INode, type IEdge, type IShape } from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import { nodeEndpointsTop } from 'monitor-api/modules/apm_topo';
import { Debounce } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import CompareGraphTools from '../../apm-time-series/components/compare-topo-fullscreen/compare-graph-tools';
import ApmTopoLegend from './apm-topo-legend';
// import TopoMenu, { type ITopoMenuItem } from './topo-menu';
import {
  CategoryEnum,
  type NodeDisplayTypeMap,
  type EdgeDataType,
  NodeDisplayType,
  nodeIconMap,
  nodeLanguageMap,
} from './utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './apm-relation-topo.scss';

export interface INodeModel {
  data: {
    category: CategoryEnum;
    display_key: string;
    name: string;
    type: NodeDisplayTypeMap;
    kind: string;
    id: string;
    extra_info: Record<string, any>;
  };
  have_data: boolean;
  request_count: number;
  color: string;
  size: number;
  menu: { name: string; action: string; url?: string; type?: string }[];
  node_tips: { name: string; value: string }[];
}

type IEdgeModel = {
  from_name: string;
  to_name: string;
  edge_breadth: number;
  duration_avg?: string;
  duration_p99?: string;
  duration_p95?: string;
  request_count?: number;
};

type ApmRelationTopoProps = {
  data: { nodes: INodeModel[]; edges: IEdgeModel[] };
  activeNode: string;
  edgeType: EdgeDataType;
  appName: string;
  showType: string;
  dataType: string;
  refreshTopoLayout: boolean;
  filterCondition: {
    type: CategoryEnum;
    showNoData: boolean;
    searchValue: string;
  };
};

type ApmRelationTopoEvent = {
  onNodeClick: (node: INodeModel) => void;
  onResourceDrilling: (node: INodeModel) => void;
  onEdgeTypeChange: (edgeType: EdgeDataType) => void;
  onServiceDetail: (node: INodeModel) => void;
  onDrillingNodeClick: (node: INodeModel, name: string) => void;
};

type INodeModelConfig = ModelConfig & INodeModel;

// 节点hover阴影宽度
const HoverCircleWidth = 13;

const LIMIT_RADIAL_LAYOUT_COUNT = 700;
const LIMIT_WORKER_ENABLED = 500;

@Component
export default class ApmRelationTopo extends tsc<ApmRelationTopoProps, ApmRelationTopoEvent> {
  @Prop() data: ApmRelationTopoProps['data'];
  @Prop() activeNode: string;
  @Prop() edgeType: EdgeDataType;
  @Prop({ default: true }) refreshTopoLayout: boolean;
  @Prop() filterCondition: ApmRelationTopoProps['filterCondition'];
  @Prop() showType: string;
  @Prop() appName: string;
  @Prop() dataType: string;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  @Ref('relationGraph') relationGraphRef: HTMLDivElement;
  @Ref('topoToolsPanel') topoToolsPanelRef: HTMLDivElement;
  @Ref('topoToolsPopover') topoToolsPopoverRef: HTMLDivElement;
  @Ref('thumbnailTool') thumbnailToolRef: HTMLDivElement;
  @Ref('menuList') menuListRef: HTMLDivElement;

  canvasWidth = 0; // 画布宽度
  canvasHeight = 0; // 画布高度
  minZoomVal = 0.1; // 缩放滑动条最小值
  maxZoomVal = 2; // 缩放滑动条最大值
  graph: Graph = null; // 拓扑图实例
  toolsPopoverInstance = null; // 工具栏弹窗实例
  /** 拓扑图是否渲染完成 */
  isRender = false;
  /** 图例筛选 */
  legendFilter = {
    status: '',
    size: '',
  };
  /** 接口下钻节点列表 */
  interfaceNodeList = [];

  /** 图表缩放大小 */
  scaleValue = 1;
  /** 图表初始缩放 */
  initScale = 1;
  /** 上一次展示的图 */
  lastShowImage = '';
  /** 是否显示缩略图 */
  showThumbnail = false;
  /** 是否显示图例 */
  showLegend = false;
  /** 工具栏弹窗大小 */
  graphToolsRect = {
    width: 0,
    height: 0,
  };

  /** 布局基础配置 */
  baseLayoutConf = {
    center: [this.canvasWidth / 2, this.canvasHeight / 2], // 布局的中心
    linkDistance: 400, // 边长度
    maxIteration: 1000, // 最大迭代次数
    preventOverlap: true, // 是否防止重叠
    nodeSize: 40, // 节点大小（直径）
    nodeSpacing: 500, // preventOverlap 为 true 时生效, 防止重叠时节点边缘间距的最小值
  };

  radialLayoutConf = {
    ...this.baseLayoutConf,
    type: 'radial',
    maxPreventOverlapIteration: 1000, // 防止重叠步骤的最大迭代次数
    unitRadius: 200, // 每一圈距离上一圈的距离
    strictRadial: false, // 是否必须是严格的 radial 布局，及每一层的节点严格布局在一个环上。preventOverlap 为 true 时生效。
  };

  gForceLayoutConf = {
    ...this.baseLayoutConf,
    type: 'gForce',
    linkDistance: 200,
    nodeSpacing: 200,
    maxIteration: 4000,
    workerEnabled: true, // 可选，开启 web-worker
  };

  menuCfg = {
    x: 0,
    y: 0,
    show: false,
    drillingLoading: true,
    isDrilling: false,
    nodeModel: null,
    drillingList: [],
  };

  layout = null;

  /** 当前使用的布局 应用概览使用 radial布局、下钻服务使用 dagre 布局 */
  get graphLayout() {
    const curNodeLen = this.data?.nodes?.length || 0;
    // 节点过多 使用 gForce 布局
    if (curNodeLen > LIMIT_RADIAL_LAYOUT_COUNT) return this.gForceLayoutConf;
    // 默认使用 radial 辐射布局
    return Object.assign(this.radialLayoutConf, {
      // 当节点数量大于 LIMIT_WORKER_ENABLED 开启
      workerEnabled: curNodeLen > LIMIT_WORKER_ENABLED,
    });
  }

  /** 格式化后的数据 */
  get formatData() {
    const { nodes = [], edges = [] } = this.data;
    return {
      nodes: nodes.map(node => ({
        ...node,
        id: node.data.id,
      })),
      edges: edges.map(item => {
        const common = {
          source: item.from_name,
          target: item.to_name,
          label: String(item.duration_avg || item.duration_p95 || item.duration_p99 || item.request_count),
          style: {
            lineWidth: item.edge_breadth,
            stroke: '#C4C6CC',
            lineDash: [4, 4],
            endArrow: {
              path: G6.Arrow.triangle(10, 10, 0), // 路径
              fill: '#C4C6CC', // 填充颜色
            },
          },
        };

        if (item.from_name === item.to_name) {
          return {
            type: 'apm-loop-dash',
            ...common,
          };
        }
        return {
          type: 'apm-line-dash',
          ...common,
        };
      }),
    };
  }

  beforeDestroy() {
    this.toolsPopoverInstance?.destroy?.();
    this.toolsPopoverInstance = null;
    this.hideMenu();
    removeListener(this.$el as HTMLDivElement, this.handleResize);
  }

  mounted() {
    addListener(this.$el as HTMLDivElement, this.handleResize);
  }

  @Debounce(100)
  handleResize() {
    if (!this.graph || this.graph.get('destroyed')) return;
    const { width, height } = (this.relationGraphRef as HTMLDivElement).getBoundingClientRect();
    this.showLegend = false;
    this.showThumbnail = false;
    this.toolsPopoverInstance?.hide();
    this.canvasWidth = width;
    this.canvasHeight = height;
    // 修改画布大小
    this.graph.changeSize(width, height);
    // 将拓扑图移到画布中心
    this.graph.fitCenter();

    // 节点
    if (this.menuCfg.show) {
      const nodeTarget = this.graph.find('node', node => node.getModel().id === this.menuCfg.nodeModel.id);
      const { x, y } = nodeTarget.getModel(); // 获得该节点的位置，对应 pointX/pointY 坐标
      const canvasXY = this.graph.getCanvasByPoint(x, y);
      this.menuCfg.x = canvasXY.x;
      this.menuCfg.y = canvasXY.y;
    }
  }

  @Watch('data')
  handleDataChange() {
    this.initGraph();
  }

  @Watch('filterCondition', { deep: true })
  handleFilterConditionChange() {
    if (this.showType === 'topo') this.handleHighlightNode();
  }

  /**
   * @description: 定义节点 tooltip 内容
   * @param { HTMLElement } e
   */
  getTooltipsContent(e) {
    const outDiv = document.createElement('div');
    const { color, node_tips, data } = e.item.getModel();

    const {
      id,
      name,
      kind,
      extra_info: { language },
    } = data;

    const languageIcon = nodeLanguageMap[language] || '';

    const isService = kind === 'service';

    outDiv.innerHTML = `
        <h3 class='node-label'>
          <span class='label-mark' style='background-color: ${color}'></span>
          <div style="min-height:32px;">
            <div class='node-text'>${name || id}</div>
            <img
              class='language-icon'
              src='${languageIcon}'
              alt='${language}'
              style="display: ${languageIcon && isService ? '' : 'none'}" />
            <span class='language-name' style="display: ${!isService ? 'none' : ''}">${language}</span>
          </div>
        </h3>
        <ul class='node-message'>
          ${node_tips
            .map(
              tip =>
                `<li><div class='value'>${tip.value}</div><div style='color: rgba(0,0,0,0.60);'>${tip.name}</div></li>`
            )
            .join('')}
        </ul>
      `;
    return outDiv;
  }

  /** 节点菜单点击 */
  handleNodeMenuClick(menu: INodeModel['menu'][0]) {
    const { name, action = '', type, url } = menu;
    if (!action || !name) return;
    // 下钻
    if (action === 'span_drilling') {
      this.getNodeDrillingList(this.menuCfg.nodeModel.data.name);
      this.menuCfg.isDrilling = true;
      return;
    }

    if (action === 'resource_drilling') {
      // 资源拓扑
      this.$emit('resourceDrilling', this.menuCfg.nodeModel);
    }
    if (action === 'service_detail') {
      /** 服务概览 */
      this.$emit('serviceDetail', this.menuCfg.nodeModel);
    }
    if (type === 'link') {
      this.$router.push({
        path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${url}`.replace(/\/\//g, '/'),
      });
    }

    this.hideMenu();
  }

  handleDrillingNodeClick(name: string) {
    this.$emit('drillingNodeClick', this.menuCfg.nodeModel, name);
  }

  initGraph() {
    if (this.graph && !this.refreshTopoLayout) {
      this.graph.destroyLayout();
      this.graph.changeData(this.formatData);
      const activeNode = this.graph.findById(this.activeNode);
      if (activeNode) {
        activeNode.setState('active', true);
      }
    } else {
      if (this.graph) {
        this.graph.destroy();
        this.graph = null;
      }
      setTimeout(() => {
        const { width, height } = this.relationGraphRef.getBoundingClientRect();
        this.canvasWidth = width;
        this.canvasHeight = height - 6;
        // 自定义节点
        G6.registerNode(
          'apm-custom-node',
          {
            /**
             * 绘制节点，包含文本
             * @param  {Object} cfg 节点的配置项
             * @param  {G.Group} group 图形分组，节点中图形对象的容器
             * @return {G.Shape} 返回一个绘制的图形作为 keyShape，通过 node.get('keyShape') 可以获取。
             */
            draw: (cfg: INodeModelConfig, group: IGroup) => this.drawNode(cfg, group),
            update: undefined,
            /**
             * 设置节点的状态，主要是交互状态，业务状态请在 draw 方法中实现
             * 单图形的节点仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
             * @param  {String} name 状态名称
             * @param  {Object} value 状态值
             * @param  {Node} node 节点
             */
            setState: (name, value, item: INode) => this.setNodeState(name, value, item),
          },
          'circle'
        );
        // 自定义边
        G6.registerEdge(
          'apm-line-dash',
          {
            /**
             * 设置边的状态，主要是交互状态，业务状态请在 draw 方法中实现
             * 单图形的边仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
             * @param  {String} name 状态名称
             * @param  {Object} value 状态值
             * @param  {Edge} edge 边
             */
            setState: (name, value, item: IEdge) => this.setEdgeState(name, value, item),
          },
          'quadratic'
        );
        G6.registerEdge(
          'apm-loop-dash',
          {
            /**
             * 设置边的状态，主要是交互状态，业务状态请在 draw 方法中实现
             * 单图形的边仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
             * @param  {String} name 状态名称
             * @param  {Object} value 状态值
             * @param  {Edge} edge 边
             */
            setState: (name, value, item: IEdge) => this.setEdgeState(name, value, item),
          },
          'loop'
        );

        const minimap = new G6.Minimap({
          container: this.thumbnailToolRef,
          size: [236, 146],
        });
        const plugins = [minimap];
        this.graph = new G6.Graph({
          container: this.relationGraphRef as HTMLElement, // 指定挂载容器
          width: this.canvasWidth,
          height: this.canvasHeight,
          minZoom: this.minZoomVal, // 画布最小缩放比例
          maxZoom: this.maxZoomVal, // 画布最大缩放比例
          fitCenter: true, // 图的中心将对齐到画布中心
          fitView: true, // 将图适配到画布大小，可以防止超出画布或留白太多
          animate: false,
          groupByTypes: false,
          modes: {
            // 设置画布的交互模式
            default: [
              'drag-canvas', // 拖拽画布
              'zoom-canvas', // 缩放画布
              'drag-node', // 拖拽节点
            ],
          },
          /** 图布局 */
          layout: { ...this.graphLayout },
          defaultEdge: {
            // 边的配置
            type: 'apm-line-dash',
            labelCfg: {
              autoRotate: true,
              style: {
                fontSize: 10,
                color: '#63656E',
                background: {
                  fill: '#F0F1F5',
                  padding: [2, 4, 2, 4],
                  radius: 2,
                },
              },
            },
          },
          defaultNode: {
            // 节点配置
            type: 'apm-custom-node',
          },
          plugins,
        });
        this.bindListener(this.graph); // 图监听事件
        this.graph.read(this.formatData); // 读取数据源并渲染
      }, 30);
    }
  }

  drawNode(cfg: INodeModelConfig, group: IGroup) {
    const { size = 36, color, data } = cfg;
    const { type, category, name } = data;
    const [fillType, borderType] = type.split('_');

    // 是否为残影节点
    const isGhost = fillType === NodeDisplayType.VOID;
    // 是否为虚线节点
    const isDashed = borderType === NodeDisplayType.DASHED;

    group.addShape('circle', {
      attrs: {
        fill: '#EAEBF0',
        r: size,
        cursor: 'pointer',
      },
      name: 'custom-node-hover-circle',
    });

    // 节点基础结构
    const keyShape = group.addShape('circle', {
      attrs: {
        fill: '#fff', // 填充颜色,
        stroke: isGhost ? '#DCDEE5' : color, // 描边颜色
        lineWidth: isGhost ? 2 : 4, // 描边宽度
        r: size,
        cursor: 'pointer',
        lineDash: isDashed ? [4, 4] : [],
      },
      name: 'custom-node-keyShape',
    });

    group.addShape('circle', {
      attrs: {
        stroke: '#3A84FF', // 描边颜色
        lineWidth: 6, // 描边宽度
        r: size + 6,
        opacity: 0.2,
        cursor: 'pointer',
      },
      visible: false,
      name: 'custom-node-active-circle',
    });

    group.addShape('circle', {
      attrs: {
        stroke: '#3A84FF', // 描边颜色
        lineWidth: 6, // 描边宽度
        r: size + 12,
        opacity: 0.1,
        cursor: 'pointer',
      },
      visible: false,
      name: 'custom-node-active-circle',
    });

    if (category) {
      group.addShape('text', {
        attrs: {
          fontFamily: 'icon-monitor', // 对应css里面的font-family: "iconfont";
          textAlign: 'center',
          textBaseline: 'middle',
          fontSize: size >= 36 ? 24 : 16,
          text: nodeIconMap[category],
          fill: '#63656E',
          cursor: 'pointer',
          opacity: isGhost ? 0.4 : 1,
        },
        draggable: true,
        name: 'node-icon',
      });
    }

    // 节点label
    group.addShape('text', {
      attrs: {
        x: 0,
        y: 32,
        textAlign: 'center', // 文本内容的当前对齐方式
        text: name, //  文本内容
        fill: '#313238', // 填充颜色,
        fontSize: 12,
        fontWeight: 700,
        lineHeight: 12,
        cursor: 'pointer',
        opacity: isGhost ? 0.4 : 1,
      },
      draggable: true,
      name: 'text-shape',
    });

    return keyShape;
  }

  /**
   * 监听图表事件
   * @param graph
   */
  bindListener(graph: Graph) {
    graph.on('node:click', evt => {
      const { item } = evt;
      for (const node of graph.getNodes()) {
        node.setState('active', item._cfg.id === node._cfg.id);
      }
      const allEdges = this.graph.getEdges();
      const nodeEdges = (item as INode).getEdges();
      for (const edge of allEdges) {
        edge.setState('active', nodeEdges.includes(edge));
      }
      this.$emit('nodeClick', item.getModel());
    });

    graph.on('node:mouseenter', evt => {
      const { item } = evt;
      graph.setItemState(item, 'hover', true);
    });

    graph.on('node:mouseleave', evt => {
      const { item } = evt;
      graph.setItemState(item, 'hover', false);
    });

    graph.on('node:mousedown', evt => {
      const { originalEvent, canvasX, canvasY, item } = evt;
      if ((originalEvent as MouseEvent).button === 2) {
        for (const node of this.graph.getNodes()) {
          node.setState('active', item._cfg.id === node._cfg.id);
        }
        this.showMenu(canvasX, canvasY, item as INode);
      }
    });

    graph.on('wheelzoom', () => {
      this.scaleValue = this.graph.getZoom();
    });

    graph.on('afterrender', () => {
      this.isRender = true;
      const zoom = this.graph.getZoom();
      this.scaleValue = Number(zoom.toFixed(2));
      this.initScale = Number(zoom.toFixed(2));
      if (zoom >= 1) {
        this.graph.zoomTo(1);
        this.initScale = 1;
        this.scaleValue = 1;
      }
      const activeNode = this.graph.findById(this.activeNode);
      if (activeNode) {
        activeNode.setState('active', true);
      }
      this.handleHighlightNode();
    });
  }

  showMenu(x: number, y: number, item: INode) {
    this.menuCfg = {
      show: true,
      x,
      y,
      drillingLoading: true,
      nodeModel: item.getModel(),
      isDrilling: false,
      drillingList: [],
    };
    this.$nextTick(() => {
      const { width: graphWidth } = this.relationGraphRef.getBoundingClientRect();
      const { width, left } = this.menuListRef.getBoundingClientRect();
      // 超出画布宽度，则调整菜单位置
      if (width + left > graphWidth) {
        this.menuCfg.x = x - width;
      }
    });
    document.body.addEventListener('click', this.hideMenu);
  }

  hideMenu(e?: Event) {
    if (e && this.menuListRef.contains(e.target as HTMLElement)) return;
    this.menuCfg = {
      x: 0,
      y: 0,
      show: false,
      nodeModel: null,
      drillingLoading: true,
      isDrilling: false,
      drillingList: [],
    };
    document.body.removeEventListener('click', this.hideMenu);
  }

  /** 设置节点状态 */
  setNodeState(name: string, value: boolean | string, item: INode) {
    const group = item.get<IGroup>('group');
    const { size = 36, color = '#2DCB56' } = item.getModel() as INodeModelConfig;
    const hoverCircle = group.find(e => e.get('name') === 'custom-node-hover-circle');
    if (name === 'hover' && !item.hasState('active')) {
      const edges = item.getEdges();
      item.toBack();
      hoverCircle.stopAnimate();
      if (value) {
        hoverCircle.animate(
          radio => {
            return {
              r: size + radio * HoverCircleWidth,
            };
          },
          {
            duration: 300,
          }
        );
      } else {
        hoverCircle.animate(
          radio => {
            return {
              r: size + (1 - radio) * HoverCircleWidth,
            };
          },
          { duration: 300 }
        );
      }

      for (const edge of edges) {
        !edge.hasState('active') && this.edgeAnimate(edge, value as boolean);
      }
    }

    if (name === 'active') {
      const activeCircle = group.findAll(e => e.get('name') === 'custom-node-active-circle');
      hoverCircle.stopAnimate();
      hoverCircle.attr({
        r: size,
      });
      for (const shape of activeCircle) {
        value ? shape.show() : shape.hide();
      }
      if (value) {
        const allEdges = this.graph.getEdges();
        const nodeEdges = item.getEdges();
        for (const edge of allEdges) {
          edge.setState('active', nodeEdges.includes(edge));
        }
      }
    }

    if (name === 'no-select') {
      const textShape = group.find(e => e.get('name') === 'text-shape');
      const nodeIcon = group.find(e => e.get('name') === 'node-icon');
      const nodeKeyShape = group.find(e => e.get('name') === 'custom-node-keyShape');
      textShape.attr('opacity', value ? 0.4 : 1);
      nodeIcon.attr('opacity', value ? 0.4 : 1);
      nodeKeyShape.attr('stroke', value ? '#DCDEE5' : color);
      nodeKeyShape.attr('lineWidth', value ? 2 : 4);
    }
  }

  /** 设置边状态 */
  setEdgeState(name: string, value: boolean | string, item: IEdge) {
    const group = item.get('group');
    const keyShape: IShape = group.get('children')[0];

    if (name === 'active') {
      if (value) {
        this.edgeAnimate(item, true);
        // 设置边属性
        keyShape.attr({
          stroke: '#699DF4',
          endArrow: {
            path: G6.Arrow.triangle(10, 10, 0), // 线条路径 String | Array
            fill: '#699DF4', // 填充颜色
            stroke: '#699DF4', // 描边颜色
            strokeOpacity: 0, // 描边透明度
          },
        });
      } else {
        this.edgeAnimate(item, false);
        keyShape.attr({
          stroke: '#C4C6CC',
        });
        keyShape.attr('endArrow', {
          ...keyShape.attr('endArrow'),
          fill: '#C4C6CC', // 填充颜色
        });
      }
    }

    if (name === 'no-select') {
      keyShape.attr({
        opacity: value ? 0.4 : 1,
      });
    }
  }

  /** 边滑动动画 */
  edgeAnimate(edge: IEdge, start: boolean) {
    const group = edge.get('group');
    const keyShape: IShape = group.get('children')[0];
    if (start) {
      let index = 0; // 边 path 图形的动画
      // 设置边动画
      keyShape.animate(
        () => {
          index += 0.5;
          if (index > 8) index = 0;
          return { lineDash: [4, 4], lineDashOffset: -index };
        },
        {
          repeat: true,
          duration: 3000,
        }
      );
    } else {
      keyShape.stopAnimate();
      keyShape.attr({
        lineDashOffset: 0,
      });
    }
  }

  /** 下载图片 */
  handleDownloadImage() {
    if (!this.graph) return;
    const name = `${dayjs.tz().format('YYYY-MM-DD HH:mm:ss')}`;
    this.graph.downloadFullImage(name, 'image/png', {
      backgroundColor: '#fff',
      padding: 30,
    });
  }

  /** 缩放滑块切换 */
  handleScaleChange(ratio: number) {
    if (!this.graph) return;
    this.scaleValue = ratio;
    // 以画布中心为圆心放大/缩小
    this.graph.zoomTo(ratio);
    this.graph.fitCenter();
  }

  /**
   * 展示图例
   */
  handleShowLegend() {
    this.showLegend = !this.showLegend;
    this.showThumbnail = false;
    if (this.showLegend) {
      this.graphToolsRect = {
        width: 416,
        height: 237,
      };
      this.initToolsPopover(this.lastShowImage !== 'legend');
      this.lastShowImage = 'legend';
    } else {
      this.toolsPopoverInstance?.hide();
    }
  }

  /**
   * 展示缩略图
   */
  handleShowThumbnail() {
    if (!this.graph) return;
    this.showThumbnail = !this.showThumbnail;
    this.showLegend = false;
    if (this.showThumbnail) {
      this.graphToolsRect = {
        width: 240,
        height: 148,
      };
      this.initToolsPopover(this.lastShowImage !== 'thumbnail');
      this.lastShowImage = 'thumbnail';
    } else {
      this.toolsPopoverInstance?.hide();
    }
  }

  /**
   * 回中
   */
  handleResetCenter() {
    if (!this.graph) return;
    this.graph.fitCenter();
  }

  /**
   * 初始化工具栏弹窗
   */
  initToolsPopover(init = false) {
    if (!this.toolsPopoverInstance || init) {
      this.toolsPopoverInstance?.destroy?.();
      this.toolsPopoverInstance = null;
      this.toolsPopoverInstance = this.$bkPopover(this.topoToolsPanelRef, {
        content: this.topoToolsPopoverRef,
        arrow: false,
        trigger: 'manual',
        theme: 'light apm-topo-tools-popover',
        interactive: true,
        hideOnClick: false,
        placement: this.showLegend ? 'top-end' : 'top-start',
        appendTo: 'parent',
        zIndex: '1001',
      });
    }
    this.toolsPopoverInstance.show();
  }

  @Emit('edgeTypeChange')
  handleEdgeTypeChange(type: EdgeDataType) {
    return type;
  }

  handleLegendFilterChange(filter) {
    this.legendFilter = filter;
    this.handleHighlightNode();
  }

  /** 根据筛选条件高亮节点 */
  handleHighlightNode() {
    if (!this.graph) return;
    const { type, searchValue, showNoData } = this.filterCondition;
    const showAll = type === CategoryEnum.ALL;
    const targetNodes = []; // 所选分类节点
    const allEdges = []; // 所有边
    const allNodes = this.graph.getNodes(); // 所有节点
    for (const node of allNodes) {
      const { data, have_data, request_count, color } = node.getModel() as INodeModelConfig;
      const { category, name, id } = data;
      // 关键字搜索匹配
      const isKeywordMatch = name.toLowerCase().includes(searchValue.toLowerCase());
      // 是否展示无数据节点
      const isShowNoDataNode = showNoData || have_data;
      // 节点类型过滤
      const isCategoryFilter = showAll || category === type;
      // 节点请求数过滤
      let isSizeFilter = true;
      if (this.legendFilter.size) {
        switch (this.legendFilter.size) {
          case 'small':
            isSizeFilter = request_count < 200;
            break;
          case 'medium':
            isSizeFilter = request_count >= 200 && request_count < 1000;
            break;
          case 'large':
            isSizeFilter = request_count >= 1000;
            break;
        }
      }
      let isStatusFilter = true;
      // 节点颜色过滤
      if (this.legendFilter.status) {
        switch (this.legendFilter.status) {
          case 'success':
            isStatusFilter = color === '#2DCB56';
            break;
          case 'warning':
            isStatusFilter = color === '#FF9C01';
            break;
          case 'error':
            isStatusFilter = color === '#EA3636';
            break;
          case 'empty':
            isStatusFilter = color === '#DCDEE5';
            break;
        }
      }

      // 高亮当前分类的节点 根据分类、关键字搜索，节点类型匹配过滤
      const isDisabled = !isKeywordMatch || !isShowNoDataNode || !isCategoryFilter || !isSizeFilter || !isStatusFilter;
      this.graph.setItemState(node, 'no-select', isDisabled);
      // 保存高亮节点 用于设置关联边高亮
      if (!isDisabled) targetNodes.push(id);

      for (const edge of node.getEdges()) {
        if (!allEdges.includes(edge)) allEdges.push(edge);
      }
    }

    for (const edge of allEdges) {
      const edgeModel = edge.getModel();
      // source、target均是高亮节点的边
      const isRelated = [edgeModel.source, edgeModel.target].every(item => targetNodes.includes(item));
      this.graph.setItemState(edge, 'no-select', !isRelated);
    }
  }

  /** 节点下钻列表 */
  async getNodeDrillingList(nodeName) {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    this.menuCfg.isDrilling = true;
    this.menuCfg.drillingLoading = true;
    this.menuCfg.drillingList = await nodeEndpointsTop({
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime,
      node_name: nodeName,
      data_type: this.dataType,
    }).catch(() => []);
    this.menuCfg.drillingLoading = false;
  }

  reset() {
    this.showLegend = false;
    this.showThumbnail = false;
    this.toolsPopoverInstance?.hide();
  }

  render() {
    return (
      <div
        class='apm-relation-topo'
        onContextmenu={e => {
          e.stopPropagation();
          e.preventDefault();
        }}
      >
        <div
          ref='relationGraph'
          class='graph-wrap'
        />
        <div
          ref='topoToolsPanel'
          class='graph-tools-panel'
        >
          <CompareGraphTools
            maxScale={this.maxZoomVal}
            minScale={this.minZoomVal}
            originScaleValue={this.initScale}
            scaleValue={this.scaleValue}
            showLegend={this.showLegend}
            showThumbnail={this.showThumbnail}
            onDownloadImage={this.handleDownloadImage}
            onResetCenter={this.handleResetCenter}
            onScaleChange={this.handleScaleChange}
            onShowLegend={this.handleShowLegend}
            onShowThumbnail={this.handleShowThumbnail}
          />
          <div style='display: none;'>
            <div
              ref='topoToolsPopover'
              style={{
                'min-width': `${this.graphToolsRect.width}px`,
                'min-height': `${this.graphToolsRect.height}px`,
              }}
              class='topo-graph-content'
            >
              <div
                ref='thumbnailTool'
                style={{
                  display: this.showThumbnail ? 'block' : 'none',
                }}
                class='topo-graph-thumbnail'
              />

              <ApmTopoLegend
                style={{
                  display: this.showLegend ? 'block' : 'none',
                }}
                edgeType={this.edgeType}
                legendFilter={this.legendFilter}
                onEdgeTypeChange={this.handleEdgeTypeChange}
                onLegendFilterChange={this.handleLegendFilterChange}
              />
            </div>
          </div>
        </div>

        <div
          ref='menuList'
          style={{
            display: this.menuCfg.show ? 'block' : 'none',
            left: `${this.menuCfg.x}px`,
            top: `${this.menuCfg.y}px`,
          }}
          class='node-menu-list'
        >
          <div
            style={{ display: this.menuCfg.isDrilling ? 'block' : 'none' }}
            class='node-drilling-container'
          >
            <div class='header'>
              <span>{this.menuCfg.nodeModel?.data.name}</span>
              <div
                class='close-icon topo-menu-action'
                onClick={() => this.hideMenu()}
              >
                <div class='row-line' />
              </div>
            </div>
            {this.menuCfg.drillingLoading ? (
              <div
                class='drilling-loading'
                v-bkloading={{ isLoading: true, size: 'small', color: '#ecedf2' }}
              />
            ) : (
              <ul class='node-list'>
                {this.menuCfg.drillingList.map(item => (
                  <li
                    key={item.id}
                    class='node-item topo-menu-action'
                    onClick={() => this.handleDrillingNodeClick(item.name)}
                  >
                    <div
                      style={{ 'border-color': item.color }}
                      class='node'
                    >
                      <i class='icon-monitor icon-fx' />
                    </div>
                    <span class='node-text'>{item.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <ul
            style={{ display: this.menuCfg.isDrilling ? 'none' : 'block' }}
            class='topo-menu-list'
          >
            {this.menuCfg.nodeModel?.menu.map(target => (
              <li
                key={target.name}
                class='topo-menu-action'
                onClick={() => {
                  this.handleNodeMenuClick(target);
                }}
              >
                {target.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
