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

import { listIndexByHost } from '../../../../monitor-api/modules/alert_events';
import CommonTable from '../../../../monitor-pc/pages/monitor-k8s/components/common-table';
import { ITableColumn } from '../../../../monitor-pc/pages/monitor-k8s/typings';
import TipMsg from '../../setting/components/tip-msg';

import { IDetail } from './type';

import './log-info.scss';

/* 来源方式 */
const collectorScenarioIdMap = {
  log: window.i18n.tc('采集接入'),
  bkdata: window.i18n.tc('计算平台'),
  es: window.i18n.tc('第三方ES')
};

type TStatus = 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PARTFAILED' | 'TERMINATED' | 'UNKNOWN' | 'PREPARE';

const logTableColumns: ITableColumn[] = [
  { id: 'index_set_name', name: window.i18n.tc('索引集名称'), type: 'string' },
  { id: 'index_set_scenario_id', name: window.i18n.tc('索引来源'), type: 'scoped_slots' },
  { id: 'status', name: window.i18n.tc('数据状态'), type: 'scoped_slots' },
  { id: 'retention', name: window.i18n.tc('过期时间'), type: 'scoped_slots' },
  { id: 'operate', name: window.i18n.tc('操作'), type: 'scoped_slots' }
];

interface IProps {
  show?: boolean;
  detail?: IDetail;
}

@Component
export default class LogInfo extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;

  /* 目标ip */
  ip = '';
  cloudId = '';
  /* 所有数据 */
  allData = [];
  /* 表格数据 */
  tableData = [];
  pagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  loading = false;

  @Watch('show')
  handleShow(show: boolean) {
    if (show) {
      if (!this.allData.length) {
        this.init();
      }
    }
  }

  /* 初始化 */
  async init() {
    this.loading = true;
    const ipMap = ['bk_target_ip', 'ip'];
    const cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
    this.ip = this.detail.dimensions.find(item => ipMap.includes(item.key)).value;
    const cloudId = this.detail.dimensions.find(item => cloudIdMap.includes(item.key)).value;
    this.cloudId = cloudId;
    this.allData = await listIndexByHost({
      ip: this.ip,
      bk_cloud_id: cloudId,
      bk_biz_id: this.detail.bk_biz_id
    }).catch(() => []);
    this.pagination.count = this.allData.length;
    this.pagination.limit = 10;
    this.pagination.current = 1;
    this.getTableData();
    this.loading = false;
  }

  /* 分页数据 */
  getTableData() {
    this.tableData = this.allData.slice(
      (this.pagination.current - 1) * this.pagination.limit,
      this.pagination.current * this.pagination.limit
    );
  }

  handlePageChange(v: number) {
    this.pagination.current = v;
    this.getTableData();
  }

  handleLimitChange(v: number) {
    this.pagination.current = 1;
    this.pagination.limit = v;
    this.getTableData();
  }

  /* 跳转到日志平台 */
  handleClick(row) {
    const startTime = encodeURIComponent(dayjs.tz(this.detail.begin_time * 1000).format('YYYY-MM-DD HH:mm:ss'));
    const endTime = encodeURIComponent(
      dayjs.tz(this.detail.end_time ? this.detail.end_time * 1000 : new Date().getTime()).format('YYYY-MM-DD HH:mm:ss')
    );
    const host = window.bk_log_search_url || window.bklogsearch_host;
    let hostScopes = null;
    if (this.ip) {
      hostScopes = {
        target_nodes: [
          {
            ip: this.ip,
            bk_cloud_id: this.cloudId,
            bk_supplier_id: ''
          }
        ],
        target_node_type: 'INSTANCE'
      };
    }
    const url = `${host}#/retrieve/${row.index_set_id}?bizId=${
      this.detail.bk_biz_id || this.$store.getters.bizId
    }&keyword=${encodeURIComponent('*')}&start_time=${startTime}&end_time=${endTime}${
      hostScopes ? `&host_scopes=${encodeURIComponent(JSON.stringify(hostScopes))}` : ''
    }`;
    window.open(url);
  }

  getStatusLabel(status: TStatus, text: string) {
    return (
      <span class='run-status'>
        <span class={['status', status]}></span>
        <span class='status-msg'>{text || ''}</span>
      </span>
    );
  }

  handleToLog() {
    const host = window.bk_log_search_url || window.bklogsearch_host;
    window.open(`${host}#/retrieve/?bizId=${this.detail.bk_biz_id || this.$store.getters.bizId}`);
  }

  render() {
    return (
      <div
        class={['event-detail-log-info-component', { show: this.show }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.allData.length ? (
          <TipMsg msg={this.$t('通过目标{0}，找到日志检索集可以进行检索', [this.ip]) as string}></TipMsg>
        ) : undefined}
        {this.allData.length ? (
          <CommonTable
            class='log-table'
            columns={logTableColumns}
            data={this.tableData}
            checkable={false}
            hasColnumSetting={false}
            pagination={this.pagination}
            scopedSlots={{
              index_set_scenario_id: row =>
                collectorScenarioIdMap[row.index_set_scenario_id] || row.index_set_scenario_id,
              status: row => this.getStatusLabel(row.status, row.status_name),
              retention: row => (row.retention ? `${row.retention}${this.$t('天')}` : '--'),
              operate: row => (
                <span
                  class='link'
                  onClick={() => this.handleClick(row)}
                >
                  {this.$t('检索')}
                </span>
              )
            }}
            onPageChange={this.handlePageChange}
            onLimitChange={this.handleLimitChange}
          ></CommonTable>
        ) : (
          <div class='no-data'>
            <bk-exception type='building'>
              <div class='no-data-msg'>
                <span class='title'>{this.$t('通过目标{0}，找不到日志索引集', [this.ip])}</span>
                <bk-button
                  class='btn'
                  theme='primary'
                  onClick={() => this.handleToLog()}
                >
                  {this.$t('前往日志检索')}
                </bk-button>
              </div>
            </bk-exception>
          </div>
        )}
      </div>
    );
  }
}
