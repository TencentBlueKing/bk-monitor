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
import { Component } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';
import { getApplyRecords, getReport } from '@api/modules/new_report';
import dayjs from 'dayjs';

import QueryTypeRadio from '../my-subscription/components/query-type-radio';
import { ApplyStatus } from '../my-subscription/mapping';
import { MyApplicationQueryType } from '../my-subscription/types';
import { getDefaultReportData } from '../my-subscription/utils';

import ReportDetail from './components/report-detail';

import './my-apply.scss';

@Component({
  components: {
    ReportDetail,
    QueryTypeRadio
  }
})
class MyApply extends tsc<{}> {
  approvalStatus: MyApplicationQueryType = 'ALL';
  searchValue = '';
  tableData = [];
  isTableLoading = false;
  isShowSideslider = false;
  isShowQCSSlider = false;
  detailInfo = getDefaultReportData();
  tabList = [
    { type: 'ALL', text: '全部', iconClass: 'ALL', isShow: false },
    { type: 'RUNNING', text: '待审批', iconClass: 'RUNNING' },
    { type: 'SUCCESS', text: '审批通过', iconClass: 'SUCCESS' },
    { type: 'FAILED', text: '审批驳回', iconClass: 'FAILED' }
  ];
  handleGetSubscriptionID(report_id) {
    getReport({ report_id }).then(response => {
      this.detailInfo = response;
      this.isShowSideslider = true;
    });
  }

  /** 该列表筛选为纯前端筛选 */
  get computedTableData() {
    return this.tableData
      .filter(item => {
        return this.approvalStatus === 'ALL' || item.status === this.approvalStatus;
      })
      .filter(item => {
        return (
          item.content_title.includes(this.searchValue) ||
          item.approval_sn.includes(this.searchValue) ||
          item.approvers.find(item => item.includes(this.searchValue)) ||
          item.create_time.includes(this.searchValue)
        );
      });
  }

  mounted() {
    this.isTableLoading = true;
    getApplyRecords()
      .then(response => {
        this.tableData = response;
      })
      .finally(() => {
        this.isTableLoading = false;
      });
  }

  render() {
    return (
      <div class='my-apply-container'>
        <div>
          <div class='header-container'>
            {/* 纯前端筛选即可 */}
            <QueryTypeRadio
              v-model={this.approvalStatus}
              tabList={this.tabList}
            ></QueryTypeRadio>

            <bk-input
              v-model={this.searchValue}
              placeholder={this.$t('搜索')}
              right-icon='bk-icon icon-search'
              style='width: 320px;'
            ></bk-input>
          </div>

          <bk-table
            data={this.computedTableData}
            v-bkloading={{
              isLoading: this.isTableLoading
            }}
            style='margin-top: 24px;'
          >
            <bk-table-column
              label={this.$t('单号')}
              prop='approval_sn'
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{row.approval_sn}</div>;
                }
              }}
            ></bk-table-column>

            <bk-table-column
              label={this.$t('邮件标题')}
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div
                      style='padding: 14px 0;'
                      v-bk-overflow-tips
                    >
                      <bk-button
                        text
                        theme='primary'
                        onClick={() => {
                          this.handleGetSubscriptionID(row.report_id);
                        }}
                        style='height: auto;'
                      >
                        {row.content_title}
                      </bk-button>
                    </div>
                  );
                }
              }}
            ></bk-table-column>

            {/* 这个要重新取值，具体看接口返回直取 */}
            <bk-table-column
              label={this.$t('当前步骤')}
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{row.approval_step?.[0]?.name || '--'}</div>;
                }
              }}
            ></bk-table-column>

            <bk-table-column
              label={this.$t('当前处理人')}
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{row.approvers?.toString?.()}</div>;
                }
              }}
            ></bk-table-column>

            <bk-table-column
              label={this.$t('单据状态')}
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div
                      style='display: flex; align-items: center;'
                      v-bk-overflow-tips
                    >
                      <i class={['circle', row.status]}></i>
                      {ApplyStatus[row.status]}
                    </div>
                  );
                }
              }}
            ></bk-table-column>

            <bk-table-column
              label={this.$t('提单时间')}
              prop='create_time'
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{dayjs(row.create_time).format('YYYY-MM-DD HH:mm:ss')}</div>;
                }
              }}
            ></bk-table-column>

            <bk-table-column
              label={this.$t('操作')}
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div style='padding: 14px 0;'>
                      <bk-button
                        text
                        onClick={() => {
                          window.open(row.approval_url, '_blank');
                        }}
                        style='height: auto;'
                      >
                        {this.$t('查看单据详情')}
                        <i
                          class='icon-monitor icon-mc-link'
                          style='margin-left: 5px;'
                        ></i>
                      </bk-button>
                    </div>
                  );
                }
              }}
            ></bk-table-column>
          </bk-table>
        </div>

        <bk-sideslider
          is-show={this.isShowSideslider}
          width='640'
          ext-cls='my-apply-slider'
          transfer
          quick-close
          before-close={() => {
            this.isShowSideslider = false;
          }}
        >
          <div
            class='title-container'
            slot='header'
          >
            <span class='title'>{this.$t('订阅详情')}</span>
            <span class='sub-title'>-&nbsp;{this.detailInfo.name}</span>
          </div>

          <div slot='content'>
            <ReportDetail detailInfo={this.detailInfo}></ReportDetail>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
export default ofType().convert(MyApply);
