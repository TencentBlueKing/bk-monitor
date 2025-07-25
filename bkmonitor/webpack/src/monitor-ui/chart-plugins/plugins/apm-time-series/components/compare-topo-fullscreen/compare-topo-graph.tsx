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

import G6, { type Graph, type IEdge, type IGroup, type INode, type ModelConfig } from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';

import CompareGraphTools from './compare-graph-tools';

import './compare-topo-graph.scss';
type CompareTopoGraphEvent = {
  onNodeClick: (id: string) => void;
};

type CompareTopoGraphProps = {
  activeNode: string;
  data: any;
};

@Component
export default class CompareTopoGraph extends tsc<CompareTopoGraphProps, CompareTopoGraphEvent> {
  @Prop() data: any;
  @Prop() activeNode: string;
  @Ref('compareTopoGraph') compareTopoGraphRef: HTMLDivElement;
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

  get graphLayout() {
    return {
      type: 'radial',
      center: [this.canvasWidth / 2, this.canvasHeight / 2], // 布局的中心
      linkDistance: 400, // 边长度
      maxIteration: 1000, // 最大迭代次数
      preventOverlap: true, // 是否防止重叠
      nodeSize: 40, // 节点大小（直径）
      nodeSpacing: 500, // preventOverlap 为 true 时生效, 防止重叠时节点边缘间距的最小值
      maxPreventOverlapIteration: 1000, // 防止重叠步骤的最大迭代次数
      unitRadius: 200, // 每一圈距离上一圈的距离
      strictRadial: false, // 是否必须是严格的 radial 布局，及每一层的节点严格布局在一个环上。preventOverlap 为 true 时生效。
    };
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
    const { width, height } = (this.compareTopoGraphRef as HTMLDivElement).getBoundingClientRect();
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

  initGraph() {
    if (this.graph) {
      this.graph.destroy();
      this.graph = null;
    }
    setTimeout(() => {
      const { width, height } = this.compareTopoGraphRef.getBoundingClientRect();
      this.canvasWidth = width;
      this.canvasHeight = height - 6;
      // 自定义节点
      G6.registerNode(
        'compare-custom-node',
        {
          /**
           * 绘制节点，包含文本
           * @param  {Object} cfg 节点的配置项
           * @param  {G.Group} group 图形分组，节点中图形对象的容器
           * @return {G.Shape} 返回一个绘制的图形作为 keyShape，通过 node.get('keyShape') 可以获取。
           */
          draw: (cfg: ModelConfig, group: IGroup) => this.drawNode(cfg, group),
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
        'compare-line-dash',
        {
          /**
           * 绘制边，包含文本
           * @param  {Object} cfg 边的配置项
           * @param  {G.Group} group 图形分组，边中的图形对象的容器
           * @return {G.Shape} 绘制的图形，通过 node.get('keyShape') 可以获取到
           */
          draw: (cfg, group) => this.drawLine(cfg, group),
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
      const plugins = [minimap];
      this.graph = new G6.Graph({
        container: this.compareTopoGraphRef as HTMLElement, // 指定挂载容器
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
          type: 'compare-line-dash',
          style: {
            stroke: '#C4C6CC',
            lineWidth: 1,
            lineDash: [4, 4],
          },
        },
        defaultNode: {
          // 节点配置
          type: 'compare-custom-node',
        },
        plugins,
      });
      this.bindListener(this.graph); // 图监听事件
      this.graph.read(this.data); // 读取数据源并渲染
      this.graph.setItemState(this.activeNode, 'active', true);
      this.graph.setItemState(this.activeNode, 'active', true);
    }, 30);
  }

  drawNode(cfg: ModelConfig, group: IGroup) {
    // 节点基础结构
    group.addShape('circle', {
      attrs: {
        fill: '#fff', // 填充颜色,
        stroke: '#DCDEE5', // 描边颜色
        lineWidth: 2, // 描边宽度
        r: 35,
        cursor: 'pointer',
        lineDash: (cfg.lineDash as number[]) || [],
      },
      name: 'custom-node-keyShape',
    });

    group.addShape('circle', {
      attrs: {
        stroke: '#3A84FF', // 描边颜色
        lineWidth: 4, // 描边宽度
        r: 38,
        opacity: 0.2,
        cursor: 'pointer',
      },
      visible: cfg.id === this.activeNode,
      name: 'custom-node-active-circle',
    });

    group.addShape('circle', {
      attrs: {
        stroke: '#3A84FF', // 描边颜色
        lineWidth: 4, // 描边宽度
        r: 42,
        opacity: 0.1,
        cursor: 'pointer',
      },
      visible: cfg.id === this.activeNode,
      name: 'custom-node-active-circle',
    });

    const keyShape = group.addShape('circle', {
      zIndex: -1,
      attrs: {
        fill: '#EAEBF0',
        r: 36,
        cursor: 'pointer',
      },
      name: 'custom-node-hover-circle',
    });

    if (cfg.topoType === 'icon') {
      group.addShape('image', {
        attrs: {
          x: -12,
          y: -12,
          width: 24,
          height: 24,
          img: cfg.icon,
          cursor: 'pointer',
        },
        name: 'node-icon',
      });
    } else {
      // 对比值
      const compareValueText = group.addShape('text', {
        attrs: {
          x: 0,
          y: -3,
          text: (cfg.compareValue as number) >= 0 ? `+${cfg.compareValue}` : cfg.compareValue,
          fill: (cfg.compareValue as number) >= 0 ? '#EA3636' : '#00B02E', // 填充颜色,
          fontSize: 18,
          fontWeight: 700,
          lineHeight: 20,
          cursor: 'pointer',
        },
        name: 'compare-value',
      });
      const compareValueBox = compareValueText.getBBox();
      compareValueText.attr({
        x: -compareValueBox.width + 9.5,
      });
      group.addShape('text', {
        attrs: {
          x: 12,
          y: -4,
          text: '%',
          fill: (cfg.compareValue as number) >= 0 ? '#EA3636' : '#00B02E', // 填充颜色,
          fontSize: 12,
          lineHeight: 20,
          cursor: 'pointer',
        },
        name: 'compare-value-unit',
      });

      group.addShape('circle', {
        attrs: {
          x: -20,
          y: 10,
          fill: '#FF9C01',
          r: 3,
          cursor: 'pointer',
        },
      });

      group.addShape('text', {
        attrs: {
          x: -15,
          y: 17,
          text: cfg.number1,
          fill: '#63656E', // 填充颜色,
          fontSize: 12,
          lineHeight: 20,
          cursor: 'pointer',
        },
        name: 'value1',
      });

      group.addShape('circle', {
        attrs: {
          x: 7,
          y: 10,
          fill: '#7B29FF',
          r: 3,
          cursor: 'pointer',
        },
      });

      group.addShape('text', {
        attrs: {
          x: 12,
          y: 17,
          text: cfg.number2,
          fill: '#63656E', // 填充颜色,
          fontSize: 12,
          lineHeight: 20,
          cursor: 'pointer',
        },
        name: 'value2',
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
      },
      name: 'text-shape',
    });

    group.sort();

    return keyShape;
  }

  /**
   * 绘制边，包含文本
   * @param  {Object} cfg 边的配置项
   * @param  {G.Group} group 图形分组，边中的图形对象的容器
   * @return {G.Shape} 绘制的图形，通过 node.get('keyShape') 可以获取到
   */
  drawLine(cfg, group: IGroup) {
    const endArrow = {
      path: G6.Arrow.triangle(10, 10, -10), // 路径
      fill: '#C4C6CC', // 填充颜色
    };

    const keyShape = group.addShape('path', {
      attrs: {
        path: G6.Arrow.triangle(10, 10, -10), // 路径
        endArrow,
      },
      name: 'edge-shape',
    });

    return keyShape;
  }

  bindListener(graph: Graph) {
    graph.on('node:click', evt => {
      const { item } = evt;
      const { id } = item._cfg;
      for (const node of graph.getNodes()) {
        node.setState('active', item._cfg.id === node._cfg.id);
      }
      this.$emit('nodeClick', id);
    });

    graph.on('node:mouseenter', evt => {
      const { item } = evt;
      graph.setItemState(item, 'hover', true);
    });

    graph.on('node:mouseleave', evt => {
      const { item } = evt;
      graph.setItemState(item, 'hover', false);
    });
  }

  setNodeState(name: string, value: boolean | string, item: INode) {
    const group = item.get<IGroup>('group');
    const hoverCircle = group.find(e => e.get('name') === 'custom-node-hover-circle');
    if (name === 'hover' && !item.hasState('active')) {
      item.toBack();
      if (value) {
        hoverCircle.animate(
          radio => {
            return {
              r: 36 + radio * 8,
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
              r: 36 + (1 - radio) * 8,
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
        r: 36,
      });
      for (const shape of activeCircle) {
        value ? shape.show() : shape.hide();
      }
      if (value) {
        const allEdges = this.graph.getEdges();
        const relatedEdges = new Set(this.findAllNodeEdge(item, 'all'));
        for (const edge of allEdges) {
          edge.setState('active', relatedEdges.has(edge));
        }
      }
    }
  }

  setEdgeState(name: string, value: boolean | string, item: IEdge) {
    const group = item.get('group');
    if (name === 'active') {
      const keyShape = group.find(ele => ele.get('name') === 'edge-shape');
      if (value) {
        let index = 0; // 边 path 图形的动画
        // 设置边动画
        keyShape.animate(
          () => {
            index += 1;
            if (index > 8) index = 0;
            return { lineDashOffset: -index };
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
          endArrow: {
            path: G6.Arrow.triangle(10, 10, 0),
            fill: '#C4C6CC', // 填充颜色
          },
        });
      }
    }
  }

  /**
   * 找到节点上下游所有层级的边
   * @param node  节点
   * @Param direction 遍历方向
   * @returns  边
   */
  findAllNodeEdge(node: INode, direction: 'all' | 'down' | 'up') {
    const edges = [];
    if (direction !== 'down') {
      for (const edge of node.getInEdges()) {
        edges.push(edge);
        edges.push(...this.findAllNodeEdge(edge.getSource(), 'up'));
      }
    }
    if (direction !== 'up') {
      for (const edge of node.getOutEdges()) {
        edges.push(edge);
        edges.push(...this.findAllNodeEdge(edge.getTarget(), 'down'));
      }
    }

    return edges;
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
        width: 260,
        height: 128,
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
      <div class='compare-topo-graph'>
        <div
          ref='compareTopoGraph'
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
                <div class='left-legend'>
                  <div class='legend-item success'>{this.$t('正常')}</div>
                  <div class='legend-item warn'>{this.$t('错误率 < 10%')}</div>
                  <div class='legend-item error'>{this.$t('错误率 ≥ 10%')}</div>
                  <div class='legend-item empty'>{this.$t('无数据')}</div>
                </div>
                <div class='right-legend'>
                  <bk-radio-group>
                    <div class='legend-item'>
                      <bk-radio value='1'>0~200</bk-radio>
                    </div>
                    <div class='legend-item'>
                      <bk-radio value='2'>200~1k</bk-radio>
                    </div>
                    <div class='legend-item'>
                      <bk-radio value='3'>1k 以上</bk-radio>
                    </div>
                  </bk-radio-group>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
