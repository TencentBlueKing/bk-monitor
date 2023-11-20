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
import { Arrow, Graph, registerEdge, registerLayout, registerNode } from '@antv/g6';

import dbsvg from './db.svg';
import httpSvg from './http.svg';
import topoData, { EdgeStatus, NodeStatus } from './topo-data';
import TopoTools from './topo-tools';

import './failure-topo.scss';

const StatusNodeMap = {
  [NodeStatus.Normal]: {
    groupAttrs: {
      fill: 'rgba(197, 197, 197, 0.2)',
      stroke: '#979BA5'
    },
    rectAttrs: {
      stroke: '#EAEBF0',
      fill: '#313238'
    },
    textAttrs: {
      fill: '#fff'
    }
  },
  [NodeStatus.Error]: {
    groupAttrs: {
      fill: 'rgba(255, 102, 102, 0.4)',
      stroke: '#F55555'
    },
    rectAttrs: {
      stroke: '#F55555',
      fill: '#313238'
    },
    textErrorAttrs: {
      fill: '#313238'
    },
    textNormalAttrs: {
      fill: '#fff'
    }
  },
  [NodeStatus.Root]: {
    groupAttrs: {
      fill: '#F55555',
      stroke: '#F55555'
    },
    rectAttrs: {
      stroke: '#3A3B3D',
      fill: '#F55555'
    },
    textAttrs: {
      fill: '#fff'
    }
  }
};
export default defineComponent({
  name: 'FailureTopo',
  props: {
    content: {
      type: String,
      default: ''
    }
  },
  setup() {
    const topoGraphRef = ref<HTMLDivElement>(null);
    const registerCustomNode = () => {
      registerNode('topo-node', {
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
              name: 'topo-node-running'
            });
            const circle2 = group.addShape('circle', {
              attrs: {
                lineWidth: 0, // 描边宽度
                cursor: 'pointer', // 手势类型
                r: 22, // 圆半径
                stroke: 'rgba(5, 122, 234, 1)'
              },
              name: 'topo-node-running'
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
              name: 'topo-node-rect'
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
              name: 'topo-node-text'
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
            name: 'topo-node-shape'
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
            name: 'topo-node-img'
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
              name: 'topo-node-rect'
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
              name: 'topo-node-text'
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
        'topo-edge',
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
              name: 'topo-node-text'
            });
          },
          update: undefined
        },
        'line'
      );
    };
    const registerCustomLayout = () => {
      registerLayout('topo-layout', {
        execute() {
          console.info('execute', this);
          const { nodes, edges, combos, width } = this;
          const begin = 60;
          const indexStep = Math.ceil(width / 500);
          const comboMargin = 40;
          const nodeMargin = 40;
          const nodeSize = 30;
          console.info(nodes, edges, combos);
          combos.forEach((combo, comboIndex) => {
            const comboNodes = nodes.filter(node => node.comboId === combo.id);
            comboNodes.forEach((node, index) => {
              node.x = (comboIndex % indexStep) * 400 + index * (nodeMargin + nodeSize) + begin;
              node.y = Math.floor(comboIndex / indexStep) * 200 + begin;
            });
            // combo.ch;
            // combo.x = index * 400 + 20;
            // combo.y = Math.floor(index / 2) * 200 + 20;
          });
        }
      });
    };
    onMounted(() => {
      const { width, height } = topoGraphRef.value.getBoundingClientRect();
      registerCustomLayout();
      registerCustomNode();
      registerCustomEdge();
      const graph = new Graph({
        container: 'topo-graph',
        width,
        height: Math.max(160 * topoData.combos.length, height),
        // fitView: [20, 20] as any,
        // fitView: true,
        fitViewPadding: 16,
        minZoom: 0.00000001,
        groupByTypes: false,
        layout: {
          // type: 'comboForce',
          // maxIteration: 1000,
          // nodeSpacing: () => 3,
          // // preventOverlap: true,
          // // collideStrength: 1,
          // comboSpacing: () => 100,
          // preventComboOverlap: true,
          // preventNodeOverlap: true,

          // // center: [ 0, 0 ],     // 可选，默认为图的中心
          // // linkDistance: 1050,         // 可选，边长
          // // nodeStrength: 30,         // 可选
          // edgeStrength: 0.1,        // 可选

          // // gravity: 0.1,
          // // comboGravity: 0.1,
          // // workerEnabled: true,
          // gpuEnabled: true,
          // type: 'grid',

          // type: 'dagre',
          type: 'topo-layout'
          // rankdir: 'LR',
          // align: 'UL',
          // nodesep: 10,
          // ranksep: 10,
          // sortByCombo: true
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
          type: 'rect',
          style: {
            fill: '#3A3B3D',
            radius: 6,
            stroke: '#3A3B3D'
          },
          // size: [200, 100],
          labelCfg: {
            style: {
              fill: '#979BA5',
              fontSize: 12
            }
          }
        },
        modes: {
          default: ['drag-combo', 'drag-node', 'drag-canvas', 'zoom-canvas']
        }
      });
      graph.node(node => {
        return {
          ...node,
          type: 'topo-node'
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
          type: 'topo-edge'
        };
      });
      graph.data(topoData);
      graph.render();
      // setTimeout(() => {
      //   // topoData.nodes.forEach((node, index) => {
      //   //   node.x += Math.random() * 50 - 25;
      //   //   node.y += Math.random() * 50 - 25;
      //   // })
      //   topoData.combos.forEach((node, index) => {
      //     node.x += Math.random() * 50 - 25;
      //     node.y += Math.random() * 50 - 25;
      //   });
      //   graph.updateCombos();
      //   graph.changeData(topoData);
      // }, 2000);
      // graph.combo(combo => {
      //   const { id } = combo;
      //   const nodes = graph.findAll('node', node => {
      //    return node.getModel().comboId === id
      //   })
      //   console.info(nodes, '--------')
      //   // const nodes = combo.;
      // })
      graph.on('node:mouseenter', e => {
        const nodeItem = e.item;
        graph.setItemState(nodeItem, 'hover', true);
      });
      // 监听鼠标离开节点
      graph.on('node:mouseleave', e => {
        const nodeItem = e.item;
        graph.setItemState(nodeItem, 'hover', false);
        graph.setItemState(nodeItem, 'running', false);
      });
      graph.on('node:click', e => {
        const nodeItem = e.item;
        const { status, aggregateNode } = nodeItem.getModel() as any;
        if (status === NodeStatus.Root) {
          graph.setItemState(nodeItem, 'running', true);
          return;
        }
      });
    });

    return {
      topoGraphRef
    };
  },
  render() {
    return (
      <div class='failure-topo'>
        <TopoTools />
        <div
          class='topo-graph-wrapper'
          ref='topoGraphRef'
        >
          <div
            class='topo-graph'
            id='topo-graph'
          />
        </div>
      </div>
    );
  }
});
