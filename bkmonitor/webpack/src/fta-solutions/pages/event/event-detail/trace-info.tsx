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
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { errorListByTraceIds } from 'monitor-api/modules/apm_metric';
import { traceListById } from 'monitor-api/modules/apm_trace';
import bus from 'monitor-common/utils/event-bus';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import StatusTab from 'monitor-ui/chart-plugins/plugins/table-chart/status-tab';

import { formatDuration } from '../../../../trace/components/trace-view/utils/date';
import { createAutoTimeRange } from './aiops-chart';

import type { IDetail } from './type';
import type { IFilterDict, ITableColumn } from 'monitor-pc/pages/monitor-k8s/typings';

import './trace-info.scss';

const traceTableColumns: ITableColumn[] = [
  { id: 'trace_id', name: 'traceid', type: 'scoped_slots' },
  { id: 'span_id', name: 'spanid', type: 'string' },
  { id: 'status_code', name: window.i18n.tc('状态'), type: 'scoped_slots' },
  { id: 'elapsed_time', name: window.i18n.tc('耗时'), type: 'string', sortable: 'custom' },
  { id: 'url', name: window.i18n.tc('操作'), type: 'scoped_slots' },
];

interface IProps {
  detail?: IDetail;
  show?: boolean;
  traceIds?: string[];
}

