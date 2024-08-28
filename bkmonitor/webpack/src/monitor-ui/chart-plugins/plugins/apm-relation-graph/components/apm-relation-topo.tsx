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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import G6, { type IGroup, type ModelConfig, type Graph, type INode, type IEdge, type IShape } from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';

import CompareGraphTools from '../../apm-time-series/components/compare-topo-fullscreen/compare-graph-tools';

import './apm-relation-topo.scss';
type ApmRelationTopoProps = {
  data: any;
  activeNode: string[];
  scene: string;
};

type ApmRelationTopoEvent = {
  onNodeClick: (id: string) => void;
};

interface INodeModelConfig extends ModelConfig {
  lineDash?: number[];
  stroke?: string;
  size?: number;
  disabled?: boolean;
}

interface IEdgeModelConfig extends ModelConfig {
  lineWidth?: number;
  stroke?: string;
  lineDash: number[];
}

// 节点hover阴影宽度
const HoverCircleWidth = 13;

const LIMIT_RADIAL_LAYOUT_COUNT = 700;
const LIMIT_WORKER_ENABLED = 500;

@Component
export default class ApmRelationTopo extends tsc<ApmRelationTopoProps, ApmRelationTopoEvent> {
  @Prop() data: any;
  @Prop() activeNode: string[];
  @Prop() scene: string;
  @Ref('relationGraph') relationGraphRef: HTMLDivElement;
  @Ref('graphToolsPanel') graphToolsPanelRef: HTMLDivElement;
  @Ref('topoGraphContent') topoGraphContentRef: HTMLDivElement;
  @Ref('thumbnailTool') thumbnailToolRef: HTMLDivElement;

  canvasWidth = 0; // 画布宽度
  canvasHeight = 0; // 画布高度
  minZoomVal = 0.1; // 缩放滑动条最小值
  maxZoomVal = 1; // 缩放滑动条最大值
  graph: Graph = null; // 拓扑图实例
  toolsPopoverInstance = null; // 工具栏弹窗实例

  /** 图表缩放大小 */
  scaleValue = 100;
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

  legendFilter = {
    nodeColor: [
      { color: '#2DCB56', label: '正常', id: 'success' },
      { color: '#FF9C01', label: '错误率 < 10%', id: 'warning' },
      { color: '#EA3636', label: '错误率 ≥ 10%', id: 'error' },
      { color: '#DCDEE5', label: '无数据', id: 'empty' },
    ],
    nodeSize: [
      {
        id: 'small',
        label: '请求数 0~200',
      },
      {
        id: 'medium',
        label: '请求数 200~1k',
      },
      {
        id: 'large',
        label: '请求数 1k 以上',
      },
    ],
    durationList: [
      { id: 'average', label: '平均耗时' },
      { id: 'p99', label: 'P99 耗时' },
      { id: 'p95', label: 'P95 耗时' },
    ],
  };

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

  beforeDestroy() {
    this.toolsPopoverInstance?.destroy?.();
    this.toolsPopoverInstance = null;
    removeListener(this.$el as HTMLDivElement, this.handleResize);
  }

  mounted() {
    addListener(this.$el as HTMLDivElement, this.handleResize);
  }

  handleResize() {
    if (!this.graph || this.graph.get('destroyed')) return;
    const { width, height } = (this.relationGraphRef as HTMLDivElement).getBoundingClientRect();
    this.canvasWidth = width;
    this.canvasHeight = height;
    // 修改画布大小
    this.graph.changeSize(width, height);
    // 将拓扑图移到画布中心
    this.graph.fitCenter();
  }

  @Watch('data')
  handleDataChange() {
    this.initGraph();
  }

  // 节点菜单
  contextMenu() {
    return new G6.Menu({
      className: 'node-menu-container',
      trigger: 'contextmenu',
      // 是否阻止行为发生
      shouldBegin(evt) {
        if (evt.item) return true;
        return false;
      },
      // 菜单项内容
      getContent(evt) {
        const { item } = evt;
        if (!item) return;
        const itemType = item.getType();
        const model = item.getModel() as any;
        if (itemType && model) {
          return `<ul>
            ${model.menu
              .map(
                target =>
                  `<li id='${JSON.stringify(target)}'>
                    <span class="icon-monitor node-menu-icon ${target.icon}"></span>
                    ${target.name}
                   </li>`
              )
              .join('')}
            </ul>`;
        }
      },
      handleMenuClick: (target, item) => this.handleNodeMenuClick(target, item),
      // 在哪些类型的元素上响应 node：节点 | canvas：画布
      itemTypes: ['node'],
    });
  }

  handleNodeMenuClick(target, item) {
    console.log(target, item);
  }

