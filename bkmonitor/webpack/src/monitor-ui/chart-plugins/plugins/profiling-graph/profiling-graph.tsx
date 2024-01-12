/* eslint-disable max-len */
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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { Debounce } from '../../../../monitor-common/utils/utils';
import { PROFILING_QUERY_DATA } from '../../../../trace/plugins/charts/profiling-graph/mock';
import {
  BaseDataType,
  IQueryParams,
  PanelModel,
  ProfilingTableItem,
  TextDirectionType,
  ViewModeType
} from '../../typings';
import { CommonSimpleChart } from '../common-simple-chart';

import ChartTitle from './chart-title/chart-title';
import FrameGraph from './flame-graph/flame-graph';
import TableGraph from './table-graph/table-graph';

import './profiling-graph.scss';

interface IProfilingChartProps {
  panel: PanelModel;
  queryParams: IQueryParams;
}

@Component
class ProfilingChart extends CommonSimpleChart {
  @Prop({ default: () => {}, type: Object }) queryParams: IQueryParams;

  isLoading = false;
  tableData: ProfilingTableItem[] = [];
  flameData: BaseDataType = {
    name: '',
    children: undefined,
    id: ''
  };
  unit = '';
  empty = false;
  emptyText = '查无数据';
  // 视图模式
  activeMode: ViewModeType = ViewModeType.Combine;
  textDirection: TextDirectionType = TextDirectionType.Ltr;

  @Debounce(16)
  @Watch('queryParams', { immediate: true, deep: true })
  handleQueryParamsChange() {
    this.handleQuery();
  }

  handleQuery() {
    try {
      // isLoaing.value = true;
      // const { queryParams } = this.$props;
      // const params = Object.assign({}, queryParams);
      // const data = await profileQuery(params).catch(() => false);
      const data = PROFILING_QUERY_DATA;
      if (data) {
        this.unit = data.unit || '';
        this.tableData = data.table_data || [];
        this.flameData = data.flame_data as any;
      }
    } catch (e) {
      console.error(e);
      // isLoaing.value = false;
    }
  }
  handleModeChange(val: ViewModeType) {
    this.activeMode = val;
  }
  handleTextDirectionChange(val: TextDirectionType) {
    this.textDirection = val;
  }

  render() {
    if (this.empty) {
      return <div class='empty-chart'>{this.emptyText}</div>;
    }
    return (
      <div
        class='profiling-graph'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <ChartTitle
          activeMode={this.activeMode}
          textDirection={this.textDirection}
          onModeChange={this.handleModeChange}
          onTextDirectionChange={this.handleTextDirectionChange}
        />
        <div class='profiling-graph-content'>
          {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
            <TableGraph
              data={this.tableData}
              unit={this.unit}
              textDirection={this.textDirection}
            />
          )}
          {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
            <FrameGraph
              data={this.flameData}
              appName={'bkmonitor_production'}
              profileId={'3d0d77e0669cdb72'}
              start={1703747947993154}
              end={1703747948022443}
              bizId={2}
              textDirection={this.textDirection}
            />
          )}
        </div>
      </div>
    );
  }
}

export default ofType<IProfilingChartProps>().convert(ProfilingChart);