@Component
export default class TraceInfo extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Array, default: () => [] }) traceIds: string[];

  loading = false;

  alltraceIdTable = []; /* 原始数据 */
  traceIdSortTable = []; /* 排序数据 */
  traceIdTable = []; /* 分页数据 */
  traceTablePagination = {
    current: 1,
    count: 0,
    limit: 10,
  };

  /* 错误列表数据 */
  errData = {
    columns: [],
    data: [],
    filter: [],
    check_filter: [],
    total: 0,
  };
  errDataPagination = {
    current: 1,
    count: 0,
    limit: 10,
  };
  errDataParams: {
    filter: string;
    filterDict: IFilterDict;
    sortKey: string;
  } = {
    filterDict: {},
    sortKey: '',
    filter: 'all',
  };
  errLoading = false;

  startTime = 0;
  endTime = 0;

  @Watch('show')
  handleShow(v: boolean) {
    if (v && !this.alltraceIdTable.length) {
      this.init();
    }
  }

  mounted() {
    bus.$on('switch_scenes_type', this.handleToSceneDetail);
    bus.$on('switch_to_overview', this.handleToSceneOverview);
  }

  destroyed() {
    bus.$off('switch_scenes_type');
    bus.$off('switch_to_overview');
  }

  handleToSceneDetail(data) {
    window.open(`${location.origin}${location.pathname}${location.search}#/apm${data.url}`);
  }
  handleToSceneOverview(data) {
    window.open(`${location.origin}${location.pathname}${location.search}#/apm${data.url}`);
  }

  init() {
    this.loading = true;
    const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(this.detail.begin_time, this.detail.end_time, interval);
    this.startTime = dayjs.tz(startTime).unix();
    this.endTime = dayjs.tz(endTime).unix();
    traceListById({
      bk_biz_id: this.detail.bk_biz_id,
      trace_ids: this.traceIds,
      start_time: this.startTime,
      end_time: this.endTime,
    })
      .then(data => {
        this.alltraceIdTable = data.map(item => ({
          trace_id: item.root_span.trace_id,
          span_id: item.root_span.span_id,
          status_code: item.status_code,
          url: item.url,
          elapsedTime: item.root_span.elapsed_time,
          elapsed_time: formatDuration(item.root_span.elapsed_time),
        }));
        this.traceIdSortTable = [...this.alltraceIdTable];
        this.traceTablePagination.count = this.alltraceIdTable.length;
        this.traceTablePagination.limit = 10;
        this.traceTablePagination.current = 1;
        this.getTraceTableData();
      })
      .finally(() => {
        this.loading = false;
      });
    this.errDataPagination.limit = 10;
    this.errDataPagination.current = 1;
    this.getErrData();
  }

  /* traceid 表格分页 */
  getTraceTableData() {
    this.traceIdTable = this.traceIdSortTable.slice(
      (this.traceTablePagination.current - 1) * this.traceTablePagination.limit,
      this.traceTablePagination.current * this.traceTablePagination.limit
    );
  }

  handletTracePageChange(v: number) {
    this.traceTablePagination.current = v;
    this.getTraceTableData();
  }

  handletTraceLimitChange(v: number) {
    this.traceTablePagination.current = 1;
    this.traceTablePagination.limit = v;
    this.getTraceTableData();
  }

  handleSortChange(value) {
    // ascending 升序 descending 降序 null 重置
    if (value.order) {
      if (value.order === 'ascending') {
        this.traceIdSortTable.sort((a, b) => a.elapsedTime - b.elapsedTime);
      }
      if (value.order === 'descending') {
        this.traceIdSortTable.sort((a, b) => b.elapsedTime - a.elapsedTime);
      }
    } else {
      this.traceIdSortTable = [...this.alltraceIdTable];
    }
    this.traceTablePagination.limit = 10;
    this.traceTablePagination.current = 1;
    this.getTraceTableData();
  }

  /* 获取错误列表 */
  async getErrData(isInit = false) {
    if (!isInit) this.errLoading = true;
    const errData = await errorListByTraceIds({
      trace_ids: this.traceIds.slice(0, 10),
      bk_biz_id: this.detail.bk_biz_id,
      end_time: this.endTime,
      start_time: this.startTime,
      filter: this.errDataParams.filter,
      filter_dict: this.errDataParams.filterDict,
      keyword: '',
      page: this.errDataPagination.current,
      page_size: this.errDataPagination.limit,
      sort: this.errDataParams.sortKey,
    }).catch(() => ({
      columns: [],
      data: [],
      filter: [],
      check_filter: [],
      total: 0,
    }));
    /* 将type: link target: self 数据个更改为target: target */
    const linkSlefColumns = [];
    let curData = [];
    const { columns, data } = errData;
    columns.forEach(c => {
      if (c.type === 'link') {
        linkSlefColumns.push(c.id);
      }
    });
    curData = data.map(item => {
      const obj = {};
      const keys = Object.keys(item);
      keys.forEach(key => {
        const targetItem = item[key];
        if (linkSlefColumns.includes(key) && targetItem?.target === 'self') {
          obj[key] = {
            ...targetItem,
            target: 'target',
            url: `${location.origin}${location.pathname}${location.search}#/apm${targetItem.url}`,
          };
        } else {
          obj[key] = targetItem;
        }
      });
      return obj;
    });
    this.errData = {
      ...errData,
      data: curData,
    };
    this.errDataPagination.count = errData.total;
    if (!isInit) this.errLoading = false;
  }

  handleErrDataFilterChange(filters) {
    this.errDataParams.filterDict = filters;
    this.errDataPagination.current = 1;
    this.getErrData();
  }

  handleErrDataPageChange(page: number) {
    this.errDataPagination.current = page;
    this.getErrData();
  }
  handleErrDataLimitChange(limit: number) {
    this.errDataPagination.current = 1;
    this.errDataPagination.limit = limit;
    this.getErrData();
  }
  handleErrDataSortChange({ prop, order }) {
    switch (order) {
      case 'ascending':
        this.errDataParams.sortKey = prop;
        break;
      case 'descending':
        this.errDataParams.sortKey = `-${prop}`;
        break;
      default:
        this.errDataParams.sortKey = undefined;
    }
    this.getErrData();
  }
  handleErrDataStatusChange() {
    this.errDataPagination.current = 1;
    this.getErrData();
  }

  handleGoLink(row) {
    window.open(`${location.origin}${row.url}`);
  }

  render() {
    return (
      <div class={['event-detail-trace-info-component', { show: this.show }]}>
        <div
          class='top-info'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='info-title'>{`Traceid ${this.$t('列表')}`}</div>
          <CommonTable
            class='trace-table'
            scopedSlots={{
              trace_id: row => (
                <span
                  class='link'
                  onClick={() => this.handleGoLink(row)}
                >
                  {row.trace_id}
                </span>
              ),
              status_code: row =>
                row.status_code ? (
                  <div class={`status-code status-${row.status_code.type}`}>{row.status_code.value || '--'}</div>
                ) : (
                  '--'
                ),
              url: row => (
                <span
                  class='link'
                  onClick={() => this.handleGoLink(row)}
                >
                  {this.$t('检索')}
                </span>
              ),
            }}
            checkable={false}
            columns={traceTableColumns}
            data={this.traceIdTable}
            pagination={this.traceTablePagination}
            onLimitChange={this.handletTraceLimitChange}
            onPageChange={this.handletTracePageChange}
            onSortChange={this.handleSortChange}
          />
        </div>
        <div
          class='err-info'
          v-bkloading={{ isLoading: this.errLoading }}
        >
          <div class='info-title'>{this.$t('该实例下的错误列表')}</div>
          <div class='filter-content'>
            <StatusTab
              v-model={this.errDataParams.filter}
              needAll={false}
              statusList={this.errData.filter}
              onChange={this.handleErrDataStatusChange}
            />
          </div>
          <CommonTable
            class='err-table'
            checkable={false}
            columns={this.errData.columns}
            data={this.errData.data}
            defaultSize='small'
            pagination={this.errDataPagination}
            paginationType='simple'
            onFilterChange={this.handleErrDataFilterChange}
            onLimitChange={this.handleErrDataLimitChange}
            onPageChange={this.handleErrDataPageChange}
            onSortChange={this.handleErrDataSortChange}
          />
          {/* <div class="info-bottom">
          <span>当前仅显示5条数据</span>
          <span class="link">
            {this.$t('查看更多')}
            <span class="icon-monitor icon-fenxiang"></span>
          </span>
        </div> */}
        </div>
      </div>
    );
  }
}