  initGraph() {
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
           * 绘制边，包含文本
           * @param  {Object} cfg 边的配置项
           * @param  {G.Group} group 图形分组，边中的图形对象的容器
           * @return {G.Shape} 绘制的图形，通过 node.get('keyShape') 可以获取到
           */
          afterDraw: (cfg: IEdgeModelConfig, group) => this.afterDrawLine(cfg, group),
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

      const minimap = new G6.Minimap({
        container: this.thumbnailToolRef,
        size: [236, 146],
      });
      const plugins = [
        minimap,
        this.contextMenu(), // 节点菜单
      ];
      this.graph = new G6.Graph({
        container: this.relationGraphRef as HTMLElement, // 指定挂载容器
        width: this.canvasWidth,
        height: this.canvasHeight,
        minZoom: this.minZoomVal, // 画布最小缩放比例
        maxZoom: this.maxZoomVal, // 画布最大缩放比例
        fitCenter: true, // 图的中心将对齐到画布中心
        animate: false,
        groupByTypes: false,
        modes: {
          // 设置画布的交互模式
          default: [
            'drag-canvas', // 拖拽画布
            'zoom-canvas', // 缩放画布
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
      this.graph.read(this.data); // 读取数据源并渲染
      const nodes = this.graph.findAll('node', node => this.activeNode.includes(node.getID()));
      const activeEdge: IEdge[] = nodes.reduce((pre, node: INode) => {
        node.setState('active', true);
        pre.push(...node.getEdges());
        return pre;
      }, []);
      for (const edge of activeEdge) {
        edge.setState('active', true);
      }
    }, 30);
  }

  drawNode(cfg: INodeModelConfig, group: IGroup) {
    const { size = 36, disabled } = cfg;

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
        stroke: disabled ? '#DCDEE5' : cfg.stroke || '#2DCB56', // 描边颜色
        lineWidth: disabled ? 2 : 4, // 描边宽度
        r: size,
        cursor: 'pointer',
        lineDash: cfg.lineDash || [],
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

    if (cfg.icon) {
      group.addShape('image', {
        attrs: {
          x: -12,
          y: -12,
          width: 24,
          height: 24,
          img: cfg.icon,
          cursor: 'pointer',
          opacity: disabled ? 0.4 : 1,
        },
        name: 'node-icon',
      });
    }

    // 节点label
    group.addShape('text', {
      attrs: {
        x: 0,
        y: 32,
        textAlign: 'center', // 文本内容的当前对齐方式
        text: cfg.name, //  文本内容
        fill: '#313238', // 填充颜色,
        fontSize: 12,
        fontWeight: 700,
        lineHeight: 12,
        cursor: 'pointer',
        opacity: disabled ? 0.4 : 1,
      },
      name: 'text-shape',
    });

    return keyShape;
  }

  afterDrawLine(cfg: IEdgeModelConfig, group: IGroup) {
    const { lineWidth = 1, stroke = '#C4C6CC', lineDash = [4, 4] } = cfg;
    const endArrow = {
      path: G6.Arrow.triangle(10, 10, 0), // 路径
      fill: '#C4C6CC', // 填充颜色
    };
    const shape: IShape = group.get('children')[0];

    shape.attr({
      lineWidth,
      stroke,
      lineDash,
      endArrow,
    });
  }

  bindListener(graph: Graph) {
    graph.on('node:click', evt => {
      const { item } = evt;
      const { id, model } = item._cfg;
      if (model.disabled) return;
      for (const node of graph.getNodes()) {
        node.setState('active', item._cfg.id === node._cfg.id);
      }
      const allEdges = this.graph.getEdges();
      const nodeEdges = (item as INode).getEdges();
      for (const edge of allEdges) {
        edge.setState('active', nodeEdges.includes(edge));
      }
      this.$emit('nodeClick', id);
    });

    graph.on('node:mouseenter', evt => {
      const { item } = evt;
      const { model } = item._cfg;
      if (model.disabled) return;
      graph.setItemState(item, 'hover', true);
    });

    graph.on('node:mouseleave', evt => {
      const { item } = evt;
      const { model } = item._cfg;
      if (model.disabled) return;
      graph.setItemState(item, 'hover', false);
    });
  }

  setNodeState(name: string, value: boolean | string, item: INode) {
    const group = item.get<IGroup>('group');
    const { size = 36, stroke = '#2DCB56' } = item.getModel() as INodeModelConfig;
    const hoverCircle = group.find(e => e.get('name') === 'custom-node-hover-circle');
    if (name === 'hover' && !item.hasState('active')) {
      item.toBack();
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
    }

    if (name === 'disabled') {
      const textShape = group.find(e => e.get('name') === 'text-shape');
      const nodeIcon = group.find(e => e.get('name') === 'node-icon');
      const nodeKeyShape = group.find(e => e.get('name') === 'custom-node-keyShape');
      textShape.attr({
        opacity: value ? 0.4 : 1,
      });
      nodeIcon.attr({
        opacity: value ? 0.4 : 1,
      });
      nodeKeyShape.attr({
        stroke: value ? '#DCDEE5' : stroke,
        lineWidth: value ? 2 : 4,
      });
    }
  }

  setEdgeState(name: string, value: boolean | string, item: IEdge) {
    const group = item.get('group');
    const keyShape: IShape = group.get('children')[0];

    if (name === 'active') {
      if (value) {
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
        keyShape.stopAnimate();
        keyShape.attr({
          stroke: '#C4C6CC',
          lineDashOffset: 0,
        });
        keyShape.attr('endArrow', {
          ...keyShape.attr('endArrow'),
          fill: '#C4C6CC', // 填充颜色
        });
      }
    }
  }

  handleDownloadImage() {
    if (!this.graph) return;
    const name = `${dayjs.tz().format('YYYY-MM-DD HH:mm:ss')}`;
    this.graph.downloadFullImage(name, 'image/png', {
      backgroundColor: '#fff',
      padding: 30,
    });
  }

  handleScaleChange(ratio: number) {
    if (!this.graph) return;
    this.scaleValue = ratio;
    // 以画布中心为圆心放大/缩小
    this.graph.zoomTo(ratio / 100);
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
      this.initToolsPopover();
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
    if (this.showThumbnail) {
      this.graphToolsRect = {
        width: 240,
        height: 148,
      };
      this.initToolsPopover();
    } else {
      this.toolsPopoverInstance?.hide();
    }
    this.showLegend = false;
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
  initToolsPopover() {
    if (!this.toolsPopoverInstance) {
      this.toolsPopoverInstance = this.$bkPopover(this.graphToolsPanelRef, {
        content: this.topoGraphContentRef,
        arrow: false,
        trigger: 'manual',
        theme: 'light',
        interactive: true,
        hideOnClick: false,
        placement: 'top-start',
      });
    }
    this.toolsPopoverInstance.show();
  }

  reset() {
    this.showLegend = false;
    this.showThumbnail = false;
    this.toolsPopoverInstance?.hide();
  }

  render() {
    return (
      <div class='apm-relation-topo'>
        <div
          ref='relationGraph'
          class='graph-wrap'
        />
        <div
          ref='graphToolsPanel'
          class='graph-tools-panel'
        >
          <CompareGraphTools
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
              ref='topoGraphContent'
              style={{
                width: `${this.graphToolsRect.width}px`,
                height: `${this.graphToolsRect.height}px`,
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

              <div
                style={{
                  display: this.showLegend ? 'block' : 'none',
                }}
                class='topo-graph-legend'
              >
                <div class='filter-category'>
                  <div class='filter-title'>{this.$t('节点颜色')}</div>
                  <div class='filter-list node-color'>
                    {this.legendFilter.nodeColor.map(item => (
                      <div
                        key={item.id}
                        class='color-item'
                      >
                        <div
                          style={{
                            background: item.color,
                          }}
                          class='color-mark'
                        />
                        {item.label}
                      </div>
                    ))}
                  </div>
                </div>
                <div class='filter-category'>
                  <div class='filter-title'>{this.$t('节点大小')}</div>
                  <div class='filter-list node-size'>
                    {this.legendFilter.nodeSize.map(item => (
                      <div
                        key={item.id}
                        class='node-item'
                      >
                        <div class='radio' />
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div class='filter-category'>
                  <div class='filter-title line'>
                    {this.$t('连接线')}
                    <div class='line-type'>
                      <div class={{ active: this.scene === 'request' }}>{this.$t('请求量')}</div>
                      <div class={{ active: this.scene === 'duration' }}>{this.$t('耗时')}</div>
                    </div>
                  </div>
                  <div class='filter-list connect-line'>
                    {this.scene === 'request'
                      ? [
                          <div
                            key='1'
                            class='request-item'
                          >
                            <div class='flow-block'>
                              {new Array(10).fill(null).map((_, index) => (
                                <div
                                  key={index}
                                  class='seldom'
                                />
                              ))}
                            </div>
                            {this.$t('请求量少')}
                          </div>,
                          <div
                            key='2'
                            class='request-item'
                          >
                            <div class='flow-block'>
                              {new Array(7).fill(null).map((_, index) => (
                                <div
                                  key={index}
                                  class='many'
                                />
                              ))}
                            </div>
                            {this.$t('请求量多')}
                          </div>,
                        ]
                      : this.legendFilter.durationList.map(item => (
                          <div
                            key={item.id}
                            class='duration-item'
                          >
                            <div class='radio' />
                            <span>{item.label}</span>
                          </div>
                        ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
