/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, nextTick, ref, watch } from 'vue';
import { UseTopoChart } from 'monitor-ui/chart-plugins/plugins/profiling-graph/topo-graph/use-topo';

import './topo-graph.scss';

export default defineComponent({
  name: 'TopoGraph',
  props: {
    topoSrc: {
      type: String,
      default: ''
    }
  },
  setup(props) {
    let graphInstance = null;

    const containerRef = ref(null);
    const imageRef = ref(null);

    watch(
      () => props.topoSrc,
      () => {
        nextTick(() => {
          if (props.topoSrc) {
            graphInstance = new UseTopoChart(containerRef.value, imageRef.value);
            imageRef.value.innerHTML = props.topoSrc;
          }
        });
      },
      {
        immediate: true
      }
    );

    return {
      graphInstance,
      containerRef,
      imageRef
    };
  },
  render() {
    return (
      <div
        class='profiling-topo-graph'
        ref='containerRef'
      >
        <div
          ref='imageRef'
          class='topo-img'
        />
      </div>
    );
  }
});
