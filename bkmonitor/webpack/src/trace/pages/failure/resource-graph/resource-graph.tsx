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
import { defineComponent, onMounted, ref } from 'vue';
import { Arrow, Graph, registerCombo, registerEdge, registerLayout, registerNode } from '@antv/g6';

import dbsvg from '../failure-topo/db.svg';
import httpSvg from '../failure-topo/http.svg';

import resourceData, { EdgeStatus, NodeStatus, StatusNodeMap } from './resource-data';

import './resource-graph.scss';

console.info('resourceData', resourceData);

export default defineComponent({
  name: 'ResourceGraph',
  props: {
    content: {
      type: String,
      default: ''
    }
  },
  setup() {
    const graphRef = ref<HTMLDivElement | null>(null);
    let graph: Graph;
    const registerCustomNode = () => {
      registerNode('resource-node', {
        afterDraw(cfg, group) {
          if (cfg.status === NodeStatus.Root) {
            group.addShape('circle', {
              zIndex: -11,
              attrs: {
                lineWidth: 2, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 22, // 圆半径
                stroke: 'rgba(58, 59, 61, 1)'
              },
              name: 'resource-node-running'
            });
            const circle2 = group.addShape('circle', {
              attrs: {
                lineWidth: 0, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 22, // 圆半径
                stroke: 'rgba(5, 122, 234, 1)'
              },
              name: 'resource-node-running'
            });
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -15,
                y: 12,
                width: 30,
                height: 16,
                radius: 8,
                fill: '#fff',
                ...StatusNodeMap[NodeStatus.Root]?.rectAttrs
              },
              name: 'resource-node-rect'
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 20,
                textAlign: 'center',
                textBaseline: 'middle',
                text: '根因',
                fontSize: 12,
                fill: '#fff',
                ...StatusNodeMap[NodeStatus.Root].textAttrs
              },
              name: 'resource-node-text'
            });
            circle2.animate(
              {
                lineWidth: 6,
                r: 24,
                strokeOpacity: 0.3
              },
              {
                repeat: true, // 循环
                duration: 3000,
                // easing: 'easeCubic',
                delay: 100 // 无延迟
              }
            );
          }
        },
        draw(cfg, group) {
          const { status, aggregateNode } = cfg as any;
          const nodeShape = group.addShape('circle', {
            zIndex: 10,
            attrs: {
              lineWidth: 1, // 描边宽度
              cursor: 'pointer', // 手势类型
              r: 20, // 圆半径
              ...StatusNodeMap[status].groupAttrs
            },
            name: 'resource-node-shape'
          });
          group.addShape('image', {
            attrs: {
              x: -12,
              y: -12,
              width: 24,
              height: 24,
              cursor: 'pointer', // 手势类型
              img: status === NodeStatus.Error ? dbsvg : httpSvg // 图片资源
            },
            name: 'resource-node-img'
          });
          if (aggregateNode?.length) {
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                x: -15,
                y: 12,
                width: 30,
                height: 16,
                radius: 8,
                fill: '#fff',
                ...StatusNodeMap[status]?.rectAttrs
              },
              name: 'resource-node-rect'
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: 0,
                y: 20,
                textAlign: 'center',
                textBaseline: 'middle',
                text: status === NodeStatus.Root ? '根因' : aggregateNode.length,
                fontSize: 12,
                fill: '#fff',
                ...StatusNodeMap[status].textAttrs
              },
              name: 'resource-node-text'
            });
          }
          return nodeShape;
        },
        setState(name, value, item) {
          const group = item.getContainer();
          const shape = group.get('children')[0]; // 顺序根据 draw 时确定
          if (name === 'hover') {
            // box-shadow: 0 2px 6px 0 rgba(0, 0, 0, 0.5);
            shape?.attr({
              shadowColor: value ? 'rgba(0, 0, 0, 0.5)' : false,
              shadowBlur: value ? 6 : false,
              shadowOffsetX: value ? 0 : false,
              shadowOffsetY: value ? 2 : false,
              strokeOpacity: value ? 0.6 : 1,
              cursor: 'pointer' // 手势类型
            });
          }
        }
      });
    };
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
            group.addShape('rect', {
              zIndex: 10,
              attrs: {
                width: 10,
                height: 10,
                fill: 'rgba(58, 59, 61, 1)',
                // x 和 y 分别减去 width / 2 与 height / 2，使矩形中心在 midPoint 上
                x: midPoint.x - 5,
                y: midPoint.y - 5,
                radius: 5
              }
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: midPoint.x,
                y: midPoint.y,
                textAlign: 'center',
                textBaseline: 'middle',
                text: cfg.count,
                fontSize: 12,
                fill: '#fff'
              },
              name: 'resource-node-text'
            });
          },
          update: undefined
        },
        'line'
      );
    };
    const registerCustomCombo = () => {
      registerCombo(
        'resource-combo',
        {
          labelPosition: 'left',
          labelAutoRotate: false,
          drawShape(cfg, group) {
            const keyShape = group.addShape('rect', {
              zIndex: 10,
              attrs: {
                fill: '#ddd',
                x: 0,
                y: 0
              },
              name: 'resource-combo-shape'
            });
            const w = graph.getWidth();
            const height = graph.getHeight();
            const comboxHeight = height / resourceData.combos.length;
            if (cfg.groupName) {
              group.addShape('text', {
                zIndex: 12,
                attrs: {
                  x: -w / 2 + 8,
                  y: -comboxHeight / 2,
                  textAlign: 'left',
                  text: cfg.groupName,
                  fontSize: 12,
                  fontWeight: 400,
                  fill: '#63656E'
                },
                name: 'resource-combo-title'
              });
            }
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: -w / 2 + 8,
                y: 0,
                textAlign: 'left',
                text: cfg.title,
                fontSize: 12,
                fontWeight: 700,
                fill: '#fff'
              },
              name: 'resource-combo-text'
            });
            group.addShape('text', {
              zIndex: 11,
              attrs: {
                x: -w / 2 + 8,
                y: 18,
                textAlign: 'left',
                text: cfg.subTitle,
                fontSize: 12,
                fontWeight: 700,
                fill: '#979BA5'
              },
              name: 'resource-combo-text'
            });
            group.addShape('rect', {
              zIndex: 2,
              attrs: {
                x: -w / 2 + 80,
                y: -comboxHeight / 2 - 26,
                width: 2,
                height: comboxHeight + 40,
                fill: 'rgba(0, 0, 0, 0.3)'
              },
              name: 'resource-combo-bg'
            });
            return keyShape;
          }
        },
        'rect'
      );
    };
    const registerCustomLayout = () => {
      registerLayout('resource-layout', {
        execute() {
          console.info('execute', this);
          const { nodes, combos } = this;
          const nodeBegin = 80;
          const width = graph.getWidth() - nodeBegin - 100;
          const height = graph.getHeight();
          const comboxHeight = height / combos.length;
          const nodeSize = 46;
          combos.forEach((combo, comboIndex) => {
            const comboNodes = nodes.filter(node => node.comboId.toString() === combo.id.toString());
            const xBegin = nodeBegin + nodeSize / 2;
            const yBegin = comboxHeight / 2 + comboIndex * comboxHeight;
            const nodeStep = width / comboNodes.length;
            comboNodes.forEach((node, index) => {
              node.x = xBegin + index * nodeStep;
              node.y = yBegin;
            });
          });
        }
      });
    };
    onMounted(() => {
      const { width, height } = graphRef.value.getBoundingClientRect();
      console.info('width', width, height);
      registerCustomNode();
      registerCustomEdge();
      registerCustomCombo();
      registerCustomLayout();
      graph = new Graph({
        container: graphRef.value,
        width,
        height,
        fitView: false,
        fitViewPadding: 0,
        groupByTypes: false,
        layout: {
          type: 'resource-layout'
        },
        defaultNode: {
          type: 'circle',
          size: 40
        },
        defaultEdge: {
          size: 1,
          color: '#63656D'
        },
        defaultCombo: {
          // type: 'rect',
          type: 'resource-combo',
          style: {
            fill: '#292A2B',
            radius: 0,
            lineWidth: 0
          }
        },
        modes: {
          default: []
        }
      });
      graph.node(node => {
        return {
          ...node,
          type: 'resource-node'
        };
      });
      graph.edge((cfg: any) => {
        const isInvoke = cfg.type === EdgeStatus.Invoke;
        const edg = {
          ...cfg,
          style: {
            endArrow:
              cfg.type === EdgeStatus.Invoke
                ? {
                    path: Arrow.triangle(),
                    d: 0,
                    fill: '#F55555',
                    stroke: '#F55555',
                    lineDash: [0, 0]
                  }
                : false,
            fill: isInvoke ? '#F55555' : '#63656E',
            stroke: isInvoke ? '#F55555' : '#63656E',
            lineWidth: isInvoke ? 2 : 1,
            lineDash: isInvoke ? [4, 2] : false
          }
        };
        if (!cfg.color) return edg;
        return {
          ...edg,
          type: 'resource-edge'
        };
      });
      graph.combo(combo => {
        return {
          ...combo,
          type: 'resource-combo'
        };
      });
      graph.on('afterlayout', () => {
        const combos = graph.getCombos();
        const groups = Array.from(new Set(combos.map(combo => combo.get('model').groupId)));
        combos.forEach(combo => {
          // 获取 Combo 中包含的节点和边的范围
          const bbox = combo.getBBox();
          const height = graph.getHeight();
          const comboxHeight = height / combos.length;
          const h = bbox.maxY - bbox.minY;
          const w = graph.getWidth();
          const fillColor = groups.findIndex(id => id === combo.get('model').groupId) % 2 === 1 ? '#292A2B' : '#1B1C1F';
          graph.updateItem(combo, {
            size: [w, Math.max(comboxHeight, h)],
            x: w / 2,
            style: {
              fill: fillColor,
              stroke: fillColor
            }
          });
        });
      });
      graph.data(resourceData);
      graph.render();
    });
    return {
      graphRef,
      graph
    };
  },
  render() {
    return (
      <div class='resource-graph'>
        <div
          ref='graphRef'
          class='graph-wrapper'
        />
      </div>
    );
  }
});
