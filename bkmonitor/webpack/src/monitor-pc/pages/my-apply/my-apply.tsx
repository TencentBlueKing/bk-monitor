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

import QuickCreateSubscription from '../../components/quick-create-subscription/quick-create-subscription';

import SubscriptionDetail from './components/subscription-detail';

import './my-apply.scss';

enum Status {
  RUNNING = window.i18n.t('待审批'),
  SUCCESS = window.i18n.t('审批通过'),
  FAILED = window.i18n.t('审批驳回')
}

@Component({
  components: {
    SubscriptionDetail,
    QuickCreateSubscription
  }
})
class MyApply extends tsc<{}> {
  approvalStatus = 'ALL';
  searchValue = '';
  tableData = [];
  isTableLoading = false;
  isShowSideslider = false;
  isShowQCSSlider = false;
  detailInfo = {};
  handleGetSubscriptionID(subscription_id) {
    getReport({ subscription_id })
      .then(response => {
        this.detailInfo = response;
        this.isShowSideslider = true;
      })
      .catch(console.log);
  }

  get computedTableData() {
    return this.tableData
      .filter(item => {
        if (this.approvalStatus === 'ALL') {
          return item;
        }
        if (item.status === this.approvalStatus) {
          return item;
        }
      })
      .filter(item => {
        if (
          item.content_title.includes(this.searchValue) ||
          item.approval_sn.includes(this.searchValue) ||
          item.approvers.find(item => item.includes(this.searchValue)) ||
          item.create_time.includes(this.searchValue)
        ) {
          return item;
        }
      });
  }

  mounted() {
    this.isTableLoading = true;
    getApplyRecords()
      .then(response => {
        console.log(response);
        this.tableData = response;
      })
      .catch(console.log)
      .finally(() => {
        this.isTableLoading = false;
      });
  }

  render() {
    return (
      <div class='my-apply-container'>
        <div class='header-container'>
          {/* 纯前端筛选即可 */}
          <div class='radio-container'>
            <div
              class={['radio', this.approvalStatus === 'ALL' && 'selected']}
              onClick={() => (this.approvalStatus = 'ALL')}
            >
              {this.$t('全部')}
            </div>
            <div
              class={['radio', this.approvalStatus === 'RUNNING' && 'selected']}
              onClick={() => (this.approvalStatus = 'RUNNING')}
            >
              <i class='circle RUNNING'></i>
              {this.$t('待审批')}
            </div>
            <div
              class={['radio', this.approvalStatus === 'SUCCESS' && 'selected']}
              onClick={() => (this.approvalStatus = 'SUCCESS')}
            >
              <i class='circle SUCCESS'></i>
              {this.$t('审批通过')}
            </div>
            <div
              class={['radio', this.approvalStatus === 'FAILED' && 'selected']}
              onClick={() => (this.approvalStatus = 'FAILED')}
            >
              <i class='circle FAILED'></i>
              {this.$t('审批驳回')}
            </div>
          </div>

          <bk-input
            v-model={this.searchValue}
            placeholder={this.$t('搜索')}
            right-icon='bk-icon icon-search'
            style={{ width: '320px' }}
          ></bk-input>
        </div>

        <bk-table
          data={this.computedTableData}
          v-bkloading={{
            isLoading: this.isTableLoading
          }}
          style={{ marginTop: '24px' }}
        >
          <bk-table-column
            label={this.$t('单号')}
            prop='approval_sn'
          ></bk-table-column>

          <bk-table-column
            label={this.$t('邮件标题')}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <bk-button
                    text
                    theme='primary'
                    onClick={() => {
                      this.handleGetSubscriptionID(row.subscription_id);
                    }}
                  >
                    {row.content_title}
                  </bk-button>
                );
              }
            }}
          ></bk-table-column>

          {/* 这个要重新取值，具体看接口返回直取 */}
          <bk-table-column
            label={this.$t('当前步骤')}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{row.approval_step[0].name}</div>;
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('当前处理人')}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{row.approvers.toString()}</div>;
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('单据状态')}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <i class={['circle', row.status]}></i>
                    {Status[row.status]}
                  </div>
                );
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('提单时间')}
            prop='create_time'
          ></bk-table-column>

          <bk-table-column
            label={this.$t('操作')}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <bk-button
                    text
                    title='primary'
                    onClick={() => {
                      window.open(row.approval_url, '_blank');
                    }}
                  >
                    {this.$t('查看单据详情')}
                    <i
                      class='icon-monitor icon-mc-link'
                      style={{ marginLeft: '5px' }}
                    ></i>
                  </bk-button>
                );
              }
            }}
          ></bk-table-column>
        </bk-table>

        <bk-sideslider
          is-show={this.isShowSideslider}
          width='640'
          ext-cls='my-apply-slider'
          transfer
          before-close={() => {
            this.isShowSideslider = false;
          }}
        >
          <div
            class='title-container'
            slot='header'
          >
            <span class='title'>{this.$t('订阅详情')}</span>
            <span class='sub-title'>-&nbsp;{this.detailInfo?.name}</span>
          </div>

          <div slot='content'>
            <SubscriptionDetail detailInfo={this.detailInfo}></SubscriptionDetail>
          </div>
        </bk-sideslider>

        {/* 测试代码 */}
        {/* <QuickCreateSubscription v-model={this.isShowQCSSlider}></QuickCreateSubscription>
        <bk-button
          onClick={() => {
            this.isShowQCSSlider = true;
          }}
        ></bk-button> */}
      </div>
    );
  }
}
export default ofType().convert(MyApply);
