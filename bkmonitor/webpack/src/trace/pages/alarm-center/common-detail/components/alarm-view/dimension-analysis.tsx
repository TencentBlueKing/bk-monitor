/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent, shallowRef } from 'vue';

import DimensionAnalysisTable from './components/dimension-analysis-table';
import DimensionSelector from './components/dimension-selector';
import DimensionChart from './dimension-chart';

import './dimension-analysis.scss';

const TYPE_ENUM = {
  TABLE: 'table',
  CHART: 'chart',
};
const showTypeList = [
  {
    id: TYPE_ENUM.TABLE,
    icon: 'icon-mc-list',
  },
  { id: TYPE_ENUM.CHART, icon: 'icon-mc-overview' },
];

export default defineComponent({
  name: 'DimensionAnalysis',
  props: {
    a: {
      type: String,
      default: '',
    },
  },
  emits: {
    change: (_val: any) => true,
  },
  setup() {
    const showTypeActive = shallowRef(TYPE_ENUM.TABLE);
    const handleShowTypeChange = (val: string) => {
      showTypeActive.value = val;
    };

    return {
      showTypeActive,
      handleShowTypeChange,
    };
  },
  render() {
    return (
      <div class='alarm-view-panel-dimension-analysis-wrap'>
        <DimensionChart />
        <div class='dimension-analysis-table-view'>
          <div class='dimension-analysis-left'>
            <DimensionSelector />
          </div>
          <div class='dimension-analysis-right'>
            <div class='type-select'>
              {showTypeList.map(item => (
                <div
                  key={item.id}
                  class={['type-select-item', { active: this.showTypeActive === item.id }]}
                  onClick={() => this.handleShowTypeChange(item.id)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
            <div class='dimension-analysis-data'>
              {this.showTypeActive === TYPE_ENUM.TABLE ? <DimensionAnalysisTable /> : '图标'}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
