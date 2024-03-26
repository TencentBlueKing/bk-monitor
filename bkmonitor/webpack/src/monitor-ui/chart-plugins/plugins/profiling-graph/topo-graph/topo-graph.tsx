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

import { UseTopoChart } from './use-topo';

import './topo-graph.scss';

interface ITopoGraphProps {
  topoSrc: string;
}

@Component
export default class TopoGraph extends tsc<ITopoGraphProps> {
  @Ref() containerRef: HTMLDivElement;
  @Ref() imageRef: HTMLDivElement;

  @Prop({ default: '', type: String }) topoSrc: string;

  graphInstance = null;

  @Watch('topoSrc', { immediate: true })
  handleTopoSrcChange() {
    this.$nextTick(() => {
      if (this.topoSrc) {
        this.graphInstance = new UseTopoChart(this.containerRef, this.imageRef);
        this.imageRef.innerHTML = this.topoSrc;
      }
    });
  }

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
}
