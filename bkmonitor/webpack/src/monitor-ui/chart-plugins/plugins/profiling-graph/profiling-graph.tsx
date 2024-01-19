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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { query } from '../../../../monitor-api/modules/apm_profile';
import { Debounce } from '../../../../monitor-common/utils/utils';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
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
import TopoGraph from './topo-graph/topo-graph';

import './profiling-graph.scss';

interface IProfilingChartProps {
  panel: PanelModel;
  queryParams?: IQueryParams;
}

@Component
class ProfilingChart extends CommonSimpleChart {
  @Ref() frameGraphRef: FrameGraph;

  @Prop({ default: () => {}, type: Object }) queryParams: IQueryParams;

  isLoading = false;
  tableData: ProfilingTableItem[] = [];
  flameData: BaseDataType = {
    name: '',
    children: undefined,
    id: ''
  };
  unit = '';
  empty = true;
  emptyText = window.i18n.t('查无数据');
  // 视图模式
  activeMode: ViewModeType = ViewModeType.Combine;
  textDirection: TextDirectionType = TextDirectionType.Ltr;
  highlightId = -1;
  filterKeyword = '';
  topoSrc = '';

  get flameFilterKeywords() {
    return this.filterKeyword?.trim?.().length ? [this.filterKeyword] : [];
  }

  @Debounce(16)
  @Watch('queryParams', { immediate: true, deep: true })
  handleQueryParamsChange() {
    this.handleQuery();
  }

  getParams(args: Record<string, any> = {}) {
    const { queryParams } = this.$props;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    return {
      ...args,
      ...queryParams,
      start: startTime * Math.pow(10, 6),
      end: endTime * Math.pow(10, 6),
      // TODO
      app_name: 'profiling_bar',
      service_name: 'fuxi_gin_server'
    };
  }
  async handleQuery() {
    try {
      this.isLoading = true;
      this.highlightId = -1;
      const params = this.getParams({ diagram_types: ['table', 'flamegraph'] });
      const data = await query(params).catch(() => false);
      // data = PROFILING_QUERY_DATA; // TODO
      if (data.diagrams) {
        this.unit = data.diagrams.unit || '';
        this.tableData = data.diagrams.table_data || [];
        this.flameData = data.diagrams.flame_data;
        this.empty = false;
      } else {
        this.empty = true;
      }
      this.isLoading = false;
    } catch (e) {
      console.error(e);
      this.isLoading = false;
    }
  }
  async handleModeChange(val: ViewModeType) {
    if (val === this.activeMode) return;

    this.highlightId = -1;
    this.activeMode = val;

    if (val === ViewModeType.Topo && !this.topoSrc) {
      this.isLoading = true;
      const params = this.getParams({ diagram_types: ['callgraph'] });
      const data = await query(params).catch(() => false);
      if (data.diagrams) {
        this.topoSrc = data.diagrams.call_graph_data || '';
      }
      this.isLoading = true;
    }
  }
  handleTextDirectionChange(val: TextDirectionType) {
    this.textDirection = val;
  }
  /** 表格排序 */
  async handleSortChange(sortKey: string) {
    const params = this.getParams({
      diagram_types: ['table'],
      sort: sortKey
    });
    const data = await query(params).catch(() => false);
    if (data.diagrams) {
      this.highlightId = -1;
      this.tableData = data.diagrams.table_data || [];
    }
  }
  handleDownload(type: string) {
    switch (type) {
      case 'png':
        this.frameGraphRef?.handleStoreImg();
        break;
      case 'pprof':
        break;
      default:
        break;
    }
  }

  render() {
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
          onKeywordChange={val => (this.filterKeyword = val)}
          onDownload={this.handleDownload}
        />
        {this.empty ? (
          <div class='empty-chart'>{this.emptyText}</div>
        ) : (
          <div class='profiling-graph-content'>
            {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
              <TableGraph
                data={this.tableData}
                unit={this.unit}
                textDirection={this.textDirection}
                highlightId={this.highlightId}
                filterKeyword={this.filterKeyword}
                onUpdateHighlightId={id => (this.highlightId = id)}
                onSortChange={this.handleSortChange}
              />
            )}
            {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
              <FrameGraph
                ref='frameGraphRef'
                textDirection={this.textDirection}
                showGraphTools={false}
                data={this.flameData}
                highlightId={this.highlightId}
                filterKeywords={this.flameFilterKeywords}
                onUpdateHighlightId={id => (this.highlightId = id)}
              />
            )}
            {ViewModeType.Topo === this.activeMode && <TopoGraph topoSrc={this.topoSrc} />}
          </div>
        )}
      </div>
    );
  }
}

export default ofType<IProfilingChartProps>().convert(ProfilingChart);
