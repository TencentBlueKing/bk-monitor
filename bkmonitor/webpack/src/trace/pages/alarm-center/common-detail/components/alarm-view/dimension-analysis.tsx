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
import DimensionTreeMapCharts from './echarts/dimension-tree-map-charts';

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
    const dimensionList = shallowRef(
      new Array(10).fill(null).map((_, index) => ({ id: `dimension_0${index}`, name: `维度${index}` }))
    );

    /**
     * 是否多选
     */
    const isMulti = shallowRef(false);
    /**
     * 选中的维度
     */
    const selectedDimension = shallowRef<string[]>([dimensionList.value[0].id]);
    /**
     * 下钻条件
     */
    const where = shallowRef([
      {
        method: 'eq',
        value: ['test'],
        condition: 'and',
        key: 'test',
      },
    ]);

    const handleDrillDown = (item: any) => {
      console.log(item);
    };
    const handleTableDrillDown = (obj: { dimension: string; where: any[] }) => {
      const existingKeys = new Set(obj.where.map(item => item.key));
      where.value = [...where.value.filter(item => !existingKeys.has(item.key)), ...obj.where];
      selectedDimension.value = [obj.dimension];
    };

    const handleShowTypeChange = (val: string) => {
      showTypeActive.value = val;
    };

    const handleMultiChange = (val: boolean) => {
      isMulti.value = val;
      if (!val) {
        selectedDimension.value = selectedDimension.value.length ? [selectedDimension.value[0]] : [];
      }
    };

    const handleDimensionSelectChange = (val: string[]) => {
      selectedDimension.value = val;
    };

    const handleRemoveCondition = (index: number) => {
      where.value = [...where.value.slice(0, index), ...where.value.slice(index + 1)];
    };

    return {
      isMulti,
      showTypeActive,
      dimensionList,
      selectedDimension,
      where,
      handleDrillDown,
      handleTableDrillDown,
      handleShowTypeChange,
      handleMultiChange,
      handleDimensionSelectChange,
      handleRemoveCondition,
    };
  },
  render() {
    return (
      <div class='alarm-view-panel-dimension-analysis-wrap'>
        <DimensionChart />
        <div class='dimension-analysis-table-view'>
          <div class='dimension-analysis-left'>
            <DimensionSelector
              dimensions={this.dimensionList}
              isMulti={this.isMulti}
              selected={this.selectedDimension}
              onChange={this.handleDimensionSelectChange}
              onMultiChange={this.handleMultiChange}
            />
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
            {this.where.length > 0 && (
              <div class='conditions-wrap'>
                {this.where.map((item, index) => (
                  <div
                    key={index}
                    class='condition-item'
                  >
                    {item.key}
                    <span class='method'>等于</span>
                    {item.value}
                    <span
                      class='icon-monitor icon-mc-close'
                      onClick={() => this.handleRemoveCondition(index)}
                    />
                  </div>
                ))}
              </div>
            )}
            <div class='dimension-analysis-data'>
              {this.showTypeActive === TYPE_ENUM.TABLE ? (
                <DimensionAnalysisTable
                  dimensions={this.dimensionList}
                  displayDimensions={this.selectedDimension}
                  onDrillDown={this.handleTableDrillDown}
                />
              ) : (
                <DimensionTreeMapCharts
                  dimensionList={this.dimensionList}
                  onDrillDown={this.handleDrillDown}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
