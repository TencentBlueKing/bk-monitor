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

import { computed, defineComponent, ref } from 'vue';

import { VueFlow } from '@vue-flow/core';

import { useTraceStore } from '../../store/modules/trace';

import './service-topo.scss';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';

export default defineComponent({
  name: 'ServiceTopo',
  setup() {
    const store = useTraceStore();

    const emptyText = ref<string>('加载中...');
    const empty = ref<boolean>(false);
    const graphContainer = ref<Element>();
    const traceData = computed(() => store.traceData);

    const nodes = computed(() => [
      {
        id: '1',
        type: 'input',
        position: { x: 250, y: 5 },
        data: { label: 'Node 1' },
      },
      {
        id: '2',
        position: { x: 100, y: 100 },
        data: { label: 'Node 2' },
      },
      {
        id: '3',
        type: 'output',
        position: { x: 400, y: 200 },
        data: { label: 'Node 3' },
      },
      {
        id: '4',
        type: 'special', // <-- this is the custom node type name
        position: { x: 400, y: 200 },
        data: {
          label: 'Node 4',
          hello: 'world',
        },
      },
    ]);
    const edges = ref([
      {
        id: 'e1->2',
        source: '1',
        target: '2',
      },
      {
        id: 'e2->3',
        source: '2',
        target: '3',
        animated: true,
      },
      {
        id: 'e3->4',
        type: 'special',
        source: '3',
        target: '4',
        data: {
          hello: 'world',
        },
      },
    ]);

    return {
      emptyText,
      empty,
      graphContainer,
      traceData,
      nodes,
      edges,
    };
  },

  render() {
    return (
      <div class='service-topo-component'>
        {this.empty && <div class='empty-chart'>{this.emptyText}</div>}
        <div class='graph-container'>
          <VueFlow
            edges={this.edges}
            nodes={this.nodes}
          >
            {{
              'node-input': () => <div>asdfasdf</div>,
            }}
          </VueFlow>
        </div>
      </div>
    );
  },
});
