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

import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import { VueFlow, useVueFlow } from '@vue-flow/core';

import { useLayout } from '../../hooks/vue-flow-use-layout';
import { useTraceStore } from '../../store/modules/trace';

import './service-topo.scss';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';

enum ENodeType {
  component = 'component',
  interface = 'interface',
  service = 'service',
}

export default defineComponent({
  name: 'ServiceTopo',
  setup() {
    // hooks
    const store = useTraceStore();
    const { fitView, setViewport } = useVueFlow();
    const { layout } = useLayout();

    // dom
    const graphContainer = ref<Element>();

    // data
    const emptyText = ref<string>('加载中...');
    const empty = ref<boolean>(false);
    const serviceTopoData = computed(() => store.traceData.streamline_service_topo);

    const nodes = ref([]);
    const edges = ref([]);

    watch(
      () => serviceTopoData.value,
      data => {
        nodes.value = data.nodes.map(item => ({
          id: item.key,
          type: item.node_type,
          position: { x: 0, y: 0 },
          data: {
            ...item,
          },
        }));
        edges.value = data.edges.map(item => ({
          id: item.key,
          source: item.source,
          target: item.target,
        }));
      },
      { immediate: true }
    );

    /**
     * @description 自动布局节点位置
     * @param direction
     */
    function layoutGraph(direction: string) {
      nodes.value = layout(nodes.value, edges.value, direction);
      nextTick(() => {
        fitView();
        const wrapWidth = graphContainer.value.clientWidth;
        const positionXs = nodes.value.map(item => item.position.x);
        const positionXSort = positionXs.sort((a, b) => a - b);
        const x =
          wrapWidth / 2 -
          ((positionXSort[positionXSort.length - 1] - positionXSort[0]) / 2 + positionXSort[0]) +
          positionXSort[0] -
          32;
        setViewport({
          zoom: 1,
          x: x,
          y: 16,
        });
      });
    }

    return {
      emptyText,
      empty,
      graphContainer,
      nodes,
      edges,
      layoutGraph,
    };
  },

  render() {
    return (
      <div class='service-topo-component'>
        {this.empty && <div class='empty-chart'>{this.emptyText}</div>}
        <div
          ref='graphContainer'
          class='graph-container'
        >
          <VueFlow
            edges={this.edges}
            nodes={this.nodes}
            onNodesInitialized={() => this.layoutGraph('TB')}
          >
            {(() => ({
              [`node-${ENodeType.interface}`]: data => (
                <div
                  style={{
                    borderLeftColor: data.data.color,
                  }}
                  class='node-interface'
                >
                  <img
                    class='node-interface-icon'
                    src={data.data.icon}
                  />
                  <div class='node-interface-name'>{data.data.display_name}</div>
                </div>
              ),
              [`node-${ENodeType.service}`]: data => (
                <div class='node-service'>
                  <div class='node-service-top'>
                    <img src={data.data.icon}></img>
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
              [`node-${ENodeType.component}`]: data => (
                <div class='node-service'>
                  <div class='node-service-top'>
                    <img src={data.data.icon}></img>
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
            }))()}
          </VueFlow>
        </div>
      </div>
    );
  },
});
