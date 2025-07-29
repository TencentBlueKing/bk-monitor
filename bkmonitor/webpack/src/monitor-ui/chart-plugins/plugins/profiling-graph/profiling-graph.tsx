/* eslint-disable @typescript-eslint/naming-convention */

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
import { Component, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import { start } from 'monitor-api/modules/apm_meta';
import { query, queryServicesDetail } from 'monitor-api/modules/apm_profile';
import { serviceInfo } from 'monitor-api/modules/apm_service';
import { skipToDocsLink } from 'monitor-common/utils/docs';
import { Debounce, typeTools } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonDetail from 'monitor-pc/pages/monitor-k8s/components/common-detail';

import {
  type BaseDataType,
  type DataTypeItem,
  type IQueryParams,
  type ProfilingTableItem,
  PanelModel,
  TextDirectionType,
  ViewModeType,
} from '../../typings';
import { assignUniqueIds } from '../../utils';
import { CommonSimpleChart } from '../common-simple-chart';
import ChartTitle from './chart-title/chart-title';
import DiffChart from './diff-chart/diff-chart';
import FilterSelect from './filter-select/filter-select';
import FrameGraph from './flame-graph/flame-graph-v2';
import TableGraph from './table-graph/table-graph';
import TopoGraph from './topo-graph/topo-graph';
import TrendChart from './trend-chart/trend-chart';

import type { ProfileDataUnit } from './utils';

import './profiling-graph.scss';

interface IProfilingChartProps {
  panel: PanelModel;
}

@Component
class ProfilingChart extends CommonSimpleChart {
  @Ref() frameGraphRef: InstanceType<typeof FrameGraph>;
  @Ref() graphWrapperRef: HTMLDivElement;

  isGraphLoading = false;
  isFirstLoad = true;
  tableData: ProfilingTableItem[] = [];
  flameData: BaseDataType = {
    name: '',
    children: undefined,
    id: '',
  };
  unit: ProfileDataUnit = 'nanoseconds';
  empty = true;
  emptyText = window.i18n.t('加载中...');
  // 视图模式
  activeMode: ViewModeType = ViewModeType.Combine;
  textDirection: TextDirectionType = TextDirectionType.Ltr;
  highlightId = -1;
  highlightName = '';
  filterKeyword = '';
  topoSrc = '';
  dataTypeList: DataTypeItem[] = [];
  dataType = '';
  aggMethodList: DataTypeItem[] = [
    {
      key: 'AVG',
      name: 'AVG',
    },
    {
      key: 'SUM',
      name: 'SUM',
    },
    {
      key: 'LAST',
      name: 'LAST',
    },
  ];
  aggMethod = '';
  /** trend图表数据 */
  trendSeriesData = [];
  trendLoading = false;
  queryParams: IQueryParams = {};
  /** 是否开启时间对比 */
  enableDateDiff = false;
  /** 对比时间 */
  diffDate: number[][] = [];
  /** 服务详情侧边栏展开 / 收起 */
  collapseInfo = false;
  /** 是否展示服务详情侧边栏 */
  enableDetail = false;
  /** 未开启 profiling */
  enableProfiling = false;
  /** 无 profiling 上报数据 */
  isProfilingDataNormal = false;
  /** 开启 profiling 请求 loading */
  enableProfilingLoading = false;
  applicationId = -1;
  downloadImgIndex = 0;
  get detailPanel() {
    return new PanelModel({
      title: 'workload',
      type: 'info',
      targets: [
        {
          datasource: 'info',
          dataType: 'info',
          api: 'apm_profile.queryServicesDetail',
          data: {
            start_time: '$start_time',
            end_time: '$end_time',
            app_name: '$app_name',
            service_name: '$service_name',
            view_mode: 'sidebar',
          },
        },
      ],
    } as any);
  }

  cancelTableFlameFn = () => {};
  cancelTopoFn = () => {};

  get flameFilterKeywords() {
    return this.filterKeyword?.trim?.().length ? [this.filterKeyword] : [];
  }

  getParams(args: Record<string, any> = {}, start_time = '', end_time = '') {
    const { app_name, service_name } = this.viewOptions.filters as any;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const { diff_filter_labels = {}, filter_labels = {}, ...queryParams } = this.queryParams;
    const params = {
      ...args,
      ...queryParams,
      filter_labels: {
        ...filter_labels,
        ...(this.enableDateDiff && this.diffDate.length
          ? {
              start: Math.floor(this.diffDate[0][0] / 1000) * 1000000,
              end: Math.floor(this.diffDate[0][1] / 1000) * 1000000,
            }
          : {}),
      },
      diff_filter_labels: {
        ...diff_filter_labels,
        ...(this.enableDateDiff && this.diffDate.length
          ? {
              start: Math.floor(this.diffDate[1][0] / 1000) * 1000000,
              end: Math.floor(this.diffDate[1][1] / 1000) * 1000000,
            }
          : {}),
      },
      app_name,
      service_name,
      start: (start_time ? dayjs.tz(start_time).unix() : startTime) * 10 ** 6,
      end: (end_time ? dayjs.tz(end_time).unix() : endTime) * 10 ** 6,
      data_type: this.dataType,
      agg_method: this.aggMethod,
    };

    return params;
  }

  @Debounce(300)
  async getPanelData(start_time = '', end_time = '') {
    const initQuery = () => {
      if (!this.dataTypeList.length) {
        this.getServiceDetail(start_time, end_time);
        return;
      }
      this.handleQuery(start_time, end_time);
    };
    if (this.isFirstLoad || !this.enableProfiling || !this.isProfilingDataNormal) {
      const [start, end] = handleTransformToTimestamp(this.timeRange);
      const { app_name, service_name } = this.viewOptions.filters as any;

      await serviceInfo({
        start_time: (start_time ? dayjs.tz(start_time).unix() : start) * 1000,
        end_time: (end_time ? dayjs.tz(end_time).unix() : end) * 1000,
        app_name,
        service_name,
      })
        .then(data => {
          this.enableProfiling = data?.is_enabled_profiling ?? false;
          if (this.isFirstLoad) {
            this.isProfilingDataNormal = data?.is_profiling_data_normal ?? false;
          }
          this.applicationId = data?.application_id ?? -1;

          if (this.enableProfiling && this.isProfilingDataNormal) {
            initQuery();
          } else {
            this.emptyText = '';
          }
        })
        .catch(() => {
          this.emptyText = '';
        })
        .finally(() => {
          this.isFirstLoad = false;
        });
    } else {
      initQuery();
    }
  }

  async getServiceDetail(start_time = '', end_time = '') {
    const [start, end] = handleTransformToTimestamp(this.timeRange);
    const { app_name, service_name } = this.viewOptions.filters as any;

    await queryServicesDetail({
      start_time: start_time ? dayjs.tz(start_time).unix() : start,
      end_time: end_time ? dayjs.tz(end_time).unix() : end,
      app_name,
      service_name,
    })
      .then(res => {
        if (res?.data_types?.length) {
          this.dataTypeList = res.data_types;
          this.dataType = this.dataTypeList[0].key;
          this.aggMethod = this.dataTypeList[0]?.default_agg_method || 'AVG';
          this.queryParams = {
            app_name,
            service_name,
            data_type: this.dataType,
          };
          this.handleQuery(start_time, end_time);
        }
      })
      .catch(() => ({}));
  }
  async handleQuery(start_time = '', end_time = '') {
    this.getTableFlameData(start_time, end_time);
    if (this.queryParams.is_compared) {
      if (this.activeMode === ViewModeType.Topo) {
        this.activeMode = ViewModeType.Combine;
      }
    } else {
      if (this.activeMode === ViewModeType.Topo) {
        this.getTopoSrc(start_time, end_time);
      }
    }
  }
  async handleModeChange(val: ViewModeType) {
    if (val === this.activeMode) return;
    this.highlightId = -1;
    this.activeMode = val;
    if (val === ViewModeType.Topo && !this.topoSrc) {
      this.getTopoSrc();
    }
  }
  /** 获取表格和火焰图 */
  async getTableFlameData(start_time = '', end_time = '') {
    this.isGraphLoading = true;
    this.highlightId = -1;
    this.emptyText = window.i18n.t('加载中...');
    this.cancelTableFlameFn();
    const params = this.getParams({ diagram_types: ['table', 'flamegraph'] }, start_time, end_time);
    await query(params, {
      cancelToken: new CancelToken(c => (this.cancelTableFlameFn = c)),
    })
      .then(data => {
        // 为数据节点及其子节点分配唯一 ID
        data?.flame_data?.children && assignUniqueIds(data.flame_data.children);
        if (data && Object.keys(data)?.length) {
          this.unit = data.unit || '';
          this.tableData = data.table_data?.items ?? [];
          this.flameData = data.flame_data || [];
          this.empty = false;
          this.emptyText = '';
        }
        if (!this.tableData?.length && !this.flameData?.length) {
          this.empty = true;
          this.emptyText = window.i18n.t('暂无数据');
        }
        this.isGraphLoading = false;
      })
      .catch(e => {
        if (e.message) {
          this.emptyText = '';
          this.isGraphLoading = false;
        }
        this.empty = true;
      });
  }
  /** 获取拓扑图 */
  async getTopoSrc(start_time = '', end_time = '') {
    this.cancelTopoFn();
    if (ViewModeType.Topo === this.activeMode) {
      this.isGraphLoading = true;
    }
    const params = this.getParams({ diagram_types: ['callgraph'] }, start_time, end_time);
    await query(params, {
      cancelToken: new CancelToken(c => (this.cancelTopoFn = c)),
    })
      .then(data => {
        if (data) {
          this.topoSrc = data.call_graph_data || '';
        }
        this.isGraphLoading = false;
      })
      .catch(e => {
        if (e.message) {
          this.isGraphLoading = false;
        }
      });
  }
  handleTimeRangeChange() {
    this.getPanelData();
  }
  handleTextDirectionChange(val: TextDirectionType) {
    this.textDirection = val;
  }
  /** 表格排序 */
  async handleSortChange() {
    // const params = this.getParams({
    //   diagram_types: ['table'],
    //   sort: sortKey
    // });
    // const data = await query(params).catch(() => false);
    // if (data) {
    //   this.highlightId = -1;
    //   this.tableData = data.table_data?.items ?? [];
    // }
    this.highlightId = -1;
  }
  handleDownload(type: string) {
    switch (type) {
      case 'png':
        this.downloadImgIndex += 1;
        break;
      case 'pprof': {
        const params = this.getParams({ export_format: 'pprof' });
        const downloadUrl = `/apm/profile_api/query/export/?bk_biz_id=${window.bk_biz_id}${this.getUrlParamsString(
          params
        )}`;
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        break;
      }
      default:
        break;
    }
  }
  handleDataTypeChange(val, type?: string) {
    if ([this.dataType, this.aggMethod].includes(val)) return;
    if (type === 'agg') {
      this.aggMethod = val;
    } else {
      this.dataType = val;
      // 切换数据类型时，汇聚方法需要切换成后端给的值
      this.aggMethod = this.dataTypeList.find(item => item.key === val).default_agg_method || 'AVG';
      this.queryParams.data_type = val;
    }
    this.getPanelData();
  }
  getUrlParamsString(obj) {
    const str = Object.keys(obj)
      .reduce((ary, key) => {
        if (obj[key]) {
          ary.push(
            `${encodeURIComponent(key)}=${encodeURIComponent(
              typeTools.isObject(obj[key]) ? JSON.stringify(obj[key]) : obj[key]
            )}`
          );
        }
        return ary;
      }, [])
      .join('&');
    if (str.length) return `&${str}`;
    return '';
  }
  goLink() {
    const params = this.getParams({ diagram_types: this.activeMode });
    const target = JSON.stringify({ ...params, start: this.timeRange[0], end: this.timeRange[1] });
    const url = location.href.replace(location.hash, `#/trace/profiling?target=${encodeURIComponent(target)}`);
    window.open(url, '_blank');
  }
  handleFiltersChange(values, key) {
    this.queryParams = {
      ...this.queryParams,
      [key === 'filter' ? 'filter_labels' : 'diff_filter_labels']: values,
    };
    this.getPanelData();
  }
  /** 对比模式 */
  handleDiffModeChange(isDiff: boolean) {
    this.queryParams = {
      ...this.queryParams,
      is_compared: isDiff,
    };
    this.getPanelData();
  }
  handleDateDiffChange(enable) {
    this.enableDateDiff = enable;
    this.setDiffDefaultDate();
    this.handleQuery();
  }
  handleTrendSeriesData(data) {
    this.trendSeriesData = data;
  }

  handleTrendLoading(loading) {
    this.trendLoading = loading;
  }

  setDiffDefaultDate() {
    if (this.enableDateDiff) {
      if (this.trendSeriesData?.length) {
        const { datapoints } = this.trendSeriesData[0];
        const len = datapoints.length;
        const start = datapoints[0][1];
        const end = datapoints[len - 1][1];
        const mid = start + (end - start) / 2;
        this.diffDate = [
          [start, mid],
          [mid, end],
        ];
      } else {
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        const mid = startTime + (endTime - startTime) / 2;
        this.diffDate = [
          [startTime * 1000, mid * 1000],
          [mid * 1000, endTime * 1000],
        ];
      }
    } else {
      this.diffDate = [];
    }
  }

  handleBrushEnd(data, type) {
    if (type === 'search') {
      this.diffDate[0] = data;
    } else {
      this.diffDate[1] = data;
    }
    this.diffDate = [...this.diffDate];
    this.handleQuery();
  }

  handleDetailShowChange(show: boolean) {
    this.collapseInfo = !show;
  }
  async handleEmptyEvent() {
    // 开启 profiling
    if (!this.enableProfiling) {
      if (this.enableProfilingLoading) return;
      // const { app_name, service_name } = this.viewOptions as any;
      this.enableProfilingLoading = true;
      await start({ application_id: this.applicationId, type: 'profiling' })
        .then(() => {
          this.enableProfiling = true;
        })
        .finally(() => (this.enableProfilingLoading = false));
    } else if (!this.isProfilingDataNormal) {
      // 查看接入指引
      skipToDocsLink('profiling_docs', window.docUrlMap);
    }
  }
  handleKeywordChange(v: string) {
    this.filterKeyword = v;
    this.graphWrapperRef?.scrollTo({
      top: 0,
      behavior: 'instant',
    });
  }

  render() {
    return (
      <div class='profiling-retrieval-chart'>
        {this.enableProfiling && this.isProfilingDataNormal ? (
          [
            <div
              key={'main'}
              class='main'
            >
              <FilterSelect
                appName={this.queryParams.app_name}
                serviceName={this.queryParams.service_name}
                onDateDiffChange={this.handleDateDiffChange}
                onDiffChange={val => this.handleFiltersChange(val, 'diff')}
                onDiffModeChange={this.handleDiffModeChange}
                onFilterChange={val => this.handleFiltersChange(val, 'filter')}
              />
              <div class='profiling-retrieval-header'>
                <div class='data-type'>
                  <span>{this.$t('数据类型')}</span>
                  <div class='bk-button-group data-type-list'>
                    {this.dataTypeList.map(item => {
                      return (
                        <bk-button
                          key={item.key}
                          class={item.key === this.dataType ? 'is-selected' : ''}
                          size='small'
                          onClick={() => this.handleDataTypeChange(item.key)}
                        >
                          {item.name}
                        </bk-button>
                      );
                    })}
                  </div>
                </div>
                <div class='data-type'>
                  <span>{this.$t('汇聚方法')}</span>
                  <div class='bk-button-group data-type-list'>
                    {this.aggMethodList.map(item => {
                      return (
                        <bk-button
                          key={item.key}
                          class={item.key === this.aggMethod ? 'is-selected' : ''}
                          size='small'
                          onClick={() => this.handleDataTypeChange(item.key, 'agg')}
                        >
                          {item.name}
                        </bk-button>
                      );
                    })}
                  </div>
                </div>
                <div class='link-tips'>
                  <i class='icon-monitor icon-tishi' />
                  <i18n
                    class='flex-center'
                    path='更多功能，请前往 {0}'
                  >
                    <span
                      class='link-text'
                      onClick={() => this.goLink()}
                    >
                      {`Profiling ${this.$t('检索')}`}
                    </span>
                  </i18n>
                </div>
              </div>
              <TrendChart
                diffDate={this.diffDate}
                queryParams={this.queryParams}
                onLoading={this.handleTrendLoading}
                onOptionsLoaded={this.setDiffDefaultDate}
                onSeriesData={this.handleTrendSeriesData}
              />
              {this.enableDateDiff && (
                <div
                  key='diffChartView'
                  class='diff-chart-view'
                >
                  <DiffChart
                    brushRect={this.diffDate[0]}
                    colorIndex={0}
                    data={this.trendSeriesData[0]}
                    loading={this.trendLoading}
                    title={this.$tc('查询项')}
                    onBrushEnd={val => this.handleBrushEnd(val, 'search')}
                  />
                  <DiffChart
                    brushRect={this.diffDate[1]}
                    colorIndex={1}
                    data={this.trendSeriesData[1]}
                    loading={this.trendLoading}
                    title={this.$tc('对比项')}
                    onBrushEnd={val => this.handleBrushEnd(val, 'diff')}
                  />
                </div>
              )}

              <div
                class='profiling-graph'
                v-bkloading={{ isLoading: this.isGraphLoading }}
              >
                <ChartTitle
                  activeMode={this.activeMode}
                  isCompared={this.queryParams.is_compared}
                  keyword={this.filterKeyword}
                  textDirection={this.textDirection}
                  onDownload={this.handleDownload}
                  onKeywordChange={this.handleKeywordChange}
                  onModeChange={this.handleModeChange}
                  onTextDirectionChange={this.handleTextDirectionChange}
                />
                {this.empty ? (
                  <div class='empty-chart'>{this.emptyText}</div>
                ) : (
                  <div
                    ref='graphWrapperRef'
                    class='profiling-graph-content'
                  >
                    {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
                      <TableGraph
                        style={{
                          width: this.activeMode === ViewModeType.Combine ? '50%' : '100%',
                        }}
                        data={this.tableData}
                        dataType={this.queryParams.data_type}
                        filterKeyword={this.filterKeyword}
                        highlightName={this.highlightName}
                        isCompared={this.queryParams.is_compared}
                        textDirection={this.textDirection}
                        unit={this.unit}
                        onSortChange={this.handleSortChange}
                        onUpdateHighlightName={name => {
                          this.highlightName = name;
                          this.handleKeywordChange(name);
                        }}
                      />
                    )}
                    {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
                      <FrameGraph
                        style={{
                          width: this.activeMode === ViewModeType.Combine ? '50%' : '100%',
                        }}
                        appName={(this.viewOptions as any).app_name}
                        data={this.flameData}
                        downloadImgIndex={this.downloadImgIndex}
                        filterKeyword={this.filterKeyword}
                        isCompared={this.queryParams.is_compared}
                        textDirection={this.textDirection}
                        unit={this.unit}
                        onUpdateFilterKeyword={name => {
                          this.highlightName = name;
                          this.handleKeywordChange(name);
                        }}
                      />
                    )}
                    {ViewModeType.Topo === this.activeMode && <TopoGraph topoSrc={this.topoSrc} />}
                  </div>
                )}
              </div>
            </div>,
            <keep-alive key={'keep-alive'}>
              <CommonDetail
                collapse={this.collapseInfo}
                maxWidth={500}
                needShrinkBtn={false}
                panel={this.detailPanel}
                placement={'right'}
                startPlacement={'left'}
                title={this.$tc('详情')}
                onShowChange={this.handleDetailShowChange}
              />
            </keep-alive>,
          ]
        ) : (
          <div class='empty-page'>
            {this.emptyText ? (
              this.emptyText
            ) : (
              <bk-exception type='building'>
                <span>
                  {!this.enableProfiling ? this.$t('暂未开启 Profiling 功能') : this.$t('暂无 Profiling 数据')}
                </span>
                <div class='text-wrap'>
                  <span class='text-row'>
                    {!this.enableProfiling
                      ? this.enableProfilingLoading
                        ? this.$t('开启中，请耐心等待...')
                        : this.$t('该服务所在 APM 应用未开启 Profiling 功能')
                      : this.$t('已开启 Profiling 功能，请参考接入指引进行数据上报')}
                  </span>
                  <bk-button
                    loading={this.enableProfilingLoading}
                    text={this.enableProfiling}
                    theme='primary'
                    onClick={() => this.handleEmptyEvent()}
                  >
                    {this.enableProfiling ? this.$t('查看接入指引') : this.$t('立即开启')}
                  </bk-button>
                </div>
              </bk-exception>
            )}
          </div>
        )}
      </div>
    );
  }
}

export default ofType<IProfilingChartProps>().convert(ProfilingChart);
