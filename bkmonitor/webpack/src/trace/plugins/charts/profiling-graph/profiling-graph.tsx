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

import { defineComponent, ref } from 'vue';

import ChartTitle from './chart-title/chart-title';
import FrameGraph from './flame-graph/flame-graph';
import TableGraph from './table-graph/table-graph';

import './profiling-graph.scss';

export default defineComponent({
  name: 'ProfilingGraph',
  setup() {
    // 当前视图模式
    const activeMode = ref('table');

    /** 切换视图模式 */
    const handleModeChange = (val: string) => {
      activeMode.value = val;
    };

    return {
      activeMode,
      handleModeChange
    };
  },
  render() {
    return (
      <div class='profiling-graph'>
        <ChartTitle
          activeMode={this.activeMode}
          onModeChange={this.handleModeChange}
        />
        <div class='profiling-graph-content'>
          {['table', 'tableAndFlame'].includes(this.activeMode) ? <TableGraph /> : ''}
          {['flame', 'tableAndFlame'].includes(this.activeMode) ? (
            <FrameGraph
              appName={'bkmonitor_production'}
              profileId={'3d0d77e0669cdb72'}
              start={1703747947993154}
              end={1703747948022443}
              bizId={2}
              showGraphTools={false}
            />
          ) : (
            ''
          )}
        </div>
      </div>
    );
  }
});
